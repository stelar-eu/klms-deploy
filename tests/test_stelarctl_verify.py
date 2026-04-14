from __future__ import annotations

from types import SimpleNamespace

from stelarctl.platform_model import PlatformModel
from stelarctl.verify import CORE_CHECKS, run_verification_checks, verification_checks_for_model


def make_model() -> PlatformModel:
    return PlatformModel(
        platform="minikube",
        k8s_context="minikube",
        namespace="stelar-dev",
        author="dev@example.com",
        tier="core",
        infrastructure={
            "storage": {"dynamic_class": "standard", "provisioning_class": "csi-hostpath-sc"},
            "ingress_class": "nginx",
            "tls": {"mode": "none"},
        },
        dns={"root": "minikube.test", "scheme": "http"},
        config={
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "apikey",
            "s3_console_url": "http://klms.minikube.test/s3/login",
            "enable_llm_search": False,
        },
        secrets=[],
    )


def test_verification_checks_for_model_returns_core_checks():
    checks = verification_checks_for_model(make_model())

    assert checks == CORE_CHECKS


def test_run_verification_checks_reports_success(monkeypatch):
    responses = {
        ("ckan:api", "api/3/action/status_show"): ({"success": True}, 200, {}),
        ("keycloak:keycloak-kchealth", "health/ready"): ({"status": "UP"}, 200, {}),
        ("minio:minio-minapi", "minio/health/live"): ("", 200, {}),
    }

    class FakeCoreApi:
        def connect_get_namespaced_service_proxy_with_path_with_http_info(self, name, namespace, path, _request_timeout=None):
            return responses[(name, path)]

    monkeypatch.setattr("stelarctl.verify.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.verify.client.CoreV1Api", FakeCoreApi)

    results = run_verification_checks("minikube", "stelar-dev", CORE_CHECKS)

    assert [result.ok for result in results] == [True, True, True]


def test_run_verification_checks_reports_bad_status_and_missing_content(monkeypatch):
    responses = {
        ("ckan:api", "api/3/action/status_show"): ({"success": False}, 200, {}),
        ("keycloak:keycloak-kchealth", "health/ready"): ("not ready", 503, {}),
        ("minio:minio-minapi", "minio/health/live"): ("", 200, {}),
    }

    class FakeCoreApi:
        def connect_get_namespaced_service_proxy_with_path_with_http_info(self, name, namespace, path, _request_timeout=None):
            return responses[(name, path)]

    monkeypatch.setattr("stelarctl.verify.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.verify.client.CoreV1Api", FakeCoreApi)

    results = run_verification_checks("minikube", "stelar-dev", CORE_CHECKS)

    assert results[0].ok is False
    assert results[0].detail == "successful CKAN status response"
    assert results[1].ok is False
    assert "unexpected status 503" == results[1].detail
    assert results[2].ok is True


def test_run_verification_checks_reports_request_failures(monkeypatch):
    class FakeCoreApi:
        def connect_get_namespaced_service_proxy_with_path_with_http_info(self, name, namespace, path, _request_timeout=None):
            raise RuntimeError("boom")

    monkeypatch.setattr("stelarctl.verify.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.verify.client.CoreV1Api", FakeCoreApi)

    results = run_verification_checks("minikube", "stelar-dev", CORE_CHECKS[:1])

    assert len(results) == 1
    assert results[0].ok is False
    assert "request failed: boom" == results[0].detail


def test_run_verification_checks_accepts_python_literal_payloads(monkeypatch):
    responses = {
        ("ckan:api", "api/3/action/status_show"): ("{'success': True}", 200, {}),
        ("keycloak:keycloak-kchealth", "health/ready"): ("{'status': 'UP'}", 200, {}),
    }

    class FakeCoreApi:
        def connect_get_namespaced_service_proxy_with_path_with_http_info(self, name, namespace, path, _request_timeout=None):
            return responses[(name, path)]

    monkeypatch.setattr("stelarctl.verify.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.verify.client.CoreV1Api", FakeCoreApi)

    results = run_verification_checks("minikube", "stelar-dev", CORE_CHECKS[:2])

    assert [result.ok for result in results] == [True, True]
