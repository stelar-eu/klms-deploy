"""Compatibility facade for minimal product generation operations."""

from __future__ import annotations

from kubernetes import client as kube_client
from kubernetes import config as kube_config

from .common import CommandError
from .minimal_product_builder import (
    build_minimal_product,
    generate_minimal_secret_values,
)
from .minimal_product_reports import (
    SECRET_FILE_MODE,
    build_generated_secret_report,
    default_secret_report_path,
    write_secret_report,
    write_yaml,
)
from .minimal_product_types import (
    MINIMAL_PASSWORD_FIELDS,
    InferredStorageClasses,
    MinimalProductConfig,
    MinimalSecretValues,
)
from .storage_inference import (
    PREFERRED_STORAGE_CLASS_NAMES,
    infer_storage_classes_from_cluster,
)

__all__ = [
    "CommandError",
    "InferredStorageClasses",
    "MINIMAL_PASSWORD_FIELDS",
    "MinimalProductConfig",
    "MinimalSecretValues",
    "PREFERRED_STORAGE_CLASS_NAMES",
    "SECRET_FILE_MODE",
    "build_generated_secret_report",
    "build_minimal_product",
    "default_secret_report_path",
    "generate_minimal_secret_values",
    "infer_storage_classes_from_cluster",
    "kube_client",
    "kube_config",
    "write_secret_report",
    "write_yaml",
]
