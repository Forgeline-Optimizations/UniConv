"""Download pinned Pandoc/ffmpeg/ffprobe into vendor/<platform_tag>/ (sources: ADR-001).

Idempotent: when vendor/<tag>/.manifest-hash matches this manifest, nothing happens.
Usage: python scripts/fetch_binaries.py [--tag win32-x86_64|darwin-arm64]
"""

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANDOC = "3.13"
FFMPEG = "9.0.2"
TYPST = "0.15.1"
RESVG = "0.49.0"
_RIEDL = "https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2"
_TYPST = f"https://github.com/typst/typst/releases/download/v{TYPST}"
_RESVG = f"https://github.com/linebender/resvg/releases/download/v{RESVG}"


@dataclass(frozen=True)
class Archive:
    url: str
    sha256: str
    members: dict[str, str]                       # output name -> path inside the archive
    licenses: dict[str, str] = field(default_factory=dict)  # licenses/<name> -> archive path


MANIFEST: dict[str, list[Archive]] = {
    "win32-x86_64": [
        Archive(
            f"https://github.com/jgm/pandoc/releases/download/{PANDOC}/"
            f"pandoc-{PANDOC}-windows-x86_64.zip",
            "23e1f2e978a3df80db8bf65c9c59534f41a23140480cfb4f783a882ab7dc6a4e",
            {"pandoc.exe": f"pandoc-{PANDOC}/pandoc.exe"},
            {"pandoc-COPYRIGHT.txt": f"pandoc-{PANDOC}/COPYRIGHT.txt"},
        ),
        Archive(
            f"https://github.com/GyanD/codexffmpeg/releases/download/{FFMPEG}/"
            f"ffmpeg-{FFMPEG}-essentials_build.zip",
            "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba",
            {"ffmpeg.exe": f"ffmpeg-{FFMPEG}-essentials_build/bin/ffmpeg.exe",
             "ffprobe.exe": f"ffmpeg-{FFMPEG}-essentials_build/bin/ffprobe.exe"},
            {"ffmpeg-LICENSE.txt": f"ffmpeg-{FFMPEG}-essentials_build/LICENSE",
             "ffmpeg-README.txt": f"ffmpeg-{FFMPEG}-essentials_build/README.txt"},
        ),
        Archive(
            f"{_TYPST}/typst-x86_64-pc-windows-msvc.zip",
            "19ce3551153c2fe7ee9fa2f95208310c8f4d3209fedb699e0333faf8913f6736",
            {"typst.exe": "typst-x86_64-pc-windows-msvc/typst.exe"},
            {"typst-LICENSE.txt": "typst-x86_64-pc-windows-msvc/LICENSE",
             "typst-NOTICE.txt": "typst-x86_64-pc-windows-msvc/NOTICE"},
        ),
        Archive(
            f"{_RESVG}/resvg-win-x86_64.zip",
            "38af9631b37e61118a32a5ef31e6be6af083eda63b4c17ffc4fdc63e449277df",
            {"resvg.exe": "resvg.exe"},  # no license file inside: packaging/licenses/
        ),
    ],
    "darwin-arm64": [
        Archive(
            f"https://github.com/jgm/pandoc/releases/download/{PANDOC}/"
            f"pandoc-{PANDOC}-arm64-macOS.zip",
            "f436d18bebbfb3ddd326597686dacab9fac5dc23bd060495020f35a28a43a7c3",
            {"pandoc": f"pandoc-{PANDOC}-arm64/bin/pandoc"},
        ),
        Archive(
            f"{_RIEDL}/ffmpeg.zip",
            "c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924",
            {"ffmpeg": "ffmpeg"},
        ),
        Archive(
            f"{_RIEDL}/ffprobe.zip",
            "fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6",
            {"ffprobe": "ffprobe"},
        ),
        Archive(
            f"{_TYPST}/typst-aarch64-apple-darwin.tar.xz",
            "48f62ed034aa3a7978309579ac6ca00045e2ef0da73114e8af27cfd8e74dc05a",
            {"typst": "typst-aarch64-apple-darwin/typst"},
            {"typst-LICENSE.txt": "typst-aarch64-apple-darwin/LICENSE",
             "typst-NOTICE.txt": "typst-aarch64-apple-darwin/NOTICE"},
        ),
        Archive(
            f"{_RESVG}/resvg-macos-aarch64.zip",
            "847acb5210c7c6244b5e8f07dd62fa1ce596108cce8193628ebfd5750504b259",
            {"resvg": "resvg"},
        ),
    ],
}


def platform_tag() -> str:
    # Same rule as uniconv.core.tools.platform_tag; duplicated so this script needs no install.
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
    machine = platform.machine().lower()
    return f"{sys.platform}-{arch.get(machine, machine)}"


def manifest_hash(archives: list[Archive]) -> str:
    blob = json.dumps([asdict(a) for a in archives], sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def download(url: str, dest: Path, expected: str) -> None:
    print(f"  downloading {url}")
    digest = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "uniconv-fetch-binaries"})
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as fh:
        while chunk := resp.read(1 << 20):
            digest.update(chunk)
            fh.write(chunk)
    if digest.hexdigest() != expected:
        raise SystemExit(f"SHA-256 mismatch for {url}:\n  got  {digest.hexdigest()}\n"
                         f"  want {expected}")


def extract(archive: Path, member: str, dest: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf, zf.open(member) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
    else:  # .tar.xz / .tar.gz: read the named member only, never extractall() (review #19)
        with tarfile.open(archive) as tf:
            src = tf.extractfile(member)
            if src is None:
                raise SystemExit(f"{member} in {archive.name} is not a regular file")
            with src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
    if sys.platform != "win32":
        dest.chmod(0o755)  # zip does not always keep the executable bit


def fetch(tag: str) -> Path:
    if tag not in MANIFEST:
        raise SystemExit(f"No binaries pinned for {tag}; known: {', '.join(MANIFEST)}")
    archives = MANIFEST[tag]
    target = ROOT / "vendor" / tag
    stamp = target / ".manifest-hash"
    want = manifest_hash(archives)
    if stamp.is_file() and stamp.read_text().strip() == want:
        print(f"vendor/{tag} is up to date")
        return target

    staging = target.with_name(f".{tag}.staging")
    shutil.rmtree(staging, ignore_errors=True)
    (staging / "licenses").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        for i, archive in enumerate(archives):
            # keep the real name: extract() picks zip or tar from the extension
            path = Path(tmp) / f"{i}-{archive.url.rsplit('/', 1)[-1]}"
            download(archive.url, path, archive.sha256)
            for name, member in archive.members.items():
                extract(path, member, staging / name)
            for name, member in archive.licenses.items():
                extract(path, member, staging / "licenses" / name)
    (staging / ".manifest-hash").write_text(want)
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)  # only a complete set ever appears under vendor/<tag>
    print(f"vendor/{tag} ready: {', '.join(sorted(p.name for p in target.iterdir()))}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default=platform_tag())
    fetch(parser.parse_args().tag)


if __name__ == "__main__":
    main()
