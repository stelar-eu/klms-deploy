"""Build minimal product specifications from validated input."""

from __future__ import annotations

import secrets

from .common import CommandError, JsonObject
from .minimal_product_types import (
    MINIMAL_PASSWORD_FIELDS,
    MinimalProductConfig,
    MinimalSecretValues,
)
from .secret_resources import validate_password


def generate_minimal_secret_values() -> MinimalSecretValues:
    """Generate product secret values with OS-backed cryptographic randomness."""
    return MinimalSecretValues(
        postgres_db_password=_secret_token(),
        ckan_db_password=_secret_token(),
        datastore_db_password=_secret_token(),
        keycloak_db_password=_secret_token(),
        quay_db_password=_secret_token(),
        smtp_password=_secret_token(),
        api_session_secret_key=_secret_token(48),
        ckan_admin_password=_secret_token(),
        ckan_session_key=_secret_token(48),
        ckan_jwt_key=f"string:{_secret_token()}",
        keycloak_root_password=_secret_token(),
        minio_root_password=_secret_token(),
    )


def build_minimal_product(config: MinimalProductConfig) -> JsonObject:
    """Build the minimal product spec accepted by the feature model."""
    scheme = _normalized_scheme(config.scheme)
    _validate_minimal_passwords(config.secrets)
    insecure_minio_client = _normalized_minio_insecure_value(
        scheme,
        config.insecure_minio_client,
    )
    # The minimal generator deliberately supports only the two low-friction
    # paths: plain HTTP/no_tls or HTTPS/cert_manager. Manual TLS needs explicit
    # secret names and certificate files, so it remains a custom product flow.
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
        "namespace": config.namespace,
        "dynamicStorageClass": config.dynamic_storage_class,
        "dynamic_volume_storage_class": config.provisioning_storage_class,
        "SCHEME": scheme,
        "ROOT_DOMAIN": config.root_domain,
        "PRIMARY_SUBDOMAIN": config.primary_subdomain,
        "optional_components": [],
        "cluster": [],
        "postgres": {
            "volume": ["pvc"],
            "POSTGRES_DB_PASSWORD": config.secrets.postgres_db_password,
            "POSTGRES_DB_PASSWORD_SECRET_NAME": "postgresdb-secret",
            "CKAN_DB_PASSWORD": config.secrets.ckan_db_password,
            "CKAN_DB_PASSWORD_SECRET_NAME": "ckandb-secret",
            "DATASTORE_DB_PASSWORD": config.secrets.datastore_db_password,
            "DATASTORE_DB_PASSWORD_SECRET_NAME": "datastoredb-secret",
            "KEYCLOAK_DB_PASSWORD": config.secrets.keycloak_db_password,
            "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "keycloakdb-secret",
            "QUAY_DB_PASSWORD": config.secrets.quay_db_password,
            "QUAY_DB_PASSWORD_SECRET_NAME": "quaydb-secret",
        },
        "api": {
            "SMTP_SERVER": config.smtp_server,
            "SMTP_PORT": config.smtp_port,
            "SMTP_USERNAME": config.smtp_username,
            "SMTP_PASSWORD": config.secrets.smtp_password,
            "SMTP_PASSWORD_SECRET_NAME": "smtpapi-secret",
            "SESSION_SECRET_KEY": config.secrets.api_session_secret_key,
            "SESSION_SECRET_KEY_SECRET_NAME": "session-secret-key",
        },
        "ckan": {
            "CKAN_ADMIN_PASSWORD": config.secrets.ckan_admin_password,
            "CKAN_ADMIN_PASSWORD_SECRET_NAME": "ckanadmin-secret",
            "CKAN_SESSION_KEY": config.secrets.ckan_session_key,
            "CKAN_JWT_KEY": config.secrets.ckan_jwt_key,
            "CKAN_AUTH_SECRET_NAME": "ckan-auth-secret",
        },
        "keycloak": {
            "SUBDOMAIN": config.keycloak_subdomain,
            "KEYCLOAK_ROOT_PASSWORD": config.secrets.keycloak_root_password,
            "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "keycloakroot-secret",
        },
        "minio": {
            "volume": ["pvc"],
            "API_SUBDOMAIN": config.minio_api_subdomain,
            "API_DOMAIN": minio_api_domain,
            "CONSOLE_DOMAIN": f"{primary_domain}/s3",
            "S3_CONSOLE_URL": f"{primary_domain}/s3/login",
            "INSECURE_MC_CLIENT": insecure_minio_client,
            "MINIO_ROOT_PASSWORD": config.secrets.minio_root_password,
            "MINIO_ROOT_PASSWORD_SECRET_NAME": "minioroot-secret",
        },
        "solr": {
            "volume": ["pvc"],
        },
        "quay": {
            "SUBDOMAIN": config.registry_subdomain,
        },
        "ingress": ingress,
    }
    return {"spec": spec}


def _validate_minimal_passwords(secrets: MinimalSecretValues) -> None:
    for attribute, source in MINIMAL_PASSWORD_FIELDS.items():
        validate_password(getattr(secrets, attribute), source=source)


def _secret_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


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
