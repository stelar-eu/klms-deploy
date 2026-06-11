"""CLI adapter for the `stelarctl lake` command group."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import (
    CONTEXT_SETTINGS,
    LAKE_ACTIVATE_EPILOG,
    LAKE_ACTIVATE_HELP,
    LAKE_BOOTSTRAP_EPILOG,
    LAKE_BOOTSTRAP_HELP,
    LAKE_VERIFY_EPILOG,
    LAKE_VERIFY_HELP,
    LAKE_ADD_EPILOG,
    LAKE_ADD_HELP,
    LAKE_EPILOG,
    LAKE_HELP,
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
    LAKE_PURGE_SECRETS_EPILOG,
    LAKE_PURGE_SECRETS_HELP,
    LAKE_STATUS_EPILOG,
    LAKE_STATUS_HELP,
    show_help_on_no_args,
)
from ..operations.lake_workspace import WorkspaceEnvironmentInfo
from .bootstrap_secrets import prompt_bootstrap_secret_values
from .formatting import item_list, presence
from .lake_product import lake_activate_command, lake_create_command
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
    add_lake_environment,
    inspect_lake_status,
    lake_environment_info,
    plan_lake_secret_purge,
    purge_lake_secrets,
    list_lake_environments,
    remove_lake_environment,
    write_manual_tls_sample,
)


def register_lake_commands(app: typer.Typer) -> None:
    """Register `lake` and its subcommands on the root CLI app."""
    lake_app = typer.Typer(
        help=LAKE_HELP,
        epilog=LAKE_EPILOG,
        invoke_without_command=True,
        callback=show_help_on_no_args,
        context_settings=CONTEXT_SETTINGS,
    )
    lake_app.command(
        "add",
        help=LAKE_ADD_HELP,
        epilog=LAKE_ADD_EPILOG,
        short_help="Add an environment directory",
    )(lake_add_command)
    lake_app.command(
        "create",
        help=LAKE_CREATE_HELP,
        epilog=LAKE_CREATE_EPILOG,
        short_help="Create product files",
    )(lake_create_command)
    lake_app.command(
        "activate",
        help=LAKE_ACTIVATE_HELP,
        epilog=LAKE_ACTIVATE_EPILOG,
        short_help="Set active product",
    )(lake_activate_command)
    lake_app.command(
        "list",
        help=LAKE_LIST_HELP,
        epilog=LAKE_LIST_EPILOG,
        short_help="List lake environments",
    )(lake_list_command)
    lake_app.command(
        "info",
        help=LAKE_INFO_HELP,
        epilog=LAKE_INFO_EPILOG,
        short_help="Show one lake environment",
    )(lake_info_command)
    lake_app.command(
        "remove",
        help=LAKE_REMOVE_HELP,
        epilog=LAKE_REMOVE_EPILOG,
        short_help="Remove a lake environment",
    )(lake_remove_command)
    lake_app.command(
        "manual-tls-template",
        help=LAKE_MANUAL_TLS_TEMPLATE_HELP,
        epilog=LAKE_MANUAL_TLS_TEMPLATE_EPILOG,
        short_help="Write manual TLS template",
    )(lake_manual_tls_template_command)
    lake_app.command(
        "verify",
        help=LAKE_VERIFY_HELP,
        epilog=LAKE_VERIFY_EPILOG,
        short_help="Verify cluster readiness",
    )(lake_verify_command)
    lake_app.command(
        "status",
        help=LAKE_STATUS_HELP,
        epilog=LAKE_STATUS_EPILOG,
        short_help="Inspect deployment status",
    )(lake_status_command)
    lake_app.command(
        "purge-secrets",
        help=LAKE_PURGE_SECRETS_HELP,
        epilog=LAKE_PURGE_SECRETS_EPILOG,
        short_help="Delete bootstrap Secrets",
    )(lake_purge_secrets_command)
    lake_app.command(
        "bootstrap",
        help=LAKE_BOOTSTRAP_HELP,
        epilog=LAKE_BOOTSTRAP_EPILOG,
        short_help="Prepare cluster metadata and secrets",
    )(lake_bootstrap_command)
    app.add_typer(lake_app, name="lake")


def lake_add_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace-relative lake environment path"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
            help="Write this kubectl context to spec.json",
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Write this Kubernetes namespace to spec.json",
        ),
    ] = None,
    adopt_existing_main: Annotated[
        bool,
        typer.Option(
            "--adopt-existing-main",
            help=(
                "Adopt an existing main.jsonnet only when it matches the "
                "managed stelarctl template, then mark spec.json"
            ),
        ),
    ] = False,
) -> None:
    try:
        add_lake_environment(
            env,
            workspace,
            progress=TyperLakeEnvironmentProgress(),
            adopt_existing_main=adopt_existing_main,
            context_name=context,
            namespace=namespace,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def lake_list_command(
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
        typer.echo(f"    active product: {presence(environment.active_product)}")
        typer.echo(f"    generated products: {item_list(environment.generated_products)}")


def lake_info_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace-relative lake environment path"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Remove even when active product or bootstrap metadata would be lost",
        ),
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
            force=force,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _echo_lake_environment_info(environment: WorkspaceEnvironmentInfo) -> None:
    typer.echo(f"Lake environment: {environment.name}")
    typer.echo(f"path: {environment.path}")
    typer.echo(f"main.jsonnet: {presence(environment.main_jsonnet)}")
    typer.echo(f"spec.json: {presence(environment.spec_json)}")
    typer.echo(f"active product: {presence(environment.active_product)}")
    typer.echo(f"generated products: {item_list(environment.generated_products)}")


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


def lake_status_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace environment name"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
            help="Kubectl context to inspect without writing spec.json",
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Kubernetes namespace to inspect without writing spec.json",
        ),
    ] = None,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait",
            help="Poll init Jobs until they succeed or --job-timeout is reached",
        ),
    ] = False,
    job_timeout: Annotated[
        float | None,
        typer.Option(
            "--job-timeout",
            min=0.0,
            help="Required with --wait: seconds to wait for init Jobs to succeed",
        ),
    ] = None,
    poll_interval: Annotated[
        float | None,
        typer.Option(
            "--poll-interval",
            help="Required with --wait: positive seconds between init Job status polls",
        ),
    ] = None,
) -> None:
    try:
        job_timeout_seconds, poll_interval_seconds = _status_polling_options(
            wait,
            job_timeout,
            poll_interval,
        )
        status = inspect_lake_status(
            env,
            workspace,
            context=context,
            namespace=namespace,
            job_timeout_seconds=job_timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo_lake_status(status)


def _status_polling_options(
    wait: bool,
    job_timeout: float | None,
    poll_interval: float | None,
) -> tuple[float, float]:
    if not wait:
        if job_timeout is not None or poll_interval is not None:
            raise CommandError(
                "--job-timeout and --poll-interval are only valid with --wait"
            )
        return 0.0, 0.0

    if job_timeout is None or poll_interval is None:
        raise CommandError(
            "--wait requires both --job-timeout SECONDS and --poll-interval SECONDS"
        )
    if poll_interval <= 0:
        raise CommandError("--poll-interval must be greater than 0 when --wait is used")
    return job_timeout, poll_interval


def _echo_lake_status(status) -> None:
    typer.echo(f"Lake status: {status.environment}")
    typer.echo(f"context: {status.context}")
    typer.echo(f"namespace: {status.namespace}")
    typer.echo(f"selected components: {item_list(status.selected_components)}")
    for diagnostic in status.diagnostics:
        typer.echo(f"diagnostic: {diagnostic}")
    typer.echo(
        "bootstrap: "
        f"{status.bootstrap.state} "
        f"({len(status.bootstrap.existing)}/{len(status.bootstrap.expected)} Secrets present)"
    )
    if status.bootstrap.detail:
        typer.echo(f"bootstrap detail: {status.bootstrap.detail}")
    if status.bootstrap.missing:
        typer.echo(f"missing bootstrap Secrets: {item_list(status.bootstrap.missing)}")

    typer.echo(f"deployment: {status.deployment.state}")
    for workload in status.deployment.workloads:
        typer.echo(
            f"  - {workload.kind} {workload.name} "
            f"[{workload.component}]: {workload.state} - {workload.detail}"
        )
    for note in status.deployment.unchecked_components:
        typer.echo(f"  - {note.component}: unchecked - {note.detail}")


def lake_purge_secrets_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace environment name"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
            help="Kubectl context to target without writing spec.json",
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Kubernetes namespace to target without writing spec.json",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Delete without an interactive prompt"),
    ] = False,
) -> None:
    try:
        plan = plan_lake_secret_purge(
            env,
            workspace,
            context=context,
            namespace=namespace,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not yes:
        confirmed = typer.confirm(
            "Delete "
            f"{len(plan.secret_names)} bootstrap Secrets from namespace "
            f"{plan.namespace!r} on context {plan.context!r}?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit(code=1)

    try:
        result = purge_lake_secrets(plan)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo_lake_secret_purge_result(result)


def _echo_lake_secret_purge_result(result) -> None:
    typer.echo(f"Lake secret purge: {result.plan.environment}")
    typer.echo(f"context: {result.plan.context}")
    typer.echo(f"namespace: {result.plan.namespace}")
    typer.echo(f"expected secrets: {len(result.plan.secret_names)}")
    typer.echo(f"deleted secrets: {item_list(result.deleted)}")
    typer.echo(f"already missing secrets: {item_list(result.missing)}")


def lake_bootstrap_command(
    env: Annotated[
        str,
        typer.Argument(help="Workspace environment name"),
    ],
    workspace: Annotated[
        Path,
        typer.Option(
            "--workspace",
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
    manual_secrets: Annotated[
        bool,
        typer.Option(
            "--manual-secrets",
            help="Prompt for bootstrap Secret values instead of generating them",
        ),
    ] = False,
) -> None:
    try:
        bootstrap_lake(
            env,
            workspace,
            preflight="skip" if skip_preflight else "strict",
            progress=TyperClusterProgress(),
            secret_values_factory=(
                prompt_bootstrap_secret_values if manual_secrets else None
            ),
        )
    except PreflightAccessError as exc:
        typer.echo(f"Warning: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
