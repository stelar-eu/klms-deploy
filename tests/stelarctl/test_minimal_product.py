import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from stelar.deploy import feature_model
from stelar.deploy.cli import app
from stelar.deploy.cli_handlers import lake_product as lake_product_cli
from stelar.deploy.models.product import (
    Product,
    ProductValidationFailure,
    ProductValidator,
)
from stelar.deploy.operations import add_lake_environment, minimal_product
from stelar.deploy.operations.minimal_product import (
    CommandError,
    InferredStorageClasses,
    MinimalProductConfig,
    build_minimal_product,
    generate_minimal_secret_values,
    infer_storage_classes_from_cluster,
)


runner = CliRunner()


def make_workspace(path):
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


def minimal_config(**overrides) -> MinimalProductConfig:
    values = {
        "root_domain": "example.test",
        "primary_subdomain": "klms",
        "keycloak_subdomain": "kc",
        "minio_api_subdomain": "minio",
        "registry_subdomain": "img",
        "scheme": "https",
        "cluster_issuer": "letsencrypt-prod",
        "dynamic_storage_class": "longhorn",
        "provisioning_storage_class": "longhorn",
        "insecure_minio_client": "false",
        "smtp_server": "smtp.example.test",
        "smtp_port": "587",
        "smtp_username": "operator",
        "secrets": generate_minimal_secret_values(),
    }
    values.update(overrides)
    return MinimalProductConfig(**values)


def test_build_minimal_product_validates_against_feature_model():
    product = build_minimal_product(minimal_config())
    fullspec = ProductValidator(feature_model).validate(Product.model_validate(product))
    klms = fullspec["klms"]

    assert klms["optional_components"] == []
    assert klms["cluster"] == []
    assert klms["postgres"]["volume"] == ["pvc"]
    assert klms["solr"]["volume"] == ["pvc"]
    assert klms["minio"]["volume"] == ["pvc"]
    assert klms["ingress"]["ingress_controller"] == ["nginx"]
    assert klms["ingress"]["tls"] == ["cert_manager"]
    assert klms["ingress"]["cert_manager"]["ClusterIssuer"] == "letsencrypt-prod"
    assert "manual_tls" not in klms["ingress"]
    assert klms["minio"]["API_DOMAIN"] == "https://minio.example.test"
    assert klms["minio"]["CONSOLE_DOMAIN"] == "https://klms.example.test/s3"


def test_build_minimal_product_uses_no_tls_for_http():
    product = build_minimal_product(
        minimal_config(scheme="http", cluster_issuer="ignored")
    )
    fullspec = ProductValidator(feature_model).validate(Product.model_validate(product))
    klms = fullspec["klms"]

    assert "CLUSTER_ISSUER" not in klms
    assert klms["ingress"]["tls"] == ["no_tls"]
    assert "cert_manager" not in klms["ingress"]
    assert klms["minio"]["INSECURE_MC_CLIENT"] == "true"


def test_build_minimal_product_forces_insecure_minio_for_http():
    product = build_minimal_product(
        minimal_config(
            scheme="http",
            cluster_issuer="ignored",
            insecure_minio_client="false",
        )
    )

    assert product["spec"]["minio"]["INSECURE_MC_CLIENT"] == "true"


@pytest.mark.parametrize(
    ("secret_field", "message"),
    [
        ("postgres_db_password", "postgres.POSTGRES_DB_PASSWORD"),
        ("ckan_db_password", "postgres.CKAN_DB_PASSWORD"),
        ("datastore_db_password", "postgres.DATASTORE_DB_PASSWORD"),
        ("keycloak_db_password", "postgres.KEYCLOAK_DB_PASSWORD"),
        ("quay_db_password", "postgres.QUAY_DB_PASSWORD"),
        ("smtp_password", "api.SMTP_PASSWORD"),
        ("ckan_admin_password", "ckan.CKAN_ADMIN_PASSWORD"),
        ("keycloak_root_password", "keycloak.KEYCLOAK_ROOT_PASSWORD"),
        ("minio_root_password", "minio.MINIO_ROOT_PASSWORD"),
    ],
)
def test_build_minimal_product_rejects_short_passwords(secret_field, message):
    secrets = replace(generate_minimal_secret_values(), **{secret_field: "1234"})

    with pytest.raises(
        CommandError,
        match=rf"{message}.*at least 8 characters",
    ):
        build_minimal_product(minimal_config(secrets=secrets))


