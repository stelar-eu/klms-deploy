from __future__ import annotations

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from stelarctl.cli import _resolve_status_target, app
from stelarctl.status import (
    ExpectedResource,
    _component_status,
    _deployment_status,
    _job_status,
    _pod_failures,
    _statefulset_status,
    calculate_progress,
    collect_inferred_status,
    derive_phase,
    format_status,
    render_bar,
)


runner = CliRunner()


def _obj(**kwargs):
    return SimpleNamespace(**kwargs)


def test_resolve_status_target_raises_for_unknown_context(monkeypatch):
    monkeypatch.setattr(
        "stelarctl.cli.config.list_kube_config_contexts",
        lambda: ([{"name": "minikube", "context": {}}], {"name": "minikube", "context": {}}),
    )

    with pytest.raises(Exception) as exc:
        _resolve_status_target(None, "other", None)

    assert "Kubernetes context 'other' not found." in str(exc.value)


def test_resolve_status_target_raises_when_no_active_context(monkeypatch):
    monkeypatch.setattr("stelarctl.cli.config.list_kube_config_contexts", lambda: ([], None))

    with pytest.raises(Exception) as exc:
        _resolve_status_target(None, None, None)

    assert "No active Kubernetes context found" in str(exc.value)


def test_status_command_prints_warnings_for_inactive_target(monkeypatch):
    monkeypatch.setattr("stelarctl.cli.collect_inferred_status", lambda context, namespace: (None, ["missing namespace"]))

    result = runner.invoke(app, ["status", "--context", "minikube", "--namespace", "missing"])

    assert result.exit_code == 0
    assert "No active STELAR deployment found in minikube/missing." in result.stdout
    assert "Warnings:" in result.stdout
    assert "- missing namespace" in result.stdout


