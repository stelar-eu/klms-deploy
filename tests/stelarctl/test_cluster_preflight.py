from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from stelar.deploy.operations.cluster_preflight import (
    PreflightAccessError,
    run_preflight_checks,
)


def ready_ingress_pod():
    return SimpleNamespace(
        metadata=SimpleNamespace(
            labels={
                "app.kubernetes.io/name": "ingress-nginx",
                "app.kubernetes.io/component": "controller",
            },
            name="ingress-nginx-controller",
        ),
        status=SimpleNamespace(
            phase="Running",
            conditions=[SimpleNamespace(type="Ready", status="True")],
        ),
    )


def forbidden():
    raise ApiException(status=403, reason="Forbidden")


def test_run_preflight_checks_uses_injected_client_and_skips_cert_manager():
    calls = []

    class CoreV1Api:
        def read_namespace(self, name):
            calls.append(("namespace", name))

        def list_pod_for_all_namespaces(self, *, label_selector=None):
            calls.append(("pods", label_selector))
            return SimpleNamespace(items=[ready_ingress_pod()])

    class StorageV1Api:
        def read_storage_class(self, name):
            calls.append(("storage", name))

    class NetworkingV1Api:
        def read_ingress_class(self, name):
            calls.append(("ingress_class", name))

    kube_client = SimpleNamespace(
        CoreV1Api=CoreV1Api,
        StorageV1Api=StorageV1Api,
        NetworkingV1Api=NetworkingV1Api,
    )

    run_preflight_checks(
        "stelar",
        ["fast", "slow"],
        "",
        kube_client_module=kube_client,
        api_exception_type=ApiException,
    )

    assert calls == [
        ("namespace", "stelar"),
        ("storage", "fast"),
        ("storage", "slow"),
        ("ingress_class", "nginx"),
        ("pods", "app.kubernetes.io/component=controller"),
    ]


def test_run_preflight_checks_validates_cert_manager_when_issuer_is_configured():
    calls = []

    class CoreV1Api:
        def read_namespace(self, name):
            calls.append(("namespace", name))

        def list_pod_for_all_namespaces(self, *, label_selector=None):
            calls.append(("pods", label_selector))
            return SimpleNamespace(items=[ready_ingress_pod()])

    class StorageV1Api:
        def read_storage_class(self, name):
            calls.append(("storage", name))

    class NetworkingV1Api:
        def read_ingress_class(self, name):
            calls.append(("ingress_class", name))

    class ApiextensionsV1Api:
        def read_custom_resource_definition(self, name):
            calls.append(("crd", name))

    class AppsV1Api:
        def read_namespaced_deployment_status(self, name, namespace):
            calls.append(("deployment", namespace, name))
            return SimpleNamespace(
                spec=SimpleNamespace(replicas=1),
                status=SimpleNamespace(available_replicas=1),
            )

    class CustomObjectsApi:
        def get_cluster_custom_object(self, *, group, version, plural, name):
            calls.append(("issuer", group, version, plural, name))
            return {"status": {"conditions": [{"type": "Ready", "status": "True"}]}}

    kube_client = SimpleNamespace(
        CoreV1Api=CoreV1Api,
        StorageV1Api=StorageV1Api,
        NetworkingV1Api=NetworkingV1Api,
        ApiextensionsV1Api=ApiextensionsV1Api,
        AppsV1Api=AppsV1Api,
        CustomObjectsApi=CustomObjectsApi,
    )

    run_preflight_checks(
        "stelar",
        ["fast"],
        "letsencrypt-prod",
        kube_client_module=kube_client,
        api_exception_type=ApiException,
    )

    assert ("crd", "certificates.cert-manager.io") in calls
    assert ("deployment", "cert-manager", "cert-manager") in calls
    assert (
        "issuer",
        "cert-manager.io",
        "v1",
        "clusterissuers",
        "letsencrypt-prod",
    ) in calls


def test_run_preflight_checks_reports_rbac_denial_with_skip_hint():
    class CoreV1Api:
        def read_namespace(self, name):
            return None

    class StorageV1Api:
        def read_storage_class(self, name):
            forbidden()

    kube_client = SimpleNamespace(
        CoreV1Api=CoreV1Api,
        StorageV1Api=StorageV1Api,
    )

    with pytest.raises(PreflightAccessError, match="--skip-preflight"):
        run_preflight_checks(
            "stelar",
            ["fast"],
            "",
            kube_client_module=kube_client,
            api_exception_type=ApiException,
        )
