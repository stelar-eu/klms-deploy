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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from os import PathLike

# A path-like argument can be a string or an os.PathLike object.
PathSpec = str|PathLike


class Workspace:
    """A workspace object represents a directory containing a number of STELAR environments.
    
    A workspace is a directory containing a jsonnetfile.yaml and optional lib and vendor directories.
    Note that the existence of `jsonnetfile.yaml` is checked by Tanka to determine its <rootDir>.
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
        if not (path/"jsonnetfile.json").exists():
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
    
