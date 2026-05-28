"""Validation helpers for generated product fullspecs."""

from __future__ import annotations

from .common import CommandError, JsonObject

TLS_MODES = {"no_tls", "cert_manager", "self_signed"}


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

    if scheme == "http" and tls_mode != "no_tls":
        raise CommandError(
            f"{source} with SCHEME http must select ingress.tls no_tls"
        )
    if scheme == "https" and tls_mode == "no_tls":
        raise CommandError(
            f"{source} with SCHEME https must select cert_manager or self_signed "
            "in ingress.tls"
        )
