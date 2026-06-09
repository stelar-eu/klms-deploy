"""CLI handler registration package for `stelarctl`.

Add future command groups by creating a module with a `register_*_commands`
function and calling it from `register_commands`.
"""

from __future__ import annotations

import typer

from .lake import register_lake_commands
from .workspace import register_workspace_commands


def register_commands(app: typer.Typer) -> None:
    """Register every command group on the root CLI app."""
    register_workspace_commands(app)
    register_lake_commands(app)
