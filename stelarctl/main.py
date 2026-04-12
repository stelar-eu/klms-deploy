try:
    from .cli import app
except ImportError:
    from stelarctl.cli import app


def main():
    app()


if __name__ == "__main__":
    main()
