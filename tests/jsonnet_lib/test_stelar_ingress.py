import pytest
from jsonnet import JsonnetRunner


@pytest.fixture
def J() -> JsonnetRunner:
    return JsonnetRunner(
        "tests/jsonnet_lib/test_stelar_ingress.jsonnet",
        ["lib", "vendor"],
        """
        local ingress = import "util/stelar_ingress.libsonnet";
        """,
    )


def manual_tls_config():
    return """
    {
      SCHEME: "https",
      ROOT_DOMAIN: "example.test",
      PRIMARY_SUBDOMAIN: "klms",
      keycloak: { SUBDOMAIN: "kc" },
      minio: { API_SUBDOMAIN: "minio" },
      quay: { SUBDOMAIN: "img" },
      ingress: {
        tls: ["manual_tls"],
        manual_tls: {
          PRIMARY_TLS_SECRET_NAME: "klms-manual-tls",
          KEYCLOAK_TLS_SECRET_NAME: "kc-manual-tls",
          MINIO_API_TLS_SECRET_NAME: "minio-manual-tls",
          REGISTRY_TLS_SECRET_NAME: "img-manual-tls",
        },
      },
    }
    """


def test_manual_tls_uses_configured_primary_secret_name(J: JsonnetRunner):
    out = J(
        f"""
        ingress.new(
          "api",
          {{}},
          "klms",
          [["/", "Prefix", "api", "http"]],
          {manual_tls_config()}
        ).spec.tls[0]
        """
    )

    assert out == {
        "hosts": ["klms.example.test"],
        "secretName": "klms-manual-tls",
    }


def test_manual_tls_uses_configured_keycloak_secret_name(J: JsonnetRunner):
    out = J(
        f"""
        ingress.new(
          "keycloak",
          {{}},
          "kc",
          [["/", "Prefix", "keycloak", "http"]],
          {manual_tls_config()}
        ).spec.tls[0]
        """
    )

    assert out == {
        "hosts": ["kc.example.test"],
        "secretName": "kc-manual-tls",
    }
