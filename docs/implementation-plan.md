# Implementatieplan: UniConv v1

Oct 30, 2026 · @Sander Nales

## Anker

**Wat v1 oplevert:** UniConv, een installeerbare desktop-app voor Windows en Apple Silicon-Macs die één bestand tegelijk converteert binnen één familie (afbeelding, data, document, audio/video), met een zelfgekozen outputmap en een JSON-config voor alle kwaliteitsinstellingen.

**Kernbeslissing:** alle logica zit in een UI-onafhankelijke core. Elke converter *bezit* zijn eigen formaten en opties, dus een nieuwe familie is één bestand plus één regel in de registry. De UI en de CLI bouwen alleen een `Job` en kennen zelf geen formaten.

**Buiten scope voor v1:** batch in de UI, opties per conversie in de UI, PDF-output van documenten, PDF→DOCX, OCR, tracing, conversies tussen families, code-signing, auto-update, portable-modus en een Intel-Mac-build.

**Vaste keuzes**

| Onderwerp | Keuze |
| --- | --- |
| Naam | UniConv (Python-package `uniconv`, CLI `uniconv`) |
| Repo | `github.com/Forgeline-Optimizations/uniconv` |
| Bundle-ID (macOS) | `io.github.forgeline-optimizations.uniconv` |
| Python | 3.12 |
| UI | PySide6 (Qt 6) |
| Engines | Pillow + pillow-heif, pandas + stdlib, Pandoc 3.x, ffmpeg + ffprobe |
| Detectie | `filetype` (magic bytes), extensie als fallback |
| Config | JSON-overrides, gevalideerd met pydantic v2 |
| Packaging | PyInstaller onedir, Inno Setup (Windows), DMG (macOS arm64) |
| CI/CD | GitHub Actions: tests op elke push, release op tag `v*` |
| Licentie | GPL-3.0, omdat Pandoc GPL is en ffmpeg met x264 ook |

**Aanname:** GitHub-organisatienamen kunnen geen spaties bevatten, dus ik ga uit van de slug `Forgeline-Optimizations`. Klopt die niet, dan pas je hem aan in stap 1, 28 en 29.

**Geschrapt om het in één nacht te halen:** de portable-modus, de Intel-Mac-build, de Windows-portable-zip, een los stylesheet-bestand en een meegeleverd default-JSON-bestand (dat genereert de app nu zelf uit de code). Vier core-modules zijn samengevoegd tot twee. Het plan telt nu 37 stappen in plaats van 43.

```text
   PySide6 UI        CLI            Outputmap
        \            /                  ^
         v          v                   | finalize na succes
Config --> [ JobRunner ] --werkmap--> Workspace
                 |
                 v vindt converter
             Registry
        /     |      |      \
   Afbeelding Data Document Audio/video
   Pillow    pandas Pandoc  ffmpeg
```

De UI en de CLI bouwen alleen een `Job`; de JobRunner kiest via de registry een converter, die in de werkmap schrijft. Pas na succes verplaatst `Workspace.finalize()` het resultaat naar de outputmap.

## Review: wat kan er misgaan

Het eerste plan bevatte zes fouten die v1 in de praktijk zouden breken, en een handvol die lelijke foutmeldingen geven. Alle fixes zitten nu in de stappen; de laatste kolom zegt waar.

**Kritiek: breekt v1 voor gewone gebruikers**

| # | Wat gaat er mis | Fix | Stap |
| --- | --- | --- | --- |
| 1 | Overschrijven faalt op Windows: `shutil.move` weigert als het doelbestand al bestaat | Verplaatsen naar een tijdelijke naam in de doelmap, dan `os.replace` (atomair, overschrijft ook op Windows) | 10 |
| 2 | Video met oneven breedte of hoogte (gedraaid of bijgesneden telefoonfilmpje): x264 met `yuv420p` weigert | Scale-filter naar even afmetingen | 26 |
| 3 | Gebruiker zet in de UI de outputmodus om, maar de runner gebruikt nog de oude config: bestand landt in de verkeerde map | De `Job` krijgt de outputmap expliciet mee; de runner leest `paths` nooit zelf | 11, 17 |
| 4 | CMYK-JPEG of 16-bit TIFF naar PNG/WebP/JPEG: Pillow kan die modus niet schrijven, of een CMYK-kleurprofiel komt op RGB-pixels | Modus normaliseren per doelformaat; ICC-profiel alleen houden bij gelijke kleurruimte | 12 |
| 5 | CSV uit Nederlandse Excel (Windows-1252 of met BOM): decodefout of een kolom `ï»¿id` | Encoding automatisch bepalen; CSV-output met BOM zodat Excel accenten goed toont | 23 |
| 6 | MKV met beeldondertitels naar MP4: ffmpeg faalt op de ondertitelcodec | Ondertitels weglaten (`-sn`) met een verlieshint | 26 |

**Lastig maar niet fataal**

| # | Wat gaat er mis | Fix | Stap |
| --- | --- | --- | --- |
| 7 | Outputmap niet beschrijfbaar of bestand open in Excel/Word: gebruiker ziet "Onverwachte fout" | `finalize` zet `OSError` om in een leesbare melding | 10 |
| 8 | XML naar CSV vindt geen lijst onder `{"root": {"row": [...]}}` | Afdalen door wrapper-objecten tot de eerste lijst | 23 |
| 9 | Zeer grote afbeelding: geheugenpiek of `DecompressionBombError` | Megapixellimiet in de afbeeldingsopties | 12 |
| 10 | Klikken tijdens een lopende conversie zet de UI-state door elkaar | Alle invoer uit zolang een job loopt | 17 |
| 11 | `embed_resources` zonder `standalone` geeft een Pandoc-fout | Embedden impliceert standalone | 24 |
| 12 | WebM (VP9) is met standaardinstellingen vaak trager dan realtime | `-deadline good -cpu-used 4 -row-mt 1` | 26 |
| 13 | Een update installeert naast de oude versie in plaats van eroverheen | Vaste `AppId` in Inno Setup | 29 |
| 14 | Een tweede app-instantie ruimt de werkmap van een lopende job op | Alleen restanten ouder dan 24 uur opruimen | 10 |
| 15 | Finder toont versie 0.0.0 | Versie meegeven aan `BUNDLE` | 28 |

**Buiten de code**

| # | Risico | Aanpak |
| --- | --- | --- |
| 16 | Er bestaat geen officiële statische GPL-ffmpeg voor macOS arm64; dit is het grootste risico van de nacht | Begin met stap 21. Lukt het niet, release dan zonder media: `available()` verbergt de familie automatisch |
| 17 | Ongesigneerde app: SmartScreen (Windows) en Gatekeeper (macOS) waarschuwen | Duidelijke stappen in de README (stap 33) |
| 18 | De macOS-UI wordt in CI alleen via de CLI getest | Laat de DMG vóór een publieke release door iemand op een Mac openen |

## Uitbreidbaarheid en modulariteit

De opzet is uitbreidbaar, maar in de eerste versie raakte een nieuwe familie vijf bestanden (enum, formatentabel, configmodel, default-JSON, registry). Nu bezit elke converter zijn formaten en zijn optiemodel, en is de prijs per uitbreiding:

| Uitbreiding | Wat je aanraakt |
| --- | --- |
| Nieuw formaat in een bestaande familie | Eén `Format(...)` in die converter, eventueel een `match`-tak |
| Nieuwe familie (bijv. ebooks, 3D) | Eén nieuw converterbestand plus één regel in `build_default_registry()` |
| Batch | Alleen de UI: de core verwerkt al lijsten |
| Opties per conversie in de UI | Formulier genereren uit `Options.model_json_schema()`, plus één `options`-veld op `Job` |
| Meerstaps-conversies (bijv. HEIC → PNG → iets anders) | `Registry.find()` vervangen door een kortste-pad-zoektocht; converters blijven gelijk |
| Andere frontend (web, Finder-actie) | Praat met `JobRunner`, net als UI en CLI |

De grenzen worden bewaakt: de core importeert nooit Qt (test in stap 35), externe tools lopen alleen via `core/tools.py`, en alleen `Workspace.finalize()` schrijft naar de map van de gebruiker.

## Bouwvolgorde voor één nacht

Elke fase eindigt in een werkende, geteste staat, dus je kunt na elke fase stoppen en toch iets bruikbaars hebben. De tijden zijn richtwaarden bij bouwen met Claude Code.

1. **Start de Audit van stap 21 als eerste** (ffmpeg- en Pandoc-bronnen kiezen en hashes pinnen, ongeveer 45 min). Dit blokkeert fase 3, 4 en 5; zo weet je vroeg of media erin kan.
2. Fase 0, scaffolding (ongeveer 30 min).
3. Fase 1, core, afbeeldingen en CLI (ongeveer 2 uur). Daarna werkt `uniconv convert foto.heic --to png`.
4. Fase 2, UI (ongeveer 1,5 uur). Daarna is er een bruikbare app voor afbeeldingen.
5. Fase 3, data en documenten (ongeveer 1,5 uur).
6. Fase 4, audio en video (ongeveer 1 uur).
7. Fase 5, release (ongeveer 1,5 uur, vooral wachten op CI-runs).

**Snijlijn:** loopt de nacht uit, tag dan na fase 3 een release zonder media. Er hoeft niets aan de code te veranderen.

## Repostructuur en conventies

```text
uniconv/
├── pyproject.toml
├── LICENSE                      # GPL-3.0
├── README.md
├── THIRD_PARTY_LICENSES.md
├── .gitignore
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── scripts/fetch_binaries.py
├── vendor/                      # generated, git-ignored
├── packaging/
│   ├── uniconv.spec
│   ├── windows/installer.iss, icon.ico
│   └── macos/build_dmg.sh, icon.icns
├── src/uniconv/
│   ├── __init__.py
│   ├── __main__.py              # GUI without args, CLI with
│   ├── cli.py
│   ├── config.py
│   ├── paths.py
│   ├── core/
│   │   ├── errors.py
│   │   ├── converter.py         # Format, ConversionContext, CancelToken, Converter
│   │   ├── registry.py          # registry + detection
│   │   ├── workspace.py
│   │   ├── jobs.py
│   │   └── tools.py             # find and run pandoc/ffmpeg
│   ├── converters/
│   │   ├── image.py
│   │   ├── data.py
│   │   ├── document.py
│   │   └── media.py
│   └── ui/
│       ├── app.py
│       ├── main_window.py
│       ├── drop_zone.py
│       └── worker.py
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── ui/
```

