"""Small output-formatting helpers shared by CLI handlers."""

from __future__ import annotations


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def presence(value: bool) -> str:
    return "present" if value else "missing"


def item_list(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "(none)"
