"""Progress hooks for deployment operations."""

from __future__ import annotations

from typing import Any


def _noop(*_args: Any, **_kwargs: Any) -> None:
    return None


class _NoOpProgress:
    """Base progress reporter that ignores hooks not implemented by subclasses."""

    def __getattr__(self, _name: str):
        return _noop


class ClusterProgress(_NoOpProgress):
    """No-op progress reporter for cluster bootstrap."""


class LakeActivationProgress(_NoOpProgress):
    """No-op progress reporter for lake product activation."""


class LakeEnvironmentProgress(_NoOpProgress):
    """No-op progress reporter for lake environment initialization."""


class LakeWorkspaceProgress(_NoOpProgress):
    """No-op progress reporter for lake workspace initialization."""
