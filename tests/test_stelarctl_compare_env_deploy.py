from pathlib import Path

import pytest
import typer

from stelarctl.compare import compare_models
from stelarctl.deploy import (
    DeployDecision,
    perform_deploy,
    plan_deploy,
    preflight_check,
    teardown_target,
    wait_for_ready,
)
from stelarctl.env import load_stored_model, resolve_env_target, save_stored_model, write_spec_json
from stelarctl.live import LiveDeployment
from stelarctl.platform_model import PlatformModel


def make_model(
    *,
    context: str = "minikube",
    namespace: str = "stelar-dev",
    tier: str = "core",
    smtp_password: str = "smtp-secret",
    platform: str = "minikube",
    author: str = "dev@example.com",
) -> PlatformModel:
    return PlatformModel(
        platform=platform,
        k8s_context=context,
        namespace=namespace,
        author=author,
        tier=tier,
        infrastructure={
            "storage": {"dynamic_class": "standard", "provisioning_class": "standard"},
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
        secrets=[
            {"name": "postgresdb-secret", "data": {"password": "postgres"}},
            {"name": "ckandb-secret", "data": {"password": "ckan"}},
            {"name": "keycloakdb-secret", "data": {"password": "keycloak"}},
            {"name": "datastoredb-secret", "data": {"password": "datastore"}},
            {"name": "keycloakroot-secret", "data": {"password": "root"}},
            {"name": "smtpapi-secret", "data": {"password": smtp_password}},
            {"name": "ckanadmin-secret", "data": {"password": "admin"}},
            {"name": "minioroot-secret", "data": {"password": "minio"}},
            {"name": "session-secret-key", "data": {"key": "session"}},
            {"name": "quaydb-secret", "data": {"password": "quay"}},
        ],
    )


def make_inferred(model: PlatformModel) -> PlatformModel:
    payload = model.model_dump(mode="python")
    for secret in payload["secrets"]:
        for key in list(secret["data"]):
            secret["data"][key] = None
    return PlatformModel(**payload)


def test_compare_models_can_ignore_secret_values():
    left = make_model(smtp_password="new-password")
    right = make_model(smtp_password="old-password")

    assert not compare_models(left, right, include_secret_values=True).equal
    assert compare_models(left, right, include_secret_values=False).equal


def test_compare_models_can_ignore_non_observable_live_fields():
    left = make_model()
    right = make_model()
    right.infrastructure.storage.dynamic_class = "csi-hostpath-sc"

    assert not compare_models(left, right, include_secret_values=False).equal
    assert compare_models(
        left,
        right,
        include_secret_values=False,
        ignore_fields={"infrastructure.storage.dynamic_class"},
    ).equal


def test_env_round_trip_persists_model_and_target(tmp_path: Path):
    env_dir = tmp_path / "environments" / "minikube.dev"
    model = make_model()

    write_spec_json(env_dir, model)
    save_stored_model(env_dir, model)

    resolved_context, resolved_namespace = resolve_env_target(env_dir)
    loaded = load_stored_model(env_dir)

    assert (resolved_context, resolved_namespace) == (model.k8s_context, model.namespace)
    assert loaded == model


def test_plan_deploy_fresh_when_no_stored_and_no_live(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: None)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, False, None, []),
    )

    decision = plan_deploy(make_model(), tmp_path / "env")

    assert decision.action == "fresh"


def test_plan_deploy_noop_when_input_matches_consistent_stored(monkeypatch, tmp_path: Path):
    model = make_model()
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: model)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, make_inferred(model), []),
    )

    decision = plan_deploy(model, tmp_path / "env")

    assert decision.action == "noop"


def test_plan_deploy_hard_redeploy_when_secret_values_change_against_stored(monkeypatch, tmp_path: Path):
    stored = make_model(smtp_password="old-password")
    incoming = make_model(smtp_password="new-password")
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: stored)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, make_inferred(stored), []),
    )

    decision = plan_deploy(incoming, tmp_path / "env")

    assert decision.action == "hard_redeploy"
    assert any("secrets.smtpapi-secret.password" in item for item in decision.differences)


def test_plan_deploy_prompts_for_secret_values_when_only_live_state_exists(monkeypatch, tmp_path: Path):
    live_model = make_inferred(make_model())
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: None)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, live_model, []),
    )

    decision = plan_deploy(make_model(), tmp_path / "env")

    assert decision.action == "prompt_secret_values"
    assert decision.needs_secret_confirmation is True


