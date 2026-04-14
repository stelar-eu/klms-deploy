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
    label: str
    service: str
    path: str
    expected_substrings: tuple[str, ...] = ()
    validator: Callable[[Any], bool] | None = None
    expected_detail: str = ""


@dataclass(frozen=True)
class VerificationResult:
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


def verification_checks_for_model(model: PlatformModel) -> tuple[VerificationCheck, ...]:
    # Initial verification suite is intentionally conservative and targets
    # the core services with stable in-cluster endpoints.
    return CORE_CHECKS


def run_verification_checks(
    context_name: str,
    namespace: str,
    checks: tuple[VerificationCheck, ...],
    *,
    request_timeout: tuple[int, int] = (5, 20),
) -> list[VerificationResult]:
    config.load_kube_config(context=context_name)
    core_api = client.CoreV1Api()

    results: list[VerificationResult] = []
    for check in checks:
        path = check.path.lstrip("/")
        try:
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
    if isinstance(body, str):
        return body
    try:
        return json.dumps(body, sort_keys=True)
    except TypeError:
        return str(body)


def _ckan_status_ok(body: Any) -> bool:
    parsed = _body_to_mapping(body)
    if parsed is not None:
        return parsed.get("success") is True
    return "'success': True" in _body_to_text(body) or '"success": true' in _body_to_text(body).lower()


def _keycloak_ready_ok(body: Any) -> bool:
    parsed = _body_to_mapping(body)
    if parsed is not None:
        return parsed.get("status") == "UP"
    return "UP" in _body_to_text(body)


def _body_to_mapping(body: Any) -> dict[str, Any] | None:
    if isinstance(body, dict):
        return body
    if not isinstance(body, str):
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(body)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
