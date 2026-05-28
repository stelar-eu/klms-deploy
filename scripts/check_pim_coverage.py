#!/usr/bin/env python3
"""Check whether manifest env/config inputs are represented in lib/pim.libsonnet.

The checker does four things:
1. Flattens the current PIM inventory into short keys like `api.SMTP_SERVER`.
2. Extracts `config.*` and `pim.*` references from `lib/*.libsonnet`.
3. Maps known `config.*` references to expected PIM keys.
4. Reports missing coverage, stale manifest refs, unused PIM keys, and
   hardcoded env-like literals that may still need inventorying.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CONFIG_TO_PIM = {
    "config.endpoint.SCHEME": "cluster.SCHEME",
    "config.endpoint.ROOT_DOMAIN": "cluster.ROOT_DOMAIN",
    "config.endpoint.CLUSTER_ISSUER": "cluster.CLUSTER_ISSUER",
    "config.endpoint.PRIMARY_SUBDOMAIN": "cluster.PRIMARY_SUBDOMAIN",
    "config.endpoint.KEYCLOAK_SUBDOMAIN": "keycloak.SUBDOMAIN",
    "config.endpoint.MINIO_API_SUBDOMAIN": "minio.API_SUBDOMAIN",
    "config.endpoint.REGISTRY_SUBDOMAIN": "registry.SUBDOMAIN",
    "config.api.SMTP_SERVER": "api.SMTP_SERVER",
    "config.api.SMTP_PORT": "api.SMTP_PORT",
    "config.api.SMTP_USERNAME": "api.SMTP_USERNAME",
    "config.api.S3_CONSOLE_URL": "minio.S3_CONSOLE_URL",
    "config.minio.API_DOMAIN": "minio.API_DOMAIN",
    "config.minio.CONSOLE_DOMAIN": "minio.CONSOLE_DOMAIN",
    "config.minio.INSECURE_MC_CLIENT": "minio.INSECURE_MC_CLIENT",
    "config.llm_search.ENABLE_LLM_SEARCH": "llm_search.ENABLE_LLM_SEARCH",
    "config.llm_search.GROQ_API_URL": "llm_search.GROQ_API_URL",
    "config.llm_search.GROQ_MODEL": "llm_search.GROQ_MODEL",
    "config.secrets.db.postgres_db_password_secret": "db.POSTGRES_DB_PASSWORD_SECRET_NAME",
    "config.secrets.db.ckan_db_password_secret": "db.CKAN_DB_PASSWORD_SECRET_NAME",
    "config.secrets.db.keycloak_db_passowrd_secret": "db.KEYCLOAK_DB_PASSWORD_SECRET_NAME",
    "config.secrets.db.datastore_db_password_secret": "db.DATASTORE_DB_PASSWORD_SECRET_NAME",
    "config.secrets.db.quay_db_password_secret": "db.QUAY_DB_PASSWORD_SECRET_NAME",
    "config.secrets.keycloak.root_password_secret": "keycloak.KEYCLOAK_ROOT_PASSWORD_SECRET_NAME",
    "config.secrets.api.smtp_password_secret": "api.SMTP_PASSWORD_SECRET_NAME",
    "config.secrets.api.session_secret_key": "api.SESSION_SECRET_KEY_SECRET_NAME",
    "config.secrets.ckan.ckan_admin_password_secret": "ckan.CKAN_ADMIN_PASSWORD_SECRET_NAME",
    "config.secrets.ckan.ckan_auth_secret": "ckan.CKAN_AUTH_SECRET_NAME",
    "config.secrets.minio.minio_root_password_secret": "minio.MINIO_ROOT_PASSWORD_SECRET_NAME",
    "config.secrets.llm_search.groq_api_key_secret": "llm_search.GROQ_API_KEY_SECRET_NAME",
}

CONFIG_ENDPOINT_PLACEHOLDER_RE = re.compile(r"%\(([A-Za-z0-9_]+)\)s")
CONFIG_REF_RE = re.compile(r"\bconfig\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+")
PIM_REF_RE = re.compile(r"\bpim\.[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+")
KEY_PATTERN = r"(?:([A-Za-z_][A-Za-z0-9_]*)|'([^']+)'|\"([^\"]+)\")"
OBJECT_START_RE = re.compile(rf"^\s*{KEY_PATTERN}\s*:\s*\{{\s*$")
OBJECT_EMPTY_RE = re.compile(rf"^\s*{KEY_PATTERN}\s*:\s*\{{\s*\}}\s*,?\s*$")
VALUE_RE = re.compile(rf"^\s*{KEY_PATTERN}\s*:\s*(.+)$")
ENV_KEY_RE = re.compile(r'^\s*[\'"]?([A-Z][A-Z0-9_-]*)[\'"]?\s*:\s*(.+?)(?:,\s*)?$')
SIMPLE_LITERAL_RE = re.compile(r"""^(?:'[^']*'|"[^"]*"|-?\d+(?:\.\d+)?|true|false|null)$""")


