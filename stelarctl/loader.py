"""YAML loading and Pydantic validation helpers.

All CLI commands that accept a platform model pass through this module, so YAML
parsing and validation failures are handled consistently before any command can
touch the filesystem or Kubernetes.
"""

import yaml
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar

M = TypeVar("M", bound=BaseModel)


def load_model(path: str, model_class: Type[M]) -> M:
    """Load a YAML file and instantiate the requested Pydantic model class."""
    # safe_load avoids executing YAML tags and returns plain Python structures
    # that Pydantic can validate against the requested schema.
    with open(path) as f:
        raw = yaml.safe_load(f)

    try:
        return model_class(**raw)
    except ValidationError as e:
        # Print Pydantic's field-level diagnostics and exit with a CLI-friendly
        # non-zero status. Raising SystemExit here keeps command handlers small
        # and avoids partially initialized model objects.
        print(e)
        raise SystemExit(1)
