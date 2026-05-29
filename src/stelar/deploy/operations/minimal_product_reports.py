"""YAML and generated secret report writers for product generation."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from .common import CommandError, JsonObject


SECRET_FILE_MODE = 0o600


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


def _ensure_parent_dir(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CommandError(f"Could not create directory {path.parent}: {exc}") from exc
