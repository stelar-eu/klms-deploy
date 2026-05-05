"""STELAR operator tooling package.

`stelarctl` is the operator-facing CLI for STELAR KLMS deployments.
See ARCHITECTURE.txt for the deployment flow and design decisions,
and DOCS.md for per-module reference.
"""

from pathlib import Path

from .models.feature import load_feature_model

# Directory where this module resides
_MODULE_DIR = Path(__file__).resolve().parent
# Path to JSON file (e.g., in same directory or a subfolder)
_DATA_PATH = _MODULE_DIR / "STELAR.yaml"

# Load at import time
feature_model = load_feature_model(_DATA_PATH)
