from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from stelarctl import main
from stelarctl.env import (
    ensure_env_dir,
    load_stored_model,
    resolve_env_target,
    save_stored_model,
    spec_path,
    stored_model_path,
    write_spec_json,
)
from stelarctl.generator import (
    _cluster_issuer,
    _insecure_minio,
    _secret_name,
    generate_main_jsonnet,
)
from stelarctl.loader import load_model
from stelarctl.platform_model import DNSConfig, PlatformModel
from stelarctl.secrets import _apply_secret, _encode, _random_string, apply_generated_secrets, apply_secrets, delete_secrets


def make_model(
    *,
    scheme: str = "http",
    tls_mode: str = "none",
    issuer: str | None = None,
    enable_llm_search: bool = False,
    groq_url: str | None = None,
    groq_model: str | None = None,
) -> PlatformModel:
    return PlatformModel(
        platform="minikube",
        k8s_context="minikube",
        namespace="stelar-dev",
        author="dev@example.com",
        tier="core",
        infrastructure={
            "storage": {"dynamic_class": "standard", "provisioning_class": "csi-hostpath-sc"},
            "ingress_class": "nginx",
            "tls": {"mode": tls_mode, **({"issuer": issuer} if issuer is not None else {})},
        },
        dns={"root": "minikube.test", "scheme": scheme},
        config={
            "smtp_server": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "apikey",
            "s3_console_url": "http://klms.minikube.test/s3/login",
            "enable_llm_search": enable_llm_search,
            "groq_api_url": groq_url,
            "groq_api_model": groq_model,
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


def test_dns_url_for_uses_named_subdomain():
    dns = DNSConfig(root="example.com", scheme="https", primary="klms")

    assert dns.url_for("primary") == "https://klms.example.com"


def test_platform_model_requires_groq_fields_when_llm_enabled():
    with pytest.raises(ValidationError):
        make_model(enable_llm_search=True)


def test_platform_model_requires_issuer_for_cert_manager():
    with pytest.raises(ValidationError):
        make_model(scheme="https", tls_mode="cert-manager")


def test_platform_model_rejects_tls_for_http_scheme():
    with pytest.raises(ValidationError):
        make_model(scheme="http", tls_mode="manual")


def test_load_stored_model_returns_none_when_file_missing(tmp_path: Path):
    assert load_stored_model(tmp_path / "env") is None


def test_save_stored_model_creates_directory_and_round_trips(tmp_path: Path):
    env_path = tmp_path / "nested" / "env"
    model = make_model()

    path = save_stored_model(env_path, model)

    assert path == stored_model_path(env_path)
    assert env_path.exists()
    assert load_stored_model(env_path) == model


def test_write_spec_json_contains_expected_defaults(tmp_path: Path):
    env_path = tmp_path / "env"
    model = make_model()

    path = write_spec_json(env_path, model)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path == spec_path(env_path)
    assert payload["spec"]["contextNames"] == ["minikube"]
    assert payload["spec"]["namespace"] == "stelar-dev"
    assert payload["spec"]["resourceDefaults"]["annotations"]["stelar.eu/author"] == "dev@example.com"
    assert payload["spec"]["resourceDefaults"]["labels"]["stelar.deployment"] == "main"


def test_resolve_env_target_raises_for_missing_spec(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_env_target(tmp_path / "missing-env")


def test_resolve_env_target_raises_for_invalid_spec(tmp_path: Path):
    env_path = tmp_path / "env"
    ensure_env_dir(env_path)
    spec_path(env_path).write_text(json.dumps({"spec": {"contextNames": [], "namespace": ""}}), encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_env_target(env_path)


def test_load_model_exits_on_validation_error(tmp_path: Path, capsys):
    model_path = tmp_path / "bad.yaml"
    model_path.write_text("platform: bad\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        load_model(str(model_path), PlatformModel)

    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Field required" in captured.out


def test_cluster_issuer_and_insecure_minio_helpers():
    manual = make_model(scheme="https", tls_mode="manual")
    cert_manager = make_model(scheme="https", tls_mode="cert-manager", issuer="letsencrypt")

    assert _cluster_issuer(manual) == "null"
    assert _cluster_issuer(cert_manager) == "'letsencrypt'"
    assert _insecure_minio(make_model()) == "true"
    assert _insecure_minio(manual) == "false"


def test_secret_name_helper_raises_when_secret_missing():
    with pytest.raises(ValueError):
        _secret_name(make_model(), "missing-secret")


def test_generate_main_jsonnet_renders_llm_and_tls_settings():
    model = make_model(
        scheme="https",
        tls_mode="cert-manager",
        issuer="letsencrypt",
        enable_llm_search=True,
        groq_url="https://api.groq.example",
        groq_model="llama-3",
    )

    rendered = generate_main_jsonnet(model)

    assert "local tier = import 'tiers/core.libsonnet';" in rendered
    assert "CLUSTER_ISSUER: 'letsencrypt'" in rendered
    assert "INSECURE_MC_CLIENT: 'false'" in rendered
    assert "ENABLE_LLM_SEARCH: 'true'" in rendered
    assert "GROQ_API_URL: 'https://api.groq.example'" in rendered
    assert "import 'llmsearch.libsonnet'" in rendered


def test_random_string_respects_chunking():
    value = _random_string(10, chunk_size=4, separator="-")

    parts = value.split("-")
    assert len(parts) == 3
    assert "".join(parts).isalnum()
    assert len("".join(parts)) == 10


def test_encode_base64_encodes_values():
    encoded = _encode({"password": "secret"})

    assert encoded == {"password": base64.b64encode(b"secret").decode("utf-8")}


def test_apply_secret_replaces_on_conflict(monkeypatch):
    calls: list[tuple[str, str]] = []

    class FakeApiException(Exception):
        def __init__(self, status):
            self.status = status

    class FakeV1:
        def create_namespaced_secret(self, namespace, body):
            calls.append(("create", body["metadata"]["name"]))
            raise FakeApiException(409)

        def replace_namespaced_secret(self, name, namespace, body):
            calls.append(("replace", name))

    monkeypatch.setattr("stelarctl.secrets.client.exceptions.ApiException", FakeApiException)

    _apply_secret(FakeV1(), "smtpapi-secret", "stelar-dev", {"password": "secret"})

    assert calls == [("create", "smtpapi-secret"), ("replace", "smtpapi-secret")]


def test_apply_secrets_omits_none_values(monkeypatch):
    applied: list[tuple[str, str, dict]] = []
    model = make_model()
    model.secrets = [SimpleNamespace(name="session-secret-key", data=SimpleNamespace(model_dump=lambda exclude_none=True: {"key": "session"}))]

    monkeypatch.setattr("stelarctl.secrets.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.secrets.client.CoreV1Api", lambda: object())
    monkeypatch.setattr(
        "stelarctl.secrets._apply_secret",
        lambda v1, name, namespace, data: applied.append((name, namespace, data)),
    )

    apply_secrets(model)

    assert applied == [("session-secret-key", "stelar-dev", {"key": "session"})]


def test_apply_generated_secrets_uses_generated_keys(monkeypatch):
    applied: list[tuple[str, str, dict]] = []
    generated = iter(["session-token", "jwt-token"])

    monkeypatch.setattr("stelarctl.secrets.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.secrets.client.CoreV1Api", lambda: object())
    monkeypatch.setattr("stelarctl.secrets._random_string", lambda *args, **kwargs: next(generated))
    monkeypatch.setattr(
        "stelarctl.secrets._apply_secret",
        lambda v1, name, namespace, data: applied.append((name, namespace, data)),
    )

    apply_generated_secrets(make_model())

    assert applied == [
        (
            "ckan-auth-secret",
            "stelar-dev",
            {"session-key": "session-token", "jwt-key": "string:jwt-token"},
        )
    ]


def test_delete_secrets_deletes_every_secret(monkeypatch):
    deleted: list[str] = []
    secrets = SimpleNamespace(items=[SimpleNamespace(metadata=SimpleNamespace(name="a")), SimpleNamespace(metadata=SimpleNamespace(name="b"))])

    class FakeV1:
        def list_namespaced_secret(self, namespace):
            return secrets

        def delete_namespaced_secret(self, name, namespace):
            deleted.append(name)

    monkeypatch.setattr("stelarctl.secrets.config.load_kube_config", lambda context: None)
    monkeypatch.setattr("stelarctl.secrets.client.CoreV1Api", FakeV1)

    delete_secrets(make_model())

    assert deleted == ["a", "b"]


def test_main_calls_app(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(main, "app", lambda: calls.append("app"))

    main.main()

    assert calls == ["app"]
