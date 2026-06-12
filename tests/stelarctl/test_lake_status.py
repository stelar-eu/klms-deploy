import json

import pytest
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from stelar.deploy.cli import app
from stelar.deploy.operations import CommandError, add_lake_environment, inspect_lake_status
from stelar.deploy.operations import lake_status as status_commands


runner = CliRunner()
CURRENT_STATUS_FULLSPEC = None


def make_workspace(path: Path) -> Path:
    path.mkdir()
    (path / "jsonnetfile.json").write_text("{}\n", encoding="utf-8")
    template_dir = path / "vendor" / "lib" / "environment_templates"
    template_dir.mkdir(parents=True)
    (template_dir / "main_template.jsonnet").write_text(
        'local build_lake = import "lib/util/build_lake.libsonnet";\n'
        'local environment_spec = import "./spec.json";\n'
        '\n'
        'build_lake(environment_spec)\n',
        encoding="utf-8",
    )
    return path


def write_status_environment(workspace: Path, fullspec: dict) -> Path:
    global CURRENT_STATUS_FULLSPEC
    CURRENT_STATUS_FULLSPEC = fullspec
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
                "CKAN_DB_PASSWORD_SECRET_NAME": "product-ckan-db-secret",
                "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "product-keycloak-db-secret",
                "DATASTORE_DB_PASSWORD_SECRET_NAME": "product-datastore-secret",
                "QUAY_DB_PASSWORD_SECRET_NAME": "product-quay-db-secret",
            },
            "keycloak": {
                "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "product-keycloak-root-secret",
            },
            "api": {
                "SMTP_PASSWORD_SECRET_NAME": "product-smtp-secret",
                "SESSION_SECRET_KEY_SECRET_NAME": "product-session-secret",
            },
            "ckan": {
                "CKAN_ADMIN_PASSWORD_SECRET_NAME": "product-ckan-admin-secret",
                "CKAN_AUTH_SECRET_NAME": "product-ckan-auth-secret",
            },
            "minio": {
                "MINIO_ROOT_USER": "minioadmin",
                "MINIO_ROOT_PASSWORD_SECRET_NAME": "product-minio-root-secret",
                "INSECURE_MC_CLIENT": "true",
            },
        }
    }


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
        klms["ckan"]["CKAN_AUTH_SECRET_NAME"],
    }


def set_status_cluster(
    monkeypatch,
    *,
    existing_secrets=None,
    deployments=None,
    statefulsets=None,
    jobs=None,
    missing=None,
    lake_state_fullspec="current",
):
    existing_secrets = set(existing_secrets or ())
    if lake_state_fullspec == "current":
        lake_state_fullspec = CURRENT_STATUS_FULLSPEC
    deployments = dict(deployments or {})
    statefulsets = dict(statefulsets or {})
    jobs = {name: list(values) for name, values in dict(jobs or {}).items()}
    calls = {"secrets": [], "deployments": [], "statefulsets": [], "jobs": [], "configmaps": []}

    def not_found():
        raise status_commands.ApiException(status=404, reason="Not Found")

    def forbidden():
        raise status_commands.ApiException(status=403, reason="Forbidden")

    def load_kube_config(*, context):
        calls["context"] = context

    def list_kube_config_contexts():
        return ([{"name": "current-context", "context": {"namespace": "test"}}], {"name": "current-context"})

    class CoreV1Api:
        def read_namespaced_config_map(self, name, namespace):
            calls["configmaps"].append((namespace, name))
            if missing == "lake_state_forbidden":
                forbidden()
            if lake_state_fullspec is None:
                not_found()
            return SimpleNamespace(
                data={
                    "product_name": "generated",
                    "product_filename": "generated.json",
                    "fullspec.json": json.dumps(lake_state_fullspec),
                }
            )

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


def test_lake_status_uses_configmap_fullspec_when_local_active_product_differs(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    environment_dir = write_status_environment(workspace, fullspec)
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["stelar"]["active_product"] = base_fullspec(core_components=["postgres"])
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    calls = set_status_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        deployments={"redis": (1, 1)},
    )

    status = inspect_lake_status("dev", workspace, job_timeout_seconds=0)

    assert status.selected_components == ("system", "redis")
    assert status.bootstrap.state == "bootstrapped"
    assert status.deployment.state == "deployed"
    assert status.diagnostics == ("cluster product: generated",)
    assert calls["secrets"] == [("test", name) for name in status.bootstrap.expected]


def test_lake_status_rejects_invalid_active_product_scheme_tls(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec(core_components=["redis"])
    fullspec["klms"]["SCHEME"] = "https"
    fullspec["klms"]["ingress"] = {"tls": ["no_tls"], "no_tls": {}}
    write_status_environment(workspace, fullspec)
    set_status_cluster(monkeypatch)

    with pytest.raises(CommandError, match="SCHEME https.*manual_tls"):
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

