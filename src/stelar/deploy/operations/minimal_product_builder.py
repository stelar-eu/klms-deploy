"""Build minimal product specifications from validated input."""

from __future__ import annotations

from dataclasses import asdict

from .common import CommandError, JsonObject
from .minimal_product_types import (
    DEFAULT_MINIMAL_SECRET_NAMES,
    MinimalProductConfig,
    MinimalSecretNames,
)

_SECRET_NAME_FIELDS = {
    "postgres": {
        "postgres_db_password_secret_name": "POSTGRES_DB_PASSWORD_SECRET_NAME",
        "ckan_db_password_secret_name": "CKAN_DB_PASSWORD_SECRET_NAME",
        "datastore_db_password_secret_name": "DATASTORE_DB_PASSWORD_SECRET_NAME",
        "keycloak_db_password_secret_name": "KEYCLOAK_DB_PASSWORD_SECRET_NAME",
        "quay_db_password_secret_name": "QUAY_DB_PASSWORD_SECRET_NAME",
    },
    "api": {
        "smtp_password_secret_name": "SMTP_PASSWORD_SECRET_NAME",
        "api_session_secret_key_secret_name": "SESSION_SECRET_KEY_SECRET_NAME",
    },
    "ckan": {
        "ckan_admin_password_secret_name": "CKAN_ADMIN_PASSWORD_SECRET_NAME",
        "ckan_auth_secret_name": "CKAN_AUTH_SECRET_NAME",
    },
    "keycloak": {
        "keycloak_root_password_secret_name": "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME",
    },
    "minio": {
        "minio_root_password_secret_name": "MINIO_ROOT_PASSWORD_SECRET_NAME",
    },
}


def build_minimal_product(config: MinimalProductConfig) -> JsonObject:
    """Build the minimal product spec accepted by the feature model."""
    scheme = _normalized_scheme(config.scheme)
    insecure_minio_client = _normalized_minio_insecure_value(
        scheme,
        config.insecure_minio_client,
    )
    # The minimal generator deliberately supports only the two low-friction
    # paths: plain HTTP/no_tls or HTTPS/cert_manager. Manual TLS needs explicit
    # certificate files, so it remains a custom product flow.
    ingress: JsonObject = {"ingress_controller": ["nginx"], "tls": ["no_tls"]}
    if scheme == "https":
        if not config.cluster_issuer:
            raise CommandError(
                "ClusterIssuer name is required when URL scheme is https"
            )
        ingress["tls"] = ["cert_manager"]
        ingress["cert_manager"] = {"ClusterIssuer": config.cluster_issuer}

    minio_api_domain = (
        f"{scheme}://{config.minio_api_subdomain}.{config.root_domain}"
    )
    primary_domain = f"{scheme}://{config.primary_subdomain}.{config.root_domain}"

    spec: JsonObject = {
        "dynamicStorageClass": config.dynamic_storage_class,
        "dynamic_volume_storage_class": config.provisioning_storage_class,
        "SCHEME": scheme,
        "ROOT_DOMAIN": config.root_domain,
        "PRIMARY_SUBDOMAIN": config.primary_subdomain,
        "optional_components": [],
        "cluster": [],
        "postgres": {"volume": ["pvc"]},
        "api": {
            "SMTP_SERVER": config.smtp_server,
            "SMTP_PORT": config.smtp_port,
            "SMTP_USERNAME": config.smtp_username,
        },
        "ckan": {},
        "keycloak": {
            "SUBDOMAIN": config.keycloak_subdomain,
        },
        "minio": {
            "volume": ["pvc"],
            "API_SUBDOMAIN": config.minio_api_subdomain,
            "API_DOMAIN": minio_api_domain,
            "CONSOLE_DOMAIN": f"{primary_domain}/s3",
            "S3_CONSOLE_URL": f"{primary_domain}/s3/login",
            "INSECURE_MC_CLIENT": insecure_minio_client,
        },
        "solr": {
            "volume": ["pvc"],
        },
        "quay": {
            "SUBDOMAIN": config.registry_subdomain,
        },
        "ingress": ingress,
    }
    _apply_secret_name_overrides(spec, config.secret_names)
    return {"spec": spec}


def _apply_secret_name_overrides(
    spec: JsonObject,
    secret_names: MinimalSecretNames | None,
) -> None:
    if secret_names is None:
        return

    values = asdict(secret_names)
    for section, fields in _SECRET_NAME_FIELDS.items():
        section_config = spec.setdefault(section, {})
        for attribute, product_key in fields.items():
            value = values[attribute].strip()
            if not value:
                raise CommandError(f"{product_key} cannot be empty")
            if value != DEFAULT_MINIMAL_SECRET_NAMES[attribute]:
                section_config[product_key] = value


def _normalized_scheme(scheme: str) -> str:
    if scheme not in {"http", "https"}:
        raise CommandError("Scheme must be either http or https")
    return scheme


def _normalized_minio_insecure_value(scheme: str, value: str) -> str:
    # HTTP deployments must force the MinIO client into insecure mode; accepting
    # a user-provided false here would generate a product that renders but fails.
    if scheme == "http":
        return "true"
    if value not in {"true", "false"}:
        raise CommandError("Insecure MinIO client must be either true or false")
    return value
