"""Business logic for lake environment initialization."""

from __future__ import annotations

import json
import shutil
import sys

from pathlib import Path

from ..workspace import Workspace
from .common import (
    CommandError,
    ensure_object,
    read_environment_json,
    validate_workspace,
    write_environment_json,
)
from .environment_spec import validate_environment_target_fields
from .progress import LakeEnvironmentProgress

ENVIRONMENT_TEMPLATE_DIR = Path("vendor") / "lib" / "environment_templates"
INITIALIZED_LAKE_ENVIRONMENT_FILES = ("main.jsonnet", "spec.json")
MAIN_JSONNET_TEMPLATE = "main_template.jsonnet"
LAKE_ENVIRONMENT_ANNOTATION = "stelar.eu/lake-environment"
LAKE_ENVIRONMENT_ANNOTATION_VALUE = "true"
_WARNED_UNMANAGED_MAIN_JSONNET: set[Path] = set()
SPEC_JSON_SKELETON = {
    "apiVersion": "tanka.dev/v1alpha1",
    "metadata": {
        "annotations": {
            LAKE_ENVIRONMENT_ANNOTATION: LAKE_ENVIRONMENT_ANNOTATION_VALUE,
        },
    },
    "spec": {},
}


def add_lake_environment(
    environment: str,
    workspace_path: Path = Path("."),
    progress: LakeEnvironmentProgress | None = None,
    *,
    adopt_existing_main: bool = False,
    context_name: str | None = None,
    namespace: str | None = None,
) -> None:
    """Initialize a Tanka environment folder for a lake.

    Behavior:
    - Validate that workspace_path points to a valid workspace.
    - Create <environment> relative to the workspace when it does not exist.
    - Copy main_template.jsonnet from the vendored STELAR library as main.jsonnet.
    - Create a minimal spec.json skeleton when missing.
    - Preserve existing valid spec.json files and add the lake marker when missing.
    - Refuse implicit adoption when main.jsonnet already exists without the marker.
    """
    progress = progress or LakeEnvironmentProgress()
    context_name, namespace = validate_environment_target_fields(
        context_name=context_name,
        namespace=namespace,
    )
    workspace = validate_workspace(workspace_path)
    environment_dir = _ensure_lake_environment_dir(
        workspace.path,
        environment,
        progress,
    )

    spec_json_path = environment_dir / "spec.json"
    _validate_existing_main_jsonnet_adoption(
        workspace,
        environment_dir,
        adopt_existing_main=adopt_existing_main,
    )
    _ensure_main_jsonnet(workspace, environment_dir, progress)
    _ensure_spec_json(environment_dir, progress)
    _warn_if_unmanaged_main_jsonnet(workspace, environment_dir)
    _write_target_fields_if_requested(
        spec_json_path,
        context_name=context_name,
        namespace=namespace,
    )


def remove_lake_environment(
    environment: str,
    workspace_path: Path = Path("."),
    progress: LakeEnvironmentProgress | None = None,
    *,
    force: bool = False,
) -> None:
    """Delete an initialized, stelarctl-marked lake environment directory."""
    progress = progress or LakeEnvironmentProgress()
    workspace = validate_workspace(workspace_path)
    environment_dir = initialized_lake_environment_dir(workspace, environment)
    if not force:
        _reject_unsafe_environment_removal(environment, environment_dir)

    try:
        progress.removing_environment(str(environment_dir))
        shutil.rmtree(environment_dir)
    except OSError as exc:
        raise CommandError(f"Could not remove {environment_dir}: {exc}") from exc
    progress.environment_removed(str(environment_dir))



def _reject_unsafe_environment_removal(
    environment: str,
    environment_dir: Path,
) -> None:
    spec_json = read_environment_json(environment_dir / "spec.json")
    stelar_spec = spec_json.get("spec", {})
    if isinstance(stelar_spec, dict):
        stelar_spec = stelar_spec.get("stelar", {})
    if not isinstance(stelar_spec, dict):
        stelar_spec = {}

    reasons = []
    if "active_product" in stelar_spec or "current_product" in stelar_spec or "active_product_name" in stelar_spec:
        reasons.append("an active product")
    if not reasons:
        return

    reason_text = " and ".join(reasons)
    raise CommandError(
        f"Refusing to remove lake environment {environment!r} because it still "
        f"contains {reason_text}. Remove Kubernetes resources with `tk delete "
        "ENV`, unbootstrap the namespace with `stelarctl lake unbootstrap ENV`, "
        "then rerun. Use --force only if you intentionally want to discard "
        "local metadata."
    )


