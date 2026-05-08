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

from typing import Annotated
import time
from pathlib import Path

import typer
from kubernetes import config

app = typer.Typer(name="stelarctl", help="STELAR deployment management tool")


@app.command("status")
def status_command():
    typer.echo("Hello cruel world")


@app.command("model")
def model_command(
    name: Annotated[str, typer.Argument(help="The name of the model to process")],
    address: Annotated[
        str, typer.Option("--address", "-a", help="The address of the model to process")
    ],
):
    typer.echo(f"Model {name} processed at {address}")


if __name__ == "__main__":
    app()
