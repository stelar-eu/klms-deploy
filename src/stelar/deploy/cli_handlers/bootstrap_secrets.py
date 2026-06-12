"""CLI prompts for manually supplied bootstrap Secret values."""

from __future__ import annotations

from ..operations.secret_resources import BootstrapSecretValues, PASSWORD_MIN_LENGTH
from .prompts import prompt_secret as _prompt_secret


def prompt_bootstrap_secret_values() -> BootstrapSecretValues:
    """Prompt for bootstrap Secret values instead of generating them."""
    return BootstrapSecretValues(
        postgres_db_password=_prompt_password("Postgres admin DB password"),
        ckan_db_password=_prompt_password("CKAN DB password"),
        datastore_db_password=_prompt_password("Datastore DB password"),
        keycloak_db_password=_prompt_password("Keycloak DB password"),
        quay_db_password=_prompt_password("Quay DB password"),
        keycloak_root_password=_prompt_password("Keycloak admin/root password"),
        smtp_password=_prompt_password("SMTP password"),
        api_session_secret_key=_prompt_secret("STELAR API session secret"),
        ckan_admin_password=_prompt_password("CKAN admin password"),
        ckan_session_key=_prompt_secret("CKAN session key"),
        ckan_jwt_key=_prompt_secret("CKAN JWT key"),
        minio_root_password=_prompt_password("MinIO root password"),
    )


def _prompt_password(label: str) -> str:
    return _prompt_secret(label, min_length=PASSWORD_MIN_LENGTH)
