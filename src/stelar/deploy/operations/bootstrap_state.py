"""Persist and validate bootstrap target state for lake environments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .common import (
    CommandError,
    JsonObject,
    ensure_object,
    existing_object,
    write_environment_json,
)

BOOTSTRAPPED_PRODUCT_FIELD = "bootstrapped_product"


@dataclass(frozen=True)
class BootstrappedProductState:
    """Bootstrap state stored under spec.stelar.bootstrapped_product."""

    target_sha256: str
    secret_names: tuple[str, ...]
    bootstrapped_at: str
    product_name: str | None = None
    product_sha256: str | None = None


def target_sha256(context_name: str, namespace: str) -> str:
    """Hash the target that identifies one bootstrapped lake environment."""
    target = {
        "context": _required_string(context_name, "context"),
        "namespace": _required_string(namespace, "namespace"),
    }
    return _object_sha256(target)


def product_sha256(product_fullspec: JsonObject) -> str:
    """Hash the active product fullspec that bootstrap prepared."""
    return _object_sha256(product_fullspec)


def bootstrapped_product_or_none(
    spec_json: JsonObject,
) -> BootstrappedProductState | None:
    """Return stored bootstrap state, or None when the environment is untracked."""
    stelar_spec = _optional_stelar_spec(spec_json)
    value = stelar_spec.get(BOOTSTRAPPED_PRODUCT_FIELD)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product must be an object"
        )

    state_hash = value.get("target_sha256")
    if not isinstance(state_hash, str) or not state_hash.strip():
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product.target_sha256 "
            "must be a non-empty string"
        )

    secret_names = value.get("secret_names")
    if not isinstance(secret_names, list) or not all(
        isinstance(secret_name, str) and secret_name.strip()
        for secret_name in secret_names
    ):
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product.secret_names "
            "must be a list of non-empty strings"
        )

    bootstrapped_at = value.get("bootstrapped_at")
    if not isinstance(bootstrapped_at, str) or not bootstrapped_at.strip():
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product.bootstrapped_at "
            "must be a non-empty string"
        )

    product_name = value.get("product_name")
    if product_name is not None and (
        not isinstance(product_name, str) or not product_name.strip()
    ):
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product.product_name "
            "must be a non-empty string when present"
        )

    product_hash = value.get("product_sha256")
    if product_hash is not None and (
        not isinstance(product_hash, str) or not product_hash.strip()
    ):
        raise CommandError(
            "Environment spec.json spec.stelar.bootstrapped_product.product_sha256 "
            "must be a non-empty string when present"
        )

    return BootstrappedProductState(
        target_sha256=state_hash.strip(),
        secret_names=tuple(dict.fromkeys(secret_names)),
        bootstrapped_at=bootstrapped_at.strip(),
        product_name=product_name.strip() if isinstance(product_name, str) else None,
        product_sha256=product_hash.strip() if isinstance(product_hash, str) else None,
    )


def validate_bootstrap_product_matches(
    spec_json: JsonObject,
    product_fullspec: JsonObject,
) -> BootstrappedProductState | None:
    """Fail when stored bootstrap state belongs to another active product."""
    state = bootstrapped_product_or_none(spec_json)
    if state is None:
        return None
    if state.product_sha256 is None:
        raise CommandError(_product_mismatch_message(state, missing_hash=True))
    if state.product_sha256 != product_sha256(product_fullspec):
        raise CommandError(_product_mismatch_message(state, missing_hash=False))
    return state


def validate_bootstrap_target_matches(
    spec_json: JsonObject,
    context_name: str,
    namespace: str,
) -> BootstrappedProductState | None:
    """Fail when stored bootstrap state belongs to another target."""
    state = bootstrapped_product_or_none(spec_json)
    if state is None:
        return None

    current_hash = target_sha256(context_name, namespace)
    if state.target_sha256 != current_hash:
        raise CommandError(
            "Hash mismatch detected. Refusing to act because this spec no "
            "longer points to the bootstrapped lake. Restore the original "
            "spec.contextNames and spec.namespace before running this command."
        )
    return state


def require_bootstrap_target_fields(
    spec_json: JsonObject,
) -> BootstrappedProductState | None:
    """Require local target fields when bootstrap state has been recorded."""
    state = bootstrapped_product_or_none(spec_json)
    if state is None:
        return None

    spec = spec_json.get("spec")
    context_names = spec.get("contextNames") if isinstance(spec, dict) else None
    namespace = spec.get("namespace") if isinstance(spec, dict) else None
    has_context = (
        isinstance(context_names, list)
        and len(context_names) == 1
        and isinstance(context_names[0], str)
        and bool(context_names[0].strip())
    )
    has_namespace = isinstance(namespace, str) and bool(namespace.strip())
    if not has_context or not has_namespace:
        raise CommandError(
            "Environment has recorded bootstrap state, but spec.contextNames "
            "or spec.namespace is missing. Restore the original spec.contextNames "
            "and spec.namespace before running this command."
        )
    return state


def bootstrapped_target_fields_or_none(
    spec_json: JsonObject,
) -> tuple[str, str] | None:
    """Return stored target fields when bootstrap state exists."""
    if require_bootstrap_target_fields(spec_json) is None:
        return None

    spec = spec_json.get("spec")
    if not isinstance(spec, dict):
        raise CommandError("Environment spec.json spec must be an object")
    context_names = spec.get("contextNames")
    namespace = spec.get("namespace")
    # require_bootstrap_target_fields validates this shape first.
    return context_names[0].strip(), namespace.strip()  # type: ignore[index,union-attr]


def reject_bootstrap_target_overrides(
    spec_json: JsonObject,
    *,
    context: str | None,
    namespace: str | None,
) -> None:
    """Forbid CLI target overrides once bootstrap has locked the environment."""
    if bootstrapped_product_or_none(spec_json) is None:
        return
    if context is None and namespace is None:
        return
    raise CommandError(
        "Environment has recorded bootstrap state; --context and --namespace "
        "overrides are not allowed. Restore the original spec.contextNames and "
        "spec.namespace manually before running this command."
    )


def bootstrap_secret_names(
    spec_json: JsonObject,
    context_name: str,
    namespace: str,
    fallback_secret_names: tuple[str, ...],
) -> tuple[str, ...]:
    """Use stored bootstrap Secret names when target state is available."""
    state = validate_bootstrap_target_matches(spec_json, context_name, namespace)
    if state is not None:
        return state.secret_names
    return tuple(dict.fromkeys(fallback_secret_names))


def record_bootstrapped_product(
    spec_path: Path,
    spec_json: JsonObject,
    context_name: str,
    namespace: str,
    secret_names: tuple[str, ...],
    *,
    product_name: str | None = None,
    product_fullspec: JsonObject,
) -> None:
    """Write bootstrap state after all bootstrap Secrets have been created."""
    set_bootstrapped_product(
        spec_json,
        context_name,
        namespace,
        secret_names,
        product_name=product_name,
        product_fullspec=product_fullspec,
    )
    write_environment_json(spec_path, spec_json)


def set_bootstrapped_product(
    spec_json: JsonObject,
    context_name: str,
    namespace: str,
    secret_names: tuple[str, ...],
    *,
    product_name: str | None = None,
    product_fullspec: JsonObject,
) -> None:
    """Mutate spec.json with target/product state and expected Secret names."""
    if not secret_names:
        raise CommandError("Bootstrapped product must define at least one Secret name")

    stelar_spec = ensure_object(ensure_object(spec_json, "spec"), "stelar")
    state = {
        "target_sha256": target_sha256(context_name, namespace),
        "product_sha256": product_sha256(product_fullspec),
        "secret_names": list(dict.fromkeys(secret_names)),
        "bootstrapped_at": _utc_timestamp(),
    }
    if product_name is not None:
        state["product_name"] = _required_string(product_name, "product name")
    stelar_spec[BOOTSTRAPPED_PRODUCT_FIELD] = state


def clear_bootstrapped_product(spec_path: Path, spec_json: JsonObject) -> None:
    """Remove recorded bootstrap state after its tracked Secrets are purged."""
    stelar_spec = _optional_stelar_spec(spec_json)
    if BOOTSTRAPPED_PRODUCT_FIELD not in stelar_spec:
        return
    del stelar_spec[BOOTSTRAPPED_PRODUCT_FIELD]
    write_environment_json(spec_path, spec_json)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _optional_stelar_spec(spec_json: JsonObject) -> JsonObject:
    spec = spec_json.get("spec")
    if spec is None:
        return {}
    if not isinstance(spec, dict):
        raise CommandError("Environment spec.json spec must be an object")
    if "stelar" not in spec:
        return {}
    return existing_object(spec, "stelar")


def _product_mismatch_message(
    state: BootstrappedProductState,
    *,
    missing_hash: bool,
) -> str:
    if missing_hash:
        reason = "Recorded bootstrap state does not contain a product hash."
    elif state.product_name:
        reason = (
            "Active product does not match the recorded bootstrap state for "
            f"product {state.product_name!r}."
        )
    else:
        reason = "Active product does not match the recorded bootstrap state."
    return (
        reason
        + " Purge old bootstrap Secrets with `stelarctl lake purge-secrets ENV`, "
        "then run `stelarctl lake bootstrap ENV` for the active product."
    )


def _object_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"Bootstrap target {field_name} must be a non-empty string")
    return value.strip()
