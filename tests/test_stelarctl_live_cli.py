from types import SimpleNamespace

from stelarctl.cli import _resolve_status_target
from stelarctl.live import infer_live_deployment


def _obj(**kwargs):
    return SimpleNamespace(**kwargs)


def _container_env(secret_name: str, env_name: str):
    return _obj(
        name=env_name,
        value_from=_obj(secret_key_ref=_obj(name=secret_name)),
    )


def _deployment(name: str, env_map: dict[str, str]):
    env = [_container_env(secret_name, env_name) for env_name, secret_name in env_map.items()]
    return _obj(
        metadata=_obj(name=name),
        spec=_obj(template=_obj(spec=_obj(containers=[_obj(env=env)]))),
    )


def _statefulset(name: str, env_map: dict[str, str]):
    return _deployment(name, env_map)


def test_resolve_status_target_uses_active_context_namespace(monkeypatch):
    monkeypatch.setattr(
        "stelarctl.cli.config.list_kube_config_contexts",
        lambda: (
            [{"name": "minikube", "context": {"namespace": "lab"}}],
            {"name": "minikube", "context": {"namespace": "lab"}},
        ),
    )

    assert _resolve_status_target(None, None, None) == ("minikube", "lab")


def test_resolve_status_target_uses_explicit_context_and_default_namespace(monkeypatch):
    monkeypatch.setattr(
        "stelarctl.cli.config.list_kube_config_contexts",
        lambda: (
            [
                {"name": "minikube", "context": {"namespace": "lab"}},
                {"name": "other", "context": {}},
            ],
            {"name": "minikube", "context": {"namespace": "lab"}},
        ),
    )

    assert _resolve_status_target(None, "other", None) == ("other", "default")


def test_infer_live_deployment_handles_missing_namespace(monkeypatch):
    class FakeCoreApi:
        def read_namespace(self, namespace):
            raise ExceptionWrapper(404)

    class ExceptionWrapper(Exception):
        def __init__(self, status):
            self.status = status

    monkeypatch.setattr("stelarctl.live.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.live.client.CoreV1Api", FakeCoreApi)
    monkeypatch.setattr("stelarctl.live.client.exceptions.ApiException", ExceptionWrapper)

    live = infer_live_deployment("minikube", "missing")

    assert live.active is False
    assert "does not exist" in live.warnings[0]


def test_infer_live_deployment_builds_model_from_cluster(monkeypatch):
    namespace_obj = _obj(metadata=_obj(annotations={"stelar.eu/tier": "core"}))
    ingresses = [
        _obj(
            metadata=_obj(name="stelar", annotations={}),
            spec=_obj(
                ingress_class_name="nginx",
                tls=[],
                rules=[_obj(host="klms.minikube.test")],
            ),
        ),
        _obj(
            metadata=_obj(name="kc", annotations={}),
            spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="kc.minikube.test")]),
        ),
        _obj(
            metadata=_obj(name="s3", annotations={}),
            spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="minio.minikube.test")]),
        ),
        _obj(
            metadata=_obj(name="reg", annotations={}),
            spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="img.minikube.test")]),
        ),
    ]
    configmaps = [
        _obj(
            metadata=_obj(name="api-config-map"),
            data={
                "SMTP_SERVER": "smtp.example.com",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": "apikey",
                "S3_CONSOLE_URL": "http://klms.minikube.test/s3/login",
                "ENABLE_LLM_SEARCH": "false",
            },
        )
    ]
    deployments = [
        _deployment("stelarapi", {"SMTP_PASSWORD": "smtpapi-secret", "SESSION_SECRET_KEY": "session-secret-key"}),
        _deployment("keycloak", {"KEYCLOAK_ADMIN_PASSWORD": "keycloakroot-secret"}),
        _deployment("ckan", {"CKAN_SYSADMIN_PASSWORD": "ckanadmin-secret"}),
        _deployment("redis", {}),
        _deployment("stelarapi", {"SMTP_PASSWORD": "smtpapi-secret", "SESSION_SECRET_KEY": "session-secret-key"}),
        _deployment("datapusher", {}),
        _deployment("keycloak", {"KEYCLOAK_ADMIN_PASSWORD": "keycloakroot-secret"}),
        _deployment("ckan", {"CKAN_SYSADMIN_PASSWORD": "ckanadmin-secret"}),
    ]
    statefulsets = [
        _statefulset(
            "db",
            {
                "POSTGRES_PASSWORD": "postgresdb-secret",
                "CKAN_DB_PASSWORD": "ckandb-secret",
                "KEYCLOAK_DB_PASSWORD": "keycloakdb-secret",
                "DATASTORE_READONLY_PASSWORD": "datastoredb-secret",
                "QUAY_DB_PASSWORD": "quaydb-secret",
            },
        ),
        _statefulset("minio", {"MINIO_ROOT_PASSWORD": "minioroot-secret"}),
        _statefulset("solr", {}),
    ]
    pvcs = [_obj(spec=_obj(storage_class_name="standard"))]

    monkeypatch.setattr("stelarctl.live.config.load_kube_config", lambda context: None)
    monkeypatch.setattr(
        "stelarctl.live.client.CoreV1Api",
        lambda: _obj(
            read_namespace=lambda namespace: namespace_obj,
            list_namespaced_config_map=lambda namespace: _obj(items=configmaps),
            list_namespaced_persistent_volume_claim=lambda namespace: _obj(items=pvcs),
        ),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.AppsV1Api",
        lambda: _obj(
            list_namespaced_deployment=lambda namespace: _obj(items=deployments),
            list_namespaced_stateful_set=lambda namespace: _obj(items=statefulsets),
        ),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.BatchV1Api",
        lambda: _obj(list_namespaced_job=lambda namespace: _obj(items=[])),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.NetworkingV1Api",
        lambda: _obj(list_namespaced_ingress=lambda namespace: _obj(items=ingresses)),
    )

    live = infer_live_deployment("minikube", "stelar-dev")

    assert live.active is True
    assert live.model is not None
    assert live.model.k8s_context == "minikube"
    assert live.model.namespace == "stelar-dev"
    assert live.model.dns.root == "minikube.test"
    assert live.model.infrastructure.storage.dynamic_class == "standard"
    assert any(secret.name == "smtpapi-secret" for secret in live.model.secrets)


