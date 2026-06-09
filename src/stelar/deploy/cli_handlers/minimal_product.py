"""CLI helpers for interactive minimal lake product creation."""

from __future__ import annotations

import typer

from ..operations.minimal_product import (
    InferredStorageClasses,
    MinimalProductConfig,
    MinimalSecretValues,
    build_minimal_product,
    generate_minimal_secret_values,
)
from ..operations.secret_resources import PASSWORD_MIN_LENGTH
from .prompts import (
    prompt_choice as _prompt_choice,
    prompt_required as _prompt_required,
    prompt_secret as _prompt_secret,
)


def prompt_minimal_product(
    *,
    manual_secrets: bool,
    inferred_storage: InferredStorageClasses | None,
) -> dict:
    """Prompt for a minimal product and return the product object."""
    config = _prompt_minimal_product_config(
        manual_secrets=manual_secrets,
        inferred_storage=inferred_storage,
    )
    return build_minimal_product(config)


def _prompt_minimal_product_config(
    *,
    manual_secrets: bool,
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
        _prompt_secret_values()
        if manual_secrets
        else generate_minimal_secret_values()
    )

    root_domain = _prompt_required("Public root domain", default="minikube")
    primary_subdomain = _prompt_required("Primary app subdomain", default="klms")
    keycloak_subdomain = _prompt_required("Keycloak subdomain", default="kc")
    minio_api_subdomain = _prompt_required("MinIO API subdomain", default="minio")
    registry_subdomain = _prompt_required("Registry subdomain", default="img")
    insecure_minio_client = (
        "true"
        if scheme == "http"
        else _prompt_choice(
            "Insecure MinIO client",
            ("true", "false"),
            default="true",
        )
    )

    return MinimalProductConfig(
        root_domain=root_domain,
        primary_subdomain=primary_subdomain,
        keycloak_subdomain=keycloak_subdomain,
        minio_api_subdomain=minio_api_subdomain,
        registry_subdomain=registry_subdomain,
        scheme=scheme,
        cluster_issuer=cluster_issuer,
        dynamic_storage_class=dynamic_storage_class,
        provisioning_storage_class=provisioning_storage_class,
        insecure_minio_client=insecure_minio_client,
        smtp_server=_prompt_required("SMTP server", default="stelar.gr"),
        smtp_port=_prompt_required("SMTP port", default="465"),
        smtp_username=_prompt_required("SMTP username", default="user"),
        secrets=secrets,
    )


def _prompt_secret_values() -> MinimalSecretValues:
    return MinimalSecretValues(
        postgres_db_password=_prompt_secret(
            "Postgres admin DB password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        ckan_db_password=_prompt_secret(
            "CKAN DB password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        datastore_db_password=_prompt_secret(
            "Datastore DB password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        keycloak_db_password=_prompt_secret(
            "Keycloak DB password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        quay_db_password=_prompt_secret(
            "Quay DB password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        smtp_password=_prompt_secret(
            "SMTP password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        api_session_secret_key=_prompt_secret("STELAR API session secret"),
        ckan_admin_password=_prompt_secret(
            "CKAN admin password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        ckan_session_key=_prompt_secret("CKAN session key"),
        ckan_jwt_key=_prompt_secret("CKAN JWT key"),
        keycloak_root_password=_prompt_secret(
            "Keycloak admin/root password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
        minio_root_password=_prompt_secret(
            "MinIO root password",
            min_length=PASSWORD_MIN_LENGTH,
        ),
    )


def echo_inferred_storage(inferred_storage: InferredStorageClasses) -> None:
    typer.echo(
        "Inferred storage classes from "
        f"{inferred_storage.context!r}: "
        f"dynamic={inferred_storage.dynamic_storage_class!r}, "
        f"pvc={inferred_storage.provisioning_storage_class!r}"
    )
