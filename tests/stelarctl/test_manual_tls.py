import json
from pathlib import Path

import pytest

from stelar.deploy.operations.common import CommandError
from stelar.deploy.operations import manual_tls


def manual_tls_config():
    return {
        "ingress": {
            "tls": ["manual_tls"],
            "manual_tls": {
                "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
                "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
                "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
                "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
            },
        }
    }


def write_manual_tls_file(path: Path, data: dict) -> None:
    path.write_text(f"{json.dumps(data)}\n", encoding="utf-8")


def test_manual_tls_selected_only_when_config_selects_mode():
    assert manual_tls.manual_tls_selected({"ingress": {"tls": ["manual_tls"]}})
    assert not manual_tls.manual_tls_selected({"ingress": {"tls": ["cert_manager"]}})
    assert not manual_tls.manual_tls_selected({"ingress": {}})
    assert not manual_tls.manual_tls_selected({})


def test_manual_tls_secret_fields_follow_endpoint_definitions():
    assert manual_tls.MANUAL_TLS_SECRET_FIELDS == tuple(
        endpoint.secret_field for endpoint in manual_tls.MANUAL_TLS_ENDPOINTS
    )


def test_read_manual_tls_secrets_maps_endpoint_dirs_and_secret_names(
    tmp_path,
    monkeypatch,
):
    manual_tls_path = tmp_path / "manual_tls.yaml"
    write_manual_tls_file(
        manual_tls_path,
        {
            "manual_tls": {
                "primary": "./certs/primary",
                "keycloak": "./certs/keycloak",
                "minio_api": "./certs/minio-api",
                "registry": "./certs/registry",
            }
        },
    )
    seen_dirs = []

    def read_secret_files(secret_name, cert_dir):
        seen_dirs.append(cert_dir)
        return manual_tls.ManualTlsSecret(
            secret_name,
            f"certificate:{cert_dir.name}",
            f"private-key:{cert_dir.name}",
        )

    monkeypatch.setattr(manual_tls, "_read_manual_tls_secret_files", read_secret_files)

    secrets = manual_tls.read_manual_tls_secrets(
        manual_tls_path,
        manual_tls_config(),
    )

    assert [secret.name for secret in secrets] == [
        "klms-manual-tls",
        "kc-manual-tls",
        "minio-manual-tls",
        "img-manual-tls",
    ]
    assert seen_dirs == [
        tmp_path / "certs" / "primary",
        tmp_path / "certs" / "keycloak",
        tmp_path / "certs" / "minio-api",
        tmp_path / "certs" / "registry",
    ]


def test_read_manual_tls_secrets_rejects_missing_endpoint_directory(tmp_path):
    manual_tls_path = tmp_path / "manual_tls.yaml"
    write_manual_tls_file(
        manual_tls_path,
        {
            "manual_tls": {
                "primary": "./certs/primary",
                "keycloak": "./certs/keycloak",
                "minio_api": "./certs/minio-api",
            }
        },
    )

    with pytest.raises(CommandError, match="manual_tls.registry"):
        manual_tls.read_manual_tls_secrets(manual_tls_path, manual_tls_config())


def test_read_manual_tls_secrets_rejects_missing_fullspec_secret_name(tmp_path):
    manual_tls_path = tmp_path / "manual_tls.yaml"
    write_manual_tls_file(
        manual_tls_path,
        {
            "manual_tls": {
                "primary": "./certs/primary",
                "keycloak": "./certs/keycloak",
                "minio_api": "./certs/minio-api",
                "registry": "./certs/registry",
            }
        },
    )
    config = manual_tls_config()
    config["ingress"]["manual_tls"].pop("REGISTRY_TLS_SECRET_NAME")

    with pytest.raises(CommandError, match="REGISTRY_TLS_SECRET_NAME"):
        manual_tls.read_manual_tls_secrets(manual_tls_path, config)
