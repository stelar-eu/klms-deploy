"""Helpers for the Tanka environment files managed by `stelarctl`.

The environment directory is the bridge between the high-level platform model
and Tanka. stelarctl owns the generated files there so status, deploy, and
teardown all agree on the same context and namespace.
"""

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
# `model.yaml` stores the last successful desired state; `spec.json` is the
# Tanka environment descriptor. Both names are intentionally stable because
# external scripts and operators may inspect them directly.


def ensure_env_dir(env_path: Path) -> None:
    """Create the environment directory if it does not already exist."""
    env_path.mkdir(parents=True, exist_ok=True)


def stored_model_path(env_path: Path) -> Path:
    """Return the path where the last successful desired model is stored."""
    return env_path / MODEL_FILENAME


def spec_path(env_path: Path) -> Path:
    """Return the path to the generated Tanka environment spec."""
    return env_path / SPEC_FILENAME


def load_stored_model(env_path: Path) -> PlatformModel | None:
    """Load the stored desired model for an environment, if one exists."""
    path = stored_model_path(env_path)
    if not path.exists():
        return None
    return load_model(str(path), PlatformModel)


def save_stored_model(env_path: Path, model: PlatformModel) -> Path:
    """Persist the desired model after a successful deploy."""
    ensure_env_dir(env_path)
    path = stored_model_path(env_path)
    # Preserve field order from the Pydantic model so diffs against the input
    # model remain readable and stable across deploys.
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(model.model_dump(mode="python"), handle, sort_keys=False)
    return path


def write_spec_json(env_path: Path, model: PlatformModel) -> Path:
    """Write Tanka `spec.json` from the validated platform model."""
    ensure_env_dir(env_path)
    path = spec_path(env_path)
    # Tanka treats spec.json as the environment descriptor. stelarctl writes it
    # from the model so status and teardown can later resolve the deployment
    # target without re-reading the original input YAML.
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
                # These defaults are injected into generated Kubernetes objects
                # by Tanka and make it easier to identify stelarctl-managed
                # resources during manual cluster inspection.
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
    """Read `spec.json` and return the single `(context, namespace)` target."""
    path = spec_path(env_path)
    if not path.exists():
        raise FileNotFoundError(f"spec.json not found in environment directory: {env_path}")
    with path.open(encoding="utf-8") as handle:
        spec = json.load(handle)

    context_names = spec.get("spec", {}).get("contextNames") or []
    namespace = spec.get("spec", {}).get("namespace")
    # stelarctl commands operate on exactly one deployment target at a time. A
    # multi-context Tanka environment would make status and teardown ambiguous.
    if len(context_names) != 1 or not namespace:
        raise ValueError(f"Invalid Tanka environment spec in {path}")
    return context_names[0], namespace
