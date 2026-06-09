import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from stelar.deploy.cli import app
from stelar.deploy.operations import CommandError, add_lake_environment
from stelar.deploy.operations import lake_secret_purge as purge_commands
from stelar.deploy.operations.bootstrap_state import product_sha256, target_sha256
from stelar.deploy.operations import plan_lake_secret_purge, purge_lake_secrets


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
        "\n"
        "build_lake(environment_spec)\n",
        encoding="utf-8",
    )
    return path


def write_purge_environment(workspace: Path, fullspec: dict) -> Path:
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


def base_fullspec() -> dict:
    return {
        "klms": {
            "core_components": ["redis"],
            "optional_components": [],
            "cluster": [],
            "support": ["ingress"],
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
                "MINIO_ROOT_PASSWORD_SECRET_NAME": "product-minio-root-secret",
                "MINIO_ROOT_PASSWORD": "minio-root-password",
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


def add_manual_tls(fullspec: dict) -> dict:
    fullspec["klms"]["ingress"] = {
        "tls": ["manual_tls"],
        "manual_tls": {
            "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
            "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
            "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
            "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
        },
    }
    return fullspec


def set_secret_cluster(monkeypatch, *, existing_secrets=None, missing=None):
    existing_secrets = set(existing_secrets or ())
    calls = {"deleted": []}

    def not_found():
        raise purge_commands.ApiException(status=404, reason="Not Found")

    def forbidden():
        raise purge_commands.ApiException(status=403, reason="Forbidden")

    def load_kube_config(*, context):
        calls["context"] = context

    def list_kube_config_contexts():
        return (
            [{"name": "current-context", "context": {"namespace": "test"}}],
            {"name": "current-context"},
        )

    class CoreV1Api:
        def delete_namespaced_secret(self, name, namespace):
            calls["deleted"].append((namespace, name))
            if missing == "delete_forbidden":
                forbidden()
            if missing == "delete_error":
                raise purge_commands.ApiException(status=500, reason="Server Error")
            if name not in existing_secrets:
                not_found()
            existing_secrets.remove(name)
            return SimpleNamespace(metadata=SimpleNamespace(name=name))

    monkeypatch.setattr(purge_commands.kube_config, "load_kube_config", load_kube_config)
    monkeypatch.setattr(
        purge_commands.kube_config,
        "list_kube_config_contexts",
        list_kube_config_contexts,
    )
    monkeypatch.setattr(purge_commands.kube_client, "CoreV1Api", CoreV1Api)
    return calls


def test_plan_lake_secret_purge_uses_active_fullspec_target(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_purge_environment(workspace, fullspec)
    set_secret_cluster(monkeypatch)

    plan = plan_lake_secret_purge("dev", workspace)

    assert plan.context == "current-context"
    assert plan.namespace == "test"
    assert set(plan.secret_names) == expected_secret_names(fullspec)


def test_plan_lake_secret_purge_uses_stored_bootstrap_secret_names(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_purge_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        secret_names=("old-postgres-secret", "old-auth-secret"),
    )
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    del spec["spec"]["stelar"]["active_product"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_secret_cluster(monkeypatch)

    plan = plan_lake_secret_purge("dev", workspace)

    assert plan.secret_names == ("old-postgres-secret", "old-auth-secret")




def test_plan_lake_secret_purge_rejects_recorded_bootstrap_state_with_missing_target_fields_even_with_flags(
    tmp_path,
):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = write_purge_environment(workspace, base_fullspec())
    set_bootstrapped_product(environment_dir)
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    del spec["spec"]["contextNames"]
    del spec["spec"]["namespace"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")

    with pytest.raises(CommandError, match="recorded bootstrap state"):
        plan_lake_secret_purge(
            "dev",
            workspace,
            context="current-context",
            namespace="test",
        )


def test_plan_lake_secret_purge_rejects_bootstrap_target_overrides_after_bootstrap(
    tmp_path,
):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = write_purge_environment(workspace, base_fullspec())
    set_bootstrapped_product(environment_dir)

    with pytest.raises(CommandError, match="overrides are not allowed"):
        plan_lake_secret_purge(
            "dev",
            workspace,
            context="current-context",
            namespace="test",
        )


def test_plan_lake_secret_purge_rejects_bootstrap_target_hash_mismatch(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_purge_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        namespace="old-namespace",
        secret_names=("old-secret",),
    )
    set_secret_cluster(monkeypatch)

    with pytest.raises(CommandError, match="Hash mismatch detected"):
        plan_lake_secret_purge("dev", workspace)


def test_plan_lake_secret_purge_checks_target_hash_before_resolving_context(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = write_purge_environment(workspace, base_fullspec())
    set_bootstrapped_product(environment_dir, secret_names=("old-secret",))
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"]["contextNames"] = ["missing-context"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_secret_cluster(monkeypatch)

    with pytest.raises(CommandError, match="Hash mismatch detected"):
        plan_lake_secret_purge("dev", workspace)


def test_purge_lake_secrets_allows_product_mismatch_and_clears_recorded_state(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_purge_environment(workspace, fullspec)
    set_bootstrapped_product(
        environment_dir,
        secret_names=("old-postgres-secret", "old-auth-secret"),
    )
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    replacement_fullspec = base_fullspec()
    replacement_fullspec["klms"]["ROOT_DOMAIN"] = "replacement.example"
    spec["spec"]["stelar"]["active_product"] = replacement_fullspec
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_secret_cluster(
        monkeypatch,
        existing_secrets={"old-postgres-secret", "old-auth-secret"},
    )

    result = purge_lake_secrets(plan_lake_secret_purge("dev", workspace))

    assert result.deleted == ("old-postgres-secret", "old-auth-secret")
    stelar_spec = json.loads(spec_path.read_text(encoding="utf-8"))["spec"]["stelar"]
    assert "bootstrapped_product" not in stelar_spec


def test_purge_lake_secrets_deletes_existing_and_skips_missing(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_purge_environment(workspace, fullspec)
    existing = {"product-postgres-secret", "ckan-auth-secret"}
    calls = set_secret_cluster(monkeypatch, existing_secrets=existing)

    plan = plan_lake_secret_purge("dev", workspace)
    result = purge_lake_secrets(plan)

    assert result.deleted == ("product-postgres-secret", "ckan-auth-secret")
    assert "product-ckan-db-secret" in result.missing
    assert calls["context"] == "current-context"
    assert ("test", "product-postgres-secret") in calls["deleted"]


def test_purge_lake_secrets_includes_manual_tls_names(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = add_manual_tls(base_fullspec())
    write_purge_environment(workspace, fullspec)
    existing = expected_secret_names(fullspec) | {
        "klms-manual-tls",
        "kc-manual-tls",
        "minio-manual-tls",
        "img-manual-tls",
    }
    set_secret_cluster(monkeypatch, existing_secrets=existing)

    result = purge_lake_secrets(plan_lake_secret_purge("dev", workspace))

    assert "klms-manual-tls" in result.deleted
    assert "kc-manual-tls" in result.deleted
    assert "minio-manual-tls" in result.deleted
    assert "img-manual-tls" in result.deleted


def test_purge_lake_secrets_reports_forbidden_delete(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_purge_environment(workspace, fullspec)
    set_secret_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        missing="delete_forbidden",
    )

    plan = plan_lake_secret_purge("dev", workspace)
    with pytest.raises(CommandError, match="not authorized to delete Secret"):
        purge_lake_secrets(plan)


def test_lake_purge_secrets_cli_deletes_with_yes(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_purge_environment(workspace, fullspec)
    set_secret_cluster(monkeypatch, existing_secrets=expected_secret_names(fullspec))

    result = runner.invoke(
        app,
        [
            "lake",
            "purge-secrets",
            "dev",
            "--workspace",
            str(workspace),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Lake secret purge: dev" in result.output
    assert "deleted secrets:" in result.output
    assert "already missing secrets: (none)" in result.output


def test_lake_purge_secrets_cli_help_documents_scope():
    result = runner.invoke(app, ["lake", "purge-secrets", "--help"])

    assert result.exit_code == 0
    assert "tk delete ENV" in result.output
    assert "bootstrap Secrets" in result.output
    assert "--yes" in result.output
