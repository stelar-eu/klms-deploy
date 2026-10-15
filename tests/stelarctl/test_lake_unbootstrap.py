import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from stelar.deploy.cli import app
from stelar.deploy.operations import CommandError, add_lake_environment
from stelar.deploy.operations import lake_unbootstrap as unbootstrap_commands
from stelar.deploy.operations import plan_lake_unbootstrap, unbootstrap_lake
from stelar.deploy.operations.cluster import bootstrap_lake
from stelar.deploy.operations.secret_resources import BOOTSTRAP_SECRET_LABELS


runner = CliRunner()
CURRENT_UNBOOTSTRAP_FULLSPEC = None


def make_workspace(path: Path) -> Path:
    path.mkdir()
    (path / "jsonnetfile.json").write_text("{}\n", encoding="utf-8")
    template_dir = path / "vendor" / "lib" / "environment_templates"
    template_dir.mkdir(parents=True)
    (template_dir / "main_template.jsonnet").write_text(
        'local build_lake = import "lib/util/build_lake.libsonnet";\n'
        'local environment_spec = import "./spec.json";\n'
        "\n"
        "build_lake(environment_spec)\n",
        encoding="utf-8",
    )
    return path


def write_unbootstrap_environment(workspace: Path, fullspec: dict) -> Path:
    global CURRENT_UNBOOTSTRAP_FULLSPEC
    CURRENT_UNBOOTSTRAP_FULLSPEC = fullspec
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
                "MINIO_ROOT_PASSWORD_SECRET_NAME": "product-minio-root-secret",
            },
        }
    }


def bootstrap_ready_fullspec() -> dict:
    fullspec = base_fullspec()
    fullspec["klms"].update(
        SCHEME="http",
        dynamicStorageClass="standard",
        provisioning_storage_class="standard",
        ingress={"tls": ["no_tls"]},
    )
    fullspec["klms"]["minio"].update(
        MINIO_ROOT_USER="minioadmin",
        INSECURE_MC_CLIENT="true",
    )
    return fullspec


def set_bootstrapped_product(environment_dir: Path, **_ignored: object) -> None:
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"].setdefault("stelar", {})["bootstrapped_product"] = {"legacy": True}
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
        klms["ckan"]["CKAN_AUTH_SECRET_NAME"],
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


