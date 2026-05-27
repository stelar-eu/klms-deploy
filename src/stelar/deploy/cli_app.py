"""Application assembly for the `stelarctl` Typer CLI."""

from __future__ import annotations

import typer

from .cli_commands import register_commands


def build_app() -> typer.Typer:
    """Build a fresh Typer app with all supported command groups registered."""
    app = typer.Typer(name="stelarctl", help="STELAR deployment management tool")
    register_commands(app)
    return app


app = build_app()
