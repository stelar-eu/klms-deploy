"""Tanka environment spec.json update helpers."""

from __future__ import annotations

from pathlib import Path

from .common import (
    CommandError,
    JsonObject,
    ensure_object,
    existing_object,
    product_author,
    product_spec,
    read_environment_json,
    write_environment_json,
)


def environment_namespace(spec_json: JsonObject) -> str:
    """Return the Kubernetes namespace from a Tanka spec.json object."""
    spec = existing_object(spec_json, "spec")
    namespace = spec.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise CommandError("Environment spec.json must define a non-empty namespace")
    return namespace


def update_environment_spec_json(
    spec_path: Path,
    environment_name: Path,
    context_name: str,
    product_data: JsonObject,
) -> None:
    """Write context, namespace, labels, and author metadata into spec.json."""
    spec_json = read_environment_json(spec_path)
    spec = product_spec(product_data)
    namespace = spec.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        raise CommandError("Product spec must define a non-empty namespace")

    environment_name_text = environment_name.as_posix()
    metadata = ensure_object(spec_json, "metadata")
    metadata["name"] = environment_name_text
    metadata["namespace"] = f"{environment_name_text}/main.jsonnet"

    tk_spec = ensure_object(spec_json, "spec")
    tk_spec["contextNames"] = [context_name]
    tk_spec["namespace"] = namespace
    tk_spec.setdefault("expectVersions", {})
    tk_spec["injectLabels"] = True

    resource_defaults = ensure_object(tk_spec, "resourceDefaults")
    labels = ensure_object(resource_defaults, "labels")
    labels.setdefault("app.kubernetes.io/managed-by", "tanka")
    labels.setdefault("app.kubernetes.io/part-of", "stelar")
    labels.setdefault("stelar.deployment", "main")

    annotations = ensure_object(resource_defaults, "annotations")
    author = product_author(product_data)
    if author is not None:
        annotations["stelar.eu/author"] = author
    elif annotations.get("stelar.eu/author") == "<author>":
        del annotations["stelar.eu/author"]

    write_environment_json(spec_path, spec_json)