def test_deploy_command_passes_wait_flags(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("stelarctl.cli._load", lambda path: "model")
    monkeypatch.setattr(
        "stelarctl.cli.perform_deploy",
        lambda pm, env, auto_approve=False, wait=False, wait_timeout=600, wait_interval=5: calls.append(
            (pm, env, auto_approve, wait, wait_timeout, wait_interval)
        ),
    )

    result = runner.invoke(
        app,
        [
            "deploy",
            str(tmp_path / "model.yaml"),
            "--env",
            str(tmp_path / "env"),
            "--yes",
            "--wait",
            "--wait-timeout",
            "90",
            "--wait-interval",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert calls == [("model", tmp_path / "env", True, True, 90, 2)]


def test_teardown_command_passes_delete_flags(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("stelarctl.cli._resolve_target", lambda env, context_name, namespace: ("minikube", "stelar-dev"))
    monkeypatch.setattr(
        "stelarctl.cli.teardown_target",
        lambda context_name, namespace, env_path=None, delete_namespace=False, delete_env=False, auto_approve=False: calls.append(
            (context_name, namespace, env_path, delete_namespace, delete_env, auto_approve)
        ),
    )

    result = runner.invoke(
        app,
        ["teardown", "--env", str(tmp_path / "env"), "--delete-namespace", "--delete-env", "--yes"],
    )

    assert result.exit_code == 0
    assert calls == [("minikube", "stelar-dev", tmp_path / "env", True, True, True)]


def test_validate_command_renders_model_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "stelarctl.cli._load",
        lambda path: _obj(platform="minikube", tier="core", namespace="stelar-dev"),
    )

    result = runner.invoke(app, ["validate", str(tmp_path / "model.yaml")])

    assert result.exit_code == 0
    assert "Model valid: platform=minikube, tier=core, namespace=stelar-dev" in result.stdout


def test_generate_command_writes_main_jsonnet(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr("stelarctl.cli._load", lambda path: "model")
    monkeypatch.setattr("stelarctl.cli.write_main_jsonnet", lambda model, env: calls.append((model, env)))

    result = runner.invoke(app, ["generate", str(tmp_path / "model.yaml"), "--env", str(tmp_path / "env")])

    assert result.exit_code == 0
    assert calls == [("model", str(tmp_path / "env"))]


def test_render_bar_clamps_values():
    assert render_bar(120, width=10) == "[##########] 100%"
    assert render_bar(-5, width=10) == "[----------] 0%"


def test_calculate_progress_handles_zero_expected_resources():
    assert calculate_progress(0, 0, 0, 0) == 100


def test_derive_phase_reports_nearly_ready():
    phase = derive_phase(
        80,
        [SimpleNamespace(completed=False, failed=False)],
        [SimpleNamespace(ready=False)],
        [],
    )

    assert phase == "Nearly Ready"


def test_format_status_includes_blockers():
    snapshot = _obj(
        context="minikube",
        namespace="stelar-dev",
        tier="core",
        overall_percent=58,
        jobs_completed=1,
        jobs_total=3,
        components_ready=6,
        components_total=8,
        phase="Progressing",
        blockers=["API Init: job still running", "CKAN: 0/1 ready"],
    )

    rendered = format_status(snapshot)

    assert "Status: Progressing 58%" in rendered
    assert "Blocking:" in rendered
    assert "- API Init: job still running" in rendered


def test_collect_inferred_status_returns_warnings_when_inactive(monkeypatch):
    monkeypatch.setattr(
        "stelarctl.status.infer_live_deployment",
        lambda context, namespace: _obj(active=False, model=None, warnings=["missing namespace"]),
    )

    snapshot, warnings = collect_inferred_status("minikube", "missing")

    assert snapshot is None
    assert warnings == ["missing namespace"]


def test_deployment_status_reports_unobserved_generation():
    resource = ExpectedResource("deployment", "stelarapi", "STELAR API")
    deployment = _obj(
        metadata=_obj(generation=2),
        spec=_obj(replicas=1),
        status=_obj(observed_generation=1, ready_replicas=0, updated_replicas=0, available_replicas=0),
    )

    status = _deployment_status(resource, deployment)

    assert status.ready is False
    assert "controller has not observed" in status.detail


def test_component_status_reports_missing_statefulset():
    resource = ExpectedResource("statefulset", "solr", "Solr")

    status = _component_status(resource, {}, {})

    assert status.ready is False
    assert status.detail == "missing statefulset"


def test_statefulset_status_reports_ready():
    resource = ExpectedResource("statefulset", "solr", "Solr")
    statefulset = _obj(
        metadata=_obj(generation=1),
        spec=_obj(replicas=1),
        status=_obj(observed_generation=1, ready_replicas=1, updated_replicas=1),
    )

    status = _statefulset_status(resource, statefulset)

    assert status.ready is True
    assert status.detail == "ready"


def test_job_status_covers_missing_running_pending_and_complete():
    resource = ExpectedResource("job", "apiinit", "API Init")
    complete_job = _obj(
        spec=_obj(completions=1),
        status=_obj(
            conditions=[_obj(type="Complete", status="True")],
            failed=0,
            succeeded=1,
            active=0,
        ),
    )
    running_job = _obj(
        spec=_obj(completions=1),
        status=_obj(conditions=[], failed=0, succeeded=0, active=1),
    )
    pending_job = _obj(
        spec=_obj(completions=1),
        status=_obj(conditions=[], failed=0, succeeded=0, active=0),
    )

    assert _job_status(resource, {}).detail == "missing job"
    assert _job_status(resource, {"apiinit": running_job}).detail == "job still running"
    assert _job_status(resource, {"apiinit": pending_job}).detail == "job pending"
    assert _job_status(resource, {"apiinit": complete_job}).completed is True


def test_pod_failures_filters_known_failure_reasons():
    pods = [
        _obj(
            metadata=_obj(name="stelarapi-abc"),
            status=_obj(
                container_statuses=[
                    _obj(state=_obj(waiting=_obj(reason="ImagePullBackOff"))),
                    _obj(state=_obj(waiting=_obj(reason="ContainerCreating"))),
                ]
            ),
        )
    ]

    failures = _pod_failures(pods)

    assert failures == ["Pod stelarapi-abc: ImagePullBackOff"]