@dataclass(frozen=True)
class Occurrence:
    file: str
    line: int
    ref: str
    snippet: str


@dataclass(frozen=True)
class PimKey:
    full: str
    short: str
    line: int


def strip_comments(line: str) -> str:
    """Remove // and # comments while preserving quoted URLs."""
    result: list[str] = []
    in_single = False
    in_double = False
    escaped = False

    for idx, char in enumerate(line):
        nxt = line[idx + 1] if idx + 1 < len(line) else ""
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == "\\" and (in_single or in_double):
            result.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            result.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            result.append(char)
            continue
        if not in_single and not in_double:
            if char == "#":
                break
            if char == "/" and nxt == "/":
                break
        result.append(char)
    return "".join(result).rstrip()


def flatten_pim_key(parts: list[str]) -> str:
    if len(parts) >= 3 and parts[1] in {"psm", "defaults"}:
        return ".".join([parts[0]] + parts[2:])
    return ".".join(parts)


def matched_key(match: re.Match[str]) -> str:
    return next(group for group in match.groups()[:3] if group is not None)


def parse_pim_keys(pim_path: Path) -> list[PimKey]:
    stack: list[str] = []
    keys: list[PimKey] = []

    for lineno, raw_line in enumerate(pim_path.read_text().splitlines(), start=1):
        line = strip_comments(raw_line)
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("}"):
            close_count = stripped.count("}")
            for _ in range(close_count):
                if stack:
                    stack.pop()
            continue

        match = OBJECT_EMPTY_RE.match(line)
        if match:
            continue

        match = OBJECT_START_RE.match(line)
        if match:
            stack.append(matched_key(match))
            continue

        match = VALUE_RE.match(line)
        if match and stack:
            key = matched_key(match)
            value = match.groups()[-1].strip()
            if value == "{":
                stack.append(key)
                continue
            parts = stack + [key]
            keys.append(PimKey(full=".".join(parts), short=flatten_pim_key(parts), line=lineno))

    return keys


def infer_endpoint_refs(line: str) -> list[str]:
    if "config.endpoint" not in line or "% config.endpoint" not in line:
        return []
    return [f"config.endpoint.{name}" for name in CONFIG_ENDPOINT_PLACEHOLDER_RE.findall(line)]


def collect_manifest_refs(lib_dir: Path) -> tuple[list[Occurrence], list[Occurrence], list[Occurrence]]:
    config_refs: list[Occurrence] = []
    pim_refs: list[Occurrence] = []
    hardcoded_literals: list[Occurrence] = []

    for path in sorted(lib_dir.rglob("*.libsonnet")):
        if path.name == "pim.libsonnet":
            continue
        rel = str(path.relative_to(lib_dir.parent))
        for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
            line = strip_comments(raw_line)
            if not line.strip():
                continue

            refs = set(CONFIG_REF_RE.findall(line))
            refs.update(infer_endpoint_refs(line))
            for ref in sorted(refs):
                config_refs.append(Occurrence(rel, lineno, ref, raw_line.rstrip()))

            for ref in sorted(set(PIM_REF_RE.findall(line))):
                pim_refs.append(Occurrence(rel, lineno, ref, raw_line.rstrip()))

            match = ENV_KEY_RE.match(line)
            if match and path.name != "stdports.libsonnet":
                key, value = match.groups()
                if SIMPLE_LITERAL_RE.fullmatch(value.strip()):
                    hardcoded_literals.append(Occurrence(rel, lineno, key, raw_line.rstrip()))

    return config_refs, pim_refs, hardcoded_literals


