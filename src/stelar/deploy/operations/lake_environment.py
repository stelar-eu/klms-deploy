"""Business logic for lake environment initialization."""

from __future__ import annotations

import json
import shutil

from pathlib import Path

from ..workspace import Workspace
from .common import CommandError, validate_workspace
from .progress import LakeEnvironmentProgress

ENVIRONMENT_TEMPLATE_DIR = (
    Path("vendor")
    / "github.com"
    / "stelar-eu"
    / "klms-deploy"
    / "lib"
    / "environment_templates"
)
INITIALIZED_LAKE_ENVIRONMENT_FILES = ("main.jsonnet", "spec.json")
GENERATED_LAKE_ENVIRONMENT_FILES = ("product.json", "product_fullspec.json")
MAIN_JSONNET_TEMPLATE = "main_template.jsonnet"
SPEC_JSON_SKELETON = {
    "apiVersion": "tanka.dev/v1alpha1",
    "spec": {},
}


def init_lake_environment(
    environment: str,
    workspace_path: Path = Path("."),
    progress: LakeEnvironmentProgress | None = None,
) -> None:
    """Initialize a Tanka environment folder for a lake.

    Behavior:
    - Validate that workspace_path points to a valid workspace.
    - Create environments/<environment> when it does not exist.
    - Copy main_template.jsonnet from the vendored STELAR library as main.jsonnet.
    - Create a minimal spec.json skeleton when missing.
    - Do nothing when both files already exist.
    """
    progress = progress or LakeEnvironmentProgress()
    workspace = validate_workspace(workspace_path)
    environments_dir = _ensure_environments_dir(workspace, progress)
    environment_dir = _ensure_lake_environment_dir(
        environments_dir,
        environment,
        progress,
    )

    _ensure_main_jsonnet(workspace, environment_dir, progress)
    _ensure_spec_json(environment_dir, progress)


def initialized_lake_environment_dir(
    workspace: Workspace,
    environment: str,
) -> Path:
    environment_dir = (
        workspace.path / "environments" / normalize_lake_environment_name(environment)
    )

    if not environment_dir.is_dir():
        raise CommandError(
            f"Lake environment {environment!r} has not been initialized"
        )

    for filename in INITIALIZED_LAKE_ENVIRONMENT_FILES:
        path = environment_dir / filename
        if not path.is_file():
            raise CommandError(
                f"Lake environment {environment!r} is missing {filename}"
            )

    return environment_dir


def complete_lake_environment_dir(workspace: Workspace, environment: str) -> Path:
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    for filename in GENERATED_LAKE_ENVIRONMENT_FILES:
        path = environment_dir / filename
        if not path.is_file():
            raise CommandError(
                f"Lake environment {environment!r} is missing {filename}"
            )
    return environment_dir


def normalize_lake_environment_name(environment: str) -> Path:
    environment_name = environment.strip()
    if not environment_name:
        raise CommandError("Environment name cannot be empty")

    environment_path = Path(environment_name)
    if environment_path.is_absolute():
        raise CommandError("Environment name must be relative")

    parts = environment_path.parts
    if parts and parts[0] == "environments":
        parts = parts[1:]

    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise CommandError(f"Invalid environment name {environment!r}")

    return Path(*parts)


def _ensure_environments_dir(
    workspace: Workspace,
    progress: LakeEnvironmentProgress,
) -> Path:
    environments_dir = workspace.path / "environments"
    if environments_dir.exists():
        if not environments_dir.is_dir():
            raise CommandError(f"{environments_dir} exists but is not a directory")
        progress.directory_exists(str(environments_dir))
        return environments_dir

    try:
        progress.creating_directory(str(environments_dir))
        environments_dir.mkdir()
    except OSError as exc:
        raise CommandError(f"Could not create {environments_dir}: {exc}") from exc
    progress.directory_created(str(environments_dir))

    return environments_dir


def _ensure_lake_environment_dir(
    environments_dir: Path,
    environment: str,
    progress: LakeEnvironmentProgress,
) -> Path:
    environment_path = environments_dir / normalize_lake_environment_name(environment)
    if environment_path.exists():
        if not environment_path.is_dir():
            raise CommandError(f"{environment_path} exists but is not a directory")
        progress.directory_exists(str(environment_path))
        return environment_path

    try:
        progress.creating_directory(str(environment_path))
        environment_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise CommandError(f"Could not create {environment_path}: {exc}") from exc
    progress.directory_created(str(environment_path))

    return environment_path


def _ensure_main_jsonnet(
    workspace: Workspace,
    environment_dir: Path,
    progress: LakeEnvironmentProgress,
) -> None:
    main_jsonnet_path = environment_dir / "main.jsonnet"
    if main_jsonnet_path.exists():
        if not main_jsonnet_path.is_file():
            raise CommandError(f"{main_jsonnet_path} exists but is not a file")
        progress.file_exists(str(main_jsonnet_path))
        return

    _copy_environment_template(
        workspace,
        MAIN_JSONNET_TEMPLATE,
        main_jsonnet_path,
        progress,
    )


def _ensure_spec_json(environment_dir: Path, progress: LakeEnvironmentProgress) -> None:
    # `spec.json` starts as a minimal Tanka skeleton. `init-lake cluster` later
    # fills in cluster-specific state such as context, namespace, and metadata.
    spec_json_path = environment_dir / "spec.json"
    if spec_json_path.exists():
        if not spec_json_path.is_file():
            raise CommandError(f"{spec_json_path} exists but is not a file")
        progress.file_exists(str(spec_json_path))
        return

    try:
        progress.writing_file(str(spec_json_path))
        spec_json_path.write_text(
            f"{json.dumps(SPEC_JSON_SKELETON, indent=2)}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CommandError(f"Could not create {spec_json_path}: {exc}") from exc
    progress.file_written(str(spec_json_path))


def _copy_environment_template(
    workspace: Workspace,
    template_name: str,
    destination: Path,
    progress: LakeEnvironmentProgress,
) -> None:
    source = workspace.path / ENVIRONMENT_TEMPLATE_DIR / template_name
    if not source.is_file():
        raise CommandError(
            f"Environment template {source} does not exist. Run jb install first."
        )

    try:
        progress.copying_template(str(source), str(destination))
        shutil.copyfile(source, destination)
    except OSError as exc:
        raise CommandError(f"Could not create {destination}: {exc}") from exc
    progress.template_copied(str(destination))
