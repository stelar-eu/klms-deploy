"""Live readiness calculation and formatting for STELAR deployments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from .live import infer_live_deployment
    from .platform_model import PlatformModel
except ImportError:
    from live import infer_live_deployment
    from platform_model import PlatformModel


JOB_WEIGHT = 0.4
COMPONENT_WEIGHT = 0.6
# Initialization jobs usually finish before long-running services are fully
# rolled out, so they contribute less than component readiness to the final
# score while still making early progress visible.
FAILING_WAITING_REASONS = {
    "CrashLoopBackOff",
    "CreateContainerConfigError",
    "CreateContainerError",
    "ErrImagePull",
    "ImagePullBackOff",
    "RunContainerError",
}


@dataclass(frozen=True)
class ExpectedResource:
    """A Kubernetes resource expected for a STELAR tier."""

    kind: str
    name: str
    label: str


@dataclass(frozen=True)
class ResourceStatus:
    """Readiness summary for a long-running component."""

    kind: str
    name: str
    label: str
    ready: bool
    detail: str


@dataclass(frozen=True)
class JobStatus:
    """Completion summary for an initialization job."""

    name: str
    label: str
    completed: bool
    failed: bool
    detail: str


@dataclass(frozen=True)
class StatusSnapshot:
    """Point-in-time deployment readiness snapshot."""

    context: str
    namespace: str
    tier: str
    overall_percent: int
    jobs_completed: int
    jobs_total: int
    components_ready: int
    components_total: int
    phase: str
    blockers: list[str]
    job_statuses: list[JobStatus]
    component_statuses: list[ResourceStatus]


CORE_COMPONENTS = [
    ExpectedResource("statefulset", "db", "PostgreSQL"),
    ExpectedResource("deployment", "redis", "Redis"),
    ExpectedResource("statefulset", "minio", "MinIO"),
    ExpectedResource("deployment", "keycloak", "Keycloak"),
    ExpectedResource("deployment", "stelarapi", "STELAR API"),
    ExpectedResource("deployment", "ckan", "CKAN"),
    ExpectedResource("statefulset", "solr", "Solr"),
    ExpectedResource("deployment", "datapusher", "DataPusher"),
]

FULL_COMPONENTS = [
    ExpectedResource("deployment", "ontop", "Ontop"),
    ExpectedResource("deployment", "quay", "Quay Registry"),
    ExpectedResource("deployment", "visualizer", "Profile Visualizer"),
    ExpectedResource("deployment", "previewer", "Resource Previewer"),
]

CORE_JOBS = [
    ExpectedResource("job", "kcinit", "Keycloak Init"),
    ExpectedResource("job", "apiinit", "API Init"),
    ExpectedResource("job", "ckaninit", "CKAN Init"),
]

FULL_JOBS = [
    ExpectedResource("job", "ontopinit", "Ontop Init"),
    ExpectedResource("job", "quayinit", "Quay Init"),
]


def expected_components_for_model(model: PlatformModel) -> list[ExpectedResource]:
    """Return long-running components expected for a validated model."""
    components = list(CORE_COMPONENTS)
    if model.tier == "full":
        # The full tier extends the core system; it does not replace it.
        components.extend(FULL_COMPONENTS)
    if model.config.enable_llm_search:
        # LLM search is optional within a tier and is controlled by application
        # config instead of the tier library alone.
        components.append(ExpectedResource("deployment", "llmsearch", "LLM Search"))
    return components


def expected_jobs_for_model(model: PlatformModel) -> list[ExpectedResource]:
    """Return initialization jobs expected for a validated model."""
    jobs = list(CORE_JOBS)
    if model.tier == "full":
        jobs.extend(FULL_JOBS)
    return jobs


def calculate_progress(
    jobs_completed: int,
    jobs_total: int,
    components_ready: int,
    components_total: int,
) -> int:
    """Combine job and component readiness into a single percentage."""
    # Treat empty groups as complete. That keeps the formula valid if a future
    # tier has no init jobs or no long-running components in one category.
    jobs_ratio = 1.0 if jobs_total == 0 else jobs_completed / jobs_total
    components_ratio = 1.0 if components_total == 0 else components_ready / components_total
    overall = (jobs_ratio * JOB_WEIGHT) + (components_ratio * COMPONENT_WEIGHT)
    return round(overall * 100)


def render_bar(percent: int, width: int = 24) -> str:
    """Render a bounded ASCII progress bar."""
    bounded = max(0, min(100, percent))
    filled = round(width * bounded / 100)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {bounded}%"


def derive_phase(
    percent: int,
    job_statuses: list[JobStatus],
    component_statuses: list[ResourceStatus],
    pod_failures: list[str],
) -> str:
    """Convert readiness and failure signals into a user-facing phase."""
    # Hard failures outrank percentage progress. A deployment with a failed job
    # or an image-pull error should not be reported as "Nearly Ready".
    if any(job.failed for job in job_statuses) or pod_failures:
        return "Degraded"
    if percent == 100 and all(component.ready for component in component_statuses):
        return "Ready"
    if percent >= 71:
        return "Nearly Ready"
    return "Progressing"


def format_status(snapshot: StatusSnapshot) -> str:
    """Format a status snapshot for terminal output."""
    lines = [
        f"Context: {snapshot.context}",
        f"Namespace: {snapshot.namespace}",
        f"Tier: {snapshot.tier}",
        f"Status: {snapshot.phase} {snapshot.overall_percent}%",
        render_bar(snapshot.overall_percent),
        "",
        f"Jobs: {snapshot.jobs_completed}/{snapshot.jobs_total} completed",
        f"Components: {snapshot.components_ready}/{snapshot.components_total} ready",
    ]

    if snapshot.blockers:
        lines.append("")
        lines.append("Blocking:")
        lines.extend(f"- {blocker}" for blocker in snapshot.blockers)

    return "\n".join(lines)


def collect_status(model: PlatformModel) -> StatusSnapshot:
    """Collect status for the components expected by the supplied model."""
    from kubernetes import client, config

    config.load_kube_config(context=model.k8s_context)

    namespace = model.namespace
    apps_api = client.AppsV1Api()
    batch_api = client.BatchV1Api()
    core_api = client.CoreV1Api()

    # Convert Kubernetes lists to name-indexed maps once. The readiness helpers
    # then stay simple and do not repeatedly scan API result lists.
    deployments = {
        item.metadata.name: item
        for item in apps_api.list_namespaced_deployment(namespace=namespace).items
    }
    statefulsets = {
        item.metadata.name: item
        for item in apps_api.list_namespaced_stateful_set(namespace=namespace).items
    }
    jobs = {
        item.metadata.name: item
        for item in batch_api.list_namespaced_job(namespace=namespace).items
    }
    pods = core_api.list_namespaced_pod(namespace=namespace).items

    expected_components = expected_components_for_model(model)
    expected_jobs = expected_jobs_for_model(model)

    # Status is calculated against the resources the model says should exist.
    # Missing resources therefore become blockers instead of silently lowering
    # the denominator.
    component_statuses = [
        _component_status(resource, deployments, statefulsets)
        for resource in expected_components
    ]
    job_statuses = [_job_status(resource, jobs) for resource in expected_jobs]

    jobs_completed = sum(1 for job in job_statuses if job.completed)
    components_ready = sum(1 for component in component_statuses if component.ready)
    overall_percent = calculate_progress(
        jobs_completed,
        len(job_statuses),
        components_ready,
        len(component_statuses),
    )

    pod_failures = _pod_failures(pods)
    # Blockers are intentionally verbose and operator-facing. They explain why
    # the percentage has not reached 100%, not just which resource is missing.
    blockers = [
        f"{job.label}: {job.detail}"
        for job in job_statuses
        if not job.completed
    ] + [
        f"{component.label}: {component.detail}"
        for component in component_statuses
        if not component.ready
    ] + pod_failures

    return StatusSnapshot(
        context=model.k8s_context,
        namespace=namespace,
        tier=model.tier,
        overall_percent=overall_percent,
        jobs_completed=jobs_completed,
        jobs_total=len(job_statuses),
        components_ready=components_ready,
        components_total=len(component_statuses),
        phase=derive_phase(overall_percent, job_statuses, component_statuses, pod_failures),
        blockers=blockers,
        job_statuses=job_statuses,
        component_statuses=component_statuses,
    )


def collect_inferred_status(context_name: str, namespace: str) -> tuple[StatusSnapshot | None, list[str]]:
    """Infer a live model, then collect status for that inferred model."""
    live = infer_live_deployment(context_name, namespace)
    if not live.active or live.model is None:
        # Callers need warnings even when there is no snapshot, for example when
        # the namespace is missing or inference found partial evidence only.
        return None, live.warnings
    return collect_status(live.model), live.warnings


def _component_status(
    resource: ExpectedResource,
    deployments: dict[str, Any],
    statefulsets: dict[str, Any],
) -> ResourceStatus:
    """Dispatch component readiness calculation by Kubernetes resource kind."""
    # The expected resource list only uses Deployment and StatefulSet today.
    # Keeping dispatch explicit makes adding DaemonSet or CronJob checks later
    # a local change.
    if resource.kind == "deployment":
        deployment = deployments.get(resource.name)
        if deployment is None:
            return ResourceStatus(resource.kind, resource.name, resource.label, False, "missing deployment")
        return _deployment_status(resource, deployment)

    statefulset = statefulsets.get(resource.name)
    if statefulset is None:
        return ResourceStatus(resource.kind, resource.name, resource.label, False, "missing statefulset")
    return _statefulset_status(resource, statefulset)


def _deployment_status(resource: ExpectedResource, deployment: Any) -> ResourceStatus:
    """Evaluate whether a Deployment has observed and rolled out its spec."""
    spec = deployment.spec
    status = deployment.status
    replicas = spec.replicas or 0
    observed = status.observed_generation or 0
    generation = deployment.metadata.generation or 0
    ready = status.ready_replicas or 0
    updated = status.updated_replicas or 0
    available = status.available_replicas or 0

    # A controller can report old readiness while it has not observed the newest
    # generation yet. In that case, report the lag rather than stale success.
    if observed < generation:
        return ResourceStatus(
            resource.kind,
            resource.name,
            resource.label,
            False,
            "controller has not observed the latest deployment spec",
        )

    if ready >= replicas and updated >= replicas and available >= replicas:
        return ResourceStatus(resource.kind, resource.name, resource.label, True, "ready")

    # Keep the detail compact but complete enough to distinguish rollout, update,
    # and availability delays.
    return ResourceStatus(
        resource.kind,
        resource.name,
        resource.label,
        False,
        f"{ready}/{replicas} ready, {updated}/{replicas} updated, {available}/{replicas} available",
    )


def _statefulset_status(resource: ExpectedResource, statefulset: Any) -> ResourceStatus:
    """Evaluate whether a StatefulSet has observed and rolled out its spec."""
    spec = statefulset.spec
    status = statefulset.status
    replicas = spec.replicas or 0
    observed = status.observed_generation or 0
    generation = statefulset.metadata.generation or 0
    ready = status.ready_replicas or 0
    updated = status.updated_replicas or 0

    # StatefulSets do not expose availability in the same way Deployments do, so
    # readiness is based on observed generation plus ready/updated replicas.
    if observed < generation:
        return ResourceStatus(
            resource.kind,
            resource.name,
            resource.label,
            False,
            "controller has not observed the latest statefulset spec",
        )

    if ready >= replicas and updated >= replicas:
        return ResourceStatus(resource.kind, resource.name, resource.label, True, "ready")

    return ResourceStatus(
        resource.kind,
        resource.name,
        resource.label,
        False,
        f"{ready}/{replicas} ready, {updated}/{replicas} updated",
    )


def _job_status(resource: ExpectedResource, jobs: dict[str, Any]) -> JobStatus:
    """Evaluate completion or failure for an expected Kubernetes Job."""
    job = jobs.get(resource.name)
    if job is None:
        return JobStatus(resource.name, resource.label, False, False, "missing job")

    # A single failed pod for these init jobs is enough to mark the deployment
    # degraded because the jobs initialize cluster state that later services need.
    if _job_has_condition(job, "Failed", "True") or (job.status.failed or 0) > 0:
        return JobStatus(resource.name, resource.label, False, True, "job failed")

    completions = job.spec.completions or 1
    succeeded = job.status.succeeded or 0
    # Prefer Kubernetes conditions when present, but also handle test doubles and
    # older clients by comparing succeeded pods to requested completions.
    if _job_has_condition(job, "Complete", "True") or succeeded >= completions:
        return JobStatus(resource.name, resource.label, True, False, "completed")

    active = job.status.active or 0
    if active > 0:
        return JobStatus(resource.name, resource.label, False, False, "job still running")

    return JobStatus(resource.name, resource.label, False, False, "job pending")


def _job_has_condition(job: Any, kind: str, value: str) -> bool:
    """Return whether a Kubernetes Job has a condition with a given status."""
    for condition in job.status.conditions or []:
        if condition.type == kind and condition.status == value:
            return True
    return False


def _pod_failures(pods: list[Any]) -> list[str]:
    """Return pod waiting reasons that should mark deployment status degraded."""
    failures: list[str] = []
    for pod in pods:
        pod_name = pod.metadata.name
        for status in pod.status.container_statuses or []:
            waiting = getattr(status.state, "waiting", None)
            if waiting and waiting.reason in FAILING_WAITING_REASONS:
                # Only include high-signal waiting reasons. Generic Pending or
                # ContainerCreating states are normal during rollout and remain
                # represented by component readiness details.
                failures.append(f"Pod {pod_name}: {waiting.reason}")
    return failures
