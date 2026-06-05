"""Business logic for `lake create`."""

from __future__ import annotations

from pathlib import Path

from .. import feature_model
from ..models.product import ProductValidator
from .common import (
    JsonObject,
    load_product_data,
    validate_product_data,
    validate_workspace,
    write_environment_json,
)
from .environment_spec import update_environment_spec_json
from .fullspec_validation import validate_fullspec_scheme_tls_consistency
from .lake_environment import initialized_lake_environment_dir


def product_to_fullspec(
    product_path: Path,
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context_name: str | None = None,
    namespace: str | None = None,
) -> JsonObject:
    """Transform a product file into a fullspec for an environment."""
    product_data = load_product_data(product_path)
    return product_data_to_fullspec(
        product_data,
        environment,
        workspace_path,
        product_source=product_path,
        context_name=context_name,
        namespace=namespace,
    )


def product_data_to_fullspec(
    product_data: JsonObject,
    environment: str,
    workspace_path: Path = Path("."),
    *,
    product_source: Path = Path("<generated-product>"),
    context_name: str | None = None,
    namespace: str | None = None,
) -> JsonObject:
    """Transform an in-memory product into environment product files."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    product = validate_product_data(product_source, product_data)
    fullspec = ProductValidator(feature_model).validate(product)
    validate_fullspec_scheme_tls_consistency(fullspec)

    write_environment_json(environment_dir / "product.json", product_data)
    write_environment_json(environment_dir / "product_fullspec.json", fullspec)

    if context_name is not None or namespace is not None:
        update_environment_spec_json(
            environment_dir / "spec.json",
            environment_dir.relative_to(workspace.path),
            product_data,
            context_name=context_name,
            namespace=namespace,
        )

    return fullspec
