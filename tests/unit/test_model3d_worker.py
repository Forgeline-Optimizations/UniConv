"""The trimesh worker itself, called in-process (the isolation is tested in test_isolate)."""

import pytest

from uniconv.converters.model3d import _convert_worker
from uniconv.core.errors import ConversionError

trimesh = pytest.importorskip("trimesh")


def _two_objects(path):
    scene = trimesh.Scene(
        [trimesh.creation.box(), trimesh.creation.icosphere().apply_translation([3, 0, 0])]
    )
    path.write_bytes(scene.export(file_type="glb"))
    return path


def test_scene_to_stl_merges_and_warns(tmp_path):
    src = _two_objects(tmp_path / "s.glb")
    warnings = _convert_worker(str(src), str(tmp_path / "o.stl"), "glb", "stl")
    assert any("samengevoegd" in w for w in warnings)
    assert len(trimesh.load(tmp_path / "o.stl").faces) > 12


def test_empty_stl_is_refused(tmp_path):
    src = tmp_path / "leeg.stl"
    src.write_text("solid leeg\nendsolid leeg\n")
    with pytest.raises(ConversionError, match="geen 3D-geometrie"):
        _convert_worker(str(src), str(tmp_path / "o.glb"), "stl", "glb")
