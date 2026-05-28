"""CLI handler registration package for `stelarctl`.

Add future command groups by creating a module with a `register_*_commands`
function and calling it from `register_commands`.
"""

from __future__ import annotations

import typer

from .init_lake import register_init_lake_commands
from .lakespec import register_lakespec_commands
from .product import register_product_commands


def register_commands(app: typer.Typer) -> None:
    """Register every command group on the root CLI app."""
    register_product_commands(app)
    register_lakespec_commands(app)
    register_init_lake_commands(app)
