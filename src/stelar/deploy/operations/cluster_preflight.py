"""Read-only Kubernetes prerequisite checks for `init-lake cluster`."""

from __future__ import annotations

from typing import Any

from kubernetes import client as default_kube_client
from kubernetes.client.rest import ApiException

from .common import CommandError, JsonObject

INGRESS_CLASS_NAME = "nginx"
INGRESS_NGINX_CONTROLLER_SELECTORS = (
    "app.kubernetes.io/component=controller",
    "app.kubernetes.io/name=ingress-nginx",
    "app.kubernetes.io/name=rke2-ingress-nginx",
)
CERT_MANAGER_NAMESPACE = "cert-manager"
CERT_MANAGER_CRDS = [
    "certificates.cert-manager.io",
    "clusterissuers.cert-manager.io",
]
CERT_MANAGER_DEPLOYMENTS = [
    "cert-manager",
    "cert-manager-cainjector",
    "cert-manager-webhook",
]
PREFLIGHT_SKIP_HINT = (
    "Your current Kubernetes user does not have access to perform this "
    "read-only preflight check. Ask a cluster administrator for read access, "
    "or rerun with --skip-preflight to bypass prerequisite checks and let "
    "the deployment fail later if the cluster is not ready."
)


class PreflightAccessError(CommandError):
    """Raised when RBAC prevents a read-only preflight check."""


def run_preflight_checks(
    namespace: str,
    storage_class_names: list[str],
    cluster_issuer: str,
    *,
    kube_client_module: Any = default_kube_client,
    api_exception_type: type[Exception] = ApiException,
) -> None:
    """Validate cluster prerequisites with read-only Kubernetes API calls."""
    _validate_namespace(namespace, kube_client_module, api_exception_type)
    for storage_class_name in storage_class_names:
        _validate_storage_class(
            storage_class_name,
            kube_client_module,
            api_exception_type,
        )
    _validate_ingress_class(
        INGRESS_CLASS_NAME,
        kube_client_module,
        api_exception_type,
    )
    _validate_ingress_controller(
        INGRESS_CLASS_NAME,
        kube_client_module,
        api_exception_type,
    )
    if cluster_issuer:
        _validate_cert_manager(kube_client_module, api_exception_type)
        _validate_cluster_issuer(
            cluster_issuer,
            kube_client_module,
            api_exception_type,
        )


def _preflight_access_denied(check: str, exc: Exception) -> PreflightAccessError:
    status = getattr(exc, "status", "unknown")
    reason = getattr(exc, "reason", "Forbidden") or "Forbidden"
    return PreflightAccessError(
        f"Cannot perform {check} preflight check: Kubernetes API returned "
        f"{status} {reason}. {PREFLIGHT_SKIP_HINT}"
    )


def _is_forbidden(exc: Exception) -> bool:
    return getattr(exc, "status", None) == 403


def _validate_namespace(
    namespace: str,
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    core_api = kube_client_module.CoreV1Api()
    try:
        core_api.read_namespace(namespace)
    except api_exception_type as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(f"Namespace {namespace!r}", exc) from exc
        if getattr(exc, "status", None) == 404:
            raise CommandError(
                f"Namespace {namespace!r} does not exist in the selected cluster. "
                "Create the namespace or update product.json spec.namespace."
            ) from exc
        raise CommandError(
            f"Could not validate Namespace {namespace!r}: {exc}"
        ) from exc


def _validate_storage_class(
    storage_class_name: str,
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    storage_api = kube_client_module.StorageV1Api()
    try:
        storage_api.read_storage_class(storage_class_name)
    except api_exception_type as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"StorageClass {storage_class_name!r}",
                exc,
            ) from exc
        if getattr(exc, "status", None) == 404:
            raise CommandError(
                f"StorageClass {storage_class_name!r} does not exist in the "
                "selected cluster. Update product_fullspec.json storage class "
                "fields or install the StorageClass."
            ) from exc
        raise CommandError(
            f"Could not validate StorageClass {storage_class_name!r}: {exc}"
        ) from exc


def _validate_ingress_class(
    ingress_class_name: str,
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    networking_api = kube_client_module.NetworkingV1Api()
    try:
        networking_api.read_ingress_class(ingress_class_name)
    except api_exception_type as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"IngressClass {ingress_class_name!r}",
                exc,
            ) from exc
        if getattr(exc, "status", None) == 404:
            raise CommandError(
                f"IngressClass {ingress_class_name!r} does not exist in the "
                "selected cluster. Install/configure the ingress class expected "
                "by the product."
            ) from exc
        raise CommandError(
            f"Could not validate IngressClass {ingress_class_name!r}: {exc}"
        ) from exc


def _validate_ingress_controller(
    ingress_class_name: str,
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    core_api = kube_client_module.CoreV1Api()
    for selector in INGRESS_NGINX_CONTROLLER_SELECTORS:
        try:
            pods = core_api.list_pod_for_all_namespaces(label_selector=selector)
        except api_exception_type as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    "ingress-nginx controller pod discovery",
                    exc,
                ) from exc
            raise CommandError(
                f"Could not validate ingress-nginx controller for "
                f"IngressClass {ingress_class_name!r}: {exc}"
            ) from exc

        if any(
            _pod_matches_ingress_nginx_controller(pod) and _pod_is_ready(pod)
            for pod in pods.items or []
        ):
            return

    try:
        pods = core_api.list_pod_for_all_namespaces()
    except api_exception_type as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                "ingress-nginx controller pod discovery",
                exc,
            ) from exc
        raise CommandError(
            f"Could not validate ingress-nginx controller for "
            f"IngressClass {ingress_class_name!r}: {exc}"
        ) from exc

    if any(
        _pod_matches_ingress_nginx_controller(pod) and _pod_is_ready(pod)
        for pod in pods.items or []
    ):
        return

    raise CommandError(
        f"No Ready ingress-nginx controller pod found for "
        f"IngressClass {ingress_class_name!r}. Install/start ingress-nginx or "
        "update the product/cluster ingress setup."
    )


