"""Secret payload and Kubernetes Secret resource helpers."""

from __future__ import annotations

import base64
import secrets as crypto_secrets
from dataclasses import dataclass

from .common import CommandError, JsonObject
from .manual_tls import manual_tls_secret_names, manual_tls_selected

PRODUCT_SECRET_FIELDS = (
    (
        "postgres",
        "POSTGRES_DB_PASSWORD_SECRET_NAME",
        "postgres_db_password",
        "password",
        "postgres.POSTGRES_DB_PASSWORD",
    ),
    (
        "postgres",
        "CKAN_DB_PASSWORD_SECRET_NAME",
        "ckan_db_password",
        "password",
        "postgres.CKAN_DB_PASSWORD",
    ),
    (
        "postgres",
        "KEYCLOAK_DB_PASSWORD_SECRET_NAME",
        "keycloak_db_password",
        "password",
        "postgres.KEYCLOAK_DB_PASSWORD",
    ),
    (
        "postgres",
        "DATASTORE_DB_PASSWORD_SECRET_NAME",
        "datastore_db_password",
        "password",
        "postgres.DATASTORE_DB_PASSWORD",
    ),
    (
        "postgres",
        "QUAY_DB_PASSWORD_SECRET_NAME",
        "quay_db_password",
        "password",
        "postgres.QUAY_DB_PASSWORD",
    ),
    (
        "keycloak",
        "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME",
        "keycloak_root_password",
        "password",
        "keycloak.KEYCLOAK_ROOT_PASSWORD",
    ),
    (
        "api",
        "SMTP_PASSWORD_SECRET_NAME",
        "smtp_password",
        "password",
        "api.SMTP_PASSWORD",
    ),
    (
        "api",
        "SESSION_SECRET_KEY_SECRET_NAME",
        "api_session_secret_key",
        "key",
        "api.SESSION_SECRET_KEY",
    ),
    (
        "ckan",
        "CKAN_ADMIN_PASSWORD_SECRET_NAME",
        "ckan_admin_password",
        "password",
        "ckan.CKAN_ADMIN_PASSWORD",
    ),
    (
        "minio",
        "MINIO_ROOT_PASSWORD_SECRET_NAME",
        "minio_root_password",
        "password",
        "minio.MINIO_ROOT_PASSWORD",
    ),
)
OPTIONAL_PRODUCT_SECRET_FIELDS = (
    ("llm_search", "GROQ_API_KEY_SECRET_NAME", "GROQ_API_KEY", "key"),
)
CKAN_AUTH_SECRET_NAME = "ckan-auth-secret"
PASSWORD_MIN_LENGTH = 8
MINIO_ROOT_PASSWORD_MIN_LENGTH = PASSWORD_MIN_LENGTH
MINIO_ROOT_USER_MIN_LENGTH = 3

BOOTSTRAP_PASSWORD_FIELDS = {
    "postgres_db_password": "postgres.POSTGRES_DB_PASSWORD",
    "ckan_db_password": "postgres.CKAN_DB_PASSWORD",
    "datastore_db_password": "postgres.DATASTORE_DB_PASSWORD",
    "keycloak_db_password": "postgres.KEYCLOAK_DB_PASSWORD",
    "quay_db_password": "postgres.QUAY_DB_PASSWORD",
    "keycloak_root_password": "keycloak.KEYCLOAK_ROOT_PASSWORD",
    "smtp_password": "api.SMTP_PASSWORD",
    "ckan_admin_password": "ckan.CKAN_ADMIN_PASSWORD",
    "minio_root_password": "minio.MINIO_ROOT_PASSWORD",
}


@dataclass(frozen=True)
class BootstrapSecretValues:
    """Secret values created during lake bootstrap."""

    postgres_db_password: str
    ckan_db_password: str
    datastore_db_password: str
    keycloak_db_password: str
    quay_db_password: str
    keycloak_root_password: str
    smtp_password: str
    api_session_secret_key: str
    ckan_admin_password: str
    ckan_session_key: str
    ckan_jwt_key: str
    minio_root_password: str


def generate_bootstrap_secret_values() -> BootstrapSecretValues:
    """Generate bootstrap secret values with OS-backed randomness."""
    return BootstrapSecretValues(
        postgres_db_password=_secret_token(),
        ckan_db_password=_secret_token(),
        datastore_db_password=_secret_token(),
        keycloak_db_password=_secret_token(),
        quay_db_password=_secret_token(),
        keycloak_root_password=_secret_token(),
        smtp_password=_secret_token(),
        api_session_secret_key=_secret_token(48),
        ckan_admin_password=_secret_token(),
        ckan_session_key=_secret_token(48),
        ckan_jwt_key=f"string:{_secret_token()}",
        minio_root_password=_secret_token(),
    )


def product_secrets(
    spec: JsonObject,
    secret_values: BootstrapSecretValues | None = None,
) -> list[tuple[str, dict[str, str]]]:
    """Build Secret names from fullspec config and data from bootstrap values."""
    values = secret_values or generate_bootstrap_secret_values()
    validate_bootstrap_secret_values(values)
    secrets = [
        _secret_from_bootstrap_values(spec, values, section, name_key, value_attr, data_key)
        for section, name_key, value_attr, data_key, _source in PRODUCT_SECRET_FIELDS
    ]

    for section, name_key, value_key, data_key in OPTIONAL_PRODUCT_SECRET_FIELDS:
        if section in spec:
            secrets.append(
                _secret_from_product_spec(
                    spec,
                    section,
                    name_key,
                    value_key,
                    data_key,
                )
            )

    return secrets


