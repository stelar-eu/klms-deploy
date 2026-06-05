"""CLI adapter for `stelarctl lake create`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ..cli_help import LAKE_CREATE_EPILOG, LAKE_CREATE_HELP
from ..models.product import ProductValidationFailure
from ..operations import (
    CommandError,
    lake_environment_info,
    product_data_to_fullspec,
    product_to_fullspec,
)
from ..operations.minimal_product import infer_storage_classes_from_cluster
from .minimal_product import echo_inferred_storage, prompt_minimal_product


def lake_create_command(
    product_or_env: Annotated[
        str,
        typer.Argument(
            help="Product JSON/YAML file, or ENV when --minimal is used",
        ),
    ],
    env: Annotated[
        str | None,
        typer.Argument(
            help="Workspace-relative lake environment path, e.g. dev or lakes/prod",
        ),
    ] = None,
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
            help=(
                "Write this kubectl context to spec.json; also used by "
                "--infer-storage-from-cluster"
            ),
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
    minimal: Annotated[
        bool,
        typer.Option(
            "--minimal",
            help="Interactively create a minimal product directly in ENV",
        ),
    ] = False,
    manual_secrets: Annotated[
        bool,
        typer.Option(
            "--manual-secrets",
            help="Prompt for minimal-product secret values instead of generating them",
        ),
    ] = False,
    infer_storage_from_cluster: Annotated[
        bool,
        typer.Option(
            "--infer-storage-from-cluster",
            help="Infer minimal-product StorageClass values from kubectl",
        ),
    ] = False,
) -> None:
    if minimal:
        _create_minimal_lake(
            product_or_env,
            env,
            workspace,
            context=context,
            namespace=namespace,
            manual_secrets=manual_secrets,
            infer_storage_from_cluster=infer_storage_from_cluster,
        )
        return

    if _minimal_options_used(
        manual_secrets=manual_secrets,
        infer_storage_from_cluster=infer_storage_from_cluster,
    ):
        raise typer.BadParameter("Minimal-product options require --minimal")
    if env is None:
        raise typer.BadParameter(
            "Missing ENV argument. Use `lake create PRODUCT ENV` or "
            "`lake create --minimal ENV`."
        )

    product_path = _product_path(product_or_env)
    try:
        fullspec = product_to_fullspec(
            product_path,
            env,
            workspace,
            context_name=context,
            namespace=namespace,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ProductValidationFailure as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(fullspec, indent=2))


def _create_minimal_lake(
    environment: str,
    extra_env: str | None,
    workspace: Path,
    *,
    context: str | None,
    namespace: str | None,
    manual_secrets: bool,
    infer_storage_from_cluster: bool,
) -> None:
    if extra_env is not None:
        raise typer.BadParameter(
            "With --minimal, pass only ENV: `lake create --minimal ENV`."
        )

    try:
        environment_info = lake_environment_info(environment, workspace)
        product_path = environment_info.path / "product.json"

        inferred_storage = (
            infer_storage_classes_from_cluster(context)
            if infer_storage_from_cluster
            else None
        )
        if inferred_storage is not None:
            echo_inferred_storage(inferred_storage)

        product = prompt_minimal_product(
            manual_secrets=manual_secrets,
            inferred_storage=inferred_storage,
            namespace=namespace,
        )
        fullspec = product_data_to_fullspec(
            product,
            environment,
            workspace,
            product_source=product_path,
            context_name=context,
            namespace=namespace,
        )

        typer.echo(f"Wrote minimal product: {product_path}")
        typer.echo(
            "Wrote product fullspec: "
            f"{environment_info.path / 'product_fullspec.json'}"
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ProductValidationFailure as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(fullspec, indent=2))


def _minimal_options_used(
    *,
    manual_secrets: bool,
    infer_storage_from_cluster: bool,
) -> bool:
    return manual_secrets or infer_storage_from_cluster


def _product_path(product: str) -> Path:
    product_path = Path(product).expanduser().resolve()
    if not product_path.is_file():
        raise typer.BadParameter(f"Product file {product_path} does not exist")
    return product_path