- `src/`-layout, zodat tests tegen het geïnstalleerde package draaien.
- Code en comments in het Engels (publieke repo); UI- en foutteksten in het Nederlands via `self.tr()`, zodat vertalen later kan.
- Eén converter per familie. Formaatsleutels zijn uniek over alle families; de registry weigert dubbele sleutels bij het opstarten.
- Externe tools alleen via `core/tools.py`: argumentenlijst, nooit `shell=True`, altijd een timeout.

## Fase 0: scaffolding

Na deze fase installeert `pip install -e ".[dev]"` het package, laadt de config met validatie en draait CI groen op Windows en macOS. Er is nog geen conversie.

### Stap 1 — Create `pyproject.toml`

**Why:** één plek voor dependencies, entry point en tool-instellingen, zodat CI, ontwikkelaars en PyInstaller exact dezelfde omgeving bouwen.

**What changes:** hatchling als build-backend, runtime-dependencies, `dev`- en `build`-extra's, en ruff/pytest-config. Ruff-regelset `S` (bandit) vangt `shell=True` af.

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "uniconv"
version = "0.1.0"
requires-python = ">=3.12"
license = "GPL-3.0-or-later"
dependencies = [
  "PySide6>=6.7",
  "Pillow>=10.4",
  "pillow-heif>=0.18",
  "pandas>=2.2",
  "openpyxl>=3.1",
  "PyYAML>=6.0",
  "tomli-w>=1.0",
  "xmltodict>=0.13",
  "filetype>=1.2",
  "platformdirs>=4.2",
  "pydantic>=2.7",
]

[project.urls]
Homepage = "https://github.com/Forgeline-Optimizations/uniconv"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt>=4.4", "ruff>=0.6"]
build = ["pyinstaller>=6.6"]

[project.scripts]
uniconv = "uniconv.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/uniconv"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S"]
ignore = ["S101"]  # assert is fine in tests

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "needs_pandoc: skipped when the pandoc binary is missing",
  "needs_ffmpeg: skipped when the ffmpeg binary is missing",
]
```

### Stap 2 — Create `.gitignore`, `LICENSE`, `README.md`

**Why:** de repo moet vanaf de eerste commit publiek kunnen, met de juiste licentie en zonder build-artefacten.

**What changes:** mechanisch. `LICENSE` = de volledige GPL-3.0-tekst. `.gitignore` = de standaard Python-template plus `vendor/`, `build/`, `dist/` en `.venv/`. `README.md` krijgt een titel, één zin over het doel en de dev-install; stap 33 vult hem aan.

### Stap 3 — Create `src/uniconv/__init__.py` en `src/uniconv/__main__.py`

**Why:** `__main__.py` is het enige entry point voor `python -m uniconv`, het console-script en de PyInstaller-build. Hier bestaat alleen `--version`; stap 14 koppelt de CLI eraan en stap 19 de GUI.

```python
# src/uniconv/__init__.py
__version__ = "0.1.0"
APP_NAME = "UniConv"
```

```python
# src/uniconv/__main__.py
import sys

from uniconv import __version__


