"""CLI adapter for product-to-fullspec generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import PRODUCT_GENERATE_EPILOG, PRODUCT_GENERATE_HELP
from ..operations import CommandError, product_to_fullspec
from ..models.product import ProductValidationFailure


def register_lakespec_commands(app: typer.Typer) -> None:
    """Register fullspec generation commands on a Typer app."""
    app.command(
        "generate",
        help=PRODUCT_GENERATE_HELP,
        epilog=PRODUCT_GENERATE_EPILOG,
        short_help="Generate product fullspec",
    )(generate_lakespec_command)


def generate_lakespec_command(
    product: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Product JSON/YAML file to transform",
        ),
    ],
    environment: Annotated[
        str,
        typer.Argument(help="Workspace environment name, e.g. environments/aws.dev"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
            "-w",
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="Workspace root containing jsonnetfile.json",
        ),
    ] = Path("."),
) -> None:
    try:
        fullspec = product_to_fullspec(product, environment, workspace)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ProductValidationFailure as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(fullspec, indent=2))
