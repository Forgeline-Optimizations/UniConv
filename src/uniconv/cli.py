"""Command-line front end. Builds a Job and prints one line per result; never imports Qt."""

import argparse
import signal
import sys
from pathlib import Path

from uniconv import __version__
from uniconv.config import load_config
from uniconv.core.converter import CancelToken
from uniconv.core.errors import UniconvError
from uniconv.core.jobs import Job, JobRunner
from uniconv.core.registry import Registry, build_default_registry
from uniconv.core.workspace import Workspace
from uniconv.paths import config_file, resolve_work_dir


def _print_formats(registry: Registry) -> None:
    for family, label in registry.families():
        conv = registry.converter(family)
        print(f"{label} ({family})")
        for src in conv.sources():
            print(f"  {src:6} -> {', '.join(conv.targets(src))}")


def _guess_family(registry: Registry, path: Path) -> str | None:
    for family, _ in registry.families():
        try:
            registry.detect(path, family)
            return family
        except UniconvError:
            continue
    return None


def run_cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="uniconv", description="Converteer bestanden lokaal.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("formats", help="toon ondersteunde formaten per familie")
    c = sub.add_parser("convert", help="converteer een of meer bestanden")
    c.add_argument("inputs", nargs="+", type=Path)
    c.add_argument("--to", required=True, help="doelformaat, bijv. png")
    c.add_argument("--family", help="familie (standaard: automatisch bepaald)")
    c.add_argument("--out", type=Path, help="outputmap (standaard: naast elk invoerbestand)")
    args = p.parse_args(argv)

    cfg = load_config(config_file())
    registry = build_default_registry()
    if args.cmd == "formats":
        _print_formats(registry)
        return 0

    family = args.family
    if family is None:
        family = _guess_family(registry, args.inputs[0])
        if family is None:
            print(f"Onbekend bestandstype: {args.inputs[0].name}", file=sys.stderr)
            return 1
    elif family not in dict(registry.families()):
        print(f"Onbekende familie: {family}", file=sys.stderr)
        return 2

    runner = JobRunner(registry, Workspace(resolve_work_dir(cfg)), cfg)
    cancel = CancelToken()
    signal.signal(signal.SIGINT, lambda *_: cancel.cancel())
    job = Job(family, args.to.lower().lstrip("."), list(args.inputs),
              args.out.resolve() if args.out else None)
    results = runner.run(job, cancel)

    for r in results:
        match r.status:
            case "done":
                print(f"OK      {r.input} -> {r.output}")
            case "skipped":
                print(f"OVERGESLAGEN {r.input} (doel bestaat al)")
            case "cancelled":
                print(f"GEANNULEERD {r.input}")
            case _:
                print(f"MISLUKT {r.input}: {r.error}", file=sys.stderr)
        for w in r.warnings:
            print(f"  let op: {w}")
    return 0 if all(r.status in ("done", "skipped") for r in results) else 1
