"""Tanka environment spec.json update helpers."""

from __future__ import annotations

from pathlib import Path

from .common import (
    CommandError,
    JsonObject,
    ensure_object,
    existing_object,
    product_author,
    read_environment_json,
    write_environment_json,
)


def environment_context_name(spec_json: JsonObject) -> str:
    """Return the single Kubernetes context from a Tanka spec.json object."""
    context_name = environment_context_name_or_none(spec_json)
    if context_name is None:
        raise CommandError("Environment spec.json must define spec.contextNames")
    return context_name


def environment_context_name_or_none(spec_json: JsonObject) -> str | None:
    """Return the configured context, or None when spec.contextNames is absent."""
    spec = _optional_spec(spec_json)
    context_names = spec.get("contextNames")
    if context_names is None:
        return None
    if not isinstance(context_names, list) or len(context_names) != 1:
        raise CommandError(
            "Environment spec.json spec.contextNames must contain exactly one context"
        )
    context_name = context_names[0]
    if not isinstance(context_name, str) or not context_name.strip():
        raise CommandError(
            "Environment spec.json spec.contextNames must contain a non-empty context"
        )
    return context_name


def environment_namespace(spec_json: JsonObject) -> str:
    """Return the Kubernetes namespace from a Tanka spec.json object."""
    namespace = environment_namespace_or_none(spec_json)
    if namespace is None:
        raise CommandError("Environment spec.json must define a non-empty namespace")
    return namespace


def environment_namespace_or_none(spec_json: JsonObject) -> str | None:
    """Return the configured namespace, or None when spec.namespace is absent."""
    spec = _optional_spec(spec_json)
    namespace = spec.get("namespace")
    if namespace is None:
        return None
    if not isinstance(namespace, str) or not namespace.strip():
        raise CommandError(
            "Environment spec.json spec.namespace must contain a non-empty namespace"
        )
    return namespace


def update_environment_spec_json(
    spec_path: Path,
    environment_name: Path,
    product_data: JsonObject,
    *,
    context_name: str | None = None,
    namespace: str | None = None,
) -> None:
    """Write Tanka metadata and any provided context/namespace into spec.json."""
    spec_json = read_environment_json(spec_path)
    update_environment_spec(
        spec_json,
        environment_name,
        product_data,
        context_name=context_name,
        namespace=namespace,
    )
    write_environment_json(spec_path, spec_json)


def update_environment_spec(
    spec_json: JsonObject,
    environment_name: Path,
    product_data: JsonObject,
    *,
    context_name: str | None = None,
    namespace: str | None = None,
) -> None:
    """Mutate a spec.json object with Tanka metadata and optional cluster fields."""
    context_name = _validate_optional_string(context_name, "context")
    namespace = _validate_optional_string(namespace, "namespace")

    environment_entrypoint = environment_name.as_posix()
    metadata = ensure_object(spec_json, "metadata")
    metadata["name"] = environment_entrypoint
    metadata["namespace"] = f"{environment_entrypoint}/main.jsonnet"

    tk_spec = ensure_object(spec_json, "spec")
    if context_name is not None:
        tk_spec["contextNames"] = [context_name]
    if namespace is not None:
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


def _optional_spec(spec_json: JsonObject) -> JsonObject:
    if "spec" not in spec_json:
        return {}
    return existing_object(spec_json, "spec")


def _validate_optional_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"Environment {field_name} must be a non-empty string")
    return value.strip()
