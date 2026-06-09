"""Shared Kubernetes target resolution for lake environment commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .bootstrap_state import (
    BootstrappedProductState,
    bootstrapped_target_fields_or_none,
    reject_bootstrap_target_overrides,
    validate_bootstrap_target_matches,
)
from .common import CommandError, JsonObject
from .environment_spec import (
    environment_context_name_or_none,
    environment_namespace_or_none,
)
from .kube_context import resolve_kube_context, resolve_kube_namespace


@dataclass(frozen=True)
class EnvironmentTarget:
    """Resolved kubectl context/namespace plus optional bootstrap state."""

    context: str
    namespace: str
    bootstrap_state: BootstrappedProductState | None = None


def resolve_environment_target(
    environment: str,
    spec_json: JsonObject,
    *,
    context: str | None = None,
    namespace: str | None = None,
    infer_missing: bool = False,
    on_inferred_context: Callable[[str], None] | None = None,
    on_inferred_namespace: Callable[[str, str], None] | None = None,
) -> EnvironmentTarget:
    """Resolve a command target while enforcing recorded bootstrap locks."""
    bootstrapped_target = bootstrapped_target_fields_or_none(spec_json)
    if bootstrapped_target is not None:
        state = validate_bootstrap_target_matches(spec_json, *bootstrapped_target)
        reject_bootstrap_target_overrides(
            spec_json,
            context=context,
            namespace=namespace,
        )
        return EnvironmentTarget(
            resolve_kube_context(bootstrapped_target[0]),
            bootstrapped_target[1],
            state,
        )

    context_name = _target_context(
        environment,
        spec_json,
        context,
        infer_missing=infer_missing,
        on_inferred=on_inferred_context,
    )
    target_namespace = _target_namespace(
        environment,
        spec_json,
        namespace,
        context_name,
        infer_missing=infer_missing,
        on_inferred=on_inferred_namespace,
    )
    state = validate_bootstrap_target_matches(spec_json, context_name, target_namespace)
    return EnvironmentTarget(context_name, target_namespace, state)


def _target_context(
    environment: str,
    spec_json: JsonObject,
    context: str | None,
    *,
    infer_missing: bool,
    on_inferred: Callable[[str], None] | None,
) -> str:
    if context is not None:
        return resolve_kube_context(_required_flag_value(context, "context"))

    configured_context = environment_context_name_or_none(spec_json)
    if configured_context is not None:
        return resolve_kube_context(configured_context)
    if infer_missing:
        context_name = resolve_kube_context(None)
        if on_inferred is not None:
            on_inferred(context_name)
        return context_name

    raise CommandError(
        f"Lake environment {environment!r} has no context in spec.json. "
        "Rerun with --context CONTEXT or run lake bootstrap to infer and write it."
    )


def _target_namespace(
    environment: str,
    spec_json: JsonObject,
    namespace: str | None,
    context_name: str,
    *,
    infer_missing: bool,
    on_inferred: Callable[[str, str], None] | None,
) -> str:
    if namespace is not None:
        return _required_flag_value(namespace, "namespace")

    configured_namespace = environment_namespace_or_none(spec_json)
    if configured_namespace is not None:
        return configured_namespace
    if infer_missing:
        target_namespace = resolve_kube_namespace(context_name)
        if on_inferred is not None:
            on_inferred(target_namespace, context_name)
        return target_namespace

    raise CommandError(
        f"Lake environment {environment!r} has no namespace in spec.json. "
        "Rerun with --namespace NAMESPACE or run lake bootstrap to infer and write it."
    )


def _required_flag_value(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"--{name} must be a non-empty value")
    return value.strip()
