import json
from pathlib import Path

import pytest
from jsonnet import JsonnetRunner


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def stelar_vendor_root(tmp_path: Path) -> Path:
    vendor_root = tmp_path / "vendor-root"
    stelar_org = vendor_root / "github.com" / "stelar-eu"
    stelar_org.mkdir(parents=True)
    (stelar_org / "klms-deploy").symlink_to(REPO_ROOT, target_is_directory=True)
    return vendor_root


@pytest.fixture
def J(stelar_vendor_root: Path) -> JsonnetRunner:
    return JsonnetRunner(
        "tests/jsonnet_lib/test_build_lake.jsonnet",
        [str(stelar_vendor_root), str(REPO_ROOT / "vendor")],
        """
        local build_lake = import "github.com/stelar-eu/klms-deploy/lib/util/build_lake.libsonnet";
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


def test_build_lake_renders_selected_component_from_fullspec(J: JsonnetRunner):
    out = J(
        f"""
        local result = build_lake({redis_fullspec()});
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
        local result = build_lake({redis_fullspec('api: { IMAGE: "unused", PORT: 80 },')});
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


def test_main_template_imports_fullspec_and_delegates_to_build_lake(
    tmp_path: Path,
    stelar_vendor_root: Path,
):
    environment = tmp_path / "env"
    environment.mkdir()
    template = REPO_ROOT / "lib" / "environment_templates" / "main_template.jsonnet"
    main_jsonnet = environment / "main.jsonnet"
    main_jsonnet.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    (environment / "product_fullspec.json").write_text(
        json.dumps(redis_fullspec_data()),
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
