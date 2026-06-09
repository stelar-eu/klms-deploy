"""Delete bootstrap Secrets created by `stelarctl lake bootstrap`."""

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
    target = resolve_environment_target(
        environment,
        spec_json,
        context=context,
        namespace=namespace,
    )
    context_name = target.context
    target_namespace = target.namespace
    bootstrap_state = target.bootstrap_state
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


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
