# Module: converters

**Responsibility:** one file per family that turns an input file into the target format
using a proven engine. Each converter declares its own formats (with MIME types) and its
own pydantic `Options`. It does NOT detect formats, choose output folders or touch any
path other than `ctx.output_path`.
**Sprint:** image 1, data + document 3, media 4 - Status: In progress (image)

## Interface
Each module exposes one `Converter` subclass plus its options model:

| File | Class | Options | Engine | Plan step |
|------|-------|---------|--------|-----------|
| `image.py` | `ImageConverter` (`image`, "Afbeelding") | `ImageOptions` | Pillow + pillow-heif | 12 |
| `data.py` | `DataConverter` (`data`, "Data") | `DataOptions` | pandas, json, PyYAML, tomllib/tomli-w, xmltodict | 23 |
| `document.py` | `DocumentConverter` (`document`, "Document") | `DocumentOptions` | Pandoc via `core.tools` | 24 |
| `media.py` | `MediaConverter` (`media`, "Audio/video") | `MediaOptions` | ffmpeg/ffprobe via `core.tools` | 26 |

Adding a family: new file here + one line in `build_default_registry()`. Nothing else.

## Key design choices
- **Image:** HEIC is source-only, PDF is target-only. `ImageOps.exif_transpose` bakes in
  camera rotation. `_normalize_mode()` converts to a mode the target writer accepts
  (`_TARGET_MODES`): alpha onto `flatten_background` for JPG/BMP/PDF, 16-bit grey scaled
  to 8 bit, CMYK to RGB (review #4). Keep the ICC profile only if the colour space did not
  change. Reject images above `max_megapixels` before loading pixels (review #9). Animated
  or multi-page input: first frame + `ctx.warn`.
- **Data (Sprint 3):** two shapes, tables (CSV, XLSX) and trees (JSON, YAML, TOML, XML).
  Tree to table unwraps single-key objects until a list is found (review #8). Text read
  with `encoding: "auto"` = UTF-8-sig, fallback cp1252 + warning (review #5). CSV written
  as UTF-8 with BOM for Excel.
- **Document (Sprint 3):** `--embed-resources` always together with `--standalone`
  (review #11). No PDF output (needs LaTeX). `txt` is target-only.
- **Media (Sprint 4):** x264 with `yuv420p` plus scale filter to even dimensions
  (review #2); `-sn -dn` drops subtitle/data streams (review #6); VP9 with
  `-deadline good -cpu-used 4 -row-mt 1` (review #12); audio sources only to audio targets;
  progress from `-progress pipe:1` `out_time_us` divided by ffprobe duration.
- `available()` returns False when the tool is missing, so the family disappears.

## Dependencies
- **Depends on:** `uniconv.core.converter`, `uniconv.core.errors`, `uniconv.core.tools`
  (document, media).
- **Consumed by:** `uniconv.core.registry.build_default_registry()`.

## Current state
Nothing implemented yet. Sprint 1: `image.py` only. `data.py`, `document.py` and
`media.py` follow in Sprints 3 and 4 exactly as specified in the plan.

## Known issues / deliberate shortcuts
- One default quality per target; per-conversion options come later via
  `Options.model_json_schema()`.
- No HEIC output, no PDF input, no cross-family conversions (out of scope for v1).
