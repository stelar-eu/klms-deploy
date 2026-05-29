"""Kubernetes StorageClass inference for generated products."""

from __future__ import annotations

from kubernetes import client as kube_client
from kubernetes import config as kube_config

from .common import CommandError
from .kube_context import resolve_kube_context
from .minimal_product_types import InferredStorageClasses


PREFERRED_STORAGE_CLASS_NAMES = (
    "longhorn",
    "csi-hostpath-sc",
    "local-path",
    "standard",
    "ebs-sc",
    "gp3",
    "gp2",
)


def infer_storage_classes_from_cluster(
    context: str | None = None,
) -> InferredStorageClasses:
    """Infer storage class names from the active or requested kubectl context."""
    context_name = resolve_kube_context(context)
    try:
        kube_config.load_kube_config(context=context_name)
        storage_classes = kube_client.StorageV1Api().list_storage_class()
    except Exception as exc:
        raise CommandError(
            f"Could not infer StorageClass from kubectl context {context_name!r}: {exc}"
        ) from exc

    storage_class_name = _select_storage_class_name(storage_classes.items or [])
    return InferredStorageClasses(
        context=context_name,
        dynamic_storage_class=storage_class_name,
        provisioning_storage_class=storage_class_name,
    )


def _select_storage_class_name(storage_classes: list[object]) -> str:
    names = sorted(
        name
        for name in (
            _storage_class_name(storage_class) for storage_class in storage_classes
        )
        if name
    )
    if not names:
        raise CommandError("No StorageClass found in the active Kubernetes context")

    default_names = sorted(
        name
        for name, storage_class in (
            (_storage_class_name(storage_class), storage_class)
            for storage_class in storage_classes
        )
        if name and _is_default_storage_class(storage_class)
    )
    if default_names:
        return default_names[0]

    for preferred_name in PREFERRED_STORAGE_CLASS_NAMES:
        if preferred_name in names:
            return preferred_name

    return names[0]


def _storage_class_name(storage_class: object) -> str | None:
    metadata = getattr(storage_class, "metadata", None)
    name = getattr(metadata, "name", None)
    return name if isinstance(name, str) and name else None


def _is_default_storage_class(storage_class: object) -> bool:
    metadata = getattr(storage_class, "metadata", None)
    annotations = getattr(metadata, "annotations", None) or {}
    return (
        annotations.get("storageclass.kubernetes.io/is-default-class") == "true"
        or annotations.get("storageclass.beta.kubernetes.io/is-default-class")
        == "true"
    )
