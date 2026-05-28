import base64
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from stelar.deploy.operations import cluster as cluster_commands
from stelar.deploy.operations import lakespec as lakespec_commands
from stelar.deploy.operations import lake_workspace as workspace_commands
from stelar.deploy.cli import app
from stelar.deploy.operations import (
    CommandError,
    init_lake_cluster,
    init_lake_environment,
    init_lake_workspace,
    product_to_fullspec,
)
from stelar.deploy.models.product import ProductValidationFailure


MAIN_JSONNET_TEMPLATE = (
    "// Static environment template. The selected components are rendered from a\n"
    "// generated product fullspec imported as one shared config object.\n"
    "\n"
    'local product_transformation = import "github.com/stelar-eu/klms-deploy/lib/util/product_transformation.libsonnet";\n'
    'local component_registry = import "github.com/stelar-eu/klms-deploy/lib/util/components.libsonnet";\n'
    "\n"
    'local product_fullspec = import "./product_fullspec.json";\n'
    "\n"
    "local selected_components = std.objectFields(product_transformation.extract_components(product_fullspec));\n"
    "local global_config = product_transformation.extract_configuration(product_fullspec);\n"
    "\n"
    "local render_order = [\n"
    "  name\n"
    "  for name in component_registry.get_names()\n"
    "  if std.member(selected_components, name)\n"
    "];\n"
    "\n"
    "{\n"
    "  manifests: [\n"
    "    component_registry.get(name).manifest(global_config)\n"
    "    for name in render_order\n"
    "  ],\n"
    "}\n"
)
SPEC_JSON_TEMPLATE = '{\n  "apiVersion": "tanka.dev/v1alpha1",\n  "spec": {}\n}\n'
runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def plain_help(output: str) -> str:
    return ANSI_ESCAPE_RE.sub("", output)


def read_jsonnetfile(workspace: Path) -> dict:
    return json.loads((workspace / "jsonnetfile.json").read_text(encoding="utf-8"))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(f"{json.dumps(data)}\n", encoding="utf-8")


def make_workspace(path: Path) -> Path:
    path.mkdir()
    (path / "jsonnetfile.json").write_text("{}", encoding="utf-8")

    template_dir = environment_template_dir(path)
    template_dir.mkdir(parents=True)
    (template_dir / "main.jsonnet").write_text(
        MAIN_JSONNET_TEMPLATE,
        encoding="utf-8",
    )
    return path


def environment_template_dir(workspace: Path) -> Path:
    return (
        workspace
        / "vendor"
        / "github.com"
        / "stelar-eu"
        / "klms-deploy"
        / "lib"
        / "environment_templates"
    )


def write_generated_lake_files(
    workspace: Path,
    environment: str = "dev",
    *,
    namespace: str = "test",
    dynamic_storage_class: str = "fast-storage",
    provisioning_storage_class: str = "provisioning-storage",
    scheme: str = "https",
    cluster_issuer: str | None = "letsencrypt-production",
) -> Path:
    environment_dir = workspace / "environments" / environment
    spec_json = {
        "apiVersion": "tanka.dev/v1alpha1",
        "spec": {},
    }
    product_json = {
        "spec": {
            "namespace": namespace,
            "postgres": {
                "POSTGRES_DB_PASSWORD": "postgres-password",
                "POSTGRES_DB_PASSWORD_SECRET_NAME": "product-postgres-secret",
                "CKAN_DB_PASSWORD": "ckan-password",
                "CKAN_DB_PASSWORD_SECRET_NAME": "product-ckan-db-secret",
                "KEYCLOAK_DB_PASSWORD": "keycloak-db-password",
                "KEYCLOAK_DB_PASSWORD_SECRET_NAME": "product-keycloak-db-secret",
                "DATASTORE_DB_PASSWORD": "datastore-password",
                "DATASTORE_DB_PASSWORD_SECRET_NAME": "product-datastore-secret",
                "QUAY_DB_PASSWORD": "quay-password",
                "QUAY_DB_PASSWORD_SECRET_NAME": "product-quay-db-secret",
            },
            "keycloak": {
                "KEYCLOAK_ROOT_PASSWORD": "keycloak-root-password",
                "KEYCLOAK_ROOT_PASSWORD_SECRET_NAME": "product-keycloak-root-secret",
            },
            "api": {
                "SMTP_PASSWORD": "smtp-password",
                "SMTP_PASSWORD_SECRET_NAME": "product-smtp-secret",
                "SESSION_SECRET_KEY": "session-secret-value",
                "SESSION_SECRET_KEY_SECRET_NAME": "product-session-secret",
            },
            "ckan": {
                "CKAN_ADMIN_PASSWORD": "ckan-admin-password",
                "CKAN_ADMIN_PASSWORD_SECRET_NAME": "product-ckan-admin-secret",
            },
            "minio": {
                "MINIO_ROOT_PASSWORD": "minio-root-password",
                "MINIO_ROOT_PASSWORD_SECRET_NAME": "product-minio-root-secret",
            },
        }
    }
    ingress = {"ingress_controller": ["nginx"], "tls": ["no_tls"]}
    if scheme == "https":
        ingress["tls"] = ["cert_manager"]
        ingress["cert_manager"] = (
            {"ClusterIssuer": cluster_issuer}
            if cluster_issuer is not None
            else {}
        )

    product_fullspec = {
        "klms": {
            "dynamicStorageClass": dynamic_storage_class,
            "dynamic_volume_storage_class": provisioning_storage_class,
            "SCHEME": scheme,
            "minio": {"INSECURE_MC_CLIENT": "true" if scheme == "http" else "false"},
            "ingress": ingress,
        }
    }

    (environment_dir / "spec.json").write_text(
        f"{json.dumps(spec_json)}\n",
        encoding="utf-8",
    )
    (environment_dir / "product.json").write_text(
        f"{json.dumps(product_json)}\n",
        encoding="utf-8",
    )
    (environment_dir / "product_fullspec.json").write_text(
        f"{json.dumps(product_fullspec)}\n",
        encoding="utf-8",
    )
    return environment_dir