def main(argv: list[str] | None = None) -> int:
    """Entry point. Step 14 adds the CLI branch, step 19 the GUI branch."""
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--version"]:
        print(__version__)
        return 0
    print("uniconv: nothing to do yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

### Stap 4 — Create `src/uniconv/config.py`

**Why:** de app-instellingen (paden, gedrag, limieten) hebben hun defaults in de code, en elke familie heeft zijn eigen optiemodel in zijn converter (stap 8). Het gebruikersbestand `config.json` bevat alleen *afwijkingen*. Zo bestaat er geen tweede defaults-bestand dat uit de pas kan lopen, en komen nieuwe defaults in een update automatisch door.

**What changes:** pydantic-modellen, `load_config()`, `save_user_overrides()`, `deep_merge()` en `write_reference_copy()`. Een ongeldig gebruikersbestand wordt hernoemd naar `config.invalid.json` en de app start met defaults. `defaults` is hier een ruwe dict per familie; de registry valideert die tegen het optiemodel van de converter (stap 9).

```python
class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_dir: Path | None = None
    output_dir: Path | None = None
    output_mode: Literal["fixed", "beside_source"] = "fixed"


class BehaviorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overwrite: Literal["rename", "overwrite", "skip"] = "rename"
    cleanup_work_dir_on_start: bool = True
    open_folder_after_convert: bool = False


class LimitsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeout_seconds: int = Field(900, ge=10)
    max_input_mb: int = Field(4096, ge=1)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    paths: PathsConfig = PathsConfig()
    behavior: BehaviorConfig = BehaviorConfig()
    limits: LimitsConfig = LimitsConfig()
    defaults: dict[str, dict[str, Any]] = {}  # per family; validated by that converter's Options


def load_config(config_file: Path) -> AppConfig:
    """Code defaults + the user's overrides. Never raises on bad user input."""
    if config_file.exists():
        try:
            return AppConfig.model_validate_json(config_file.read_text(encoding="utf-8"))
        except ValidationError as exc:  # pydantic also wraps JSON syntax errors here
            log.warning("Invalid config %s, using defaults: %s", config_file, exc)
            config_file.replace(config_file.with_name("config.invalid.json"))
    return AppConfig()


def save_user_overrides(config_file: Path, changes: dict) -> AppConfig:
    """Merge `changes` into the user file, validate, then write atomically."""
    current = json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    merged = deep_merge(current, changes)
    cfg = AppConfig.model_validate(merged)  # raise before anything is written
    config_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, indent=2, default=str), encoding="utf-8")
    tmp.replace(config_file)
    return cfg


def write_reference_copy(config_dir: Path, family_defaults: dict[str, dict]) -> None:
    """Write config.defaults.json: every key with its default, so users know what to override."""
    ref = AppConfig().model_dump(mode="json") | {"defaults": family_defaults}
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defaults.json").write_text(json.dumps(ref, indent=2), encoding="utf-8")
```

Zo ziet het gegenereerde `config.defaults.json` eruit na fase 4. Een gebruiker kopieert alleen de regels die hij wil wijzigen naar `config.json`.

```json
{
  "version": 1,
  "paths": { "work_dir": null, "output_dir": null, "output_mode": "fixed" },
  "behavior": { "overwrite": "rename", "cleanup_work_dir_on_start": true, "open_folder_after_convert": false },
  "limits": { "timeout_seconds": 900, "max_input_mb": 4096 },
  "defaults": {
    "image": { "jpeg_quality": 90, "png_compress_level": 6, "webp_quality": 85, "pdf_dpi": 150,
               "flatten_background": "#FFFFFF", "max_megapixels": 150 },
    "data": { "encoding": "auto", "csv_delimiter": ",", "indent": 2 },
    "document": { "standalone": true, "embed_resources": true },
    "media": { "audio_bitrate": "192k", "video_crf": 23, "video_preset": "veryfast", "webm_crf": 32 }
  }
}
```

### Stap 5 — Create `src/uniconv/paths.py`

**Why:** de installatiemap is op beide OS'en meestal niet beschrijfbaar (`Program Files`, `/Applications`). Config en werkmap staan daarom in de per-gebruiker-mappen. Alle padlogica zit hier, zodat geen andere module zelf paden verzint.

```python
def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]  # repo root in development


def config_file() -> Path:
    # Windows: %LOCALAPPDATA%\UniConv  ·  macOS: ~/Library/Application Support/UniConv
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False)) / "config.json"


def resolve_work_dir(cfg: AppConfig) -> Path:
    return cfg.paths.work_dir or Path(platformdirs.user_cache_dir(APP_NAME, appauthor=False)) / "work"


def default_output_dir(cfg: AppConfig) -> Path:
    return cfg.paths.output_dir or Path(platformdirs.user_downloads_dir()) / "Converted"
```

### Stap 6 — Create `.github/workflows/ci.yml`

**Why:** padgedrag, bestandslocks en subprocess-gedrag verschillen tussen Windows en macOS (zie review #1). Die verschillen moeten bij elke push zichtbaar worden.

```yaml
name: ci
on: [push, pull_request]

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e ".[dev]"
      # step 22 adds: cache vendor/ + python scripts/fetch_binaries.py
      - run: ruff check .
      - run: pytest -q
        env:
          QT_QPA_PLATFORM: offscreen  # pytest-qt without a display
```

## Fase 1: core en afbeeldingen

Na deze fase converteert `uniconv convert foto.heic --to png --out ~/Downloads` een bestand van begin tot eind: detectie, conversie in de werkmap, atomair verplaatsen naar de outputmap. Volgorde: contracten, registry, werkmap, runner, eerste converter, CLI.

### Stap 7 — Create `src/uniconv/core/errors.py`

**Why:** de UI moet fouten tonen zonder stacktraces te parsen. Elke verwachte fout heeft een eigen type, en `str(exc)` is altijd een tekst voor de gebruiker.

```python
class UniconvError(Exception):
    """Base class. str(exc) is always a user-facing message."""

class UnsupportedFormatError(UniconvError): ...      # format not known at all
class WrongFamilyError(UniconvError): ...            # e.g. an MP3 dropped while "image" is selected
class UnsupportedConversionError(UniconvError): ...  # pair not offered
class ConversionError(UniconvError): ...             # engine failed, content can't be mapped, can't write
class ToolMissingError(UniconvError): ...            # pandoc/ffmpeg not found
class ConversionCancelled(UniconvError): ...
class InputTooLargeError(UniconvError): ...
```

### Stap 8 — Create `src/uniconv/core/converter.py`

**Why:** dit is het contract voor elke familie, en het is de reden dat het systeem uitbreidbaar is. Een converter declareert zelf zijn familie, zijn formaten (inclusief de MIME-types voor detectie) en zijn optiemodel. Niemand anders hoeft die te kennen.

**What changes:** `Format`, `CancelToken`, `ConversionContext` en de abstracte `Converter`. `sources()` en `targets()` hebben een default op basis van `formats`, dus de meeste converters implementeren alleen `convert()`.

```python
@dataclass(frozen=True)
class Format:
    key: str                      # unique across ALL families: "jpg"
    label: str                    # UI text: "JPEG"
    extensions: tuple[str, ...]   # first one is used for output: (".jpg", ".jpeg")
    mimes: tuple[str, ...] = ()   # what filetype.guess() reports; empty = text format, extension only
    source: bool = True           # may be converted FROM
    target: bool = True           # may be converted TO


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ConversionCancelled("Conversie geannuleerd")


@dataclass
class ConversionContext:
    input_path: Path
    output_path: Path             # always inside the job's work dir
    source: Format
    target: Format
    options: BaseModel            # an instance of the converter's Options
    timeout_s: int
    cancel: CancelToken
    on_progress: Callable[[float], None] = lambda _: None  # 0.0..1.0
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


class Converter(ABC):
    family: ClassVar[str]                   # "image"
    family_label: ClassVar[str]             # "Afbeelding"
    formats: ClassVar[tuple[Format, ...]]
    Options: ClassVar[type[BaseModel]]      # its section under "defaults" in config.json

    def available(self) -> bool:
        """False when a required external tool is missing; the family is then hidden."""
        return True

    def sources(self) -> list[str]:
        return [f.key for f in self.formats if f.source]

    def targets(self, source: str) -> list[str]:
        return [f.key for f in self.formats if f.target and f.key != source]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return []

    @abstractmethod
    def convert(self, ctx: ConversionContext) -> None:
        """Write ctx.output_path or raise a UniconvError. Never touch other paths."""
```

### Stap 9 — Create `src/uniconv/core/registry.py`

**Why:** de registry is het enige wat de runner en de UI over converters weten. Hij doet ook de detectie, omdat de formaattabel uit de geregistreerde converters komt; zo bestaat er geen losse lijst met MIME-types die uit de pas kan lopen.

**What changes:** `Registry` en `build_default_registry()`. Detectie: eerst magic bytes via `filetype`, dan de extensie, en dan de familiecontrole. Optie-validatie gebeurt hier per familie, met een melding die naar de precieze config-sleutel wijst.

```python
class Registry:
    def __init__(self) -> None:
        self._convs: dict[str, Converter] = {}            # insertion order = UI order
        self._formats: dict[str, tuple[Format, Converter]] = {}

    def register(self, conv: Converter) -> None:
        for f in conv.formats:
            if f.key in self._formats:  # programming error: fail loudly at start-up and in tests
                raise ValueError(f"format key {f.key!r} registered twice")
            self._formats[f.key] = (f, conv)
        self._convs[conv.family] = conv

    def families(self) -> list[tuple[str, str]]:
        return [(c.family, c.family_label) for c in self._convs.values()]

    def format(self, key: str) -> Format:
        return self._formats[key][0]

    def extensions(self, family: str) -> list[str]:
        return [e for f in self._convs[family].formats if f.source for e in f.extensions]

    def targets(self, family: str, source: str) -> list[str]:
        return self._convs[family].targets(source)

    def find(self, family: str, source: str, target: str) -> Converter:
        conv = self._convs.get(family)
        if conv is None or target not in conv.targets(source):
            raise UnsupportedConversionError(f"{source.upper()} naar {target.upper()} wordt niet ondersteund")
        return conv

    def detect(self, path: Path, family: str) -> Format:
        kind = filetype.guess(path)
        hit = next((v for v in self._formats.values() if kind and kind.mime in v[0].mimes), None)
        if hit is None:  # text formats, or a ZIP container filetype reports as plain zip
            ext = path.suffix.lower()
            hit = next((v for v in self._formats.values() if ext in v[0].extensions), None)
        if hit is None:
            raise UnsupportedFormatError(f"Onbekend bestandstype: {path.name}")
        fmt, conv = hit
        if conv.family != family:
            raise WrongFamilyError(f"{path.name} is een {fmt.label}-bestand. Kies '{conv.family_label}'.")
        if not fmt.source:
            raise UnsupportedConversionError(f"{fmt.label} kan in deze versie alleen als doel")
        return fmt

    def options_for(self, family: str, cfg: AppConfig) -> BaseModel:
        try:
            return self._convs[family].Options.model_validate(cfg.defaults.get(family, {}))
        except ValidationError as exc:
            loc = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise ConversionError(f"Ongeldige instelling defaults.{family}.{loc} in config.json") from exc

    def default_options(self) -> dict[str, dict]:
        return {fam: c.Options().model_dump(mode="json") for fam, c in self._convs.items()}


def build_default_registry() -> Registry:
    reg = Registry()
    for conv in (ImageConverter(),):  # step 25: DataConverter(), DocumentConverter(); step 27: MediaConverter()
        if conv.available():
            reg.register(conv)
    return reg
```

**Audit:** controleer bij het implementeren welke MIME-string `filetype` echt teruggeeft voor elk formaat (bijv. M4A, MKV, WebM, DOCX) en zet die in de `mimes` van het `Format`. De matrixtests (stap 36) vangen fouten.

### Stap 10 — Create `src/uniconv/core/workspace.py`

**Why:** dit is de vaste plek voor tijdelijke bestanden. Converters schrijven alleen hierheen; pas na succes verhuist het resultaat naar de map van de gebruiker. Zo blijft er bij een crash of annulering nooit een half bestand achter. Review #1, #7 en #14 worden hier opgelost.

**What changes:** een submap per job, opruimen van restanten ouder dan 24 uur, en `finalize()` die eerst naar een verborgen tijdelijke naam in de doelmap verplaatst en dan met `os.replace` de echte naam geeft. `os.replace` overschrijft op Windows wél, en is atomair binnen één volume.

```python
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
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)

    def finalize(self, tmp: Path, dest_dir: Path, stem: str, ext: str, policy: str) -> Path | None:
        """Move tmp to dest_dir/stem+ext. None when policy is 'skip' and the file exists."""
        dest = dest_dir / f"{stem}{ext}"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                if policy == "skip":
                    return None
                if policy == "rename":
                    dest = _unique(dest)  # "foto (1).png", "foto (2).png", ...
            staged = dest_dir / f".{dest.name}.uniconv-partial"
            shutil.move(tmp, staged)   # may copy across volumes: never under the final name
            os.replace(staged, dest)   # atomic, overwrites on Windows too
            return dest
        except PermissionError as exc:
            raise ConversionError(f"Kan {dest.name} niet opslaan: geen schrijfrechten of het bestand is geopend in een ander programma") from exc
        except OSError as exc:
            raise ConversionError(f"Kan niet opslaan in {dest_dir}: {exc.strerror}") from exc
```

Bij een fout na `shutil.move` blijft het `.uniconv-partial`-bestand mogelijk staan; `finalize` verwijdert het in een `finally` als het nog bestaat.

### Stap 11 — Create `src/uniconv/core/jobs.py`

**Why:** de runner is de enige plek die detectie, opties, werkmap en converter aan elkaar knoopt. UI en CLI roepen alleen `JobRunner.run()` aan. De outputmap zit nu in de `Job` zelf (review #3): de aanroeper bepaalt hem uit de actuele instellingen, de runner leest `cfg.paths` nooit.

```python
@dataclass
class Job:
    family: str
    target: str
    inputs: list[Path]          # v1 UI: always length 1
    output_dir: Path | None     # None = next to each input. Resolved by the caller.
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ItemResult:
    input: Path
    status: Literal["done", "skipped", "failed", "cancelled"]
    output: Path | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class JobRunner:
    def __init__(self, registry: Registry, workspace: Workspace, cfg: AppConfig) -> None:
        self.registry, self.workspace, self.cfg = registry, workspace, cfg

    def update_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg  # called by the UI after saving settings; never during a running job

    def run(self, job: Job, cancel: CancelToken,
            on_progress: Callable[[int, float], None] = lambda i, p: None) -> list[ItemResult]:
        results = []
        for i, src in enumerate(job.inputs):  # one failed item never stops the others
            if cancel.cancelled:
                results.append(ItemResult(src, "cancelled"))
            else:
                results.append(self._run_one(job, i, src, cancel, on_progress))
        return results

    def _run_one(self, job, i, src, cancel, on_progress) -> ItemResult:
        name = f"{job.id}-{i}"
        work = self.workspace.job_dir(name)
        try:
            if src.stat().st_size > self.cfg.limits.max_input_mb * 1024 * 1024:
                raise InputTooLargeError(f"{src.name} is groter dan {self.cfg.limits.max_input_mb} MB")
            source = self.registry.detect(src, job.family)
            target = self.registry.format(job.target)
            conv = self.registry.find(job.family, source.key, target.key)
            ctx = ConversionContext(
                input_path=src, output_path=work / f"out{target.extensions[0]}",
                source=source, target=target,
                options=self.registry.options_for(job.family, self.cfg),
                timeout_s=self.cfg.limits.timeout_seconds, cancel=cancel,
                on_progress=lambda p: on_progress(i, p),
            )
            conv.convert(ctx)
            cancel.raise_if_cancelled()
            out = self.workspace.finalize(ctx.output_path, job.output_dir or src.parent,
                                          src.stem, target.extensions[0], self.cfg.behavior.overwrite)
            on_progress(i, 1.0)
            return ItemResult(src, "skipped" if out is None else "done", out, warnings=ctx.warnings)
        except ConversionCancelled:
            return ItemResult(src, "cancelled")
        except UniconvError as exc:
            return ItemResult(src, "failed", error=str(exc))
        except Exception as exc:  # engine bug: log the traceback, show a short message
            log.exception("Unexpected failure converting %s", src)
            return ItemResult(src, "failed", error=f"Onverwachte fout: {exc}")
        finally:
            self.workspace.discard(name)
```

### Stap 12 — Create `src/uniconv/converters/image.py`

**Why:** de eerste echte converter en het bewijs dat het contract klopt. Afbeeldingen hebben veel kleine valkuilen: transparantie, EXIF-rotatie, animaties, CMYK, 16-bit en kleurprofielen (review #4 en #9).

**What changes:** `ImageOptions`, de formaattabel en `ImageConverter`. HEIC is alleen bron, PDF alleen doel. De kern is `_normalize_mode()`: die zet elke Pillow-modus om naar een modus die het doelformaat kan schrijven.

```python
register_heif_opener()


class ImageOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jpeg_quality: int = Field(90, ge=1, le=95)     # >95 only grows files in Pillow
    png_compress_level: int = Field(6, ge=0, le=9)
    webp_quality: int = Field(85, ge=1, le=100)
    pdf_dpi: int = Field(150, ge=72, le=600)
    flatten_background: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    max_megapixels: int = Field(150, ge=1)          # below Pillow's own ~178 MP hard limit


# Modes each writer accepts without surprises; anything else is converted first.
_TARGET_MODES = {
    "jpg": ("RGB", "L"), "bmp": ("RGB", "L", "1"), "pdf": ("RGB", "L"),
    "png": ("RGBA", "RGB", "LA", "L", "P", "1"), "webp": ("RGBA", "RGB"),
    "tiff": ("RGBA", "RGB", "L", "CMYK", "1"), "gif": ("P",),
}
_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF",
               "bmp": "BMP", "tiff": "TIFF", "pdf": "PDF"}


class ImageConverter(Converter):
    family, family_label, Options = "image", "Afbeelding", ImageOptions
    formats = (
        Format("jpg", "JPEG", (".jpg", ".jpeg"), ("image/jpeg",)),
        Format("png", "PNG", (".png",), ("image/png",)),
        Format("webp", "WebP", (".webp",), ("image/webp",)),
        Format("gif", "GIF", (".gif",), ("image/gif",)),
        Format("bmp", "BMP", (".bmp",), ("image/bmp",)),
        Format("tiff", "TIFF", (".tif", ".tiff"), ("image/tiff",)),
        Format("heic", "HEIC", (".heic", ".heif"), ("image/heic", "image/heif"), target=False),
        Format("pdf", "PDF", (".pdf",), ("application/pdf",), source=False),
    )

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if target in {"jpg", "bmp", "pdf"} and source in {"png", "webp", "gif", "tiff", "heic"}:
            out.append("Eventuele transparantie wordt een effen achtergrond.")
        if target == "gif":
            out.append("GIF heeft maximaal 256 kleuren.")
        if target == "jpg":
            out.append("JPEG is lossy: elke conversie kost wat kwaliteit.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options
        key = ctx.target.key
        try:
            with Image.open(ctx.input_path) as im:  # lazy: size is known before pixels load
                if im.width * im.height > opts.max_megapixels * 1_000_000:
                    raise ConversionError(f"Afbeelding is groter dan {opts.max_megapixels} megapixel "
                                          "(aan te passen in config.json)")
                if getattr(im, "n_frames", 1) > 1:
                    ctx.warn("Alleen het eerste frame of de eerste pagina is geconverteerd.")
                img = ImageOps.exif_transpose(im)  # returns a copy: safe after the with-block
                icc = im.info.get("icc_profile")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc
        ctx.cancel.raise_if_cancelled()

        before = _colour_space(img.mode)
        img = _normalize_mode(img, key, opts.flatten_background)
        if _colour_space(img.mode) != before:
            icc = None  # NOTE: a CMYK profile attached to RGB pixels renders wrong colours

        params: dict = {}
        if icc and key in {"jpg", "png", "webp", "tiff"}:
            params["icc_profile"] = icc  # keeps Display P3 iPhone photos looking right
        match key:
            case "jpg":
                params |= {"quality": opts.jpeg_quality, "optimize": True}
            case "png":
                params |= {"compress_level": opts.png_compress_level}
            case "webp":
                params |= {"quality": opts.webp_quality}
            case "tiff":
                params |= {"compression": "tiff_lzw"}
            case "pdf":
                params |= {"resolution": float(opts.pdf_dpi)}
        img.save(ctx.output_path, format=_PIL_FORMAT[key], **params)


def _colour_space(mode: str) -> str:
    return "CMYK" if mode == "CMYK" else "GREY" if mode in ("1", "L", "LA", "I", "I;16") else "RGB"


def _normalize_mode(img: Image.Image, key: str, background: str) -> Image.Image:
    allowed = _TARGET_MODES[key]
    if img.mode in allowed:
        return img
    if key == "gif":
        return img.convert("RGBA").quantize(colors=256)
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    if has_alpha and "RGBA" in allowed:
        return img.convert("RGBA")
    if has_alpha:  # target cannot store alpha: composite onto the configured colour
        rgba = img.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, background), rgba).convert("RGB")
    if img.mode in ("I", "I;16"):  # 16-bit grey: scale to 8 bit instead of clipping to white
        return img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    return img.convert("RGB")  # CMYK, YCbCr, P without alpha, ...
```

### Stap 13 — Create `src/uniconv/cli.py`

**Why:** een CLI maakt de core los van de UI testbaar en debugbaar, en is de snelste manier om een bugreport te reproduceren. Op Windows heeft de geïnstalleerde (windowed) app geen console, dus de CLI is vooral voor `python -m uniconv`; dat staat in de README.

**What changes:** `formats` toont per familie de bronnen en doelen. `convert` neemt bestanden, `--to`, en optioneel `--family` en `--out`. Zonder `--family` probeert de CLI elke familie tot `detect()` slaagt.

```python
def run_cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="uniconv")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("formats")
    c = sub.add_parser("convert")
    c.add_argument("inputs", nargs="+", type=Path)
    c.add_argument("--to", required=True)
    c.add_argument("--family")
    c.add_argument("--out", type=Path, help="default: next to each input")
    args = p.parse_args(argv)

    cfg = load_config(config_file())
    registry = build_default_registry()
    runner = JobRunner(registry, Workspace(resolve_work_dir(cfg)), cfg)
    # ... build Job(family, args.to, args.inputs, args.out), wire Ctrl+C to CancelToken.cancel,
    # print one line per ItemResult incl. warnings
    return 0 if all(r.status in ("done", "skipped") for r in results) else 1
```

### Stap 14 — Edit `src/uniconv/__main__.py`

**Why:** de CLI moet via het bestaande entry point bereikbaar zijn.

```python
# BEFORE
    if argv == ["--version"]:
        print(__version__)
        return 0
    print("uniconv: nothing to do yet", file=sys.stderr)
    return 2

# AFTER
    if argv:
        from uniconv.cli import run_cli  # lazy: the CLI never imports Qt
        return run_cli(argv)
    print("uniconv: GUI arrives in step 19, use a subcommand", file=sys.stderr)
    return 2
```

## Fase 2: UI

Na deze fase opent `uniconv` zonder argumenten een venster waarin je een familie kiest, één bestand sleept, een doelformaat kiest en converteert, terwijl de UI responsief blijft. Alle keuzes komen uit de registry; de UI kent zelf geen formaten.

**Schermindeling (van boven naar beneden)**

1. Familiekiezer: een toggle-knop per familie uit `registry.families()`. Een familie zonder tool (bijv. geen ffmpeg) bestaat dan simpelweg niet in de registry en dus ook niet in de UI.
2. Dropzone: "Sleep een bestand hierheen of klik om te kiezen". Na het droppen toont hij bestandsnaam en gedetecteerd formaat.
3. Doelformaat: dropdown, gevuld met `registry.targets(familie, bron)`.
4. Verlieshint: grijze tekst met `expected_losses()`, alleen zichtbaar als er iets is.
5. Outputmap: padveld (alleen-lezen), knop "Kies…" en vinkje "Naast het bronbestand".
6. Knop "Converteer" die tijdens het werk "Annuleer" wordt, een voortgangsbalk en een statusregel.
7. Na succes: "Open map", plus eventuele runtime-waarschuwingen.

### Stap 15 — Create `src/uniconv/ui/drop_zone.py`

**Why:** drag & drop en klikken-om-te-kiezen moeten hetzelfde signaal opleveren, zodat het hoofdvenster maar één codepad heeft. De stijl staat als constante in dit bestand; een los `.qss`-bestand zou alleen een extra data-bestand voor PyInstaller zijn.

```python
_STYLE = """
#DropZone { border: 2px dashed palette(mid); border-radius: 12px; min-height: 160px; }
#DropZone[dragActive="true"] { border-color: palette(highlight); background: palette(alternate-base); }
"""  # palette() colours follow light/dark mode on both OSes


class DropZone(QFrame):
    file_chosen = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setStyleSheet(_STYLE)
        self.setAcceptDrops(True)
        self._name_filter = "Alle bestanden (*)"
        # centred QLabel with the prompt; show_file(name, label) replaces its text

    def set_extensions(self, label: str, extensions: list[str]) -> None:
        self._name_filter = f"{label} ({' '.join('*' + e for e in extensions)})"

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls() and any(u.isLocalFile() for u in e.mimeData().urls()):
            self._set_active(True)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e: QDragLeaveEvent) -> None:
        self._set_active(False)

    def dropEvent(self, e: QDropEvent) -> None:
        self._set_active(False)
        files = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        files = [p for p in files if p.is_file()]  # folders are ignored in v1
        if files:
            self.file_chosen.emit(files[0])  # v1: first file only (batch later)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Kies een bestand"), "", self._name_filter)
        if path:
            self.file_chosen.emit(Path(path))

    def _set_active(self, on: bool) -> None:
        self.setProperty("dragActive", on)
        self.style().unpolish(self)  # re-apply the stylesheet for the property selector
        self.style().polish(self)
```

### Stap 16 — Create `src/uniconv/ui/worker.py`

**Why:** een video-conversie kan minuten duren. Op de UI-thread bevriest het venster en markeert Windows het als "reageert niet". De worker draait `JobRunner.run()` op een `QThread` en stuurt voortgang via signals terug.

```python
class JobWorker(QObject):
    progress = Signal(float)   # 0.0..1.0 for the current item
    finished = Signal(list)    # list[ItemResult]

    def __init__(self, runner: JobRunner, job: Job) -> None:
        super().__init__()
        self._runner, self._job = runner, job
        self.cancel_token = CancelToken()

    @Slot()
    def run(self) -> None:
        results = self._runner.run(self._job, self.cancel_token,
                                   on_progress=lambda _i, p: self.progress.emit(p))
        self.finished.emit(results)


def start_job(runner: JobRunner, job: Job, parent: QObject) -> tuple[QThread, JobWorker]:
    thread = QThread(parent)
    worker = JobWorker(runner, job)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker  # caller keeps references until finished
```

Annuleren zet alleen het `CancelToken`. Pillow controleert het tussen stappen, Pandoc en ffmpeg elke 100 ms via `core/tools.py`.

### Stap 17 — Create `src/uniconv/ui/main_window.py`

**Why:** het hoofdvenster is de enige plek met UI-state. Het vertaalt acties naar één `Job` en resultaten naar tekst. Twee review-fixes zitten hier: de outputmap gaat expliciet mee in de `Job` (#3), en alle invoer staat uit zolang er een job loopt (#10).

```python
class MainWindow(QMainWindow):
    def __init__(self, registry: Registry, runner: JobRunner, cfg: AppConfig) -> None:
        ...
        self._family = registry.families()[0][0]
        self._source: tuple[Path, Format] | None = None
        self._worker: JobWorker | None = None

    @Slot(Path)
    def _on_file_chosen(self, path: Path) -> None:
        try:
            fmt = self.registry.detect(path, self._family)
        except UniconvError as exc:
            self._show_status(str(exc), error=True)  # e.g. the WrongFamilyError text
            return
        self._source = (path, fmt)
        self.drop_zone.show_file(path.name, fmt.label)
        self.target_combo.clear()
        for key in self.registry.targets(self._family, fmt.key):
            self.target_combo.addItem(self.registry.format(key).label, key)
        self._update_loss_hint()
        self.convert_btn.setEnabled(self.target_combo.count() > 0)

    def _output_dir(self) -> Path | None:
        # Resolved here from the CURRENT settings, never inside the runner (review #3)
        if self.cfg.paths.output_mode == "beside_source":
            return None
        return default_output_dir(self.cfg)

    def _on_output_settings_changed(self, changes: dict) -> None:
        self.cfg = save_user_overrides(config_file(), {"paths": changes})
        self.runner.update_config(self.cfg)

    @Slot()
    def _on_convert_clicked(self) -> None:
        if self._worker is not None:          # the button doubles as Cancel
            self._worker.cancel_token.cancel()
            return
        path, _ = self._source
        job = Job(self._family, self.target_combo.currentData(), [path], self._output_dir())
        self._thread, self._worker = start_job(self.runner, job, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._set_busy(True)

    def _set_busy(self, busy: bool) -> None:
        for w in (*self.family_buttons, self.drop_zone, self.target_combo,
                  self.choose_dir_btn, self.beside_checkbox):
            w.setEnabled(not busy)
        self.convert_btn.setText(self.tr("Annuleer") if busy else self.tr("Converteer"))
        self.progress.setRange(0, 0 if busy else 100)  # indeterminate until a converter reports progress
        if busy:
            self.open_folder_btn.setVisible(False)

    @Slot(float)
    def _on_progress(self, p: float) -> None:
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(int(p * 100))

    @Slot(list)
    def _on_finished(self, results: list[ItemResult]) -> None:
        self._worker = None
        self._set_busy(False)
        r = results[0]
        match r.status:
            case "done":
                self.progress.setValue(100)
                self._last_output = r.output
                self._show_status(self.tr("Klaar: {0}").format(r.output.name))
                self.open_folder_btn.setVisible(True)
                if self.cfg.behavior.open_folder_after_convert:
                    self._open_folder()
            case "skipped":
                self._show_status(self.tr("Overgeslagen: bestand bestaat al"))
            case "cancelled":
                self._show_status(self.tr("Geannuleerd"))
            case "failed":
                self._show_status(r.error, error=True)
        self.warnings_label.setText("\n".join(r.warnings))

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output.parent)))

    def closeEvent(self, e: QCloseEvent) -> None:
        if self._worker is not None:  # don't leave an ffmpeg process orphaned
            self._worker.cancel_token.cancel()
            self._thread.wait(5000)
        super().closeEvent(e)
```

Bij het wisselen van familie worden bron, dropdown en hint gereset en krijgt de dropzone `registry.extensions(familie)`. Een menu "Help" bevat "Open configmap" en "Open logmap", zodat gebruikers `config.json` en het log vinden.

### Stap 18 — Create `src/uniconv/ui/app.py`

**Why:** één bootstrap die config laadt, logging instelt, de werkmap opruimt en de objecten koppelt. Logging naar een bestand is nodig omdat een windowed build op Windows geen console heeft. De familie-opties worden hier bij het starten al gevalideerd, zodat een typo in `config.json` meteen zichtbaar is en niet pas bij de eerste conversie.

```python
def run_gui() -> int:
    _setup_logging(Path(platformdirs.user_log_dir(APP_NAME, appauthor=False)) / "uniconv.log")
    cfg_path = config_file()
    cfg = load_config(cfg_path)
    registry = build_default_registry()
    write_reference_copy(cfg_path.parent, registry.default_options())

    workspace = Workspace(resolve_work_dir(cfg))
    if cfg.behavior.cleanup_work_dir_on_start:
        workspace.cleanup_stale()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Forgeline Optimizations")
    win = MainWindow(registry, JobRunner(registry, workspace, cfg), cfg)

    problems = []
    for family, _label in registry.families():
        try:
            registry.options_for(family, cfg)
        except ConversionError as exc:
            problems.append(str(exc))
    if problems:  # shown once; conversions of that family keep failing with the same message
        QMessageBox.warning(win, APP_NAME, "\n".join(problems))

    win.show()
    return app.exec()
```

`_setup_logging` gebruikt een `RotatingFileHandler` (1 MB, 3 backups).

### Stap 19 — Edit `src/uniconv/__main__.py`

**Why:** zonder argumenten moet de app het venster openen; dat doet een dubbelklik op de geïnstalleerde app. Finder start een `.app` soms met een argument `-psn_0_...`, dat moet eruit, anders opent de CLI in plaats van het venster.

```python
# BEFORE
    argv = sys.argv[1:] if argv is None else argv
    # ...
    print("uniconv: GUI arrives in step 19, use a subcommand", file=sys.stderr)
    return 2

# AFTER
    argv = sys.argv[1:] if argv is None else argv
    argv = [a for a in argv if not a.startswith("-psn_")]  # macOS Finder process serial number
    # ...
    from uniconv.ui.app import run_gui  # lazy: CLI runs stay free of Qt start-up cost
    return run_gui()
```

## Fase 3: data en documenten

Na deze fase zijn de families Data en Document beschikbaar. Hier ontstaat ook `core/tools.py` (externe tools vinden en veilig draaien), die fase 4 hergebruikt.

### Stap 20 — Create `src/uniconv/core/tools.py`

**Why:** Pandoc en ffmpeg moeten op één veilige manier gevonden en gedraaid worden: argumentenlijst, timeout, annuleerbaar, en op Windows zonder flitsend consolevenster. Vinden en draaien horen bij elkaar, dus ze delen één module.

```python
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def platform_tag() -> str:
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
    return f"{sys.platform}-{arch[platform.machine().lower()]}"  # win32-x86_64, darwin-arm64


@cache
def find_tool(name: str) -> Path | None:
    """Bundled copy first (frozen: <_MEIPASS>/bin, dev: vendor/<tag>), then PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    base = Path(sys._MEIPASS) / "bin" if is_frozen() else install_dir() / "vendor" / platform_tag()
    if (base / exe).is_file():
        return base / exe
    found = shutil.which(name)
    return Path(found) if found else None


def run_tool(cmd: list[str], *, timeout_s: int, cancel: CancelToken,
             on_stdout_line: Callable[[str], None] | None = None) -> str:
    """Run an external tool; returns stderr. Raises ConversionError / ConversionCancelled."""
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW,
    )  # NOTE: list argv, never shell=True (ruff S602 enforces this)
    err_lines: list[str] = []
    t_err = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t_out = threading.Thread(target=_pump, args=(proc.stdout, on_stdout_line), daemon=True)
    t_err.start(); t_out.start()  # drain both pipes so the child never blocks on a full buffer

    deadline = time.monotonic() + timeout_s
    while proc.poll() is None:
        if cancel.cancelled or time.monotonic() > deadline:
            proc.kill()
            proc.wait()
            if cancel.cancelled:
                raise ConversionCancelled("Conversie geannuleerd")
            raise ConversionError(f"Conversie duurde langer dan {timeout_s} s en is gestopt")
        time.sleep(0.1)
    t_err.join(); t_out.join()
    stderr = "".join(err_lines)
    if proc.returncode != 0:
        raise ConversionError(_last_meaningful_line(stderr) or f"Tool stopte met code {proc.returncode}")
    return stderr
```

### Stap 21 — Create `scripts/fetch_binaries.py`

**Why:** binaries horen niet in Git (honderden MB, per platform), maar CI en ontwikkelaars moeten exact dezelfde versies krijgen. Het script downloadt vastgepinde versies, controleert SHA-256, pakt ze uit naar `vendor/<platform_tag>/` en zet op macOS `chmod +x` (zip bewaart die bit niet altijd).

**What changes:** een manifest bovenin, per platform een URL, hash en het pad binnen het archief voor `pandoc`, `ffmpeg` en `ffprobe`. Idempotent: als `vendor/<tag>/.manifest-hash` overeenkomt, doet het niets.

```python
MANIFEST = {
    "win32-x86_64": [
        Asset("pandoc", url="https://github.com/jgm/pandoc/releases/download/<ver>/pandoc-<ver>-windows-x86_64.zip",
              sha256="<pin>", member="pandoc-<ver>/pandoc.exe"),
        Asset("ffmpeg", url="<pinned GPL build>", sha256="<pin>", member="<dir>/bin/ffmpeg.exe"),
        Asset("ffprobe", url="<same archive>", sha256="<pin>", member="<dir>/bin/ffprobe.exe"),
    ],
    "darwin-arm64": [...],
}
```

**Audit (doe dit als eerste van de nacht, review #16):** Pandoc publiceert officiële zips voor Windows en macOS arm64. Voor ffmpeg bestaat geen officiële binary: kies per platform een bekende GPL-buildbron met libx264, libvpx, libopus, libmp3lame en libvorbis, controleer op macOS met `otool -L` dat hij alleen systeembibliotheken gebruikt, en noteer bron en versie voor stap 31. Vind je voor macOS arm64 geen bruikbare statische build, laat ffmpeg dan weg uit het macOS-manifest; de mediafamilie verdwijnt dan vanzelf uit die build.

### Stap 22 — Edit `.github/workflows/ci.yml`

**Why:** zonder binaries slaat CI de Pandoc- en ffmpeg-tests over en bewijzen ze niets.

```yaml
# BEFORE
      # step 22 adds: cache vendor/ + python scripts/fetch_binaries.py

# AFTER
      - uses: actions/cache@v4
        with:
          path: vendor
          key: vendor-${{ runner.os }}-${{ runner.arch }}-${{ hashFiles('scripts/fetch_binaries.py') }}
      - run: python scripts/fetch_binaries.py
```

### Stap 23 — Create `src/uniconv/converters/data.py`

**Why:** dataformaten vallen in twee vormen uiteen: **tabellen** (CSV, XLSX) en **bomen** (JSON, YAML, TOML, XML). Binnen een vorm is conversie verliesvrij, ertussen is één regel nodig. Via deze twee tussenvormen hoef je geen paren te coderen. Review #5 en #8 worden hier opgelost.

| Van → naar | Regel | Fout of waarschuwing |
| --- | --- | --- |
| Boom → tabel | Afdalen door objecten met één sleutel tot er een lijst is; lijst van objecten → `pd.json_normalize` (geneste velden worden `adres.stad`); één los object wordt één rij | Anders `ConversionError`: "geen lijst van records" |
| Tabel → boom | `df.to_json(orient="records", date_format="iso")` en dan `json.loads` | Geen; datums worden ISO-strings, lege cellen `null` |
| Naar TOML | Root moet een object zijn: een lijst wordt `{"rows": [...]}`; `null` bestaat niet in TOML en wordt weggelaten | Waarschuwing bij beide ingrepen |
| Naar XML | Eén root vereist: een lijst wordt `{"root": {"row": [...]}}` | Waarschuwing dat er geen attributen worden gemaakt |
| Van XLSX | Alleen het eerste werkblad | Waarschuwing als er meer werkbladen zijn |
| Tekst lezen | `encoding: "auto"`: eerst UTF-8 (BOM wordt gestript), anders Windows-1252 | Waarschuwing bij de fallback |
| CSV schrijven | UTF-8 mét BOM, zodat Excel accenten goed toont | Geen |

```python
class DataOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: str = "auto"          # or an explicit codec name such as "utf-8" or "cp1252"
    csv_delimiter: str = Field(",", min_length=1, max_length=1)
    indent: int = Field(2, ge=0, le=8)


_TABULAR = {"csv", "xlsx"}


class DataConverter(Converter):
    family, family_label, Options = "data", "Data", DataOptions
    formats = (
        Format("csv", "CSV", (".csv",)),
        Format("xlsx", "Excel", (".xlsx",),
               ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)),
        Format("json", "JSON", (".json",)),
        Format("yaml", "YAML", (".yaml", ".yml")),
        Format("toml", "TOML", (".toml",)),
        Format("xml", "XML", (".xml",)),
    )

    def convert(self, ctx: ConversionContext) -> None:
        data = _load(ctx.input_path, ctx.source.key, ctx.options, ctx)
        ctx.cancel.raise_if_cancelled()
        if ctx.target.key in _TABULAR and not isinstance(data, pd.DataFrame):
            data = _tree_to_frame(data)
        elif ctx.target.key not in _TABULAR and isinstance(data, pd.DataFrame):
            data = json.loads(data.to_json(orient="records", date_format="iso"))
        _dump(data, ctx.output_path, ctx.target.key, ctx.options, ctx)


def _read_text(path: Path, opts: DataOptions, ctx: ConversionContext) -> str:
    raw = path.read_bytes()
    if opts.encoding != "auto":
        return raw.decode(opts.encoding)
    try:
        return raw.decode("utf-8-sig")  # also strips the BOM Excel adds
    except UnicodeDecodeError:
        ctx.warn("Bestand is geen UTF-8 en is gelezen als Windows-1252.")
        return raw.decode("cp1252")


def _tree_to_frame(data: Any) -> pd.DataFrame:
    # unwrap {"root": {"row": [...]}} (XML) or {"items": [...]} (API exports)
    while isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))
    if isinstance(data, dict):
        data = [data]  # a single record becomes one row
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        return pd.json_normalize(data)
    raise ConversionError("Deze data is geen lijst van records en past daarom niet in een tabel.")
```

`_load` en `_dump` gebruiken een `match` op de formaatsleutel: CSV via `pd.read_csv(io.StringIO(text), sep=None, engine="python")` (raadt `;` of `,`, met `,` als fallback als het raden mislukt), XLSX via `pd.ExcelFile` (waarschuwing bij meer werkbladen), JSON via `json`, YAML via `yaml.safe_load`/`safe_dump(sort_keys=False, allow_unicode=True)` (nooit `yaml.load`: dat kan code uitvoeren), TOML via `tomllib`/`tomli_w`, XML via `xmltodict`. Schrijven: CSV met `encoding="utf-8-sig"` en `sep=opts.csv_delimiter`, JSON met `ensure_ascii=False`. Elke parsefout wordt `ConversionError` met de regel uit de exceptie.

### Stap 24 — Create `src/uniconv/converters/document.py`

**Why:** Pandoc doet het echte werk; deze converter vertaalt formaatsleutels naar Pandoc-namen en kiest de vlaggen. PDF-output vereist LaTeX en blijft buiten v1. Review #11: embedden impliceert standalone.

```python
class DocumentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    standalone: bool = True        # full document with <head>/preamble instead of a fragment
    embed_resources: bool = True   # HTML: images inlined, one self-contained file


_PANDOC = {"md": "markdown", "html": "html", "tex": "latex", "docx": "docx",
           "odt": "odt", "epub": "epub", "rtf": "rtf", "txt": "plain"}
_HAS_IMAGES = {"docx", "odt", "epub"}


class DocumentConverter(Converter):
    family, family_label, Options = "document", "Document", DocumentOptions
    formats = (
        Format("md", "Markdown", (".md", ".markdown")),
        Format("html", "HTML", (".html", ".htm")),
        Format("tex", "LaTeX", (".tex",)),
        Format("docx", "Word", (".docx",),
               ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",)),
        Format("odt", "OpenDocument", (".odt",), ("application/vnd.oasis.opendocument.text",)),
        Format("epub", "EPUB", (".epub",), ("application/epub+zip",)),
        Format("rtf", "RTF", (".rtf",), ("application/rtf",)),
        Format("txt", "Platte tekst", (".txt",), source=False),  # plain text has no structure to read
    )

    def available(self) -> bool:
        return find_tool("pandoc") is not None

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if source in {"docx", "odt"}:
            out.append("Opmaak zoals lettertypes, kleuren en marges gaat verloren.")
        if source in _HAS_IMAGES and target in {"md", "tex", "txt", "rtf"}:
            out.append("Afbeeldingen worden niet meegenomen.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        opts: DocumentOptions = ctx.options
        dst = ctx.target.key
        cmd = [str(find_tool("pandoc")), str(ctx.input_path),
               "-f", _PANDOC[ctx.source.key], "-t", _PANDOC[dst], "-o", str(ctx.output_path),
               f"--resource-path={ctx.input_path.parent}"]  # resolve relative image paths
        if dst == "html" and opts.embed_resources:
            cmd += ["--standalone", "--embed-resources"]  # embed requires standalone (review #11)
        elif opts.standalone and dst in {"html", "tex", "rtf"}:
            cmd.append("--standalone")
        run_tool(cmd, timeout_s=ctx.timeout_s, cancel=ctx.cancel)
```

### Stap 25 — Edit `src/uniconv/core/registry.py`

**Why:** de nieuwe converters moeten in de registry; zonder Pandoc verbergt `available()` de documentfamilie.

```python
# BEFORE
    for conv in (ImageConverter(),):  # step 25: DataConverter(), DocumentConverter(); step 27: MediaConverter()

# AFTER
    for conv in (ImageConverter(), DataConverter(), DocumentConverter()):  # step 27: MediaConverter()
```

## Fase 4: audio en video

Na deze fase is de familie Audio/video beschikbaar, met echte voortgang en annuleren. De infrastructuur (`tools.py`, worker-thread, onbepaalde voortgangsbalk) bestaat al, dus deze fase is vooral de codec-tabel. Review #2, #6 en #12 worden hier opgelost.

### Stap 26 — Create `src/uniconv/converters/media.py`

**Why:** ffmpeg kan alles, maar alleen met de juiste codec per container. Deze converter legt per doel vast welke codecs en vlaggen worden gebruikt, en leest de voortgang uit ffmpeg zodat de balk iets betekent.

| Doel | Video | Audio | Kwaliteit uit config |
| --- | --- | --- | --- |
| MP4, MOV, MKV | libx264 | AAC | `video_crf`, `video_preset`, `audio_bitrate` |
| WebM | libvpx-vp9 | libopus | `webm_crf`, `audio_bitrate` |
| MP3 | — | libmp3lame | `audio_bitrate` |
| M4A | — | AAC | `audio_bitrate` |
| OGG | — | libvorbis | `audio_bitrate` |
| Opus | — | libopus | `audio_bitrate` |
| FLAC | — | flac | lossless |
| WAV | — | pcm\_s16le | lossless |

```python
class MediaOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_bitrate: str = Field("192k", pattern=r"^\d{2,3}k$")
    video_crf: int = Field(23, ge=0, le=51)
    video_preset: Literal["ultrafast", "veryfast", "fast", "medium", "slow"] = "veryfast"
    webm_crf: int = Field(32, ge=0, le=63)


_AUDIO = {"mp3", "wav", "flac", "ogg", "m4a", "opus"}
_EVEN = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]  # yuv420p needs even width and height (review #2)


class MediaConverter(Converter):
    family, family_label, Options = "media", "Audio/video", MediaOptions
    formats = (
        Format("mp3", "MP3", (".mp3",), ("audio/mpeg",)),
        Format("wav", "WAV", (".wav",), ("audio/x-wav", "audio/wav")),
        Format("flac", "FLAC", (".flac",), ("audio/x-flac", "audio/flac")),
        Format("ogg", "Ogg Vorbis", (".ogg",), ("audio/ogg",)),
        Format("m4a", "M4A", (".m4a",), ("audio/mp4", "audio/x-m4a")),
        Format("opus", "Opus", (".opus",), ("audio/opus",)),
        Format("mp4", "MP4", (".mp4",), ("video/mp4",)),
        Format("mkv", "MKV", (".mkv",), ("video/x-matroska",)),
        Format("webm", "WebM", (".webm",), ("video/webm",)),
        Format("mov", "QuickTime", (".mov",), ("video/quicktime",)),
    )  # NOTE: verify every mime with the step 9 audit; .ogg and .opus can both be audio/ogg

    def available(self) -> bool:
        return find_tool("ffmpeg") is not None and find_tool("ffprobe") is not None

    def targets(self, source: str) -> list[str]:
        keys = super().targets(source)
        return keys if source not in _AUDIO else [k for k in keys if k in _AUDIO]  # no audio -> video

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if source not in _AUDIO and target in _AUDIO:
            out.append("Alleen het geluid wordt bewaard.")
        if source not in _AUDIO and target not in _AUDIO:
            out.append("Ondertitels en extra audiosporen worden niet meegenomen.")
        if source in {"wav", "flac"} and target in {"mp3", "m4a", "ogg", "opus"}:
            out.append("Lossless naar lossy: kleiner bestand, minder detail.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        duration = _probe_duration(ctx)  # seconds or None; None keeps the progress bar indeterminate
        cmd = [str(find_tool("ffmpeg")), "-hide_banner", "-nostdin", "-y",
               "-i", str(ctx.input_path),
               "-sn", "-dn",  # drop subtitle/data streams: image subs break MP4 (review #6)
               *_codec_args(ctx.target.key, ctx.options),
               "-progress", "pipe:1", "-nostats",
               str(ctx.output_path)]

        def on_line(line: str) -> None:
            if duration and line.startswith("out_time_us="):  # position in microseconds
                us = line.split("=", 1)[1].strip()
                if us.isdigit():
                    ctx.on_progress(min(int(us) / 1e6 / duration, 0.99))

        run_tool(cmd, timeout_s=ctx.timeout_s, cancel=ctx.cancel, on_stdout_line=on_line)


def _codec_args(target: str, o: MediaOptions) -> list[str]:
    x264 = [*_EVEN, "-c:v", "libx264", "-preset", o.video_preset, "-crf", str(o.video_crf),
            "-pix_fmt", "yuv420p"]  # 8-bit 4:2:0: plays in QuickTime and browsers, also from 10-bit HDR
    aac = ["-c:a", "aac", "-b:a", o.audio_bitrate]
    match target:
        case "mp4" | "mov":
            return [*x264, *aac, "-movflags", "+faststart"]
        case "mkv":
            return [*x264, *aac]
        case "webm":  # VP9 defaults are slower than realtime; these settings are (review #12)
            return [*_EVEN, "-c:v", "libvpx-vp9", "-crf", str(o.webm_crf), "-b:v", "0",
                    "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
                    "-c:a", "libopus", "-b:a", o.audio_bitrate]
        case "mp3":
            return ["-vn", "-c:a", "libmp3lame", "-b:a", o.audio_bitrate]
        case "m4a":
            return ["-vn", *aac]
        case "ogg":
            return ["-vn", "-c:a", "libvorbis", "-b:a", o.audio_bitrate]
        case "opus":
            return ["-vn", "-c:a", "libopus", "-b:a", o.audio_bitrate]
        case "flac":
            return ["-vn", "-c:a", "flac"]
        case "wav":
            return ["-vn", "-c:a", "pcm_s16le"]
```

`-vn` bij audiodoelen voorkomt ook dat albumhoezen in MP3's als videostream worden meegenomen. `_probe_duration` roept `ffprobe -v error -show_entries format=duration -of csv=p=0 <input>` aan via `run_tool` en geeft `None` als het antwoord geen getal is.

**Audit:** draai na het pinnen (stap 21) `ffmpeg -encoders` op beide platforms en controleer dat libx264, libvpx-vp9, libopus, libmp3lame en libvorbis erin zitten.

### Stap 27 — Edit `src/uniconv/core/registry.py`

**Why:** de mediaconverter moet in de registry; zonder ffmpeg verbergt `available()` de familie (dat is ook de snijlijn uit de bouwvolgorde).

```python
# BEFORE
    for conv in (ImageConverter(), DataConverter(), DocumentConverter()):  # step 27: MediaConverter()

# AFTER
    for conv in (ImageConverter(), DataConverter(), DocumentConverter(), MediaConverter()):
```

## Fase 5: packaging en release

Na deze fase levert het pushen van tag `v0.1.0` automatisch een GitHub-release op met twee downloads: een Windows-installer en een DMG voor Apple Silicon. Elke build wordt vóór het uploaden met echte conversies getest.

### Stap 28 — Create `packaging/uniconv.spec`

**Why:** PyInstaller moet weten welke libraries en meegeleverde tools erbij horen. Een spec-bestand maakt de build reproduceerbaar. `onedir` in plaats van `onefile`: sneller opstarten en minder valse meldingen van virusscanners.

**What changes:** nieuw bestand, plus iconen `packaging/windows/icon.ico` en `packaging/macos/icon.icns`. De binaries uit `vendor/<tag>/` gaan naar `bin/` in de bundel, precies waar `find_tool()` zoekt. Ongebruikte Qt-modules worden uitgesloten. De versie gaat mee naar Finder (review #15).

```python
import platform, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from uniconv import __version__  # noqa: E402
from uniconv.core.tools import platform_tag  # noqa: E402  (same tag as at runtime)

binaries = [(str(p), "bin") for p in (ROOT / "vendor" / platform_tag()).iterdir()
            if p.is_file() and not p.name.startswith(".")]
binaries += collect_dynamic_libs("pillow_heif")  # libheif ships as a shared library
datas = [(str(ROOT / "LICENSE"), "."), (str(ROOT / "THIRD_PARTY_LICENSES.md"), ".")]

a = Analysis(
    [str(ROOT / "src/uniconv/__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="UniConv",
          console=False, icon=str(ROOT / "packaging/windows/icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="UniConv")

if sys.platform == "darwin":
    app = BUNDLE(
        coll, name="UniConv.app", icon=str(ROOT / "packaging/macos/icon.icns"),
        bundle_identifier="io.github.forgeline-optimizations.uniconv",
        version=__version__,
        info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0"},
    )
```

### Stap 29 — Create `packaging/windows/installer.iss`

**Why:** gebruikers verwachten een installer met Startmenu-snelkoppeling en uninstaller. Een per-gebruiker-installatie vereist geen adminrechten. De vaste `AppId` zorgt dat een nieuwe versie over de oude heen installeert (review #13).

```ini
[Setup]
; Never change this GUID: it identifies the app across versions
AppId={{504A34CB-03E6-468D-B807-ABF6D6AC0117}
AppName=UniConv
AppVersion={#AppVersion}
AppPublisher=Forgeline Optimizations
AppPublisherURL=https://github.com/Forgeline-Optimizations/uniconv
DefaultDirName={localappdata}\Programs\UniConv
DefaultGroupName=UniConv
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=UniConv-{#AppVersion}-windows-x86_64-setup
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\UniConv.exe

[Files]
Source: "..\..\dist\UniConv\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\UniConv"; Filename: "{app}\UniConv.exe"
Name: "{userdesktop}\UniConv"; Filename: "{app}\UniConv.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Snelkoppeling op het bureaublad"; Flags: unchecked
```

De uninstaller verwijdert alleen `{app}`. Config, log en werkmap blijven staan; dat staat in de README.

### Stap 30 — Create `packaging/macos/build_dmg.sh`

**Why:** een DMG is hoe Mac-gebruikers apps verwachten. Op Apple Silicon moet elke binary minstens ad-hoc gesigneerd zijn, anders start hij niet; dit script signeert de hele bundel inclusief ffmpeg en Pandoc.

```bash
#!/usr/bin/env bash
set -euo pipefail
VERSION="$1"
APP="dist/UniConv.app"
codesign --force --deep --sign - "$APP"   # ad-hoc: no Apple Developer account needed
hdiutil create -volname "UniConv" -srcfolder "$APP" -ov -format UDZO \
  "dist/UniConv-${VERSION}-macos-arm64.dmg"
```

### Stap 31 — Create `THIRD_PARTY_LICENSES.md`

**Why:** de GPL van Pandoc en ffmpeg vereist dat je bij distributie hun licentie meelevert en zegt waar de broncode staat. Zonder dit bestand is de release juridisch niet in orde.

**What changes:** per meegeleverde component (Pandoc, ffmpeg met de gekozen build, Qt/PySide6, Pillow, libheif/pillow-heif, pandas en de overige dependencies): naam, versie, licentie en een link naar de broncode van die versie. De versies komen uit het manifest van stap 21. De spec (stap 28) neemt het bestand mee in de bundel.

### Stap 32 — Create `.github/workflows/release.yml`

**Why:** releases moeten reproduceerbaar zijn en niet van één laptop afhangen. De smoke-test draait de *gebouwde* app, omdat packagingfouten (vergeten library, verkeerd binary-pad) alleen daar zichtbaar worden. Een windowed exe heeft op Windows mogelijk geen stdout, dus de test controleert bestanden, geen printuitvoer.

```yaml
name: release
on:
  push:
    tags: ["v*"]
permissions:
  contents: write

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest]  # macos-latest = Apple Silicon
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install ".[build]"
      - run: python scripts/fetch_binaries.py
      - run: pyinstaller packaging/uniconv.spec --noconfirm

      - name: Smoke test the frozen app
        run: |
          python -c "from PIL import Image; Image.new('RGBA', (8, 8), (255, 0, 0, 128)).save('smoke.png')"
          python -c "import wave; w = wave.open('smoke.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(bytes(16000)); w.close()"
          if [ "$RUNNER_OS" = "Windows" ]; then BIN=dist/UniConv/UniConv.exe; else BIN=dist/UniConv.app/Contents/MacOS/UniConv; fi
          "$BIN" convert smoke.png --to jpg --out smoke_out
          test -f smoke_out/smoke.jpg
          # skip the media check when this platform shipped without ffmpeg (step 21 fallback)
          if ls vendor/*/ffmpeg* >/dev/null 2>&1; then
            "$BIN" convert smoke.wav --to mp3 --out smoke_out
            test -f smoke_out/smoke.mp3
          fi

      - name: Package (Windows)
        if: runner.os == 'Windows'
        run: iscc "//DAppVersion=${GITHUB_REF_NAME#v}" packaging/windows/installer.iss

      - name: Package (macOS)
        if: runner.os == 'macOS'
        run: bash packaging/macos/build_dmg.sh "${GITHUB_REF_NAME#v}"

      - uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.exe
            dist/*.dmg
```

**Audit:** controleer of Inno Setup (`iscc`) op het Windows-runner-image staat; zo niet, voeg `choco install innosetup -y` toe vóór de package-stap.

### Stap 33 — Edit `README.md`

**Why:** de README is de winkelpagina op GitHub. Gebruikers moeten zonder zoeken weten hoe ze installeren, waarom hun OS waarschuwt en waar hun instellingen staan.

**What changes:** de stub uit stap 2 wordt aangevuld met: een screenshot; de ondersteunde formaten per familie (uit `python -m uniconv formats`); installatie per OS, met de SmartScreen-stap ("Meer info → Toch uitvoeren") en de Gatekeeper-stap (macOS 15+: Systeeminstellingen → Privacy en beveiliging → "Open toch"); een tabel met de locaties van `config.json`, `config.defaults.json`, werkmap en log per OS; hoe je kwaliteit aanpast via `config.json`; "Ontwikkelen" (`pip install -e ".[dev]"`, `python scripts/fetch_binaries.py`, `pytest`); en de licentie met een verwijzing naar `THIRD_PARTY_LICENSES.md`.

## Tests

De suite bewijst drie dingen: elk aangeboden paar levert een geldig bestand op, verlies wordt gemeld, en er komt nooit een half of verkeerd bestand in de map van de gebruiker. Elke review-fix uit de kritieke tabel heeft minstens één eigen test. Schrijf de tests van een fase mee in die fase, niet pas aan het eind.

### Stap 34 — Create `tests/conftest.py`

**Why:** één fabriek voor voorbeeldbestanden en één geïsoleerde runner per test, zodat de matrixtests elk paar uit de registry kunnen testen zonder binaire bestanden in de repo.

**What changes:** fixtures `cfg` (defaults, werkmap in `tmp_path`), `registry`, `runner`, `out_dir` en `make_sample(key, **kw) -> Path`. Afbeeldingen maakt Pillow (HEIC via pillow-heif, dat ook kan schrijven), data en Markdown zijn tekst, DOCX/ODT/EPUB maakt Pandoc uit Markdown, audio/video maakt ffmpeg met `-f lavfi -i sine=duration=1` en `testsrc=duration=1:size=64x64`. Een hook slaat `needs_pandoc`/`needs_ffmpeg`-tests over als `find_tool()` niets vindt.

### Stap 35 — Create de unit-tests in `tests/unit/`

| Bestand | Bewijst |
| --- | --- |
| `test_config.py` | Zonder bestand: code-defaults; een override wint; een onbekende sleutel of kapotte JSON leidt tot `config.invalid.json` plus defaults; `save_user_overrides` schrijft alleen de afwijking en weigert ongeldige waarden zonder het bestand te raken |
| `test_registry.py` | Een dubbele formaatsleutel geeft `ValueError` bij `register`; `targets()` bevat nooit de bron; HEIC is geen doel en PDF geen bron; `options_for` met `jpeg_quality: 120` geeft een melding met `defaults.image.jpeg_quality` |
| `test_detect.py` | Een PNG met extensie `.jpg` wordt PNG; CSV via extensie; een MP3 in de familie Afbeelding geeft `WrongFamilyError` met "MP3" en "Audio/video" in de tekst; onbekende extensie geeft `UnsupportedFormatError` |
| `test_workspace.py` | `rename` geeft `foto (1).png`; `skip` geeft `None` en laat het bestaande bestand staan; **`overwrite` vervangt een bestaand bestand (review #1, draait in CI op Windows)**; een alleen-lezen doelmap geeft `ConversionError`, geen `OSError` (#7); er blijft geen `.uniconv-partial` achter; `cleanup_stale` laat mappen jonger dan 24 uur staan (#14) |
| `test_tools.py` | Exit-code ≠ 0 wordt `ConversionError` met de laatste stderr-regel; timeout doodt het proces binnen 1 s; cancel geeft `ConversionCancelled` (testproces: `python -c "import time; time.sleep(30)"`) |
| `test_layering.py` | Geen module onder `uniconv.core` of `uniconv.converters` importeert `PySide6` of `uniconv.ui` (AST-scan) |

### Stap 36 — Create de integratietests in `tests/integration/`

| Bestand | Bewijst |
| --- | --- |
| `test_matrix.py` | Geparametriseerd over **alle** families en elk paar uit `registry.targets()`: conversie slaagt, het bestand is niet leeg, en binaire doelen worden door `filetype` als het doelformaat herkend. Een nieuw formaat wordt zo automatisch getest. |
| `test_jobs.py` | Een converter die een half bestand schrijft en dan faalt, laat niets achter in `out_dir` en de werkmap is leeg; twee inputs waarvan één kapot geeft `["failed", "done"]`; geannuleerd geeft `cancelled` zonder output; te groot bestand geeft `InputTooLargeError`; `output_dir=None` schrijft naast de bron (#3) |
| `test_image.py` | PNG met alpha naar JPG wordt wit (voorbeeld hieronder); **CMYK-JPEG naar PNG en 16-bit TIFF naar JPG slagen (#4)**; EXIF-oriëntatie 6 wordt rechtop opgeslagen; geanimeerde GIF geeft de één-frame-waarschuwing; een afbeelding boven `max_megapixels` geeft een nette fout (#9) |
| `test_data.py` | CSV → JSON → CSV geeft dezelfde records; **CSV in cp1252 en CSV met BOM worden goed gelezen (#5)**; **XML met `<root><row>` naar CSV geeft rijen (#8)**; geneste JSON geeft kolom `adres.stad`; CSV met `;` werkt; JSON-scalar naar CSV geeft de records-fout |
| `test_document.py` (`needs_pandoc`) | MD → HTML bevat `<h1>`; MD met afbeelding → HTML bevat een `data:image`-URI; `standalone: false` met embed faalt niet (#11) |
| `test_media.py` (`needs_ffmpeg`) | **Video van 63×47 pixels naar MP4 slaagt (#2)**; MKV met een ondertitelspoor naar MP4 slaagt (#6); MP4 → MP3 heeft geen videostream; voortgang loopt op; annuleren stopt binnen 1 s |

**Representatieve test** (`test_image.py`): transparantie verdwijnt stil als je niet oplet. Deze test legt vast dat het resultaat de geconfigureerde achtergrond krijgt én dat er vooraf gewaarschuwd wordt.

```python
def test_png_alpha_to_jpg_is_flattened_on_configured_background(registry, runner, tmp_path, out_dir):
    src = tmp_path / "logo.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 0)).save(src)  # fully transparent red

    conv = registry.find("image", "png", "jpg")
    assert any("transparantie" in w.lower() for w in conv.expected_losses("png", "jpg"))

    [result] = runner.run(Job("image", "jpg", [src], out_dir), CancelToken())

    assert result.status == "done"
    with Image.open(result.output) as out:
        assert out.format == "JPEG"
        assert out.mode == "RGB"
        assert min(out.getpixel((0, 0))) > 245  # white (#FFFFFF), allowing for JPEG noise
```

**Belangrijkste integratietest** (`test_jobs.py`): "een mislukte conversie laat niets achter". Gebruik een `FailingConverter` (eigen familie, één testformaat) die eerst een half bestand naar `ctx.output_path` schrijft en dan `ConversionError` gooit. Controleer dat `out_dir` leeg is en `workspace.root` geen jobmappen meer bevat. Dat de test een eigen familie kan registreren, bewijst meteen de uitbreidbaarheid.

### Stap 37 — Create `tests/ui/test_main_window.py`

**Why:** de UI is dun, maar de koppeling met registry en worker-thread kan breken zonder dat een unit-test het ziet.

| Test | Bewijst |
| --- | --- |
| `test_drop_fills_target_combo` | Een PNG vult de dropdown met de afbeeldingsdoelen, zonder PNG en zonder HEIC |
| `test_wrong_family_shows_error` | Een MP3 in de familie Afbeelding toont de foutmelding en houdt "Converteer" uit |
| `test_convert_end_to_end` | Klik "Converteer", wacht met `qtbot.waitSignal(worker.finished)`; status noemt het outputbestand en "Open map" is zichtbaar |
| `test_inputs_disabled_while_busy` | Tijdens een job staan familieknoppen, dropzone en dropdown uit (#10) |

## Samenvatting

| Stap | Bestand | Actie | Wat verandert |
| --- | --- | --- | --- |
| 1 | `pyproject.toml` | **Create** | Dependencies, entry point `uniconv`, ruff en pytest |
| 2 | `.gitignore`, `LICENSE`, `README.md` | **Create** | GPL-3.0, ignores, README-stub |
| 3 | `src/uniconv/__init__.py`, `__main__.py` | **Create** | Versie, `APP_NAME`, entry point met `--version` |
| 4 | `src/uniconv/config.py` | **Create** | App-config met code-defaults, overrides, referentiekopie |
| 5 | `src/uniconv/paths.py` | **Create** | Config-, werk- en outputpaden per gebruiker |
| 6 | `.github/workflows/ci.yml` | **Create** | Lint en tests op Windows en macOS |
| 7 | `src/uniconv/core/errors.py` | **Create** | Fouttypes met gebruikersboodschap |
| 8 | `src/uniconv/core/converter.py` | **Create** | `Format`, `CancelToken`, `ConversionContext`, `Converter` met eigen formaten en opties |
| 9 | `src/uniconv/core/registry.py` | **Create** | Registry, detectie, optievalidatie (**Audit** MIME-types) |
| 10 | `src/uniconv/core/workspace.py` | **Create** | Werkmap per job, `finalize` met `os.replace` en leesbare fouten |
| 11 | `src/uniconv/core/jobs.py` | **Create** | `Job` met expliciete outputmap, `JobRunner` |
| 12 | `src/uniconv/converters/image.py` | **Create** | Pillow-converter met modusnormalisatie, ICC en limiet |
| 13 | `src/uniconv/cli.py` | **Create** | `formats` en `convert` |
| 14 | `src/uniconv/__main__.py` | **Edit** | CLI-tak |
| 15 | `src/uniconv/ui/drop_zone.py` | **Create** | Drag & drop en bestandsdialoog, inline stijl |
| 16 | `src/uniconv/ui/worker.py` | **Create** | `JobWorker` op een `QThread` |
| 17 | `src/uniconv/ui/main_window.py` | **Create** | Hoofdvenster, invoer uit tijdens busy, voortgang |
| 18 | `src/uniconv/ui/app.py` | **Create** | Bootstrap, logging, optievalidatie bij start |
| 19 | `src/uniconv/__main__.py` | **Edit** | GUI-tak en `-psn_`-filter |
| 20 | `src/uniconv/core/tools.py` | **Create** | Tools vinden en veilig, annuleerbaar draaien |
| 21 | `scripts/fetch_binaries.py` | **Create** | Gepinde downloads (**Audit** bronnen, als eerste) |
| 22 | `.github/workflows/ci.yml` | **Edit** | Binaries ophalen en cachen |
| 23 | `src/uniconv/converters/data.py` | **Create** | Tabel/boom-conversies, encoding-detectie |
| 24 | `src/uniconv/converters/document.py` | **Create** | Pandoc-wrapper |
| 25 | `src/uniconv/core/registry.py` | **Edit** | Data en documenten registreren |
| 26 | `src/uniconv/converters/media.py` | **Create** | ffmpeg-codectabel, even afmetingen, voortgang (**Audit** encoders) |
| 27 | `src/uniconv/core/registry.py` | **Edit** | Media registreren |
| 28 | `packaging/uniconv.spec` (+ iconen) | **Create** | PyInstaller onedir, `UniConv.app` met versie |
| 29 | `packaging/windows/installer.iss` | **Create** | Per-gebruiker-installer met vaste `AppId` |
| 30 | `packaging/macos/build_dmg.sh` | **Create** | Ad-hoc signing en DMG (arm64) |
| 31 | `THIRD_PARTY_LICENSES.md` | **Create** | Licenties en bronverwijzingen |
| 32 | `.github/workflows/release.yml` | **Create** | Builds, smoke-test, release (**Audit** Inno Setup) |
| 33 | `README.md` | **Edit** | Installatie, waarschuwingen, paden, config, ontwikkelen |
| 34 | `tests/conftest.py` | **Create** | Voorbeeldbestanden genereren, fixtures |
| 35 | `tests/unit/*` | **Create** | 6 testbestanden voor core-onderdelen |
| 36 | `tests/integration/*` | **Create** | Matrixtest over alle families plus gedragstests per review-fix |
| 37 | `tests/ui/test_main_window.py` | **Create** | pytest-qt-tests voor het venster |

**Beslist:** GitHub-slug `Forgeline-Optimizations` is bevestigd; de `AppId`-GUID in stap 29 is `504A34CB-03E6-468D-B807-ABF6D6AC0117`.
