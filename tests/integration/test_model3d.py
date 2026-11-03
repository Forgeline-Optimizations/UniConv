"""3D models between STL, OBJ, PLY, OFF, GLB, glTF and 3MF (plan 0.2 step 18)."""

import json

from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job


def _run(runner, src, target, out_dir):
    [result] = runner.run(Job("model3d", target, [src], out_dir), CancelToken())
    return result


def test_two_objects_to_stl_are_merged_with_a_warning(runner, make_sample, out_dir):
    """Review #16: STL has no scene graph."""
    result = _run(runner, make_sample("glb"), "stl", out_dir)
    assert result.status == "done", result.error
    assert any("samengevoegd" in w for w in result.warnings)


def test_gltf_is_one_file_with_embedded_buffers(runner, make_sample, out_dir):
    result = _run(runner, make_sample("glb"), "gltf", out_dir)
    assert result.status == "done", result.error
    gltf = json.loads(result.output.read_text(encoding="utf-8"))
    assert all(b["uri"].startswith("data:") for b in gltf["buffers"])
    assert [p.name for p in out_dir.iterdir()] == ["sample.gltf"]


def test_obj_makes_no_mtl_next_to_it(runner, make_sample, out_dir):
    """Review #16: OBJ with textures would be several files."""
    result = _run(runner, make_sample("glb"), "obj", out_dir)
    assert result.status == "done", result.error
    assert [p.suffix for p in out_dir.iterdir()] == [".obj"]


def test_glb_to_stl_mentions_axes(registry):
    """Review #16: glTF is Y-up in metres, STL usually Z-up in millimetres."""
    conv = registry.find("model3d", "glb", "stl")
    assert any("Assen" in m for m in conv.expected_losses("glb", "stl"))
    assert not any("Assen" in m for m in conv.expected_losses("glb", "gltf"))


def test_empty_stl_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "leeg.stl"
    src.write_text("solid leeg\nendsolid leeg\n", encoding="utf-8")
    result = _run(runner, src, "glb", out_dir)
    assert result.status == "failed"
    assert "geen 3D-geometrie" in result.error
    assert list(out_dir.iterdir()) == []


def test_garbage_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "kapot.glb"
    src.write_bytes(b"glTF\x02\x00\x00\x00 not really")
    result = _run(runner, src, "stl", out_dir)
    assert result.status == "failed"
    assert not result.error.startswith("Onverwachte fout")


def test_3mf_zip_is_detected_as_3mf(registry, make_sample):
    """filetype says application/zip, which is weak: the extension decides."""
    assert registry.detect(make_sample("3mf"), "model3d").key == "3mf"