def set_cluster_preflight(
    monkeypatch,
    *,
    missing: str | None = None,
    issuer_ready: bool = True,
    existing_secrets: set[str] | None = None,
    missing_storage_classes: set[str] | None = None,
    ingress_controller_label_name: str = "ingress-nginx",
    ingress_controller_has_component_label: bool = True,
    context_names: tuple[str, ...] = ("current-context",),
    active_context: str | None = "current-context",
) -> dict:
    existing_secrets = set(existing_secrets or ())
    missing_storage_classes = set(missing_storage_classes or ())
    calls = {"created_secrets": [], "read_secrets": []}
    active = {"name": active_context} if active_context is not None else None

    def not_found():
        raise cluster_commands.ApiException(status=404, reason="Not Found")

    def forbidden():
        raise cluster_commands.ApiException(status=403, reason="Forbidden")

    def load_kube_config(*, context):
        if missing == "load_context":
            raise RuntimeError("cannot load context")
        calls["context"] = context

    def list_kube_config_contexts():
        if missing == "contexts":
            raise RuntimeError("cannot list contexts")
        return [{"name": name} for name in context_names], active

    class CoreV1Api:
        def read_namespace(self, name):
            calls["namespace"] = name
            if missing == "namespace_forbidden":
                forbidden()
            if missing == "namespace":
                not_found()

        def read_namespaced_secret(self, name, namespace):
            calls["read_secrets"].append((namespace, name))
            if missing == "secret_read_forbidden":
                forbidden()
            if missing == "secret_read_error":
                raise cluster_commands.ApiException(status=500, reason="Server Error")
            if name not in existing_secrets:
                not_found()
            return SimpleNamespace(metadata=SimpleNamespace(name=name))

        def create_namespaced_secret(self, *, namespace, body):
            name = body["metadata"]["name"]
            if missing == "secret_conflict":
                raise cluster_commands.ApiException(status=409, reason="Conflict")
            if missing == "secret_create_forbidden":
                forbidden()
            if missing == "secret_create_error":
                raise cluster_commands.ApiException(status=500, reason="Server Error")
            calls["created_secrets"].append((namespace, name, body))
            existing_secrets.add(name)
            return body

        def list_pod_for_all_namespaces(self, *, label_selector=None):
            calls.setdefault("ingress_controller_selectors", []).append(
                label_selector
            )
            if missing == "ingress_controller_forbidden":
                forbidden()
            if missing == "ingress_controller":
                return SimpleNamespace(items=[])
            labels = {"app.kubernetes.io/name": ingress_controller_label_name}
            if ingress_controller_has_component_label:
                labels["app.kubernetes.io/component"] = "controller"
            if (
                label_selector == "app.kubernetes.io/component=controller"
                and not ingress_controller_has_component_label
            ):
                return SimpleNamespace(items=[])
            if label_selector and label_selector.startswith(
                "app.kubernetes.io/name="
            ):
                expected_name = label_selector.split("=", 1)[1]
                if ingress_controller_label_name != expected_name:
                    return SimpleNamespace(items=[])
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        metadata=SimpleNamespace(
                            labels=labels,
                            name=f"{ingress_controller_label_name}-controller",
                        ),
                        status=SimpleNamespace(
                            phase="Running",
                            conditions=[
                                SimpleNamespace(type="Ready", status="True"),
                            ],
                        )
                    )
                ]
            )

    class StorageV1Api:
        def read_storage_class(self, name):
            calls.setdefault("storage_classes", []).append(name)
            if missing == "storage_class_forbidden":
                forbidden()
            if missing == "storage_class" or name in missing_storage_classes:
                not_found()

    class NetworkingV1Api:
        def read_ingress_class(self, name):
            calls["ingress_class"] = name
            if missing == "ingress_class_forbidden":
                forbidden()
            if missing == "ingress_class":
                not_found()

    class ApiextensionsV1Api:
        def read_custom_resource_definition(self, name):
            calls.setdefault("crds", []).append(name)
            if missing == "crd_forbidden":
                forbidden()
            if missing == "crd":
                not_found()

    class AppsV1Api:
        def read_namespaced_deployment_status(self, name, namespace):
            calls.setdefault("deployments", []).append((namespace, name))
            if missing == "cert_manager_deployment_forbidden":
                forbidden()
            if missing == "cert_manager_deployment":
                not_found()
            available_replicas = 0 if missing == "cert_manager_unready" else 1
            return SimpleNamespace(
                spec=SimpleNamespace(replicas=1),
                status=SimpleNamespace(available_replicas=available_replicas),
            )

    class CustomObjectsApi:
        def get_cluster_custom_object(self, *, group, version, plural, name):
            calls["cluster_issuer"] = {
                "group": group,
                "version": version,
                "plural": plural,
                "name": name,
            }
            if missing == "cluster_issuer_forbidden":
                forbidden()
            if missing == "cluster_issuer":
                not_found()
            status = "True" if issuer_ready else "False"
            return {"status": {"conditions": [{"type": "Ready", "status": status}]}}

    monkeypatch.setattr(
        cluster_commands.kube_config,
        "load_kube_config",
        load_kube_config,
    )
    monkeypatch.setattr(
        cluster_commands.kube_config,
        "list_kube_config_contexts",
        list_kube_config_contexts,
    )
    monkeypatch.setattr(cluster_commands.kube_client, "CoreV1Api", CoreV1Api)
    monkeypatch.setattr(cluster_commands.kube_client, "StorageV1Api", StorageV1Api)
    monkeypatch.setattr(
        cluster_commands.kube_client,
        "NetworkingV1Api",
        NetworkingV1Api,
    )
    monkeypatch.setattr(
        cluster_commands.kube_client,
        "ApiextensionsV1Api",
        ApiextensionsV1Api,
    )
    monkeypatch.setattr(cluster_commands.kube_client, "AppsV1Api", AppsV1Api)
    monkeypatch.setattr(
        cluster_commands.kube_client,
        "CustomObjectsApi",
        CustomObjectsApi,
    )

    return calls


def read_product_spec(environment_dir: Path) -> dict:
    return json.loads((environment_dir / "product.json").read_text())["spec"]


def secret_names_from_product_spec(product_spec: dict) -> set[str]:
    return {
        product_spec["postgres"]["POSTGRES_DB_PASSWORD_SECRET_NAME"],
        product_spec["postgres"]["CKAN_DB_PASSWORD_SECRET_NAME"],
        product_spec["postgres"]["KEYCLOAK_DB_PASSWORD_SECRET_NAME"],
        product_spec["postgres"]["DATASTORE_DB_PASSWORD_SECRET_NAME"],
        product_spec["postgres"]["QUAY_DB_PASSWORD_SECRET_NAME"],
        product_spec["keycloak"]["KEYCLOAK_ROOT_PASSWORD_SECRET_NAME"],
        product_spec["api"]["SMTP_PASSWORD_SECRET_NAME"],
        product_spec["api"]["SESSION_SECRET_KEY_SECRET_NAME"],
        product_spec["ckan"]["CKAN_ADMIN_PASSWORD_SECRET_NAME"],
        "ckan-auth-secret",
        product_spec["minio"]["MINIO_ROOT_PASSWORD_SECRET_NAME"],
    }


def decoded_secret_data(secret: dict) -> dict[str, str]:
    return {
        key: base64.b64decode(value).decode("utf-8")
        for key, value in secret["data"].items()
    }


