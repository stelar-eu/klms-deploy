"""Validation helpers for generated product fullspecs."""

from __future__ import annotations

from .common import CommandError, JsonObject
from .manual_tls import MANUAL_TLS_SECRET_FIELDS
from .secret_resources import (
    validate_minio_root_password,
    validate_minio_root_user,
    validate_password,
)

TLS_MODES = {"no_tls", "cert_manager", "manual_tls", "self_signed"}


def validate_fullspec_scheme_tls_consistency(
    fullspec: JsonObject,
    *,
    source: str = "product_fullspec.json",
) -> None:
    """Validate that SCHEME and ingress.tls select a compatible mode."""
    config = fullspec.get("klms")
    if not isinstance(config, dict):
        raise CommandError(f"{source} must contain a klms object")
    validate_config_scheme_tls_consistency(config, source=source)


def validate_config_scheme_tls_consistency(
    config: JsonObject,
    *,
    source: str = "product_fullspec.json",
) -> None:
    """Validate a KLMS config object for SCHEME/ingress.tls consistency."""
    scheme = config.get("SCHEME")
    if scheme not in {"http", "https"}:
        raise CommandError(f"{source} must define SCHEME as http or https")

    ingress = config.get("ingress")
    if not isinstance(ingress, dict):
        raise CommandError(f"{source} must define ingress as an object")

    tls = ingress.get("tls")
    if not isinstance(tls, list) or not all(isinstance(item, str) for item in tls):
        raise CommandError(f"{source} must define ingress.tls as a list")
    if len(tls) != 1:
        raise CommandError(f"{source} must select exactly one ingress.tls mode")

    tls_mode = tls[0]
    if tls_mode not in TLS_MODES:
        modes = ", ".join(sorted(TLS_MODES))
        raise CommandError(f"{source} ingress.tls must be one of: {modes}")

    _validate_passwords(config, source=source)
    _validate_minio_credentials(config, source=source)

    if scheme == "http" and tls_mode != "no_tls":
        raise CommandError(
            f"{source} with SCHEME http must select ingress.tls no_tls"
        )
    if scheme == "http":
        _validate_http_minio_insecure(config, source=source)
    if scheme == "https" and tls_mode == "no_tls":
        raise CommandError(
            f"{source} with SCHEME https must select cert_manager, manual_tls, "
            "or self_signed in ingress.tls"
        )

    if tls_mode == "manual_tls":
        _validate_manual_tls_config(ingress, source=source)


def _validate_http_minio_insecure(config: JsonObject, *, source: str) -> None:
    minio = _required_minio_config(config, source=source)
    if minio.get("INSECURE_MC_CLIENT") != "true":
        raise CommandError(
            f"{source} with SCHEME http must define "
            "minio.INSECURE_MC_CLIENT as true"
        )


def _validate_passwords(
    value: object,
    *,
    source: str,
    path: tuple[str, ...] = (),
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            item_path = (*path, key_text)
            if key_text.endswith("PASSWORD"):
                dotted_path = ".".join(item_path)
                if not isinstance(item, str) or not item:
                    raise CommandError(
                        f"{source} must define {dotted_path} "
                        "as a non-empty string"
                    )
                validate_password(item, source=f"{source} {dotted_path}")
            _validate_passwords(item, source=source, path=item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_passwords(item, source=source, path=(*path, str(index)))


def _validate_minio_credentials(config: JsonObject, *, source: str) -> None:
    minio = _required_minio_config(config, source=source)
    root_user = _required_minio_string(minio, "MINIO_ROOT_USER", source=source)
    root_password = _required_minio_string(
        minio,
        "MINIO_ROOT_PASSWORD",
        source=source,
    )
    validate_minio_root_user(root_user, source=f"{source} minio.MINIO_ROOT_USER")
    validate_minio_root_password(
        root_password,
        source=f"{source} minio.MINIO_ROOT_PASSWORD",
    )


def _required_minio_config(config: JsonObject, *, source: str) -> JsonObject:
    minio = config.get("minio")
    if not isinstance(minio, dict):
        raise CommandError(f"{source} must define minio as an object")
    return minio


def _required_minio_string(
    minio: JsonObject,
    field_name: str,
    *,
    source: str,
) -> str:
    value = minio.get(field_name)
    if not isinstance(value, str) or not value:
        raise CommandError(
            f"{source} must define minio.{field_name} as a non-empty string"
        )
    return value


def _validate_manual_tls_config(ingress: JsonObject, *, source: str) -> None:
    manual_tls = ingress.get("manual_tls")
    if not isinstance(manual_tls, dict):
        raise CommandError(f"{source} must define ingress.manual_tls as an object")

    for field_name in MANUAL_TLS_SECRET_FIELDS:
        value = manual_tls.get(field_name)
        if not isinstance(value, str) or not value:
            raise CommandError(
                f"{source} must define ingress.manual_tls.{field_name} "
                "as a non-empty string"
            )
