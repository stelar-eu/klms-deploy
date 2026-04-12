from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from stelarctl.deploy import clear_namespace_annotations, preflight_check, purge_namespace
from stelarctl.live import (
    _infer_network,
    _infer_secret_names,
    _infer_storage,
    _infer_tier_from_workloads,
    _secret_name_from_env,
    infer_live_deployment,
)
from stelarctl.platform_model import PlatformModel


def _obj(**kwargs):
    return SimpleNamespace(**kwargs)


def make_model(
    *,
    tls_mode: str = "none",
    issuer: str | None = None,
    dynamic_class: str = "standard",
    provisioning_class: str = "csi-hostpath-sc",
    ingress_class: str = "nginx",
) -> PlatformModel:
    return PlatformModel(
        platform="minikube",
        k8s_context="minikube",
        namespace="stelar-dev",
        author="dev@example.com",
        tier="core",
        infrastructure={
            "storage": {"dynamic_class": dynamic_class, "provisioning_class": provisioning_class},
            "ingress_class": ingress_class,
            "tls": {"mode": tls_mode, **({"issuer": issuer} if issuer is not None else {})},
        },
        dns={"root": "minikube.test", "scheme": "https" if tls_mode != "none" else "http"},
        config={
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "apikey",
            "s3_console_url": "http://klms.minikube.test/s3/login",
            "enable_llm_search": False,
        },
        secrets=[
            {"name": "postgresdb-secret", "data": {"password": "postgres"}},
            {"name": "ckandb-secret", "data": {"password": "ckan"}},
            {"name": "keycloakdb-secret", "data": {"password": "keycloak"}},
            {"name": "datastoredb-secret", "data": {"password": "datastore"}},
            {"name": "keycloakroot-secret", "data": {"password": "root"}},
            {"name": "smtpapi-secret", "data": {"password": "smtp"}},
            {"name": "ckanadmin-secret", "data": {"password": "admin"}},
            {"name": "minioroot-secret", "data": {"password": "minio"}},
            {"name": "session-secret-key", "data": {"key": "session"}},
            {"name": "quaydb-secret", "data": {"password": "quay"}},
        ],
    )


def test_preflight_check_raises_for_missing_storage_class(monkeypatch):
    model = make_model(dynamic_class="missing-storage")

    monkeypatch.setattr(
        "stelarctl.deploy.config.list_kube_config_contexts",
        lambda: ([{"name": "minikube"}], {"name": "minikube"}),
    )
    monkeypatch.setattr("stelarctl.deploy.config.load_kube_config", lambda context=None: None)
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: None)
    monkeypatch.setattr(
        "stelarctl.deploy.client.CoreV1Api",
        lambda: _obj(read_namespace=lambda namespace: _obj()),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.StorageV1Api",
        lambda: _obj(list_storage_class=lambda: _obj(items=[_obj(metadata=_obj(name="standard"))])),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.NetworkingV1Api",
        lambda: _obj(list_ingress_class=lambda: _obj(items=[_obj(metadata=_obj(name="nginx"))])),
    )
    monkeypatch.setattr("stelarctl.deploy.client.CustomObjectsApi", lambda: _obj())

    with pytest.raises(typer.BadParameter) as exc:
        preflight_check(model, auto_approve=True)

    assert "infrastructure.storage.dynamic_class" in str(exc.value)


def test_preflight_check_raises_for_missing_ingress_class(monkeypatch):
    model = make_model(ingress_class="missing-ingress")

    monkeypatch.setattr(
        "stelarctl.deploy.config.list_kube_config_contexts",
        lambda: ([{"name": "minikube"}], {"name": "minikube"}),
    )
    monkeypatch.setattr("stelarctl.deploy.config.load_kube_config", lambda context=None: None)
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: None)
    monkeypatch.setattr(
        "stelarctl.deploy.client.CoreV1Api",
        lambda: _obj(read_namespace=lambda namespace: _obj()),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.StorageV1Api",
        lambda: _obj(
            list_storage_class=lambda: _obj(
                items=[
                    _obj(metadata=_obj(name="standard")),
                    _obj(metadata=_obj(name="csi-hostpath-sc")),
                ]
            )
        ),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.NetworkingV1Api",
        lambda: _obj(list_ingress_class=lambda: _obj(items=[_obj(metadata=_obj(name="nginx"))])),
    )
    monkeypatch.setattr("stelarctl.deploy.client.CustomObjectsApi", lambda: _obj())

    with pytest.raises(typer.BadParameter) as exc:
        preflight_check(model, auto_approve=True)

    assert "infrastructure.ingress_class" in str(exc.value)


def test_preflight_check_raises_when_clusterissuer_not_ready(monkeypatch):
    model = make_model(tls_mode="cert-manager", issuer="letsencrypt")

    monkeypatch.setattr(
        "stelarctl.deploy.config.list_kube_config_contexts",
        lambda: ([{"name": "minikube"}], {"name": "minikube"}),
    )
    monkeypatch.setattr("stelarctl.deploy.config.load_kube_config", lambda context=None: None)
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: None)
    monkeypatch.setattr(
        "stelarctl.deploy.client.CoreV1Api",
        lambda: _obj(read_namespace=lambda namespace: _obj()),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.StorageV1Api",
        lambda: _obj(
            list_storage_class=lambda: _obj(
                items=[
                    _obj(metadata=_obj(name="standard")),
                    _obj(metadata=_obj(name="csi-hostpath-sc")),
                ]
            )
        ),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.NetworkingV1Api",
        lambda: _obj(list_ingress_class=lambda: _obj(items=[_obj(metadata=_obj(name="nginx"))])),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.CustomObjectsApi",
        lambda: _obj(
            get_cluster_custom_object=lambda **kwargs: {"status": {"conditions": [{"type": "Ready", "status": "False"}]}}
        ),
    )

    with pytest.raises(typer.BadParameter) as exc:
        preflight_check(model, auto_approve=True)

    assert "exists but is not Ready" in str(exc.value)


