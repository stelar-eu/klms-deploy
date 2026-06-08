"""Typed data structures for minimal product generation."""

from __future__ import annotations

from dataclasses import dataclass


MINIMAL_PASSWORD_FIELDS = {
    "postgres_db_password": "postgres.POSTGRES_DB_PASSWORD",
    "ckan_db_password": "postgres.CKAN_DB_PASSWORD",
    "datastore_db_password": "postgres.DATASTORE_DB_PASSWORD",
    "keycloak_db_password": "postgres.KEYCLOAK_DB_PASSWORD",
    "quay_db_password": "postgres.QUAY_DB_PASSWORD",
    "smtp_password": "api.SMTP_PASSWORD",
    "ckan_admin_password": "ckan.CKAN_ADMIN_PASSWORD",
    "keycloak_root_password": "keycloak.KEYCLOAK_ROOT_PASSWORD",
    "minio_root_password": "minio.MINIO_ROOT_PASSWORD",
}


@dataclass(frozen=True)
class MinimalSecretValues:
    """Secret values required by the minimal STELAR product."""

    postgres_db_password: str
    ckan_db_password: str
    datastore_db_password: str
    keycloak_db_password: str
    quay_db_password: str
    smtp_password: str
    api_session_secret_key: str
    ckan_admin_password: str
    ckan_session_key: str
    ckan_jwt_key: str
    keycloak_root_password: str
    minio_root_password: str


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
    secrets: MinimalSecretValues


@dataclass(frozen=True)
class InferredStorageClasses:
    """Storage class names inferred from a Kubernetes context."""

    context: str
    dynamic_storage_class: str
    provisioning_storage_class: str
