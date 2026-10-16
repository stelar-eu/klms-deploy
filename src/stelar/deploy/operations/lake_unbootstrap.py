"""Undo lake bootstrap by deleting generated Secrets and ConfigMaps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from . import kube_context as kube_context_helpers
from .bootstrap_state import clear_bootstrapped_product
from .common import CommandError, JsonObject, read_environment_json, validate_workspace
from .deployment_config import deployment_config
from .environment_spec import environment_active_product
from .environment_target import resolve_environment_target
from .kube_context import load_kube_context
from .lake_environment import initialized_lake_environment_dir
from .lake_state_configmap import (
    LAKE_STATE_CONFIGMAP_NAME,
    read_lake_state_configmap,
)
from .secret_resources import expected_bootstrap_secret_names

# Expose kube_config for tests and integrations that monkeypatch this module.
kube_config = kube_context_helpers.kube_config


@dataclass(frozen=True)
class LakeUnbootstrapPlan:
    """Resolved target and resource names for lake unbootstrap."""

    environment: str
    context: str
    namespace: str
    secret_names: tuple[str, ...]
    spec_path: Path | None = None
    delete_state_configmap: bool = False
    configmap_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class LakeUnbootstrapResult:
    """Outcome of unbootstrapping one namespace."""

    plan: LakeUnbootstrapPlan
    deleted: tuple[str, ...]
    missing: tuple[str, ...]
    state_configmap_deleted: bool = False
    deleted_configmaps: tuple[str, ...] = ()
    missing_configmaps: tuple[str, ...] = ()


def plan_lake_unbootstrap(
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context: str | None = None,
    namespace: str | None = None,
) -> LakeUnbootstrapPlan:
    """Resolve the target namespace/context and generated resource names."""
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
                "active product to derive generated resource names from."
            ) from exc

    init_secret_names, init_configmap_names = _init_generated_resource_names(config)
    configmap_names = init_configmap_names
    if delete_state_configmap:
        # Remove the state marker last so a failed init-resource cleanup remains
        # discoverable as a bootstrapped/partial lake on the next inspection.
        configmap_names += (LAKE_STATE_CONFIGMAP_NAME,)

    return LakeUnbootstrapPlan(
        environment=environment,
        context=context_name,
        namespace=target_namespace,
        secret_names=tuple(
            dict.fromkeys(expected_bootstrap_secret_names(config) + init_secret_names)
        ),
        spec_path=spec_path,
        delete_state_configmap=delete_state_configmap,
        configmap_names=tuple(dict.fromkeys(configmap_names)),
    )


def unbootstrap_lake(plan: LakeUnbootstrapPlan) -> LakeUnbootstrapResult:
    """Delete planned generated resources regardless of ownership labels."""
    load_kube_context(plan.context)
    core_api = kube_client.CoreV1Api()
    deleted: list[str] = []
    deleted_configmaps: list[str] = []
    # Resolve every candidate before deleting anything. The fullspec selects exact
    # resource names; labels do not restrict deletion.
    secret_deletions, missing = _prepare_secret_deletions(core_api, plan)
    configmap_deletions, missing_configmaps = _prepare_configmap_deletions(
        core_api,
        plan,
    )

    for secret_name, delete_options in secret_deletions.items():
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
                    "changed after deletion preflight. Refusing to delete "
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

    for configmap_name, delete_options in configmap_deletions.items():
        try:
            core_api.delete_namespaced_config_map(
                configmap_name,
                plan.namespace,
                body=delete_options,
            )
        except ApiException as exc:
            if getattr(exc, "status", None) == 404:
                missing_configmaps.append(configmap_name)
                continue
            if getattr(exc, "status", None) == 409:
                raise CommandError(
                    f"ConfigMap {configmap_name!r} in namespace "
                    f"{plan.namespace!r} changed after deletion preflight. "
                    "Refusing to delete a changed or replaced ConfigMap; "
                    "inspect it before retrying."
                ) from exc
            if _is_forbidden(exc):
                raise CommandError(
                    "Kubernetes user is not authorized to delete ConfigMap "
                    f"{configmap_name!r} in namespace {plan.namespace!r}. Ask a "
                    "cluster administrator for permission to delete configmaps "
                    "or rerun with an authorized context."
                ) from exc
            raise CommandError(
                f"Could not delete ConfigMap {configmap_name!r} in namespace "
                f"{plan.namespace!r}: {exc}"
            ) from exc
        deleted_configmaps.append(configmap_name)

    if plan.spec_path is not None:
        spec_json = read_environment_json(plan.spec_path)
        clear_bootstrapped_product(plan.spec_path, spec_json)

    return LakeUnbootstrapResult(
        plan=plan,
        deleted=tuple(deleted),
        missing=tuple(missing),
        state_configmap_deleted=(
            LAKE_STATE_CONFIGMAP_NAME in deleted_configmaps
        ),
        deleted_configmaps=tuple(deleted_configmaps),
        missing_configmaps=tuple(missing_configmaps),
    )


def _init_generated_resource_names(
    config: JsonObject,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return exact resource names created imperatively by selected init jobs."""
    selected = set(_selected_components(config))
    secret_names: list[str] = []
    configmap_names: list[str] = []

    if "keycloak" in selected:
        keycloak = config.get("keycloak")
        if not isinstance(keycloak, dict):
            raise CommandError(
                "Fullspec config must define keycloak settings when the "
                "keycloak component is selected"
            )
        for field_name in (
            "KC_API_CLIENT_NAME",
            "KC_MINIO_CLIENT_NAME",
            "KC_CKAN_CLIENT_NAME",
        ):
            client_name = keycloak.get(field_name)
            if not isinstance(client_name, str) or not client_name:
                raise CommandError(
                    f"Fullspec config must define keycloak.{field_name} as a "
                    "non-empty string when the keycloak component is selected"
                )
            secret_names.append(f"{client_name}-client-secret")
        secret_names.append("stelar-admin-id")

    if "ckan" in selected:
        secret_names.append("ckan-admin-token-secret")

    if "quay" in selected:
        configmap_names.append("registry-config")

    return tuple(dict.fromkeys(secret_names)), tuple(dict.fromkeys(configmap_names))


