"""Post-deploy verification checks against stable in-cluster service endpoints.

Readiness tells us that Kubernetes controllers have converged. Verification adds
a service-level smoke test by calling selected in-cluster HTTP endpoints through
the Kubernetes service proxy.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
from typing import Any, Callable

from kubernetes import client, config

try:
    from .platform_model import PlatformModel
except ImportError:
    from platform_model import PlatformModel


@dataclass(frozen=True)
class VerificationCheck:
    """Definition of one HTTP check made through the Kubernetes service proxy.

    `service` uses Kubernetes service-proxy syntax, including named ports when
    needed. A check can validate either through `validator` for structured
    responses or through `expected_substrings` for simple text responses.
    """

    label: str
    service: str
    path: str
    expected_substrings: tuple[str, ...] = ()
    validator: Callable[[Any], bool] | None = None
    expected_detail: str = ""


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of a deploy verification check.

    `detail` is always operator-facing. It should explain what failed rather
    than expose Python exception structure unless the request itself failed.
    """

    label: str
    ok: bool
    detail: str


CORE_CHECKS = (
    VerificationCheck(
        label="CKAN status API",
        service="ckan:api",
        path="api/3/action/status_show",
        validator=lambda body: _ckan_status_ok(body),
        expected_detail="successful CKAN status response",
    ),
    VerificationCheck(
        label="Keycloak readiness API",
        service="keycloak:keycloak-kchealth",
        path="health/ready",
        validator=lambda body: _keycloak_ready_ok(body),
        expected_detail="Keycloak health status UP",
    ),
    VerificationCheck(
        label="MinIO health API",
        service="minio:minio-minapi",
        path="minio/health/live",
    ),
)
# Verification runs after readiness and targets stable in-cluster service
# endpoints through the Kubernetes service proxy. These checks intentionally
# avoid public ingress paths so DNS and external TLS issues do not mask whether
# core services are actually responding inside the cluster.


def verification_checks_for_model(model: PlatformModel) -> tuple[VerificationCheck, ...]:
    # Initial verification suite is intentionally conservative and targets
    # the core services with stable in-cluster endpoints. The model argument is
    # kept so this function can later vary checks by tier or optional features
    # without changing deploy.py.
    return CORE_CHECKS


def run_verification_checks(
    context_name: str,
    namespace: str,
    checks: tuple[VerificationCheck, ...],
    *,
    request_timeout: tuple[int, int] = (5, 20),
) -> list[VerificationResult]:
    """Run service-proxy checks in the target namespace."""
    config.load_kube_config(context=context_name)
    core_api = client.CoreV1Api()

    results: list[VerificationResult] = []
    for check in checks:
        path = check.path.lstrip("/")
        try:
            # The service proxy avoids opening local port-forwards and keeps the
            # request scoped to the selected kubeconfig context and namespace.
            body, status_code, _headers = core_api.connect_get_namespaced_service_proxy_with_path_with_http_info(
                name=check.service,
                namespace=namespace,
                path=path,
                _request_timeout=request_timeout,
            )
        except Exception as exc:
            results.append(VerificationResult(check.label, False, f"request failed: {exc}"))
            continue

        if status_code != 200:
            results.append(VerificationResult(check.label, False, f"unexpected status {status_code}"))
            continue

        if check.validator is not None:
            # Structured validators are preferred for APIs with stable response
            # shapes. expected_substrings remains available for simple text
            # endpoints such as health checks.
            if not check.validator(body):
                detail = check.expected_detail or "response failed validation"
                results.append(VerificationResult(check.label, False, detail))
                continue
            results.append(VerificationResult(check.label, True, "ok"))
            continue

        body_text = _body_to_text(body)
        missing = [value for value in check.expected_substrings if value not in body_text]
        if missing:
            joined = ", ".join(missing)
            results.append(VerificationResult(check.label, False, f"response missing expected content: {joined}"))
            continue

        results.append(VerificationResult(check.label, True, "ok"))

    return results


def _body_to_text(body: Any) -> str:
    """Convert Kubernetes client response bodies into searchable text."""
    if isinstance(body, str):
        return body
    try:
        return json.dumps(body, sort_keys=True)
    except TypeError:
        return str(body)


def _ckan_status_ok(body: Any) -> bool:
    """Validate the CKAN status API response."""
    parsed = _body_to_mapping(body)
    if parsed is not None:
        return parsed.get("success") is True
    return "'success': True" in _body_to_text(body) or '"success": true' in _body_to_text(body).lower()


def _keycloak_ready_ok(body: Any) -> bool:
    """Validate the Keycloak readiness response."""
    parsed = _body_to_mapping(body)
    if parsed is not None:
        return parsed.get("status") == "UP"
    return "UP" in _body_to_text(body)


def _body_to_mapping(body: Any) -> dict[str, Any] | None:
    """Parse JSON-like response bodies into mappings when possible."""
    if isinstance(body, dict):
        return body
    if not isinstance(body, str):
        return None

    # Some Kubernetes client versions return JSON strings, while tests and
    # service proxies may return Python-literal-looking strings. Try strict JSON
    # first, then ast.literal_eval as a tolerant fallback.
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(body)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
