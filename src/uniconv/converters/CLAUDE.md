# Module: converters

**Responsibility:** one file per engine ("provider") that turns an input file into the
target format. Each provider declares its formats (shared ones from `formats.py`) and its
pydantic `Options`. It does NOT detect formats, choose output folders or touch any path
other than its job dir and `ctx.output_path`.
**Sprint:** image 1, data + document 3, media 4; 0.2 vector, office, browser, model3d and
the PDF routes - Status: Done

## Interface (providers in priority order, see `core/registry.py::default_providers()`)
| Family | Provider (file) | Options section | Engine | Runs |
|---|---|---|---|---|
| image | `ImageConverter` (`image.py`) | `image` | Pillow, img2pdf | in-process |
| image | `VectorConverter` (`vector.py`) | `image` (shared) | resvg, Typst, vtracer | binary, binary, child process |
| data | `DataConverter` (`data.py`) | `data` | pandas, json, PyYAML, tomllib/tomli-w, xmltodict | in-process |
| data | `OfficeSheetConverter` (`office.py`) | `office` | LibreOffice (detected) | user app |
| document | `OfficeDocumentConverter` (`office.py`) | `office` | LibreOffice (detected) | user app |
| document | `BrowserPdfConverter` (`browser.py`) | `browser` | Chrome/Edge (detected) | user app |
| document | `DocumentConverter` (`document.py`) | `document` | Pandoc + Typst | binaries |
| media | `MediaConverter` (`media.py`) | `media` | ffmpeg/ffprobe | binaries |
| model3d | `Model3DConverter` (`model3d.py`) | `model3d` (`NoOptions`) | trimesh | child process |

`formats.py` holds every `Format` used by more than one provider (rasters, SVG, PDF,
spreadsheets, documents, presentations). Adding an engine: a new file plus one line in
`default_providers()`. Plans: `docs/implementation-plan.md` (v1),
`docs/extension-plan-0.2.md` (0.2, steps 9, 12-14, 16, 18).

## Key design choices and pitfalls
- **Image:** HEIC source-only, PDF target-only. `encode_raster()` is the shared save path:
  `_normalize_mode()` per target (alpha onto `flatten_background` for JPG/BMP, 16-bit grey
  scaled to 8 bit, CMYK to RGB, v1 #4); the ICC profile is kept only if the colour space did
  not change, and popped from `img.info` because Pillow writers fall back to it. Size is
  checked from the header (v1 #9). Raster targets: first frame + warning. PDF via img2pdf:
  JPEG embedded byte for byte, everything else as a lossless PNG per frame (multi-page),
  alpha kept; palette frames become RGB/RGBA first (0.2 #1, #18).
- **Vector:** SVG size read from the root tag before rendering; refused above
  `max_megapixels` after scaling (resvg aborts on huge canvases, 0.2 #2). Small SVGs are
  scaled up to `svg_min_px`. On Windows/macOS resvg falls back to an installed font
  silently; its "No match for ... font-family" warning (0.2 #9) only appears on font-less
  systems. SVG -> PDF via Typst `#image("in.svg")` on an auto-sized page; .svgz is unzipped
  first; linked images Typst cannot read -> raster PDF (resvg 2x + img2pdf) with a warning
  (#26); only generic fonts -> warning (#10). Tracing: downscale to `trace_max_megapixels`
  (a 4 MP photo took 111 s in the plan's tests), vtracer via `run_isolated` (#3).
- **Data:** tables (CSV, XLSX) vs trees (JSON, YAML, TOML, XML). Tree to table unwraps
  single-key objects until a list (v1 #8). Text with `encoding: "auto"` = UTF-8-sig, then
  cp1252 + warning (v1 #5); CSV written with BOM. CSV is read as text, `_infer_types` makes
  columns numeric only when no value has a leading zero; delimiter sniffed over `,;\t|`.
  XML output: keys sanitised (warning), booleans as "true"/"false", lists wrapped in `root`.
- **Document:** input goes after `--`; EPUB default title via `--metadata-file`;
  `--embed-resources` implies `--standalone` (v1 #11). PDF = Pandoc
  `-s -t typst --extract-media=media` with `cwd=jobdir`, then `typst compile --root jobdir`
  (Pandoc's own `-t pdf` writes absolute temp image paths Typst cannot read, 0.2 #25); the
  input path is `resolve()`d because cwd changes; missing images -> warning. Loss hints for
  DOCX/ODT/RTF/HTML -> PDF name LibreOffice / Chrome (#11, #12).
- **Office (LibreOffice):** input copied to `input<ext>` (#14); own profile in a SHORT temp
  dir `uniconv-lo-*`, removed in `finally` (inside the job dir it broke Windows' 260-char
  path limit: no PDF and no error); success = `lo-out/input.pdf` exists (#4). CI audit: on
  both OSes a failure exits NON-zero with "Error: source file could not be loaded" on
  stderr (the plan assumed exit 0); both paths give the same Dutch message (#13).
  `soffice.com` waits for the PDF; a 10 s poll remains as a harmless fallback. Time-out
  message tells macOS users to open LibreOffice once (#17).
- **Browser:** `--headless --print-to-pdf --no-pdf-header-footer`, own `--user-data-dir` in
  the job dir, page `--timeout`, process limit = page timeout + 60 s (#15).
- **Media:** x264 + scale to even dimensions (v1 #2), `-sn -dn` (v1 #6), VP9 speed flags
  (v1 #12), audio sources only to audio targets; one ffprobe call gives duration and stream
  types (album art is not video); progress from `-progress pipe:1`.
- **3D:** trimesh in `run_isolated`; STL/PLY/OFF merge the scene (the worker returns a
  warning), OBJ without textures (one file), glTF with embedded buffers (one file), an
  axes/units hint between glTF and the rest (#16); empty meshes get a clear error.

## Dependencies
- **Depends on:** `uniconv.core` (converter, errors, tools, isolate, apps).
- **Consumed by:** `uniconv.core.registry.default_providers()`.

## Known issues / deliberate shortcuts
- One default quality per target; per-conversion options would come from
  `Options.model_json_schema()`.
- No PDF as source, no OCR, no FBX/CAD, no cross-family conversions.