def test_infer_live_deployment_falls_back_to_ingress_for_s3_console_url(monkeypatch):
    namespace_obj = _obj(metadata=_obj(annotations={"stelar.eu/tier": "core"}))
    ingresses = [
        _obj(
            metadata=_obj(name="stelar", annotations={}),
            spec=_obj(
                ingress_class_name="nginx",
                tls=[],
                rules=[_obj(host="klms.minikube.test")],
            ),
        ),
        _obj(
            metadata=_obj(name="kc", annotations={}),
            spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="kc.minikube.test")]),
        ),
        _obj(
            metadata=_obj(name="s3", annotations={}),
            spec=_obj(ingress_class_name="nginx", tls=[], rules=[_obj(host="minio.minikube.test")]),
        ),
    ]
    configmaps = [
        _obj(
            metadata=_obj(name="api-config-map"),
            data={
                "SMTP_SERVER": "smtp.example.com",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": "apikey",
                "ENABLE_LLM_SEARCH": "false",
            },
        )
    ]
    deployments = [
        _deployment("stelarapi", {"SMTP_PASSWORD": "smtpapi-secret", "SESSION_SECRET_KEY": "session-secret-key"}),
        _deployment("keycloak", {"KEYCLOAK_ADMIN_PASSWORD": "keycloakroot-secret"}),
        _deployment("ckan", {"CKAN_SYSADMIN_PASSWORD": "ckanadmin-secret"}),
        _deployment("redis", {}),
        _deployment("datapusher", {}),
    ]
    statefulsets = [
        _statefulset(
            "db",
            {
                "POSTGRES_PASSWORD": "postgresdb-secret",
                "CKAN_DB_PASSWORD": "ckandb-secret",
                "KEYCLOAK_DB_PASSWORD": "keycloakdb-secret",
                "DATASTORE_READONLY_PASSWORD": "datastoredb-secret",
            },
        ),
        _statefulset("minio", {"MINIO_ROOT_PASSWORD": "minioroot-secret"}),
        _statefulset("solr", {}),
    ]
    pvcs = [_obj(spec=_obj(storage_class_name="standard"))]

    monkeypatch.setattr("stelarctl.live.config.load_kube_config", lambda context: None)
    monkeypatch.setattr(
        "stelarctl.live.client.CoreV1Api",
        lambda: _obj(
            read_namespace=lambda namespace: namespace_obj,
            list_namespaced_config_map=lambda namespace: _obj(items=configmaps),
            list_namespaced_persistent_volume_claim=lambda namespace: _obj(items=pvcs),
        ),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.AppsV1Api",
        lambda: _obj(
            list_namespaced_deployment=lambda namespace: _obj(items=deployments),
            list_namespaced_stateful_set=lambda namespace: _obj(items=statefulsets),
        ),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.BatchV1Api",
        lambda: _obj(list_namespaced_job=lambda namespace: _obj(items=[])),
    )
    monkeypatch.setattr(
        "stelarctl.live.client.NetworkingV1Api",
        lambda: _obj(list_namespaced_ingress=lambda namespace: _obj(items=ingresses)),
    )

    live = infer_live_deployment("minikube", "stelar-dev")

    assert live.model is not None
    assert live.model.config.s3_console_url == "http://klms.minikube.test/s3/login"
