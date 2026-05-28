"""Deployment operation package for `stelarctl`.

The Typer layer imports from this package and should remain thin. Operation
modules own deployment business logic and reusable helpers.
"""

from .cluster import PreflightAccessError, init_lake_cluster
from .common import (
    CommandError,
    load_product,
    load_product_data,
    validate_environment,
    validate_workspace,
)
from .lake_environment import init_lake_environment
from .lake_workspace import init_lake_workspace
from .lakespec import product_to_fullspec
from .manual_tls import MANUAL_TLS_FILE_NAME, write_manual_tls_sample
from .minimal_product import (
    build_minimal_product,
    generate_minimal_secret_values,
    infer_storage_classes_from_cluster,
)

__all__ = [
    "CommandError",
    "PreflightAccessError",
    "build_minimal_product",
    "generate_minimal_secret_values",
    "infer_storage_classes_from_cluster",
    "init_lake_cluster",
    "init_lake_environment",
    "init_lake_workspace",
    "load_product",
    "load_product_data",
    "MANUAL_TLS_FILE_NAME",
    "product_to_fullspec",
    "validate_environment",
    "validate_workspace",
    "write_manual_tls_sample",
]
