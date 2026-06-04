"""CLI adapter for the `stelarctl init-lake` command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import (
    CONTEXT_SETTINGS,
    INIT_LAKE_CLUSTER_EPILOG,
    INIT_LAKE_CLUSTER_HELP,
    INIT_LAKE_ENVIRONMENT_EPILOG,
    INIT_LAKE_ENVIRONMENT_HELP,
    INIT_LAKE_EPILOG,
    INIT_LAKE_HELP,
    show_help_on_no_args,
)
from .progress import (
    TyperClusterProgress,
    TyperLakeEnvironmentProgress,
)
from ..operations import (
    CommandError,
    PreflightAccessError,
    init_lake_cluster,
    init_lake_environment,
)


def register_init_lake_commands(app: typer.Typer) -> None:
    """Register `init-lake` and its subcommands on the root CLI app."""
    init_lake_app = typer.Typer(
        help=INIT_LAKE_HELP,
        epilog=INIT_LAKE_EPILOG,
        invoke_without_command=True,
        callback=show_help_on_no_args,
        context_settings=CONTEXT_SETTINGS,
    )
    init_lake_app.command(
        "environment",
        help=INIT_LAKE_ENVIRONMENT_HELP,
        epilog=INIT_LAKE_ENVIRONMENT_EPILOG,
        short_help="Create an environment directory",
    )(init_lake_environment_command)
    init_lake_app.command(
        "cluster",
        help=INIT_LAKE_CLUSTER_HELP,
        epilog=INIT_LAKE_CLUSTER_EPILOG,
        short_help="Prepare cluster metadata and secrets",
    )(init_lake_cluster_command)
    app.add_typer(init_lake_app, name="init-lake")


def init_lake_environment_command(
    env: Annotated[
        str,
        typer.Argument(help="Environment name to create under environments"),
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
        init_lake_environment(
            env,
            workspace,
            progress=TyperLakeEnvironmentProgress(),
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def init_lake_cluster_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace environment name"),
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
    context: Annotated[
        str | None,
        typer.Option("--context", help="Kubectl context to use"),
    ] = None,
    skip_preflight: Annotated[
        bool,
        typer.Option(
            "--skip-preflight",
            help="Skip read-only prerequisite checks before applying secrets",
        ),
    ] = False,
) -> None:
    try:
        init_lake_cluster(
            env,
            workspace,
            context,
            preflight="skip" if skip_preflight else "strict",
            progress=TyperClusterProgress(),
        )
    except PreflightAccessError as exc:
        typer.echo(f"Warning: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
