"""Model comparison helpers used by deployment planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .platform_model import PlatformModel
except ImportError:
    from platform_model import PlatformModel


@dataclass(frozen=True)
class ComparisonResult:
    """Flat difference list plus a convenience equality flag."""

    differences: list[str]
    equal: bool


def compare_models(
    left: PlatformModel,
    right: PlatformModel,
    *,
    include_secret_values: bool,
    ignore_fields: set[str] | None = None,
) -> ComparisonResult:
    """Compare two platform models with optional secret-value comparison."""
    left_flat = _flatten(_normalize_model(left, include_secret_values=include_secret_values))
    right_flat = _flatten(_normalize_model(right, include_secret_values=include_secret_values))

    differences: list[str] = []
    ignored = ignore_fields or set()
    for key in sorted(set(left_flat) | set(right_flat)):
        if key in ignored:
            continue
        left_value = left_flat.get(key, "<missing>")
        right_value = right_flat.get(key, "<missing>")
        if left_value != right_value:
            differences.append(f"{key}: {right_value} -> {left_value}")

    return ComparisonResult(differences=differences, equal=not differences)


def _normalize_model(model: PlatformModel, *, include_secret_values: bool) -> dict[str, Any]:
    """Normalize a model into comparable data, masking secret values when needed."""
    payload = model.model_dump(exclude_none=True)
    payload.pop("secrets", None)
    normalized_secrets: dict[str, Any] = {}
    for secret in sorted(model.secrets, key=lambda item: item.name):
        if include_secret_values:
            normalized_secrets[secret.name] = secret.data.model_dump(exclude_none=True)
        else:
            normalized_secrets[secret.name] = "__secret__"
    payload["secrets"] = normalized_secrets
    return payload


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dictionaries into dot-separated keys for readable diffs."""
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, nested_value in value.items():
            nested_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten(nested_value, nested_prefix))
        return flattened
    if isinstance(value, list):
        return {prefix: tuple(value)}
    return {prefix: value}
