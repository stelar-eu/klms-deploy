"""Legacy local bootstrap-state cleanup helpers.

New bootstrap truth lives in the cluster-side ``stelar-lake-state`` ConfigMap.
This module only removes old ``spec.stelar.bootstrapped_product`` fields that may
exist in environments created by older stelarctl versions.
"""

from __future__ import annotations

from pathlib import Path

from .common import CommandError, JsonObject, existing_object, write_environment_json

BOOTSTRAPPED_PRODUCT_FIELD = "bootstrapped_product"


def clear_bootstrapped_product(spec_path: Path, spec_json: JsonObject) -> None:
    """Remove deprecated local bootstrap state when present."""
    stelar_spec = _optional_stelar_spec(spec_json)
    if BOOTSTRAPPED_PRODUCT_FIELD not in stelar_spec:
        return
    del stelar_spec[BOOTSTRAPPED_PRODUCT_FIELD]
    write_environment_json(spec_path, spec_json)


def _optional_stelar_spec(spec_json: JsonObject) -> JsonObject:
    spec = spec_json.get("spec")
    if spec is None:
        return {}
    if not isinstance(spec, dict):
        raise CommandError("Environment spec.json spec must be an object")
    if "stelar" not in spec:
        return {}
    return existing_object(spec, "stelar")
