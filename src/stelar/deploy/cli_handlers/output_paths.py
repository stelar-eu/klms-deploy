"""Output path validation helpers for CLI commands."""

from __future__ import annotations

from pathlib import Path

from ..operations import CommandError


def validate_output_path(path: Path, *, force: bool) -> None:
    """Reject existing output files unless the caller explicitly allows overwrite."""
    if path.exists() and not force:
        raise CommandError(f"{path} already exists; use --force to overwrite it")


def validate_distinct_paths(left: Path, right: Path) -> None:
    """Reject command outputs that would write different artifacts to one path."""
    if left == right:
        raise CommandError("Product output and secret-values output must differ")