def set_secret_cluster(
    monkeypatch,
    *,
    existing_secrets=None,
    missing=None,
    lake_state_fullspec="current",
    labels_by_secret=None,
    metadata_overrides=None,
):
    existing_secrets = set(existing_secrets or ())
    secret_metadata = {
        name: {
            "name": name,
            "labels": dict((labels_by_secret or {}).get(name, BOOTSTRAP_SECRET_LABELS)),
            "uid": f"uid-{name}",
            "resource_version": "1",
            **(metadata_overrides or {}).get(name, {}),
        }
        for name in existing_secrets
    }
    if lake_state_fullspec == "current":
        lake_state_fullspec = CURRENT_UNBOOTSTRAP_FULLSPEC
    calls = {
        "deleted": [],
        "configmaps": [],
        "read_secrets": [],
        "delete_options": {},
        "created_secrets": [],
        "existing_secrets": existing_secrets,
        "secret_metadata": secret_metadata,
    }

    def not_found():
        raise unbootstrap_commands.ApiException(status=404, reason="Not Found")

    def forbidden():
        raise unbootstrap_commands.ApiException(status=403, reason="Forbidden")

    def load_kube_config(*, context):
        calls["context"] = context

    def list_kube_config_contexts():
        return (
            [{"name": "current-context", "context": {"namespace": "test"}}],
            {"name": "current-context"},
        )

    class CoreV1Api:
        def read_namespaced_secret(self, name, namespace):
            calls["read_secrets"].append((namespace, name))
            if missing == "secret_read_forbidden":
                forbidden()
            if missing == "secret_read_error":
                raise unbootstrap_commands.ApiException(status=500, reason="Server Error")
            if name not in existing_secrets:
                not_found()
            return SimpleNamespace(metadata=SimpleNamespace(**secret_metadata[name]))

        def create_namespaced_secret(self, *, namespace, body):
            name = body["metadata"]["name"]
            assert name not in existing_secrets
            calls["created_secrets"].append((namespace, name, body))
            existing_secrets.add(name)
            secret_metadata[name] = {
                **body["metadata"],
                "uid": f"uid-{name}",
                "resource_version": "1",
            }

        def create_namespaced_config_map(self, *, namespace, body):
            raise unbootstrap_commands.ApiException(status=500, reason="Server Error")

        def read_namespaced_config_map(self, name, namespace):
            calls["configmaps"].append(("read", namespace, name))
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

        def delete_namespaced_config_map(self, name, namespace):
            calls["configmaps"].append(("delete", namespace, name))
            if missing == "configmap_delete_forbidden":
                forbidden()
            if lake_state_fullspec is None:
                not_found()
            return SimpleNamespace(metadata=SimpleNamespace(name=name))

        def delete_namespaced_secret(self, name, namespace, *, body):
            calls["deleted"].append((namespace, name))
            calls["delete_options"][name] = body
            if missing == "delete_forbidden":
                forbidden()
            if missing == "delete_error":
                raise unbootstrap_commands.ApiException(status=500, reason="Server Error")
            if name not in existing_secrets:
                not_found()
            if missing == "secret_replaced":
                secret_metadata[name]["uid"] = f"replacement-{name}"
            if missing == "secret_relabeled":
                secret_metadata[name]["labels"] = {"owner": "another-app"}
                secret_metadata[name]["resource_version"] = "2"
            if (
                body.preconditions.uid != secret_metadata[name]["uid"]
                or body.preconditions.resource_version != secret_metadata[name]["resource_version"]
            ):
                raise unbootstrap_commands.ApiException(status=409, reason="Conflict")
            existing_secrets.remove(name)
            return SimpleNamespace(metadata=SimpleNamespace(name=name))

    monkeypatch.setattr(unbootstrap_commands.kube_config, "load_kube_config", load_kube_config)
    monkeypatch.setattr(
        unbootstrap_commands.kube_config,
        "list_kube_config_contexts",
        list_kube_config_contexts,
    )
    monkeypatch.setattr(unbootstrap_commands.kube_client, "CoreV1Api", CoreV1Api)
    return calls