def test_plan_deploy_detects_drift_and_uses_live_baseline(monkeypatch, tmp_path: Path):
    stored = make_model(namespace="old-ns")
    live_model = make_inferred(make_model())
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: stored)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, live_model, []),
    )

    decision = plan_deploy(make_model(), tmp_path / "env")

    assert decision.action == "prompt_secret_values"
    assert decision.live_drift_differences


def test_plan_deploy_detects_drift_and_hard_redeploys_when_input_differs_from_live(monkeypatch, tmp_path: Path):
    stored = make_model(namespace="old-ns")
    live_model = make_inferred(make_model())
    incoming = make_model(tier="full")
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: stored)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, live_model, []),
    )

    decision = plan_deploy(incoming, tmp_path / "env")

    assert decision.action == "hard_redeploy"
    assert any("tier:" in item for item in decision.differences)


def test_plan_deploy_treats_missing_live_namespace_as_fresh_even_with_stored(monkeypatch, tmp_path: Path):
    stored = make_model()
    monkeypatch.setattr("stelarctl.deploy.load_stored_model", lambda env_path: stored)
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, False, None, []),
    )

    decision = plan_deploy(make_model(), tmp_path / "env")

    assert decision.action == "fresh"


def test_perform_deploy_returns_early_on_noop(monkeypatch, tmp_path: Path):
    model = make_model()
    called = {"preflight": False}

    monkeypatch.setattr(
        "stelarctl.deploy.plan_deploy",
        lambda input_model, env_path: DeployDecision(action="noop", reason="same", differences=[]),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.preflight_check",
        lambda input_model: called.__setitem__("preflight", True),
    )

    decision = perform_deploy(model, tmp_path / "env", auto_approve=True)

    assert decision.action == "noop"
    assert called["preflight"] is False


def test_perform_deploy_waits_even_on_noop(monkeypatch, tmp_path: Path):
    model = make_model()
    calls: list[str] = []

    monkeypatch.setattr(
        "stelarctl.deploy.plan_deploy",
        lambda input_model, env_path: DeployDecision(action="noop", reason="same", differences=[]),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.wait_for_ready",
        lambda context_name, namespace, timeout_seconds=600, poll_interval=5: calls.append(
            f"wait:{context_name}:{namespace}:{timeout_seconds}:{poll_interval}"
        ),
    )

    decision = perform_deploy(
        model,
        tmp_path / "env",
        auto_approve=True,
        wait=True,
        wait_timeout=45,
        wait_interval=3,
    )

    assert decision.action == "noop"
    assert calls == ["wait:minikube:stelar-dev:45:3"]


def test_perform_deploy_secret_confirmation_can_short_circuit(monkeypatch, tmp_path: Path):
    model = make_model()
    monkeypatch.setattr(
        "stelarctl.deploy.plan_deploy",
        lambda input_model, env_path: DeployDecision(
            action="prompt_secret_values",
            reason="unknown secrets",
            differences=[],
            needs_secret_confirmation=True,
        ),
    )
    monkeypatch.setattr("stelarctl.deploy.typer.confirm", lambda *args, **kwargs: True)

    decision = perform_deploy(model, tmp_path / "env", auto_approve=True)

    assert decision.action == "noop"


def test_perform_deploy_runs_apply_flow_for_hard_redeploy(monkeypatch, tmp_path: Path):
    model = make_model()
    calls: list[str] = []

    monkeypatch.setattr(
        "stelarctl.deploy.plan_deploy",
        lambda input_model, env_path: DeployDecision(
            action="hard_redeploy",
            reason="changed",
            differences=["tier: core -> full"],
        ),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.preflight_check",
        lambda input_model, auto_approve=False: calls.append("preflight"),
    )
    monkeypatch.setattr("stelarctl.deploy.write_spec_json", lambda env_path, input_model: calls.append("spec"))
    monkeypatch.setattr("stelarctl.deploy.write_main_jsonnet", lambda input_model, env: calls.append("main"))
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: calls.append("cmd:" + command[0]))
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, True, make_inferred(model), []),
    )
    monkeypatch.setattr("stelarctl.deploy.purge_namespace", lambda context, namespace: calls.append("purge"))
    monkeypatch.setattr("stelarctl.deploy.annotate_namespace", lambda input_model: calls.append("annotate"))
    monkeypatch.setattr("stelarctl.deploy.apply_secrets", lambda input_model: calls.append("secrets"))
    monkeypatch.setattr("stelarctl.deploy.apply_generated_secrets", lambda input_model: calls.append("generated"))
    monkeypatch.setattr("stelarctl.deploy.save_stored_model", lambda env_path, input_model: calls.append("save"))

    decision = perform_deploy(model, tmp_path / "env", auto_approve=True)

    assert decision.action == "hard_redeploy"
    assert calls == [
        "preflight",
        "spec",
        "main",
        "cmd:tk",
        "purge",
        "annotate",
        "secrets",
        "generated",
        "cmd:tk",
        "save",
    ]


