# PyInstaller spec: onedir build (faster start-up, fewer antivirus false positives than onefile).
# Build: python scripts/fetch_binaries.py && pyinstaller packaging/uniconv.spec --noconfirm
# ruff: noqa
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from uniconv import __version__  # noqa: E402
from uniconv.core.tools import platform_tag  # noqa: E402  (same tag as at runtime)

vendor = ROOT / "vendor" / platform_tag()
if not vendor.is_dir():
    raise SystemExit(f"{vendor} missing: run python scripts/fetch_binaries.py first")

# Tools land in <_MEIPASS>/bin, exactly where core.tools.find_tool() looks when frozen.
binaries = [(str(p), "bin") for p in vendor.iterdir() if p.is_file() and not p.name.startswith(".")]
binaries += collect_dynamic_libs("pillow_heif")  # libheif ships as a shared library
datas = [
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_LICENSES.md"), "."),
    (str(vendor / "licenses"), "licenses"),
    (str(ROOT / "packaging" / "licenses"), "licenses"),  # resvg ships none in its zip
]
datas += collect_data_files("trimesh")  # trimesh/resources/*: glTF/3MF templates
icon = ROOT / ("packaging/macos/icon.icns" if sys.platform == "darwin"
               else "packaging/windows/icon.ico")

a = Analysis(
    [str(ROOT / "src/uniconv/__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=["uniconv.cli", "uniconv.ui.app"],  # imported lazily in __main__
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
              "pytest", "pytestqt"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="UniConv",
          console=False, icon=str(icon))
coll = COLLECT(exe, a.binaries, a.datas, name="UniConv")

if sys.platform == "darwin":
    app = BUNDLE(
        coll, name="UniConv.app", icon=str(icon),
        bundle_identifier="io.github.forgeline-optimizations.uniconv",
        version=__version__,  # otherwise Finder shows 0.0.0 (review #15)
        info_plist={
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            # PySide6 >= 6.10, pikepdf 10 and scipy wheels on macos-latest need macOS 14 (#8)
            "LSMinimumSystemVersion": "14.0",
        },
    )