def _pod_matches_ingress_nginx_controller(pod: Any) -> bool:
    metadata = getattr(pod, "metadata", None)
    labels = getattr(metadata, "labels", None) or {}
    label_name = labels.get("app.kubernetes.io/name", "")
    pod_name = getattr(metadata, "name", "") or ""
    return "ingress-nginx" in label_name or "ingress-nginx" in pod_name


def _pod_is_ready(pod: Any) -> bool:
    status = getattr(pod, "status", None)
    if getattr(status, "phase", None) != "Running":
        return False

    return any(
        getattr(condition, "type", None) == "Ready"
        and getattr(condition, "status", None) == "True"
        for condition in getattr(status, "conditions", []) or []
    )


def _validate_cert_manager(
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    apiextensions_api = kube_client_module.ApiextensionsV1Api()
    for crd_name in CERT_MANAGER_CRDS:
        try:
            apiextensions_api.read_custom_resource_definition(crd_name)
        except api_exception_type as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    f"cert-manager CRD {crd_name!r}",
                    exc,
                ) from exc
            if getattr(exc, "status", None) == 404:
                raise CommandError(
                    f"cert-manager CRD {crd_name!r} does not exist. Install "
                    "cert-manager or generate a product that does not require "
                    "cert-manager-managed TLS."
                ) from exc
            raise CommandError(
                f"Could not validate cert-manager CRD {crd_name!r}: {exc}"
            ) from exc

    apps_api = kube_client_module.AppsV1Api()
    for deployment_name in CERT_MANAGER_DEPLOYMENTS:
        try:
            deployment = apps_api.read_namespaced_deployment_status(
                deployment_name,
                CERT_MANAGER_NAMESPACE,
            )
        except api_exception_type as exc:
            if _is_forbidden(exc):
                raise _preflight_access_denied(
                    f"cert-manager Deployment {deployment_name!r}",
                    exc,
                ) from exc
            if getattr(exc, "status", None) == 404:
                raise CommandError(
                    f"cert-manager Deployment {deployment_name!r} does not exist "
                    f"in namespace {CERT_MANAGER_NAMESPACE!r}. Install "
                    "cert-manager or generate a product that does not require "
                    "cert-manager-managed TLS."
                ) from exc
            raise CommandError(
                f"Could not validate cert-manager Deployment "
                f"{deployment_name!r}: {exc}"
            ) from exc

        desired_replicas = deployment.spec.replicas or 1
        available_replicas = deployment.status.available_replicas or 0
        if available_replicas < desired_replicas:
            raise CommandError(
                f"cert-manager Deployment {deployment_name!r} is not Ready. "
                "Wait for cert-manager to become Ready before deploying HTTPS."
            )


def _validate_cluster_issuer(
    cluster_issuer: str,
    kube_client_module: Any,
    api_exception_type: type[Exception],
) -> None:
    custom_objects_api = kube_client_module.CustomObjectsApi()
    try:
        issuer = custom_objects_api.get_cluster_custom_object(
            group="cert-manager.io",
            version="v1",
            plural="clusterissuers",
            name=cluster_issuer,
        )
    except api_exception_type as exc:
        if _is_forbidden(exc):
            raise _preflight_access_denied(
                f"ClusterIssuer {cluster_issuer!r}",
                exc,
            ) from exc
        if getattr(exc, "status", None) == 404:
            raise CommandError(
                f"ClusterIssuer {cluster_issuer!r} does not exist in the "
                "selected cluster. Create the issuer or update the product "
                "ingress.cert_manager.ClusterIssuer value."
            ) from exc
        raise CommandError(
            f"Could not validate ClusterIssuer {cluster_issuer!r}: {exc}"
        ) from exc

    if not _is_ready_condition_true(issuer):
        raise CommandError(
            f"ClusterIssuer {cluster_issuer!r} is not Ready. Fix the issuer "
            "before deploying HTTPS."
        )


def _is_ready_condition_true(resource: JsonObject) -> bool:
    status = resource.get("status", {})
    if not isinstance(status, dict):
        return False
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        return False
    return any(
        isinstance(condition, dict)
        and condition.get("type") == "Ready"
        and condition.get("status") == "True"
        for condition in conditions
    )
