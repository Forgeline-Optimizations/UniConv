import sys

from uniconv import __version__


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m uniconv`, the console script and the PyInstaller build."""
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--version"]:
        print(__version__)
        return 0
    if argv:
        from uniconv.cli import run_cli  # lazy: the CLI never imports Qt
        return run_cli(argv)
    print("uniconv: GUI arrives in step 19, use a subcommand", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
