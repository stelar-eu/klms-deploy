from collections.abc import Callable
from typing import Any

import typer
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


def purge_resources_in_target(context: str, namespace: str) -> None:
    """Delete namespaced resources from the target without deleting the namespace."""
    config.load_kube_config(context=context)

    errors: list[str] = []
    _purge_custom_resources(namespace, errors)

    for kind, delete_collection in _standard_resource_deletes(namespace):
        _delete_collection(kind, delete_collection, errors)

    if errors:
        raise typer.BadParameter(
            f"Could not purge all resources in {context}/{namespace}:\n- "
            + "\n- ".join(errors)
        )


def _standard_resource_deletes(namespace: str) -> list[tuple[str, Callable[[Any], Any]]]:
    batch = client.BatchV1Api()
    apps = client.AppsV1Api()
    core = client.CoreV1Api()
    networking = client.NetworkingV1Api()
    policy = client.PolicyV1Api()
    rbac = client.RbacAuthorizationV1Api()
    autoscaling = client.AutoscalingV2Api()
    coordination = client.CoordinationV1Api()
    discovery = client.DiscoveryV1Api()

    return [
        ("CronJobs", lambda body: batch.delete_collection_namespaced_cron_job(namespace, body=body)),
        ("Jobs", lambda body: batch.delete_collection_namespaced_job(namespace, body=body)),
        ("Deployments", lambda body: apps.delete_collection_namespaced_deployment(namespace, body=body)),
        ("StatefulSets", lambda body: apps.delete_collection_namespaced_stateful_set(namespace, body=body)),
        ("DaemonSets", lambda body: apps.delete_collection_namespaced_daemon_set(namespace, body=body)),
        ("ReplicaSets", lambda body: apps.delete_collection_namespaced_replica_set(namespace, body=body)),
        ("ReplicationControllers", lambda body: core.delete_collection_namespaced_replication_controller(namespace, body=body)),
        ("Pods", lambda body: core.delete_collection_namespaced_pod(namespace, body=body)),
        ("Services", lambda body: core.delete_collection_namespaced_service(namespace, body=body)),
        ("Ingresses", lambda body: networking.delete_collection_namespaced_ingress(namespace, body=body)),
        ("NetworkPolicies", lambda body: networking.delete_collection_namespaced_network_policy(namespace, body=body)),
        ("HorizontalPodAutoscalers", lambda body: autoscaling.delete_collection_namespaced_horizontal_pod_autoscaler(namespace, body=body)),
        ("PodDisruptionBudgets", lambda body: policy.delete_collection_namespaced_pod_disruption_budget(namespace, body=body)),
        ("EndpointSlices", lambda body: discovery.delete_collection_namespaced_endpoint_slice(namespace, body=body)),
        ("Endpoints", lambda body: core.delete_collection_namespaced_endpoints(namespace, body=body)),
        ("ConfigMaps", lambda body: core.delete_collection_namespaced_config_map(namespace, body=body)),
        ("Secrets", lambda body: core.delete_collection_namespaced_secret(namespace, body=body)),
        ("ServiceAccounts", lambda body: core.delete_collection_namespaced_service_account(namespace, body=body)),
        ("PersistentVolumeClaims", lambda body: core.delete_collection_namespaced_persistent_volume_claim(namespace, body=body)),
        ("ResourceQuotas", lambda body: core.delete_collection_namespaced_resource_quota(namespace, body=body)),
        ("LimitRanges", lambda body: core.delete_collection_namespaced_limit_range(namespace, body=body)),
        ("Roles", lambda body: rbac.delete_collection_namespaced_role(namespace, body=body)),
        ("RoleBindings", lambda body: rbac.delete_collection_namespaced_role_binding(namespace, body=body)),
        ("Leases", lambda body: coordination.delete_collection_namespaced_lease(namespace, body=body)),
    ]


def _purge_custom_resources(namespace: str, errors: list[str]) -> None:
    api_extensions = client.ApiextensionsV1Api()
    custom = client.CustomObjectsApi()

    try:
        crds = api_extensions.list_custom_resource_definition().items
    except ApiException as exc:
        if exc.status == 404:
            return
        errors.append(f"CustomResourceDefinitions: {_api_error_message(exc)}")
        return

    for crd in crds:
        if crd.spec.scope != "Namespaced":
            continue

        version = _served_crd_version(crd)
        if version is None:
            continue

        kind = f"{crd.spec.names.plural}.{crd.spec.group}/{version}"
        _delete_collection(
            kind,
            lambda body, crd=crd, version=version: custom.delete_collection_namespaced_custom_object(
                group=crd.spec.group,
                version=version,
                namespace=namespace,
                plural=crd.spec.names.plural,
                body=body,
            ),
            errors,
        )


def _served_crd_version(crd: Any) -> str | None:
    versions = getattr(crd.spec, "versions", None) or []
    for version in versions:
        if version.served:
            return version.name
    return getattr(crd.spec, "version", None)


def _delete_collection(kind: str, delete_collection: Callable[[Any], Any], errors: list[str]) -> None:
    try:
        delete_collection(_delete_options())
    except ApiException as exc:
        if exc.status == 404:
            return
        errors.append(f"{kind}: {_api_error_message(exc)}")


def _delete_options() -> client.V1DeleteOptions:
    return client.V1DeleteOptions(propagation_policy="Foreground")


def _api_error_message(exc: ApiException) -> str:
    if exc.status and exc.reason:
        return f"Kubernetes API error {exc.status}: {exc.reason}"
    return str(exc)