def product_secret_names(spec: JsonObject) -> tuple[str, ...]:
    """Return product Secret names created from fullspec config fields."""
    names = [
        _secret_name_from_product_spec(spec, section, name_key)
        for section, name_key, _value_attr, _data_key, _source in PRODUCT_SECRET_FIELDS
    ]

    for section, name_key, _value_key, _data_key in OPTIONAL_PRODUCT_SECRET_FIELDS:
        if section in spec:
            names.append(_secret_name_from_product_spec(spec, section, name_key))

    names.append(ckan_auth_secret_name(spec))
    return tuple(names)


def expected_bootstrap_secret_names(spec: JsonObject) -> tuple[str, ...]:
    """Return all bootstrap Secret names for a rendered KLMS config."""
    names = product_secret_names(spec)
    if manual_tls_selected(spec):
        names += manual_tls_secret_names(spec)
    return tuple(dict.fromkeys(names))


def ckan_auth_secret_name(spec: JsonObject) -> str:
    """Return the CKAN auth Secret name from fullspec config."""
    section_config = _product_spec_section(spec, "ckan")
    value = section_config.get("CKAN_AUTH_SECRET_NAME", CKAN_AUTH_SECRET_NAME)
    if not isinstance(value, str) or not value:
        raise CommandError(
            "Fullspec config must define ckan.CKAN_AUTH_SECRET_NAME "
            "as a non-empty string"
        )
    return value


def ckan_auth_secret_data(
    secret_values: BootstrapSecretValues | None = None,
) -> dict[str, str]:
    """Build CKAN auth secret values."""
    values = secret_values or generate_bootstrap_secret_values()
    validate_bootstrap_secret_values(values)
    return {
        "session-key": values.ckan_session_key,
        "jwt-key": values.ckan_jwt_key,
    }


def validate_bootstrap_secret_values(values: BootstrapSecretValues) -> None:
    for attribute, value in values.__dict__.items():
        if not isinstance(value, str) or not value:
            raise CommandError(f"{attribute} must be a non-empty string")
    for attribute, source in BOOTSTRAP_PASSWORD_FIELDS.items():
        validate_password(getattr(values, attribute), source=source)


def kubernetes_tls_secret(
    secret_name: str,
    namespace: str,
    cert_pem: str,
    key_pem: str,
) -> JsonObject:
    """Build a Kubernetes TLS Secret resource."""
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
        },
        "type": "kubernetes.io/tls",
        "data": {
            "tls.crt": _b64(cert_pem),
            "tls.key": _b64(key_pem),
        },
    }


def kubernetes_secret(
    secret_name: str,
    namespace: str,
    data: dict[str, str],
) -> JsonObject:
    """Build a Kubernetes opaque Secret resource."""
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": secret_name,
            "namespace": namespace,
        },
        "type": "Opaque",
        "data": {key: _b64(value) for key, value in data.items()},
    }


def _secret_from_bootstrap_values(
    spec: JsonObject,
    values: BootstrapSecretValues,
    section: str,
    name_key: str,
    value_attr: str,
    data_key: str,
) -> tuple[str, dict[str, str]]:
    secret_name = _secret_name_from_product_spec(spec, section, name_key)
    return secret_name, {data_key: getattr(values, value_attr)}


def _secret_from_product_spec(
    spec: JsonObject,
    section: str,
    name_key: str,
    value_key: str,
    data_key: str,
) -> tuple[str, dict[str, str]]:
    section_config = _product_spec_section(spec, section)
    secret_name = _required_product_spec_string(section_config, section, name_key)
    secret_value = _required_product_spec_string(section_config, section, value_key)
    return secret_name, {data_key: secret_value}


def _secret_name_from_product_spec(
    spec: JsonObject,
    section: str,
    name_key: str,
) -> str:
    section_config = _product_spec_section(spec, section)
    return _required_product_spec_string(section_config, section, name_key)


def validate_password(value: str, *, source: str) -> None:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise CommandError(
            f"{source} must be at least {PASSWORD_MIN_LENGTH} characters long"
        )


def validate_minio_root_password(value: str, *, source: str) -> None:
    validate_password(value, source=source)


def validate_minio_root_user(value: str, *, source: str) -> None:
    if len(value) < MINIO_ROOT_USER_MIN_LENGTH:
        raise CommandError(
            f"{source} must be at least "
            f"{MINIO_ROOT_USER_MIN_LENGTH} characters long"
        )


def _product_spec_section(spec: JsonObject, section: str) -> JsonObject:
    value = spec.get(section)
    if not isinstance(value, dict):
        raise CommandError(f"Fullspec config must contain a {section} object")
    return value


def _required_product_spec_string(
    section_config: JsonObject,
    section: str,
    key: str,
) -> str:
    value = section_config.get(key)
    if not isinstance(value, str) or not value:
        raise CommandError(
            f"Fullspec config must define {section}.{key} "
            "as a non-empty string"
        )
    return value


def _secret_token(byte_length: int = 32) -> str:
    return crypto_secrets.token_urlsafe(byte_length)


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")
