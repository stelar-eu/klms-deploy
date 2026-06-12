"""Typer progress reporters for stelarctl CLI handlers."""

from __future__ import annotations

import typer

from ..operations.progress import (
    ClusterProgress,
    LakeEnvironmentProgress,
    LakeSwitchProgress,
    LakeWorkspaceProgress,
)


class TyperClusterProgress(ClusterProgress):
    """Render cluster initialization progress through Typer."""

    def inferred_context(self, context_name: str) -> None:
        typer.echo(
            "ℹ️ spec.json has no contextNames; using active kubectl "
            f"context {context_name!r}."
        )

    def inferred_namespace(self, namespace: str, context_name: str) -> None:
        typer.echo(
            "ℹ️ spec.json has no namespace; using namespace "
            f"{namespace!r} from kubectl context {context_name!r}."
        )

    def generating_secret(self, secret_name: str) -> None:
        typer.echo(f"🔐 Generating secret {secret_name!r}...")

    def secret_generated(self, secret_name: str) -> None:
        typer.echo(f"✅ Secret {secret_name!r} generated.")

    def applying_secret(self, secret_name: str) -> None:
        typer.echo(f"🚀 Applying secret {secret_name!r} to the K8s cluster...")

    def secret_applied(self, secret_name: str) -> None:
        typer.echo(f"✅ Secret {secret_name!r} applied successfully.")

    def secret_exists(self, secret_name: str) -> None:
        typer.echo(f"⚠️ Secret {secret_name!r} already exists.")

    def bootstrap_already_applied(
        self,
        namespace: str,
        secret_names: tuple[str, ...],
    ) -> None:
        typer.echo(
            "⚠️ Bootstrap appears to have already run in namespace "
            f"{namespace!r}: all {len(secret_names)} required Secrets exist."
        )

    def bootstrap_state_check_forbidden(self, namespace: str, reason: str) -> None:
        typer.echo(
            "⚠️ Cannot check whether bootstrap Secrets already exist in namespace "
            f"{namespace!r}: {reason}. Proceeding at your own risk."
        )

    def lake_state_exists(self, namespace: str, configmap_name: str) -> None:
        typer.echo(
            "⚠️ Lake bootstrap appears to have already run in namespace "
            f"{namespace!r}: ConfigMap {configmap_name!r} exists."
        )

    def applying_configmap(self, configmap_name: str) -> None:
        typer.echo(f"🚀 Applying ConfigMap {configmap_name!r} to the K8s cluster...")

    def configmap_applied(self, configmap_name: str) -> None:
        typer.echo(f"✅ ConfigMap {configmap_name!r} applied successfully.")


class TyperLakeSwitchProgress(LakeSwitchProgress):
    """Render lake product switch notices through Typer."""

    def switch_matches_bootstrapped_product(
        self,
        product_name: str,
        namespace: str,
    ) -> None:
        typer.echo(
            "ℹ️ Product "
            f"{product_name!r} already matches the cluster lake state in "
            f"namespace {namespace!r}."
        )

    def switching_despite_bootstrapped_product(
        self,
        product_name: str,
        namespace: str,
        bootstrapped_product_name: str | None,
    ) -> None:
        cluster_product = (
            f" product {bootstrapped_product_name!r}"
            if bootstrapped_product_name
            else " a different product"
        )
        typer.echo(
            "⚠️ Namespace "
            f"{namespace!r} is already bootstrapped for{cluster_product}. "
            f"Switching local render selection to {product_name!r} anyway; "
            "unbootstrap the namespace and rerun lake bootstrap before applying "
            "this product to the same namespace."
        )

    def switching_despite_state_check_failure(
        self,
        product_name: str,
        namespace: str,
        reason: str,
    ) -> None:
        typer.echo(
            "⚠️ Cannot inspect cluster lake state in namespace "
            f"{namespace!r}: {reason}. Switching local render selection to "
            f"{product_name!r} anyway."
        )


class TyperLakeEnvironmentProgress(LakeEnvironmentProgress):
    """Render lake environment initialization progress through Typer."""

    def creating_directory(self, path: str) -> None:
        typer.echo(f"🌐 Creating directory {path!r}...")

    def directory_created(self, path: str) -> None:
        typer.echo(f"✅ Directory {path!r} created.")

    def directory_exists(self, path: str) -> None:
        typer.echo(f"⚠️ Directory {path!r} already exists.")

    def copying_template(self, source: str, destination: str) -> None:
        typer.echo(f"🖊️ Copying template {source!r} to {destination!r}...")

    def template_copied(self, destination: str) -> None:
        typer.echo(f"✅ Template written successfully at {destination!r}.")

    def writing_file(self, path: str) -> None:
        typer.echo(f"🖊️ Writing Tanka spec skeleton to {path!r}...")

    def file_written(self, path: str) -> None:
        typer.echo(f"✅ Tanka spec skeleton written successfully at {path!r}.")

    def file_exists(self, path: str) -> None:
        typer.echo(f"⚠️ File {path!r} already exists.")

    def existing_spec_adopted(self, path: str) -> None:
        typer.echo(
            f"⚠️ Existing Tanka spec {path!r} was preserved and marked as a "
            "stelarctl lake environment."
        )

    def removing_environment(self, path: str) -> None:
        typer.echo(f"🗑️ Removing lake environment {path!r}...")

    def environment_removed(self, path: str) -> None:
        typer.echo(f"✅ Lake environment {path!r} removed.")


class TyperLakeWorkspaceProgress(LakeWorkspaceProgress):
    """Render lake workspace initialization progress through Typer."""

    def creating_directory(self, path: str) -> None:
        typer.echo(f"🌐 Creating directory {path!r}...")

    def directory_created(self, path: str) -> None:
        typer.echo(f"✅ Directory {path!r} created.")

    def directory_exists(self, path: str) -> None:
        typer.echo(f"⚠️ Directory {path!r} already exists.")

    def writing_file(self, path: str) -> None:
        typer.echo(f"🖊️ Writing JSONNet file to {path!r}...")

    def file_written(self, path: str) -> None:
        typer.echo(f"✅ JSONNet file written successfully at {path!r}.")

    def rewriting_file(self, path: str) -> None:
        typer.echo(f"🖊️ Rewriting JSONNet file at {path!r}...")

    def file_rewritten(self, path: str) -> None:
        typer.echo(f"✅ JSONNet file rewritten successfully at {path!r}.")

    def file_exists(self, path: str) -> None:
        typer.echo(f"⚠️ JSONNet file {path!r} already has all lake dependencies.")

    def updating_file(self, path: str) -> None:
        typer.echo(f"🖊️ Adding missing lake dependencies to {path!r}...")

    def file_updated(self, path: str) -> None:
        typer.echo(f"✅ JSONNet file updated successfully at {path!r}.")