def test_perform_deploy_can_wait_for_readiness(monkeypatch, tmp_path: Path):
    model = make_model()
    calls: list[str] = []

    monkeypatch.setattr(
        "stelarctl.deploy.plan_deploy",
        lambda input_model, env_path: DeployDecision(action="fresh", reason="fresh", differences=[]),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.preflight_check",
        lambda input_model, auto_approve=False: calls.append("preflight"),
    )
    monkeypatch.setattr("stelarctl.deploy.write_spec_json", lambda env_path, input_model: calls.append("spec"))
    monkeypatch.setattr("stelarctl.deploy.write_main_jsonnet", lambda input_model, env: calls.append("main"))
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: calls.append("cmd:" + command[0]))
    monkeypatch.setattr(
        "stelarctl.deploy.infer_live_deployment",
        lambda context, namespace: LiveDeployment(context, namespace, False, None, []),
    )
    monkeypatch.setattr("stelarctl.deploy.annotate_namespace", lambda input_model: calls.append("annotate"))
    monkeypatch.setattr("stelarctl.deploy.apply_secrets", lambda input_model: calls.append("secrets"))
    monkeypatch.setattr("stelarctl.deploy.apply_generated_secrets", lambda input_model: calls.append("generated"))
    monkeypatch.setattr("stelarctl.deploy.save_stored_model", lambda env_path, input_model: calls.append("save"))
    monkeypatch.setattr(
        "stelarctl.deploy.wait_for_ready",
        lambda context_name, namespace, timeout_seconds=600, poll_interval=5: calls.append(
            f"wait:{context_name}:{namespace}:{timeout_seconds}:{poll_interval}"
        ),
    )

    perform_deploy(
        model,
        tmp_path / "env",
        auto_approve=True,
        wait=True,
        wait_timeout=123,
        wait_interval=7,
    )

    assert calls[-1] == "wait:minikube:stelar-dev:123:7"


def test_wait_for_ready_returns_when_snapshot_reaches_ready(monkeypatch):
    snapshots = iter(
        [
            (
                type(
                    "Snapshot",
                    (),
                    {
                        "phase": "Progressing",
                        "overall_percent": 38,
                        "jobs_completed": 0,
                        "jobs_total": 3,
                        "components_ready": 5,
                        "components_total": 8,
                    },
                )(),
                [],
            ),
            (
                type(
                    "Snapshot",
                    (),
                    {
                        "phase": "Ready",
                        "overall_percent": 100,
                        "jobs_completed": 3,
                        "jobs_total": 3,
                        "components_ready": 8,
                        "components_total": 8,
                    },
                )(),
                [],
            ),
        ]
    )
    messages: list[str] = []

    monkeypatch.setattr("stelarctl.deploy.collect_inferred_status", lambda context, namespace: next(snapshots))
    monkeypatch.setattr("stelarctl.deploy.time.sleep", lambda seconds: None)
    monkeypatch.setattr("stelarctl.deploy.typer.echo", lambda message="", **kwargs: messages.append(message))
    monkeypatch.setattr("stelarctl.deploy.format_status", lambda snapshot: "formatted")

    wait_for_ready("minikube", "stelar-dev", timeout_seconds=30, poll_interval=1)

    assert any("Waiting for 'minikube/stelar-dev' to reach Ready 100%" in message for message in messages)
    assert "Progressing 38% (jobs 0/3, components 5/8)" in messages
    assert "Deployment reached Ready 100%." in messages
    assert "formatted" in messages


