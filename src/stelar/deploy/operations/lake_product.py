"""Business logic for `lake create`."""

from __future__ import annotations

import re
from pathlib import Path

from .. import feature_model
from ..models.product import ProductValidator
from .bootstrap_state import (
    bootstrapped_product_or_none,
    validate_bootstrap_product_matches,
    validate_bootstrap_target_matches,
)
from .common import (
    CommandError,
    JsonObject,
    load_product_data,
    read_environment_json,
    validate_product_data,
    validate_workspace,
    write_environment_json,
)
from .deployment_config import deployment_config
from .environment_spec import (
    environment_active_product,
    environment_context_name_or_none,
    environment_namespace_or_none,
    update_environment_active_product,
)
from .kube_context import load_kube_context
from .kubernetes_secrets import check_secret_existence
from .fullspec_validation import validate_fullspec_scheme_tls_consistency
from .lake_environment import initialized_lake_environment_dir
from .progress import LakeActivationProgress
from .secret_resources import expected_bootstrap_secret_names

PRODUCT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def product_to_fullspec(
    product_path: Path,
    environment: str,
    workspace_path: Path = Path("."),
    *,
    product_name: str | None = None,
) -> JsonObject:
    """Transform a product file into a fullspec for an environment."""
    product_data = load_product_data(product_path)
    return product_data_to_fullspec(
        product_data,
        environment,
        workspace_path,
        product_source=product_path,
        product_name=product_name,
    )


def product_data_to_fullspec(
    product_data: JsonObject,
    environment: str,
    workspace_path: Path = Path("."),
    *,
    product_source: Path = Path("<generated-product>"),
    product_name: str | None = None,
) -> JsonObject:
    """Transform an in-memory product into environment product files."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    _validate_environment_unlocked(read_environment_json(environment_dir / "spec.json"))
    product_name = normalize_product_name(
        product_name or product_name_from_path(product_source)
    )
    product = validate_product_data(product_source, product_data)
    fullspec = ProductValidator(feature_model).validate(product)
    validate_fullspec_scheme_tls_consistency(fullspec)

    write_environment_json(
        environment_dir / product_json_filename(product_name),
        product_data,
    )
    product_fullspec_filename = product_fullspec_json_filename(product_name)
    write_environment_json(
        environment_dir / product_fullspec_filename,
        fullspec,
    )
    _activate_if_first_product(environment_dir, fullspec, product_name)
    return fullspec


def _activate_if_first_product(
    environment_dir: Path,
    fullspec: JsonObject,
    product_name: str,
) -> None:
    spec_path = environment_dir / "spec.json"
    try:
        environment_active_product(read_environment_json(spec_path))
    except CommandError as exc:
        if "spec.stelar.active_product" not in str(exc):
            raise
        update_environment_active_product(
            spec_path,
            fullspec,
            product_name=product_name,
        )


def activate_lake_product(
    product_name: str,
    environment: str,
    workspace_path: Path = Path("."),
    progress: LakeActivationProgress | None = None,
) -> JsonObject:
    """Set a generated named product as the environment active product."""
    progress = progress or LakeActivationProgress()
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    product_name = normalize_product_name(product_name)
    product_path = environment_dir / product_json_filename(product_name)
    fullspec_path = environment_dir / product_fullspec_json_filename(product_name)

    if not product_path.is_file():
        raise CommandError(
            f"Lake product {product_name!r} is missing {product_path.name}"
        )
    if not fullspec_path.is_file():
        raise CommandError(
            f"Lake product {product_name!r} is missing {fullspec_path.name}"
        )

    fullspec = read_environment_json(fullspec_path)
    spec_path = environment_dir / "spec.json"
    spec_json = read_environment_json(spec_path)
    _validate_environment_unlocked(spec_json)
    validate_fullspec_scheme_tls_consistency(fullspec, source=fullspec_path.name)
    validate_bootstrap_product_matches(spec_json, fullspec)
    current_fullspec = _current_active_product_or_none(spec_json)
    _notify_activation_bootstrap_state(
        product_name,
        spec_json,
        current_fullspec,
        fullspec,
        progress,
    )
    update_environment_active_product(
        spec_path,
        fullspec,
        product_name=product_name,
    )
    return fullspec


def _validate_environment_unlocked(spec_json: JsonObject) -> None:
    if bootstrapped_product_or_none(spec_json) is None:
        return

    context_name = environment_context_name_or_none(spec_json)
    namespace = environment_namespace_or_none(spec_json)
    if context_name is None or namespace is None:
        raise CommandError(
            "Environment has recorded bootstrap state, but spec.contextNames "
            "or spec.namespace is missing. Restore the original spec.contextNames "
            "and spec.namespace before running this command."
        )
    validate_bootstrap_target_matches(spec_json, context_name, namespace)


def _current_active_product_or_none(spec_json: JsonObject) -> JsonObject | None:
    try:
        return environment_active_product(spec_json)
    except CommandError as exc:
        if "spec.stelar.active_product" not in str(exc):
            raise
        return None


def _notify_activation_bootstrap_state(
    product_name: str,
    spec_json: JsonObject,
    current_fullspec: JsonObject | None,
    target_fullspec: JsonObject,
    progress: LakeActivationProgress,
) -> None:
    if current_fullspec is None:
        return

    context_name = environment_context_name_or_none(spec_json)
    namespace = environment_namespace_or_none(spec_json)
    if context_name is None or namespace is None:
        return

    checked_fullspec = (
        target_fullspec if current_fullspec == target_fullspec else current_fullspec
    )
    config = deployment_config(checked_fullspec)
    secret_names = expected_bootstrap_secret_names(config)
    if not secret_names:
        return

    try:
        load_kube_context(context_name)
        state = check_secret_existence(namespace, secret_names)
    except CommandError as exc:
        progress.activating_despite_bootstrap_check_failure(
            product_name,
            namespace,
            str(exc),
        )
        return

    if current_fullspec == target_fullspec and state.all_exist:
        progress.bootstrapped_product_reactivated(
            product_name,
            namespace,
            secret_names,
        )
        return

    if state.existing:
        progress.activating_despite_existing_bootstrap(
            product_name,
            namespace,
            state.existing,
            secret_names,
        )


def product_name_from_path(product_path: Path) -> str:
    """Derive the environment product name from an input product filename."""
    name = product_path.stem
    if not name or product_path.name == "<generated-product>":
        raise CommandError("Product name is required")
    return normalize_product_name(name)


def normalize_product_name(product_name: str) -> str:
    """Validate and normalize a product name used for ENV/<name>.json files."""
    name = product_name.strip()
    if name.endswith(".json"):
        name = name[:-5]
    if not name:
        raise CommandError("Product name cannot be empty")
    if "/" in name or "\\" in name:
        raise CommandError("Product name must not contain path separators")
    if not PRODUCT_NAME_RE.fullmatch(name):
        raise CommandError(
            "Product name must start with a letter or digit and contain only "
            "letters, digits, dots, underscores, or hyphens"
        )
    return name


def product_json_filename(product_name: str) -> str:
    return f"{normalize_product_name(product_name)}.json"


def product_fullspec_json_filename(product_name: str) -> str:
    return f"{normalize_product_name(product_name)}_fullspec.json"
