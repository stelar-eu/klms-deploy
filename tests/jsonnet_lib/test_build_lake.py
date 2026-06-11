import json
from pathlib import Path

import pytest
from jsonnet import JsonnetRunner


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def stelar_vendor_root(tmp_path: Path) -> Path:
    vendor_root = tmp_path / "vendor-root"
    vendor_root.mkdir(parents=True)
    (vendor_root / "lib").symlink_to(REPO_ROOT / "lib", target_is_directory=True)
    return vendor_root


@pytest.fixture
def J(stelar_vendor_root: Path) -> JsonnetRunner:
    return JsonnetRunner(
        "tests/jsonnet_lib/test_build_lake.jsonnet",
        [str(stelar_vendor_root), str(REPO_ROOT / "vendor")],
        """
        local build_lake = import "lib/util/build_lake.libsonnet";
        """,
    )


def redis_fullspec(extra: str = "") -> str:
    return f"""
    {{
      klms: {{
        core_components: ["redis"],
        optional_components: [],
        cluster: [],
        redis: {{
          IMAGE: "redis:7",
          PORT: 6379,
        }},
        {extra}
      }},
    }}
    """


def redis_fullspec_data() -> dict:
    return {
        "klms": {
            "core_components": ["redis"],
            "optional_components": [],
            "cluster": [],
            "redis": {
                "IMAGE": "redis:7",
                "PORT": 6379,
            },
        },
    }


def environment_spec(fullspec: str, namespace: str = "test") -> str:
    return f"""
    {{
      spec: {{
        namespace: "{namespace}",
        stelar: {{ active_product: {fullspec} }},
      }},
    }}
    """


def test_build_lake_renders_selected_component_from_fullspec(J: JsonnetRunner):
    out = J(
        f"""
        local result = build_lake({environment_spec(redis_fullspec())});
        {{
          manifest_count: std.length(result.manifests),
          resource_keys: std.objectFields(result.manifests[0]),
          deployment_name: result.manifests[0].deployment.metadata.name,
          service_name: result.manifests[0].service.metadata.name,
          image: result.manifests[0].deployment.spec.template.spec.containers[0].image,
        }}
        """
    )

    assert out == {
        "manifest_count": 1,
        "resource_keys": ["deployment", "service"],
        "deployment_name": "redis",
        "service_name": "redis",
        "image": "redis:7",
    }


def test_build_lake_ignores_unselected_component_configuration(J: JsonnetRunner):
    out = J(
        f"""
        local result = build_lake({environment_spec(redis_fullspec('api: { IMAGE: "unused", PORT: 80 },'))});
        {{
          manifest_count: std.length(result.manifests),
          first_manifest_name: result.manifests[0].deployment.metadata.name,
        }}
        """
    )

    assert out == {
        "manifest_count": 1,
        "first_manifest_name": "redis",
    }


def test_build_lake_injects_environment_namespace_into_component_config(J: JsonnetRunner):
    out = J(
        f"""
        local fullspec = {{
          klms: {{
            support: {{}},
            core_components: [],
            optional_components: [],
            cluster: [],
            SCHEME: "http",
            api: {{ PORT: 80 }},
          }},
        }};
        local result = build_lake({environment_spec("fullspec", namespace="lake-ns")});
        {{
          manifest_count: std.length(result.manifests),
          network_policy_namespace: result.manifests[0].networkpolicy.metadata.namespace,
        }}
        """
    )

    assert out == {
        "manifest_count": 1,
        "network_policy_namespace": "lake-ns",
    }


def test_component_registry_includes_feature_model_component_entrypoints(
    J: JsonnetRunner,
):
    out = J(
        """
        local component_registry = import "lib/util/components.libsonnet";
        local feature_model_components = [
          "airflow",
          "previewer",
          "sde",
          "visualizer",
        ];
        {
          missing: [
            name
            for name in feature_model_components
            if !std.member(component_registry.get_names(), name)
          ],
        }
        """
    )

    assert out["missing"] == []


def test_main_template_imports_environment_spec_and_delegates_to_build_lake(
    tmp_path: Path,
    stelar_vendor_root: Path,
):
    environment = tmp_path / "env"
    environment.mkdir()
    template = REPO_ROOT / "lib" / "environment_templates" / "main_template.jsonnet"
    main_jsonnet = environment / "main.jsonnet"
    main_jsonnet.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    (environment / "spec.json").write_text(
        json.dumps({"spec": {"namespace": "test", "stelar": {"active_product": redis_fullspec_data()}}}),
        encoding="utf-8",
    )

    runner = JsonnetRunner(
        "tests/jsonnet_lib/test_main_template.jsonnet",
        [str(stelar_vendor_root), str(REPO_ROOT / "vendor")],
    )

    out = runner(
        f"""
        local result = import "{main_jsonnet.as_posix()}";
        {{
          manifest_count: std.length(result.manifests),
          deployment_name: result.manifests[0].deployment.metadata.name,
        }}
        """
    )

    assert out == {
        "manifest_count": 1,
        "deployment_name": "redis",
    }
