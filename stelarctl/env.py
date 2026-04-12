from __future__ import annotations

import json
from pathlib import Path

import yaml

try:
    from .loader import load_model
    from .platform_model import PlatformModel
except ImportError:
    from loader import load_model
    from platform_model import PlatformModel


MODEL_FILENAME = "model.yaml"
SPEC_FILENAME = "spec.json"


def ensure_env_dir(env_path: Path) -> None:
    env_path.mkdir(parents=True, exist_ok=True)


def stored_model_path(env_path: Path) -> Path:
    return env_path / MODEL_FILENAME


def spec_path(env_path: Path) -> Path:
    return env_path / SPEC_FILENAME


def load_stored_model(env_path: Path) -> PlatformModel | None:
    path = stored_model_path(env_path)
    if not path.exists():
        return None
    return load_model(str(path), PlatformModel)


def save_stored_model(env_path: Path, model: PlatformModel) -> Path:
    ensure_env_dir(env_path)
    path = stored_model_path(env_path)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(model.model_dump(mode="python"), handle, sort_keys=False)
    return path


def write_spec_json(env_path: Path, model: PlatformModel) -> Path:
    ensure_env_dir(env_path)
    path = spec_path(env_path)
    payload = {
        "apiVersion": "tanka.dev/v1alpha1",
        "kind": "Environment",
        "metadata": {
            "name": str(env_path),
            "namespace": f"{env_path}/main.jsonnet",
        },
        "spec": {
            "contextNames": [model.k8s_context],
            "namespace": model.namespace,
            "resourceDefaults": {
                "annotations": {
                    "stelar.eu/author": model.author,
                },
                "labels": {
                    "app.kubernetes.io/managed-by": "tanka",
                    "app.kubernetes.io/part-of": "stelar",
                    "stelar.deployment": "main",
                },
            },
            "expectVersions": {},
            "injectLabels": True,
        },
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return path


def resolve_env_target(env_path: Path) -> tuple[str, str]:
    path = spec_path(env_path)
    if not path.exists():
        raise FileNotFoundError(f"spec.json not found in environment directory: {env_path}")
    with path.open(encoding="utf-8") as handle:
        spec = json.load(handle)

    context_names = spec.get("spec", {}).get("contextNames") or []
    namespace = spec.get("spec", {}).get("namespace")
    if len(context_names) != 1 or not namespace:
        raise ValueError(f"Invalid Tanka environment spec in {path}")
    return context_names[0], namespace
