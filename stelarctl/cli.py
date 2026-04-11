import typer
from pathlib import Path
from typing import Optional

from loader import load_model
from platform_model import PlatformModel
from generator import write_main_jsonnet
from secrets import apply_secrets, apply_generated_secrets, delete_secrets

app = typer.Typer(name="stelarctl", help="STELAR platform deployment tool")


def _load(model_path: Path) -> PlatformModel:
    return load_model(str(model_path), PlatformModel)


@app.command()
def generate(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    env: Path = typer.Option(..., "--env", "-e", help="Path to Tanka environment directory"),
):
    """Generate main.jsonnet for a Tanka environment from a platform model."""
    pm = _load(model)
    write_main_jsonnet(pm, str(env))


@app.command()
def secrets_apply(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    generated: bool = typer.Option(True, help="Also apply system-generated secrets (e.g. ckan-auth-secret)"),
):
    """Apply secrets defined in the platform model to the cluster."""
    pm = _load(model)
    apply_secrets(pm)
    typer.echo("✅ User-defined secrets applied.")
    if generated:
        apply_generated_secrets(pm)
        typer.echo("✅ Generated secrets applied.")


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
    typer.echo(f"✅ All secrets deleted from namespace '{pm.namespace}'.")


@app.command()
def deploy(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
    env: Path = typer.Option(..., "--env", "-e", help="Path to Tanka environment directory"),
    skip_secrets: bool = typer.Option(False, "--skip-secrets", help="Skip secret application"),
):
    """Full deployment: apply secrets and generate main.jsonnet."""
    pm = _load(model)

    if not skip_secrets:
        apply_secrets(pm)
        apply_generated_secrets(pm)
        typer.echo("✅ Secrets applied.")

    write_main_jsonnet(pm, str(env))
    typer.echo("✅ main.jsonnet generated. Run 'tk apply <env>' to deploy.")


@app.command()
def validate(
    model: Path = typer.Argument(..., help="Path to platform model YAML"),
):
    """Validate a platform model YAML without applying anything."""
    pm = _load(model)
    typer.echo(f"✅ Model valid: platform={pm.platform}, tier={pm.tier}, namespace={pm.namespace}")


if __name__ == "__main__":
    app()