def dedupe_occurrences(items: Iterable[Occurrence]) -> list[Occurrence]:
    seen = set()
    result = []
    for item in items:
        key = (item.file, item.line, item.ref)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_report(repo_root: Path, pim_path: Path, lib_dir: Path) -> dict:
    pim_keys = parse_pim_keys(pim_path)
    config_refs, pim_refs, hardcoded_literals = collect_manifest_refs(lib_dir)

    inventory_by_short: dict[str, PimKey] = {}
    inventory_by_leaf: dict[str, list[PimKey]] = defaultdict(list)
    for key in pim_keys:
        inventory_by_short[key.short] = key
        inventory_by_leaf[key.short.split(".")[-1]].append(key)

    missing_from_pim = []
    owner_mismatches = []
    unmapped_config_refs = []
    used_inventory = set()

    for occ in dedupe_occurrences(config_refs):
        expected = CONFIG_TO_PIM.get(occ.ref)
        if expected is None:
            unmapped_config_refs.append(
                {
                    "ref": occ.ref,
                    "file": occ.file,
                    "line": occ.line,
                    "snippet": occ.snippet,
                }
            )
            continue

        if expected in inventory_by_short:
            used_inventory.add(expected)
            continue

        leaf = expected.split(".")[-1]
        alternatives = [key.short for key in inventory_by_leaf.get(leaf, [])]
        target = {
            "ref": occ.ref,
            "expected_pim_key": expected,
            "file": occ.file,
            "line": occ.line,
            "snippet": occ.snippet,
        }
        if alternatives:
            target["alternatives"] = alternatives
            owner_mismatches.append(target)
        else:
            missing_from_pim.append(target)

    stale_pim_refs = []
    for occ in dedupe_occurrences(pim_refs):
        short = occ.ref.removeprefix("pim.")
        if short in inventory_by_short:
            used_inventory.add(short)
            continue
        stale_pim_refs.append(
            {
                "ref": occ.ref,
                "file": occ.file,
                "line": occ.line,
                "snippet": occ.snippet,
            }
        )

    unused_pim_keys = [
        {
            "pim_key": key.short,
            "full_path": key.full,
            "line": key.line,
        }
        for key in pim_keys
        if key.short not in used_inventory
    ]

    covered_literal_envs = []
    missing_literal_envs = []
    for occ in dedupe_occurrences(hardcoded_literals):
        target = {
            "env": occ.ref,
            "file": occ.file,
            "line": occ.line,
            "snippet": occ.snippet,
        }
        if occ.ref in inventory_by_leaf:
            covered_literal_envs.append(target)
        else:
            missing_literal_envs.append(target)

    return {
        "repo_root": str(repo_root),
        "pim_file": str(pim_path.relative_to(repo_root)),
        "lib_dir": str(lib_dir.relative_to(repo_root)),
        "summary": {
            "pim_keys": len(pim_keys),
            "config_refs": len(dedupe_occurrences(config_refs)),
            "pim_refs": len(dedupe_occurrences(pim_refs)),
            "missing_from_pim": len(missing_from_pim),
            "owner_mismatches": len(owner_mismatches),
            "unmapped_config_refs": len(unmapped_config_refs),
            "stale_pim_refs": len(stale_pim_refs),
            "unused_pim_keys": len(unused_pim_keys),
            "hardcoded_literal_envs": len(dedupe_occurrences(hardcoded_literals)),
            "hardcoded_literal_envs_missing_from_pim": len(missing_literal_envs),
        },
        "missing_from_pim": missing_from_pim,
        "owner_mismatches": owner_mismatches,
        "unmapped_config_refs": unmapped_config_refs,
        "stale_pim_refs": stale_pim_refs,
        "unused_pim_keys": unused_pim_keys,
        "hardcoded_literal_envs": covered_literal_envs + missing_literal_envs,
        "hardcoded_literal_envs_covered_by_pim": covered_literal_envs,
        "hardcoded_literal_envs_missing_from_pim": missing_literal_envs,
    }


def print_section(title: str, rows: list[dict], key_field: str, limit: int) -> None:
    print(f"\n{title} ({len(rows)})")
    if not rows:
        print("  none")
        return

    for row in rows[:limit]:
        if "file" in row:
            location = f"{row['file']}:{row['line']}"
        else:
            location = f"lib/pim.libsonnet:{row['line']}"
        print(f"  - {row[key_field]} [{location}]")
    if len(rows) > limit:
        print(f"  ... {len(rows) - limit} more")


def print_report(report: dict, limit: int) -> None:
    summary = report["summary"]
    print("PIM coverage summary")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print_section("Missing from PIM", report["missing_from_pim"], "expected_pim_key", limit)
    print_section("Owner mismatches", report["owner_mismatches"], "expected_pim_key", limit)
    print_section("Unmapped config refs", report["unmapped_config_refs"], "ref", limit)
    print_section("Stale manifest PIM refs", report["stale_pim_refs"], "ref", limit)
    print_section("Unused PIM keys", report["unused_pim_keys"], "pim_key", limit)
    print_section(
        "Hardcoded literal envs missing from PIM",
        report["hardcoded_literal_envs_missing_from_pim"],
        "env",
        limit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pim", type=Path, default=None, help="Path to pim.libsonnet")
    parser.add_argument("--lib-dir", type=Path, default=None, help="Path to lib directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--limit", type=int, default=20, help="Max rows per section in text output")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    pim_path = (args.pim or repo_root / "lib" / "pim.libsonnet").resolve()
    lib_dir = (args.lib_dir or repo_root / "lib").resolve()

    report = build_report(repo_root, pim_path, lib_dir)

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        print_report(report, args.limit)

    has_failures = any(
        report["summary"][key] > 0
        for key in ("missing_from_pim", "owner_mismatches", "unmapped_config_refs", "stale_pim_refs")
    )
    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
