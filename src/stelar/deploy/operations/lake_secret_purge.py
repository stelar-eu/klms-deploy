"""Delete bootstrap Secrets created by `stelarctl lake bootstrap`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from . import kube_context as kube_context_helpers
from .bootstrap_state import (
    bootstrapped_target_fields_or_none,
    clear_bootstrapped_product,
    reject_bootstrap_target_overrides,
    validate_bootstrap_target_matches,
)
from .common import CommandError, JsonObject, read_environment_json, validate_workspace
from .deployment_config import deployment_config
from .environment_spec import (
    environment_active_product,
    environment_context_name_or_none,
    environment_namespace_or_none,
)
from .kube_context import load_kube_context, resolve_kube_context
from .lake_environment import initialized_lake_environment_dir
from .secret_resources import expected_bootstrap_secret_names

# Expose kube_config for tests and integrations that monkeypatch this module.
kube_config = kube_context_helpers.kube_config


@dataclass(frozen=True)
class LakeSecretPurgePlan:
    """Resolved target and Secret names for a lake bootstrap Secret purge."""

    environment: str
    context: str
    namespace: str
    secret_names: tuple[str, ...]
    spec_path: Path | None = None
    clear_bootstrap_state: bool = False


@dataclass(frozen=True)
class LakeSecretPurgeResult:
    """Outcome of deleting bootstrap Secrets from one namespace."""

    plan: LakeSecretPurgePlan
    deleted: tuple[str, ...]
    missing: tuple[str, ...]



def plan_lake_secret_purge(
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context: str | None = None,
    namespace: str | None = None,
) -> LakeSecretPurgePlan:
    """Resolve the target namespace/context and bootstrap Secret names."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    spec_json = read_environment_json(environment_dir / "spec.json")
    bootstrapped_target = bootstrapped_target_fields_or_none(spec_json)
    if bootstrapped_target is not None:
        bootstrap_state = validate_bootstrap_target_matches(
            spec_json,
            *bootstrapped_target,
        )
        reject_bootstrap_target_overrides(
            spec_json,
            context=context,
            namespace=namespace,
        )
        context_name = resolve_kube_context(bootstrapped_target[0])
        target_namespace = bootstrapped_target[1]
    else:
        context_name = _purge_context(environment, spec_json, context)
        target_namespace = _purge_namespace(environment, spec_json, namespace)
        bootstrap_state = validate_bootstrap_target_matches(
            spec_json,
            context_name,
            target_namespace,
        )
    if bootstrap_state is None:
        product_fullspec = environment_active_product(spec_json)
        config = deployment_config(product_fullspec)
        secret_names = expected_bootstrap_secret_names(config)
    else:
        secret_names = bootstrap_state.secret_names

    return LakeSecretPurgePlan(
        environment=environment,
        context=context_name,
        namespace=target_namespace,
        secret_names=secret_names,
        spec_path=environment_dir / "spec.json" if bootstrap_state is not None else None,
        clear_bootstrap_state=bootstrap_state is not None,
    )



def purge_lake_secrets(plan: LakeSecretPurgePlan) -> LakeSecretPurgeResult:
    """Delete all planned bootstrap Secrets, treating missing Secrets as purged."""
    load_kube_context(plan.context)
    core_api = kube_client.CoreV1Api()
    deleted: list[str] = []
    missing: list[str] = []

    for secret_name in plan.secret_names:
        try:
            core_api.delete_namespaced_secret(secret_name, plan.namespace)
        except ApiException as exc:
            if getattr(exc, "status", None) == 404:
                missing.append(secret_name)
                continue
            if _is_forbidden(exc):
                raise CommandError(
                    f"Kubernetes user is not authorized to delete Secret "
                    f"{secret_name!r} in namespace {plan.namespace!r}. Ask a "
                    "cluster administrator for permission to delete secrets or "
                    "rerun with an authorized context."
                ) from exc
            raise CommandError(
                f"Could not delete Secret {secret_name!r} in namespace "
                f"{plan.namespace!r}: {exc}"
            ) from exc
        deleted.append(secret_name)

    if plan.clear_bootstrap_state and plan.spec_path is not None:
        spec_json = read_environment_json(plan.spec_path)
        clear_bootstrapped_product(plan.spec_path, spec_json)

    return LakeSecretPurgeResult(plan, tuple(deleted), tuple(missing))



def _purge_context(
    environment: str,
    spec_json: JsonObject,
    context: str | None,
) -> str:
    if context is not None:
        return resolve_kube_context(_required_flag_value(context, "context"))
    configured_context = environment_context_name_or_none(spec_json)
    if configured_context is None:
        raise CommandError(
            f"Lake environment {environment!r} has no context in spec.json. "
            "Rerun with --context CONTEXT or run lake bootstrap to infer and write it."
        )
    return resolve_kube_context(configured_context)



def _purge_namespace(
    environment: str,
    spec_json: JsonObject,
    namespace: str | None,
) -> str:
    if namespace is not None:
        return _required_flag_value(namespace, "namespace")
    configured_namespace = environment_namespace_or_none(spec_json)
    if configured_namespace is None:
        raise CommandError(
            f"Lake environment {environment!r} has no namespace in spec.json. "
            "Rerun with --namespace NAMESPACE or run lake bootstrap to infer and write it."
        )
    return configured_namespace



def _required_flag_value(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"--{name} must be a non-empty value")
    return value.strip()



def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
