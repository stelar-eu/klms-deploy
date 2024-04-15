"""_A library for convenient use of Jsonnet_

  The routines here make it convenient to use jsonnet from python.
  This is useful in:
   - testing jsonnet code
   - enriching jsonnet with python-based native functions
   - advanced integration with other jsonnet tools (e.g., tanka)
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import _jsonnet as J
import os
import json


if TYPE_CHECKING:
    JsonOutput = object


class JsonnetImporter:
    """Impement an importer supporting path lookup and optionally cache."""

    def __init__(self, path=[], use_cache=False):
        self.path = path
        self.use_cache = use_cache
        if use_cache:
            self.cache = {}

    def try_path_cached(self, dir, rel):
        if not rel:
            raise RuntimeError("Got invalid filename (empty string).")
        if rel[0] == "/":
            full_path = rel
        else:
            full_path = os.path.join(dir, rel)
        if full_path[-1] == "/":
            raise RuntimeError("Attempted to import a directory")
        return full_path, self.fetch_full_path(full_path)

    def fetch_full_path(self, full_path):
        if self.use_cache:
            return self.fetch_full_path_from_cache(full_path)
        else:
            return self.load_full_path(full_path)

    def load_full_path(self, full_path):
        if not os.path.isfile(full_path):
            return None
        else:
            with open(full_path) as f:
                return f.read().encode()

    def fetch_full_path_from_cache(self, full_path):
        if full_path not in self.cache:
            self.cache[full_path] = self.load_full_path(full_path)
        return self.cache[full_path]

    def import_file(self, dir, rel):
        full_path, content = self.try_path_cached(dir, rel)
        if content:
            return full_path, content
        raise ValueError("File not found")

    def __call__(self, dir, rel):
        for d in [dir, *self.path]:
            try:
                return self.import_file(d, rel)
            except ValueError:
                pass
        raise RuntimeError("file not found")


class JsonnetRunner:
    """Context for running jsonnet code snippets conveniently."""

    def __init__(
        self, filename, path: list[str] = [], 
        prelude: str = "",
        raw_output: bool = False, **kwargs
    ):
        """_Initialize the context_

        Args:
            filename (str): A file name to pass as the execution context
            path (list[str], optional): List of directories to use as path.
                Defaults to [].
            prelude (str, optional): A piece of code to be prepended to every
                snippet.
            raw_output (bool, optional): If True, return raw JSON text, else
                    return a python object. Defaults to False.
            **kwargs: passed to execute_snippet as is
        """
        self.filename = filename
        self.jimport = JsonnetImporter(path=path)
        self.prelude = prelude
        self.raw_output = raw_output
        self.kwargs = kwargs

    def __call__(self, snippet: str) -> JsonOutput:
        """Execute a snippet

        Args:
            snippet (str): A string of Jsonnet code to execute

        Returns:
            object: The result of the execution
        """
        raw = J.evaluate_snippet(
            self.filename, 
            self.prelude + snippet, 
            import_callback=self.jimport, 
            **self.kwargs
        )
        return self.processed_output(raw)

    def processed_output(self, raw: str) -> JsonOutput:
        if self.raw_output:
            return raw
        else:
            return json.loads(raw)
