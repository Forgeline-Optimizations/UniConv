# Third-party licenses

UniConv is licensed under the GNU General Public License v3.0 or later (see `LICENSE`).
The installers bundle the components below. Their license texts ship in the app folder
(`LICENSE`, `licenses/`) and are linked here together with the source code of the exact
version used. Versions of the external tools are pinned in `scripts/fetch_binaries.py`
(see `.claude/decisions/ADR-001-pinned-binary-sources.md` and `ADR-002`).

## Bundled programs

| Component | Version | License | Source code |
|---|---|---|---|
| Pandoc | 3.13 | GPL-2.0-or-later | https://github.com/jgm/pandoc/tree/3.13 |
| FFmpeg (ffmpeg, ffprobe), Windows build by gyan.dev | 9.0.2 | GPL-3.0-or-later (built with `--enable-gpl --enable-version3`) | https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz, build scripts and library list: https://www.gyan.dev/ffmpeg/builds/ |
| FFmpeg (ffmpeg, ffprobe), macOS arm64 build by Martin Riedl | 9.0.2 | GPL-3.0-or-later (built with `--enable-gpl --enable-version3`) | https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz, build scripts: https://gitlab.com/martinr92/ffmpeg |
| Typst | 0.15.1 | Apache-2.0 (`licenses/typst-LICENSE.txt`, `licenses/typst-NOTICE.txt`) | https://github.com/typst/typst/tree/v0.15.1 |
| resvg | 0.49.0 | Apache-2.0 OR MIT (`licenses/resvg-LICENSE-*.txt`) | https://github.com/linebender/resvg/tree/v0.49.0 |

The FFmpeg builds statically include, among others, x264 (GPL-2.0-or-later), libvpx
(BSD-3-Clause), Opus (BSD-3-Clause), LAME (LGPL-2.0-or-later) and libvorbis (BSD-3-Clause).
The complete list of libraries and versions per build is in `licenses/ffmpeg-README.txt`
(Windows) and at https://ffmpeg.martin-riedl.de (macOS, "versions.txt" of build
`1789931890_9.0.2`).

## Python runtime and libraries

| Component | Version | License | Source code |
|---|---|---|---|
| CPython | 3.12 | PSF-2.0 | https://github.com/python/cpython |
| PySide6 / Shiboken6 (Qt for Python) | 6.12.0 | LGPL-3.0-only (used under LGPL) | https://code.qt.io/cgit/pyside/pyside-setup.git |
| Qt 6 libraries | 6.12 | LGPL-3.0-only | https://code.qt.io/cgit/qt/qt5.git |
| Pillow | 13.0.0 | MIT-CMU | https://github.com/python-pillow/Pillow |
| pillow-heif | 1.8.1 | BSD-3-Clause | https://github.com/bigcat88/pillow_heif |
| libheif (via pillow-heif) | 1.23.6 | LGPL-3.0-or-later | https://github.com/strukturag/libheif |
| libde265 (via pillow-heif) | bundled | LGPL-3.0-or-later | https://github.com/strukturag/libde265 |
| pandas | 3.1.0 | BSD-3-Clause | https://github.com/pandas-dev/pandas |
| NumPy | 2.5.4 | BSD-3-Clause and others | https://github.com/numpy/numpy |
| openpyxl | 3.1.5 | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| et-xmlfile | 2.0.0 | MIT | https://foss.heptapod.net/openpyxl/et_xmlfile |
| PyYAML | 6.0.3 | MIT | https://github.com/yaml/pyyaml |
| tomli-w | 1.2.0 | MIT | https://github.com/hukkin/tomli-w |
| xmltodict | 1.0.4 | MIT | https://github.com/martinblech/xmltodict |
| filetype | 1.2.0 | MIT | https://github.com/h2non/filetype.py |
| platformdirs | 4.14.3 | MIT | https://github.com/tox-dev/platformdirs |
| pydantic / pydantic-core | 2.14.2 / 2.50.2 | MIT | https://github.com/pydantic/pydantic |
| python-dateutil | 4.0.0 | BSD-3-Clause / Apache-2.0 | https://github.com/dateutil/dateutil |
| tzdata | 2026.6 | Apache-2.0 | https://github.com/python/tzdata |
| typing-extensions, annotated-types, typing-inspection | see wheel | PSF-2.0 / MIT | https://pypi.org |
| img2pdf | 0.6.3 | LGPL-3.0-or-later | https://gitlab.mister-muffin.de/josch/img2pdf |
| pikepdf | 10.17.0 | MPL-2.0 | https://github.com/pikepdf/pikepdf |
| qpdf (inside pikepdf) | bundled | Apache-2.0 | https://github.com/qpdf/qpdf |
| vtracer | 0.6.15 | MIT | https://github.com/visioncortex/vtracer |
| trimesh | 5.2.0 | MIT | https://github.com/mikedh/trimesh |
| SciPy | 1.18.1 | BSD-3-Clause (bundles further permissive libraries) | https://github.com/scipy/scipy |
| NetworkX | 3.7 | BSD-3-Clause | https://github.com/networkx/networkx |
| lxml (with libxml2, libxslt) | 6.1.3 | BSD-3-Clause (libxml2/libxslt: MIT) | https://github.com/lxml/lxml |

The application is frozen with PyInstaller 6 (GPL-2.0-or-later with the bootloader
exception, which permits distributing the bundled app under any license).

All components are compatible with GPL-3.0-or-later. For img2pdf (LGPL-3.0) and pikepdf
(MPL-2.0) the license text and a source link suffice; they are unmodified.

## Detected, not bundled

LibreOffice and Chrome / Edge / Chromium are **not** included in UniConv. When the user has
installed one of them, UniConv starts it as a separate program for Office-to-PDF and
HTML-to-PDF conversions (see `src/uniconv/core/apps.py`). Their licenses apply to the copy
the user installed.

## Obtaining the source

The complete corresponding source of UniConv is this repository at the tag of the release.
For the bundled binaries, use the source links above for the listed version. If a link
stops working, open an issue at https://github.com/Forgeline-Optimizations/UniConv/issues
and we will provide the source, as required by the GPL.