def test_plan_lake_unbootstrap_uses_active_fullspec_target(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    set_secret_cluster(monkeypatch)

    plan = plan_lake_unbootstrap("dev", workspace)

    assert plan.context == "current-context"
    assert plan.namespace == "test"
    assert set(plan.secret_names) == expected_secret_names(fullspec)


def test_plan_lake_unbootstrap_uses_configmap_fullspec_without_active_product(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_unbootstrap_environment(workspace, fullspec)
    spec_path = environment_dir / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    del spec["spec"]["stelar"]["active_product"]
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")
    set_secret_cluster(monkeypatch)

    plan = plan_lake_unbootstrap("dev", workspace)

    assert set(plan.secret_names) == expected_secret_names(fullspec)
    assert plan.delete_state_configmap is True


def test_unbootstrap_lake_uses_configmap_fullspec_and_clears_legacy_state(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_unbootstrap_environment(workspace, fullspec)
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
        existing_secrets=expected_secret_names(fullspec),
    )

    result = unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert set(result.deleted) == expected_secret_names(fullspec)
    assert result.state_configmap_deleted is True
    stelar_spec = json.loads(spec_path.read_text(encoding="utf-8"))["spec"]["stelar"]
    assert "bootstrapped_product" not in stelar_spec


def test_unbootstrap_lake_deletes_existing_and_skips_missing(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    existing = {"product-postgres-secret", "product-ckan-auth-secret"}
    calls = set_secret_cluster(monkeypatch, existing_secrets=existing)

    plan = plan_lake_unbootstrap("dev", workspace)
    result = unbootstrap_lake(plan)

    assert result.deleted == ("product-postgres-secret", "product-ckan-auth-secret")
    assert "product-ckan-db-secret" in result.missing
    assert calls["context"] == "current-context"
    assert ("test", "product-postgres-secret") in calls["deleted"]
    options = calls["delete_options"]["product-postgres-secret"]
    assert options.preconditions.uid == "uid-product-postgres-secret"
    assert options.preconditions.resource_version == "1"
    assert ("test", "product-ckan-db-secret") not in calls["deleted"]


def test_unbootstrap_lake_includes_manual_tls_names(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = add_manual_tls(base_fullspec())
    write_unbootstrap_environment(workspace, fullspec)
    existing = expected_secret_names(fullspec) | {
        "klms-manual-tls",
        "kc-manual-tls",
        "minio-manual-tls",
        "img-manual-tls",
    }
    set_secret_cluster(monkeypatch, existing_secrets=existing)

    result = unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert "klms-manual-tls" in result.deleted
    assert "kc-manual-tls" in result.deleted
    assert "minio-manual-tls" in result.deleted
    assert "img-manual-tls" in result.deleted


def test_unbootstrap_lake_reports_forbidden_delete(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    set_secret_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        missing="delete_forbidden",
    )

    plan = plan_lake_unbootstrap("dev", workspace)
    with pytest.raises(CommandError, match="not authorized to delete Secret"):
        unbootstrap_lake(plan)


@pytest.mark.parametrize("has_state", [False, True])
@pytest.mark.parametrize(
    "labels",
    [
        {},
        {"app.kubernetes.io/managed-by": "stelarctl", "app.kubernetes.io/part-of": "stelar"},
        {**BOOTSTRAP_SECRET_LABELS, "app.kubernetes.io/managed-by": "another-app"},
        {**BOOTSTRAP_SECRET_LABELS, "stelar.eu/bootstrap-secret": "false"},
    ],
)
def test_unbootstrap_deletes_selected_secrets_regardless_of_labels(
    tmp_path, monkeypatch, has_state, labels,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_unbootstrap_environment(workspace, fullspec)
    set_bootstrapped_product(environment_dir)
    existing = {"product-postgres-secret", "product-ckan-auth-secret"}
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets=existing,
        labels_by_secret={"product-ckan-auth-secret": labels},
        lake_state_fullspec=fullspec if has_state else None,
    )

    result = unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert set(result.deleted) == existing
    assert calls["existing_secrets"] == set()
    assert any(action == "delete" for action, *_ in calls["configmaps"]) is has_state
    stelar_spec = json.loads(
        (environment_dir / "spec.json").read_text(encoding="utf-8")
    )["spec"]["stelar"]
    assert "bootstrapped_product" not in stelar_spec


def test_unbootstrap_deletes_selected_preexisting_secret_after_refused_bootstrap(
    tmp_path, monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = bootstrap_ready_fullspec()
    environment_dir = write_unbootstrap_environment(workspace, fullspec)
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets={"product-postgres-secret"},
        labels_by_secret={"product-postgres-secret": {"owner": "another-app"}},
        lake_state_fullspec=None,
    )

    with pytest.raises(CommandError, match="partial bootstrap"):
        bootstrap_lake("dev", workspace, preflight="skip")
    result = unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert calls["created_secrets"] == []
    assert result.deleted == ("product-postgres-secret",)
    assert calls["existing_secrets"] == set()


def test_failed_bootstrap_can_clean_up_its_owned_secrets_without_configmap(
    tmp_path, monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = bootstrap_ready_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    calls = set_secret_cluster(monkeypatch, lake_state_fullspec=None)

    # Simulate bootstrap failing at its final state ConfigMap write.
    with pytest.raises(CommandError, match="Could not create ConfigMap"):
        bootstrap_lake("dev", workspace, preflight="skip")
    assert calls["existing_secrets"] == expected_secret_names(fullspec)
    for _, _, body in calls["created_secrets"]:
        assert body["metadata"]["labels"] == BOOTSTRAP_SECRET_LABELS

    result = unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert set(result.deleted) == expected_secret_names(fullspec)
    assert calls["existing_secrets"] == set()
    assert result.state_configmap_deleted is False


@pytest.mark.parametrize("field", ["uid", "resource_version"])
def test_unbootstrap_refuses_secret_without_deletion_identity(
    tmp_path, monkeypatch, field,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets={"product-postgres-secret"},
        metadata_overrides={"product-postgres-secret": {field: None}},
    )

    with pytest.raises(CommandError, match="UID or resourceVersion is missing"):
        unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert calls["deleted"] == []
    assert not any(action == "delete" for action, *_ in calls["configmaps"])


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("secret_read_forbidden", "not authorized to read Secret"),
        ("secret_read_error", "Could not inspect Secret"),
    ],
)
def test_unbootstrap_read_failure_does_not_delete_any_resources(
    tmp_path, monkeypatch, failure, message,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets=expected_secret_names(fullspec),
        missing=failure,
    )

    with pytest.raises(CommandError, match=message):
        unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert calls["deleted"] == []
    assert not any(action == "delete" for action, *_ in calls["configmaps"])


@pytest.mark.parametrize("failure", ["secret_replaced", "secret_relabeled"])
def test_unbootstrap_preserves_secret_changed_after_deletion_preflight(
    tmp_path, monkeypatch, failure,
):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    environment_dir = write_unbootstrap_environment(workspace, fullspec)
    set_bootstrapped_product(environment_dir)
    before = (environment_dir / "spec.json").read_text(encoding="utf-8")
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets={"product-postgres-secret"},
        missing=failure,
    )

    with pytest.raises(CommandError, match="changed after deletion preflight"):
        unbootstrap_lake(plan_lake_unbootstrap("dev", workspace))

    assert calls["existing_secrets"] == {"product-postgres-secret"}
    assert not any(action == "delete" for action, *_ in calls["configmaps"])
    assert (environment_dir / "spec.json").read_text(encoding="utf-8") == before


def test_lake_unbootstrap_yes_warns_and_deletes_without_labels(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    calls = set_secret_cluster(
        monkeypatch,
        existing_secrets={"product-postgres-secret"},
        labels_by_secret={"product-postgres-secret": {}},
    )

    result = runner.invoke(
        app, ["lake", "unbootstrap", "dev", "--workspace", str(workspace), "--yes"],
    )

    assert result.exit_code == 0, result.output
    assert "WARNING: destructive cleanup" in result.output
    assert "regardless of Secret ownership labels" in result.output
    assert "Secrets selected for purge:" in result.output
    assert calls["deleted"] == [("test", "product-postgres-secret")]


def test_lake_unbootstrap_cli_deletes_with_yes(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    fullspec = base_fullspec()
    write_unbootstrap_environment(workspace, fullspec)
    set_secret_cluster(monkeypatch, existing_secrets=expected_secret_names(fullspec))

    result = runner.invoke(
        app,
        [
            "lake",
            "unbootstrap",
            "dev",
            "--workspace",
            str(workspace),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Lake unbootstrap: dev" in result.output
    assert "deleted secrets:" in result.output
    assert "already missing secrets: (none)" in result.output


def test_lake_unbootstrap_cli_help_documents_scope():
    result = runner.invoke(app, ["lake", "unbootstrap", "--help"])

    assert result.exit_code == 0
    assert "tk delete ENV" in result.output
    assert "bootstrap Secrets" in result.output
    assert "--yes" in result.output
