"""Business logic for `product generate`."""

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
from .fullspec_validation import validate_fullspec_scheme_tls_consistency
from .lake_environment import initialized_lake_environment_dir


def product_to_fullspec(
    product_path: Path,
    environment: str,
    workspace_path: Path = Path("."),
) -> JsonObject:
    """Transform a product file into a fullspec for an environment."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    product_data = load_product_data(product_path)
    product = validate_product_data(product_path, product_data)
    fullspec = ProductValidator(feature_model).validate(product)
    validate_fullspec_scheme_tls_consistency(fullspec)

    write_environment_json(environment_dir / "product.json", product_data)
    write_environment_json(environment_dir / "product_fullspec.json", fullspec)

    return fullspec
