from __future__ import annotations

import time
from pathlib import Path

import typer
from kubernetes import config

try:
    from .deploy import perform_deploy, teardown_target
    from .env import resolve_env_target
    from .generator import write_main_jsonnet
    from .loader import load_model
    from .platform_model import PlatformModel
    from .secrets import apply_generated_secrets, apply_secrets, delete_secrets
    from .status import collect_inferred_status, format_status
except ImportError:
    from deploy import perform_deploy, teardown_target
    from env import resolve_env_target
    from generator import write_main_jsonnet
    from loader import load_model
    from platform_model import PlatformModel
    from secrets import apply_generated_secrets, apply_secrets, delete_secrets
    from status import collect_inferred_status, format_status


app = typer.Typer(name="stelarctl", help="STELAR platform deployment tool")


def _load(model_path: Path) -> PlatformModel:
    return load_model(str(model_path), PlatformModel)


def _clear_screen():
    typer.echo("\033[2J\033[H", nl=False)


def _resolve_status_target(
    env: Path | None,
    context_name: str | None,
    namespace: str | None,
) -> tuple[str, str]:
    if env is not None:
        return resolve_env_target(env)
    if context_name and namespace:
        return context_name, namespace

    contexts, active = config.list_kube_config_contexts()
    if not active:
        raise typer.BadParameter("No active Kubernetes context found. Provide --env or --context/--namespace.")
    if context_name:
        for entry in contexts:
            if entry["name"] == context_name:
                return context_name, namespace or entry.get("context", {}).get("namespace") or "default"
        raise typer.BadParameter(f"Kubernetes context '{context_name}' not found.")
    active_namespace = active.get("context", {}).get("namespace") or "default"
    return active["name"], namespace or active_namespace


def _resolve_target(
    env: Path | None,
    context_name: str | None,
    namespace: str | None,
) -> tuple[str, str]:
    return _resolve_status_target(env, context_name, namespace)


@app.command()
def generate(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    env: Path = typer.Option(..., "--env", "-e", help="Path to Tanka environment directory"),
):
    """Generate main.jsonnet for a Tanka environment from a platform model."""
    pm = _load(model)
    write_main_jsonnet(pm, str(env))


@app.command("status")
def status_command(
    env: Path | None = typer.Option(None, "--env", "-e", help="Path to Tanka environment directory"),
    context_name: str | None = typer.Option(None, "--context", help="Kubernetes context to inspect"),
    namespace: str | None = typer.Option(None, "--namespace", help="Namespace to inspect"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Refresh status continuously"),
    interval: int = typer.Option(5, "--interval", "-i", min=1, help="Watch refresh interval in seconds"),
):
    """Show live deployment progress as a percentage and loading bar."""
    resolved_context, resolved_namespace = _resolve_status_target(env, context_name, namespace)

    while True:
        snapshot, warnings = collect_inferred_status(resolved_context, resolved_namespace)
        if watch:
            _clear_screen()
        if snapshot is None:
            typer.echo(f"No active STELAR deployment found in {resolved_context}/{resolved_namespace}.")
        else:
            typer.echo("Model source: inferred from live cluster")
            typer.echo(format_status(snapshot))
        if warnings:
            typer.echo("")
            typer.echo("Warnings:")
            for warning in warnings:
                typer.echo(f"- {warning}")
        if not watch:
            break
        time.sleep(interval)


@app.command()
def secrets_apply(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    generated: bool = typer.Option(True, help="Also apply system-generated secrets (e.g. ckan-auth-secret)"),
):
    """Apply secrets defined in the platform model to the cluster."""
    pm = _load(model)
    apply_secrets(pm)
    typer.echo("User-defined secrets applied.")
    if generated:
        apply_generated_secrets(pm)
        typer.echo("Generated secrets applied.")


@app.command()
def secrets_delete(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Delete all secrets in the namespace defined by the platform model."""
    pm = _load(model)
    if not confirm:
        typer.confirm(
            f"Delete ALL secrets in namespace '{pm.namespace}' on context '{pm.k8s_context}'?",
            abort=True,
        )
    delete_secrets(pm)
    typer.echo(f"All secrets deleted from namespace '{pm.namespace}'.")


@app.command()
def deploy(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    env: Path = typer.Option(..., "--env", "-e", help="Path to Tanka environment directory"),
    auto_approve: bool = typer.Option(False, "--yes", "-y", help="Skip hard-redeploy confirmation prompt"),
    wait: bool = typer.Option(False, "--wait", help="Wait until the deployment reaches Ready 100%"),
    wait_timeout: int = typer.Option(600, "--wait-timeout", min=1, help="Maximum seconds to wait for readiness"),
    wait_interval: int = typer.Option(5, "--wait-interval", min=1, help="Polling interval in seconds while waiting"),
):
    """Full deployment: compare state, hard-redeploy if needed, then apply through Tanka."""
    pm = _load(model)
    perform_deploy(
        pm,
        env,
        auto_approve=auto_approve,
        wait=wait,
        wait_timeout=wait_timeout,
        wait_interval=wait_interval,
    )


@app.command()
def teardown(
    env: Path | None = typer.Option(None, "--env", "-e", help="Path to Tanka environment directory"),
    context_name: str | None = typer.Option(None, "--context", help="Kubernetes context to inspect"),
    namespace: str | None = typer.Option(None, "--namespace", help="Namespace to inspect"),
    delete_namespace: bool = typer.Option(False, "--delete-namespace", help="Delete the namespace after purging resources"),
    delete_env: bool = typer.Option(False, "--delete-env", help="Delete the local Tanka environment directory"),
    auto_approve: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Remove deployment resources, optionally deleting the namespace and environment directory."""
    resolved_context, resolved_namespace = _resolve_target(env, context_name, namespace)
    teardown_target(
        resolved_context,
        resolved_namespace,
        env_path=env,
        delete_namespace=delete_namespace,
        delete_env=delete_env,
        auto_approve=auto_approve,
    )


@app.command()
def validate(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
):
    """Validate a platform model YAML without applying anything."""
    pm = _load(model)
    typer.echo(f"Model valid: platform={pm.platform}, tier={pm.tier}, namespace={pm.namespace}")


if __name__ == "__main__":
    app()
