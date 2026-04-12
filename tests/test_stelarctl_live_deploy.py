from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "bin" / "stelarctl"
LIVE_TIMEOUT_SECONDS = 600
LIVE_POLL_INTERVAL_SECONDS = 5


def _run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [str(CLI), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def _wait_for_inactive(context_name: str, namespace: str, timeout_seconds: int = 120) -> str:
    deadline = time.time() + timeout_seconds
    latest_output = ""
    while time.time() < deadline:
        result = _run_cli("status", "--context", context_name, "--namespace", namespace)
        latest_output = result.stdout
        if f"No active STELAR deployment found in {context_name}/{namespace}." in latest_output:
            return latest_output
        time.sleep(2)
    pytest.fail(f"Timed out waiting for inactive status.\nLast output:\n{latest_output}")


@pytest.mark.skipif(
    os.environ.get("STELARCTL_RUN_LIVE_TESTS") != "1",
    reason="Set STELARCTL_RUN_LIVE_TESTS=1 to run live minikube deployment tests.",
)
def test_live_deploy_status_redeploy_and_teardown(tmp_path: Path):
    source_model_path = REPO_ROOT / "stelarctl" / "example_models" / "minikube.yaml"
    source_model = yaml.safe_load(source_model_path.read_text(encoding="utf-8"))

    unique_suffix = uuid.uuid4().hex[:8]
    namespace = f"stelar-live-{unique_suffix}"
    env_path = REPO_ROOT / "environments" / ".live-tests" / f"env-{unique_suffix}"
    model_path = tmp_path / "model.yaml"

    source_model["namespace"] = namespace
    model_path.write_text(yaml.safe_dump(source_model, sort_keys=False), encoding="utf-8")

    context_name = source_model["k8s_context"]

    try:
        validate = _run_cli("validate", str(model_path))
        assert "Model valid:" in validate.stdout

        deploy = _run_cli(
            "deploy",
            str(model_path),
            "--env",
            str(env_path),
            "--yes",
            "--wait",
            "--wait-timeout",
            str(LIVE_TIMEOUT_SECONDS),
            "--wait-interval",
            str(LIVE_POLL_INTERVAL_SECONDS),
        )
        assert "Stored deployment model written to" in deploy.stdout
        assert "Deployment reached Ready 100%." in deploy.stdout
        assert (env_path / "model.yaml").exists()

        ready_status = _run_cli("status", "--context", context_name, "--namespace", namespace).stdout
        assert "Jobs: 3/3 completed" in ready_status
        assert "Components: 8/8 ready" in ready_status

        redeploy = _run_cli("deploy", str(model_path), "--env", str(env_path), "--yes")
        assert "Input model matches the active deployment. No changes to apply." in redeploy.stdout

        status_via_env = _run_cli("status", "--env", str(env_path))
        assert "Status: Ready 100%" in status_via_env.stdout
    finally:
        _run_cli(
            "teardown",
            "--context",
            context_name,
            "--namespace",
            namespace,
            "--env",
            str(env_path),
            "--delete-namespace",
            "--delete-env",
            "--yes",
            check=False,
        )
        _wait_for_inactive(context_name, namespace)
