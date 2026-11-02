"""Temporary files live here; only finalize() writes to the user's folder."""

import os
import shutil
import time
from datetime import timedelta
from pathlib import Path

from uniconv.core.errors import ConversionError

PARTIAL_SUFFIX = ".uniconv-partial"


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, name: str) -> Path:
        d = self.root / name
        d.mkdir()
        return d

    def discard(self, name: str) -> None:
        shutil.rmtree(self.root / name, ignore_errors=True)

    def cleanup_stale(self, older_than: timedelta = timedelta(hours=24)) -> None:
        # 24h, not 1h: a second app instance must not delete a long video job of the first
        cutoff = time.time() - older_than.total_seconds()
        for d in self.root.iterdir():
            try:
                if d.is_dir() and d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                continue

    def finalize(self, tmp: Path, dest_dir: Path, stem: str, ext: str, policy: str) -> Path | None:
        """Move tmp to dest_dir/stem+ext. None when policy is 'skip' and the file exists."""
        dest = dest_dir / f"{stem}{ext}"
        staged: Path | None = None
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                if policy == "skip":
                    return None
                if policy == "rename":
                    dest = _unique(dest)
            staged = dest_dir / f".{dest.name}{PARTIAL_SUFFIX}"
            shutil.move(tmp, staged)   # may copy across volumes: never under the final name
            os.replace(staged, dest)   # atomic, and unlike shutil.move it overwrites on Windows
            return dest
        except PermissionError as exc:
            raise ConversionError(
                f"Kan {dest.name} niet opslaan: geen schrijfrechten of het bestand is geopend "
                "in een ander programma"
            ) from exc
        except OSError as exc:
            raise ConversionError(
                f"Kan niet opslaan in {dest_dir}: {exc.strerror or exc}"
            ) from exc
        finally:
            if staged is not None and staged.exists():
                try:
                    staged.unlink()
                except OSError:
                    pass


def _unique(dest: Path) -> Path:
    """"foto.png" -> "foto (1).png", "foto (2).png", ..."""
    n = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        if not candidate.exists():
            return candidate
        n += 1