def test_build_minimal_product_rejects_invalid_https_insecure_minio_value():
    with pytest.raises(CommandError, match="Insecure MinIO client"):
        build_minimal_product(minimal_config(insecure_minio_client="maybe"))


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("api", "SMTP_PASSWORD"),
        ("postgres", "POSTGRES_DB_PASSWORD"),
        ("postgres", "CKAN_DB_PASSWORD"),
        ("postgres", "DATASTORE_DB_PASSWORD"),
        ("postgres", "KEYCLOAK_DB_PASSWORD"),
        ("postgres", "QUAY_DB_PASSWORD"),
        ("ckan", "CKAN_ADMIN_PASSWORD"),
        ("keycloak", "KEYCLOAK_ROOT_PASSWORD"),
        ("minio", "MINIO_ROOT_PASSWORD"),
    ],
)
def test_feature_model_rejects_short_password_constraints(section, field):
    product = build_minimal_product(minimal_config())
    product["spec"][section][field] = "1234"

    with pytest.raises(ProductValidationFailure, match=field):
        ProductValidator(feature_model).validate(Product.model_validate(product))


def test_feature_model_rejects_short_minio_root_user():
    product = build_minimal_product(minimal_config())
    product["spec"]["minio"]["MINIO_ROOT_USER"] = "ab"

    with pytest.raises(ProductValidationFailure, match="MINIO_ROOT_USER"):
        ProductValidator(feature_model).validate(Product.model_validate(product))


def test_feature_model_rejects_multiple_tls_modes():
    product = build_minimal_product(minimal_config())
    product["spec"]["ingress"]["tls"] = ["cert_manager", "manual_tls"]
    product["spec"]["ingress"]["manual_tls"] = {
        "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
        "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
        "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
        "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
    }

    with pytest.raises(ProductValidationFailure, match="Exactly one member of group tls"):
        ProductValidator(feature_model).validate(Product.model_validate(product))


def test_feature_model_accepts_manual_tls_secret_names():
    product = build_minimal_product(minimal_config())
    product["spec"]["ingress"].pop("cert_manager")
    product["spec"]["ingress"]["tls"] = ["manual_tls"]
    product["spec"]["ingress"]["manual_tls"] = {
        "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
        "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
        "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
        "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
    }

    fullspec = ProductValidator(feature_model).validate(Product.model_validate(product))

    assert fullspec["klms"]["ingress"]["tls"] == ["manual_tls"]
    assert fullspec["klms"]["ingress"]["manual_tls"] == {
        "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
        "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
        "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
        "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
    }


def test_feature_model_requires_manual_tls_secret_names():
    product = build_minimal_product(minimal_config())
    product["spec"]["ingress"].pop("cert_manager")
    product["spec"]["ingress"]["tls"] = ["manual_tls"]
    product["spec"]["ingress"]["manual_tls"] = {
        "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
    }

    with pytest.raises(ProductValidationFailure, match="KEYCLOAK_TLS_SECRET_NAME"):
        ProductValidator(feature_model).validate(Product.model_validate(product))


def test_generate_minimal_secret_values_uses_non_empty_distinct_values():
    values = generate_minimal_secret_values()
    raw_values = list(values.__dict__.values())

    assert all(isinstance(value, str) and value for value in raw_values)
    assert values.ckan_jwt_key.startswith("string:")
    assert len(set(raw_values)) == len(raw_values)


def test_infer_storage_classes_from_cluster_uses_default_storage_class(monkeypatch):
    storage_class = make_storage_class(
        "fast",
        {"storageclass.kubernetes.io/is-default-class": "true"},
    )
    monkeypatch.setattr(
        minimal_product.kube_config,
        "list_kube_config_contexts",
        lambda: ([{"name": "dev"}], {"name": "dev"}),
    )
    monkeypatch.setattr(
        minimal_product.kube_config,
        "load_kube_config",
        lambda *, context: None,
    )
    monkeypatch.setattr(
        minimal_product.kube_client,
        "StorageV1Api",
        lambda: SimpleNamespace(
            list_storage_class=lambda: SimpleNamespace(items=[storage_class])
        ),
    )

    inferred = infer_storage_classes_from_cluster()

    assert inferred == InferredStorageClasses(
        context="dev",
        dynamic_storage_class="fast",
        provisioning_storage_class="fast",
    )


def test_infer_storage_classes_from_cluster_prefers_known_storage_name(monkeypatch):
    storage_classes = [make_storage_class("zzz"), make_storage_class("longhorn")]
    monkeypatch.setattr(
        minimal_product.kube_config,
        "list_kube_config_contexts",
        lambda: ([{"name": "dev"}], {"name": "dev"}),
    )
    monkeypatch.setattr(
        minimal_product.kube_config,
        "load_kube_config",
        lambda *, context: None,
    )
    monkeypatch.setattr(
        minimal_product.kube_client,
        "StorageV1Api",
        lambda: SimpleNamespace(
            list_storage_class=lambda: SimpleNamespace(items=storage_classes)
        ),
    )

    inferred = infer_storage_classes_from_cluster("dev")

    assert inferred.dynamic_storage_class == "longhorn"
    assert inferred.provisioning_storage_class == "longhorn"


