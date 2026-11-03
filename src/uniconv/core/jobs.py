"""The only place that ties detection, options, work dir and converter together."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from uniconv.config import AppConfig
from uniconv.core.converter import CancelToken, ConversionContext
from uniconv.core.errors import (
    ConversionCancelled,
    ConversionError,
    InputTooLargeError,
    UniconvError,
)
from uniconv.core.registry import Registry
from uniconv.core.workspace import Workspace

log = logging.getLogger(__name__)


@dataclass
class Job:
    family: str
    target: str
    inputs: list[Path]          # v1 UI: always length 1
    output_dir: Path | None     # None = next to each input. Resolved by the caller (review #3).
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ItemResult:
    input: Path
    status: Literal["done", "skipped", "failed", "cancelled"]
    output: Path | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def _no_progress(i: int, p: float) -> None:
    pass


class JobRunner:
    def __init__(self, registry: Registry, workspace: Workspace, cfg: AppConfig) -> None:
        self.registry, self.workspace, self.cfg = registry, workspace, cfg

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg  # called by the UI after saving settings; never during a running job

    def run(self, job: Job, cancel: CancelToken,
            on_progress: Callable[[int, float], None] = _no_progress) -> list[ItemResult]:
        results = []
        for i, src in enumerate(job.inputs):  # one failed item never stops the others
            if cancel.cancelled:
                results.append(ItemResult(src, "cancelled"))
            else:
                results.append(self._run_one(job, i, src, cancel, on_progress))
        return results

    def _run_one(self, job: Job, i: int, src: Path, cancel: CancelToken,
                 on_progress: Callable[[int, float], None]) -> ItemResult:
        name = f"{job.id}-{i}"
        try:
            work = self.workspace.job_dir(name)
            try:
                size = src.stat().st_size
            except OSError as exc:
                raise ConversionError(f"Kan {src.name} niet lezen: {exc.strerror}") from exc
            if size > self.cfg.limits.max_input_mb * 1024 * 1024:
                raise InputTooLargeError(
                    f"{src.name} is groter dan {self.cfg.limits.max_input_mb} MB"
                )
            source = self.registry.detect(src, job.family)
            target = self.registry.format(job.target)
            conv = self.registry.find(job.family, source.key, target.key)
            ctx = ConversionContext(
                input_path=src, output_path=work / f"out{target.extensions[0]}",
                source=source, target=target,
                options=self.registry.options_for(conv, self.cfg),
                timeout_s=self.cfg.limits.timeout_seconds, cancel=cancel,
                on_progress=lambda p: on_progress(i, p),
            )
            conv.convert(ctx)
            cancel.raise_if_cancelled()
            if not ctx.output_path.is_file():
                raise ConversionError("De conversie leverde geen bestand op")
            out = self.workspace.finalize(
                ctx.output_path, job.output_dir or src.parent,
                src.stem, target.extensions[0], self.cfg.behavior.overwrite,
            )
            on_progress(i, 1.0)
            return ItemResult(src, "skipped" if out is None else "done", out,
                              warnings=ctx.warnings)
        except ConversionCancelled:
            return ItemResult(src, "cancelled")
        except UniconvError as exc:
            return ItemResult(src, "failed", error=str(exc))
        except Exception as exc:  # engine bug: log the traceback, show a short message
            log.exception("Unexpected failure converting %s", src)
            return ItemResult(src, "failed", error=f"Onverwachte fout: {exc}")
        finally:
            self.workspace.discard(name)
