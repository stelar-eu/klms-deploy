"""CLI adapter for the `stelarctl lake` command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import (
    CONTEXT_SETTINGS,
    LAKE_BOOTSTRAP_EPILOG,
    LAKE_BOOTSTRAP_HELP,
    LAKE_VERIFY_EPILOG,
    LAKE_VERIFY_HELP,
    INIT_LAKE_ENVIRONMENT_EPILOG,
    INIT_LAKE_ENVIRONMENT_HELP,
    INIT_LAKE_EPILOG,
    INIT_LAKE_HELP,
    LAKE_CREATE_EPILOG,
    LAKE_CREATE_HELP,
    LAKE_INFO_EPILOG,
    LAKE_INFO_HELP,
    LAKE_LIST_EPILOG,
    LAKE_LIST_HELP,
    LAKE_MANUAL_TLS_TEMPLATE_EPILOG,
    LAKE_MANUAL_TLS_TEMPLATE_HELP,
    LAKE_REMOVE_EPILOG,
    LAKE_REMOVE_HELP,
    show_help_on_no_args,
)
from ..operations.lake_workspace import WorkspaceEnvironmentInfo
from .lakespec import lake_create_command
from .progress import (
    TyperClusterProgress,
    TyperLakeEnvironmentProgress,
)
from ..operations import (
    MANUAL_TLS_FILE_NAME,
    CommandError,
    PreflightAccessError,
    bootstrap_lake,
    check_lake_cluster,
    init_lake_environment,
    lake_environment_info,
    list_lake_environments,
    remove_lake_environment,
    write_manual_tls_sample,
)


def register_init_lake_commands(app: typer.Typer) -> None:
    """Register `lake` and its subcommands on the root CLI app."""
    init_lake_app = typer.Typer(
        help=INIT_LAKE_HELP,
        epilog=INIT_LAKE_EPILOG,
        invoke_without_command=True,
        callback=show_help_on_no_args,
        context_settings=CONTEXT_SETTINGS,
    )
    init_lake_app.command(
        "add",
        help=INIT_LAKE_ENVIRONMENT_HELP,
        epilog=INIT_LAKE_ENVIRONMENT_EPILOG,
        short_help="Add an environment directory",
    )(init_lake_environment_command)
    init_lake_app.command(
        "create",
        help=LAKE_CREATE_HELP,
        epilog=LAKE_CREATE_EPILOG,
        short_help="Create product files",
    )(lake_create_command)
    init_lake_app.command(
        "list",
        help=LAKE_LIST_HELP,
        epilog=LAKE_LIST_EPILOG,
        short_help="List lake environments",
    )(lake_list_command)
    init_lake_app.command(
        "info",
        help=LAKE_INFO_HELP,
        epilog=LAKE_INFO_EPILOG,
        short_help="Show one lake environment",
    )(lake_info_command)
    init_lake_app.command(
        "remove",
        help=LAKE_REMOVE_HELP,
        epilog=LAKE_REMOVE_EPILOG,
        short_help="Remove a lake environment",
    )(lake_remove_command)
    init_lake_app.command(
        "manual-tls-template",
        help=LAKE_MANUAL_TLS_TEMPLATE_HELP,
        epilog=LAKE_MANUAL_TLS_TEMPLATE_EPILOG,
        short_help="Write manual TLS template",
    )(lake_manual_tls_template_command)
    init_lake_app.command(
        "verify",
        help=LAKE_VERIFY_HELP,
        epilog=LAKE_VERIFY_EPILOG,
        short_help="Verify cluster readiness",
    )(lake_verify_command)
    init_lake_app.command(
        "bootstrap",
        help=LAKE_BOOTSTRAP_HELP,
        epilog=LAKE_BOOTSTRAP_EPILOG,
        short_help="Prepare cluster metadata and secrets",
    )(lake_bootstrap_command)
    app.add_typer(init_lake_app, name="lake")


def init_lake_environment_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace-relative lake environment path"),
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
    adopt_existing_main: Annotated[
        bool,
        typer.Option(
            "--adopt-existing-main",
            help=(
                "Allow lake add to mark an environment whose main.jsonnet "
                "already exists but spec.json is missing or unmarked"
            ),
        ),
    ] = False,
) -> None:
    try:
        init_lake_environment(
            env,
            workspace,
            progress=TyperLakeEnvironmentProgress(),
            adopt_existing_main=adopt_existing_main,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def lake_list_command(
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
        environments = list_lake_environments(workspace)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Lake environments: {len(environments)}")
    if not environments:
        typer.echo("  (none)")
        return

    for environment in environments:
        typer.echo(f"  - {environment.name}")
        typer.echo(f"    path: {environment.path}")
        typer.echo(f"    product: {_presence(environment.product_json)}")
        typer.echo(f"    fullspec: {_presence(environment.product_fullspec_json)}")


def lake_info_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace-relative lake environment path"),
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
        environment = lake_environment_info(env, workspace)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo_lake_environment_info(environment)


def lake_remove_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace-relative lake environment path"),
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
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Delete without an interactive prompt"),
    ] = False,
) -> None:
    try:
        environment = lake_environment_info(env, workspace)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not yes:
        confirmed = typer.confirm(
            f"Delete lake environment {environment.name!r} at {environment.path}?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit(code=1)

    try:
        remove_lake_environment(
            env,
            workspace,
            progress=TyperLakeEnvironmentProgress(),
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _echo_lake_environment_info(environment: WorkspaceEnvironmentInfo) -> None:
    typer.echo(f"Lake environment: {environment.name}")
    typer.echo(f"path: {environment.path}")
    typer.echo(f"main.jsonnet: {_presence(environment.main_jsonnet)}")
    typer.echo(f"spec.json: {_presence(environment.spec_json)}")
    typer.echo(f"product.json: {_presence(environment.product_json)}")
    typer.echo(f"product_fullspec.json: {_presence(environment.product_fullspec_json)}")


def _presence(present: bool) -> str:
    return "present" if present else "missing"


def lake_manual_tls_template_command(
    output: Annotated[
        Path,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            resolve_path=True,
            help="Manual TLS secret input YAML file to create",
        ),
    ] = Path(MANUAL_TLS_FILE_NAME),
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing output file"),
    ] = False,
) -> None:
    try:
        write_manual_tls_sample(output, force=force)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Wrote manual TLS sample: {output}")
    typer.echo(
        "Edit each endpoint value so it points to a folder containing tls.crt "
        "and tls.key, then place the file at ENV/manual_tls.yaml "
        "before running lake bootstrap."
    )



def lake_verify_command(
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
        typer.Option(
            "--context",
            help="Kubectl context to check without writing spec.json",
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Kubernetes namespace to check without writing spec.json",
        ),
    ] = None,
) -> None:
    try:
        check_lake_cluster(
            env,
            workspace,
            context=context,
            namespace=namespace,
        )
    except PreflightAccessError as exc:
        typer.echo(f"Warning: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo("Lake verification passed.")


def lake_bootstrap_command(
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
    skip_preflight: Annotated[
        bool,
        typer.Option(
            "--skip-preflight",
            help="Skip read-only prerequisite checks before applying secrets",
        ),
    ] = False,
) -> None:
    try:
        bootstrap_lake(
            env,
            workspace,
            preflight="skip" if skip_preflight else "strict",
            progress=TyperClusterProgress(),
        )
    except PreflightAccessError as exc:
        typer.echo(f"Warning: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
