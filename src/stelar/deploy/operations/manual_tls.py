"""Manual TLS template, input parsing, and certificate validation."""

from __future__ import annotations

import base64
import binascii
import pkgutil
import ssl
from dataclasses import dataclass
from pathlib import Path

import yaml

from .common import CommandError, JsonObject

MANUAL_TLS_FILE_NAME = "manual_tls.yaml"
MANUAL_TLS_TEMPLATE_PACKAGE = "stelar.deploy"
MANUAL_TLS_TEMPLATE = f"templates/{MANUAL_TLS_FILE_NAME}"
TLS_CERT_FILE_NAME = "tls.crt"
TLS_KEY_FILE_NAME = "tls.key"
TLS_PEM_LABELS = {
    "certificate": ("CERTIFICATE",),
    "private key": (
        "PRIVATE KEY",
        "RSA PRIVATE KEY",
        "EC PRIVATE KEY",
        "ENCRYPTED PRIVATE KEY",
    ),
}


@dataclass(frozen=True)
class ManualTlsEndpoint:
    """A manual TLS endpoint expected in fullspec and manual_tls.yaml."""

    name: str
    secret_field: str


@dataclass(frozen=True)
class ManualTlsSecret:
    """Validated TLS secret material ready to apply to Kubernetes."""

    name: str
    certificate: str
    private_key: str


MANUAL_TLS_ENDPOINTS = (
    ManualTlsEndpoint("primary", "PRIMARY_TLS_SECRET_NAME"),
    ManualTlsEndpoint("keycloak", "KEYCLOAK_TLS_SECRET_NAME"),
    ManualTlsEndpoint("minio_api", "MINIO_API_TLS_SECRET_NAME"),
    ManualTlsEndpoint("registry", "REGISTRY_TLS_SECRET_NAME"),
)
MANUAL_TLS_SECRET_FIELDS = tuple(endpoint.secret_field for endpoint in MANUAL_TLS_ENDPOINTS)


def manual_tls_selected(config: JsonObject) -> bool:
    """Return true when a KLMS config selects ingress.tls manual_tls."""
    ingress = config.get("ingress")
    if not isinstance(ingress, dict):
        return False
    tls = ingress.get("tls")
    return isinstance(tls, list) and "manual_tls" in tls


def read_manual_tls_secrets(
    manual_tls_path: Path,
    config: JsonObject,
) -> list[ManualTlsSecret]:
    """Read and validate manual TLS cert/key pairs for the selected config."""
    manual_tls_config = _read_manual_tls_file(manual_tls_path)
    expected_names = _manual_tls_expected_secret_names(config)
    entries = []

    for endpoint in MANUAL_TLS_ENDPOINTS:
        directory = manual_tls_config.get(endpoint.name)
        if not isinstance(directory, str) or not directory:
            raise CommandError(
                f"{manual_tls_path} must define manual_tls.{endpoint.name} "
                "as a non-empty directory string"
            )

        cert_dir = Path(directory)
        if not cert_dir.is_absolute():
            cert_dir = manual_tls_path.parent / cert_dir
        entries.append((
            _required_manual_tls_secret_name(expected_names, endpoint.secret_field),
            cert_dir,
        ))

    return [_read_manual_tls_secret_files(secret_name, cert_dir) for secret_name, cert_dir in entries]


