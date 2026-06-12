"""Read-only cluster status inspection for `stelarctl lake status`."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kubernetes import client as kube_client
from kubernetes.client.rest import ApiException

from . import kube_context as kube_context_helpers
from .common import CommandError, JsonObject, read_environment_json, validate_workspace
from .deployment_config import deployment_config
from .environment_target import resolve_environment_target
from .fullspec_validation import validate_config_scheme_tls_consistency
from .kube_context import load_kube_context
from .lake_environment import initialized_lake_environment_dir
from .lake_state_configmap import (
    LAKE_STATE_CONFIGMAP_NAME,
    LakeState,
    read_lake_state_configmap,
)
from .secret_resources import expected_bootstrap_secret_names

# Expose kube_config for tests and integrations that monkeypatch this module.
kube_config = kube_context_helpers.kube_config

BootstrapState = Literal["bootstrapped", "not_bootstrapped", "partial", "unknown"]
DeploymentState = Literal["deployed", "not_deployed", "progressing", "degraded", "unknown", "unchecked"]
WorkloadState = Literal["ready", "complete", "progressing", "degraded", "missing", "unknown"]
WorkloadKind = Literal["Deployment", "StatefulSet", "Job"]


@dataclass(frozen=True)
class BootstrapStatus:
    """Bootstrap Secret state inferred from expected Kubernetes Secrets."""

    state: BootstrapState
    expected: tuple[str, ...]
    existing: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class WorkloadExpectation:
    """One Kubernetes workload expected for a selected fullspec component."""

    component: str
    kind: WorkloadKind
    name: str


@dataclass(frozen=True)
class WorkloadStatus:
    """Observed status for one expected workload."""

    component: str
    kind: WorkloadKind
    name: str
    state: WorkloadState
    detail: str


@dataclass(frozen=True)
class ComponentNote:
    """Selected component that cannot be inspected through native workload checks."""

    component: str
    detail: str


@dataclass(frozen=True)
class DeploymentStatus:
    """Deployment state inferred from selected component workloads."""

    state: DeploymentState
    workloads: tuple[WorkloadStatus, ...]
    unchecked_components: tuple[ComponentNote, ...] = ()


@dataclass(frozen=True)
class LakeStatus:
    """Complete read-only status report for one lake environment."""

    environment: str
    context: str
    namespace: str
    selected_components: tuple[str, ...]
    bootstrap: BootstrapStatus
    deployment: DeploymentStatus
    diagnostics: tuple[str, ...] = ()


STATIC_COMPONENT_WORKLOADS: dict[str, tuple[WorkloadExpectation, ...]] = {
    "postgres": (WorkloadExpectation("postgres", "StatefulSet", "db"),),
    "redis": (WorkloadExpectation("redis", "Deployment", "redis"),),
    "solr": (WorkloadExpectation("solr", "StatefulSet", "solr"),),
    "datapusher": (WorkloadExpectation("datapusher", "Deployment", "datapusher"),),
    "ontop": (
        WorkloadExpectation("ontop", "Deployment", "ontop"),
        WorkloadExpectation("ontop", "Job", "ontopinit"),
    ),
    "minio": (WorkloadExpectation("minio", "StatefulSet", "minio"),),
    "keycloak": (
        WorkloadExpectation("keycloak", "Deployment", "keycloak"),
        WorkloadExpectation("keycloak", "Job", "kcinit"),
    ),
    "api": (
        WorkloadExpectation("api", "Deployment", "stelarapi"),
        WorkloadExpectation("api", "Job", "apiinit"),
    ),
    "ckan": (
        WorkloadExpectation("ckan", "Deployment", "ckan"),
        WorkloadExpectation("ckan", "Job", "ckaninit"),
    ),
    "quay": (
        WorkloadExpectation("quay", "Deployment", "quay"),
        WorkloadExpectation("quay", "Job", "quayinit"),
    ),
    "llm_search": (WorkloadExpectation("llm_search", "Deployment", "llmsearch"),),
}

UNCHECKED_COMPONENTS = {
    "system": "deployment-wide resources; no application workload to inspect",
    "prometheus": "placeholder component; no native workload mapping exists yet",
    "grafana": "placeholder component; no native workload mapping exists yet",
    "airflow": "Helm-backed component; native workload status mapping is not implemented yet",
}

SDE_DEFAULT_COMPONENTS = ("kafka", "zookeeper", "flink", "kafbat", "sdemanager")


def inspect_lake_status(
    environment: str,
    workspace_path: Path = Path("."),
    *,
    context: str | None = None,
    namespace: str | None = None,
    job_timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 5.0,
) -> LakeStatus:
    """Inspect cluster-recorded bootstrap and deployment status."""
    _validate_polling(job_timeout_seconds, poll_interval_seconds)
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
    status_namespace = target.namespace

    load_kube_context(context_name)
    lake_state = read_lake_state_configmap(status_namespace)
    if lake_state is None:
        return _not_bootstrapped_status(environment, context_name, status_namespace)

    config = deployment_config(lake_state.fullspec)
    validate_config_scheme_tls_consistency(
        config,
        source=f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME} fullspec.json",
    )
    selected_components = extract_selected_components(config)
    expected_secrets = expected_bootstrap_secret_names(config)
    bootstrap = inspect_bootstrap_status(status_namespace, expected_secrets)
    expectations, unchecked = expected_workloads(config, selected_components)
    deployment = inspect_deployment_status(
        status_namespace,
        expectations,
        unchecked,
        job_timeout_seconds=job_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )

    return LakeStatus(
        environment=environment,
        context=context_name,
        namespace=status_namespace,
        selected_components=selected_components,
        bootstrap=bootstrap,
        deployment=deployment,
        diagnostics=_lake_state_diagnostics(lake_state),
    )


def _not_bootstrapped_status(
    environment: str,
    context_name: str,
    namespace: str,
) -> LakeStatus:
    return LakeStatus(
        environment=environment,
        context=context_name,
        namespace=namespace,
        selected_components=(),
        bootstrap=BootstrapStatus(
            "not_bootstrapped",
            (),
            detail=(
                f"ConfigMap {LAKE_STATE_CONFIGMAP_NAME!r} was not found in "
                f"namespace {namespace!r}."
            ),
        ),
        deployment=DeploymentStatus("not_deployed", ()),
    )


def _lake_state_diagnostics(lake_state: LakeState) -> tuple[str, ...]:
    if lake_state.product_name is None:
        return ()
    return (f"cluster product: {lake_state.product_name}",)

def extract_selected_components(config: JsonObject) -> tuple[str, ...]:
    """Mirror lib/util/product_transformation.extract_components in Python."""
    components: list[str] = []
    if "support" in config:
        components.append("system")
    for field_name in ("core_components", "optional_components", "cluster"):
        for component in _string_list(config.get(field_name), field_name):
            components.append(component)
    return tuple(dict.fromkeys(components))


def inspect_bootstrap_status(
    namespace: str,
    expected: tuple[str, ...],
) -> BootstrapStatus:
    """Infer bootstrap state by checking expected bootstrap Secret names."""
    core_api = kube_client.CoreV1Api()
    existing = []
    missing = []

    for secret_name in expected:
        try:
            core_api.read_namespaced_secret(secret_name, namespace)
        except ApiException as exc:
            if _is_forbidden(exc):
                return BootstrapStatus(
                    "unknown",
                    expected,
                    tuple(existing),
                    tuple(missing),
                    _forbidden_detail("Secret", secret_name, namespace, exc),
                )
            if getattr(exc, "status", None) == 404:
                missing.append(secret_name)
                continue
            return BootstrapStatus(
                "unknown",
                expected,
                tuple(existing),
                tuple(missing),
                f"Could not inspect Secret {secret_name!r}: {exc}",
            )
        existing.append(secret_name)

    if len(existing) == len(expected):
        state: BootstrapState = "bootstrapped"
    elif existing:
        state = "partial"
    else:
        state = "not_bootstrapped"
    return BootstrapStatus(state, expected, tuple(existing), tuple(missing))


def expected_workloads(
    config: JsonObject,
    selected_components: tuple[str, ...],
) -> tuple[tuple[WorkloadExpectation, ...], tuple[ComponentNote, ...]]:
    """Build expected workload checks from selected fullspec components."""
    workloads: list[WorkloadExpectation] = []
    unchecked: list[ComponentNote] = []

    for component in selected_components:
        if component == "sde":
            workloads.extend(_sde_workloads(config))
            continue
        if component == "visualizer":
            workloads.append(
                WorkloadExpectation(
                    "visualizer",
                    "Deployment",
                    _string_from_paths(
                        config,
                        (("visualizer", "deployment", "name"), ("deployment", "name")),
                        "visualizer",
                    ),
                )
            )
            continue
        if component == "previewer":
            workloads.append(
                WorkloadExpectation(
                    "previewer",
                    "Deployment",
                    _string_from_paths(
                        config,
                        (("previewer", "deployment", "name"), ("deployment", "name")),
                        "previewer",
                    ),
                )
            )
            continue
        if component in STATIC_COMPONENT_WORKLOADS:
            workloads.extend(STATIC_COMPONENT_WORKLOADS[component])
            continue
        reason = UNCHECKED_COMPONENTS.get(component)
        if reason is None:
            reason = "selected component has no known native workload mapping"
        unchecked.append(ComponentNote(component, reason))

    return tuple(workloads), tuple(unchecked)


def inspect_deployment_status(
    namespace: str,
    expectations: tuple[WorkloadExpectation, ...],
    unchecked_components: tuple[ComponentNote, ...],
    *,
    job_timeout_seconds: float,
    poll_interval_seconds: float,
) -> DeploymentStatus:
    apps_api = kube_client.AppsV1Api()
    batch_api = kube_client.BatchV1Api()
    statuses = []

    for expectation in expectations:
        if expectation.kind == "Deployment":
            statuses.append(_deployment_status(apps_api, namespace, expectation))
        elif expectation.kind == "StatefulSet":
            statuses.append(_statefulset_status(apps_api, namespace, expectation))
        else:
            statuses.append(
                _job_status(
                    batch_api,
                    namespace,
                    expectation,
                    timeout_seconds=job_timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                )
            )

    return DeploymentStatus(
        _deployment_state(tuple(statuses), unchecked_components),
        tuple(statuses),
        unchecked_components,
    )


def _deployment_status(
    apps_api: Any,
    namespace: str,
    expectation: WorkloadExpectation,
) -> WorkloadStatus:
    try:
        deployment = apps_api.read_namespaced_deployment_status(
            expectation.name,
            namespace,
        )
    except ApiException as exc:
        return _workload_api_error(expectation, namespace, exc)

    desired = _desired_replicas(deployment)
    ready = _int_or_zero(getattr(deployment.status, "ready_replicas", None))
    available = _int_or_zero(getattr(deployment.status, "available_replicas", None))
    effective_ready = max(ready, available)
    if effective_ready >= desired:
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "ready",
            f"{effective_ready}/{desired} replicas ready",
        )
    return WorkloadStatus(
        expectation.component,
        expectation.kind,
        expectation.name,
        "progressing",
        f"{effective_ready}/{desired} replicas ready",
    )


def _statefulset_status(
    apps_api: Any,
    namespace: str,
    expectation: WorkloadExpectation,
) -> WorkloadStatus:
    try:
        statefulset = apps_api.read_namespaced_stateful_set_status(
            expectation.name,
            namespace,
        )
    except ApiException as exc:
        return _workload_api_error(expectation, namespace, exc)

    desired = _desired_replicas(statefulset)
    ready = _int_or_zero(getattr(statefulset.status, "ready_replicas", None))
    if ready >= desired:
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "ready",
            f"{ready}/{desired} replicas ready",
        )
    return WorkloadStatus(
        expectation.component,
        expectation.kind,
        expectation.name,
        "progressing",
        f"{ready}/{desired} replicas ready",
    )


def _job_status(
    batch_api: Any,
    namespace: str,
    expectation: WorkloadExpectation,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> WorkloadStatus:
    deadline = time.monotonic() + timeout_seconds
    last_status: WorkloadStatus | None = None

    while True:
        current = _job_status_once(batch_api, namespace, expectation, timeout_seconds)
        if current.state in {"complete", "missing", "unknown"}:
            return current
        last_status = current
        if time.monotonic() >= deadline:
            return last_status
        sleep_for = min(poll_interval_seconds, max(0.0, deadline - time.monotonic()))
        if sleep_for > 0:
            time.sleep(sleep_for)


def _job_status_once(
    batch_api: Any,
    namespace: str,
    expectation: WorkloadExpectation,
    timeout_seconds: float,
) -> WorkloadStatus:
    try:
        job = batch_api.read_namespaced_job_status(expectation.name, namespace)
    except ApiException as exc:
        return _workload_api_error(expectation, namespace, exc)

    status = job.status
    succeeded = _int_or_zero(getattr(status, "succeeded", None))
    active = _int_or_zero(getattr(status, "active", None))
    failed = _int_or_zero(getattr(status, "failed", None))
    conditions = getattr(status, "conditions", None) or []

    if succeeded > 0 or _condition_true(conditions, "Complete"):
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "complete",
            f"succeeded={succeeded}",
        )
    if failed > 0 or _condition_true(conditions, "Failed"):
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "degraded",
            f"failed={failed}; no success after {timeout_seconds:g}s retry window",
        )
    return WorkloadStatus(
        expectation.component,
        expectation.kind,
        expectation.name,
        "progressing",
        f"active={active}, succeeded={succeeded}, failed={failed}",
    )


def _deployment_state(
    workloads: tuple[WorkloadStatus, ...],
    unchecked_components: tuple[ComponentNote, ...],
) -> DeploymentState:
    blocking_unchecked = any(
        note.component != "system" for note in unchecked_components
    )
    if not workloads:
        return "unchecked" if unchecked_components else "not_deployed"
    states = {workload.state for workload in workloads}
    if "unknown" in states:
        return "unknown"
    if states == {"missing"}:
        return "not_deployed"
    if "missing" in states or "degraded" in states:
        return "degraded"
    if "progressing" in states:
        return "progressing"
    if blocking_unchecked:
        return "unchecked"
    return "deployed"


def _workload_api_error(
    expectation: WorkloadExpectation,
    namespace: str,
    exc: ApiException,
) -> WorkloadStatus:
    if _is_forbidden(exc):
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "unknown",
            _forbidden_detail(expectation.kind, expectation.name, namespace, exc),
        )
    if getattr(exc, "status", None) == 404:
        return WorkloadStatus(
            expectation.component,
            expectation.kind,
            expectation.name,
            "missing",
            "not found",
        )
    return WorkloadStatus(
        expectation.component,
        expectation.kind,
        expectation.name,
        "unknown",
        f"Could not inspect {expectation.kind} {expectation.name!r}: {exc}",
    )


def _sde_workloads(config: JsonObject) -> list[WorkloadExpectation]:
    sde_components = _sde_components(config)
    workloads = []
    if "kafka" in sde_components or "zookeeper" in sde_components:
        workloads.append(
            WorkloadExpectation(
                "sde.kafka_zookeeper",
                "Deployment",
                _string_from_paths(
                    config,
                    (("kafka", "deployment_name"), ("sde", "kafka", "deployment_name")),
                    "kafka-cluster",
                ),
            )
        )
    if "flink" in sde_components:
        workloads.append(
            WorkloadExpectation(
                "sde.flink",
                "Deployment",
                _string_from_paths(
                    config,
                    (("flink", "deployment_name"), ("sde", "flink", "deployment_name")),
                    "flink-cluster",
                ),
            )
        )
    if "kafbat" in sde_components:
        workloads.append(
            WorkloadExpectation(
                "sde.kafbat",
                "Deployment",
                _string_from_paths(
                    config,
                    (("kafbat", "deployment_name"), ("sde", "kafbat", "deployment_name")),
                    "kafbat",
                ),
            )
        )
    if "sdemanager" in sde_components:
        workloads.append(
            WorkloadExpectation(
                "sde.sdemanager",
                "Deployment",
                _string_from_paths(
                    config,
                    (
                        ("sdemanager", "deployment_name"),
                        ("sde", "sdemanager", "deployment_name"),
                    ),
                    "sde-manager",
                ),
            )
        )
    return workloads


def _sde_components(config: JsonObject) -> tuple[str, ...]:
    sde_config = config.get("sde")
    if isinstance(sde_config, dict):
        components = sde_config.get("components")
        if isinstance(components, list) and all(isinstance(item, str) for item in components):
            return tuple(components)
    return SDE_DEFAULT_COMPONENTS


def _string_list(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CommandError(f"spec.stelar.active_product {field_name} must be a list of strings")
    return tuple(value)


def _string_from_paths(
    config: JsonObject,
    paths: tuple[tuple[str, ...], ...],
    default: str,
) -> str:
    for path in paths:
        current: object = config
        for part in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if isinstance(current, str) and current:
            return current
    return default


def _desired_replicas(workload: Any) -> int:
    replicas = getattr(workload.spec, "replicas", None)
    if isinstance(replicas, int) and replicas > 0:
        return replicas
    return 1


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def _condition_true(conditions: object, condition_type: str) -> bool:
    for condition in conditions:
        if getattr(condition, "type", None) == condition_type and getattr(condition, "status", None) == "True":
            return True
    return False


def _is_forbidden(exc: ApiException) -> bool:
    return getattr(exc, "status", None) == 403


def _forbidden_detail(kind: str, name: str, namespace: str, exc: ApiException) -> str:
    status = getattr(exc, "status", "unknown")
    reason = getattr(exc, "reason", "Forbidden") or "Forbidden"
    return (
        f"Kubernetes user is not authorized to inspect {kind} {name!r} "
        f"in namespace {namespace!r}: {status} {reason}"
    )


def _validate_polling(job_timeout_seconds: float, poll_interval_seconds: float) -> None:
    if job_timeout_seconds < 0:
        raise CommandError("--job-timeout must be greater than or equal to 0")
    if poll_interval_seconds < 0:
        raise CommandError("--poll-interval must be greater than or equal to 0")
