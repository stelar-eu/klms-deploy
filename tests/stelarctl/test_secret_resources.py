import base64

import pytest

from stelar.deploy.operations.common import CommandError
from stelar.deploy.operations.secret_resources import (
    CKAN_AUTH_SECRET_NAME,
    ckan_auth_secret_data,
    kubernetes_secret,
    kubernetes_tls_secret,
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
            "POSTGRES_DB_PASSWORD": "postgres-password",
            "POSTGRES_DB_PASSWORD_SECRET_NAME": "postgres-secret",
            "CKAN_DB_PASSWORD": "ckan-password",
            "CKAN_DB_PASSWORD_SECRET_NAME": "ckan-secret",
            "KEYCLOAK_DB_PASSWORD": "keycloak-db-password",
            "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "keycloak-db-secret",
            "DATASTORE_DB_PASSWORD": "datastore-password",
            "DATASTORE_DB_PASSWORD_SECRET_NAME": "datastore-secret",
            "QUAY_DB_PASSWORD": "quay-password",
            "QUAY_DB_PASSWORD_SECRET_NAME": "quay-secret",
        },
        "keycloak": {
            "KEYCLOAK_ROOT_PASSWORD": "keycloak-root-password",
            "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "keycloak-root-secret",
        },
        "api": {
            "SMTP_PASSWORD": "smtp-password",
            "SMTP_PASSWORD_SECRET_NAME": "smtp-secret",
            "SESSION_SECRET_KEY": "session-secret",
            "SESSION_SECRET_KEY_SECRET_NAME": "session-secret-name",
        },
        "ckan": {
            "CKAN_ADMIN_PASSWORD": "ckan-admin-password",
            "CKAN_ADMIN_PASSWORD_SECRET_NAME": "ckan-admin-secret",
        },
        "minio": {
            "MINIO_ROOT_PASSWORD": "minio-root-password",
            "MINIO_ROOT_PASSWORD_SECRET_NAME": "minio-root-secret",
        },
    }


def test_product_secrets_extracts_required_and_optional_secret_fields():
    spec = product_spec()
    spec["llm_search"] = {
        "GROQ_API_KEY": "groq-key",
        "GROQ_API_KEY_SECRET_NAME": "groq-secret",
    }

    secrets = dict(product_secrets(spec))

    assert secrets["postgres-secret"] == {"password": "postgres-password"}
    assert secrets["session-secret-name"] == {"key": "session-secret"}
    assert secrets["minio-root-secret"] == {"password": "minio-root-password"}
    assert secrets["groq-secret"] == {"key": "groq-key"}


def test_product_secrets_rejects_missing_secret_field():
    spec = product_spec()
    spec["postgres"].pop("CKAN_DB_PASSWORD")

    with pytest.raises(CommandError, match="postgres.CKAN_DB_PASSWORD"):
        product_secrets(spec)


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
    data = ckan_auth_secret_data()

    assert CKAN_AUTH_SECRET_NAME == "ckan-auth-secret"
    assert set(data) == {"session-key", "jwt-key"}
    assert data["jwt-key"].startswith("string:")
    assert data["session-key"]
