"""Typed data structures for minimal product generation."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MINIMAL_SECRET_NAMES = {
    "postgres_db_password_secret_name": "postgresdb-secret",
    "ckan_db_password_secret_name": "ckandb-secret",
    "datastore_db_password_secret_name": "datastoredb-secret",
    "keycloak_db_password_secret_name": "keycloakdb-secret",
    "quay_db_password_secret_name": "quaydb-secret",
    "smtp_password_secret_name": "smtpapi-secret",
    "api_session_secret_key_secret_name": "session-secret-key",
    "ckan_admin_password_secret_name": "ckanadmin-secret",
    "ckan_auth_secret_name": "ckan-auth-secret",
    "keycloak_root_password_secret_name": "keycloakroot-secret",
    "minio_root_password_secret_name": "minioroot-secret",
}


@dataclass(frozen=True)
class MinimalSecretNames:
    """Optional Kubernetes Secret name overrides for a minimal product."""

    postgres_db_password_secret_name: str
    ckan_db_password_secret_name: str
    datastore_db_password_secret_name: str
    keycloak_db_password_secret_name: str
    quay_db_password_secret_name: str
    smtp_password_secret_name: str
    api_session_secret_key_secret_name: str
    ckan_admin_password_secret_name: str
    ckan_auth_secret_name: str
    keycloak_root_password_secret_name: str
    minio_root_password_secret_name: str


@dataclass(frozen=True)
class MinimalProductConfig:
    """User-controlled values for a minimal STELAR product."""

    root_domain: str
    primary_subdomain: str
    keycloak_subdomain: str
    minio_api_subdomain: str
    registry_subdomain: str
    scheme: str
    cluster_issuer: str | None
    dynamic_storage_class: str
    provisioning_storage_class: str
    insecure_minio_client: str
    smtp_server: str
    smtp_port: str
    smtp_username: str
    secret_names: MinimalSecretNames | None = None


@dataclass(frozen=True)
class InferredStorageClasses:
    """Storage class names inferred from a Kubernetes context."""

    context: str
    dynamic_storage_class: str
    provisioning_storage_class: str
