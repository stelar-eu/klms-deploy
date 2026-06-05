"""Business logic for lake workspace initialization and inspection."""

from __future__ import annotations

import json
import pkgutil
from dataclasses import dataclass
from pathlib import Path

from .common import CommandError, validate_workspace
from .lake_environment import (
    initialized_lake_environment_dir,
    is_lake_environment_spec,
)
from .progress import LakeWorkspaceProgress

WORKSPACE_TEMPLATE_PACKAGE = "stelar.deploy"
JSONNETFILE_TEMPLATE = "templates/jsonnetfile.json"


@dataclass(frozen=True)
class WorkspaceEnvironmentInfo:
    """Filesystem state for one Tanka environment inside a workspace."""

    name: str
    path: Path
    main_jsonnet: bool
    spec_json: bool
    product_json: bool
    product_fullspec_json: bool


@dataclass(frozen=True)
class WorkspaceInfo:
    """Filesystem state for a STELAR deployment workspace."""

    path: Path
    initialized: bool
    jsonnetfile: bool
    lib: bool
    vendor: bool
    environments_dir: bool
    environments: tuple[WorkspaceEnvironmentInfo, ...]


def init_lake_workspace(
    workspace_path: Path,
    *,
    force: bool = False,
    progress: LakeWorkspaceProgress | None = None,
) -> None:
    """Initialize a workspace directory for lake deployment files."""
    progress = progress or LakeWorkspaceProgress()
    workspace = Path(workspace_path)

    _ensure_directory(workspace, progress)
    _ensure_directory(workspace / "lib", progress)
    _ensure_jsonnetfile(workspace / "jsonnetfile.json", force, progress)


def workspace_info(workspace_path: Path) -> WorkspaceInfo:
    """Return read-only filesystem information for a workspace path."""
    workspace = Path(workspace_path)
    jsonnetfile = workspace / "jsonnetfile.json"
    if not workspace.is_dir():
        raise CommandError(f"Workspace path {workspace} is not a directory")
    environments = _marked_environment_infos(workspace)
    return WorkspaceInfo(
        path=workspace,
        initialized=jsonnetfile.is_file(),
        jsonnetfile=jsonnetfile.is_file(),
        lib=(workspace / "lib").is_dir(),
        vendor=(workspace / "vendor").is_dir(),
        environments_dir=(workspace / "environments").is_dir(),
        environments=environments,
    )


def list_lake_environments(
    workspace_path: Path = Path("."),
) -> tuple[WorkspaceEnvironmentInfo, ...]:
    """Return stelarctl-marked lake environments in an initialized workspace."""
    workspace = validate_workspace(workspace_path)
    return _marked_environment_infos(workspace.path)


def lake_environment_info(
    environment: str,
    workspace_path: Path = Path("."),
) -> WorkspaceEnvironmentInfo:
    """Return filesystem information for one initialized lake environment."""
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    return _environment_info(workspace.path, environment_dir)


def _marked_environment_infos(workspace: Path) -> tuple[WorkspaceEnvironmentInfo, ...]:
    spec_files = [
        spec_json
        for spec_json in sorted(workspace.rglob("spec.json"))
        if is_lake_environment_spec(spec_json)
    ]
    return tuple(
        _environment_info(workspace, spec_json.parent) for spec_json in spec_files
    )


def _environment_info(
    workspace: Path,
    environment_dir: Path,
) -> WorkspaceEnvironmentInfo:
    name = environment_dir.relative_to(workspace).as_posix()
    main_jsonnet = environment_dir / "main.jsonnet"
    return WorkspaceEnvironmentInfo(
        name=name,
        path=environment_dir,
        main_jsonnet=main_jsonnet.is_file(),
        spec_json=(environment_dir / "spec.json").is_file(),
        product_json=(environment_dir / "product.json").is_file(),
        product_fullspec_json=(environment_dir / "product_fullspec.json").is_file(),
    )


