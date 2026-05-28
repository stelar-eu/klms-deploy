"""Manual TLS secret file helpers."""

from __future__ import annotations

import pkgutil
from pathlib import Path

from .common import CommandError

MANUAL_TLS_FILE_NAME = "manual_tls.yaml"
MANUAL_TLS_TEMPLATE_PACKAGE = "stelar.deploy"
MANUAL_TLS_TEMPLATE = f"templates/{MANUAL_TLS_FILE_NAME}"


def _manual_tls_template() -> str:
    data = pkgutil.get_data(MANUAL_TLS_TEMPLATE_PACKAGE, MANUAL_TLS_TEMPLATE)
    if data is None:
        raise CommandError(
            f"Packaged manual TLS template {MANUAL_TLS_TEMPLATE!r} is missing"
        )
    return data.decode("utf-8")


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
