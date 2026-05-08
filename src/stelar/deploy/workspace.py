#
# A workspace specifies an installation of information containing (a) a set of environments
# (b) additional jsonnet code in the ./lib and ./vendor directories.
# The source distribution of klms-deploy is an example of a workspace.
#
# A workspace is the base for an execution of stelarctl, and provides
# necessary information. The workspace is created at the beginning of execution.
#

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    pass

from os import PathLike

from .environ import Environment

# A path-like argument can be a string or an os.PathLike object.
PathSpec = str | PathLike


class Workspace:
    """A workspace is a directory containing a number of STELAR environments.

    A workspace is a directory containing a `jsonnetfile.yaml`.
    Also,  optionally,  `lib` and `vendor` directories.
    Note that the existence of `jsonnetfile.yaml` is used by Tanka to
    determine its `<rootDir>`.
    """

    @classmethod
    def normalize_pathspec(cls, path: PathSpec | None) -> Path:
        """Return a path-like argument as a pathlib.Path

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

        A workspace must be a directory containing a jsonnetfile.yaml.
        We may want to add more checks in the future, but this is a good start.

        Parameters
        ----------
        path : Path
             The path to check for workspace validity.

        Raises
        ------
        ValueError
             If the path is not a directory or does not contain a jsonnetfile.yaml.
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
            If the path is not a directory or does not contain a jsonnetfile.yaml.
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
