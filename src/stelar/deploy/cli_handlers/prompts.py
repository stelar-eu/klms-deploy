"""Reusable Typer prompt helpers."""

from __future__ import annotations

import typer


def prompt_required(label: str, *, default: str | None = None) -> str:
    """Prompt until the user provides a non-empty value."""
    while True:
        value = typer.prompt(label, default=default).strip()
        if value:
            return value
        typer.echo(f"{label} cannot be empty", err=True)


def prompt_secret(label: str, *, min_length: int = 1) -> str:
    """Prompt for a secret value, confirming and enforcing a minimum length."""
    while True:
        value = typer.prompt(
            label,
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(value) >= min_length:
            return value
        if min_length == 1:
            typer.echo(f"{label} cannot be empty", err=True)
        else:
            typer.echo(
                f"{label} must be at least {min_length} characters long",
                err=True,
            )


def prompt_choice(label: str, choices: tuple[str, ...], *, default: str) -> str:
    """Prompt until the user provides one of the supported choices."""
    choice_list = "/".join(choices)
    while True:
        value = typer.prompt(f"{label} [{choice_list}]", default=default).strip()
        if value in choices:
            return value
        typer.echo(f"{label} must be one of: {choice_list}", err=True)
