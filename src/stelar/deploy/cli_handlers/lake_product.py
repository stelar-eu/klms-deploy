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
    activate_lake_product,
    lake_environment_info,
    product_data_to_fullspec,
    product_fullspec_json_filename,
    product_json_filename,
    product_name_from_path,
    product_to_fullspec,
)
from ..operations.bootstrap_state import (
    bootstrapped_product_or_none,
    reject_bootstrap_target_overrides,
)
from ..operations.common import read_environment_json
from ..operations.environment_spec import (
    environment_active_product,
    environment_active_product_name_or_none,
    update_environment_target_fields,
    validate_environment_target_fields,
)
from ..operations.minimal_product import infer_storage_classes_from_cluster
from .minimal_product import echo_inferred_storage, prompt_minimal_product
from .progress import TyperLakeActivationProgress


def lake_create_command(
    product_or_env: Annotated[
        str,
        typer.Argument(
            help="Product JSON/YAML file, or PRODUCT_NAME when --minimal is used",
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
                "Kubectl context to write to spec.json in --minimal mode; "
                "also used by --infer-storage-from-cluster"
            ),
        ),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Kubernetes namespace to write to spec.json in --minimal mode",
        ),
    ] = None,
    minimal: Annotated[
        bool,
        typer.Option(
            "--minimal",
            help="Interactively create a minimal product directly in ENV",
        ),
    ] = False,
    custom_secret_names: Annotated[
        bool,
        typer.Option(
            "--custom-secret-names",
            help="Prompt for minimal-product Kubernetes Secret name overrides",
        ),
    ] = False,
    infer_storage_from_cluster: Annotated[
        bool,
        typer.Option(
            "--infer-storage-from-cluster",
            help="Infer minimal-product StorageClass values from kubectl",
        ),
    ] = False,
    print_fullspec: Annotated[
        bool,
        typer.Option(
            "--print-fullspec",
            help="Print the generated fullspec JSON to stdout",
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
            custom_secret_names=custom_secret_names,
            infer_storage_from_cluster=infer_storage_from_cluster,
            print_fullspec=print_fullspec,
        )
        return

    if _minimal_options_used(
        custom_secret_names=custom_secret_names,
        infer_storage_from_cluster=infer_storage_from_cluster,
    ):
        raise typer.BadParameter("Minimal-product options require --minimal")
    if env is None:
        raise typer.BadParameter(
            "Missing ENV argument. Use `lake create PRODUCT ENV` or "
            "`lake create --minimal PRODUCT_NAME ENV`."
        )

    product_path = _product_path(product_or_env)
    try:
        product_name = product_name_from_path(product_path)
        if context is not None or namespace is not None:
            raise CommandError(
                "lake create only transforms products; activate a generated "
                "product with lake activate. Persist target fields with "
                "lake add --context/--namespace, or pass them only to "
                "lake verify for read-only checks."
            )
        fullspec = product_to_fullspec(
            product_path,
            env,
            workspace,
            product_name=product_name,
        )
        _echo_generated_product_paths(
            env,
            workspace,
            product_name,
            err=print_fullspec,
        )
        _warn_if_regenerated_active_product_is_stale(
            env,
            workspace,
            product_name,
            fullspec,
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ProductValidationFailure as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if print_fullspec:
        typer.echo(json.dumps(fullspec, indent=2))


def _create_minimal_lake(
    product_name: str,
    environment: str | None,
    workspace: Path,
    *,
    context: str | None,
    namespace: str | None,
    custom_secret_names: bool,
    infer_storage_from_cluster: bool,
    print_fullspec: bool,
) -> None:
    if environment is None:
        raise typer.BadParameter(
            "With --minimal, use `lake create --minimal PRODUCT_NAME ENV`."
        )

    try:
        context, namespace = validate_environment_target_fields(
            context_name=context,
            namespace=namespace,
        )
        environment_info = lake_environment_info(environment, workspace)
        spec_path = environment_info.path / "spec.json"
        spec_json = read_environment_json(spec_path)
        reject_bootstrap_target_overrides(
            spec_json,
            context=context,
            namespace=namespace,
        )
        product_path = environment_info.path / product_json_filename(product_name)
        product_fullspec_path = environment_info.path / product_fullspec_json_filename(
            product_name
        )

        inferred_storage = (
            infer_storage_classes_from_cluster(context)
            if infer_storage_from_cluster
            else None
        )
        if inferred_storage is not None:
            echo_inferred_storage(inferred_storage)

        product = prompt_minimal_product(
            custom_secret_names=custom_secret_names,
            inferred_storage=inferred_storage,
        )
        fullspec = product_data_to_fullspec(
            product,
            environment,
            workspace,
            product_source=product_path,
            product_name=product_name,
        )
        updated_target_fields = update_environment_target_fields(
            spec_path,
            context_name=context,
            namespace=namespace,
        )
        _echo_updated_target_fields(updated_target_fields, err=print_fullspec)
        _warn_if_regenerated_active_product_is_stale(
            environment,
            workspace,
            product_name,
            fullspec,
        )

        typer.echo(f"Wrote minimal product: {product_path}", err=print_fullspec)
        typer.echo(f"Wrote product fullspec: {product_fullspec_path}", err=print_fullspec)
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ProductValidationFailure as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if print_fullspec:
        typer.echo(json.dumps(fullspec, indent=2))


def _echo_generated_product_paths(
    environment: str,
    workspace: Path,
    product_name: str,
    *,
    err: bool,
) -> None:
    environment_path = lake_environment_info(environment, workspace).path
    typer.echo(
        f"Wrote product: {environment_path / product_json_filename(product_name)}",
        err=err,
    )
    typer.echo(
        "Wrote product fullspec: "
        f"{environment_path / product_fullspec_json_filename(product_name)}",
        err=err,
    )


def _echo_updated_target_fields(updated_fields: set[str], *, err: bool) -> None:
    if "context" in updated_fields:
        typer.echo("Updated environment context in spec.json", err=err)
    if "namespace" in updated_fields:
        typer.echo("Updated environment namespace in spec.json", err=err)


def _warn_if_regenerated_active_product_is_stale(
    environment: str,
    workspace: Path,
    product_name: str,
    fullspec: dict[str, object],
) -> None:
    normalized_product_name = Path(product_json_filename(product_name)).stem
    try:
        environment_info = lake_environment_info(environment, workspace)
        spec_json = read_environment_json(environment_info.path / "spec.json")
        active_name = environment_active_product_name_or_none(spec_json)
        if active_name != normalized_product_name:
            return
        active_fullspec = environment_active_product(spec_json)
    except CommandError:
        return

    if active_fullspec == fullspec:
        return
    if bootstrapped_product_or_none(spec_json) is not None:
        typer.echo(
            "Warning: regenerated active product "
            f"{normalized_product_name!r}, but this environment has recorded "
            "bootstrap state for the previous fullspec. Purge old bootstrap "
            f"Secrets with `stelarctl lake purge-secrets {environment}`, then "
            f"run `stelarctl lake activate {normalized_product_name} "
            f"{environment}`, then run `stelarctl lake bootstrap {environment}` "
            "for the regenerated fullspec.",
            err=True,
        )
        return
    typer.echo(
        "Warning: regenerated active product "
        f"{normalized_product_name!r}, but spec.stelar.active_product still "
        "contains the previous fullspec. Run `stelarctl lake activate "
        f"{normalized_product_name} {environment}` to render the regenerated "
        "fullspec.",
        err=True,
    )


def _minimal_options_used(
    *,
    custom_secret_names: bool,
    infer_storage_from_cluster: bool,
) -> bool:
    return custom_secret_names or infer_storage_from_cluster


def _product_path(product: str) -> Path:
    product_path = Path(product).expanduser().resolve()
    if not product_path.is_file():
        raise typer.BadParameter(f"Product file {product_path} does not exist")
    return product_path


def lake_activate_command(
    product_name: Annotated[
        str,
        typer.Argument(help="Generated product name, with or without .json"),
    ],
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
        fullspec = activate_lake_product(
            product_name,
            env,
            workspace,
            progress=TyperLakeActivationProgress(),
        )
    except CommandError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Activated product: {product_name}")
    typer.echo(json.dumps(fullspec, indent=2))
