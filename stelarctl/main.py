"""Console entry point for the `stelarctl` command.

Keeping the executable entry point separate from `cli.py` lets packaging point
at one tiny `main()` function while the Typer app and command implementation
remain importable from tests.
"""

try:
    from .cli import app
except ImportError:
    # Allow running this file in environments that place stelarctl on
    # PYTHONPATH without installing it as a package.
    from stelarctl.cli import app


def main():
    """Invoke the Typer application."""
    app()


if __name__ == "__main__":
    main()
