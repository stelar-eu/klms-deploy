"""Secret payload and Kubernetes Secret resource helpers."""

from __future__ import annotations

import base64
import random
import string

from .common import CommandError, JsonObject

PRODUCT_SECRET_FIELDS = (
    (
        "postgres",
        "POSTGRES_DB_PASSWORD_SECRET_NAME",
        "POSTGRES_DB_PASSWORD",
        "password",
    ),
    ("postgres", "CKAN_DB_PASSWORD_SECRET_NAME", "CKAN_DB_PASSWORD", "password"),
    (
        "postgres",
        "KEYCLOAK_DB_PASSWORD_SECRET_NAME",
        "KEYCLOAK_DB_PASSWORD",
        "password",
    ),
    (
        "postgres",
        "DATASTORE_DB_PASSWORD_SECRET_NAME",
        "DATASTORE_DB_PASSWORD",
        "password",
    ),
    ("postgres", "QUAY_DB_PASSWORD_SECRET_NAME", "QUAY_DB_PASSWORD", "password"),
    (
        "keycloak",
        "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME",
        "KEYCLOAK_ROOT_PASSWORD",
        "password",
    ),
    ("api", "SMTP_PASSWORD_SECRET_NAME", "SMTP_PASSWORD", "password"),
    ("api", "SESSION_SECRET_KEY_SECRET_NAME", "SESSION_SECRET_KEY", "key"),
    ("ckan", "CKAN_ADMIN_PASSWORD_SECRET_NAME", "CKAN_ADMIN_PASSWORD", "password"),
    ("minio", "MINIO_ROOT_PASSWORD_SECRET_NAME", "MINIO_ROOT_PASSWORD", "password"),
)
OPTIONAL_PRODUCT_SECRET_FIELDS = (
    ("llm_search", "GROQ_API_KEY_SECRET_NAME", "GROQ_API_KEY", "key"),
)
CKAN_AUTH_SECRET_NAME = "ckan-auth-secret"
PASSWORD_MIN_LENGTH = 8
MINIO_ROOT_PASSWORD_MIN_LENGTH = PASSWORD_MIN_LENGTH
MINIO_ROOT_USER_MIN_LENGTH = 3


def product_secrets(spec: JsonObject) -> list[tuple[str, dict[str, str]]]:
    """Build Secret names and data from product spec secret fields."""
    secrets = [
        _secret_from_product_spec(spec, section, name_key, value_key, data_key)
        for section, name_key, value_key, data_key in PRODUCT_SECRET_FIELDS
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


def ckan_auth_secret_data() -> dict[str, str]:
    """Generate CKAN auth secret values."""
    return {
        "session-key": _generate_random_string(40, 8, "-"),
        "jwt-key": _generate_jwt_key(),
    }


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
    _validate_secret_value(section, value_key, secret_value)
    return secret_name, {data_key: secret_value}


def _validate_secret_value(section: str, key: str, value: str) -> None:
    if key.endswith("PASSWORD"):
        validate_password(value, source=f"{section}.{key}")


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
        raise CommandError(f"Product spec must contain a {section} object")
    return value


def _required_product_spec_string(
    section_config: JsonObject,
    section: str,
    key: str,
) -> str:
    value = section_config.get(key)
    if not isinstance(value, str) or not value:
        raise CommandError(
            f"Product spec must define {section}.{key} "
            "as a non-empty string"
        )
    return value


def _generate_jwt_key(length: int = 43) -> str:
    return f"string:{_random_token(length)}"


def _generate_random_string(
    length: int = 40,
    chunk_size: int = 8,
    separator: str = "-",
) -> str:
    raw_string = _random_token(length)
    chunks = [
        raw_string[index : index + chunk_size]
        for index in range(0, length, chunk_size)
    ]
    return separator.join(chunks)


def _random_token(length: int) -> str:
    rng = random.SystemRandom()
    characters = string.ascii_letters + string.digits
    return "".join(rng.choice(characters) for _ in range(length))


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")
