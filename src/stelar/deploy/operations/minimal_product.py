"""Minimal product generation for interactive CLI flows."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import yaml
from kubernetes import client as kube_client
from kubernetes import config as kube_config

from .common import CommandError, JsonObject


SECRET_FILE_MODE = 0o600
PREFERRED_STORAGE_CLASS_NAMES = (
    "longhorn",
    "csi-hostpath-sc",
    "local-path",
    "standard",
    "ebs-sc",
    "gp3",
    "gp2",
)


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

    namespace: str
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
            "INSECURE_MC_CLIENT": config.insecure_minio_client,
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


def build_generated_secret_report(
    product: JsonObject,
    product_path: Path,
) -> JsonObject:
    """Build a sidecar file with generated secret values for operator reference."""
    spec = product["spec"]
    return {
        "product": str(product_path),
        "warning": "This file contains generated secret values. Store it securely.",
        "secrets": {
            "postgres": {
                "POSTGRES_DB_PASSWORD_SECRET_NAME": spec["postgres"][
                    "POSTGRES_DB_PASSWORD_SECRET_NAME"
                ],
                "POSTGRES_DB_PASSWORD": spec["postgres"]["POSTGRES_DB_PASSWORD"],
                "CKAN_DB_PASSWORD_SECRET_NAME": spec["postgres"][
                    "CKAN_DB_PASSWORD_SECRET_NAME"
                ],
                "CKAN_DB_PASSWORD": spec["postgres"]["CKAN_DB_PASSWORD"],
                "DATASTORE_DB_PASSWORD_SECRET_NAME": spec["postgres"][
                    "DATASTORE_DB_PASSWORD_SECRET_NAME"
                ],
                "DATASTORE_DB_PASSWORD": spec["postgres"][
                    "DATASTORE_DB_PASSWORD"
                ],
                "KEYCLOAK_DB_PASSWORD_SECRET_NAME": spec["postgres"][
                    "KEYCLOAK_DB_PASSWORD_SECRET_NAME"
                ],
                "KEYCLOAK_DB_PASSWORD": spec["postgres"][
                    "KEYCLOAK_DB_PASSWORD"
                ],
                "QUAY_DB_PASSWORD_SECRET_NAME": spec["postgres"][
                    "QUAY_DB_PASSWORD_SECRET_NAME"
                ],
                "QUAY_DB_PASSWORD": spec["postgres"]["QUAY_DB_PASSWORD"],
            },
            "api": {
                "SMTP_PASSWORD_SECRET_NAME": spec["api"][
                    "SMTP_PASSWORD_SECRET_NAME"
                ],
                "SMTP_PASSWORD": spec["api"]["SMTP_PASSWORD"],
                "SESSION_SECRET_KEY_SECRET_NAME": spec["api"][
                    "SESSION_SECRET_KEY_SECRET_NAME"
                ],
                "SESSION_SECRET_KEY": spec["api"]["SESSION_SECRET_KEY"],
            },
            "ckan": {
                "CKAN_ADMIN_PASSWORD_SECRET_NAME": spec["ckan"][
                    "CKAN_ADMIN_PASSWORD_SECRET_NAME"
                ],
                "CKAN_ADMIN_PASSWORD": spec["ckan"]["CKAN_ADMIN_PASSWORD"],
                "CKAN_AUTH_SECRET_NAME": spec["ckan"]["CKAN_AUTH_SECRET_NAME"],
                "CKAN_SESSION_KEY": spec["ckan"]["CKAN_SESSION_KEY"],
                "CKAN_JWT_KEY": spec["ckan"]["CKAN_JWT_KEY"],
            },
            "keycloak": {
                "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": spec["keycloak"][
                    "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME"
                ],
                "KEYCLOAK_ROOT_PASSWORD": spec["keycloak"][
                    "KEYCLOAK_ROOT_PASSWORD"
                ],
            },
            "minio": {
                "MINIO_ROOT_PASSWORD_SECRET_NAME": spec["minio"][
                    "MINIO_ROOT_PASSWORD_SECRET_NAME"
                ],
                "MINIO_ROOT_PASSWORD": spec["minio"]["MINIO_ROOT_PASSWORD"],
            },
        },
    }


def write_yaml(path: Path, data: JsonObject, *, force: bool = False) -> None:
    """Write a YAML object, refusing to overwrite unless explicitly requested."""
    _ensure_parent_dir(path)
    if path.exists() and not force:
        raise CommandError(f"{path} already exists; use --force to overwrite it")
    try:
        path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CommandError(f"Could not write {path}: {exc}") from exc


def write_secret_report(path: Path, data: JsonObject, *, force: bool = False) -> None:
    """Write the generated secret report with owner-only file permissions."""
    write_yaml(path, data, force=force)
    try:
        os.chmod(path, SECRET_FILE_MODE)
    except OSError as exc:
        raise CommandError(f"Could not set secure permissions on {path}: {exc}") from exc


def default_secret_report_path(product_path: Path) -> Path:
    """Return the default sidecar path for generated secret values."""
    return product_path.with_name(f"{product_path.stem}.secrets.yaml")


def infer_storage_classes_from_cluster(
    context: str | None = None,
) -> InferredStorageClasses:
    """Infer storage class names from the active or requested kubectl context."""
    context_name = _resolve_kube_context(context)
    try:
        kube_config.load_kube_config(context=context_name)
        storage_classes = kube_client.StorageV1Api().list_storage_class()
    except Exception as exc:
        raise CommandError(
            f"Could not infer StorageClass from kubectl context {context_name!r}: {exc}"
        ) from exc

    storage_class_name = _select_storage_class_name(storage_classes.items or [])
    return InferredStorageClasses(
        context=context_name,
        dynamic_storage_class=storage_class_name,
        provisioning_storage_class=storage_class_name,
    )


def _select_storage_class_name(storage_classes: list[object]) -> str:
    names = sorted(
        name
        for name in (_storage_class_name(storage_class) for storage_class in storage_classes)
        if name
    )
    if not names:
        raise CommandError("No StorageClass found in the active Kubernetes context")

    default_names = sorted(
        name
        for name, storage_class in (
            (_storage_class_name(storage_class), storage_class)
            for storage_class in storage_classes
        )
        if name and _is_default_storage_class(storage_class)
    )
    if default_names:
        return default_names[0]

    for preferred_name in PREFERRED_STORAGE_CLASS_NAMES:
        if preferred_name in names:
            return preferred_name

    return names[0]


def _storage_class_name(storage_class: object) -> str | None:
    metadata = getattr(storage_class, "metadata", None)
    name = getattr(metadata, "name", None)
    return name if isinstance(name, str) and name else None


def _is_default_storage_class(storage_class: object) -> bool:
    metadata = getattr(storage_class, "metadata", None)
    annotations = getattr(metadata, "annotations", None) or {}
    return (
        annotations.get("storageclass.kubernetes.io/is-default-class") == "true"
        or annotations.get("storageclass.beta.kubernetes.io/is-default-class")
        == "true"
    )


def _resolve_kube_context(context: str | None) -> str:
    try:
        contexts, active_context = kube_config.list_kube_config_contexts()
    except Exception as exc:
        raise CommandError(f"Could not load kubectl contexts: {exc}") from exc

    context_names = {
        kube_context["name"]
        for kube_context in contexts or []
        if isinstance(kube_context, dict) and "name" in kube_context
    }

    if context is None:
        if not isinstance(active_context, dict) or not active_context.get("name"):
            raise CommandError("No active kubectl context found")
        context = active_context["name"]

    if context not in context_names:
        raise CommandError(f"Kubectl context {context!r} does not exist")

    return context


def _secret_token(byte_length: int = 32) -> str:
    return secrets.token_urlsafe(byte_length)


def _normalized_scheme(scheme: str) -> str:
    if scheme not in {"http", "https"}:
        raise CommandError("Scheme must be either http or https")
    return scheme


def _ensure_parent_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CommandError(f"Could not create directory {path.parent}: {exc}") from exc
