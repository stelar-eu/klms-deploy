#
# Environments are folders in a workspace that contain the
# configuration for a tanka operation.
#
# Some environments are STELAR deployments, but not all.
# For example, a workspace may contain an environment for some
# kubernetes service that the KLMS works with. Other environments
# may be used to install utilities that the KLMS depends on, such
# as cert-manager, some storage class operator, etc.
#

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workspace import Workspace


class Environment:
    """An environment has a workspace and a name. The name is the relative
    path from the workspace to the environment directory. The environment
    directory must contain a main.jsonnet file, which is the entry point
    for the tanka.
    """

    def __init__(self, name: str, workspace: Workspace):
        self.name = name
        self.workspace = workspace