def initialized_lake_environment_dir(
    workspace: Workspace,
    environment: str,
) -> Path:
    environment_dir = workspace.path / normalize_lake_environment_name(environment)

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

    spec_json = environment_dir / "spec.json"
    if not is_lake_environment_spec(spec_json):
        raise CommandError(
            f"Lake environment {environment!r} is missing the stelarctl marker"
        )
    _warn_if_unmanaged_main_jsonnet(workspace, environment_dir)

    return environment_dir


def normalize_lake_environment_name(environment: str) -> Path:
    environment_name = environment.strip()
    if not environment_name:
        raise CommandError("Environment name cannot be empty")

    environment_path = Path(environment_name)
    if environment_path.is_absolute():
        raise CommandError("Environment name must be relative")

    parts = environment_path.parts

    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise CommandError(f"Invalid environment name {environment!r}")

    return Path(*parts)


def is_lake_environment_spec(spec_json_path: Path) -> bool:
    try:
        with spec_json_path.open("r", encoding="utf-8") as spec_file:
            spec_json = json.load(spec_file)
    except (OSError, json.JSONDecodeError):
        return False

    if not isinstance(spec_json, dict):
        return False
    metadata = spec_json.get("metadata")
    if not isinstance(metadata, dict):
        return False
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return False
    return (
        annotations.get(LAKE_ENVIRONMENT_ANNOTATION)
        == LAKE_ENVIRONMENT_ANNOTATION_VALUE
    )


