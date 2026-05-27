"""Shared helpers for stelarctl commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..environ import Environment
from ..models.product import Product
from ..workspace import Workspace

JsonObject = dict[str, Any]


class CommandError(ValueError):
    """Raised when command input cannot be processed."""


def validate_workspace(workspace_path: Path) -> Workspace:
    """Validate and load a workspace."""
    try:
        return Workspace(workspace_path)
    except (TypeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc


def load_product(product_path: Path) -> Product:
    """Load and validate a product JSON/YAML file."""
    product_data = load_product_data(product_path)
    return validate_product_data(product_path, product_data)


def load_product_data(product_path: Path) -> JsonObject:
    """Load a product JSON/YAML file as raw data."""
    try:
        with product_path.open("r", encoding="utf-8") as product_file:
            product_data = yaml.safe_load(product_file)
    except OSError as exc:
        raise CommandError(
            f"Could not read product file {product_path}: {exc}"
        ) from exc

    if product_data is None:
        raise CommandError(f"Product file {product_path} is empty")

    if not isinstance(product_data, dict):
        raise CommandError(f"Product file {product_path} must contain an object")

    return product_data


def validate_environment(workspace_path: Path, environment: str) -> Environment:
    """Validate that a workspace and environment exist."""
    workspace = validate_workspace(workspace_path)
    try:
        return workspace.env(environment)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc


def validate_product_data(product_path: Path, product_data: JsonObject) -> Product:
    try:
        return Product.model_validate(product_data)
    except ValidationError as exc:
        raise CommandError(f"Invalid product file {product_path}: {exc}") from exc


def write_environment_json(path: Path, data: JsonObject) -> None:
    try:
        path.write_text(f"{json.dumps(data, indent=2)}\n", encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"Could not write {path}: {exc}") from exc


def read_environment_json(path: Path) -> JsonObject:
    try:
        with path.open("r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except OSError as exc:
        raise CommandError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CommandError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CommandError(f"{path} must contain an object")

    return data


def product_spec(product_data: JsonObject) -> JsonObject:
    spec = product_data.get("spec")
    if not isinstance(spec, dict):
        raise CommandError("Product file must contain a spec object")
    return spec


def product_author(product_data: JsonObject) -> str | None:
    author = product_data.get("author")
    if author is None:
        author = product_spec(product_data).get("author")
    if author is None:
        return None
    if not isinstance(author, str) or not author:
        raise CommandError("Product author must be a non-empty string")
    return author


def ensure_object(data: JsonObject, key: str) -> JsonObject:
    value = data.setdefault(key, {})
    if not isinstance(value, dict):
        raise CommandError(f"Expected {key} to contain an object")
    return value


def existing_object(data: JsonObject, key: str) -> JsonObject:
    value = data.get(key)
    if not isinstance(value, dict):
        raise CommandError(f"Expected {key} to contain an object")
    return value
