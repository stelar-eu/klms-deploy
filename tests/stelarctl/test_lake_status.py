import json

import pytest
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from stelar.deploy.cli import app
from stelar.deploy.operations import CommandError, add_lake_environment, inspect_lake_status
from stelar.deploy.operations.bootstrap_state import product_sha256, target_sha256
from stelar.deploy.operations import lake_status as status_commands


runner = CliRunner()


def make_workspace(path: Path) -> Path:
    path.mkdir()
    (path / "jsonnetfile.json").write_text("{}\n", encoding="utf-8")
    template_dir = (
        path
        / "vendor"
        / "github.com"
        / "stelar-eu"
        / "klms-deploy"
        / "lib"
        / "environment_templates"
    )
    template_dir.mkdir(parents=True)
    (template_dir / "main_template.jsonnet").write_text(
        'local build_lake = import "github.com/stelar-eu/klms-deploy/lib/util/build_lake.libsonnet";\n'
        'local environment_spec = import "./spec.json";\n'
        '\n'
        'build_lake(environment_spec)\n',
        encoding="utf-8",
    )
    return path


def write_status_environment(workspace: Path, fullspec: dict) -> Path:
    add_lake_environment("dev", workspace)
    environment_dir = workspace / "dev"
    spec = {
        "apiVersion": "tanka.dev/v1alpha1",
        "metadata": {"annotations": {"stelar.eu/lake-environment": "true"}},
        "spec": {
            "contextNames": ["current-context"],
            "namespace": "test",
            "stelar": {"active_product": fullspec},
        },
    }
    (environment_dir / "spec.json").write_text(
        f"{json.dumps(spec)}\n",
        encoding="utf-8",
    )
    return environment_dir


def base_fullspec(*, core_components=None, optional_components=None, cluster=None) -> dict:
    return {
        "klms": {
            "core_components": list(core_components or []),
            "optional_components": list(optional_components or []),
            "cluster": list(cluster or []),
            "support": ["ingress"],
            "SCHEME": "http",
            "ingress": {"tls": ["no_tls"], "no_tls": {}},
            "postgres": {
                "POSTGRES_DB_PASSWORD_SECRET_NAME": "product-postgres-secret",
                "POSTGRES_DB_PASSWORD": "postgres-password",
                "CKAN_DB_PASSWORD_SECRET_NAME": "product-ckan-db-secret",
                "CKAN_DB_PASSWORD": "ckan-password",
                "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "product-keycloak-db-secret",
                "KEYCLOAK_DB_PASSWORD": "keycloak-db-password",
                "DATASTORE_DB_PASSWORD_SECRET_NAME": "product-datastore-secret",
                "DATASTORE_DB_PASSWORD": "datastore-password",
                "QUAY_DB_PASSWORD_SECRET_NAME": "product-quay-db-secret",
                "QUAY_DB_PASSWORD": "quay-password",
            },
            "keycloak": {
                "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "product-keycloak-root-secret",
                "KEYCLOAK_ROOT_PASSWORD": "keycloak-root-password",
            },
            "api": {
                "SMTP_PASSWORD_SECRET_NAME": "product-smtp-secret",
                "SMTP_PASSWORD": "smtp-password",
                "SESSION_SECRET_KEY_SECRET_NAME": "product-session-secret",
                "SESSION_SECRET_KEY": "session-secret-value",
            },
            "ckan": {
                "CKAN_ADMIN_PASSWORD_SECRET_NAME": "product-ckan-admin-secret",
                "CKAN_ADMIN_PASSWORD": "ckan-admin-password",
            },
            "minio": {
                "MINIO_ROOT_USER": "minioadmin",
                "MINIO_ROOT_PASSWORD_SECRET_NAME": "product-minio-root-secret",
                "MINIO_ROOT_PASSWORD": "minio-root-password",
                "INSECURE_MC_CLIENT": "true",
            },
        }
    }


def set_bootstrapped_product(
    environment_dir: Path,
    *,
    context: str = "current-context",
    namespace: str = "test",
    secret_names: tuple[str, ...] = ("stored-secret",),
) -> None:
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    stelar_spec = spec["spec"].setdefault("stelar", {})
    stelar_spec["bootstrapped_product"] = {
        "target_sha256": target_sha256(context, namespace),
        "product_sha256": product_sha256(stelar_spec["active_product"]),
        "secret_names": list(secret_names),
        "bootstrapped_at": "2026-06-07T00:00:00Z",
    }
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")


