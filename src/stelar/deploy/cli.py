"""Typer command definitions for the `stelarctl` executable.

This module keeps CLI concerns small: parse command-line arguments, resolve a
target deployment, load the platform model, and delegate real work to the
deployment, environment, status, and secret modules.

Command functions should stay thin. If a branch starts to need Kubernetes API
logic, Tanka command orchestration, or model comparison rules, that behavior
belongs in the supporting modules so it can be unit-tested without invoking the
CLI runner.
"""

from __future__ import annotations

import time
from pathlib import Path

import typer
from kubernetes import config

app = typer.Typer(name="stelarctl", help="STELAR deployment management tool")


@app.command("status")
def status_command():
    typer.echo("Hello cruel world")


if __name__=='__main__':
    app()

