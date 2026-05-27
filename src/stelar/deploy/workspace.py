"""Workspace discovery and validation helpers.

A STELAR deployment workspace contains `jsonnetfile.json`, generated
environments, and optional local Jsonnet code under `lib` and `vendor`.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Iterable

from .environ import Environment

# A path-like argument can be a string or an os.PathLike object.
PathSpec = str | PathLike


class Workspace:
    """A workspace is a directory containing a number of STELAR environments.

    A workspace contains `jsonnetfile.json` and may also contain `lib` and
    `vendor` directories. The Jsonnet bundle file is the marker used by
    stelarctl to treat a directory as a workspace.
    """

    @classmethod
    def normalize_pathspec(cls, path: PathSpec | None) -> Path:
        """Return a path-like argument as a pathlib.Path.

        Parameters
        ----------
        path : PathSpec | None
            A path-like argument, or None to indicate the current directory.

        Returns
        -------
        Path            The path argument as a pathlib.Path.

        Raises
        ------
        TypeError        If the argument is not a string or os.PathLike object.
        """
        if path is None:
            path = Path()
        elif not isinstance(path, PathSpec):
            raise TypeError("Expected a string or a os.PathLike object")
        else:
            path = Path(path)
        return path

    @classmethod
    def check_path(cls, path: Path):
        """Check if the current workspace has a legal structure.

        A workspace must be a directory containing jsonnetfile.json.
        We may want to add more checks in the future, but this is a good start.

        Parameters
        ----------
        path : Path
             The path to check for workspace validity.

        Raises
        ------
        ValueError
             If the path is not a directory or does not contain jsonnetfile.json.
        """
        if not path.is_dir():
            raise ValueError(f"Workspace path {path} is not a directory")
        if not (path / "jsonnetfile.json").exists():
            raise ValueError(f"Workspace path {path} does not contain jsonnetfile.json")

    def __init__(self, path: PathSpec | None = None):
        """Create a workspace from a path-like argument.

        Parameters
        ----------
        path : PathSpec | None
            A path-like argument, or None to indicate the current directory.

        Raises
        ------
        TypeError
            If the argument is not a string or os.PathLike object.
        ValueError
            If the path is not a directory or does not contain jsonnetfile.json.
        """
        self.path = self.normalize_pathspec(path)
        self.check_path(self.path)

    @property
    def vendor(self) -> Path:
        """Return the path to the vendor directory of this workspace.

        Returns
        -------
        Path
            The path to the vendor directory of this workspace.
        """
        return self.path / "vendor"

    def environment_dirs(self) -> Iterable[Path]:
        """Find all environments in this workspace.

        An environment is a directory containing a `main.jsonnet` file.
        We search for environments recursively, so subdirectories of
        environments are also considered.

        Returns
        -------
        Iterable[Path]
            An iterable of paths to the environments in this workspace.
        """
        return (p for p in self.path.rglob("main.jsonnet") if p.is_file())

    def env(self, name: str) -> Environment:
        """Return the path to the environment with the given name.

        The name of an environment is the relative path from the workspace
        to the directory containing the main.jsonnet file, with path separators
        replaced by slashes. For example, if the workspace is at /home/user/workspace
        and there is an environment at /home/user/workspace/environments/prod/main.jsonnet,
        then the name of that environment is "environments/prod".

        Parameters
        ----------
        name : str
            The name of the environment to return.

        Returns
        -------
        Environment
            The environment with the given name.

        Raises
        ------
        ValueError
            If no environment with the given name exists in this workspace.
        """
        env_path = self.path / name / "main.jsonnet"
        if not env_path.is_file():
            raise ValueError(
                f"No environment named {name} found in workspace {self.path}"
            )
        return Environment(name, self)

    @property
    def klms_model_dir(self) -> Path:
        """Return the path to the model directory of this workspace.

        The model directory is a directory containing jsonnet files that define
        the features and their relationships. It is expected to be at ./model
        relative to the workspace root, but this is not strictly enforced.

        Returns
        -------
        Path
            The path to the model directory of this workspace.
        """
        return self.path / "models"
