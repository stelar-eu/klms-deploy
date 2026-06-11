"""CLI helpers for interactive minimal lake product creation."""

from __future__ import annotations

import typer

from ..operations.minimal_product import (
    DEFAULT_MINIMAL_SECRET_NAMES,
    InferredStorageClasses,
    MinimalProductConfig,
    MinimalSecretNames,
    build_minimal_product,
)
from .prompts import (
    prompt_choice as _prompt_choice,
    prompt_required as _prompt_required,
)


def prompt_minimal_product(
    *,
    custom_secret_names: bool,
    inferred_storage: InferredStorageClasses | None,
) -> dict:
    """Prompt for a minimal product and return the product object."""
    config = _prompt_minimal_product_config(
        custom_secret_names=custom_secret_names,
        inferred_storage=inferred_storage,
    )
    return build_minimal_product(config)


def _prompt_minimal_product_config(
    *,
    custom_secret_names: bool,
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
        secret_names=_prompt_secret_names() if custom_secret_names else None,
    )


def _prompt_secret_names() -> MinimalSecretNames:
    typer.echo("Secret name overrides; press Enter to keep each default.")
    return MinimalSecretNames(
        postgres_db_password_secret_name=_prompt_secret_name(
            "Postgres admin DB Secret name",
            "postgres_db_password_secret_name",
        ),
        ckan_db_password_secret_name=_prompt_secret_name(
            "CKAN DB Secret name",
            "ckan_db_password_secret_name",
        ),
        datastore_db_password_secret_name=_prompt_secret_name(
            "Datastore DB Secret name",
            "datastore_db_password_secret_name",
        ),
        keycloak_db_password_secret_name=_prompt_secret_name(
            "Keycloak DB Secret name",
            "keycloak_db_password_secret_name",
        ),
        quay_db_password_secret_name=_prompt_secret_name(
            "Quay DB Secret name",
            "quay_db_password_secret_name",
        ),
        smtp_password_secret_name=_prompt_secret_name(
            "SMTP password Secret name",
            "smtp_password_secret_name",
        ),
        api_session_secret_key_secret_name=_prompt_secret_name(
            "API session Secret name",
            "api_session_secret_key_secret_name",
        ),
        ckan_admin_password_secret_name=_prompt_secret_name(
            "CKAN admin password Secret name",
            "ckan_admin_password_secret_name",
        ),
        ckan_auth_secret_name=_prompt_secret_name(
            "CKAN auth Secret name",
            "ckan_auth_secret_name",
        ),
        keycloak_root_password_secret_name=_prompt_secret_name(
            "Keycloak root password Secret name",
            "keycloak_root_password_secret_name",
        ),
        minio_root_password_secret_name=_prompt_secret_name(
            "MinIO root password Secret name",
            "minio_root_password_secret_name",
        ),
    )


def _prompt_secret_name(label: str, key: str) -> str:
    return _prompt_required(label, default=DEFAULT_MINIMAL_SECRET_NAMES[key])


def echo_inferred_storage(inferred_storage: InferredStorageClasses) -> None:
    typer.echo(
        "Inferred storage classes from "
        f"{inferred_storage.context!r}: "
        f"dynamic={inferred_storage.dynamic_storage_class!r}, "
        f"pvc={inferred_storage.provisioning_storage_class!r}"
    )
