"""Console-script entrypoint for the `stelarctl` executable.

The actual Typer app is assembled in :mod:`stelar.deploy.cli_app` so new command
groups can be added without turning this stable entrypoint into a large module.
"""

from __future__ import annotations

from .cli_app import app


def main() -> None:
    """Run the Typer app when the module is executed directly."""
    app()


if __name__ == "__main__":
    main()