def test_lake_create_minimal_cli_generates_product_with_default_secret_values(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    add_lake_environment("dev", workspace)
    product_path = workspace / "dev" / "minimal.json"

    result = runner.invoke(
        app,
        [
            "lake",
            "create",
            "--minimal",
            "minimal.json",
            "dev",
            "--workspace",
            str(workspace),
            "--namespace",
            "stelar-dev",
            "--context",
            "dev-context",
        ],
        input=(
            "https\n"
            "letsencrypt-prod\n"
            "longhorn\n"
            "csi-hostpath-sc\n"
            "example.test\n"
            "klms\n"
            "kc\n"
            "minio\n"
            "img\n"
            "false\n"
            "smtp.example.test\n"
            "587\n"
            "operator\n"
        ),
    )

    assert result.exit_code == 0, result.output
    assert "Wrote minimal product" in result.output
    assert (workspace / "dev" / "minimal_fullspec.json").is_file()
    assert not (workspace / "dev" / "product.json").exists()
    assert not (workspace / "dev" / "product_fullspec.json").exists()
    assert "build_lake(environment_spec)" in (
        workspace / "dev" / "main.jsonnet"
    ).read_text(encoding="utf-8")
    spec = yaml.safe_load(
        (workspace / "dev" / "spec.json").read_text(encoding="utf-8")
    )
    assert "active_product" in spec["spec"]["stelar"]
    assert spec["spec"]["stelar"]["active_product_name"] == "minimal"
    assert spec["spec"]["contextNames"] == ["dev-context"]
    assert spec["spec"]["namespace"] == "stelar-dev"
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
    assert "namespace" not in product["spec"]
    assert product["spec"]["dynamicStorageClass"] == "longhorn"
    assert product["spec"]["dynamic_volume_storage_class"] == "csi-hostpath-sc"
    assert product["spec"]["cluster"] == []
    assert product["spec"]["optional_components"] == []
    assert product["spec"]["ingress"]["tls"] == ["cert_manager"]
    assert "manual_tls" not in product["spec"]["ingress"]
    assert product["spec"]["minio"]["MINIO_ROOT_PASSWORD"]
    assert not (workspace / "dev" / "product.secrets.yaml").exists()


def test_lake_create_minimal_cli_rejects_target_flags_after_bootstrap(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    add_lake_environment("dev", workspace)
    spec_path = workspace / "dev" / "spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["spec"] = {
        "contextNames": ["current-context"],
        "namespace": "test",
        "stelar": {
            "bootstrapped_product": {
                "target_sha256": "stored-target-hash",
                "secret_names": ["stored-secret"],
                "bootstrapped_at": "2026-06-07T00:00:00Z",
                "product_name": "minimal",
            },
        },
    }
    spec_path.write_text(f"{json.dumps(spec)}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "lake",
            "create",
            "--minimal",
            "minimal.json",
            "dev",
            "--workspace",
            str(workspace),
            "--context",
            "other-context",
        ],
        input="",
    )

    assert result.exit_code != 0
    assert "recorded bootstrap state" in result.output
    assert "overrides are not allowed" in result.output
    assert not (workspace / "dev" / "minimal.json").exists()
    assert json.loads(spec_path.read_text(encoding="utf-8")) == spec


