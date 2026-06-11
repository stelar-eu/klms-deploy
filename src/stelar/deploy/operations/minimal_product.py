"""Compatibility facade for minimal product generation operations."""

from __future__ import annotations

from kubernetes import client as kube_client
from kubernetes import config as kube_config

from .common import CommandError
from .minimal_product_builder import build_minimal_product
from .minimal_product_types import (
    DEFAULT_MINIMAL_SECRET_NAMES,
    InferredStorageClasses,
    MinimalProductConfig,
    MinimalSecretNames,
)
from .storage_inference import (
    PREFERRED_STORAGE_CLASS_NAMES,
    infer_storage_classes_from_cluster,
)

__all__ = [
    "CommandError",
    "DEFAULT_MINIMAL_SECRET_NAMES",
    "InferredStorageClasses",
    "MinimalProductConfig",
    "MinimalSecretNames",
    "PREFERRED_STORAGE_CLASS_NAMES",
    "build_minimal_product",
    "infer_storage_classes_from_cluster",
    "kube_client",
    "kube_config",
]