TLS_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIDDzCCAfegAwIBAgIUMyX14VqDvk6k/uvGexOAodHEy4wwDQYJKoZIhvcNAQEL
BQAwFzEVMBMGA1UEAwwMZXhhbXBsZS50ZXN0MB4XDTI2MDUyODE2NTYzM1oXDTI2
MDUyOTE2NTYzM1owFzEVMBMGA1UEAwwMZXhhbXBsZS50ZXN0MIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqWSnlrJhiQt83guiWlbxYCw95VQXFxlwpiVQ
FscNIEJNEG6uFHAgVwtkSjfFrX6jl+UJX4Hg/U/sDxNVNH8Gw6pybn/k0UIBs5E+
1DBcVdFgLD719CzOK9IuThuHMOte9vR8i14qlvWWrmmutwWLwUFRxXW2PShl6KsO
Zfso0cC196h/WgLsSyStCHdQe6PqPVE/7MzQJMxQEhnUB2YAReKenH3VnYw9QKeJ
3e3ZtnihB6VQMO9i953Gg5Cxdcngu8iPEEaU37KvfZzTRUESH59Tgz0m6JYa7SSf
MHDKdx3wPiZ/WmpiGTyJJBtATpZIdn8IoGg5OMrwuQbrPNEJfQIDAQABo1MwUTAd
BgNVHQ4EFgQUIrnFDiBpW8fmK2yyHroBeYFsZrcwHwYDVR0jBBgwFoAUIrnFDiBp
W8fmK2yyHroBeYFsZrcwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOC
AQEAHMBOpvVpj6/MZp2m8rI7Yw+zFzQhqomhhdg90tYy7GAT8AlXY0PqfGA7iMKi
JPNg6dNWpA/E+HBPh3AJT3jGz4F0olbNV5i+hhm/Xa6Fu39JTF2D2ZfYFSxv3fFc
wH8tkre+09RRqYkuLe6Ny8l4xDYpBLYX2fo6iFj3UxKaACixnQXx4iHX6iORMWD9
r9hWKTA0E4YFVFCa2DMZ/y+ZDKxQIohL1I1MuzxAmGc+ygoIRXhFC/Bnvm9oYLCe
iUlKDYLSbU3fsf5D9QmcrbwlsfKZOfPyJRlpYftKCbvTU51J4/lqqZ4FnzZ2Cx2y
pTnWBJd/FBAzvqmOT6SdXRgRIg==
-----END CERTIFICATE-----
"""
TLS_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCpZKeWsmGJC3ze
C6JaVvFgLD3lVBcXGXCmJVAWxw0gQk0Qbq4UcCBXC2RKN8WtfqOX5QlfgeD9T+wP
E1U0fwbDqnJuf+TRQgGzkT7UMFxV0WAsPvX0LM4r0i5OG4cw61729HyLXiqW9Zau
aa63BYvBQVHFdbY9KGXoqw5l+yjRwLX3qH9aAuxLJK0Id1B7o+o9UT/szNAkzFAS
GdQHZgBF4p6cfdWdjD1Ap4nd7dm2eKEHpVAw72L3ncaDkLF1yeC7yI8QRpTfsq99
nNNFQRIfn1ODPSbolhrtJJ8wcMp3HfA+Jn9aamIZPIkkG0BOlkh2fwigaDk4yvC5
Bus80Ql9AgMBAAECggEALSOdZRLz2sks5R7EjL5OZApmFA5seMNWuW+IAAna/ZWt
Y4ua5+dZNtjaSMzD6I+umHN4I/NAOUBq7zl/oxWWf92T0M5T809blLZHv9ODR3sb
3a6JbB/kcNj5beb4B5kxHS3ZYmodf0zCcofG/w6DR2RYnf3YKkPxpCaxF4vuPLZm
r0TWa0cLOHre3EFWxLQSsp3dSmgfMrg7qYnIZ2cjIJ7IYuO5ZlmU2tZEaA0AvQg4
lC05O4yywWhHHxoiLSbbWhpJcj/lwr0aFunyYKbTVlYOWBD/J/us/3ZtbKImS15V
z0olIS97fHkGNoRxRImbQvduhFAwuNnlw89HC+pPIQKBgQDZroXA3znVfQM5T0XI
TB6RNyibYcFCT6ytdd0i9/PUSSFcbAkKbKOX8Dh2fnviGe2Y/w/oiKWaEcoTZ7Hg
LGBICHyzCeULlGvuxhNtfmwjIMMMi+FJPk2IDRS5gboU8MJgCUR6g7Lt6l3WnGCt
ejbaYecIZYyi5fODwPTjSGJZwwKBgQDHNhYc4VEG3Q1KkxPvh259KZDln7j4+bhY
HjWgggZ7JeN8kKyrJV9koj4RZ2YchYtNCn39KkDlqBk7nrmfzzPDI1LX+KQHNAPW
lmhO/P4ncaWtmte21aG+OBTeP+ZlHTdPRh9JRoY/0qE1aPcWglvqM79/w7sHl0nm
uowRLB2bvwKBgD4g+pnm3GnbaV0lDASz/RFzTcqzZuZXOTC08C232UbgrH3lc9se
0L5f2K2xQghxYAgH3HGA9sr3gtZxBSq3X6+PhI/RJidc8EVREWBx8clA44qkLeOq
vZQ0L5MWvJaXdNLWMk5JYntXJftH3KwGsrs3sCoMWcxwl0UmgH6SPUfjAoGBAIUX
nJR08JZ+Tyf4tYP9XpMelyDiokktRb0RidCPrlbOTHrniYTadi4cuw0ToMQDcLrq
/JuMhEkrEpijhe7AFxwTWIDULHpnhPz0BgJnwkGGCyO+ZMpRVjto6oBF/t6lM1Oy
TKq/BGhVh8DQPOx78X66TgHFOgprSENvdK7wY2OvAoGAXuHPHr9o+BGhparM/zyU
k0OPK01pdnEBwL/5xRgtf+okaghvWIn9IH2VQjLXspZUsTrks6ZPstsBG/veU8dk
HMewtyYdIfVntS+Uez6b9vp792Dofu9H/ehgLInBfpDsk+lST7ge0QqFXJOeoCnD
PQ1vDR3zeA0+a3pp5dch4h4=
-----END PRIVATE KEY-----
"""

def configure_manual_tls_fullspec(environment_dir: Path) -> None:
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"]["ingress"] = {
        "tls": ["manual_tls"],
        "manual_tls": {
            "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
            "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
            "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
            "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
        },
    }
    write_json(environment_dir / "product_fullspec.json", fullspec)


def write_manual_tls_input(
    environment_dir: Path,
    *,
    omit_key_for: str | None = None,
    registry_directory: str = "./certs/registry",
) -> None:
    manual_tls = {
        "manual_tls": {
            "primary": "./certs/primary",
            "keycloak": "./certs/keycloak",
            "minio_api": "./certs/minio-api",
            "registry": registry_directory,
        }
    }
    (environment_dir / "manual_tls.yaml").write_text(
        f"{json.dumps(manual_tls)}\n",
        encoding="utf-8",
    )

    for endpoint_name, directory in manual_tls["manual_tls"].items():
        cert_dir = environment_dir / directory
        cert_dir.mkdir(parents=True, exist_ok=True)
        (cert_dir / "tls.crt").write_text(TLS_CERT_PEM, encoding="utf-8")
        if endpoint_name != omit_key_for:
            (cert_dir / "tls.key").write_text(TLS_KEY_PEM, encoding="utf-8")


class RecordingClusterProgress:
    def __init__(self):
        self.events = []

    def generating_secret(self, secret_name: str) -> None:
        self.events.append(("generating", secret_name))

    def secret_generated(self, secret_name: str) -> None:
        self.events.append(("generated", secret_name))

    def applying_secret(self, secret_name: str) -> None:
        self.events.append(("applying", secret_name))

    def secret_applied(self, secret_name: str) -> None:
        self.events.append(("applied", secret_name))

    def secret_exists(self, secret_name: str) -> None:
        self.events.append(("exists", secret_name))


class RecordingLakeEnvironmentProgress:
    def __init__(self):
        self.events = []

    def creating_directory(self, path: str) -> None:
        self.events.append(("creating_directory", path))

    def directory_created(self, path: str) -> None:
        self.events.append(("directory_created", path))

    def directory_exists(self, path: str) -> None:
        self.events.append(("directory_exists", path))

    def copying_template(self, source: str, destination: str) -> None:
        self.events.append(("copying_template", source, destination))

    def template_copied(self, destination: str) -> None:
        self.events.append(("template_copied", destination))

    def writing_file(self, path: str) -> None:
        self.events.append(("writing_file", path))

    def file_written(self, path: str) -> None:
        self.events.append(("file_written", path))

    def file_exists(self, path: str) -> None:
        self.events.append(("file_exists", path))


class RecordingLakeWorkspaceProgress:
    def __init__(self):
        self.events = []

    def creating_directory(self, path: str) -> None:
        self.events.append(("creating_directory", path))

    def directory_created(self, path: str) -> None:
        self.events.append(("directory_created", path))

    def directory_exists(self, path: str) -> None:
        self.events.append(("directory_exists", path))

    def writing_file(self, path: str) -> None:
        self.events.append(("writing_file", path))

    def file_written(self, path: str) -> None:
        self.events.append(("file_written", path))

    def rewriting_file(self, path: str) -> None:
        self.events.append(("rewriting_file", path))

    def file_rewritten(self, path: str) -> None:
        self.events.append(("file_rewritten", path))

    def file_exists(self, path: str) -> None:
        self.events.append(("file_exists", path))

    def updating_file(self, path: str) -> None:
        self.events.append(("updating_file", path))

    def file_updated(self, path: str) -> None:
        self.events.append(("file_updated", path))


def test_init_lake_workspace_creates_directory_lib_and_jsonnetfile(tmp_path):
    workspace = tmp_path / "workspace"
    progress = RecordingLakeWorkspaceProgress()

    init_lake_workspace(workspace, progress=progress)

    assert workspace.is_dir()
    assert (workspace / "lib").is_dir()
    jsonnetfile = read_jsonnetfile(workspace)
    assert jsonnetfile["version"] == 1
    assert jsonnetfile["legacyImports"] is True
    dependencies = jsonnetfile["dependencies"]
    assert len(dependencies) == 6
    assert dependencies[0] == {
        "source": {
            "git": {
                "remote": "https://github.com/stelar-eu/klms-deploy.git",
                "subdir": "lib",
            }
        },
        "version": "main",
    }
    assert {
        dependency["source"]["git"]["remote"]
        for dependency in dependencies[1:]
    } == {
        "https://github.com/grafana/jsonnet-libs.git",
        "https://github.com/jsonnet-libs/docsonnet.git",
        "https://github.com/jsonnet-libs/k8s-libsonnet.git",
        "https://github.com/jsonnet-libs/xtd.git",
    }
    assert progress.events == [
        ("creating_directory", str(workspace)),
        ("directory_created", str(workspace)),
        ("creating_directory", str(workspace / "lib")),
        ("directory_created", str(workspace / "lib")),
        ("writing_file", str(workspace / "jsonnetfile.json")),
        ("file_written", str(workspace / "jsonnetfile.json")),
    ]


