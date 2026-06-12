import base64
from dataclasses import replace

import pytest

from stelar.deploy.operations.common import CommandError
from stelar.deploy.operations.secret_resources import (
    BootstrapSecretValues,
    CKAN_AUTH_SECRET_NAME,
    ckan_auth_secret_data,
    ckan_auth_secret_name,
    generate_bootstrap_secret_values,
    kubernetes_secret,
    kubernetes_tls_secret,
    product_secret_names,
    product_secrets,
)


def decoded(secret):
    return {
        key: base64.b64decode(value).decode("utf-8")
        for key, value in secret["data"].items()
    }


def product_spec():
    return {
        "postgres": {
            "POSTGRES_DB_PASSWORD_SECRET_NAME": "postgres-secret",
            "CKAN_DB_PASSWORD_SECRET_NAME": "ckan-secret",
            "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "keycloak-db-secret",
            "DATASTORE_DB_PASSWORD_SECRET_NAME": "datastore-secret",
            "QUAY_DB_PASSWORD_SECRET_NAME": "quay-secret",
        },
        "keycloak": {
            "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "keycloak-root-secret",
        },
        "api": {
            "SMTP_PASSWORD_SECRET_NAME": "smtp-secret",
            "SESSION_SECRET_KEY_SECRET_NAME": "session-secret-name",
        },
        "ckan": {
            "CKAN_ADMIN_PASSWORD_SECRET_NAME": "ckan-admin-secret",
            "CKAN_AUTH_SECRET_NAME": "ckan-auth-custom",
        },
        "minio": {
            "MINIO_ROOT_PASSWORD_SECRET_NAME": "minio-root-secret",
        },
    }


def bootstrap_values(**overrides):
    values = BootstrapSecretValues(
        postgres_db_password="postgres-password",
        ckan_db_password="ckan-password",
        datastore_db_password="datastore-password",
        keycloak_db_password="keycloak-db-password",
        quay_db_password="quay-password",
        keycloak_root_password="keycloak-root-password",
        smtp_password="smtp-password",
        api_session_secret_key="session-secret",
        ckan_admin_password="ckan-admin-password",
        ckan_session_key="ckan-session-secret",
        ckan_jwt_key="string:ckan-jwt-secret",
        minio_root_password="minio-root-password",
    )
    return replace(values, **overrides)


def test_product_secrets_use_fullspec_names_and_bootstrap_values():
    spec = product_spec()
    spec["llm_search"] = {
        "GROQ_API_KEY": "groq-key",
        "GROQ_API_KEY_SECRET_NAME": "groq-secret",
    }

    secrets = dict(product_secrets(spec, bootstrap_values()))

    assert secrets["postgres-secret"] == {"password": "postgres-password"}
    assert secrets["session-secret-name"] == {"key": "session-secret"}
    assert secrets["minio-root-secret"] == {"password": "minio-root-password"}
    assert secrets["groq-secret"] == {"key": "groq-key"}


def test_product_secret_names_include_ckan_auth_name_from_fullspec():
    assert product_secret_names(product_spec())[-1] == "ckan-auth-custom"
    assert ckan_auth_secret_name(product_spec()) == "ckan-auth-custom"


def test_product_secrets_rejects_missing_secret_name_field():
    spec = product_spec()
    spec["postgres"].pop("CKAN_DB_PASSWORD_SECRET_NAME")

    with pytest.raises(CommandError, match="postgres.CKAN_DB_PASSWORD_SECRET_NAME"):
        product_secrets(spec, bootstrap_values())


@pytest.mark.parametrize(
    ("attribute", "message"),
    [
        ("postgres_db_password", "postgres.POSTGRES_DB_PASSWORD"),
        ("ckan_db_password", "postgres.CKAN_DB_PASSWORD"),
        ("keycloak_db_password", "postgres.KEYCLOAK_DB_PASSWORD"),
        ("datastore_db_password", "postgres.DATASTORE_DB_PASSWORD"),
        ("quay_db_password", "postgres.QUAY_DB_PASSWORD"),
        ("keycloak_root_password", "keycloak.KEYCLOAK_ROOT_PASSWORD"),
        ("smtp_password", "api.SMTP_PASSWORD"),
        ("ckan_admin_password", "ckan.CKAN_ADMIN_PASSWORD"),
        ("minio_root_password", "minio.MINIO_ROOT_PASSWORD"),
    ],
)
def test_product_secrets_rejects_short_manual_bootstrap_passwords(attribute, message):
    values = bootstrap_values(**{attribute: "1234"})

    with pytest.raises(CommandError, match=rf"{message}.*at least 8 characters"):
        product_secrets(product_spec(), values)


def test_generate_bootstrap_secret_values_uses_non_empty_distinct_values():
    values = generate_bootstrap_secret_values()
    raw_values = list(values.__dict__.values())

    assert all(isinstance(value, str) and value for value in raw_values)
    assert values.ckan_jwt_key.startswith("string:")
    assert len(set(raw_values)) == len(raw_values)


def test_kubernetes_secret_base64_encodes_opaque_data():
    secret = kubernetes_secret(
        "app-secret",
        "stelar",
        {"password": "secret-value", "key": "abc"},
    )

    assert secret["metadata"] == {"name": "app-secret", "namespace": "stelar"}
    assert secret["type"] == "Opaque"
    assert decoded(secret) == {"password": "secret-value", "key": "abc"}


def test_kubernetes_tls_secret_base64_encodes_tls_data():
    secret = kubernetes_tls_secret(
        "tls-secret",
        "stelar",
        "certificate-pem",
        "private-key-pem",
    )

    assert secret["metadata"] == {"name": "tls-secret", "namespace": "stelar"}
    assert secret["type"] == "kubernetes.io/tls"
    assert decoded(secret) == {
        "tls.crt": "certificate-pem",
        "tls.key": "private-key-pem",
    }


def test_ckan_auth_secret_data_uses_expected_keys_and_values():
    data = ckan_auth_secret_data(bootstrap_values())

    assert CKAN_AUTH_SECRET_NAME == "ckan-auth-secret"
    assert set(data) == {"session-key", "jwt-key"}
    assert data == {
        "session-key": "ckan-session-secret",
        "jwt-key": "string:ckan-jwt-secret",
    }