def _ensure_directory(path: Path, progress: LakeWorkspaceProgress) -> None:
    if path.exists():
        if not path.is_dir():
            raise CommandError(f"{path} exists but is not a directory")
        progress.directory_exists(str(path))
        return

    try:
        progress.creating_directory(str(path))
        path.mkdir(parents=True)
    except OSError as exc:
        raise CommandError(f"Could not create {path}: {exc}") from exc
    progress.directory_created(str(path))


def _ensure_jsonnetfile(
    path: Path,
    force: bool,
    progress: LakeWorkspaceProgress,
) -> None:
    rewriting = False
    if path.exists():
        if not path.is_file():
            raise CommandError(f"{path} exists but is not a file")
        if not force:
            _merge_jsonnetfile_dependencies(path, progress)
            return
        rewriting = True
        progress.rewriting_file(str(path))
    else:
        progress.writing_file(str(path))

    try:
        path.write_text(_jsonnetfile_template(), encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"Could not write {path}: {exc}") from exc

    if rewriting:
        progress.file_rewritten(str(path))
    else:
        progress.file_written(str(path))


def _jsonnetfile_template() -> str:
    data = pkgutil.get_data(WORKSPACE_TEMPLATE_PACKAGE, JSONNETFILE_TEMPLATE)
    if data is None:
        raise CommandError(
            f"Packaged workspace template {JSONNETFILE_TEMPLATE!r} is missing"
        )
    return data.decode("utf-8")


def _merge_jsonnetfile_dependencies(
    path: Path,
    progress: LakeWorkspaceProgress,
) -> None:
    existing = _read_jsonnetfile(path)
    template = _read_jsonnetfile_template()
    existing_dependencies = _dependencies(existing, path)
    required_dependencies = _dependencies(template, Path(JSONNETFILE_TEMPLATE))

    # Dependency source identifies the library; version pins are intentionally
    # preserved when the user already has that source in jsonnetfile.json.
    missing_dependencies = [
        dependency
        for dependency in required_dependencies
        if not _has_dependency(existing_dependencies, dependency)
    ]

    if not missing_dependencies:
        progress.file_exists(str(path))
        return

    existing_dependencies.extend(missing_dependencies)
    existing["dependencies"] = existing_dependencies
    existing.setdefault("version", template.get("version", 1))
    existing.setdefault("legacyImports", template.get("legacyImports", True))

    try:
        progress.updating_file(str(path))
        path.write_text(f"{json.dumps(existing, indent=2)}\n", encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"Could not write {path}: {exc}") from exc
    progress.file_updated(str(path))


def _read_jsonnetfile(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as jsonnetfile:
            data = json.load(jsonnetfile)
    except OSError as exc:
        raise CommandError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CommandError(f"{path} must contain an object")

    return data


def _read_jsonnetfile_template() -> dict:
    try:
        data = json.loads(_jsonnetfile_template())
    except json.JSONDecodeError as exc:
        raise CommandError(
            f"Packaged workspace template {JSONNETFILE_TEMPLATE!r} is invalid JSON: "
            f"{exc}"
        ) from exc

    if not isinstance(data, dict):
        raise CommandError(
            f"Packaged workspace template {JSONNETFILE_TEMPLATE!r} must "
            "contain an object"
        )

    return data


def _dependencies(data: dict, path: Path) -> list[dict]:
    dependencies = data.get("dependencies")
    if dependencies is None:
        dependencies = []
    if not isinstance(dependencies, list):
        raise CommandError(f"{path} dependencies must be a list")
    if not all(isinstance(dependency, dict) for dependency in dependencies):
        raise CommandError(f"{path} dependencies must contain objects")
    return dependencies


def _has_dependency(
    existing_dependencies: list[dict],
    required_dependency: dict,
) -> bool:
    required_source = required_dependency.get("source")
    return any(
        dependency.get("source") == required_source
        for dependency in existing_dependencies
    )
