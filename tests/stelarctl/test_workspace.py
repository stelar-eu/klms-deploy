from pathlib import Path

import pytest


def test_normalize_pathspec(tmp_path):
    from stelar.deploy.workspace import Workspace

    # Test with None
    assert Workspace.normalize_pathspec(None) == Path(".")

    # Test with a string path
    assert Workspace.normalize_pathspec("my/path") == Path("my/path")

    # Test with a Path object
    assert Workspace.normalize_pathspec(Path("my/path")) == Path("my/path")

    # Test with an absolute path
    abs_path = tmp_path / "absolute/path"
    assert Workspace.normalize_pathspec(str(abs_path)) == abs_path

def test_check_path(tmp_path):
    from stelar.deploy.workspace import Workspace

    # Create a valid workspace directory
    valid_workspace = tmp_path / "valid_workspace"
    valid_workspace.mkdir()
    (valid_workspace / "jsonnetfile.json").touch()

    # Should not raise an error
    Workspace.check_path(valid_workspace)

    # Test with a non-directory path
    non_dir_path = tmp_path / "not_a_directory"
    non_dir_path.touch()


    with pytest.raises(ValueError):
        Workspace.check_path(non_dir_path)

    # Test with a directory missing jsonnetfile.json
    missing_jsonnetfile = tmp_path / "missing_jsonnetfile"
    missing_jsonnetfile.mkdir()
    with pytest.raises(ValueError):
        Workspace.check_path(missing_jsonnetfile)    

