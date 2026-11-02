# UniConv

A local, installable desktop app that converts one file at a time within one family:
image, data, document or audio/video. Nothing leaves your machine.

## Development

```bash
python -m venv .venv            # Python 3.12
.venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip
python scripts/fetch_binaries.py    # pinned Pandoc + ffmpeg into vendor/
ruff check . && pytest -q
python -m uniconv convert photo.heic --to png --out ./out
```

License: GPL-3.0-or-later.
