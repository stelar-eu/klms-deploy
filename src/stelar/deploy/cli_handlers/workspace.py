"""CLI adapter for the `stelarctl workspace` command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import (
    CONTEXT_SETTINGS,
    WORKSPACE_EPILOG,
    WORKSPACE_HELP,
    WORKSPACE_INFO_EPILOG,
    WORKSPACE_INFO_HELP,
    WORKSPACE_INIT_EPILOG,
    WORKSPACE_INIT_HELP,
    show_help_on_no_args,
)
from ..operations import CommandError, init_workspace, workspace_info
from ..operations.lake_workspace import WorkspaceInfo
from .formatting import item_list, presence, yes_no
from .progress import TyperLakeWorkspaceProgress


def register_workspace_commands(app: typer.Typer) -> None:
    """Register workspace lifecycle commands on the root CLI app."""
    workspace_app = typer.Typer(
        help=WORKSPACE_HELP,
        epilog=WORKSPACE_EPILOG,
        invoke_without_command=True,
        callback=show_help_on_no_args,
        context_settings=CONTEXT_SETTINGS,
    )
    workspace_app.command(
        "init",
        help=WORKSPACE_INIT_HELP,
        epilog=WORKSPACE_INIT_EPILOG,
        short_help="Initialize a workspace root",
    )(workspace_init_command)
    workspace_app.command(
        "info",
        help=WORKSPACE_INFO_HELP,
        epilog=WORKSPACE_INFO_EPILOG,
        short_help="Show workspace state",
    )(workspace_info_command)
    app.add_typer(workspace_app, name="workspace")


def workspace_init_command(
    workspace: Annotated[
        Path,
        typer.Argument(
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Workspace root to initialize",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Rewrite jsonnetfile.json when it exists"),
    ] = False,
) -> None:
    try:
        init_workspace(
            workspace,
            force=force,
            progress=TyperLakeWorkspaceProgress(),
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def workspace_info_command(
    workspace: Annotated[
        Path,
        typer.Argument(
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="Workspace root to inspect",
        ),
    ] = Path("."),
) -> None:
    try:
        info = workspace_info(workspace)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo_workspace_info(info)


def _echo_workspace_info(info: WorkspaceInfo) -> None:
    typer.echo(f"Workspace: {info.path}")
    typer.echo(f"initialized: {yes_no(info.initialized)}")
    typer.echo(f"jsonnetfile.json: {presence(info.jsonnetfile)}")
    typer.echo(f"lib/: {presence(info.lib)}")
    typer.echo(f"vendor/: {presence(info.vendor)}")
    typer.echo(f"lake environments: {len(info.environments)}")
    typer.echo("Environments:")
    if not info.environments:
        typer.echo("  (none)")
    else:
        for environment in info.environments:
            typer.echo(f"  - {environment.name}")
            typer.echo(f"    main.jsonnet: {presence(environment.main_jsonnet)}")
            typer.echo(f"    spec.json: {presence(environment.spec_json)}")
            typer.echo(f"    active product: {presence(environment.active_product)}")
            typer.echo(
                "    generated products: "
                f"{item_list(environment.generated_products)}"
            )

    if not info.initialized:
        typer.echo("")
        typer.echo("Next step:")
        typer.echo(f"  stelarctl workspace init {info.path}")
