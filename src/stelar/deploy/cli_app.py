"""Application assembly for the `stelarctl` Typer CLI."""

from __future__ import annotations

import typer

from .cli_help import (
    CONTEXT_SETTINGS,
    ROOT_EPILOG,
    ROOT_HELP,
    LinePreservingEpilogGroup,
    show_help_on_no_args,
)
from .cli_handlers import register_commands


def build_app() -> typer.Typer:
    """Build a fresh Typer app with all supported command groups registered."""
    app = typer.Typer(
        name="stelarctl",
        cls=LinePreservingEpilogGroup,
        rich_markup_mode=None,
        help=ROOT_HELP,
        epilog=ROOT_EPILOG,
        invoke_without_command=True,
        callback=show_help_on_no_args,
        context_settings=CONTEXT_SETTINGS,
    )
    register_commands(app)
    return app


app = build_app()