def expected_secret_names(fullspec: dict) -> set[str]:
    klms = fullspec["klms"]
    return {
        klms["postgres"]["POSTGRES_DB_PASSWORD_SECRET_NAME"],
        klms["postgres"]["CKAN_DB_PASSWORD_SECRET_NAME"],
        klms["postgres"]["KEYCLOAK_DB_PASSWORD_SECRET_NAME"],
        klms["postgres"]["DATASTORE_DB_PASSWORD_SECRET_NAME"],
        klms["postgres"]["QUAY_DB_PASSWORD_SECRET_NAME"],
        klms["keycloak"]["KEYCLOAK_ROOT_PASSWORD_SECRET_NAME"],
        klms["api"]["SMTP_PASSWORD_SECRET_NAME"],
        klms["api"]["SESSION_SECRET_KEY_SECRET_NAME"],
        klms["ckan"]["CKAN_ADMIN_PASSWORD_SECRET_NAME"],
        klms["minio"]["MINIO_ROOT_PASSWORD_SECRET_NAME"],
        "ckan-auth-secret",
    }


def set_status_cluster(
    monkeypatch,
    *,
    existing_secrets=None,
    deployments=None,
    statefulsets=None,
    jobs=None,
    missing=None,
):
    existing_secrets = set(existing_secrets or ())
    deployments = dict(deployments or {})
    statefulsets = dict(statefulsets or {})
    jobs = {name: list(values) for name, values in dict(jobs or {}).items()}
    calls = {"secrets": [], "deployments": [], "statefulsets": [], "jobs": []}

    def not_found():
        raise status_commands.ApiException(status=404, reason="Not Found")

    def forbidden():
        raise status_commands.ApiException(status=403, reason="Forbidden")

    def load_kube_config(*, context):
        calls["context"] = context

    def list_kube_config_contexts():
        return ([{"name": "current-context", "context": {"namespace": "test"}}], {"name": "current-context"})

    class CoreV1Api:
        def read_namespaced_secret(self, name, namespace):
            calls["secrets"].append((namespace, name))
            if missing == "secret_forbidden":
                forbidden()
            if name not in existing_secrets:
                not_found()
            return SimpleNamespace(metadata=SimpleNamespace(name=name))

    class AppsV1Api:
        def read_namespaced_deployment_status(self, name, namespace):
            calls["deployments"].append((namespace, name))
            if missing == "deployment_forbidden":
                forbidden()
            if name not in deployments:
                not_found()
            return workload_status(*deployments[name])

        def read_namespaced_stateful_set_status(self, name, namespace):
            calls["statefulsets"].append((namespace, name))
            if name not in statefulsets:
                not_found()
            return workload_status(*statefulsets[name])

    class BatchV1Api:
        def read_namespaced_job_status(self, name, namespace):
            calls["jobs"].append((namespace, name))
            if name not in jobs or not jobs[name]:
                not_found()
            value = jobs[name].pop(0)
            if not jobs[name]:
                jobs[name].append(value)
            return job_status(value)

    monkeypatch.setattr(status_commands.kube_config, "load_kube_config", load_kube_config)
    monkeypatch.setattr(status_commands.kube_config, "list_kube_config_contexts", list_kube_config_contexts)
    monkeypatch.setattr(status_commands.kube_client, "CoreV1Api", CoreV1Api)
    monkeypatch.setattr(status_commands.kube_client, "AppsV1Api", AppsV1Api)
    monkeypatch.setattr(status_commands.kube_client, "BatchV1Api", BatchV1Api)
    return calls


def workload_status(ready: int, desired: int):
    return SimpleNamespace(
        spec=SimpleNamespace(replicas=desired),
        status=SimpleNamespace(ready_replicas=ready, available_replicas=ready),
    )


def job_status(state: str):
    if state == "complete":
        return SimpleNamespace(
            status=SimpleNamespace(
                succeeded=1,
                active=0,
                failed=0,
                conditions=[SimpleNamespace(type="Complete", status="True")],
            )
        )
    if state == "failed":
        return SimpleNamespace(
            status=SimpleNamespace(
                succeeded=0,
                active=0,
                failed=1,
                conditions=[SimpleNamespace(type="Failed", status="True")],
            )
        )
    return SimpleNamespace(
        status=SimpleNamespace(succeeded=0, active=1, failed=0, conditions=[])
    )


