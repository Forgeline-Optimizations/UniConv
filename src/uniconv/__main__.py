import sys

from uniconv import __version__


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m uniconv`, the console script and the PyInstaller build."""
    argv = sys.argv[1:] if argv is None else argv
    argv = [a for a in argv if not a.startswith("-psn_")]  # macOS Finder process serial number
    if argv == ["--version"]:
        print(__version__)
        return 0
    if argv:
        from uniconv.cli import run_cli  # lazy: the CLI never imports Qt
        return run_cli(argv)
    from uniconv.ui.app import run_gui  # lazy: CLI runs stay free of Qt start-up cost
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
