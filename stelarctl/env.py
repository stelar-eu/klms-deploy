import json
import re
from pathlib import Path
from typing import Optional

import typer

from platform_model import PlatformModel


def normalized_target_part(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9.-]+", "-", value.lower()).strip("-.")
    return normalized or "default"


def default_env_path(model: PlatformModel) -> Path:
    env_name = f"{normalized_target_part(model.k8s_context)}.{normalized_target_part(model.namespace)}"
    return Path("environments") / env_name


def spec_path(env: Path) -> Path:
    return env / "spec.json"


def read_env_target(env: Path) -> tuple[str, str] | None:
    path = spec_path(env)
    if not path.exists():
        return None

    with path.open(encoding="utf-8") as handle:
        spec = json.load(handle)

    context_names = spec.get("spec", {}).get("contextNames") or []
    namespace = spec.get("spec", {}).get("namespace")
    if len(context_names) != 1 or not namespace:
        raise typer.BadParameter(f"Invalid Tanka environment spec: {path}")
    return context_names[0], namespace


def resolve_deploy_env(model: PlatformModel, env: Optional[Path]) -> Path:
    env_path = env or default_env_path(model)
    existing_target = read_env_target(env_path)
    expected_target = (model.k8s_context, model.namespace)

    if existing_target and existing_target != expected_target:
        raise typer.BadParameter(
            f"Environment {env_path} targets {existing_target[0]}/{existing_target[1]}, "
            f"but the model targets {model.k8s_context}/{model.namespace}."
        )

    return env_path