def write_manual_tls_sample(path: Path, *, force: bool = False) -> None:
    """Write a sample manual TLS secret input file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CommandError(f"Could not create directory {path.parent}: {exc}") from exc

    if path.exists() and not force:
        raise CommandError(f"{path} already exists; use --force to overwrite it")

    try:
        path.write_text(_manual_tls_template(), encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"Could not write {path}: {exc}") from exc


def _manual_tls_template() -> str:
    data = pkgutil.get_data(MANUAL_TLS_TEMPLATE_PACKAGE, MANUAL_TLS_TEMPLATE)
    if data is None:
        raise CommandError(
            f"Packaged manual TLS template {MANUAL_TLS_TEMPLATE!r} is missing"
        )
    return data.decode("utf-8")


def _read_manual_tls_secret_files(
    secret_name: str,
    cert_dir: Path,
) -> ManualTlsSecret:
    cert_path = cert_dir / TLS_CERT_FILE_NAME
    key_path = cert_dir / TLS_KEY_FILE_NAME
    cert_pem = _read_tls_pem(cert_path, "certificate")
    key_pem = _read_tls_pem(key_path, "private key")
    _validate_tls_cert_key_pair(cert_path, key_path)
    return ManualTlsSecret(secret_name, cert_pem, key_pem)


def _required_manual_tls_secret_name(
    manual_tls: JsonObject,
    field_name: str,
) -> str:
    value = manual_tls.get(field_name)
    if not isinstance(value, str) or not value:
        raise CommandError(
            f"product_fullspec.json must define ingress.manual_tls.{field_name} "
            "as a non-empty string"
        )
    return value


def _read_manual_tls_file(manual_tls_path: Path) -> JsonObject:
    try:
        raw = yaml.safe_load(manual_tls_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CommandError(f"Could not read {manual_tls_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CommandError(f"Invalid YAML in {manual_tls_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CommandError(f"{manual_tls_path} must contain an object")
    manual_tls = raw.get("manual_tls")
    if not isinstance(manual_tls, dict):
        raise CommandError(f"{manual_tls_path} must contain a manual_tls object")
    return manual_tls


def _manual_tls_expected_secret_names(config: JsonObject) -> JsonObject:
    ingress = config.get("ingress")
    if not isinstance(ingress, dict):
        raise CommandError("product_fullspec.json must define ingress as an object")
    manual_tls = ingress.get("manual_tls")
    if not isinstance(manual_tls, dict):
        raise CommandError(
            "product_fullspec.json must define ingress.manual_tls as an object"
        )
    return manual_tls


def _read_tls_pem(path: Path, label: str) -> str:
    if not path.is_file():
        raise CommandError(f"Manual TLS {label} file {path} does not exist")
    try:
        value = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CommandError(f"Manual TLS {label} file {path} must be PEM text") from exc
    except OSError as exc:
        raise CommandError(f"Could not read manual TLS {label} file {path}: {exc}") from exc

    if not value.strip():
        raise CommandError(f"Manual TLS {label} file {path} is empty")
    _validate_tls_pem_block(path, label, value)
    return value


def _validate_tls_pem_block(path: Path, label: str, value: str) -> None:
    for pem_label in TLS_PEM_LABELS[label]:
        begin_marker = f"-----BEGIN {pem_label}-----"
        end_marker = f"-----END {pem_label}-----"
        begin_index = value.find(begin_marker)
        if begin_index == -1:
            continue

        payload_start = begin_index + len(begin_marker)
        end_index = value.find(end_marker, payload_start)
        if end_index == -1:
            raise CommandError(
                f"Manual TLS {label} file {path} contains {begin_marker} "
                f"without a matching {end_marker}"
            )

        payload = "".join(value[payload_start:end_index].strip().split())
        if not payload:
            raise CommandError(
                f"Manual TLS {label} file {path} contains an empty PEM payload"
            )
        try:
            base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CommandError(
                f"Manual TLS {label} file {path} contains invalid PEM base64"
            ) from exc
        return

    expected = ", ".join(f"BEGIN {pem_label}" for pem_label in TLS_PEM_LABELS[label])
    raise CommandError(f"Manual TLS {label} file {path} must contain {expected}")


def _validate_tls_cert_key_pair(cert_path: Path, key_path: Path) -> None:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    except ssl.SSLError as exc:
        raise CommandError(
            f"Manual TLS certificate/key pair in {cert_path.parent} is not usable: "
            f"{exc}"
        ) from exc
    except OSError as exc:
        raise CommandError(
            f"Could not validate manual TLS certificate/key pair in "
            f"{cert_path.parent}: {exc}"
        ) from exc
