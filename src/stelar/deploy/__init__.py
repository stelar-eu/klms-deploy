"""STELAR deployment tooling package.

The package exposes the packaged STELAR feature model and the `stelarctl` CLI.
Operator usage is documented in `docs/stelarctl.md` at the repository root.
"""

from pathlib import Path

from .models.feature import load_feature_model

_MODULE_DIR = Path(__file__).resolve().parent
_DATA_PATH = _MODULE_DIR / "STELAR.yaml"

feature_model = load_feature_model(_DATA_PATH)
