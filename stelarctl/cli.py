from pathlib import Path
from typing import Optional

import typer

from env import read_env_target, resolve_deploy_env
from generator import write_tanka_environment
from loader import load_model
from platform_model import PlatformModel
from preflight import validate_model_against_cluster
from purge import purge_resources_in_target
from secrets import apply_generated_secrets, apply_secrets
from status import (
    active_kube_target,
    deployment_progress,
    progress_bar,
    resources_exist_in_target,
)


app = typer.Typer(name="stelarctl", help="STELAR platform deployment tool")


def deploy_flow_pseudocode(platform_model: PlatformModel, env: Optional[Path] = None):
    """Pseudocode for the intended deploy flow. This is not called by the CLI."""

    # 1. Resolve env from model unless --env is provided.
    env_path = resolve_deploy_env(platform_model, env)

    # 2. Validate model references against model.k8s_context/model.namespace.
    valid_platform_model = validate_model_against_cluster(platform_model)

    # 3. Stop before cluster writes if validation fails.
    # validate_model_against_cluster raises before this point when invalid.
    if not valid_platform_model:
        return

    # 4. Check whether the target already contains STELAR deployment resources.
    target_has_resources = resources_exist_in_target(
        platform_model.k8s_context,
        platform_model.namespace,
    )

    # 5. If resources exist, warn and require hard-redeploy confirmation.
    if target_has_resources:
        # confirm_hard_redeploy_or_abort(
        #     context=platform_model.k8s_context,
        #     namespace=platform_model.namespace,
        #     message="Continuing will purge namespace resources, including PVCs.",
        # )
        purge_resources_in_target(platform_model.k8s_context, platform_model.namespace)

    # 6. Apply user and generated secrets.
    apply_secrets(platform_model)
    apply_generated_secrets(platform_model)

    # 7. Generate spec.json/main.jsonnet.
    write_tanka_environment(platform_model, env_path)

    # 8. Hard redeploy/status-aware apply is not implemented on this branch yet.
    raise NotImplementedError("Pseudocode only; implement each deploy step incrementally.")


@app.command()
def deploy(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    env: Optional[Path] = typer.Option(None, "--env", "-e", help="Override inferred Tanka environment directory"),
):
    """Deploy or redeploy STELAR using context and namespace from the model."""
    pm = load_model(str(model), PlatformModel)
    env_path = resolve_deploy_env(pm, env)

    typer.echo(f"Target: {pm.k8s_context}/{pm.namespace}")
    typer.echo(f"Environment: {env_path}")

    validate_model_against_cluster(pm)
    typer.echo("Model validated against cluster.")

    apply_secrets(pm)
    apply_generated_secrets(pm)
    typer.echo("Secrets applied.")

    write_tanka_environment(pm, env_path)
    typer.echo("Tanka environment generated.")
    typer.echo("Hard redeploy/status-aware apply is not implemented on this branch yet.")


@app.command()
def status():
    """Show live progress in the active kubeconfig context and namespace."""
    context, namespace = active_kube_target()
    active, progress, detail = deployment_progress(context, namespace)

    typer.echo(f"Target: {context}/{namespace}")
    if not active:
        typer.echo("No active STELAR resources found.")
        return

    typer.echo(f"Progress: {progress}% {progress_bar(progress)}")
    typer.echo(detail)


@app.command()
def teardown(
    namespace: Optional[str] = typer.Option(None, "--namespace", help="Override active kubeconfig namespace"),
    env: Optional[Path] = typer.Option(None, "--env", "-e", help="Optional Tanka environment metadata"),
):
    """Purge resources from the active kubeconfig context."""
    context, resolved_namespace = active_kube_target(namespace)

    if env is not None:
        env_target = read_env_target(env)
        if env_target and env_target != (context, resolved_namespace):
            raise typer.BadParameter(
                f"Environment {env} targets {env_target[0]}/{env_target[1]}, "
                f"but teardown targets {context}/{resolved_namespace}."
            )

    typer.echo(f"Target: {context}/{resolved_namespace}")
    typer.confirm("Purge all resources from this namespace?", abort=True)
    typer.echo("Teardown purge is not implemented on this branch yet.")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
