"""3D models via trimesh, in a child process: large meshes can take long or exhaust memory."""

from pathlib import Path

from uniconv.core.converter import ConversionContext, Converter, Format, NoOptions
from uniconv.core.errors import ConversionError
from uniconv.core.isolate import run_isolated

# filetype recognises none of these (3MF is a plain zip, which the registry treats as weak):
# detection is by extension.
_FORMATS = (
    Format("stl", "STL", (".stl",)),
    Format("obj", "OBJ", (".obj",)),
    Format("ply", "PLY", (".ply",)),
    Format("off", "OFF", (".off",)),
    Format("glb", "glTF binair (GLB)", (".glb",)),
    Format("gltf", "glTF", (".gltf",)),
    Format("3mf", "3MF", (".3mf",)),
)
_SINGLE_MESH = {"stl", "ply", "off"}  # no scene graph: all objects are merged into one
_Y_UP = {"glb", "gltf"}


class Model3DConverter(Converter):
    family = "model3d"
    family_label = "3D-model"
    formats = _FORMATS
    Options = NoOptions

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if target in _SINGLE_MESH:
            out.append("Alle objecten worden samengevoegd tot één; materialen en texturen "
                       "gaan verloren.")
        if target == "obj":
            out.append("Texturen worden niet meegenomen (OBJ zou dan uit meerdere bestanden "
                       "bestaan).")
        if (source in _Y_UP) != (target in _Y_UP):
            out.append("Assen en eenheden worden niet omgerekend: glTF is Y-omhoog in meters, "
                       "STL en 3MF meestal Z-omhoog in millimeters.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        warnings = run_isolated(_convert_worker, str(ctx.input_path), str(ctx.output_path),
                                ctx.source.key, ctx.target.key,
                                timeout_s=ctx.timeout_s, cancel=ctx.cancel)
        for w in warnings:
            ctx.warn(w)


def _convert_worker(src: str, dst: str, src_key: str, dst_key: str) -> list[str]:
    """Runs in a child process (core.isolate). Raises ConversionError with a user message;
    returns warnings for the user."""
    import trimesh  # heavy import (scipy): only in the child

    warnings: list[str] = []
    try:
        loaded = trimesh.load(src, file_type=src_key)  # resolves .mtl/.bin next to the input
    except Exception as exc:  # trimesh raises many types for bad files
        raise ConversionError(f"3D-model kan niet worden gelezen: {exc}") from exc
    if isinstance(loaded, trimesh.Scene):
        empty = not loaded.geometry
        parts = len(loaded.geometry)
    else:
        empty = len(getattr(loaded, "vertices", ())) == 0
        parts = 1
    if empty:
        raise ConversionError("Het bestand bevat geen 3D-geometrie")
    try:
        if dst_key in _SINGLE_MESH:
            mesh = loaded.to_mesh() if isinstance(loaded, trimesh.Scene) else loaded
            if parts > 1:
                warnings.append(f"Alle {parts} objecten zijn samengevoegd tot één.")
            data = mesh.export(file_type=dst_key)  # OFF only exists per mesh, not per scene
        elif dst_key == "obj":
            data = loaded.export(file_type="obj", include_texture=False)  # one file (#16)
        elif dst_key == "gltf":
            scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
            files = trimesh.exchange.gltf.export_gltf(scene, embed_buffers=True)
            (data,) = files.values()  # embedded buffers: exactly one file
        else:  # glb, 3mf
            data = loaded.export(file_type=dst_key)
    except Exception as exc:  # e.g. a point cloud has no faces for STL
        raise ConversionError(f"Kan dit model niet als {dst_key.upper()} opslaan: {exc}") from exc
    Path(dst).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return warnings
