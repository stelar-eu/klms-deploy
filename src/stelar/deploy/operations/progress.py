"""Progress hooks for deployment operations."""

from __future__ import annotations


class ClusterProgress:
    """No-op progress reporter for cluster initialization."""

    def generating_secret(self, secret_name: str) -> None:
        pass

    def secret_generated(self, secret_name: str) -> None:
        pass

    def applying_secret(self, secret_name: str) -> None:
        pass

    def secret_applied(self, secret_name: str) -> None:
        pass

    def secret_exists(self, secret_name: str) -> None:
        pass


class LakeEnvironmentProgress:
    """No-op progress reporter for lake environment initialization."""

    def creating_directory(self, path: str) -> None:
        pass

    def directory_created(self, path: str) -> None:
        pass

    def directory_exists(self, path: str) -> None:
        pass

    def copying_template(self, source: str, destination: str) -> None:
        pass

    def template_copied(self, destination: str) -> None:
        pass

    def writing_file(self, path: str) -> None:
        pass

    def file_written(self, path: str) -> None:
        pass

    def file_exists(self, path: str) -> None:
        pass


class LakeWorkspaceProgress:
    """No-op progress reporter for lake workspace initialization."""

    def creating_directory(self, path: str) -> None:
        pass

    def directory_created(self, path: str) -> None:
        pass

    def directory_exists(self, path: str) -> None:
        pass

    def writing_file(self, path: str) -> None:
        pass

    def file_written(self, path: str) -> None:
        pass

    def rewriting_file(self, path: str) -> None:
        pass

    def file_rewritten(self, path: str) -> None:
        pass

    def file_exists(self, path: str) -> None:
        pass

    def updating_file(self, path: str) -> None:
        pass

    def file_updated(self, path: str) -> None:
        pass
