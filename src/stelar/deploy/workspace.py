"""Workspace discovery and validation helpers.

A STELAR deployment workspace contains `jsonnetfile.json`, generated
environments, and optional local Jsonnet code under `lib` and `vendor`.
"""

from __future__ import annotations

from os import PathLike
from pathlib import Path

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
