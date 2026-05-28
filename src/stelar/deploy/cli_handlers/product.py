"""CLI adapter for product specification generation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..operations import CommandError
from .lakespec import register_lakespec_commands
from ..operations.minimal_product import (
    InferredStorageClasses,
    MinimalProductConfig,
    MinimalSecretValues,
    build_generated_secret_report,
    build_minimal_product,
    default_secret_report_path,
    generate_minimal_secret_values,
    infer_storage_classes_from_cluster,
    write_secret_report,
    write_yaml,
)


def register_product_commands(app: typer.Typer) -> None:
    """Register product generation commands."""
    product_app = typer.Typer(help="Create and manage product specifications")
    product_app.command("init-minimal")(init_minimal_product_command)
    register_lakespec_commands(product_app)
    app.add_typer(product_app, name="product")


def init_minimal_product_command(
    output: Annotated[
        Path,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Product YAML file to create",
        ),
    ] = Path("product.yaml"),
    generate_secret_values: Annotated[
        bool,
        typer.Option(
            "--generate-secret-values",
            help="Generate secret values instead of prompting for them",
        ),
    ] = False,
    secret_values_output: Annotated[
        Path | None,
        typer.Option(
            "--secret-values-output",
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="YAML file for generated secret values",
        ),
    ] = None,
    infer_storage_from_cluster: Annotated[
        bool,
        typer.Option(
            "--infer-storage-from-cluster",
            help="Infer StorageClass values from the active kubectl context",
        ),
    ] = False,
    context: Annotated[
        str | None,
        typer.Option(
            "--context",
            help="Kubectl context to use with --infer-storage-from-cluster",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing output files"),
    ] = False,
) -> None:
    """Interactively generate a minimal STELAR product."""
    try:
        secret_report_path = (
            secret_values_output or default_secret_report_path(output)
            if generate_secret_values
            else None
        )
        _validate_output_path(output, force=force)
        if secret_report_path is not None:
            _validate_distinct_paths(output, secret_report_path)
            _validate_output_path(secret_report_path, force=force)

        inferred_storage = (
            infer_storage_classes_from_cluster(context)
            if infer_storage_from_cluster
            else None
        )
        if inferred_storage is not None:
            _echo_inferred_storage(inferred_storage)

        config = _prompt_minimal_product_config(
            generate_secret_values=generate_secret_values,
            inferred_storage=inferred_storage,
        )
        product = build_minimal_product(config)

        write_yaml(output, product, force=force)
        typer.echo(f"Wrote minimal product: {output}")

        if secret_report_path is not None:
            secret_report = build_generated_secret_report(product, output)
            write_secret_report(secret_report_path, secret_report, force=force)
            typer.echo(f"Wrote generated secret values: {secret_report_path}")
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _prompt_minimal_product_config(
    *,
    generate_secret_values: bool,
    inferred_storage: InferredStorageClasses | None,
) -> MinimalProductConfig:
    scheme = _prompt_choice("URL scheme", ("http", "https"), default="https")
    cluster_issuer = (
        _prompt_required("ClusterIssuer name", default="letsencrypt-prod")
        if scheme == "https"
        else None
    )

    if inferred_storage is None:
        dynamic_storage_class = _prompt_required(
            "Dynamic storage class",
            default="longhorn",
        )
        provisioning_storage_class = _prompt_required(
            "PVC/provisioning storage class",
            default="csi-hostpath-sc",
        )
    else:
        dynamic_storage_class = inferred_storage.dynamic_storage_class
        provisioning_storage_class = inferred_storage.provisioning_storage_class

    secrets = (
        generate_minimal_secret_values()
        if generate_secret_values
        else _prompt_secret_values()
    )

    return MinimalProductConfig(
        namespace=_prompt_required("Kubernetes namespace", default="stelar-dev"),
        root_domain=_prompt_required("Public root domain", default="minikube"),
        primary_subdomain=_prompt_required("Primary app subdomain", default="klms"),
        keycloak_subdomain=_prompt_required("Keycloak subdomain", default="kc"),
        minio_api_subdomain=_prompt_required("MinIO API subdomain", default="minio"),
        registry_subdomain=_prompt_required("Registry subdomain", default="img"),
        scheme=scheme,
        cluster_issuer=cluster_issuer,
        dynamic_storage_class=dynamic_storage_class,
        provisioning_storage_class=provisioning_storage_class,
        insecure_minio_client=_prompt_choice(
            "Insecure MinIO client",
            ("true", "false"),
            default="true",
        ),
        smtp_server=_prompt_required("SMTP server", default="stelar.gr"),
        smtp_port=_prompt_required("SMTP port", default="465"),
        smtp_username=_prompt_required("SMTP username", default="user"),
        secrets=secrets,
    )


def _prompt_secret_values() -> MinimalSecretValues:
    return MinimalSecretValues(
        postgres_db_password=_prompt_secret("Postgres admin DB password"),
        ckan_db_password=_prompt_secret("CKAN DB password"),
        datastore_db_password=_prompt_secret("Datastore DB password"),
        keycloak_db_password=_prompt_secret("Keycloak DB password"),
        quay_db_password=_prompt_secret("Quay DB password"),
        smtp_password=_prompt_secret("SMTP password"),
        api_session_secret_key=_prompt_secret("STELAR API session secret"),
        ckan_admin_password=_prompt_secret("CKAN admin password"),
        ckan_session_key=_prompt_secret("CKAN session key"),
        ckan_jwt_key=_prompt_secret("CKAN JWT key"),
        keycloak_root_password=_prompt_secret("Keycloak admin/root password"),
        minio_root_password=_prompt_secret("MinIO root password"),
    )


def _prompt_required(label: str, *, default: str | None = None) -> str:
    while True:
        value = typer.prompt(label, default=default).strip()
        if value:
            return value
        typer.echo(f"{label} cannot be empty", err=True)


def _prompt_secret(label: str) -> str:
    while True:
        value = typer.prompt(
            label,
            hide_input=True,
            confirmation_prompt=True,
        )
        if value:
            return value
        typer.echo(f"{label} cannot be empty", err=True)


def _prompt_choice(label: str, choices: tuple[str, ...], *, default: str) -> str:
    choice_list = "/".join(choices)
    while True:
        value = typer.prompt(f"{label} [{choice_list}]", default=default).strip()
        if value in choices:
            return value
        typer.echo(f"{label} must be one of: {choice_list}", err=True)


def _echo_inferred_storage(inferred_storage: InferredStorageClasses) -> None:
    typer.echo(
        "Inferred storage classes from "
        f"{inferred_storage.context!r}: "
        f"dynamic={inferred_storage.dynamic_storage_class!r}, "
        f"pvc={inferred_storage.provisioning_storage_class!r}"
    )


def _validate_output_path(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise CommandError(f"{path} already exists; use --force to overwrite it")


def _validate_distinct_paths(left: Path, right: Path) -> None:
    if left == right:
        raise CommandError("Product output and secret-values output must differ")