def _ensure_spec_json_marker(spec_json_path: Path) -> bool:
    try:
        with spec_json_path.open("r", encoding="utf-8") as spec_file:
            spec_json = json.load(spec_file)
    except OSError as exc:
        raise CommandError(f"Could not read {spec_json_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in {spec_json_path}: {exc}") from exc

    if not isinstance(spec_json, dict):
        raise CommandError(f"{spec_json_path} must contain an object")

    metadata = spec_json.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise CommandError(f"{spec_json_path} metadata must contain an object")

    annotations = metadata.setdefault("annotations", {})
    if not isinstance(annotations, dict):
        raise CommandError(
            f"{spec_json_path} metadata.annotations must contain an object"
        )

    if (
        annotations.get(LAKE_ENVIRONMENT_ANNOTATION)
        == LAKE_ENVIRONMENT_ANNOTATION_VALUE
    ):
        return False

    annotations[LAKE_ENVIRONMENT_ANNOTATION] = LAKE_ENVIRONMENT_ANNOTATION_VALUE
    try:
        spec_json_path.write_text(
            f"{json.dumps(spec_json, indent=2)}\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise CommandError(f"Could not write {spec_json_path}: {exc}") from exc
    return True


def _ensure_lake_environment_dir(
    workspace_dir: Path,
    environment: str,
    progress: LakeEnvironmentProgress,
) -> Path:
    environment_path = workspace_dir / normalize_lake_environment_name(environment)
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


def _validate_existing_main_jsonnet_adoption(
    workspace: Workspace,
    environment_dir: Path,
    *,
    adopt_existing_main: bool,
) -> None:
    main_jsonnet_path = environment_dir / "main.jsonnet"
    if not main_jsonnet_path.exists() or not main_jsonnet_path.is_file():
        return

    spec_json_path = environment_dir / "spec.json"
    if spec_json_path.exists() and not spec_json_path.is_file():
        return
    if is_lake_environment_spec(spec_json_path):
        return

    if adopt_existing_main:
        _validate_managed_main_jsonnet(workspace, main_jsonnet_path)
        return

    raise CommandError(
        f"{main_jsonnet_path} already exists, but {spec_json_path} is not "
        "marked as a stelarctl lake environment. Refusing to adopt an "
        "existing Tanka entrypoint implicitly. Rerun with "
        "--adopt-existing-main if this directory should be managed by stelarctl."
    )



def _validate_managed_main_jsonnet(
    workspace: Workspace,
    main_jsonnet_path: Path,
) -> None:
    mismatch = _managed_main_jsonnet_mismatch(workspace, main_jsonnet_path)
    if mismatch is None:
        return
    raise CommandError(
        f"{main_jsonnet_path} does not match the managed stelarctl entrypoint "
        "template. Refusing to adopt it because `tk apply` may render "
        "resources that are unrelated to spec.stelar.active_product."
    )


def _warn_if_unmanaged_main_jsonnet(
    workspace: Workspace,
    environment_dir: Path,
) -> None:
    main_jsonnet_path = environment_dir / "main.jsonnet"
    warned_path = main_jsonnet_path.resolve()
    if warned_path in _WARNED_UNMANAGED_MAIN_JSONNET:
        return

    mismatch = _managed_main_jsonnet_mismatch(workspace, main_jsonnet_path)
    if mismatch is None:
        return

    _WARNED_UNMANAGED_MAIN_JSONNET.add(warned_path)
    print(
        "Warning: "
        f"{main_jsonnet_path} is marked as a stelarctl lake environment, "
        f"but {mismatch}. `tk apply` may render resources unrelated to "
        "spec.stelar.active_product. Restore main.jsonnet from the managed "
        "stelarctl template if this environment should be fully managed.",
        file=sys.stderr,
    )


def _managed_main_jsonnet_mismatch(
    workspace: Workspace,
    main_jsonnet_path: Path,
) -> str | None:
    expected_path = workspace.path / ENVIRONMENT_TEMPLATE_DIR / MAIN_JSONNET_TEMPLATE
    try:
        expected = expected_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"the managed template {expected_path} could not be read: {exc}"
    try:
        current = main_jsonnet_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"main.jsonnet could not be read: {exc}"

    if current == expected:
        return None
    return "main.jsonnet does not match the managed stelarctl entrypoint template"


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
    # `spec.json` starts as a minimal Tanka skeleton. `lake bootstrap` later
    # fills in cluster-specific state such as context, namespace, and metadata.
    spec_json_path = environment_dir / "spec.json"
    if spec_json_path.exists():
        if not spec_json_path.is_file():
            raise CommandError(f"{spec_json_path} exists but is not a file")
        marker_added = _ensure_spec_json_marker(spec_json_path)
        progress.file_exists(str(spec_json_path))
        if marker_added:
            progress.existing_spec_adopted(str(spec_json_path))
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





def _write_target_fields_if_requested(
    spec_json_path: Path,
    *,
    context_name: str | None,
    namespace: str | None,
) -> None:
    context_name = _optional_target_value(context_name, "context")
    namespace = _optional_target_value(namespace, "namespace")
    if context_name is None and namespace is None:
        return

    spec_json = read_environment_json(spec_json_path)
    tk_spec = ensure_object(spec_json, "spec")
    if context_name is not None:
        tk_spec["contextNames"] = [context_name]
    if namespace is not None:
        tk_spec["namespace"] = namespace
    write_environment_json(spec_json_path, spec_json)


def _optional_target_value(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"Lake environment {field_name} must be a non-empty string")
    return value.strip()


def _copy_template_file(
    workspace: Workspace,
    template_name: str,
    destination: Path,
) -> None:
    source = workspace.path / ENVIRONMENT_TEMPLATE_DIR / template_name
    if not source.is_file():
        raise CommandError(
            f"Environment template {source} does not exist. Run jb install first."
        )

    try:
        shutil.copyfile(source, destination)
    except OSError as exc:
        raise CommandError(f"Could not create {destination}: {exc}") from exc


def _copy_environment_template(
    workspace: Workspace,
    template_name: str,
    destination: Path,
    progress: LakeEnvironmentProgress,
) -> None:
    source = workspace.path / ENVIRONMENT_TEMPLATE_DIR / template_name
    progress.copying_template(str(source), str(destination))
    _copy_template_file(workspace, template_name, destination)
    progress.template_copied(str(destination))