def _selected_components(config: JsonObject) -> tuple[str, ...]:
    """Mirror the component selection performed by product_transformation."""
    components: list[str] = []
    if "support" in config:
        components.append("system")
    for field_name in ("core_components", "optional_components", "cluster"):
        value = config.get(field_name, [])
        if not isinstance(value, list) or not all(
            isinstance(component, str) for component in value
        ):
            raise CommandError(
                f"Fullspec config field {field_name} must be a list of strings"
            )
        components.extend(value)
    return tuple(dict.fromkeys(components))


def _prepare_secret_deletions(
    core_api: kube_client.CoreV1Api,
    plan: LakeUnbootstrapPlan,
) -> tuple[dict[str, kube_client.V1DeleteOptions], list[str]]:
    """Resolve existing Secrets and bind deletion to their current identity."""
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
                    "Unbootstrap requires permission to get secrets before "
                    "deletion. No resources have been deleted."
                ) from exc
            raise CommandError(
                f"Could not inspect Secret {secret_name!r} in "
                f"namespace {plan.namespace!r}: {exc}. No resources have been deleted."
            ) from exc

        metadata = getattr(secret, "metadata", None)
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


def _prepare_configmap_deletions(
    core_api: kube_client.CoreV1Api,
    plan: LakeUnbootstrapPlan,
) -> tuple[dict[str, kube_client.V1DeleteOptions], list[str]]:
    """Resolve existing ConfigMaps and bind deletion to their current identity."""
    deletions: dict[str, kube_client.V1DeleteOptions] = {}
    missing: list[str] = []
    for configmap_name in plan.configmap_names:
        try:
            configmap = core_api.read_namespaced_config_map(
                configmap_name,
                plan.namespace,
            )
        except ApiException as exc:
            if getattr(exc, "status", None) == 404:
                missing.append(configmap_name)
                continue
            if _is_forbidden(exc):
                raise CommandError(
                    "Kubernetes user is not authorized to read ConfigMap "
                    f"{configmap_name!r} in namespace {plan.namespace!r}. "
                    "Unbootstrap requires permission to get configmaps before "
                    "deletion. No resources have been deleted."
                ) from exc
            raise CommandError(
                f"Could not inspect ConfigMap {configmap_name!r} in namespace "
                f"{plan.namespace!r}: {exc}. No resources have been deleted."
            ) from exc

        metadata = getattr(configmap, "metadata", None)
        uid = getattr(metadata, "uid", None)
        resource_version = getattr(metadata, "resource_version", None)
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(resource_version, str)
            or not resource_version
        ):
            raise CommandError(
                f"Refusing to delete ConfigMap {configmap_name!r} in namespace "
                f"{plan.namespace!r}: its UID or resourceVersion is missing. "
                "No resources have been deleted."
            )
        deletions[configmap_name] = kube_client.V1DeleteOptions(
            preconditions=kube_client.V1Preconditions(
                uid=uid,
                resource_version=resource_version,
            ),
        )
    return deletions, missing


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403