def test_lake_status_reports_bootstrap_and_selected_workloads(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis", "postgres", "api"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1), "stelarapi": (1, 1)},
        statefulsets={"db": (1, 1)},
        jobs={"apiinit": ["complete"]},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.bootstrap.state == "bootstrapped"
    assert status.deployment.state == "deployed"
    assert status.selected_components == ("system", "redis", "postgres", "api")
    assert {(item.kind, item.name, item.state) for item in status.deployment.workloads} == {
        ("Deployment", "redis", "ready"),
        ("StatefulSet", "db", "ready"),
        ("Deployment", "stelarapi", "ready"),
        ("Job", "apiinit", "complete"),
    }
    assert status.deployment.unchecked_components[0].component == "system"


def test_lake_status_uses_stored_bootstrap_secret_names(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        secret_names=("old-postgres-secret", "old-auth-secret"),
    )
    calls = set_status_cluster(
        monkeypatch,
        existing_secrets={"old-postgres-secret", "old-auth-secret"},
        deployments={"redis": (1, 1)},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.bootstrap.expected == ("old-postgres-secret", "old-auth-secret")
    assert status.bootstrap.state == "bootstrapped"
    assert calls["secrets"] == [
        ("test", "old-postgres-secret"),
        ("test", "old-auth-secret"),
    ]



def test_lake_status_reports_bootstrap_product_hash_mismatch(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        secret_names=("old-postgres-secret", "old-auth-secret"),
    )
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["stelar"]["active_product"] = base_fullspec(core_components=["postgres"])
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    calls = set_status_cluster(
        monkeypatch,
        existing_secrets={"old-postgres-secret", "old-auth-secret"},
        statefulsets={"db": (1, 1)},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.bootstrap.expected == ("old-postgres-secret", "old-auth-secret")
    assert status.bootstrap.state == "bootstrapped"
    assert status.deployment.state == "deployed"
    assert [
        (workload.kind, workload.name, workload.state)
        for workload in status.deployment.workloads
    ] == [("StatefulSet", "db", "ready")]
    assert calls["secrets"] == [
        ("test", "old-postgres-secret"),
        ("test", "old-auth-secret"),
    ]
    assert len(status.diagnostics) == 1
    assert "Active product does not match" in status.diagnostics[0]
    assert "purge-secrets" in status.diagnostics[0]


def test_lake_status_rejects_invalid_active_product_scheme_tls(
    tmp_path,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    fullspec["klms"]["SCHEME"] = "https"
    fullspec["klms"]["ingress"] = {"tls": ["no_tls"], "no_tls": {}}
    write_status_environment(workspace, fullspec)

    with pytest.raises(CommandError, match="SCHEME https.*manual_tls"):
        inspect_lake_status("dev", workspace, job_timeout_seconds=0)


def test_lake_status_rejects_recorded_bootstrap_state_with_missing_target_fields_even_with_flags(
    tmp_path,
):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = write_status_environment(workspace, base_fullspec())
    set_bootstrapped_product(environment_dir)
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["stelar"]["active_product"]["klms"]["SCHEME"] = "ftp"
    del spec["spec"]["contextNames"]
    del spec["spec"]["namespace"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")

    with pytest.raises(CommandError, match="recorded bootstrap state"):
        inspect_lake_status(
            "dev",
            workspace,
            context="current-context",
            namespace="test",
            job_timeout_seconds=0,
        )


def test_lake_status_rejects_bootstrap_target_overrides_after_bootstrap(
    tmp_path,
):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = write_status_environment(workspace, base_fullspec())
    set_bootstrapped_product(environment_dir)

    with pytest.raises(CommandError, match="overrides are not allowed"):
        inspect_lake_status(
            "dev",
            workspace,
            context="current-context",
            namespace="test",
            job_timeout_seconds=0,
        )


def test_lake_status_rejects_bootstrap_target_hash_mismatch(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        namespace="old-namespace",
        secret_names=("old-secret",),
    )
    set_status_cluster(monkeypatch)

    with pytest.raises(CommandError, match="Hash mismatch detected"):
        inspect_lake_status("dev", workspace, job_timeout_seconds=0)


def test_lake_status_checks_target_hash_before_resolving_context(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    set_bootstrapped_product(environment_dir, secret_names=("old-secret",))
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["contextNames"] = ["missing-context"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_status_cluster(monkeypatch)

    with pytest.raises(CommandError, match="Hash mismatch detected"):
        inspect_lake_status("dev", workspace, job_timeout_seconds=0)


def test_lake_status_does_not_report_deployed_when_selected_components_are_unchecked(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(
        core_components=["redis"],
        optional_components=["airflow"],
    )
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1)},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    unchecked_components = {
        item.component for item in status.deployment.unchecked_components
    }
    assert "airflow" in unchecked_components
    assert status.deployment.state == "unchecked"


def test_lake_status_reports_partial_bootstrap_without_creating(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets={"product-postgres-secret"},
        deployments={"redis": (1, 1)},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.bootstrap.state == "partial"
    assert status.bootstrap.existing == ("product-postgres-secret",)
    assert "product-ckan-db-secret" in status.bootstrap.missing
    assert status.deployment.state == "deployed"


def test_lake_status_polls_failed_job_until_it_succeeds(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["api"])
    write_status_environment(workspace, fullspec)
    calls = set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"stelarapi": (1, 1)},
        jobs={"apiinit": ["failed", "complete"]},
    )
    monkeypatch.setattr(status_commands.time, "sleep", lambda _seconds: None)

    status = inspect_lake_status(
        "dev",
        workspace,
        job_timeout_seconds=1,
        poll_interval_seconds=0,
    )

    job = next(item for item in status.deployment.workloads if item.kind == "Job")
    assert job.state == "complete"
    assert calls["jobs"] == [("test", "apiinit"), ("test", "apiinit")]


def test_lake_status_reports_unknown_when_rbac_blocks_workload_reads(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        missing="deployment_forbidden",
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.deployment.state == "unknown"
    assert status.deployment.workloads[0].state == "unknown"
    assert "not authorized" in status.deployment.workloads[0].detail


def test_lake_status_cli_prints_status(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1)},
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Lake status: dev" in result.output
    assert "bootstrap: bootstrapped" in result.output
    assert "Deployment redis [redis]: ready" in result.output


def test_lake_status_cli_prints_product_mismatch_diagnostic(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        secret_names=("old-postgres-secret", "old-auth-secret"),
    )
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["stelar"]["active_product"] = base_fullspec(core_components=["postgres"])
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_status_cluster(
        monkeypatch,
        existing_secrets={"old-postgres-secret", "old-auth-secret"},
        statefulsets={"db": (1, 1)},
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "diagnostic: Bad environment state" in result.output
    assert "Active product does not match" in result.output
    assert "stelarctl lake purge-secrets ENV" in result.output
    assert "bootstrap: bootstrapped" in result.output
    assert "StatefulSet db [postgres]: ready" in result.output


def test_lake_status_cli_rejects_polling_options_without_wait(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1)},
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
            "--job-timeout",
            "30",
        ],
    )

    assert result.exit_code != 0
    assert "only valid with --wait" in result.output


def test_lake_status_cli_requires_polling_options_with_wait(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1)},
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
            "--wait",
        ],
    )

    assert result.exit_code != 0
    assert "--wait requires both --job-timeout" in result.output


def test_lake_status_cli_rejects_zero_poll_interval_with_wait(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["api"])
    write_status_environment(workspace, fullspec)
    set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"stelarapi": (1, 1)},
        jobs={"apiinit": ["complete"]},
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
            "--wait",
            "--job-timeout",
            "1",
            "--poll-interval",
            "0",
        ],
    )

    assert result.exit_code != 0
    assert "--poll-interval must be greater than 0" in result.output


def test_lake_status_cli_accepts_wait_with_polling_options(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["api"])
    write_status_environment(workspace, fullspec)
    calls = set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"stelarapi": (1, 1)},
        jobs={"apiinit": ["failed", "complete"]},
    )
    monkeypatch.setattr(status_commands.time, "sleep", lambda _seconds: None)

    result = runner.invoke(
        app,
        [
            "lake",
            "status",
            "dev",
            "--workspace",
            str(workspace),
            "--wait",
            "--job-timeout",
            "1",
            "--poll-interval",
            "0.01",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Job apiinit [api]: complete" in result.output
    assert calls["jobs"] == [("test", "apiinit"), ("test", "apiinit")]

