from collections.abc import Callable
from typing import Any, Optional

import typer
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


STELAR_LABEL_SELECTOR = "app.kubernetes.io/part-of=stelar,stelar.deployment=main"


def active_kube_target(namespace: Optional[str] = None) -> tuple[str, str]:
    contexts, active = config.list_kube_config_contexts()
    if not active:
        raise typer.BadParameter("No active Kubernetes context found.")

    active_namespace = active.get("context", {}).get("namespace") or "default"
    return active["name"], namespace or active_namespace


def resources_exist_in_target(context: str, namespace: str) -> bool:
    """Return True when the target contains labeled STELAR resources."""
    config.load_kube_config(context=context)
    batch = client.BatchV1Api()
    apps = client.AppsV1Api()
    core = client.CoreV1Api()
    networking = client.NetworkingV1Api()
    rbac = client.RbacAuthorizationV1Api()

    resource_lists: list[Callable[[], Any]] = [
        lambda: batch.list_namespaced_job(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: apps.list_namespaced_deployment(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: apps.list_namespaced_stateful_set(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: apps.list_namespaced_daemon_set(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: apps.list_namespaced_replica_set(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: core.list_namespaced_pod(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: core.list_namespaced_service(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: core.list_namespaced_persistent_volume_claim(
            namespace,
            label_selector=STELAR_LABEL_SELECTOR,
        ),
        lambda: core.list_namespaced_config_map(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: core.list_namespaced_secret(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: core.list_namespaced_service_account(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: networking.list_namespaced_ingress(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: rbac.list_namespaced_role(namespace, label_selector=STELAR_LABEL_SELECTOR),
        lambda: rbac.list_namespaced_role_binding(namespace, label_selector=STELAR_LABEL_SELECTOR),
    ]

    for list_resources in resource_lists:
        try:
            if list_resources().items:
                return True
        except ApiException as exc:
            if exc.status == 404:
                continue
            raise typer.BadParameter(
                f"Could not check STELAR resources in {context}/{namespace}: "
                f"Kubernetes API error {exc.status}: {exc.reason}"
            ) from exc

    return False


def deployment_progress(context: str, namespace: str) -> tuple[bool, int, str]:
    config.load_kube_config(context=context)
    batch = client.BatchV1Api()
    apps = client.AppsV1Api()
    core = client.CoreV1Api()

    jobs = batch.list_namespaced_job(namespace, label_selector=STELAR_LABEL_SELECTOR).items
    deployments = apps.list_namespaced_deployment(namespace, label_selector=STELAR_LABEL_SELECTOR).items
    statefulsets = apps.list_namespaced_stateful_set(namespace, label_selector=STELAR_LABEL_SELECTOR).items
    pods = core.list_namespaced_pod(namespace, label_selector=STELAR_LABEL_SELECTOR).items

    completed_jobs = sum(1 for job in jobs if (job.status.succeeded or 0) > 0)

    components = [*deployments, *statefulsets]
    ready_components = 0
    for component in components:
        desired = component.spec.replicas or 1
        ready = component.status.ready_replicas or 0
        if ready >= desired:
            ready_components += 1

    total = len(jobs) + len(components)
    completed = completed_jobs + ready_components
    active = bool(total or pods)
    progress = int((completed / total) * 100) if total else 0
    detail = (
        f"jobs {completed_jobs}/{len(jobs)}, "
        f"components {ready_components}/{len(components)}"
    )
    return active, progress, detail


def progress_bar(progress: int, width: int = 24) -> str:
    filled = max(0, min(width, round((progress / 100) * width)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"