def test_init_lake_workspace_adds_missing_dependencies_to_existing_jsonnetfile(
    tmp_path,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text(
        json.dumps(
            {
                "existing": True,
                "dependencies": [
                    {
                        "source": {
                            "git": {
                                "remote": "https://github.com/stelar-eu/klms-deploy.git",
                                "subdir": "lib",
                            }
                        },
                        "version": "custom-pin",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    progress = RecordingLakeWorkspaceProgress()

    init_lake_workspace(workspace, progress=progress)

    assert (workspace / "lib").is_dir()
    jsonnetfile = read_jsonnetfile(workspace)
    assert jsonnetfile["existing"] is True
    assert len(jsonnetfile["dependencies"]) == 6
    assert jsonnetfile["dependencies"][0]["version"] == "custom-pin"
    assert progress.events == [
        ("directory_exists", str(workspace)),
        ("creating_directory", str(workspace / "lib")),
        ("directory_created", str(workspace / "lib")),
        ("updating_file", str(workspace / "jsonnetfile.json")),
        ("file_updated", str(workspace / "jsonnetfile.json")),
    ]


def test_init_lake_workspace_skips_complete_existing_jsonnetfile(tmp_path):
    workspace = tmp_path / "workspace"
    init_lake_workspace(workspace)
    progress = RecordingLakeWorkspaceProgress()

    init_lake_workspace(workspace, progress=progress)

    assert progress.events == [
        ("directory_exists", str(workspace)),
        ("directory_exists", str(workspace / "lib")),
        ("file_exists", str(workspace / "jsonnetfile.json")),
    ]


def test_init_lake_workspace_force_rewrites_existing_jsonnetfile(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "lib").mkdir()
    (workspace / "jsonnetfile.json").write_text(
        '{"existing": true}\n',
        encoding="utf-8",
    )
    progress = RecordingLakeWorkspaceProgress()

    init_lake_workspace(workspace, force=True, progress=progress)

    assert read_jsonnetfile(workspace)["dependencies"][0]["source"]["git"] == {
        "remote": "https://github.com/stelar-eu/klms-deploy.git",
        "subdir": "lib",
    }
    assert progress.events == [
        ("directory_exists", str(workspace)),
        ("directory_exists", str(workspace / "lib")),
        ("rewriting_file", str(workspace / "jsonnetfile.json")),
        ("file_rewritten", str(workspace / "jsonnetfile.json")),
    ]


def test_init_lake_workspace_rejects_existing_file_path(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.write_text("not a directory", encoding="utf-8")

    with pytest.raises(CommandError, match="exists but is not a directory"):
        init_lake_workspace(workspace)


def test_init_lake_workspace_rejects_existing_lib_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "lib").write_text("not a directory", encoding="utf-8")

    with pytest.raises(CommandError, match="exists but is not a directory"):
        init_lake_workspace(workspace)


def test_init_lake_workspace_rejects_jsonnetfile_directory(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").mkdir()

    with pytest.raises(CommandError, match="exists but is not a file"):
        init_lake_workspace(workspace)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{invalid json\n", "Invalid JSON"),
        ("[]\n", "must contain an object"),
        ('{"dependencies": {}}\n', "dependencies must be a list"),
        ('{"dependencies": ["bad"]}\n', "dependencies must contain objects"),
    ],
)
def test_init_lake_workspace_rejects_invalid_jsonnetfile(
    tmp_path,
    content,
    message,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text(content, encoding="utf-8")

    with pytest.raises(CommandError, match=message):
        init_lake_workspace(workspace)


def test_init_lake_workspace_merges_missing_top_level_fields(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text(
        '{"dependencies": []}\n',
        encoding="utf-8",
    )

    init_lake_workspace(workspace)

    jsonnetfile = read_jsonnetfile(workspace)
    assert jsonnetfile["version"] == 1
    assert jsonnetfile["legacyImports"] is True
    assert len(jsonnetfile["dependencies"]) == 6


def test_init_lake_workspace_rejects_missing_packaged_template(
    tmp_path,
    monkeypatch,
):
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(workspace_commands.pkgutil, "get_data", lambda *_: None)

    with pytest.raises(CommandError, match="Packaged workspace template"):
        init_lake_workspace(workspace)


def test_init_lake_environment_creates_directory_and_copies_templates(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    progress = RecordingLakeEnvironmentProgress()

    init_lake_environment("dev", workspace, progress=progress)

    environment_dir = workspace / "environments" / "dev"
    assert environment_dir.is_dir()
    assert (environment_dir / "main.jsonnet").read_text(
        encoding="utf-8"
    ) == MAIN_JSONNET_TEMPLATE
    assert (environment_dir / "spec.json").read_text(
        encoding="utf-8"
    ) == SPEC_JSON_TEMPLATE
    assert progress.events == [
        ("creating_directory", str(workspace / "environments")),
        ("directory_created", str(workspace / "environments")),
        ("creating_directory", str(environment_dir)),
        ("directory_created", str(environment_dir)),
        (
            "copying_template",
            str(environment_template_dir(workspace) / "main.jsonnet"),
            str(environment_dir / "main.jsonnet"),
        ),
        ("template_copied", str(environment_dir / "main.jsonnet")),
        ("writing_file", str(environment_dir / "spec.json")),
        ("file_written", str(environment_dir / "spec.json")),
    ]


def test_init_lake_environment_accepts_environments_prefixed_name(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")

    init_lake_environment("environments/dev", workspace)

    assert (workspace / "environments" / "dev" / "main.jsonnet").is_file()
    assert (workspace / "environments" / "dev" / "spec.json").is_file()


def test_init_lake_environment_creates_nested_environment(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")

    init_lake_environment("team/dev", workspace)

    assert (workspace / "environments" / "team" / "dev" / "main.jsonnet").is_file()
    assert (workspace / "environments" / "team" / "dev" / "spec.json").is_file()


def test_init_lake_environment_adds_missing_files_to_existing_environment(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = workspace / "environments" / "dev"
    environment_dir.mkdir(parents=True)
    (environment_dir / "main.jsonnet").write_text(
        "existing main\n",
        encoding="utf-8",
    )

    init_lake_environment("dev", workspace)

    assert (environment_dir / "main.jsonnet").read_text(
        encoding="utf-8"
    ) == "existing main\n"
    assert (environment_dir / "spec.json").read_text(
        encoding="utf-8"
    ) == SPEC_JSON_TEMPLATE


def test_init_lake_environment_does_not_overwrite_existing_files(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = workspace / "environments" / "dev"
    environment_dir.mkdir(parents=True)
    (environment_dir / "main.jsonnet").write_text(
        "existing main\n",
        encoding="utf-8",
    )
    (environment_dir / "spec.json").write_text(
        "existing spec\n",
        encoding="utf-8",
    )
    progress = RecordingLakeEnvironmentProgress()

    init_lake_environment("dev", workspace, progress=progress)

    assert (environment_dir / "main.jsonnet").read_text(
        encoding="utf-8"
    ) == "existing main\n"
    assert (environment_dir / "spec.json").read_text(
        encoding="utf-8"
    ) == "existing spec\n"
    assert progress.events == [
        ("directory_exists", str(workspace / "environments")),
        ("directory_exists", str(environment_dir)),
        ("file_exists", str(environment_dir / "main.jsonnet")),
        ("file_exists", str(environment_dir / "spec.json")),
    ]


def test_init_lake_environment_validates_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(CommandError, match="jsonnetfile.json"):
        init_lake_environment("dev", workspace)


def test_init_lake_environment_rejects_environments_file(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    (workspace / "environments").write_text("not a directory", encoding="utf-8")

    with pytest.raises(CommandError, match="exists but is not a directory"):
        init_lake_environment("dev", workspace)


def test_init_lake_environment_rejects_environment_file(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    environments_dir = workspace / "environments"
    environments_dir.mkdir()
    (environments_dir / "dev").write_text("not a directory", encoding="utf-8")

    with pytest.raises(CommandError, match="exists but is not a directory"):
        init_lake_environment("dev", workspace)


def test_init_lake_environment_rejects_existing_main_jsonnet_directory(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = workspace / "environments" / "dev"
    environment_dir.mkdir(parents=True)
    (environment_dir / "main.jsonnet").mkdir()

    with pytest.raises(CommandError, match="exists but is not a file"):
        init_lake_environment("dev", workspace)


def test_init_lake_environment_rejects_existing_spec_json_directory(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = workspace / "environments" / "dev"
    environment_dir.mkdir(parents=True)
    (environment_dir / "main.jsonnet").write_text("{}", encoding="utf-8")
    (environment_dir / "spec.json").mkdir()

    with pytest.raises(CommandError, match="exists but is not a file"):
        init_lake_environment("dev", workspace)


def test_init_lake_environment_requires_vendored_main_template(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text("{}", encoding="utf-8")

    with pytest.raises(CommandError, match="Run jb install first"):
        init_lake_environment("dev", workspace)


@pytest.mark.parametrize("environment", ["", "/dev", "../dev", "dev/../prod"])
def test_init_lake_environment_rejects_invalid_environment_names(
    tmp_path,
    environment,
):
    workspace = make_workspace(tmp_path / "workspace")

    with pytest.raises(CommandError):
        init_lake_environment(environment, workspace)


def test_init_lake_cluster_requires_initialized_environment(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")

    with pytest.raises(CommandError, match="has not been initialized"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_requires_generated_product_files(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)

    with pytest.raises(CommandError, match="missing product.json"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_requires_generated_fullspec_file(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = workspace / "environments" / "dev"
    (environment_dir / "product.json").write_text(
        '{"spec": {}}\n',
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="missing product_fullspec.json"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_product_without_spec(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    write_json(environment_dir / "product.json", {})
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="Product file must contain a spec object"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_product_without_namespace(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    product["spec"].pop("namespace")
    write_json(environment_dir / "product.json", product)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="Product spec must define"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_fullspec_without_klms(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    write_json(environment_dir / "product_fullspec.json", {})
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="must contain a klms object"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_dynamic_storage_class(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"].pop("dynamicStorageClass")
    write_json(environment_dir / "product_fullspec.json", fullspec)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="must define dynamicStorageClass"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_provisioning_storage_field(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"].pop("dynamic_volume_storage_class")
    write_json(environment_dir / "product_fullspec.json", fullspec)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="provisioning_storage_class"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_accepts_provisioning_storage_alias(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"].pop("dynamic_volume_storage_class")
    fullspec["klms"]["provisioning_storage_class"] = "provisioning-storage"
    write_json(environment_dir / "product_fullspec.json", fullspec)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    assert calls["storage_classes"] == ["fast-storage", "provisioning-storage"]


def test_init_lake_cluster_deduplicates_storage_classes(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(
        workspace,
        dynamic_storage_class="shared-storage",
        provisioning_storage_class="shared-storage",
    )
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    assert calls["storage_classes"] == ["shared-storage"]


def test_init_lake_cluster_rejects_invalid_scheme(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace, scheme="ftp")
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="SCHEME as http or https"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_http_with_tls_mode(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="http")
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"]["ingress"] = {"tls": ["self_signed"], "self_signed": {}}
    write_json(environment_dir / "product_fullspec.json", fullspec)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="SCHEME http.*ingress.tls no_tls"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_https_without_tls_mode(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"]["ingress"] = {"tls": ["no_tls"], "no_tls": {}}
    write_json(environment_dir / "product_fullspec.json", fullspec)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="SCHEME https.*manual_tls"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_accepts_manual_tls_without_cert_manager_preflight(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"]["ingress"] = {
        "tls": ["manual_tls"],
        "manual_tls": {
            "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
            "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
            "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
            "REGISTRY_TLS_SECRET_NAME": "img-manual-tls",
        },
    }
    write_json(environment_dir / "product_fullspec.json", fullspec)
    write_manual_tls_input(environment_dir)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    assert calls["storage_classes"] == ["fast-storage", "provisioning-storage"]
    assert "crds" not in calls
    assert "deployments" not in calls
    assert "cluster_issuer" not in calls


def test_init_lake_cluster_requires_manual_tls_environment_file(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    product_spec = read_product_spec(environment_dir)
    set_cluster_preflight(
        monkeypatch,
        existing_secrets=secret_names_from_product_spec(product_spec),
    )

    with pytest.raises(
        CommandError,
        match="manual_tls.yaml.*stelarctl product init-manual-tls",
    ):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_applies_manual_tls_secrets_from_environment_file(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    write_manual_tls_input(environment_dir)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    created_secrets = {
        secret_name: body
        for _, secret_name, body in calls["created_secrets"]
    }
    for secret_name in {
        "klms-manual-tls",
        "kc-manual-tls",
        "minio-manual-tls",
        "img-manual-tls",
    }:
        assert created_secrets[secret_name]["type"] == "kubernetes.io/tls"
        assert decoded_secret_data(created_secrets[secret_name]) == {
            "tls.crt": TLS_CERT_PEM,
            "tls.key": TLS_KEY_PEM,
        }


def test_init_lake_cluster_rejects_invalid_manual_tls_directory_value(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    manual_tls = {
        "manual_tls": {
            "primary": "./certs/primary",
            "keycloak": "./certs/keycloak",
            "minio_api": "./certs/minio-api",
            "registry": {"directory": "./certs/registry"},
        }
    }
    (environment_dir / "manual_tls.yaml").write_text(
        f"{json.dumps(manual_tls)}\n",
        encoding="utf-8",
    )
    product_spec = read_product_spec(environment_dir)
    set_cluster_preflight(
        monkeypatch,
        existing_secrets=secret_names_from_product_spec(product_spec),
    )

    with pytest.raises(CommandError, match="manual_tls.registry"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_invalid_manual_tls_secret_files(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    write_manual_tls_input(environment_dir, omit_key_for="registry")
    product_spec = read_product_spec(environment_dir)
    set_cluster_preflight(
        monkeypatch,
        existing_secrets=secret_names_from_product_spec(product_spec),
    )

    with pytest.raises(CommandError, match="tls.key.*does not exist"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_invalid_manual_tls_pem_base64(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    write_manual_tls_input(environment_dir)
    (environment_dir / "certs" / "registry" / "tls.crt").write_text(
        "-----BEGIN CERTIFICATE-----\nnot valid base64!\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    product_spec = read_product_spec(environment_dir)
    set_cluster_preflight(
        monkeypatch,
        existing_secrets=secret_names_from_product_spec(product_spec),
    )

    with pytest.raises(CommandError, match="invalid PEM base64"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_reports_manual_tls_secret_create_forbidden(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    configure_manual_tls_fullspec(environment_dir)
    write_manual_tls_input(environment_dir)
    product_spec = read_product_spec(environment_dir)
    set_cluster_preflight(
        monkeypatch,
        existing_secrets=secret_names_from_product_spec(product_spec),
        missing="secret_create_forbidden",
    )

    with pytest.raises(CommandError, match="not authorized to create manual TLS Secret"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_requires_manual_tls_secret_names(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace, scheme="https")
    fullspec = read_json(environment_dir / "product_fullspec.json")
    fullspec["klms"]["ingress"] = {
        "tls": ["manual_tls"],
        "manual_tls": {
            "PRIMARY_TLS_SECRET_NAME": "klms-manual-tls",
            "KEYCLOAK_TLS_SECRET_NAME": "kc-manual-tls",
            "MINIO_API_TLS_SECRET_NAME": "minio-manual-tls",
        },
    }
    write_json(environment_dir / "product_fullspec.json", fullspec)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="REGISTRY_TLS_SECRET_NAME"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_requires_cluster_issuer_for_https(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace, scheme="https", cluster_issuer=None)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="ingress.cert_manager.ClusterIssuer"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_runs_cluster_preflight(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    assert calls["context"] == "current-context"
    assert calls["namespace"] == "test"
    assert calls["storage_classes"] == ["fast-storage", "provisioning-storage"]
    assert calls["ingress_class"] == "nginx"
    assert calls["ingress_controller_selectors"] == [
        "app.kubernetes.io/component=controller"
    ]
    assert calls["crds"] == [
        "certificates.cert-manager.io",
        "clusterissuers.cert-manager.io",
    ]
    assert calls["deployments"] == [
        ("cert-manager", "cert-manager"),
        ("cert-manager", "cert-manager-cainjector"),
        ("cert-manager", "cert-manager-webhook"),
    ]
    assert calls["cluster_issuer"] == {
        "group": "cert-manager.io",
        "version": "v1",
        "plural": "clusterissuers",
        "name": "letsencrypt-production",
    }


def test_init_lake_cluster_applies_product_spec_secrets(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product_spec = read_product_spec(environment_dir)
    calls = set_cluster_preflight(monkeypatch)
    progress = RecordingClusterProgress()

    init_lake_cluster("dev", workspace, progress=progress)

    created_secrets = {
        secret_name: body
        for _, secret_name, body in calls["created_secrets"]
    }
    assert set(created_secrets) == secret_names_from_product_spec(product_spec)

    postgres_secret_name = product_spec["postgres"][
        "POSTGRES_DB_PASSWORD_SECRET_NAME"
    ]
    assert decoded_secret_data(created_secrets[postgres_secret_name]) == {
        "password": product_spec["postgres"]["POSTGRES_DB_PASSWORD"]
    }

    session_secret_name = product_spec["api"]["SESSION_SECRET_KEY_SECRET_NAME"]
    assert decoded_secret_data(created_secrets[session_secret_name]) == {
        "key": product_spec["api"]["SESSION_SECRET_KEY"]
    }

    ckan_auth_data = decoded_secret_data(created_secrets["ckan-auth-secret"])
    assert set(ckan_auth_data) == {"session-key", "jwt-key"}
    assert ckan_auth_data["jwt-key"].startswith("string:")
    assert progress.events[:4] == [
        ("generating", "product-postgres-secret"),
        ("generated", "product-postgres-secret"),
        ("applying", "product-postgres-secret"),
        ("applied", "product-postgres-secret"),
    ]


def test_init_lake_cluster_skips_existing_product_spec_secrets(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product_spec = read_product_spec(environment_dir)
    existing_secrets = secret_names_from_product_spec(product_spec)
    calls = set_cluster_preflight(
        monkeypatch,
        existing_secrets=existing_secrets,
    )
    progress = RecordingClusterProgress()

    init_lake_cluster("dev", workspace, progress=progress)

    assert calls["created_secrets"] == []
    assert {name for _, name in calls["read_secrets"]} == existing_secrets
    assert set(progress.events) == {("exists", name) for name in existing_secrets}


def test_init_lake_cluster_applies_optional_llm_search_secret(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    product["spec"]["llm_search"] = {
        "GROQ_API_KEY": "groq-key-value",
        "GROQ_API_KEY_SECRET_NAME": "product-groq-secret",
    }
    write_json(environment_dir / "product.json", product)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    created_secrets = {
        secret_name: body
        for _, secret_name, body in calls["created_secrets"]
    }
    assert decoded_secret_data(created_secrets["product-groq-secret"]) == {
        "key": "groq-key-value"
    }


def test_init_lake_cluster_treats_secret_create_conflict_as_existing(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="secret_conflict")
    progress = RecordingClusterProgress()

    init_lake_cluster("dev", workspace, progress=progress)

    assert ("exists", "product-postgres-secret") in progress.events


def test_init_lake_cluster_rejects_secret_read_error(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="secret_read_error")

    with pytest.raises(CommandError, match="Could not validate Secret"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_secret_create_error(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="secret_create_error")

    with pytest.raises(CommandError, match="Could not create Secret"):
        init_lake_cluster("dev", workspace)


@pytest.mark.parametrize(
    ("mutate_product", "message"),
    [
        (
            lambda product: product["spec"].pop("postgres"),
            "Product spec must contain a postgres object",
        ),
        (
            lambda product: product["spec"]["postgres"].pop("CKAN_DB_PASSWORD"),
            "postgres.CKAN_DB_PASSWORD",
        ),
        (
            lambda product: product["spec"]["api"].update({"SMTP_PASSWORD": ""}),
            "api.SMTP_PASSWORD",
        ),
    ],
)
def test_init_lake_cluster_rejects_invalid_secret_source_fields(
    tmp_path,
    monkeypatch,
    mutate_product,
    message,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    mutate_product(product)
    write_json(environment_dir / "product.json", product)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match=message):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_namespace(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="namespace")

    with pytest.raises(CommandError, match="Namespace 'test' does not exist"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_context_list_failure(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="contexts")

    with pytest.raises(CommandError, match="Could not load kubectl contexts"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_active_context(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, active_context=None)

    with pytest.raises(CommandError, match="No active kubectl context found"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_context_load_failure(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="load_context")

    with pytest.raises(CommandError, match="Could not load kubectl context"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_storage_class(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="storage_class")

    with pytest.raises(
        CommandError,
        match="StorageClass 'fast-storage' does not exist",
    ):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_provisioning_storage_class(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(
        monkeypatch,
        missing_storage_classes={"provisioning-storage"},
    )

    with pytest.raises(
        CommandError,
        match="StorageClass 'provisioning-storage' does not exist",
    ):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_ingress_controller(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="ingress_controller")

    with pytest.raises(
        CommandError,
        match="No Ready ingress-nginx controller pod found",
    ):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_ingress_class(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="ingress_class")

    with pytest.raises(CommandError, match="IngressClass 'nginx' does not exist"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_accepts_rke2_ingress_controller(
    tmp_path, monkeypatch
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    calls = set_cluster_preflight(
        monkeypatch,
        ingress_controller_label_name="rke2-ingress-nginx",
    )

    init_lake_cluster("dev", workspace)

    assert calls["ingress_controller_selectors"] == [
        "app.kubernetes.io/component=controller"
    ]


def test_init_lake_cluster_accepts_name_only_ingress_controller(
    tmp_path, monkeypatch
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    calls = set_cluster_preflight(
        monkeypatch,
        ingress_controller_has_component_label=False,
    )

    init_lake_cluster("dev", workspace)

    assert calls["ingress_controller_selectors"] == [
        "app.kubernetes.io/component=controller",
        "app.kubernetes.io/name=ingress-nginx",
    ]


def test_init_lake_cluster_rejects_unready_cluster_issuer(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, issuer_ready=False)

    with pytest.raises(
        CommandError,
        match="ClusterIssuer 'letsencrypt-production' is not Ready",
    ):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_cert_manager_crd(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="crd")

    with pytest.raises(CommandError, match="cert-manager CRD"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_cert_manager_deployment(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="cert_manager_deployment")

    with pytest.raises(CommandError, match="cert-manager Deployment"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_unready_cert_manager_deployment(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="cert_manager_unready")

    with pytest.raises(CommandError, match="is not Ready"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_missing_cluster_issuer(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="cluster_issuer")

    with pytest.raises(
        CommandError,
        match="ClusterIssuer 'letsencrypt-production' does not exist",
    ):
        init_lake_cluster("dev", workspace)


@pytest.mark.parametrize(
    ("missing", "expected_check"),
    [
        ("namespace_forbidden", "Namespace 'test'"),
        ("storage_class_forbidden", "StorageClass 'fast-storage'"),
        ("ingress_class_forbidden", "IngressClass 'nginx'"),
        ("ingress_controller_forbidden", "ingress-nginx controller pod discovery"),
        ("crd_forbidden", "cert-manager CRD 'certificates.cert-manager.io'"),
        ("cert_manager_deployment_forbidden", "cert-manager Deployment 'cert-manager'"),
        ("cluster_issuer_forbidden", "ClusterIssuer 'letsencrypt-production'"),
    ],
)
def test_init_lake_cluster_reports_forbidden_preflight_checks(
    tmp_path,
    monkeypatch,
    missing,
    expected_check,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing=missing)

    with pytest.raises(cluster_commands.PreflightAccessError) as exc_info:
        init_lake_cluster("dev", workspace)

    message = str(exc_info.value)
    assert expected_check in message
    assert "does not have access" in message
    assert "--skip-preflight" in message


def test_init_lake_cluster_preflight_skip_bypasses_read_only_checks(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    calls = set_cluster_preflight(monkeypatch, missing="storage_class_forbidden")

    init_lake_cluster("dev", workspace, preflight="skip")

    assert "namespace" not in calls
    assert "storage_classes" not in calls
    assert "ingress_class" not in calls
    assert "ingress_controller_selectors" not in calls
    assert "crds" not in calls
    assert calls["created_secrets"]


def test_init_lake_cluster_skips_cert_manager_for_http(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace, scheme="http", cluster_issuer=None)
    calls = set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    assert "crds" not in calls
    assert "deployments" not in calls
    assert "cluster_issuer" not in calls


def test_init_lake_cli_has_environment_and_cluster_subcommands():
    result = runner.invoke(app, ["init-lake", "--help"])

    assert result.exit_code == 0
    assert "workspace" in result.stdout
    assert "environment" in result.stdout
    assert "cluster" in result.stdout


def test_init_lake_workspace_cli_creates_workspace(tmp_path):
    workspace = tmp_path / "workspace"

    result = runner.invoke(
        app,
        [
            "init-lake",
            "workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert (workspace / "jsonnetfile.json").is_file()
    assert (workspace / "lib").is_dir()
    assert f"🌐 Creating directory {str(workspace)!r}..." in result.stdout
    assert f"✅ Directory {str(workspace)!r} created." in result.stdout
    assert (
        f"🖊️ Writing JSONNet file to "
        f"{str(workspace / 'jsonnetfile.json')!r}..."
        in result.stdout
    )
    assert (
        f"✅ JSONNet file written successfully at "
        f"{str(workspace / 'jsonnetfile.json')!r}."
        in result.stdout
    )


def test_init_lake_workspace_cli_force_rewrites_jsonnetfile(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text(
        '{"existing": true}\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "init-lake",
            "workspace",
            str(workspace),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "existing" not in read_jsonnetfile(workspace)
    assert (
        f"🖊️ Rewriting JSONNet file at "
        f"{str(workspace / 'jsonnetfile.json')!r}..."
        in result.stdout
    )
    assert (
        f"✅ JSONNet file rewritten successfully at "
        f"{str(workspace / 'jsonnetfile.json')!r}."
        in result.stdout
    )


def test_init_lake_workspace_cli_adds_missing_dependencies(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "jsonnetfile.json").write_text(
        '{"dependencies": []}\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "init-lake",
            "workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert len(read_jsonnetfile(workspace)["dependencies"]) == 6
    assert (
        f"🖊️ Adding missing lake dependencies to "
        f"{str(workspace / 'jsonnetfile.json')!r}..."
        in result.stdout
    )
    assert (
        f"✅ JSONNet file updated successfully at "
        f"{str(workspace / 'jsonnetfile.json')!r}."
        in result.stdout
    )


def test_init_lake_environment_cli_creates_environment(tmp_path):
    workspace = make_workspace(tmp_path / "workspace")

    result = runner.invoke(
        app,
        [
            "init-lake",
            "environment",
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert (workspace / "environments" / "dev" / "main.jsonnet").is_file()
    assert (workspace / "environments" / "dev" / "spec.json").is_file()
    assert f"🌐 Creating directory {str(workspace / 'environments')!r}..." in result.stdout
    assert f"✅ Directory {str(workspace / 'environments')!r} created." in result.stdout
    assert (
        "🖊️ Copying template "
        f"{str(environment_template_dir(workspace) / 'main.jsonnet')!r}"
        in result.stdout
    )
    assert (
        f"✅ Template written successfully at "
        f"{str(workspace / 'environments' / 'dev' / 'main.jsonnet')!r}."
        in result.stdout
    )
    assert (
        f"🖊️ Writing Tanka spec skeleton to "
        f"{str(workspace / 'environments' / 'dev' / 'spec.json')!r}..."
        in result.stdout
    )
    assert (
        f"✅ Tanka spec skeleton written successfully at "
        f"{str(workspace / 'environments' / 'dev' / 'spec.json')!r}."
        in result.stdout
    )


def test_init_lake_cluster_cli_accepts_initialized_environment(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch)

    result = runner.invoke(
        app,
        [
            "init-lake",
            "cluster",
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert "🔐 Generating secret 'product-postgres-secret'..." in result.stdout
    assert "✅ Secret 'product-postgres-secret' generated." in result.stdout
    assert (
        "🚀 Applying secret 'product-postgres-secret' to the K8s cluster..."
        in result.stdout
    )
    assert "✅ Secret 'product-postgres-secret' applied successfully." in result.stdout


def test_init_lake_cluster_cli_reports_preflight_rbac_failure(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="storage_class_forbidden")

    result = runner.invoke(
        app,
        [
            "init-lake",
            "cluster",
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 1
    assert "Warning:" in result.output
    assert "StorageClass 'fast-storage'" in result.output
    assert "--skip-preflight" in result.output


def test_init_lake_cluster_cli_accepts_preflight_skip(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, missing="storage_class_forbidden")

    result = runner.invoke(
        app,
        [
            "init-lake",
            "cluster",
            "dev",
            "--workspace",
            str(workspace),
            "--skip-preflight",
        ],
    )

    assert result.exit_code == 0
    assert "🔐 Generating secret 'product-postgres-secret'..." in result.stdout


def test_old_init_lake_environment_cli_command_is_removed():
    help_result = runner.invoke(app, ["--help"])
    removed_command_result = runner.invoke(app, ["init-lake-environment", "--help"])

    assert help_result.exit_code == 0
    assert "init-lake-environment" not in help_result.stdout
    assert removed_command_result.exit_code != 0


def test_root_cli_help_only_lists_implemented_commands():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate-lakespec" not in result.stdout
    assert "product" in result.stdout
    assert "init-lake" in result.stdout
    assert "status" not in result.stdout
    assert "model" not in result.stdout


def test_root_cli_help_documents_current_workflow():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "product generate" in result.stdout
    assert "init-lake cluster" in result.stdout
    assert "init-manual-tls" in result.stdout


def test_root_cli_short_help_alias_is_available():
    result = runner.invoke(app, ["-h"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "product" in result.stdout


def test_root_cli_without_args_shows_help():
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "product" in result.stdout
    assert "init-lake" in result.stdout


def test_product_cli_help_documents_tls_modes():
    result = runner.invoke(app, ["product", "init-minimal", "--help"])

    assert result.exit_code == 0
    assert "INSECURE_MC_CLIENT" in result.stdout
    assert "cert_manager" in result.stdout
    assert "manual_tls" in result.stdout
    assert "not" in result.stdout
    assert "generated" in result.stdout


def test_product_manual_tls_help_documents_required_environment_file():
    result = runner.invoke(app, ["product", "init-manual-tls", "--help"])

    assert result.exit_code == 0
    output = plain_help(result.stdout)
    assert "environments/<env>/manual_tls.yaml" in output
    assert "tls.crt" in output
    assert "product_fullspec.json" in output


def test_product_generate_help_documents_fullspec_validation():
    result = runner.invoke(app, ["product", "generate", "--help"])

    assert result.exit_code == 0
    assert "minio.INSECURE_MC_CLIENT" in result.stdout
    assert "manual_tls" in result.stdout
    assert "cert_manager" in result.stdout


def test_init_lake_cluster_help_documents_preflight_and_tls_behavior():
    result = runner.invoke(app, ["init-lake", "cluster", "--help"])

    assert result.exit_code == 0
    output = plain_help(result.stdout)
    assert "--skip-preflight" in output
    assert "manual_tls" in output
    assert "cert-manager" in output


class FakeProductValidator:
    def __init__(self, feature_model):
        self.feature_model = feature_model

    def validate(self, product):
        return {
            "klms": {
                "namespace": product.spec["namespace"],
                "generated": True,
                "SCHEME": "http",
                "minio": {"INSECURE_MC_CLIENT": "true"},
                "ingress": {"tls": ["no_tls"], "no_tls": {}},
            }
        }


class FailingProductValidator:
    def __init__(self, feature_model):
        self.feature_model = feature_model

    def validate(self, product):
        raise ProductValidationFailure(
            "invalid product choices",
            {"klms": ["unsupported selection"]},
        )


class HttpWithTlsProductValidator:
    def __init__(self, feature_model):
        self.feature_model = feature_model

    def validate(self, product):
        return {
            "klms": {
                "namespace": product.spec["namespace"],
                "SCHEME": "http",
                "minio": {"INSECURE_MC_CLIENT": "true"},
                "ingress": {
                    "tls": ["cert_manager"],
                    "cert_manager": {"ClusterIssuer": "letsencrypt-production"},
                },
            }
        }


class HttpWithSecureMinioProductValidator:
    def __init__(self, feature_model):
        self.feature_model = feature_model

    def validate(self, product):
        return {
            "klms": {
                "namespace": product.spec["namespace"],
                "SCHEME": "http",
                "minio": {"INSECURE_MC_CLIENT": "false"},
                "ingress": {"tls": ["no_tls"], "no_tls": {}},
            }
        }


class HttpsNoTlsProductValidator:
    def __init__(self, feature_model):
        self.feature_model = feature_model

    def validate(self, product):
        return {
            "klms": {
                "namespace": product.spec["namespace"],
                "SCHEME": "https",
                "minio": {"INSECURE_MC_CLIENT": "false"},
                "ingress": {"tls": ["no_tls"], "no_tls": {}},
            }
        }


def test_generate_lakespec_cli_writes_files_and_prints_fullspec(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    product_path = tmp_path / "product.yaml"
    product_path.write_text(
        "author: operator@example.com\nspec:\n  namespace: test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lakespec_commands, "ProductValidator", FakeProductValidator)

    result = runner.invoke(
        app,
        [
            "product",
            "generate",
            str(product_path),
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "klms": {
            "namespace": "test",
            "generated": True,
            "SCHEME": "http",
            "minio": {"INSECURE_MC_CLIENT": "true"},
            "ingress": {"tls": ["no_tls"], "no_tls": {}},
        }
    }
    environment_dir = workspace / "environments" / "dev"
    assert read_json(environment_dir / "product_fullspec.json") == {
        "klms": {
            "namespace": "test",
            "generated": True,
            "SCHEME": "http",
            "minio": {"INSECURE_MC_CLIENT": "true"},
            "ingress": {"tls": ["no_tls"], "no_tls": {}},
        }
    }


def test_generate_lakespec_cli_reports_command_error(tmp_path):
    product_path = tmp_path / "product.yaml"
    product_path.write_text("spec:\n  namespace: test\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "product",
            "generate",
            str(product_path),
            "dev",
            "--workspace",
            str(tmp_path / "missing-workspace"),
        ],
    )

    assert result.exit_code != 0
    assert "Workspace path" in result.output


def test_generate_lakespec_cli_reports_product_validation_failure(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    product_path = tmp_path / "product.yaml"
    product_path.write_text("spec:\n  namespace: test\n", encoding="utf-8")
    monkeypatch.setattr(lakespec_commands, "ProductValidator", FailingProductValidator)

    result = runner.invoke(
        app,
        [
            "product",
            "generate",
            str(product_path),
            "dev",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 1
    assert "invalid product choices" in result.output


def test_product_to_fullspec_requires_initialized_environment(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    product_path = tmp_path / "product.yaml"
    product_path.write_text("spec:\n  namespace: test\n", encoding="utf-8")
    monkeypatch.setattr(lakespec_commands, "ProductValidator", FakeProductValidator)

    with pytest.raises(CommandError, match="has not been initialized"):
        product_to_fullspec(product_path, "dev", workspace)


def test_product_to_fullspec_requires_environment_spec_json(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    environment_dir = workspace / "environments" / "dev"
    environment_dir.mkdir(parents=True)
    (environment_dir / "main.jsonnet").write_text("{}", encoding="utf-8")
    product_path = tmp_path / "product.yaml"
    product_path.write_text("spec:\n  namespace: test\n", encoding="utf-8")
    monkeypatch.setattr(lakespec_commands, "ProductValidator", FakeProductValidator)

    with pytest.raises(CommandError, match="missing spec.json"):
        product_to_fullspec(product_path, "dev", workspace)


def test_product_to_fullspec_writes_product_and_fullspec(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    product_path = tmp_path / "product.yaml"
    product_path.write_text(
        "author: operator@example.com\nspec:\n  namespace: test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(lakespec_commands, "ProductValidator", FakeProductValidator)

    fullspec = product_to_fullspec(product_path, "dev", workspace)

    environment_dir = workspace / "environments" / "dev"
    assert fullspec == {
        "klms": {
            "namespace": "test",
            "generated": True,
            "SCHEME": "http",
            "minio": {"INSECURE_MC_CLIENT": "true"},
            "ingress": {"tls": ["no_tls"], "no_tls": {}},
        }
    }
    assert json.loads((environment_dir / "product.json").read_text()) == {
        "author": "operator@example.com",
        "spec": {"namespace": "test"},
    }
    assert (
        json.loads((environment_dir / "product_fullspec.json").read_text())
        == fullspec
    )
    assert json.loads((environment_dir / "spec.json").read_text()) == {
        "apiVersion": "tanka.dev/v1alpha1",
        "spec": {},
    }


@pytest.mark.parametrize(
    ("validator", "message"),
    [
        (HttpWithTlsProductValidator, "SCHEME http.*ingress.tls no_tls"),
        (HttpsNoTlsProductValidator, "SCHEME https.*manual_tls"),
        (HttpWithSecureMinioProductValidator, "SCHEME http.*INSECURE_MC_CLIENT"),
    ],
)
def test_product_to_fullspec_rejects_scheme_tls_mismatch(
    tmp_path,
    monkeypatch,
    validator,
    message,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    product_path = tmp_path / "product.yaml"
    product_path.write_text("spec:\n  namespace: test\n", encoding="utf-8")
    monkeypatch.setattr(lakespec_commands, "ProductValidator", validator)

    with pytest.raises(CommandError, match=message):
        product_to_fullspec(product_path, "dev", workspace)


def test_init_lake_cluster_populates_spec_with_provided_context(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(
        monkeypatch,
        context_names=("current-context", "other-context"),
    )

    init_lake_cluster("dev", workspace, context="other-context")

    spec_json = json.loads(
        (workspace / "environments" / "dev" / "spec.json").read_text()
    )
    assert spec_json == {
        "apiVersion": "tanka.dev/v1alpha1",
        "metadata": {
            "name": "environments/dev",
            "namespace": "environments/dev/main.jsonnet",
        },
        "spec": {
            "contextNames": ["other-context"],
            "namespace": "test",
            "expectVersions": {},
            "injectLabels": True,
            "resourceDefaults": {
                "annotations": {},
                "labels": {
                    "app.kubernetes.io/managed-by": "tanka",
                    "app.kubernetes.io/part-of": "stelar",
                    "stelar.deployment": "main",
                },
            },
        },
    }


def test_init_lake_cluster_sets_author_annotation(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    product["author"] = "operator@example.com"
    write_json(environment_dir / "product.json", product)
    set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    spec_json = read_json(environment_dir / "spec.json")
    annotations = spec_json["spec"]["resourceDefaults"]["annotations"]
    assert annotations["stelar.eu/author"] == "operator@example.com"


def test_init_lake_cluster_accepts_author_from_product_spec(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    product["spec"]["author"] = "spec-author@example.com"
    write_json(environment_dir / "product.json", product)
    set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    spec_json = read_json(environment_dir / "spec.json")
    annotations = spec_json["spec"]["resourceDefaults"]["annotations"]
    assert annotations["stelar.eu/author"] == "spec-author@example.com"


def test_init_lake_cluster_removes_placeholder_author_annotation(
    tmp_path,
    monkeypatch,
):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    spec_json = read_json(environment_dir / "spec.json")
    spec_json["spec"] = {
        "resourceDefaults": {
            "annotations": {"stelar.eu/author": "<author>", "keep": "value"}
        }
    }
    write_json(environment_dir / "spec.json", spec_json)
    set_cluster_preflight(monkeypatch)

    init_lake_cluster("dev", workspace)

    spec_json = read_json(environment_dir / "spec.json")
    annotations = spec_json["spec"]["resourceDefaults"]["annotations"]
    assert annotations == {"keep": "value"}


def test_init_lake_cluster_rejects_invalid_author(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    environment_dir = write_generated_lake_files(workspace)
    product = read_json(environment_dir / "product.json")
    product["author"] = ""
    write_json(environment_dir / "product.json", product)
    set_cluster_preflight(monkeypatch)

    with pytest.raises(CommandError, match="Product author"):
        init_lake_cluster("dev", workspace)


def test_init_lake_cluster_rejects_unknown_context(tmp_path, monkeypatch):
    workspace = make_workspace(tmp_path / "workspace")
    init_lake_environment("dev", workspace)
    write_generated_lake_files(workspace)
    set_cluster_preflight(monkeypatch, context_names=("current-context",))

    with pytest.raises(CommandError, match="does not exist"):
        init_lake_cluster("dev", workspace, context="missing-context")
