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


@dataclass(frozen=True)
class DeployDecision:
    action: str
    reason: str
    differences: list[str]
    needs_secret_confirmation: bool = False
    live_drift_differences: list[str] | None = None


LIVE_UNCOMPARABLE_FIELDS = {
    "infrastructure.storage.dynamic_class",
}
DEFAULT_WAIT_TIMEOUT_SECONDS = 600
DEFAULT_WAIT_POLL_INTERVAL_SECONDS = 5


def plan_deploy(input_model: PlatformModel, env_path: Path) -> DeployDecision:
    stored_model = load_stored_model(env_path)
    live = infer_live_deployment(input_model.k8s_context, input_model.namespace)

    if stored_model is None and not live.active:
        return DeployDecision(action="fresh", reason="No stored model and no active STELAR deployment found.", differences=[])

    if stored_model is not None and not live.active:
        return DeployDecision(
            action="fresh",
            reason="Stored model exists, but no live STELAR deployment was found in the target namespace.",
            differences=[],
        )

    if stored_model is None and live.model is not None:
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

    assert stored_model is not None

    live_drift = []
    if live.model is not None:
        stored_vs_live = compare_models(
            stored_model,
            live.model,
            include_secret_values=False,
            ignore_fields=LIVE_UNCOMPARABLE_FIELDS,
        )
        live_drift = stored_vs_live.differences
        baseline = live.model if live_drift else stored_model
        baseline_is_inferred = bool(live_drift)
    else:
        baseline = stored_model
        baseline_is_inferred = False

    if baseline_is_inferred:
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
    wait_timeout: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    wait_interval: int = DEFAULT_WAIT_POLL_INTERVAL_SECONDS,
) -> DeployDecision:
    decision = plan_deploy(model, env_path)

    typer.echo(decision.reason)
    if decision.live_drift_differences:
        typer.echo("Detected drift between stored state and live cluster:")
        for difference in decision.live_drift_differences:
            typer.echo(f"- {difference}")

    if decision.action == "noop":
        typer.echo("Input model matches the active deployment. No changes to apply.")
        if wait:
            wait_for_ready(
                model.k8s_context,
                model.namespace,
                timeout_seconds=wait_timeout,
                poll_interval=wait_interval,
            )
        return decision

    if decision.action == "prompt_secret_values":
        secrets_same = typer.confirm(
            "Live deployment matches except secret values cannot be verified from Kubernetes. Are the secret values unchanged?",
            default=False,
        )
        if secrets_same:
            typer.echo("No changes detected in the live deployment.")
            if wait:
                wait_for_ready(
                    model.k8s_context,
                    model.namespace,
                    timeout_seconds=wait_timeout,
                    poll_interval=wait_interval,
                )
            return DeployDecision(action="noop", reason=decision.reason, differences=[])
        decision = DeployDecision(
            action="hard_redeploy",
            reason="Secret values could not be verified and were confirmed as changed.",
            differences=[],
            live_drift_differences=decision.live_drift_differences,
        )

    if decision.differences:
        typer.echo("Model differences:")
        for difference in decision.differences:
            typer.echo(f"- {difference}")

    preflight_check(model, auto_approve=auto_approve)
    write_spec_json(env_path, model)
    write_main_jsonnet(model, str(env_path))

    typer.echo("Tanka diff preview:")
    _run_command(["tk", "diff", str(env_path), "--with-prune"], check=False)

    if not auto_approve:
        typer.confirm(
            f"Applying this model requires a hard redeploy of '{model.k8s_context}/{model.namespace}'. Continue?",
            abort=True,
        )

    live = infer_live_deployment(model.k8s_context, model.namespace)
    if live.active:
        purge_namespace(model.k8s_context, model.namespace)

    annotate_namespace(model)
    apply_secrets(model)
    apply_generated_secrets(model)

    _run_command(["tk", "apply", str(env_path), "--auto-approve", "always"])
    save_stored_model(env_path, model)
    typer.echo(f"Stored deployment model written to {env_path / 'model.yaml'}.")
    if wait:
        wait_for_ready(
            model.k8s_context,
            model.namespace,
            timeout_seconds=wait_timeout,
            poll_interval=wait_interval,
        )
    return decision


def wait_for_ready(
    context_name: str,
    namespace: str,
    *,
    timeout_seconds: int = DEFAULT_WAIT_TIMEOUT_SECONDS,
    poll_interval: int = DEFAULT_WAIT_POLL_INTERVAL_SECONDS,
) -> None:
    deadline = time.time() + timeout_seconds
    last_line = ""

    typer.echo(
        f"Waiting for '{context_name}/{namespace}' to reach Ready 100% "
        f"(timeout: {timeout_seconds}s, interval: {poll_interval}s)."
    )

    while time.time() < deadline:
        snapshot, warnings = collect_inferred_status(context_name, namespace)
        if snapshot is None:
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
                warning_line = f"Warning: {warning}"
                if warning_line != last_line:
                    typer.echo(warning_line)

        if snapshot.phase == "Ready" and snapshot.overall_percent == 100:
            typer.echo("Deployment reached Ready 100%.")
            typer.echo(format_status(snapshot))
            return

        if snapshot.phase == "Degraded":
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


def teardown_target(
    context_name: str,
    namespace: str,
    *,
    env_path: Path | None = None,
    delete_namespace: bool = False,
    delete_env: bool = False,
    auto_approve: bool = False,
) -> None:
    if delete_env and env_path is None:
        raise typer.BadParameter("--delete-env requires --env.")

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
        model_path = stored_model_path(env_path)
        if model_path.exists():
            model_path.unlink()
            typer.echo(f"Removed stored model {model_path}.")

    if delete_namespace:
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
        clear_namespace_annotations(context_name, namespace)

    if delete_env and env_path is not None and env_path.exists():
        shutil.rmtree(env_path)
        typer.echo(f"Deleted environment directory {env_path}.")


def preflight_check(model: PlatformModel, *, auto_approve: bool = False) -> None:
    contexts, active_context = config.list_kube_config_contexts()
    context_names = {item["name"] for item in contexts}
    if model.k8s_context not in context_names:
        raise typer.BadParameter(f"Kubernetes context '{model.k8s_context}' not found in kubeconfig.")

    if active_context and active_context["name"] != model.k8s_context:
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
    config.load_kube_config(context=model.k8s_context)
    core_api = client.CoreV1Api()
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
    result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout:
        typer.echo(result.stdout.rstrip())
    if result.stderr:
        typer.echo(result.stderr.rstrip(), err=True)
    if check and result.returncode != 0:
        raise typer.Exit(result.returncode)
    return result
