"""The core must stay usable without Qt: no PySide6 or uniconv.ui below the UI layer."""

import ast
from pathlib import Path

import pytest

import uniconv

PKG = Path(uniconv.__file__).parent
FORBIDDEN = ("PySide6", "uniconv.ui", "shiboken6")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize(
    "path",
    [p for sub in ("core", "converters") for p in sorted((PKG / sub).rglob("*.py"))]
    + [PKG / "cli.py", PKG / "config.py", PKG / "paths.py"],
    ids=lambda p: p.relative_to(PKG).as_posix(),
)
def test_no_qt_below_ui(path):
    bad = [n for n in _imports(path) if n.startswith(FORBIDDEN)]
    assert not bad, f"{path.name} imports {bad}"