def test_wait_for_ready_exits_on_degraded_snapshot(monkeypatch):
    snapshot = type(
        "Snapshot",
        (),
        {
            "phase": "Degraded",
            "overall_percent": 38,
            "jobs_completed": 0,
            "jobs_total": 3,
            "components_ready": 5,
            "components_total": 8,
        },
    )()
    messages: list[str] = []

    monkeypatch.setattr("stelarctl.deploy.collect_inferred_status", lambda context, namespace: (snapshot, []))
    monkeypatch.setattr("stelarctl.deploy.typer.echo", lambda message="", **kwargs: messages.append(message))
    monkeypatch.setattr("stelarctl.deploy.format_status", lambda snapshot: "formatted")

    with pytest.raises(typer.Exit) as exc:
        wait_for_ready("minikube", "stelar-dev", timeout_seconds=30, poll_interval=1)

    assert exc.value.exit_code == 1

    assert "Deployment entered a degraded state while waiting for readiness." in messages
    assert "formatted" in messages


def test_preflight_check_auto_approve_creates_namespace_without_prompt(monkeypatch):
    model = make_model()
    created = {"namespace": False}
    
    class FakeApiException(Exception):
        def __init__(self, status):
            self.status = status

    monkeypatch.setattr(
        "stelarctl.deploy.config.list_kube_config_contexts",
        lambda: ([{"name": "minikube"}], {"name": "minikube"}),
    )
    monkeypatch.setattr("stelarctl.deploy.config.load_kube_config", lambda context=None: None)
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=True: None)

    class FakeCoreApi:
        def read_namespace(self, namespace):
            raise FakeApiException(404)

        def create_namespace(self, body):
            created["namespace"] = True

    monkeypatch.setattr("stelarctl.deploy.ApiException", FakeApiException)
    monkeypatch.setattr("stelarctl.deploy.client.CoreV1Api", FakeCoreApi)
    monkeypatch.setattr(
        "stelarctl.deploy.client.StorageV1Api",
        lambda: type("StorageApi", (), {"list_storage_class": lambda self: type("Result", (), {"items": [type("Obj", (), {"metadata": type("Meta", (), {"name": "standard"})()})(), type("Obj", (), {"metadata": type("Meta", (), {"name": "csi-hostpath-sc"})()})()]})()})(),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.NetworkingV1Api",
        lambda: type("NetApi", (), {"list_ingress_class": lambda self: type("Result", (), {"items": [type("Obj", (), {"metadata": type("Meta", (), {"name": "nginx"})()})()]})()})(),
    )
    monkeypatch.setattr(
        "stelarctl.deploy.client.CustomObjectsApi",
        lambda: type("CustomApi", (), {})(),
    )
    monkeypatch.setattr("stelarctl.deploy.typer.confirm", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("prompt should not be called")))

    preflight_check(model, auto_approve=True)

    assert created["namespace"] is True


def test_teardown_target_purges_resources_and_removes_stored_model(tmp_path: Path, monkeypatch):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    model_file = env_dir / "model.yaml"
    model_file.write_text("x: 1\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr("stelarctl.deploy.purge_namespace", lambda context, namespace: calls.append("purge"))
    monkeypatch.setattr("stelarctl.deploy._run_command", lambda command, check=False: calls.append("cmd"))
    monkeypatch.setattr("stelarctl.deploy.clear_namespace_annotations", lambda context, namespace: calls.append("clear"))

    teardown_target("minikube", "stelar-dev", env_path=env_dir, auto_approve=True)

    assert calls == ["purge", "clear"]
    assert not model_file.exists()


def test_teardown_target_can_delete_namespace_and_env(tmp_path: Path, monkeypatch):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "spec.json").write_text("{}", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr("stelarctl.deploy.purge_namespace", lambda context, namespace: calls.append("purge"))
    monkeypatch.setattr("stelarctl.deploy.clear_namespace_annotations", lambda context, namespace: calls.append("clear"))
    monkeypatch.setattr(
        "stelarctl.deploy._run_command",
        lambda command, check=False: calls.append(" ".join(command)),
    )

    teardown_target(
        "minikube",
        "stelar-dev",
        env_path=env_dir,
        delete_namespace=True,
        delete_env=True,
        auto_approve=True,
    )

    assert calls[0] == "purge"
    assert "kubectl --context minikube delete namespace stelar-dev --ignore-not-found=true --wait=false" in calls[1]
    assert not env_dir.exists()
