import stat
from dataclasses import replace
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from stelar.deploy import feature_model
from stelar.deploy.cli import app
from stelar.deploy.cli_handlers import product as product_cli
from stelar.deploy.models.product import (
    Product,
    ProductValidationFailure,
    ProductValidator,
)
from stelar.deploy.operations import minimal_product
from stelar.deploy.operations.minimal_product import (
    CommandError,
    InferredStorageClasses,
    MinimalProductConfig,
    build_generated_secret_report,
    build_minimal_product,
    generate_minimal_secret_values,
    infer_storage_classes_from_cluster,
)


runner = CliRunner()


def minimal_config(**overrides) -> MinimalProductConfig:
    values = {
        "namespace": "stelar-dev",
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


def test_build_minimal_product_rejects_short_minio_root_password():
    secrets = replace(generate_minimal_secret_values(), minio_root_password="1234")

    with pytest.raises(
        CommandError,
        match="minio.MINIO_ROOT_PASSWORD.*at least 8 characters",
    ):
        build_minimal_product(minimal_config(secrets=secrets))


def test_build_minimal_product_rejects_invalid_https_insecure_minio_value():
    with pytest.raises(CommandError, match="Insecure MinIO client"):
        build_minimal_product(minimal_config(insecure_minio_client="maybe"))


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "MINIO_ROOT_PASSWORD",
            "1234",
            "MINIO_ROOT_PASSWORD",
        ),
        (
            "MINIO_ROOT_USER",
            "ab",
            "MINIO_ROOT_USER",
        ),
    ],
)
def test_feature_model_rejects_invalid_minio_credential_constraints(
    field_name,
    value,
    message,
):
    product = build_minimal_product(minimal_config())
    product["spec"]["minio"][field_name] = value

    with pytest.raises(ProductValidationFailure, match=message):
        ProductValidator(feature_model).validate(Product.model_validate(product))


def test_feature_model_rejects_multiple_tls_modes():
    product = build_minimal_product(minimal_config())
    product["spec"]["ingress"]["tls"] = ["cert_manager", "self_signed"]
    product["spec"]["ingress"]["self_signed"] = {}

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


def test_build_generated_secret_report_contains_generated_values(tmp_path):
    product_path = tmp_path / "product.yaml"
    product = build_minimal_product(minimal_config())

    report = build_generated_secret_report(product, product_path)

    assert report["product"] == str(product_path)
    assert report["secrets"]["postgres"]["POSTGRES_DB_PASSWORD"] == product[
        "spec"
    ]["postgres"]["POSTGRES_DB_PASSWORD"]
    assert report["secrets"]["api"]["SESSION_SECRET_KEY"] == product["spec"][
        "api"
    ]["SESSION_SECRET_KEY"]
    assert report["secrets"]["ckan"]["CKAN_AUTH_SECRET_NAME"] == "ckan-auth-secret"


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


def test_product_init_minimal_cli_generates_product_and_secret_report(tmp_path):
    product_path = tmp_path / "product.yaml"

    result = runner.invoke(
        app,
        [
            "product",
            "init-minimal",
            str(product_path),
            "--generate-secret-values",
        ],
        input=(
            "https\n"
            "letsencrypt-prod\n"
            "longhorn\n"
            "csi-hostpath-sc\n"
            "stelar-dev\n"
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
    secret_report_path = tmp_path / "product.secrets.yaml"
    secret_report = yaml.safe_load(secret_report_path.read_text(encoding="utf-8"))

    assert product["spec"]["namespace"] == "stelar-dev"
    assert product["spec"]["dynamicStorageClass"] == "longhorn"
    assert product["spec"]["dynamic_volume_storage_class"] == "csi-hostpath-sc"
    assert product["spec"]["cluster"] == []
    assert product["spec"]["optional_components"] == []
    assert product["spec"]["ingress"]["tls"] == ["cert_manager"]
    assert "manual_tls" not in product["spec"]["ingress"]
    assert secret_report["secrets"]["minio"]["MINIO_ROOT_PASSWORD"] == product[
        "spec"
    ]["minio"]["MINIO_ROOT_PASSWORD"]
    assert stat.S_IMODE(secret_report_path.stat().st_mode) == 0o600


def test_product_init_minimal_cli_can_infer_storage_from_cluster(tmp_path, monkeypatch):
    product_path = tmp_path / "product.yaml"
    monkeypatch.setattr(
        product_cli,
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
            "product",
            "init-minimal",
            str(product_path),
            "--generate-secret-values",
            "--infer-storage-from-cluster",
            "--context",
            "dev",
        ],
        input=(
            "http\n"
            "stelar-dev\n"
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

    assert "Inferred storage classes from 'dev'" in result.output
    assert product["spec"]["dynamicStorageClass"] == "fast-storage"
    assert product["spec"]["dynamic_volume_storage_class"] == "fast-storage"
    assert "CLUSTER_ISSUER" not in product["spec"]
    assert product["spec"]["ingress"]["tls"] == ["no_tls"]
    assert "manual_tls" not in product["spec"]["ingress"]
    assert product["spec"]["minio"]["INSECURE_MC_CLIENT"] == "true"


def test_product_init_manual_tls_cli_writes_sample_without_creating_cert_dirs(
    tmp_path,
):
    output = tmp_path / "manual_tls.yaml"

    result = runner.invoke(app, ["product", "init-manual-tls", str(output)])

    assert result.exit_code == 0, result.output
    assert "Wrote manual TLS sample" in result.output
    assert "tls.crt" in result.output
    assert "tls.key" in result.output
    data = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert data["manual_tls"]["primary"] == "./certs/primary"
    assert data["manual_tls"]["registry"] == "./certs/registry"
    assert not (tmp_path / "certs").exists()


def test_product_init_manual_tls_cli_rejects_existing_file(tmp_path):
    output = tmp_path / "manual_tls.yaml"
    output.write_text("existing", encoding="utf-8")

    result = runner.invoke(app, ["product", "init-manual-tls", str(output)])

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing"


def test_product_init_minimal_rejects_same_product_and_secret_report_path(tmp_path):
    product_path = tmp_path / "product.yaml"

    result = runner.invoke(
        app,
        [
            "product",
            "init-minimal",
            str(product_path),
            "--generate-secret-values",
            "--secret-values-output",
            str(product_path),
        ],
    )

    assert result.exit_code != 0
    assert "must differ" in result.output
    assert not product_path.exists()


def test_product_init_minimal_rejects_existing_secret_report_before_writing_product(
    tmp_path,
):
    product_path = tmp_path / "product.yaml"
    secret_report_path = tmp_path / "product.secrets.yaml"
    secret_report_path.write_text("existing\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "product",
            "init-minimal",
            str(product_path),
            "--generate-secret-values",
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
    assert not product_path.exists()


def make_storage_class(name: str, annotations: dict[str, str] | None = None):
    return SimpleNamespace(
        metadata=SimpleNamespace(
            name=name,
            annotations=annotations or {},
        )
    )
