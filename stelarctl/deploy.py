"""Deployment planning, apply, readiness waiting, and teardown orchestration.

This module is the operational core of stelarctl. It keeps deploy behavior
explicitly state-driven: first decide what the current baseline is, then show
the operator what will change, then run the destructive parts in a fixed order.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
import shutil

import typer
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

try:
    from .compare import compare_models
    from .env import load_stored_model, save_stored_model, stored_model_path, write_spec_json
    from .generator import write_main_jsonnet
    from .live import (
        STELAR_AUTHOR_ANNOTATION,
        STELAR_PLATFORM_ANNOTATION,
        STELAR_TIER_ANNOTATION,
        infer_live_deployment,
    )
    from .platform_model import PlatformModel
    from .secrets import apply_generated_secrets, apply_secrets
    from .status import collect_inferred_status, format_status
    from .verify import run_verification_checks, verification_checks_for_model
except ImportError:
    from compare import compare_models
    from env import load_stored_model, save_stored_model, stored_model_path, write_spec_json
    from generator import write_main_jsonnet
    from live import (
        STELAR_AUTHOR_ANNOTATION,
        STELAR_PLATFORM_ANNOTATION,
        STELAR_TIER_ANNOTATION,
        infer_live_deployment,
    )
    from platform_model import PlatformModel
    from secrets import apply_generated_secrets, apply_secrets
    from status import collect_inferred_status, format_status
    from verify import run_verification_checks, verification_checks_for_model


@dataclass(frozen=True)
class DeployDecision:
    """Result of comparing the input model with stored and live deployment state.

    `action` is intentionally a small string vocabulary because the CLI uses it
    to choose the next operational step. `differences` are always phrased as
    "old -> new" from the baseline toward the input model, so they can be shown
    directly to operators before a destructive redeploy.
    """

    action: str
    # Human-readable explanation printed before any apply or purge work starts.
    reason: str
    # Differences between the selected baseline and the requested input model.
    differences: list[str]
    # True when the only uncertainty is whether plaintext secret values changed.
    needs_secret_confirmation: bool = False
    # Stored-vs-live drift, reported separately from input-vs-baseline changes.
    live_drift_differences: list[str] | None = None


LIVE_UNCOMPARABLE_FIELDS = {
    "infrastructure.storage.dynamic_class",
}
# Some fields cannot be recovered faithfully from Kubernetes objects. Dynamic
# storage class is one of them because live PVCs only expose the class actually
# used by existing claims, which may not be enough to reconstruct every desired
# provisioning choice in the original model.
DEFAULT_WAIT_TIMEOUT_SECONDS = 600
DEFAULT_WAIT_POLL_INTERVAL_SECONDS = 5


def plan_deploy(input_model: PlatformModel, env_path: Path) -> DeployDecision:
    """Decide whether a deploy is fresh, a no-op, or a hard redeploy.

    The comparison uses the stored model when possible because it preserves
    secret values. When the stored model is absent or has drifted from the live
    cluster, the inferred live model becomes the baseline and secret values are
    treated as unverifiable.
    """
    stored_model = load_stored_model(env_path)
    live = infer_live_deployment(input_model.k8s_context, input_model.namespace)

    # No stored desired state and no STELAR resources means there is no baseline
    # to compare against. Treat the run as a first install.
    if stored_model is None and not live.active:
        return DeployDecision(action="fresh", reason="No stored model and no active STELAR deployment found.", differences=[])

    # A stored model without a live deployment most commonly means the namespace
    # was cleaned up outside stelarctl. A fresh deploy is safer than reporting a
    # no-op because the cluster does not currently contain the desired system.
    if stored_model is not None and not live.active:
        return DeployDecision(
            action="fresh",
            reason="Stored model exists, but no live STELAR deployment was found in the target namespace.",
            differences=[],
        )

    if stored_model is None and live.model is not None:
        # A live deployment without stored state may have been created by an
        # older tool version or from a copied environment directory. Compare
        # against inferred live state, but never compare secret values because
        # Kubernetes only stores their encoded form and stelarctl does not read
        # or decode them for planning.
        inferred_compare = compare_models(
            input_model,
            live.model,
            include_secret_values=False,
            ignore_fields=LIVE_UNCOMPARABLE_FIELDS,
        )
        if inferred_compare.equal:
            return DeployDecision(
                action="prompt_secret_values",
                reason="Live deployment matches the input model except secret values cannot be verified from the cluster.",
                differences=[],
                needs_secret_confirmation=True,
            )
        return DeployDecision(
            action="hard_redeploy",
            reason="Existing live deployment detected; input differs from inferred live state.",
            differences=inferred_compare.differences,
        )

    # All earlier branches that allow stored_model to be None have returned.
    # The assert documents that the remaining decision tree always has a stored
    # baseline, even if live state later overrides it as the safer comparison.
    assert stored_model is not None

    live_drift = []
    if live.model is not None:
        # Secret values cannot be recovered from Kubernetes, so live drift can
        # only compare non-secret fields and secret names.
        stored_vs_live = compare_models(
            stored_model,
            live.model,
            include_secret_values=False,
            ignore_fields=LIVE_UNCOMPARABLE_FIELDS,
        )
        live_drift = stored_vs_live.differences
        # If stored state differs from live state, the live cluster is the safer
        # baseline for deciding whether the input model is changing reality.
        # Otherwise, use the stored model because it still contains plaintext
        # secret values and can detect secret-only input changes.
        baseline = live.model if live_drift else stored_model
        baseline_is_inferred = bool(live_drift)
    else:
        baseline = stored_model
        baseline_is_inferred = False

    if baseline_is_inferred:
        # Inferred baselines intentionally mask secret values. If every visible
        # field matches, ask the operator whether the secret values are still the
        # same instead of silently assuming a no-op or forcing a redeploy.
        input_vs_baseline = compare_models(
            input_model,
            baseline,
            include_secret_values=False,
            ignore_fields=LIVE_UNCOMPARABLE_FIELDS,
        )
        if input_vs_baseline.equal:
            return DeployDecision(
                action="prompt_secret_values",
                reason="Stored model drifted from the live cluster. Input matches inferred live state except secret values cannot be verified.",
                differences=[],
                needs_secret_confirmation=True,
                live_drift_differences=live_drift,
            )
        return DeployDecision(
            action="hard_redeploy",
            reason="Stored model drifted from the live cluster; input differs from inferred live state.",
            differences=input_vs_baseline.differences,
            live_drift_differences=live_drift,
        )

    # At this point the stored model agrees with live state, so it is safe to do
    # the strongest comparison, including secret values.
    full_compare = compare_models(input_model, baseline, include_secret_values=True)
    if full_compare.equal:
        return DeployDecision(action="noop", reason="Input model matches the stored deployment state.", differences=[])

    return DeployDecision(
        action="hard_redeploy",
        reason="Input model differs from the stored deployment state.",
        differences=full_compare.differences,
    )


def perform_deploy(
    model: PlatformModel,
    env_path: Path,
    *,
    auto_approve: bool = False,
    wait: bool = False,
    verify: bool = False,
    wait_timeout: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    wait_interval: int = DEFAULT_WAIT_POLL_INTERVAL_SECONDS,
) -> DeployDecision:
    """Run the full deploy workflow and return the planning decision used."""
    # Verification depends on services being reachable, so it implies the same
    # readiness wait even when the operator did not pass --wait explicitly.
    effective_wait = wait or verify
    if verify and not wait:
        typer.echo("Verification requested; waiting for readiness before running checks.")

    decision = plan_deploy(model, env_path)

    typer.echo(decision.reason)
    if decision.live_drift_differences:
        # Drift is not itself the requested change, but it changes which
        # baseline is used. Echo it separately so the operator can distinguish
        # "the cluster changed" from "the input model changed".
        typer.echo("Detected drift between stored state and live cluster:")
        for difference in decision.live_drift_differences:
            typer.echo(f"- {difference}")

    if decision.action == "noop":
        # A no-op may still be useful with --wait or --verify, for example when
        # continuing to monitor a deployment that was already applied earlier.
        typer.echo("Input model matches the active deployment. No changes to apply.")
        if effective_wait:
            wait_for_ready(
                model.k8s_context,
                model.namespace,
                timeout_seconds=wait_timeout,
                poll_interval=wait_interval,
            )
        if verify:
            verify_deployment(model)
        return decision

    if decision.action == "prompt_secret_values":
        # This branch is reached only when all recoverable live state matches.
        # The operator is the only remaining source of truth for plaintext
        # secret values.
        secrets_same = typer.confirm(
            "Live deployment matches except secret values cannot be verified from Kubernetes. Are the secret values unchanged?",
            default=False,
        )
        if secrets_same:
            typer.echo("No changes detected in the live deployment.")
            if effective_wait:
                wait_for_ready(
                    model.k8s_context,
                    model.namespace,
                    timeout_seconds=wait_timeout,
                    poll_interval=wait_interval,
                )
            if verify:
                verify_deployment(model)
            return DeployDecision(action="noop", reason=decision.reason, differences=[])
        decision = DeployDecision(
            action="hard_redeploy",
            reason="Secret values could not be verified and were confirmed as changed.",
            differences=[],
            live_drift_differences=decision.live_drift_differences,
        )

    if decision.differences:
        # These differences come from compare_models and are ordered for stable
        # terminal output and predictable tests.
        typer.echo("Model differences:")
        for difference in decision.differences:
            typer.echo(f"- {difference}")

    preflight_check(model, auto_approve=auto_approve)
    # Materialize files before the Tanka diff so the preview reflects exactly
    # what will be applied after confirmation.
    write_spec_json(env_path, model)
    write_main_jsonnet(model, str(env_path))

    # Show operators the Tanka-level delta before the destructive confirmation.
    typer.echo("Tanka diff preview:")
    _run_command(["tk", "diff", str(env_path), "--with-prune"], check=False)

    if not auto_approve:
        typer.confirm(
            f"Applying this model requires a hard redeploy of '{model.k8s_context}/{model.namespace}'. Continue?",
            abort=True,
        )

    live = infer_live_deployment(model.k8s_context, model.namespace)
    if live.active:
        # The current strategy is intentionally hard redeploy only. Purging
        # known STELAR resources avoids merging incompatible old Kubernetes
        # objects with newly generated manifests.
        purge_namespace(model.k8s_context, model.namespace)

    # Namespace annotations are written after the purge so live-state inference
    # can recognize the deployment even if some resources are still starting.
    annotate_namespace(model)
    apply_secrets(model)
    apply_generated_secrets(model)

    _run_command(["tk", "apply", str(env_path), "--auto-approve", "always"])
    # Persist only after tk apply succeeds. This keeps model.yaml as the last
    # successful desired state rather than the last attempted desired state.
    save_stored_model(env_path, model)
    typer.echo(f"Stored deployment model written to {env_path / 'model.yaml'}.")
    if effective_wait:
        wait_for_ready(
            model.k8s_context,
            model.namespace,
            timeout_seconds=wait_timeout,
            poll_interval=wait_interval,
        )
    if verify:
        verify_deployment(model)
    return decision


def wait_for_ready(
    context_name: str,
    namespace: str,
    *,
    timeout_seconds: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    poll_interval: int = DEFAULT_WAIT_POLL_INTERVAL_SECONDS,
) -> None:
    """Poll inferred status until the deployment is ready, degraded, or timed out."""
    deadline = time.time() + timeout_seconds
    # Keep watch output readable in non-interactive logs by suppressing repeated
    # identical progress lines.
    last_line = ""

    typer.echo(
        f"Waiting for '{context_name}/{namespace}' to reach Ready 100% "
        f"(timeout: {timeout_seconds}s, interval: {poll_interval}s)."
    )

    while time.time() < deadline:
        snapshot, warnings = collect_inferred_status(context_name, namespace)
        if snapshot is None:
            # A deployment can briefly disappear during a hard redeploy while
            # old resources are being purged and new resources have not been
            # applied yet. Keep polling until timeout instead of failing early.
            latest = f"No active STELAR deployment found in {context_name}/{namespace}."
            if latest != last_line:
                typer.echo(latest)
                last_line = latest
            time.sleep(poll_interval)
            continue

        latest = (
            f"{snapshot.phase} {snapshot.overall_percent}% "
            f"(jobs {snapshot.jobs_completed}/{snapshot.jobs_total}, "
            f"components {snapshot.components_ready}/{snapshot.components_total})"
        )
        if latest != last_line:
            typer.echo(latest)
            last_line = latest

        if warnings:
            for warning in warnings:
                # Warnings usually come from best-effort live inference. They
                # are informational unless the derived status becomes Degraded.
                warning_line = f"Warning: {warning}"
                if warning_line != last_line:
                    typer.echo(warning_line)

        if snapshot.phase == "Ready" and snapshot.overall_percent == 100:
            typer.echo("Deployment reached Ready 100%.")
            typer.echo(format_status(snapshot))
            return

        if snapshot.phase == "Degraded":
            # Degraded is treated as terminal for wait mode because at least one
            # job failed or a pod reached a known unrecoverable waiting reason.
            typer.echo("Deployment entered a degraded state while waiting for readiness.")
            typer.echo(format_status(snapshot))
            raise typer.Exit(1)

        time.sleep(poll_interval)

    snapshot, _ = collect_inferred_status(context_name, namespace)
    typer.echo(f"Timed out waiting for '{context_name}/{namespace}' to reach Ready 100%.")
    if snapshot is None:
        typer.echo(f"No active STELAR deployment found in {context_name}/{namespace}.")
    else:
        typer.echo(format_status(snapshot))
    raise typer.Exit(1)


def verify_deployment(model: PlatformModel) -> None:
    """Run post-deploy service checks and exit non-zero on the first failed set."""
    checks = verification_checks_for_model(model)
    if not checks:
        typer.echo("No deploy verification checks are defined for this deployment.")
        return

    typer.echo("Running deploy verification checks.")
    results = run_verification_checks(model.k8s_context, model.namespace, checks)

    failed = False
    for result in results:
        # Print every result before exiting so an operator gets the full failure
        # set from one run instead of fixing checks one at a time.
        status = "PASS" if result.ok else "FAIL"
        typer.echo(f"{status} {result.label}: {result.detail}")
        failed = failed or not result.ok

    if failed:
        raise typer.Exit(1)


def teardown_target(
    context_name: str,
    namespace: str,
    *,
    env_path: Path | None = None,
    delete_namespace: bool = False,
    delete_env: bool = False,
    auto_approve: bool = False,
) -> None:
    """Purge deployment resources and optionally delete the namespace or env dir."""
    if delete_env and env_path is None:
        raise typer.BadParameter("--delete-env requires --env.")

    # Build the confirmation text from the exact selected actions so destructive
    # flags are visible in the prompt.
    actions = ["purge deployment resources"]
    if delete_namespace:
        actions.append("delete the namespace")
    if delete_env:
        actions.append("delete the local environment directory")

    if not auto_approve:
        typer.confirm(
            f"This will {', '.join(actions)} for '{context_name}/{namespace}'. Continue?",
            abort=True,
        )

    purge_namespace(context_name, namespace)

    if env_path is not None:
        # Removing the stored model prevents a future deploy from comparing
        # against a desired state that no longer has corresponding live objects.
        model_path = stored_model_path(env_path)
        if model_path.exists():
            model_path.unlink()
            typer.echo(f"Removed stored model {model_path}.")

    if delete_namespace:
        # Namespace deletion can take a long time if finalizers are present.
        # stelarctl starts deletion and returns instead of blocking indefinitely.
        _run_command(
            [
                "kubectl",
                "--context",
                context_name,
                "delete",
                "namespace",
                namespace,
                "--ignore-not-found=true",
                "--wait=false",
            ],
            check=False,
        )
    else:
        # When the namespace survives teardown, clear the metadata that would
        # otherwise make future live inference look more authoritative than it is.
        clear_namespace_annotations(context_name, namespace)

    if delete_env and env_path is not None and env_path.exists():
        shutil.rmtree(env_path)
        typer.echo(f"Deleted environment directory {env_path}.")


def preflight_check(model: PlatformModel, *, auto_approve: bool = False) -> None:
    """Validate cluster prerequisites before writing or applying manifests."""
    contexts, active_context = config.list_kube_config_contexts()
    context_names = {item["name"] for item in contexts}
    if model.k8s_context not in context_names:
        raise typer.BadParameter(f"Kubernetes context '{model.k8s_context}' not found in kubeconfig.")

    if active_context and active_context["name"] != model.k8s_context:
        # Tanka uses the kubeconfig context as part of its apply path. Align the
        # active kubectl context with the model before running tk commands.
        _run_command(["kubectl", "config", "use-context", model.k8s_context])

    config.load_kube_config(context=model.k8s_context)
    core_api = client.CoreV1Api()
    storage_api = client.StorageV1Api()
    networking_api = client.NetworkingV1Api()
    custom_api = client.CustomObjectsApi()

    try:
        core_api.read_namespace(model.namespace)
    except ApiException as exc:
        if exc.status != 404:
            raise
        # Namespace creation is the only preflight mutation. It is safe under
        # --yes because all later destructive changes still target that namespace.
        create_ns = True if auto_approve else typer.confirm(
            f"Namespace '{model.namespace}' does not exist on context '{model.k8s_context}'. Create it?",
            default=True,
        )
        if not create_ns:
            raise typer.Abort()
        core_api.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=model.namespace)))

    storage_classes = {
        item.metadata.name for item in storage_api.list_storage_class().items
    }
    # Validate both classes separately so the error can point back to the exact
    # model field that needs to be changed.
    for field_name, value in {
        "infrastructure.storage.dynamic_class": model.infrastructure.storage.dynamic_class,
        "infrastructure.storage.provisioning_class": model.infrastructure.storage.provisioning_class,
    }.items():
        if value and value not in storage_classes:
            raise typer.BadParameter(f"StorageClass '{value}' from {field_name} does not exist.")

    ingress_classes = {
        item.metadata.name for item in networking_api.list_ingress_class().items
    }
    if model.infrastructure.ingress_class not in ingress_classes:
        raise typer.BadParameter(
            f"IngressClass '{model.infrastructure.ingress_class}' from infrastructure.ingress_class does not exist."
        )

    if model.infrastructure.tls.mode == "cert-manager":
        # The generated ingress manifests reference a ClusterIssuer by name. If
        # it is absent or not Ready, deployment would apply successfully but TLS
        # certificates would never become valid.
        try:
            issuer = custom_api.get_cluster_custom_object(
                group="cert-manager.io",
                version="v1",
                plural="clusterissuers",
                name=model.infrastructure.tls.issuer,
            )
        except ApiException as exc:
            raise typer.BadParameter(
                f"ClusterIssuer '{model.infrastructure.tls.issuer}' from infrastructure.tls.issuer does not exist."
            ) from exc
        conditions = issuer.get("status", {}).get("conditions", [])
        ready = any(item.get("type") == "Ready" and item.get("status") == "True" for item in conditions)
        if not ready:
            raise typer.BadParameter(
                f"ClusterIssuer '{model.infrastructure.tls.issuer}' exists but is not Ready."
            )


def annotate_namespace(model: PlatformModel) -> None:
    """Record STELAR metadata on the namespace for later live-state inference."""
    config.load_kube_config(context=model.k8s_context)
    core_api = client.CoreV1Api()
    # These annotations are hints, not the only source of truth. live.py still
    # checks actual workloads so an annotated but empty namespace is not treated
    # as an active deployment.
    body = {
        "metadata": {
            "annotations": {
                STELAR_TIER_ANNOTATION: model.tier,
                STELAR_PLATFORM_ANNOTATION: model.platform,
                STELAR_AUTHOR_ANNOTATION: model.author,
            }
        }
    }
    core_api.patch_namespace(name=model.namespace, body=body)


def clear_namespace_annotations(context_name: str, namespace: str) -> None:
    """Remove STELAR namespace annotations left after resource teardown."""
    config.load_kube_config(context=context_name)
    core_api = client.CoreV1Api()
    try:
        core_api.patch_namespace(
            name=namespace,
            body={
                "metadata": {
                    "annotations": {
                        STELAR_TIER_ANNOTATION: None,
                        STELAR_PLATFORM_ANNOTATION: None,
                        STELAR_AUTHOR_ANNOTATION: None,
                    }
                }
            },
        )
    except ApiException as exc:
        if exc.status != 404:
            raise


def purge_namespace(context_name: str, namespace: str) -> None:
    """Delete known STELAR namespaced resources while keeping the namespace."""
    # The resource list is intentionally namespaced and STELAR-scoped by usage:
    # it removes resource kinds the generated manifests own without deleting the
    # namespace object itself. --all assumes the namespace is dedicated to STELAR.
    resources = [
        "deployments.apps",
        "statefulsets.apps",
        "jobs.batch",
        "services",
        "configmaps",
        "secrets",
        "persistentvolumeclaims",
        "ingresses.networking.k8s.io",
        "serviceaccounts",
        "roles.rbac.authorization.k8s.io",
        "rolebindings.rbac.authorization.k8s.io",
        "pods",
    ]
    _run_command(
        [
            "kubectl",
            "--context",
            context_name,
            "-n",
            namespace,
            "delete",
            ",".join(resources),
            "--all",
            "--ignore-not-found=true",
            "--wait=true",
        ],
        check=False,
    )


def _run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run an external command, echo captured output, and optionally fail fast."""
    # Capture output so Typer can write stdout/stderr through the same channel as
    # the rest of the CLI. This also makes tests deterministic because command
    # output is emitted after the subprocess exits.
    result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout:
        typer.echo(result.stdout.rstrip())
    if result.stderr:
        typer.echo(result.stderr.rstrip(), err=True)
    if check and result.returncode != 0:
        # Preserve the failing tool's return code. Operators and CI can then
        # distinguish validation errors, Tanka failures, and kubectl failures.
        raise typer.Exit(result.returncode)
    return result