def test_clear_namespace_annotations_ignores_not_found(monkeypatch):
    class FakeApiException(Exception):
        def __init__(self, status):
            self.status = status

    monkeypatch.setattr("stelarctl.deploy.config.load_kube_config", lambda context=None: None)
    monkeypatch.setattr(
        "stelarctl.deploy.client.CoreV1Api",
        lambda: _obj(
            patch_namespace=lambda name, body: (_ for _ in ()).throw(FakeApiException(404))
        ),
    )
    monkeypatch.setattr("stelarctl.deploy.ApiException", FakeApiException)

    clear_namespace_annotations("minikube", "missing")


def test_purge_namespace_uses_expected_resource_list(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "stelarctl.deploy._run_command",
        lambda command, check=False: calls.append(command),
    )

    purge_namespace("minikube", "stelar-dev")

    assert calls
    joined = " ".join(calls[0])
    assert "deployments.apps,statefulsets.apps,jobs.batch,services,configmaps,secrets,persistentvolumeclaims,ingresses.networking.k8s.io,serviceaccounts,roles.rbac.authorization.k8s.io,rolebindings.rbac.authorization.k8s.io,pods" in joined
    assert "--wait=true" in joined


def test_infer_tier_from_workloads_prefers_full_then_core():
    assert _infer_tier_from_workloads({"quay"}) == "full"
    assert _infer_tier_from_workloads({"ckan"}) == "core"
    assert _infer_tier_from_workloads(set()) is None


def test_infer_network_defaults_ingress_class_and_tls_manual():
    warnings: list[str] = []
    ingress = _obj(
        metadata=_obj(name="stelar", annotations={}),
        spec=_obj(ingress_class_name=None, tls=[_obj()], rules=[_obj(host="klms.example.com")]),
    )

    root, subdomains, scheme, tls_mode, issuer, ingress_class = _infer_network({"stelar": ingress}, warnings)

    assert root == "example.com"
    assert subdomains["primary"] == "klms"
    assert scheme == "https"
    assert tls_mode == "manual"
    assert issuer is None
    assert ingress_class == "nginx"
    assert warnings == ["Ingress class missing on ingress; defaulting to nginx."]


def test_infer_network_raises_for_bad_host():
    ingress = _obj(
        metadata=_obj(name="stelar", annotations={}),
        spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="localhost")]),
    )

    with pytest.raises(ValueError):
        _infer_network({"stelar": ingress}, [])


def test_infer_storage_handles_zero_single_and_multiple_classes():
    assert _infer_storage([]) == {"dynamic_class": "", "provisioning_class": ""}
    assert _infer_storage([_obj(spec=_obj(storage_class_name="standard"))]) == {
        "dynamic_class": "standard",
        "provisioning_class": "standard",
    }
    assert _infer_storage(
        [
            _obj(spec=_obj(storage_class_name="b-class")),
            _obj(spec=_obj(storage_class_name="a-class")),
        ]
    ) == {"dynamic_class": "a-class", "provisioning_class": "b-class"}


def test_secret_name_from_env_returns_none_for_missing_env():
    resource = _obj(spec=_obj(template=_obj(spec=_obj(containers=[_obj(env=[])]))))

    assert _secret_name_from_env(resource, "SMTP_PASSWORD") is None


def test_infer_secret_names_uses_defaults_for_missing_resources_and_full_tier():
    secrets = _infer_secret_names([], [], "full", False)
    names = {secret["name"] for secret in secrets}

    assert "quaydb-secret" in names
    assert "postgresdb-secret" in names


def test_infer_live_deployment_returns_inactive_for_annotations_only(monkeypatch):
    namespace_obj = _obj(metadata=_obj(annotations={"stelar.eu/tier": "core"}))

    monkeypatch.setattr("stelarctl.live.config.load_kube_config", lambda context: None)
    monkeypatch.setattr(
        "stelarctl.live.client.CoreV1Api",
        lambda: _obj(
            read_namespace=lambda namespace: namespace_obj,
            list_namespaced_config_map=lambda namespace: _obj(items=[]),
            list_namespaced_persistent_volume_claim=lambda namespace: _obj(items=[]),
        ),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.AppsV1Api",
        lambda: _obj(
            list_namespaced_deployment=lambda namespace: _obj(items=[]),
            list_namespaced_stateful_set=lambda namespace: _obj(items=[]),
        ),
    )
    monkeypatch.setattr("stelarctl.live.client.BatchV1Api", lambda: _obj(list_namespaced_job=lambda namespace: _obj(items=[])))
    monkeypatch.setattr("stelarctl.live.client.NetworkingV1Api", lambda: _obj(list_namespaced_ingress=lambda namespace: _obj(items=[])))

    live = infer_live_deployment("minikube", "stelar-dev")

    assert live.active is False
    assert live.model is None
