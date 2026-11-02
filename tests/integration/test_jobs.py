from pydantic import BaseModel

from uniconv.config import AppConfig, LimitsConfig, PathsConfig
from uniconv.core.converter import CancelToken, Converter, Format
from uniconv.core.errors import ConversionError
from uniconv.core.jobs import Job, JobRunner


class _Options(BaseModel):
    pass


class FailingConverter(Converter):
    """Own family + format: also proves a family can be added without touching the core."""
    family, family_label, Options = "failtest", "Faaltest", _Options
    formats = (Format("failsrc", "Fail-bron", (".failsrc",), target=False),
               Format("failout", "Fail-doel", (".failout",), source=False))

    def convert(self, ctx):
        ctx.output_path.write_bytes(b"half a fi")
        raise ConversionError("Opzettelijk mislukt")


class CancellingConverter(FailingConverter):
    family = "canceltest"
    formats = (Format("cancelsrc", "C", (".cancelsrc",), target=False),
               Format("cancelout", "C", (".cancelout",), source=False))

    def convert(self, ctx):
        ctx.output_path.write_bytes(b"complete but cancelled")
        ctx.cancel.cancel()


def test_failed_conversion_leaves_nothing_behind(registry, runner, workspace, out_dir, tmp_path):
    registry.register(FailingConverter())
    src = tmp_path / "in.failsrc"
    src.write_bytes(b"data")
    [result] = runner.run(Job("failtest", "failout", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert result.error == "Opzettelijk mislukt"
    assert list(out_dir.iterdir()) == []
    assert list(workspace.root.iterdir()) == []


def test_one_broken_input_does_not_stop_the_others(runner, make_sample, out_dir, tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"\x89PNG\r\n\x1a\nnot really")
    good = make_sample("png")
    results = runner.run(Job("image", "jpg", [broken, good], out_dir), CancelToken())
    assert [r.status for r in results] == ["failed", "done"]
    assert results[0].error


def test_cancelled_job_produces_no_output(runner, make_sample, out_dir):
    cancel = CancelToken()
    cancel.cancel()
    [result] = runner.run(Job("image", "jpg", [make_sample("png")], out_dir), cancel)
    assert result.status == "cancelled"
    assert list(out_dir.iterdir()) == []


def test_cancel_during_convert_discards_result(registry, runner, workspace, out_dir, tmp_path):
    registry.register(CancellingConverter())
    src = tmp_path / "in.cancelsrc"
    src.write_bytes(b"x")
    [result] = runner.run(Job("canceltest", "cancelout", [src], out_dir), CancelToken())
    assert result.status == "cancelled"
    assert list(out_dir.iterdir()) == []
    assert list(workspace.root.iterdir()) == []


def test_too_large_input_is_refused(registry, workspace, make_sample, out_dir, tmp_path):
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    limits=LimitsConfig(max_input_mb=1))
    big = make_sample("bmp", size=(1000, 1000))  # ~3 MB uncompressed
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("image", "png", [big], out_dir), CancelToken())
    assert result.status == "failed"
    assert "groter dan 1 MB" in result.error


def test_output_dir_none_writes_next_to_source(runner, make_sample):
    """Review #3: the caller decides; None means beside the input."""
    src = make_sample("png", name="naast")
    [result] = runner.run(Job("image", "jpg", [src], None), CancelToken())
    assert result.status == "done"
    assert result.output == src.with_suffix(".jpg")


def test_runner_ignores_cfg_paths_output_dir(registry, workspace, make_sample, out_dir, tmp_path):
    """Review #3: a stale cfg.paths.output_dir must never win over Job.output_dir."""
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work",
                                      output_dir=tmp_path / "stale"))
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("image", "jpg", [make_sample("png")], out_dir), CancelToken())
    assert result.output.parent == out_dir
    assert not (tmp_path / "stale").exists()


def test_progress_reaches_one(runner, make_sample, out_dir):
    seen = []
    runner.run(Job("image", "jpg", [make_sample("png")], out_dir), CancelToken(),
               on_progress=lambda i, p: seen.append((i, p)))
    assert seen[-1] == (0, 1.0)


def test_invalid_options_fail_readably(registry, workspace, make_sample, out_dir, tmp_path):
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"image": {"jpeg_quality": 120}})
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("image", "jpg", [make_sample("png")], out_dir), CancelToken())
    assert result.status == "failed"
    assert "defaults.image.jpeg_quality" in result.error
