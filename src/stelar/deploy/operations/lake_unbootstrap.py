"""Undo lake bootstrap by deleting bootstrap Secrets and cluster state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from . import kube_context as kube_context_helpers
from .bootstrap_state import clear_bootstrapped_product
from .common import CommandError, read_environment_json, validate_workspace
from .deployment_config import deployment_config
from .environment_spec import environment_active_product
from .environment_target import resolve_environment_target
from .kube_context import load_kube_context
from .lake_environment import initialized_lake_environment_dir
from .lake_state_configmap import (
    LAKE_STATE_CONFIGMAP_NAME,
    delete_lake_state_configmap,
    read_lake_state_configmap,
)
from .secret_resources import expected_bootstrap_secret_names

# Expose kube_config for tests and integrations that monkeypatch this module.
kube_config = kube_context_helpers.kube_config


@dataclass(frozen=True)
class LakeUnbootstrapPlan:
    """Resolved target and Secret names for lake unbootstrap."""

    environment: str
    context: str
    namespace: str
    secret_names: tuple[str, ...]
    spec_path: Path | None = None
    delete_state_configmap: bool = False


@dataclass(frozen=True)
class LakeUnbootstrapResult:
    """Outcome of unbootstrapping one namespace."""

    plan: LakeUnbootstrapPlan
    deleted: tuple[str, ...]
    missing: tuple[str, ...]
    state_configmap_deleted: bool = False


def plan_lake_unbootstrap(
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context: str | None = None,
    namespace: str | None = None,
) -> LakeUnbootstrapPlan:
    """Resolve the target namespace/context and bootstrap Secret names."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    spec_path = environment_dir / "spec.json"
    spec_json = read_environment_json(spec_path)
    target = resolve_environment_target(
        environment,
        spec_json,
        context=context,
        namespace=namespace,
    )
    context_name = target.context
    target_namespace = target.namespace

    load_kube_context(context_name)
    lake_state = read_lake_state_configmap(target_namespace)
    delete_state_configmap = lake_state is not None
    if lake_state is not None:
        config = deployment_config(lake_state.fullspec)
    else:
        # Cleanup fallback for failed bootstraps that created Secrets before the
        # final state ConfigMap was written. This is not considered bootstrapped.
        try:
            config = deployment_config(environment_active_product(spec_json))
        except CommandError as exc:
            raise CommandError(
                f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} does not exist in "
                f"namespace {target_namespace!r}, and ENV/spec.json has no "
                "active product to derive bootstrap Secret names from."
            ) from exc

    return LakeUnbootstrapPlan(
        environment=environment,
        context=context_name,
        namespace=target_namespace,
        secret_names=expected_bootstrap_secret_names(config),
        spec_path=spec_path,
        delete_state_configmap=delete_state_configmap,
    )


def unbootstrap_lake(plan: LakeUnbootstrapPlan) -> LakeUnbootstrapResult:
    """Delete planned bootstrap Secrets and state, treating missing Secrets as absent."""
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

    state_deleted = False
    if plan.delete_state_configmap:
        state_deleted = delete_lake_state_configmap(plan.namespace)

    if plan.spec_path is not None:
        spec_json = read_environment_json(plan.spec_path)
        clear_bootstrapped_product(plan.spec_path, spec_json)

    return LakeUnbootstrapResult(
        plan,
        tuple(deleted),
        tuple(missing),
        state_deleted,
    )


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