def test_lake_create_minimal_cli_rejects_empty_target_before_writing_product(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    add_lake_environment("dev", workspace)
    spec_before = json.loads((workspace / "dev" / "spec.json").read_text(encoding="utf-8"))

    result = runner.invoke(
        app,
        [
            "lake",
            "create",
            "--minimal",
            "minimal",
            "dev",
            "--workspace",
            str(workspace),
            "--namespace",
            " ",
        ],
        input="",
    )

    assert result.exit_code != 0
    assert "non-empty" in result.output
    assert not (workspace / "dev" / "minimal.json").exists()
    assert not (workspace / "dev" / "minimal_fullspec.json").exists()
    assert json.loads((workspace / "dev" / "spec.json").read_text(encoding="utf-8")) == spec_before


def test_lake_create_minimal_cli_can_infer_storage_from_cluster(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    add_lake_environment("dev", workspace)
    product_path = workspace / "dev" / "minimal.json"
    monkeypatch.setattr(
        lake_product_cli,
        "infer_storage_classes_from_cluster",
        lambda context: InferredStorageClasses(
            context=context,
            dynamic_storage_class="fast-storage",
            provisioning_storage_class="fast-storage",
        ),
    )

    result = runner.invoke(
        app,
        [
            "lake",
            "create",
            "--minimal",
            "minimal.json",
            "dev",
            "--workspace",
            str(workspace),
            "--infer-storage-from-cluster",
            "--context",
            "dev",
        ],
        input=(
            "http\n"
            "example.test\n"
            "klms\n"
            "kc\n"
            "minio\n"
            "img\n"
            "smtp.example.test\n"
            "465\n"
            "operator\n"
        ),
    )

    assert result.exit_code == 0, result.output
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))

    spec = yaml.safe_load((workspace / "dev" / "spec.json").read_text(encoding="utf-8"))

    assert "Inferred storage classes from 'dev'" in result.output
    assert spec["spec"]["contextNames"] == ["dev"]
    assert "namespace" not in product["spec"]
    assert product["spec"]["dynamicStorageClass"] == "fast-storage"
    assert product["spec"]["dynamic_volume_storage_class"] == "fast-storage"
    assert "CLUSTER_ISSUER" not in product["spec"]
    assert product["spec"]["ingress"]["tls"] == ["no_tls"]
    assert "manual_tls" not in product["spec"]["ingress"]
    assert product["spec"]["minio"]["INSECURE_MC_CLIENT"] == "true"


def test_lake_manual_tls_template_cli_writes_sample_without_creating_cert_dirs(
    tmp_path,
):
    output = tmp_path / "manual_tls.yaml"

    result = runner.invoke(app, ["lake", "manual-tls-template", str(output)])

    assert result.exit_code == 0, result.output
    assert "Wrote manual TLS sample" in result.output
    assert "tls.crt" in result.output
    assert "tls.key" in result.output
    data = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert data["manual_tls"]["primary"] == "./certs/primary"
    assert data["manual_tls"]["registry"] == "./certs/registry"
    assert not (tmp_path / "certs").exists()


def test_lake_manual_tls_template_cli_rejects_existing_file(tmp_path):
    output = tmp_path / "manual_tls.yaml"
    output.write_text("existing", encoding="utf-8")

    result = runner.invoke(app, ["lake", "manual-tls-template", str(output)])

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"


def test_lake_create_minimal_cli_manual_secrets_prompts_for_values(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    add_lake_environment("dev", workspace)
    product_path = workspace / "dev" / "minimal.json"

    result = runner.invoke(
        app,
        [
            "lake",
            "create",
            "--minimal",
            "minimal.json",
            "dev",
            "--workspace",
            str(workspace),
            "--manual-secrets",
        ],
        input=(
            "https\n"
            "letsencrypt-prod\n"
            "longhorn\n"
            "csi-hostpath-sc\n"
            "pgpass123\n"
            "pgpass123\n"
            "ckandbpass123\n"
            "ckandbpass123\n"
            "datastorepass123\n"
            "datastorepass123\n"
            "keycloakdbpass123\n"
            "keycloakdbpass123\n"
            "quaydbpass123\n"
            "quaydbpass123\n"
            "smtppass123\n"
            "smtppass123\n"
            "apisessionsecret123\n"
            "apisessionsecret123\n"
            "ckanadminpass123\n"
            "ckanadminpass123\n"
            "ckansessionsecret123\n"
            "ckansessionsecret123\n"
            "string:ckanjwtsecret123\n"
            "string:ckanjwtsecret123\n"
            "keycloakrootpass123\n"
            "keycloakrootpass123\n"
            "miniorootpass123\n"
            "miniorootpass123\n"
            "example.test\n"
            "klms\n"
            "kc\n"
            "minio\n"
            "img\n"
            "false\n"
            "smtp.example.test\n"
            "587\n"
            "operator\n"
        ),
    )

    assert result.exit_code == 0, result.output
    product = yaml.safe_load(product_path.read_text(encoding="utf-8"))

    assert product["spec"]["postgres"]["POSTGRES_DB_PASSWORD"] == "pgpass123"
    assert product["spec"]["api"]["SMTP_PASSWORD"] == "smtppass123"
    assert product["spec"]["ckan"]["CKAN_JWT_KEY"] == "string:ckanjwtsecret123"
    assert product["spec"]["minio"]["MINIO_ROOT_PASSWORD"] == "miniorootpass123"
    assert not (workspace / "dev" / "product.secrets.yaml").exists()


def make_storage_class(name: str, annotations: dict[str, str] | None = None):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            annotations=annotations or {},
        )
    )
