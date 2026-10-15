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
from .secret_resources import BOOTSTRAP_SECRET_LABELS, expected_bootstrap_secret_names

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
    """Delete only verified, stelarctl-owned bootstrap Secrets and state."""
    load_kube_context(plan.context)
    core_api = kube_client.CoreV1Api()
    deleted: list[str] = []
    # Verify every candidate before deleting anything, including the state marker.
    # A fullspec records expected names, not proof that bootstrap created them.
    deletions, missing = _prepare_secret_deletions(core_api, plan)

    for secret_name, delete_options in deletions.items():
        try:
            core_api.delete_namespaced_secret(
                secret_name,
                plan.namespace,
                body=delete_options,
            )
        except ApiException as exc:
            if getattr(exc, "status", None) == 404:
                missing.append(secret_name)
                continue
            if getattr(exc, "status", None) == 409:
                raise CommandError(
                    f"Secret {secret_name!r} in namespace {plan.namespace!r} "
                    "changed after ownership verification. Refusing to delete "
                    "a changed or replaced Secret; inspect it before retrying."
                ) from exc
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


def _prepare_secret_deletions(
    core_api: kube_client.CoreV1Api,
    plan: LakeUnbootstrapPlan,
) -> tuple[dict[str, kube_client.V1DeleteOptions], list[str]]:
    """Fail closed on unowned/unreadable Secrets and bind deletion to their identity."""
    deletions: dict[str, kube_client.V1DeleteOptions] = {}
    missing: list[str] = []
    for secret_name in plan.secret_names:
        try:
            secret = core_api.read_namespaced_secret(secret_name, plan.namespace)
        except ApiException as exc:
            if getattr(exc, "status", None) == 404:
                missing.append(secret_name)
                continue
            if _is_forbidden(exc):
                raise CommandError(
                    f"Kubernetes user is not authorized to read Secret "
                    f"{secret_name!r} in namespace {plan.namespace!r}. "
                    "Unbootstrap requires permission to get secrets to verify "
                    "ownership before deletion. No resources have been deleted."
                ) from exc
            raise CommandError(
                f"Could not verify ownership of Secret {secret_name!r} in "
                f"namespace {plan.namespace!r}: {exc}. No resources have been deleted."
            ) from exc

        metadata = getattr(secret, "metadata", None)
        labels = getattr(metadata, "labels", None) or {}
        if any(labels.get(key) != value for key, value in BOOTSTRAP_SECRET_LABELS.items()):
            raise CommandError(
                f"Refusing to delete Secret {secret_name!r} in namespace "
                f"{plan.namespace!r}: it is not marked as a stelarctl-owned "
                "bootstrap Secret. No resources have been deleted. Inspect "
                "its ownership before manually removing it; Secrets from older "
                "stelarctl versions are not automatically adopted."
            )

        uid = getattr(metadata, "uid", None)
        resource_version = getattr(metadata, "resource_version", None)
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(resource_version, str)
            or not resource_version
        ):
            raise CommandError(
                f"Refusing to delete Secret {secret_name!r} in namespace "
                f"{plan.namespace!r}: its UID or resourceVersion is missing. "
                "No resources have been deleted."
            )
        deletions[secret_name] = kube_client.V1DeleteOptions(
            preconditions=kube_client.V1Preconditions(
                uid=uid,
                resource_version=resource_version,
            ),
        )
    return deletions, missing


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
