# Uitbreidingsplan: UniConv 0.2, gemiddelde conversies

Nov 3, 2026 · @Sander Nales

## Anker

**Wat 0.2 toevoegt:** de "gemiddelde" conversies uit het eerste overzicht, allemaal getest in een sandbox voordat ze in dit plan kwamen:

- **Afbeelding naar PDF, nu verliesvrij:** JPEG wordt ongewijzigd ingebed, PNG zonder JPEG-compressie, en geanimeerde GIF's en TIFF's met meerdere pagina's worden PDF's met meerdere pagina's.
- **Tekstdocumenten naar PDF:** Markdown, LaTeX, EPUB en HTML via Pandoc + Typst (meegeleverd).
- **Office naar PDF:** Word, ODT, RTF, PowerPoint en Excel met de originele opmaak via een **geïnstalleerde** LibreOffice.
- **HTML naar PDF met CSS:** via een **geïnstalleerde** Chrome of Edge.
- **Vector:** SVG naar PNG/JPG/WebP/TIFF/BMP/GIF (resvg) en naar vector-PDF (Typst); afbeelding naar SVG door tracing (vtracer).
- **Nieuwe familie 3D-model:** STL, OBJ, PLY, OFF, GLB, glTF en 3MF onderling (trimesh).

**Kernbeslissing:** een familie mag nu meerdere **providers** hebben (één converterklasse per engine) met een vaste voorrang. Daarmee kan "Word naar PDF" via LibreOffice gaan als dat geïnstalleerd is, en anders via Pandoc + Typst met een waarschuwing. Engines die een proces kunnen laten crashen of minutenlang kunnen rekenen, draaien buiten het app-proces, zodat annuleren en time-outs blijven werken.

**Buiten scope:** PDF als bron (PDF naar Word of afbeelding), OCR, FBX en CAD (STEP/IGES), conversies tussen families, batch in de UI, LibreOffice of een browser meeleveren in de installer, en opties per conversie in de UI.

**Vaste keuzes**

| Onderwerp | Keuze |
| --- | --- |
| Versie | 0.2.0 |
| Nieuwe meegeleverde binaries | Typst 0.15.1 (Apache-2.0), resvg 0.49.0 (Apache-2.0 OR MIT) |
| Nieuwe Python-pakketten | img2pdf (LGPL-3.0) + pikepdf (MPL-2.0), vtracer (MIT), trimesh (MIT) + scipy, networkx, lxml (BSD) |
| Gedetecteerde apps (niet meegeleverd) | LibreOffice (`soffice`), Chrome / Edge / Chromium |
| Isolatie | `multiprocessing` met `spawn` voor vtracer en trimesh; CLI-tools via het bestaande `run_tool` |
| Minimale macOS-versie | 14.0 (was 12.0; zie review #8) |
| Licentie repo | Blijft GPL-3.0-or-later; alle nieuwe componenten zijn daarmee verenigbaar |

## Huidige stand

De gebouwde code (commit `7cef5ef`, "Sprint 5 done") volgt het v1-plan op één punt na: het `Converter`-contract is precies goed voor uitbreiding, maar de `Registry` laat maar één converter per familie toe en eist unieke formaatsleutels over **alle** families. Dat botst direct met deze uitbreiding.

| Onderdeel | Wat er nu is | Gevolg voor 0.2 |
| --- | --- | --- |
| `core/converter.py` | `Format`, `Converter` met `family`, `formats`, `Options`, `available()`, `targets()`, `expected_losses()` | Bruikbaar; krijgt twee optionele klasse-attributen |
| `core/registry.py` | `_convs: dict[family, Converter]`; `register()` gooit `ValueError` bij een tweede converter in een familie of een dubbele formaatsleutel | Moet herschreven: PDF is straks doel in afbeelding, document én data; DOCX zit in de Pandoc- en de LibreOffice-provider |
| `core/tools.py` | `find_tool()` (meegeleverd, dan `PATH`) en `run_tool()` (time-out, annuleren, geen shell) | Werkt voor Typst en resvg; geïnstalleerde apps vinden ontbreekt nog |
| `core/jobs.py` | `options_for(job.family, cfg)` | Opties moeten per provider komen |
| `converters/image.py` | PDF via Pillow (`img.save(format="PDF")`) | **Verliesgevend**, zie review #1 |
| `converters/document.py` | Pandoc, geen PDF-uitvoer | Krijgt PDF via Typst |
| `scripts/fetch_binaries.py` | Gepinde zips met SHA-256 (ADR-001) | Kan alleen `.zip`; Typst voor macOS is `.tar.xz` |
| `packaging/uniconv.spec` | Alles uit `vendor/<tag>/` naar `bin/`; `LSMinimumSystemVersion` 12.0 | Data van trimesh ontbreekt; macOS-minimum klopt niet (review #8) |
| `__main__.py` | Geen `multiprocessing.freeze_support()` | Verplicht zodra er processen gestart worden (review #7) |
| Aanroepers van `registry.converter(family)` | `cli.py:20`, `ui/main_window.py:191`, `tests/integration/test_matrix.py:14`, `tests/unit/test_registry.py:22,29`, `tests/unit/test_detect.py:87`, `tests/integration/test_document.py:82` | Allemaal mee aanpassen in stap 5 (code) en stap 27-28 (tests) |

## Onderzoek per conversie

Elke route is in een Linux-sandbox echt gedraaid met dezelfde versies die het plan pint: Pandoc 3.13, Typst 0.15.1, resvg 0.49.0, LibreOffice 24.2, vtracer 0.6.15, trimesh 5.2.0, img2pdf 0.6.3. Wat alleen op Windows of macOS te controleren is, staat als **Audit** in de stappen en wordt in CI getest.

| Conversie | Engine en manier | Licentie, grootte | Wat de test liet zien |
| --- | --- | --- | --- |
| Afbeelding → PDF | img2pdf (Python) in het app-proces | LGPL-3.0 + pikepdf MPL-2.0; \~10 MB | JPEG-stream byte-identiek ingebed; PNG als Flate (pixelfout 0,00 tegen 0,12 bij Pillow); GIF/WebP-animatie en TIFF met 3 pagina's geven 3 PDF-pagina's; EXIF-rotatie goed met `Rotation.ifvalid`; HEIC, CMYK en 16-bit werken. **WebP met alpha faalt** (`AlphaChannelError`) |
| Markdown, LaTeX, EPUB, HTML → PDF | Pandoc maakt Typst-bron, daarna draait de meegeleverde Typst zelf met `--root` op de jobmap (stap 12) | Apache-2.0; 52 MB (Windows), 45 MB (macOS) | Koppen, tabel, afbeelding, code, formule, é/€/emoji/中文 correct; `-V papersize=a4 -V lang=nl` geeft A4 en "Figuur 1". HTML verliest alle CSS. Word via deze route verliest de Word-lay-out |
| Word, ODT, RTF, PowerPoint, Excel → PDF | `soffice --headless --convert-to pdf`, LibreOffice van de gebruiker | MPL-2.0, niet meegeleverd | 0,3-1,2 s per bestand; Excel exporteert alle werkbladen. **Exitcode is 0 bij een mislukte conversie**, alleen "Error: source file could not be loaded" op stdout. Eigen profielmap per job kost \~0,5 s en voorkomt botsingen met een draaiende LibreOffice |
| HTML → PDF met CSS | Chrome/Edge `--headless --print-to-pdf --no-pdf-header-footer`, browser van de gebruiker | n.v.t. | Headless-shell maakte de PDF in 0,6 s. Volledige Chrome bleef in de sandbox hangen (omgevingsprobleem), dus harde time-out en CI-audit op echte runners |
| SVG → PNG/JPG/… | resvg-CLI, meegeleverd, via `run_tool` | Apache-2.0 OR MIT; 4,3-4,7 MB | Correct, inclusief verloop, transparantie, `.svgz` en relatieve `<image>`. **Een SVG van 200000×200000 laat resvg crashen** (Rust-abort), in-process (resvg-py) neemt dat de hele app mee. Onbekend lettertype: de tekst verdwijnt, alleen een waarschuwing op stderr |
| SVG → PDF (vector) | Typst met `#image("in.svg")` op een pagina van automatisch formaat | (Typst) | Vector-PDF van de juiste maat (240 px wordt 180 pt). Benoemde lettertypes goed; **algemeen `sans-serif` wordt een schreefletter** |
| Afbeelding → SVG (tracing) | vtracer (Python, Rust) in een apart proces | MIT; \~3 MB | Logo in 0,01 s, tekst scherp, verlopen worden vlakke kleuren. **Foto van 4 MP duurt 111 s en levert 60 MB SVG op**; in een apart proces binnen 0,1 s te annuleren |
| 3D onderling | trimesh in een apart proces | MIT; scipy + networkx + lxml \~41 MB (wheels Windows) | Alle 42 paren tussen STL, OBJ, PLY, OFF, GLB, glTF, 3MF werken. Zonder scipy falen OBJ en GLB. OFF alleen per mesh, niet als scene. glTF als één bestand met `embed_buffers=True`. `filetype` herkent geen enkel 3D-formaat (3MF als zip) |

**Waarom niet…**

- **WeasyPrint voor HTML/Markdown naar PDF:** heeft Pango/GTK nodig. Dat meeleveren is op Windows en macOS lastig, terwijl Typst één statische binary is.
- **LibreOffice meeleveren:** maakt de installer honderden MB groter. Gebruikers die Office-naar-PDF nodig hebben, hebben het vaak al; zonder LibreOffice valt de app terug op Pandoc + Typst.
- **resvg-py (in-process):** een kwaadaardige of foute SVG kan de hele app laten crashen.
- **vtracer-CLI:** de laatste binaries zijn van 0.6.4; de Python-wheels (0.6.15) bestaan voor Windows x64 en macOS arm64.
- **potrace:** GPL en alleen zwart-wit.
- **Assimp/FBX:** geen officieel gebouwde binaries voor macOS arm64; FBX is een gesloten formaat.

**Bronnen**

- [Pandoc manual](https://pandoc.org/MANUAL.html): `typst` staat in de lijst geldige `--pdf-engine`-waarden; `--sandbox` beperkt PDF-productie niet.
- [LibreOffice: Starting the software with parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html): `--convert-to`, `--outdir`, `--norestore`, `-env:`, en `soffice.com` voor gebruik vanaf de opdrachtregel op Windows.
- [Chrome Headless command-line reference](https://developer.chrome.com/docs/automation-and-testing/headless-cli): `--print-to-pdf`, `--no-pdf-header-footer`, `--timeout`, voor zowel headless als headless-shell.
- [Chrome Headless mode](https://developer.chrome.com/docs/chromium/headless): de oude headless-modus is sinds Chrome 132 een aparte binary.
- [PyInstaller: Common issues and pitfalls](https://pyinstaller.org/en/v6.9.0/common-issues-and-pitfalls.html): `multiprocessing.freeze_support()` is in een bevroren app op alle platforms verplicht; zonder die aanroep start de app zichzelf eindeloos opnieuw.

## Review: wat kan er misgaan

Na het onderzoek heb ik elke bevinding een tweede keer nagelopen tegen de code en de testuitvoer. Er zijn 26 punten; de laatste kolom zegt in welke stap de fix zit. #25 en #26 vond ik pas bij het uitschrijven van de stappen, door de code uit het plan opnieuw te draaien. Twee punten (#1 en #8) zitten al in de huidige 0.1.0.

**Kritiek: breekt de app of levert stilletjes slechte bestanden**

| # | Wat gaat er mis | Fix | Stap |
| --- | --- | --- | --- |
| 1 | **Al in 0.1.0:** afbeelding → PDF via Pillow slaat elke afbeelding op als JPEG (kwaliteit 75): PNG's worden lossy en JPEG's opnieuw gecomprimeerd | img2pdf: JPEG ongewijzigd, rest als verliesvrije PNG-stream | 9 |
| 2 | Een SVG met enorme afmetingen laat resvg crashen; in-process gaat de hele app mee | resvg als losse binary via `run_tool`; afmetingen vooraf lezen en weigeren boven `max_megapixels` | 16 |
| 3 | Tracing van een foto duurt minuten en is niet te annuleren | vtracer in een apart proces (`run_isolated`), invoer verkleinen tot `trace_max_megapixels` met waarschuwing | 6, 16 |
| 4 | LibreOffice geeft exitcode 0 ook als de conversie mislukt; de gebruiker krijgt dan "Klaar" zonder bestand | Na afloop controleren of de PDF bestaat; de `Error:`-regel van stdout als melding tonen | 13 |
| 5 | Draait LibreOffice al bij de gebruiker, dan kan `soffice` de taak aan die instantie geven of blokkeren | Eigen profielmap per job via `-env:UserInstallation` | 13 |
| 6 | Formaatsleutel `pdf` in drie families en `docx` in twee providers: de huidige registry weigert te starten | Registry met providers en gedeelde formaatdefinities | 3, 4 |
| 7 | Een apart proces starten in de bevroren app zonder `freeze_support()` laat de app zichzelf eindeloos opnieuw starten | `multiprocessing.freeze_support()` als eerste regel van `main()` | 1 |
| 8 | **Al in 0.1.0:** de macOS-runner installeert PySide6 6.12 (wheel vereist macOS 14), terwijl `Info.plist` 12.0 belooft; pikepdf en scipy vereisen ook 14 | `LSMinimumSystemVersion` 14.0 en README | 20, 24 |
| 25 | Pandoc's eigen PDF-route (-t pdf --pdf-engine=typst) schrijft afbeeldingen als absoluut tijdelijk pad, dat Typst relatief aan de werkmap leest: elke Markdown met een afbeelding faalt in de app | Twee stappen: Pandoc maakt Typst-bron met --extract-media=media in de jobmap, daarna Typst met --root op de jobmap | 12 |

**Belangrijk: verkeerd resultaat of verwarrende melding**

| # | Wat gaat er mis | Fix | Stap |
| --- | --- | --- | --- |
| 9 | resvg laat tekst weg als een lettertype ontbreekt (alleen een stderr-waarschuwing) | `No match for '...' font-family` uit stderr omzetten in `ctx.warn` met de lettertypenaam | 16 |
| 10 | Typst tekent `sans-serif` in een SVG als schreefletter | Bij SVG → PDF waarschuwen als de SVG alleen algemene families noemt | 16 |
| 11 | HTML → PDF via Pandoc verliest alle CSS | Browserroute heeft voorrang; terugval toont waarschuwing | 12, 14 |
| 12 | Word → PDF via Pandoc verliest de Word-lay-out | LibreOffice heeft voorrang; terugval toont "installeer LibreOffice" | 12, 13 |
| 13 | Een met wachtwoord beveiligde `.docx` herkent `filetype` als PowerPoint (OLE-container) | OLE-MIME's zijn "zwak": de extensie wint; LibreOffice-fout vertalen naar "beschadigd of met wachtwoord beveiligd" | 4, 13 |
| 14 | `doc.odt` en `doc.rtf` geven allebei `doc.pdf`; spaties en accenten in namen | Invoer als `input<ext>` naar de jobmap kopiëren; uitvoernaam is dan altijd `input.pdf` | 13 |
| 15 | Headless browser haakt in op de lopende Chrome van de gebruiker of blijft hangen | Eigen `--user-data-dir` per job, `--timeout` voor de pagina, procestime-out daarboven | 14 |
| 16 | 3D: glTF is Y-boven en in meters, STL/3MF meestal Z-boven in mm; meerdere objecten passen niet in STL/PLY/OFF; OBJ met texturen wordt meerdere bestanden | Verlieswaarschuwingen; scene samenvoegen; OBJ zonder texturen; glTF met ingebedde buffers | 18 |
| 17 | macOS: een nooit geopende, gedownloade LibreOffice kan door Gatekeeper geblokkeerd worden, zodat `soffice` wacht tot de time-out | Time-out-melding wijst op "open LibreOffice één keer zelf"; `office.timeout_seconds` apart en korter | 13 |
| 18 | WebP met alpha laat img2pdf falen | Alles behalve JPEG eerst via Pillow naar PNG (verliesvrij, alpha blijft) | 9 |
| 19 | `fetch_binaries.py` kan alleen `.zip`; Typst voor macOS is `.tar.xz` | `tarfile`-ondersteuning; alleen de genoemde leden worden via `extractfile()` gelezen | 10 |
| 26 | Typst faalt hard bij een SVG die naar een losse afbeelding verwijst, en leest geen .svgz | .svgz eerst uitpakken; bij gekoppelde afbeeldingen terugvallen op een PDF als afbeelding (resvg + img2pdf), met waarschuwing | 16 |

**Bekend en geaccepteerd**

| # | Punt | Aanpak |
| --- | --- | --- |
| 20 | resvg-archieven bevatten geen licentietekst | Teksten in `packaging/licenses/` in de repo (stap 21) |
| 21 | Installer groeit: Typst \~50 MB, scipy en co \~40 MB, resvg \~5 MB, pikepdf \~10 MB | Accepteren; vermelden in de README (stap 24) |
| 22 | Pandoc haalt externe afbeeldingen (`https://`) op, al sinds 0.1.0 bij HTML | Documenteren in de README (stap 24); `--sandbox` zou ook lokale afbeeldingen blokkeren |
| 23 | Een GIF met honderden frames geeft een PDF met honderden pagina's | Geaccepteerd; de bestandslimiet `max_input_mb` blijft gelden |
| 24 | Chinese tekens en emoji in Typst-PDF's hangen af van systeemlettertypes | Windows en macOS hebben die standaard; in de sandbox getest met IPAGothic |

## Architectuur en bouwvolgorde

De UI, CLI en `JobRunner` blijven zoals ze zijn. Alleen de registry verandert: per familie houdt hij een geordende lijst **providers** bij, en `find()` kiest de eerste beschikbare provider die het paar aanbiedt. Een provider die niet beschikbaar is (bijv. geen LibreOffice), blijft wel bekend voor detectie, zodat de UI kan zeggen wat er ontbreekt.

&#91;embedded content: providers per familie · voorrang en waar ze draaien\]

Alleen Image (Pillow, img2pdf) en Data (pandas) draaien nog in het app-proces. Alles wat kan crashen of minutenlang kan rekenen, draait in een eigen proces dat de app kan stoppen.

**Providers per familie, in volgorde van voorrang**

| Familie | Provider (bestand) | Bron → doel | Engine | Draait |
| --- | --- | --- | --- | --- |
| Afbeelding | `ImageConverter` (`image.py`) | raster → raster, raster → PDF | Pillow, img2pdf | in-process |
| Afbeelding | `VectorConverter` (`vector.py`) | SVG → raster/PDF, raster → SVG | resvg, Typst, vtracer | binary / binary / apart proces |
| Data | `DataConverter` (`data.py`) | ongewijzigd | pandas | in-process |
| Data | `OfficeSheetConverter` (`office.py`) | XLSX, XLS, ODS → PDF | LibreOffice | geïnstalleerde app |
| Document | `OfficeDocumentConverter` (`office.py`) | DOCX, DOC, ODT, RTF, PPTX, PPT, ODP → PDF | LibreOffice | geïnstalleerde app |
| Document | `BrowserPdfConverter` (`browser.py`) | HTML → PDF | Chrome / Edge / Chromium | geïnstalleerde app |
| Document | `DocumentConverter` (`document.py`) | ongewijzigd + MD, HTML, TEX, EPUB, DOCX, ODT, RTF → PDF | Pandoc + Typst | binary |
| Audio/video | `MediaConverter` | ongewijzigd | ffmpeg | binary |
| 3D-model (nieuw) | `Model3DConverter` (`model3d.py`) | STL, OBJ, PLY, OFF, GLB, glTF, 3MF onderling | trimesh | apart proces |

Bij "Document" staat Pandoc bewust achteraan: hij kan DOCX en HTML wel naar PDF zetten, maar zonder de originele opmaak. Hij is dus alleen de terugval als LibreOffice of een browser ontbreekt, en zegt dat dan in de verlieshint.

**Opties per provider.** Elke provider heeft een `options_key` (de sectie onder `defaults` in `config.json`). Providers in dezelfde familie mogen een sectie delen als ze hetzelfde optiemodel gebruiken: `VectorConverter` gebruikt `ImageOptions`, zodat `jpeg_quality` ook geldt voor SVG → JPG. Nieuwe secties: `office` en `browser` (alleen een time-out). 3D heeft geen opties.

**Bouwvolgorde.** Elke fase eindigt groen in CI en is los uit te brengen. De tijden zijn richtwaarden bij bouwen met Claude Code.

1. **Fase 0, fundament** (stap 1-7, \~2,5 uur): registry met providers, `run_isolated`, app-detectie, `freeze_support`. Geen nieuwe conversies; alle bestaande tests blijven groen.
2. **Fase 1, PDF uit afbeeldingen en tekst** (stap 8-12, \~2,5 uur): img2pdf, Typst, ADR-002. **Snijlijn 1:** dit is al een zinvolle 0.2.0 en lost review #1 en #8 op.
3. **Fase 2, Office en browser naar PDF** (stap 13-15, \~2,5 uur). Begin met de twee CI-audits (LibreOffice op Windows, browser op beide OS'en).
4. **Fase 3, vector** (stap 16-17, \~2 uur).
5. **Fase 4, 3D** (stap 18-19, \~1,5 uur). **Snijlijn 2:** vector of 3D kan naar 0.3 als de nacht te kort is; er hoeft dan niets in de code te veranderen.
6. **Fase 5, packaging en release** (stap 20-25, \~2 uur, vooral wachten op CI).

De tests van een fase (stap 26-29) worden in die fase geschreven, niet aan het eind.

## Fase 0: fundament

Na deze fase draaien alle 0.1.0-conversies ongewijzigd, maar kan een familie meerdere providers hebben, kan een conversie in een apart proces draaien, en weet de app of LibreOffice of een Chromium-browser geïnstalleerd is.

### Stap 1 — Edit `src/uniconv/__main__.py`

**Why:** zodra stap 6 een proces start, start de bevroren app zichzelf als kindproces. Zonder `freeze_support()` voert dat kind gewoon `main()` uit, opent het een tweede venster en start het weer een kind (review #7). Het moet vóór het lezen van argumenten gebeuren, omdat het kind speciale argumenten meekrijgt.

```python
# BEFORE
def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m uniconv`, the console script and the PyInstaller build."""
    argv = sys.argv[1:] if argv is None else argv

# AFTER
def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m uniconv`, the console script and the PyInstaller build."""
    # NOTE: must be first. In the frozen app a worker process re-enters here and is diverted
    # by this call; without it the app spawns itself forever (review #7).
    multiprocessing.freeze_support()
    argv = sys.argv[1:] if argv is None else argv
```

Plus `import multiprocessing` bovenaan. Buiten een bevroren app doet de aanroep niets.

### Stap 2 — Edit `src/uniconv/core/converter.py`

**Why:** een provider moet kunnen zeggen welke configsectie hij gebruikt (zodat twee providers in een familie elkaars sleutels niet afkeuren) en wat de gebruiker moet installeren als hij niet beschikbaar is.

```python
# AFTER (additions only)
class NoOptions(BaseModel):
    """For providers without settings; still validated, so typos in config.json are caught."""
    model_config = ConfigDict(extra="forbid")


class Converter(ABC):
    family: ClassVar[str]
    family_label: ClassVar[str]
    formats: ClassVar[tuple[Format, ...]]
    Options: ClassVar[type[BaseModel]]
    options_key: ClassVar[str | None] = None   # section under "defaults"; None = family
    install_hint: ClassVar[str | None] = None  # shown when available() is False

    def config_section(self) -> str:
        return self.options_key or self.family
    # ... available(), sources(), targets(), expected_losses(), convert() unchanged
```

### Stap 3 — Create `src/uniconv/converters/formats.py`

**Why:** PDF, DOCX, XLSX en de rasterformaten worden straks door meer dan één provider genoemd. De registry eist dat elke sleutel overal exact dezelfde definitie heeft. Dat lukt alleen als er één plek is waar die definities staan (review #6).

**What changes:** de `Format(...)`-regels die nu in `image.py`, `data.py` en `document.py` staan, verhuizen hierheen als constanten; die drie bestanden importeren ze. Formaten die maar één provider kent (media, 3D, CSV/JSON/YAML/TOML/XML, MD/TEX/EPUB/TXT) mogen in hun eigen bestand blijven, maar voor de eenvoud staan alle document- en dataformaten hier.

```python
"""Format definitions shared by more than one provider. The registry requires that a key
has exactly one definition, so providers import these instead of declaring their own."""

from uniconv.core.converter import Format

# raster images (Pillow) and vector
JPG = Format("jpg", "JPEG", (".jpg", ".jpeg"), ("image/jpeg",))
PNG = Format("png", "PNG", (".png",), ("image/png",))
# ... WEBP, GIF, BMP, TIFF exactly as in image.py today
HEIC = Format("heic", "HEIC", (".heic", ".heif"), ("image/heic", "image/heif"), target=False)
SVG = Format("svg", "SVG", (".svg", ".svgz"))  # text/XML: detected by extension
PDF = Format("pdf", "PDF", (".pdf",), ("application/pdf",), source=False)

# spreadsheets
XLSX = Format("xlsx", "Excel", (".xlsx",),
              ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",))
XLS = Format("xls", "Excel 97-2003", (".xls",), ("application/vnd.ms-excel",), target=False)
ODS = Format("ods", "OpenDocument-rekenblad", (".ods",),
             ("application/vnd.oasis.opendocument.spreadsheet",), target=False)

# text documents and presentations
DOCX = Format("docx", "Word", (".docx",),
              ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",))
DOC = Format("doc", "Word 97-2003", (".doc",), ("application/msword",), target=False)
PPTX = Format("pptx", "PowerPoint", (".pptx",),
              ("application/vnd.openxmlformats-officedocument.presentationml.presentation",),
              target=False)
PPT = Format("ppt", "PowerPoint 97-2003", (".ppt",), ("application/vnd.ms-powerpoint",),
             target=False)
ODP = Format("odp", "OpenDocument-presentatie", (".odp",),
             ("application/vnd.oasis.opendocument.presentation",), target=False)
# ... HTML, ODT, RTF, MD, TEX, EPUB, TXT exactly as in document.py today
```

De MIME-strings van XLS, ODS, DOC, PPT, PPTX en ODP zijn in de sandbox gecontroleerd met `filetype` 1.2.0. De nieuwe formaten zijn bewust alleen bron: ze naar PPTX of XLS schrijven valt buiten deze uitbreiding.

### Stap 4 — Rewrite `src/uniconv/core/registry.py`

**Why:** dit is de enige echte architectuurwijziging. Per familie komt er een geordende lijst providers; formaten zijn gedeeld; een bronformaat hoort nog steeds bij precies één familie (anders weet detectie niet waar een bestand thuishoort). Niet-beschikbare providers blijven geregistreerd voor detectie en hints, maar bieden geen doelen aan.

```python
_WEAK_MIMES = frozenset({
    # Containers whose MIME says little: a password-protected .docx is an OLE file that
    # filetype reports as PowerPoint (review #13); 3MF is a plain zip. The extension wins.
    "application/zip", "application/msword", "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
})


class Registry:
    def __init__(self) -> None:
        self._providers: dict[str, list[tuple[Converter, bool]]] = {}  # family -> (conv, available)
        self._formats: dict[str, Format] = {}       # key -> the single shared definition
        self._source_family: dict[str, str] = {}    # source key -> its family
        self._options: dict[str, type[BaseModel]] = {}  # config section -> Options class

    def register(self, conv: Converter) -> None:
        """Order matters: earlier providers win when two offer the same pair."""
        provs = self._providers.setdefault(conv.family, [])
        if provs and provs[0][0].family_label != conv.family_label:
            raise ValueError(f"family {conv.family!r} has two labels")
        for f in conv.formats:
            if f.key in self._formats and self._formats[f.key] != f:
                raise ValueError(f"format {f.key!r} has two definitions; use converters/formats.py")
        for key in conv.sources():
            if self._source_family.get(key, conv.family) != conv.family:
                raise ValueError(f"source format {key!r} claimed by two families")
        section = conv.config_section()
        if self._options.get(section, conv.Options) is not conv.Options:
            raise ValueError(f"config section {section!r} used with two Options models")
        # all checks passed: only now mutate, so a failed register() leaves no trace
        self._formats.update({f.key: f for f in conv.formats})
        self._source_family.update({k: conv.family for k in conv.sources()})
        self._options[section] = conv.Options
        provs.append((conv, conv.available()))  # available() is evaluated once, at start-up

    def _live(self, family: str) -> list[Converter]:
        return [c for c, ok in self._providers.get(family, []) if ok]

    def families(self) -> list[tuple[str, str]]:
        return [(fam, p[0][0].family_label) for fam, p in self._providers.items() if self._live(fam)]

    def providers(self, family: str) -> list[Converter]:
        return self._live(family)

    def sources(self, family: str) -> list[str]:
        """All readable keys, also those whose provider is missing (so a hint can be shown)."""
        return list(dict.fromkeys(k for c, _ in self._providers.get(family, []) for k in c.sources()))

    def extensions(self, family: str) -> list[str]:
        return [e for k in self.sources(family) for e in self._formats[k].extensions]

    def targets(self, family: str, source: str) -> list[str]:
        return list(dict.fromkeys(
            t for c in self._live(family) if source in c.sources() for t in c.targets(source)))

    def find(self, family: str, source: str, target: str) -> Converter:
        for c in self._live(family):
            if source in c.sources() and target in c.targets(source):
                return c
        raise UnsupportedConversionError(f"{source.upper()} naar {target.upper()} wordt niet ondersteund")

    def hints(self, family: str, source: str) -> list[str]:
        """What to install to get more targets for this source, e.g. LibreOffice."""
        return list(dict.fromkeys(
            c.install_hint for c, ok in self._providers.get(family, [])
            if not ok and c.install_hint and source in c.sources()))

    def options_for(self, conv: Converter, cfg: AppConfig) -> BaseModel:
        section = conv.config_section()
        try:
            return conv.Options.model_validate(cfg.defaults.get(section, {}))
        except ValidationError as exc:
            loc = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise ConversionError(f"Ongeldige instelling defaults.{section}.{loc} in config.json") from exc

    def default_options(self) -> dict[str, dict]:
        return {s: o().model_dump(mode="json") for s, o in self._options.items()}
```

`format(key)` blijft zoals het is, maar leest uit `self._formats`. `detect()` krijgt twee wijzigingen; de rest (foutmeldingen, `OSError`-afhandeling) blijft gelijk:

```python
    def detect(self, path: Path, family: str) -> Format:
        # ... filetype.guess with the existing OSError handling ...
        ext = path.suffix.lower()
        by_ext = next((f for f in self._formats.values() if ext in f.extensions), None)
        fmt = None
        if kind is not None:
            matches = [f for f in self._formats.values() if kind.mime in f.mimes]
            fmt = next((f for f in matches if ext in f.extensions), None)
            if fmt is None and matches and not (kind.mime in _WEAK_MIMES and by_ext):
                fmt = matches[0]
        fmt = fmt or by_ext
        if fmt is None:
            raise UnsupportedFormatError(f"Onbekend bestandstype: {path.name}")
        fam = self._source_family.get(fmt.key)
        if fam is None:  # PDF: a target in three families, a source in none
            raise UnsupportedConversionError(f"{fmt.label} kan in deze versie alleen als doel")
        if fam != family:
            label = self._providers[fam][0][0].family_label
            raise WrongFamilyError(f"{path.name} is een {fmt.label}-bestand. Kies '{label}'.")
        return fmt
```

`converter(family)` vervalt; aanroepers gebruiken `sources()`, `providers()` of `find()` (stap 5). `build_default_registry()` registreert voortaan **alle** providers, zonder `if conv.available()`; de volgorde staat in stap 15, 17 en 19.

### Stap 5 — Edit `core/jobs.py`, `cli.py`, `ui/main_window.py` en `ui/app.py`

**Why:** dit zijn de vier plekken die de oude registry-API gebruiken. De opties moeten nu van de gekozen provider komen, en de UI moet hints kunnen tonen.

```python
# core/jobs.py, in _run_one
# BEFORE
            conv = self.registry.find(job.family, source.key, target.key)
            ...
                options=self.registry.options_for(job.family, self.cfg),
# AFTER
            conv = self.registry.find(job.family, source.key, target.key)
            ...
                options=self.registry.options_for(conv, self.cfg),
```

```python
# cli.py, `formats` subcommand
# BEFORE
        conv = registry.converter(family)
        for src in conv.sources():
            print(f"  {src:6} -> {', '.join(conv.targets(src))}")
# AFTER
        for src in registry.sources(family):
            targets = registry.targets(family, src)
            hint = "; ".join(registry.hints(family, src))
            print(f"  {src:6} -> {', '.join(targets) or '-'}" + (f"   ({hint})" if hint else ""))
```

```python
# ui/main_window.py, _update_loss_hint (line ~191)
# BEFORE
            conv = self.registry.converter(self._family)
# AFTER
            conv = self.registry.find(self._family, self._source[1].key, target)  # the provider that will run
```

In `_on_file_chosen` komt na het vullen van de dropdown: als er geen doelen zijn, toont de statusregel `registry.hints(...)` (bijv. "Installeer LibreOffice (gratis) om PowerPoint te converteren"); als er wel doelen zijn en ook hints, komt de hint grijs onder de verlieshint.

```python
# ui/app.py
# BEFORE
    for family, _label in registry.families():
        try:
            registry.options_for(family, cfg)
# AFTER
    for family, _label in registry.families():
        for conv in registry.providers(family):
            try:
                registry.options_for(conv, cfg)
```

De `problems`-lijst wordt per configsectie ontdubbeld, zodat een fout in `defaults.image` maar één keer gemeld wordt.

### Stap 6 — Create `src/uniconv/core/isolate.py`

**Why:** vtracer en trimesh draaien in Python-code, dus `run_tool` werkt niet. In het app-proces kunnen ze niet geannuleerd worden, geen time-out krijgen, en een geheugenfout neemt de app mee. Een apart proces lost alle drie op (review #3). In de sandbox stopte `kill()` een tracing binnen 0,1 s.

```python
"""Run a module-level Python function in a separate process: crash-proof, cancellable,
with a time-out. For in-process engines that can run long or abort (vtracer, trimesh)."""

import multiprocessing as mp
import time
from collections.abc import Callable
from typing import Any

from uniconv.core.converter import CancelToken
from uniconv.core.errors import ConversionCancelled, ConversionError, UniconvError

# spawn everywhere: never fork a process that holds Qt state; same behaviour on all OSes
_CTX = mp.get_context("spawn")


def _child(fn: Callable[..., Any], args: tuple, conn) -> None:
    try:
        conn.send(("ok", fn(*args)))
    except UniconvError as exc:          # expected failure: keep the user message
        conn.send(("user", str(exc)))
    except BaseException as exc:         # engine bug, MemoryError, ...
        conn.send(("bug", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def run_isolated(fn: Callable[..., Any], *args: Any, timeout_s: int, cancel: CancelToken) -> Any:
    """Return fn(*args) from a child process. fn must be importable by name and never import Qt."""
    recv, send = _CTX.Pipe(duplex=False)
    proc = _CTX.Process(target=_child, args=(fn, args, send), daemon=True)
    proc.start()
    send.close()
    deadline = time.monotonic() + timeout_s
    try:
        while not recv.poll(0.1):
            # poll again after is_alive(): the child may have answered and exited in between
            if not proc.is_alive() and not recv.poll(0):
                raise ConversionError(
                    "De conversie is onverwacht gestopt; het bestand is te groot of beschadigd")
            if cancel.cancelled:
                raise ConversionCancelled("Conversie geannuleerd")
            if time.monotonic() > deadline:
                raise ConversionError(f"Conversie duurde langer dan {timeout_s} s en is gestopt")
        kind, value = recv.recv()
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        recv.close()
    if kind == "user":
        raise ConversionError(value)
    if kind == "bug":
        raise ConversionError(f"Onverwachte fout: {value}")
    return value
```

Het kind schrijft zijn resultaat zelf naar `ctx.output_path` in de jobmap. Bij annuleren of een crash ruimt de runner die map al op, dus een half bestand komt nooit bij de gebruiker. Het kind geeft alleen kleine waarden terug (een lijst waarschuwingen), want alles gaat door een pipe.

### Stap 7 — Create `src/uniconv/core/apps.py`

**Why:** LibreOffice en browsers leveren we niet mee, maar we moeten ze vinden. Dat is iets anders dan `find_tool()` (meegeleverde binaries), dus een eigen module, met dezelfde caching. Een omgevingsvariabele per app maakt ongewone installaties en tests mogelijk.

```python
"""Find applications the user installed (never bundled): LibreOffice and a Chromium browser."""

import os
import shutil
import sys
from functools import cache
from pathlib import Path


def _win(*parts: str) -> list[Path]:
    roots = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    return [Path(r, *parts) for r in roots if r]


def _candidates(app: str) -> list[Path]:
    home = Path.home()
    if app == "libreoffice":
        if sys.platform == "win32":  # soffice.com waits and prints to stdout; .exe as fallback
            return _win("LibreOffice", "program", "soffice.com") + _win("LibreOffice", "program", "soffice.exe")
        if sys.platform == "darwin":
            return [Path(d, "LibreOffice.app/Contents/MacOS/soffice") for d in ("/Applications", home / "Applications")]
    if app == "browser":
        if sys.platform == "win32":
            return (_win("Google", "Chrome", "Application", "chrome.exe")
                    + _win("Microsoft", "Edge", "Application", "msedge.exe"))
        if sys.platform == "darwin":
            return [Path(d, a) for d in ("/Applications", home / "Applications") for a in (
                "Google Chrome.app/Contents/MacOS/Google Chrome",
                "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Chromium.app/Contents/MacOS/Chromium")]
    return []


_ON_PATH = {"libreoffice": ("soffice", "libreoffice"),
            "browser": ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")}


@cache
def find_app(app: str) -> Path | None:
    """UNICONV_<APP> env var first, then the usual install locations, then PATH."""
    override = os.environ.get(f"UNICONV_{app.upper()}")
    if override and Path(override).is_file():
        return Path(override)
    for p in _candidates(app):
        if p.is_file():
            return p
    for name in _ON_PATH.get(app, ()):
        if found := shutil.which(name):
            return Path(found)
    return None
```

**Let op:** `available()` wordt één keer bij het opstarten bepaald. Installeert de gebruiker LibreOffice terwijl UniConv open staat, dan is een herstart nodig; dat staat in de hint ("… en start UniConv opnieuw").

**Audit:** controleer op de CI-runners dat `find_app("browser")` Chrome of Edge vindt (Windows: beide voorgeïnstalleerd; macOS: Chrome) en, in de LibreOffice-job van stap 22, dat `find_app("libreoffice")` op Windows `soffice.com` vindt.

## Fase 1: PDF uit afbeeldingen en tekst

Na deze fase geeft afbeelding → PDF een verliesvrije PDF (ook met meerdere pagina's), en zet de Document-familie Markdown, HTML, LaTeX, EPUB, Word, ODT en RTF om naar A4-PDF via Typst.

### Stap 8 — Edit `pyproject.toml` en `src/uniconv/__init__.py`

**Why:** alle nieuwe Python-afhankelijkheden van de hele uitbreiding in één keer, zodat de CI-cache maar één keer opnieuw opgebouwd wordt. De ondergrenzen zijn de versies die in de sandbox getest zijn.

```toml
# BEFORE
version = "0.1.0"
...
  "pydantic>=2.7",
]
...
dev = ["pytest>=8", "pytest-qt>=4.4", "ruff>=0.6"]

# AFTER
version = "0.2.0"
...
  "pydantic>=2.7",
  "img2pdf>=0.6.3",     # lossless image -> PDF; pulls in pikepdf (MPL-2.0)
  "vtracer>=0.6.15",    # raster -> SVG tracing
  "trimesh>=5.2",       # 3D formats
  "scipy>=1.13",        # trimesh needs it for OBJ/GLB normals
  "networkx>=3.3",      # trimesh: 3MF and scene graphs
  "lxml>=5.2",          # trimesh: 3MF
]
...
dev = ["pytest>=8", "pytest-qt>=4.4", "ruff>=0.6",
       "pypdfium2>=5.9",          # render PDFs in tests to check pixels
       "msoffcrypto-tool>=5.4"]   # make a password-protected .docx in tests
```

In `src/uniconv/__init__.py` wordt `__version__` ook `"0.2.0"`; de release-workflow controleert dat beide gelijk zijn aan de tag.

### Stap 9 — Edit `src/uniconv/converters/image.py`

**Why:** Pillow schrijft elke afbeelding in een PDF als JPEG op kwaliteit 75. Een PNG met tekst wordt daardoor wazig en een JPEG verliest een tweede keer kwaliteit (review #1). img2pdf bedt JPEG byte voor byte in en al het andere als verliesvrije stream; in de sandbox was de pixelfout 0,00 tegen 0,12. img2pdf weigert wel WebP met alpha (review #18). Daarom gaat alles behalve JPEG eerst via Pillow naar PNG, met behoud van alpha.

**What changes:** `convert()` stuurt het doel `pdf` naar een nieuwe `_to_pdf()`. Elk frame of elke pagina van de bron wordt een PDF-pagina; voor alle andere doelen blijft "alleen het eerste frame" gelden. De formaten komen uit `converters/formats.py` (stap 3).

```python
import io
from collections.abc import Iterator

import img2pdf
from PIL import ImageSequence


    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "pdf":
            self._to_pdf(ctx)  # lossless, multi-page (review #1)
            return
        # ... existing raster path unchanged ...

    def _to_pdf(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        _check_size(ctx.input_path, opts)  # the existing max_megapixels check, factored out
        if ctx.source.key == "jpg":
            pages = [ctx.input_path.read_bytes()]  # embedded as-is: no second JPEG generation
        else:
            pages = list(_frames_as_png(ctx, opts))  # PNG keeps alpha; img2pdf adds a soft mask
        layout = img2pdf.get_fixed_dpi_layout_fun((opts.pdf_dpi, opts.pdf_dpi))
        try:
            data = img2pdf.convert(pages, layout_fun=layout,
                                   rotation=img2pdf.Rotation.ifvalid)  # honours EXIF rotation
        except Exception as exc:  # img2pdf raises plain ValueError/its own types
            raise ConversionError(f"Kan geen PDF maken: {exc}") from exc
        ctx.output_path.write_bytes(data)


def _frames_as_png(ctx: ConversionContext, opts: ImageOptions) -> Iterator[bytes]:
    """Every frame/page as a lossless PNG; CMYK and 16-bit are normalised as for PNG output."""
    try:
        with Image.open(ctx.input_path) as im:
            for frame in ImageSequence.Iterator(im):
                ctx.cancel.raise_if_cancelled()
                img = _normalize_mode(ImageOps.exif_transpose(frame), "png", opts.flatten_background)
                buf = io.BytesIO()
                img.save(buf, format="PNG", compress_level=opts.png_compress_level)
                yield buf.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc
```

`expected_losses()` verliest de transparantie-melding voor PDF (img2pdf bewaart alpha). De melding blijft voor JPG en BMP. De één-frame-waarschuwing in het rasterpad slaat PDF over.

**Getest in de sandbox:** JPEG byte-identiek; PNG met alpha; GIF- en WebP-animatie en TIFF met 3 pagina's geven 3 pagina's; HEIC, CMYK-JPEG en 16-bit PNG werken; EXIF-oriëntatie 6 levert een staande pagina op.

### Stap 10 — Edit `scripts/fetch_binaries.py`

**Why:** Typst en resvg worden meegeleverd zoals Pandoc en ffmpeg: gepinde URL, SHA-256 en een vast pad in het archief. Typst voor macOS komt als `.tar.xz`, en het script kan nu alleen `.zip` (review #19).

**What changes:** twee versieconstanten, vier archieven, een tijdelijke bestandsnaam met de echte extensie, en `extract()` die ook tar-archieven leest. Alleen de genoemde leden worden via `extractfile()` gelezen, dus een kwaadaardig archief kan geen bestanden buiten `vendor/` schrijven.

```python
TYPST = "0.15.1"
RESVG = "0.49.0"
_TYPST = f"https://github.com/typst/typst/releases/download/v{TYPST}"
_RESVG = f"https://github.com/linebender/resvg/releases/download/v{RESVG}"

# appended to MANIFEST["win32-x86_64"]
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
            {"resvg.exe": "resvg.exe"},   # no license file inside: see step 21
        ),
# appended to MANIFEST["darwin-arm64"]
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
```

```python
def extract(archive: Path, member: str, dest: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf, zf.open(member) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
    else:  # .tar.xz / .tar.gz: read the named member only, never extractall()
        with tarfile.open(archive) as tf:
            src = tf.extractfile(member)
            if src is None:
                raise SystemExit(f"{member} in {archive.name} is not a regular file")
            with src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
    if sys.platform != "win32":
        dest.chmod(0o755)
```

In `fetch()` wordt `zip_path = Path(tmp) / f"{i}.zip"` vervangen door `Path(tmp) / f"{i}-{archive.url.rsplit('/', 1)[-1]}"`, zodat `extract()` het type aan de naam ziet. De hashes en de paden in de archieven zijn op 3 november 2026 gedownload en gecontroleerd. Omdat het script verandert, verandert ook de CI-cachesleutel (`hashFiles('scripts/fetch_binaries.py')`), dus `vendor/` wordt vanzelf opnieuw opgehaald.

### Stap 11 — Create `.claude/decisions/ADR-002-typst-resvg-and-detected-apps.md`

**Why:** ADR-001 legt vast waar meegeleverde binaries vandaan komen. Deze uitbreiding voegt twee binaries toe en introduceert iets nieuws: apps die we niet meeleveren maar wel gebruiken. Die keuze moet een volgende sessie kunnen terugvinden.

**What changes:** een ADR in het bestaande sjabloon met:

- **Decision:** de tabel uit stap 10 (Typst 0.15.1, resvg 0.49.0, URL's, SHA-256, paden) en de regel "LibreOffice en Chromium-browsers worden gedetecteerd (`core/apps.py`), nooit meegeleverd; zonder die apps valt de app terug op Pandoc + Typst of biedt hij het paar niet aan".
- **Rationale:** Typst en resvg zijn statische binaries van 45-52 MB en 4-5 MB met permissieve licenties. LibreOffice zou de installer honderden MB groter maken.
- **Alternatives considered:** WeasyPrint (Pango/GTK meeleveren), LaTeX (honderden MB), resvg-py in-process (crasht de app bij een te grote SVG), LibreOffice meeleveren.
- **Consequences:** CI controleert met `otool -L` ook `typst` en `resvg` (stap 22); providers met een geïnstalleerde app krijgen een `install_hint`.

### Stap 12 — Edit `src/uniconv/core/tools.py` en `src/uniconv/converters/document.py`

**Why:** `pandoc -t pdf --pdf-engine=typst` lijkt de voor de hand liggende route, maar faalt in de app. Pandoc kopieert afbeeldingen naar een eigen tijdelijke map en schrijft die als absoluut pad (`/tmp/media-…/pic.png`) in de Typst-bron. Typst leest een pad dat met `/` begint als relatief aan zijn projectroot, en dat is de huidige werkmap. Elke Markdown met een afbeelding mislukt dan, tenzij de werkmap toevallig `/` is. In de sandbox gebeurde precies dat.

De oplossing zijn twee stappen die wij zelf aansturen:

1. Pandoc schrijft **Typst-bron** (`-s -t typst`) met `--extract-media=media`, met als werkmap de jobmap. Afbeeldingen komen dan als `media/…` in de jobmap.
2. Typst compileert met `--root <jobmap>`. Dat werkt op elk OS, en Typst kan daardoor ook niets buiten de jobmap lezen.

In de sandbox werkte dit voor MD, HTML, TEX, EPUB, DOCX en ODT, ook met `../`- en absolute afbeeldingspaden en met een Typst-pad met spaties.

```python
# core/tools.py: run_tool gets an optional working directory
# BEFORE
def run_tool(cmd: list[str], *, timeout_s: int, cancel: CancelToken,
             on_stdout_line: Callable[[str], None] | None = None) -> str:
    ...
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL, ...
# AFTER
def run_tool(cmd: list[str], *, timeout_s: int, cancel: CancelToken,
             on_stdout_line: Callable[[str], None] | None = None,
             cwd: Path | None = None) -> str:
    ...
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL, ...
```

```python
# converters/document.py
class DocumentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    standalone: bool = True
    embed_resources: bool = True
    pdf_papersize: Literal["a4", "a5", "us-letter"] = "a4"
    pdf_lang: str = Field("nl", pattern=r"^[a-z]{2}$")  # captions: "Figuur 1", hyphenation


_PDF_SOURCES = {"md", "html", "tex", "epub", "docx", "odt", "rtf"}
_LAYOUT_LOST = {"docx", "odt", "rtf"}


class DocumentConverter(Converter):
    # formats: the existing ones (now from converters/formats.py) plus formats.PDF

    def targets(self, source: str) -> list[str]:
        keys = super().targets(source)
        if source not in _PDF_SOURCES or find_tool("typst") is None:
            keys = [k for k in keys if k != "pdf"]
        return keys

    def expected_losses(self, source: str, target: str) -> list[str]:
        if target == "pdf":  # only reached when the better provider is missing (review #11, #12)
            if source == "html":
                return ["Opmaak uit CSS gaat verloren. Met Chrome of Edge geïnstalleerd "
                        "lijkt de PDF op de webpagina."]
            if source in _LAYOUT_LOST:
                return ["De lay-out van het origineel gaat verloren. Installeer LibreOffice "
                        "(gratis) voor een getrouwe PDF."]
            return []
        return ...  # existing rules unchanged

    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "pdf":
            self._to_pdf(ctx)
            return
        # ... existing Pandoc path unchanged ...

    def _to_pdf(self, ctx: ConversionContext) -> None:
        opts: DocumentOptions = ctx.options  # type: ignore[assignment]
        pandoc, typst = find_tool("pandoc"), find_tool("typst")
        if pandoc is None or typst is None:
            raise ToolMissingError("Pandoc of Typst is niet gevonden; herinstalleer UniConv")
        work = ctx.output_path.parent  # the job's own directory
        source = work / "main.typ"
        # Step 1: Pandoc -> Typst source. cwd=work makes --extract-media write RELATIVE paths;
        # Pandoc's own `-t pdf` uses absolute temp paths that Typst cannot resolve.
        run_tool([str(pandoc), "-s", "-f", _PANDOC[ctx.source.key], "-t", "typst",
                  "--extract-media=media", f"--resource-path={ctx.input_path.parent}",
                  "-V", f"papersize={opts.pdf_papersize}", "-V", f"lang={opts.pdf_lang}",
                  "-o", str(source), "--", str(ctx.input_path)],
                 timeout_s=ctx.timeout_s, cancel=ctx.cancel, cwd=work)
        # Step 2: Typst -> PDF. --root confines Typst to the job directory.
        run_tool([str(typst), "compile", "--root", str(work), str(source), str(ctx.output_path)],
                 timeout_s=ctx.timeout_s, cancel=ctx.cancel)
```

Pandoc vervangt een afbeelding die niet bestaat door de alt-tekst en geeft een waarschuwing op stderr. Die regel (`[WARNING] Could not fetch resource …`) wordt uit de stderr van stap 1 gehaald en via `ctx.warn` getoond, dus dezelfde aanpak als bij resvg in stap 16.

**Audit:** draai de PDF-tests (stap 28) in CI op Windows. Daar is het enige verschil met de sandbox de padnotatie, en `--extract-media=media` levert relatieve paden met `/` op.

## Fase 2: Office en browser naar PDF

Na deze fase maakt de app van Word, ODT, RTF, PowerPoint en Excel een PDF met de originele opmaak als LibreOffice geïnstalleerd is, en van HTML een PDF zoals de browser hem toont als Chrome of Edge aanwezig is. Zonder die apps blijft Fase 1 de terugval.

**Begin met de twee audits** (stap 13 en 14). Ze bepalen of deze fase doorgaat zoals beschreven; zonder deze fase blijft alles uit Fase 1 werken.

### Stap 13 — Create `src/uniconv/converters/office.py` (en kleine edit in `core/errors.py` + `core/tools.py`)

**Why:** LibreOffice is de enige gratis engine die Word-, PowerPoint- en Excel-opmaak getrouw naar PDF zet. Hij heeft drie verraderlijke eigenschappen, allemaal in de sandbox gezien:

- de exitcode is 0 ook als het mislukt (review #4);
- een draaiende LibreOffice van de gebruiker kan de taak overnemen (review #5);
- de naam van de uitvoer volgt de invoernaam, dus `doc.odt` en `doc.rtf` botsen en vreemde tekens geven problemen (review #14).

**What changes:** twee providers (één voor Document, één voor Data) die dezelfde functie delen. Om een time-out te herkennen krijgt `core/errors.py` een subklasse `ConversionTimeout(ConversionError)`, en `run_tool` gooit die in plaats van een gewone `ConversionError` als de deadline verloopt.

```python
"""Office documents, presentations and spreadsheets to PDF via the user's own LibreOffice.
Never bundled: found by core.apps.find_app("libreoffice")."""

import shutil

from pydantic import BaseModel, ConfigDict, Field

from uniconv.converters import formats as F
from uniconv.core.apps import find_app
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError, ConversionTimeout, ToolMissingError
from uniconv.core.tools import run_tool

_HINT = ("Installeer LibreOffice (gratis, libreoffice.org) en start UniConv opnieuw "
         "voor PDF met de originele opmaak.")


class OfficeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Shorter than limits.timeout_seconds: a LibreOffice that macOS blocks on first start
    # should not keep the user waiting 15 minutes (review #17).
    timeout_seconds: int = Field(180, ge=10, le=3600)


class _OfficeToPdf(Converter):
    Options = OfficeOptions
    options_key = "office"
    install_hint = _HINT

    def available(self) -> bool:
        return find_app("libreoffice") is not None

    def targets(self, source: str) -> list[str]:
        return ["pdf"]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return ["Lettertypen die niet op deze computer staan, worden vervangen door gelijkende."]

    def convert(self, ctx: ConversionContext) -> None:
        _soffice_to_pdf(ctx)


class OfficeDocumentConverter(_OfficeToPdf):
    family = "document"
    family_label = "Document"
    formats = (F.DOCX, F.DOC, F.ODT, F.RTF, F.PPTX, F.PPT, F.ODP, F.PDF)


class OfficeSheetConverter(_OfficeToPdf):
    family = "data"
    family_label = "Data"
    formats = (F.XLSX, F.XLS, F.ODS, F.PDF)

    def expected_losses(self, source: str, target: str) -> list[str]:
        return [*super().expected_losses(source, target),
                "Alle werkbladen komen in de PDF; brede bladen worden over pagina's verdeeld."]


def _soffice_to_pdf(ctx: ConversionContext) -> None:
    opts: OfficeOptions = ctx.options  # type: ignore[assignment]
    soffice = find_app("libreoffice")
    if soffice is None:
        raise ToolMissingError(_HINT)
    work = ctx.output_path.parent
    # Fixed ASCII name: no clashes between doc.odt/doc.rtf, no odd characters (review #14)
    src = work / f"input{ctx.input_path.suffix.lower()}"
    shutil.copyfile(ctx.input_path, src)
    outdir = work / "lo-out"
    cmd = [str(soffice),
           f"-env:UserInstallation={(work / 'lo-profile').as_uri()}",  # own profile (review #5)
           "--headless", "--norestore", "--nologo",
           "--convert-to", "pdf", "--outdir", str(outdir), str(src)]
    try:
        stderr = run_tool(cmd, timeout_s=opts.timeout_seconds, cancel=ctx.cancel)
    except ConversionTimeout as exc:
        raise ConversionError(
            "LibreOffice reageert niet. Open LibreOffice één keer zelf (macOS vraagt dan om "
            "toestemming) en probeer het opnieuw.") from exc
    produced = outdir / "input.pdf"
    if not produced.is_file():  # exit code is 0 even on failure (review #4)
        if "could not be loaded" in stderr:
            raise ConversionError("LibreOffice kan dit bestand niet openen. Het is beschadigd "
                                  "of beveiligd met een wachtwoord.")  # review #13
        line = next((x for x in stderr.splitlines() if x.startswith("Error")), "")
        raise ConversionError("LibreOffice maakte geen PDF" + (f": {line}" if line else ""))
    produced.replace(ctx.output_path)
```

**Getest in de sandbox (LibreOffice 24.2):** DOCX met é in de naam, XLSX met twee werkbladen (3 pagina's), PPTX, ODT, RTF in 0,3-1,2 s. Met een eigen profiel per job kost elke start \~0,5 s extra. Een afgekapte DOCX en een met wachtwoord beveiligde DOCX geven direct "Error: source file could not be loaded" op stderr, met exitcode 0 en zonder uitvoer. Er bleef niets hangen.

**Audit (eerst doen):** in de LibreOffice-CI-job van stap 22 op Windows controleren dat `soffice.com` wacht tot de PDF klaar is, en dat de foutregel op stderr staat. LibreOffice raadt `soffice.com` aan voor gebruik vanaf de opdrachtregel en `soffice.exe` als er geen console nodig is. Wacht `soffice.com` niet, dan moet `_soffice_to_pdf` na afloop tot 10 s pollen op `input.pdf`.

### Stap 14 — Create `src/uniconv/converters/browser.py`

**Why:** Pandoc begrijpt geen CSS, dus een opgeslagen webpagina of HTML-rapport verliest via Typst zijn opmaak (review #11). Een Chromium-browser drukt de pagina af zoals hij op het scherm staat. Edge staat op elke Windows 10/11-pc; op de Mac is Chrome gangbaar. De flags komen uit Chrome's eigen headless-documentatie.

```python
"""HTML to PDF the way a browser shows it, via the user's Chrome/Edge/Chromium."""

class BrowserOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_timeout_ms: int = Field(15000, ge=1000, le=120000)  # capture after this, loaded or not


class BrowserPdfConverter(Converter):
    family = "document"
    family_label = "Document"
    formats = (F.HTML, F.PDF)
    Options = BrowserOptions
    options_key = "browser"
    install_hint = "Installeer Chrome of Edge voor HTML naar PDF met de opmaak van de webpagina."

    def available(self) -> bool:
        return find_app("browser") is not None

    def targets(self, source: str) -> list[str]:
        return ["pdf"]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return ["De pagina wordt geopend zoals in een browser: scripts draaien en externe "
                "afbeeldingen of lettertypen worden van internet gehaald.",
                "Zonder @page-regel in de CSS wordt het papierformaat US Letter."]

    def convert(self, ctx: ConversionContext) -> None:
        opts: BrowserOptions = ctx.options  # type: ignore[assignment]
        browser = find_app("browser")
        if browser is None:
            raise ToolMissingError(self.install_hint)
        work = ctx.output_path.parent
        cmd = [str(browser), "--headless", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--disable-extensions", "--disable-sync",
               "--disable-background-networking",
               f"--user-data-dir={work / 'browser-profile'}",  # never the user's own (review #15)
               "--no-pdf-header-footer", f"--timeout={opts.page_timeout_ms}",
               f"--print-to-pdf={ctx.output_path}", ctx.input_path.resolve().as_uri()]
        # Process limit = page limit + start-up margin; a hung browser is killed (review #15)
        run_tool(cmd, timeout_s=min(ctx.timeout_s, opts.page_timeout_ms // 1000 + 60),
                 cancel=ctx.cancel)
        if not ctx.output_path.is_file() or ctx.output_path.stat().st_size == 0:
            raise ConversionError("De browser maakte geen PDF")
```

**Getest in de sandbox:** Chromium's headless-shell maakte de PDF in 0,6 s met dezelfde flags. De volledige Chrome-binary bleef in de sandbox hangen op ontbrekende systeemdiensten (dbus); dat is een omgevingsprobleem, maar het is precies waarom de procestime-out nodig is.

**Audit (eerst doen):** in CI op `windows-latest` (Edge en Chrome) en `macos-latest` (Chrome) een HTML met een rode `<h1>` via CSS omzetten en in de PDF een rode pixel vinden (test in stap 28). Faalt dit op een platform, laat dan `available()` op dat platform `False` geven; Fase 1 blijft de terugval.

### Stap 15 — Edit `build_default_registry()` in `src/uniconv/core/registry.py`

**Why:** de volgorde van registreren is de voorrang. Bij Document moeten LibreOffice en de browser vóór Pandoc staan; bij Data LibreOffice ná pandas (pandas doet alles behalve PDF).

```python
# AFTER (this phase)
    for conv in (
        ImageConverter(),
        DataConverter(), OfficeSheetConverter(),
        OfficeDocumentConverter(), BrowserPdfConverter(), DocumentConverter(),  # best PDF first
        MediaConverter(),
    ):
        reg.register(conv)  # unavailable providers stay registered for detection and hints
```

De volgorde van de families in de UI volgt de eerste provider per familie, en blijft dus Afbeelding, Data, Document, Audio/video.

## Fase 3: vector

Na deze fase zet de Afbeelding-familie SVG om naar elk rasterformaat en naar een vector-PDF, en elke rasterafbeelding naar SVG door tracing. Alles zit in één nieuwe provider; `ImageConverter` levert alleen zijn opslaglogica.

### Stap 16 — Create `src/uniconv/converters/vector.py` (en kleine edit in `converters/image.py`)

**Why:** drie engines, drie valkuilen uit de sandbox:

- resvg crasht bij een SVG met absurde afmetingen (review #2), dus de afmetingen worden vóór het renderen gelezen en het renderen gebeurt in een eigen proces;
- resvg laat tekst met een ontbrekend lettertype weg (review #9), dus stderr wordt gelezen;
- tracing van foto's duurt minuten (review #3), dus vtracer draait via `run_isolated` op een verkleinde kopie.

De provider gebruikt `ImageOptions` (sectie `image`), zodat `jpeg_quality` en dergelijke ook voor SVG → JPG gelden.

**Edit in `image.py`:** het stuk van `convert()` vanaf `_normalize_mode` tot en met `img.save` wordt een functie `encode_raster(img, key, opts, path, icc=None)`, die `ImageConverter` en `VectorConverter` allebei aanroepen. Verder krijgt `ImageOptions` vier velden:

```python
    svg_min_px: int = Field(512, ge=16, le=16384)        # small icons are scaled up to this
    trace_colormode: Literal["color", "binary"] = "color"
    trace_max_megapixels: float = Field(1.0, gt=0, le=16)  # 4 MP took 111 s in tests
    trace_filter_speckle: int = Field(4, ge=0, le=128)     # ignore blobs smaller than this (px)
```

**vector.py:**

```python
"""SVG in and out. resvg renders SVG to pixels, Typst makes vector PDFs, vtracer traces
pixels to SVG. All three run outside the app process."""

import gzip
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps

from uniconv.converters import formats as F
from uniconv.converters.image import ImageConverter, ImageOptions, encode_raster
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError
from uniconv.core.isolate import run_isolated
from uniconv.core.tools import find_tool, run_tool

_RASTER_OUT = ["png", "jpg", "webp", "gif", "bmp", "tiff"]
_UNIT_PX = {"": 1, "px": 1, "pt": 96 / 72, "pc": 16, "mm": 96 / 25.4, "cm": 96 / 2.54,
            "in": 96, "em": 16, "ex": 8}
_GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}


class VectorConverter(Converter):
    family = "image"
    family_label = "Afbeelding"
    formats = (F.SVG, F.JPG, F.PNG, F.WEBP, F.GIF, F.BMP, F.TIFF, F.HEIC, F.PDF)
    Options = ImageOptions  # shares the "image" section with ImageConverter

    def available(self) -> bool:
        return find_tool("resvg") is not None

    def targets(self, source: str) -> list[str]:
        if source == "svg":
            return _RASTER_OUT + (["pdf"] if find_tool("typst") else [])
        return ["svg"]  # every raster source can be traced

    def expected_losses(self, source: str, target: str) -> list[str]:
        if target == "svg":
            return ["Tracing benadert de afbeelding met vlakken: kleurverlopen worden vlakke "
                    "kleuren. Werkt het best voor logo's en tekeningen, niet voor foto's."]
        if source == "svg" and target != "pdf":
            return ["Het resultaat heeft vaste afmetingen en wordt wazig bij inzoomen.",
                    *ImageConverter().expected_losses("png", target)]
        return []

    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "svg":
            self._trace(ctx)
        elif ctx.target.key == "pdf":
            self._svg_to_pdf(ctx)
        else:
            self._svg_to_raster(ctx)

    def _svg_to_raster(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        w, h = _svg_size(ctx.input_path)
        scale = max(1.0, opts.svg_min_px / max(w, h))
        if w * h * scale * scale > opts.max_megapixels * 1_000_000:  # resvg would abort (review #2)
            raise ConversionError(f"SVG is te groot om te renderen ({w:.0f}×{h:.0f} px)")
        png = ctx.output_path.with_name("render.png")
        stderr = run_tool([str(find_tool("resvg")), "--width", str(round(w * scale)),
                           "--resources-dir", str(ctx.input_path.parent),
                           str(ctx.input_path), str(png)],
                          timeout_s=ctx.timeout_s, cancel=ctx.cancel)
        for name in sorted(set(re.findall(r"No match for '\"?([^'\"]+)\"?' font-family", stderr))):
            ctx.warn(f"Lettertype '{name}' ontbreekt op deze computer; die tekst is weggelaten.")
        if ctx.target.key == "png":
            png.replace(ctx.output_path)
        else:
            with Image.open(png) as img:
                encode_raster(img.copy(), ctx.target.key, opts, ctx.output_path)

    def _svg_to_pdf(self, ctx: ConversionContext) -> None:
        work = ctx.output_path.parent
        svg = work / "in.svg"
        raw = ctx.input_path.read_bytes()
        svg.write_bytes(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)  # Typst: no .svgz
        if _only_generic_fonts(svg):
            ctx.warn("Tekst met een algemeen lettertype (zoals 'sans-serif') kan in de PDF als "
                     "schreefletter verschijnen.")  # review #10
        main = work / "main.typ"
        main.write_text('#set page(width: auto, height: auto, margin: 0pt, fill: none)\n'
                        '#image("in.svg")\n', encoding="utf-8")
        try:
            run_tool([str(find_tool("typst")), "compile", "--root", str(work), str(main),
                      str(ctx.output_path)], timeout_s=ctx.timeout_s, cancel=ctx.cancel)
        except ConversionError as exc:
            if "linked image" not in str(exc):
                raise
            # The SVG links external image files that Typst may not read: fall back to a
            # raster PDF via resvg (which resolves them) and img2pdf.
            ctx.warn("De SVG verwijst naar losse afbeeldingsbestanden; de PDF is daarom als "
                     "afbeelding gemaakt in plaats van als vector.")
            self._raster_pdf(ctx)

    def _trace(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        with Image.open(ctx.input_path) as im:
            img = ImageOps.exif_transpose(im).convert("RGBA")
        limit = opts.trace_max_megapixels * 1_000_000
        if img.width * img.height > limit:  # review #3: tracing time grows much faster than size
            factor = (limit / (img.width * img.height)) ** 0.5
            img = img.resize((max(1, int(img.width * factor)), max(1, int(img.height * factor))),
                             Image.Resampling.LANCZOS)
            ctx.warn(f"Afbeelding verkleind tot {img.width}×{img.height} px voor tracing.")
        src = ctx.output_path.with_name("trace-in.png")
        img.save(src)
        run_isolated(_trace_worker, str(src), str(ctx.output_path), opts.trace_colormode,
                     opts.trace_filter_speckle, timeout_s=ctx.timeout_s, cancel=ctx.cancel)


def _trace_worker(src: str, dst: str, colormode: str, speckle: int) -> None:
    """Runs in a child process (core.isolate). Module level, so it can be found by name."""
    import vtracer  # imported here: the parent process never needs it
    vtracer.convert_image_to_svg_py(src, dst, colormode=colormode, filter_speckle=speckle)


def _svg_size(path: Path) -> tuple[float, float]:
    """Size in px from the root <svg>; only the first element is parsed."""
    opener = gzip.open if path.read_bytes()[:2] == b"\x1f\x8b" else open
    try:
        with opener(path, "rb") as fh:
            _, root = next(ET.iterparse(fh, events=("start",)))
    except (ET.ParseError, StopIteration, OSError) as exc:
        raise ConversionError(f"SVG kan niet worden gelezen: {exc}") from exc
    vb = [float(v) for v in re.split(r"[\s,]+", root.get("viewBox", "").strip()) if v][2:4]
    w, h = _length(root.get("width")), _length(root.get("height"))
    if w is None or h is None:  # missing or "100%": fall back to the viewBox, like resvg
        w, h = (vb[0], vb[1]) if len(vb) == 2 else (100.0, 100.0)
    return max(w, 1.0), max(h, 1.0)
```

`_length()` zet `"10cm"` om via `_UNIT_PX` en geeft `None` bij `%` of onleesbare waarden. `_only_generic_fonts()` zoekt met een regex alle `font-family`-waarden (attribuut en `style`) en geeft `True` als er tekst is en elke lijst alleen uit `_GENERIC` bestaat. `_raster_pdf()` rendert met resvg op 2× en geeft de PNG aan img2pdf, met dezelfde code als stap 9.

**Getest in de sandbox:** resvg-CLI rendert verloop, transparantie, `.svgz` en relatieve `<image>`; `--width 300` behoudt de verhouding; een kapotte SVG geeft exitcode 1 met "the root node was opened but never closed"; een SVG van 200000×200000 geeft een abort met exitcode 134 (nu vooraf geweigerd). Typst geeft een vector-PDF van 180×90 pt voor een SVG van 240×120 px, faalt bij een ontbrekende gekoppelde afbeelding en leest geen `.svgz`; die twee gevallen vangt de code hierboven af. Tracing via `run_isolated` was binnen 0,1 s te annuleren.

### Stap 17 — Edit `build_default_registry()` in `src/uniconv/core/registry.py`

**Why:** `VectorConverter` staat ná `ImageConverter`. De twee overlappen niet (alleen Vector leest SVG en schrijft SVG), maar zo blijft `ImageConverter` de eerste keus als er ooit wel overlap komt.

```python
# BEFORE
        ImageConverter(),
# AFTER
        ImageConverter(), VectorConverter(),
```

## Fase 4: 3D-modellen

Na deze fase is er een vijfde familie, "3D-model", die STL, OBJ, PLY, OFF, GLB, glTF en 3MF onderling omzet. Dat zijn 42 paren, die alle 42 in de sandbox werkten.

### Stap 18 — Create `src/uniconv/converters/model3d.py`

**Why:** trimesh leest en schrijft al deze formaten met numpy en scipy, dus er is geen binary nodig. Grote meshes kunnen wel lang duren of veel geheugen kosten, dus de conversie draait via `run_isolated`. De formaten verschillen in wat ze kunnen bevatten (review #16): STL, PLY en OFF kennen maar één mesh, OBJ met texturen bestaat uit meerdere bestanden, en glTF is standaard Y-omhoog in meters.

```python
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
        run_isolated(_convert_worker, str(ctx.input_path), str(ctx.output_path),
                     ctx.source.key, ctx.target.key, timeout_s=ctx.timeout_s, cancel=ctx.cancel)


def _convert_worker(src: str, dst: str, src_key: str, dst_key: str) -> None:
    """Runs in a child process (core.isolate). Raises ConversionError with a user message."""
    import trimesh  # heavy import (scipy): only in the child

    try:
        loaded = trimesh.load(src, file_type=src_key)  # resolves .mtl/.bin next to the input
    except Exception as exc:  # trimesh raises many types for bad files
        raise ConversionError(f"3D-model kan niet worden gelezen: {exc}") from exc
    if isinstance(loaded, trimesh.Scene) and not loaded.geometry:
        raise ConversionError("Het bestand bevat geen 3D-geometrie")
    try:
        if dst_key in _SINGLE_MESH:
            mesh = loaded.to_mesh() if isinstance(loaded, trimesh.Scene) else loaded
            data = mesh.export(file_type=dst_key)  # OFF only exists per mesh, not per scene
        elif dst_key == "obj":
            data = loaded.export(file_type="obj", include_texture=False)  # one file (review #16)
        elif dst_key == "gltf":
            scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
            files = trimesh.exchange.gltf.export_gltf(scene, embed_buffers=True)
            (data,) = files.values()  # embedded buffers: exactly one file
        else:  # glb, 3mf
            data = loaded.export(file_type=dst_key)
    except Exception as exc:  # e.g. a point cloud has no faces for STL
        raise ConversionError(f"Kan dit model niet als {dst_key.upper()} opslaan: {exc}") from exc
    Path(dst).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
```

**Getest in de sandbox (trimesh 5.2.0):** alle 42 paren tussen de zeven formaten werkten, met een scene van twee objecten als bron. Zonder scipy faalden OBJ en GLB, zonder networkx en lxml werd 3MF niet aangeboden. `filetype` gaf `None` voor alle formaten behalve 3MF (`application/zip`).

**Audit:** controleer in de release-smoke-test (stap 23) dat de bevroren app een STL naar GLB en een GLB naar 3MF omzet. PyInstaller moet daarvoor de datafiles van trimesh en de scipy-modules meenemen, en `freeze_support()` moet het kindproces correct afhandelen.

### Stap 19 — Edit `build_default_registry()` in `src/uniconv/core/registry.py`

**Why:** de nieuwe familie moet geregistreerd worden; als laatste, zodat hij als laatste knop in de UI verschijnt.

```python
# BEFORE
        MediaConverter(),
    ):
# AFTER
        MediaConverter(),
        Model3DConverter(),
    ):
```

De UI heeft geen aanpassing nodig: de familieknoppen, de bestandsfilter en de doelen komen uit de registry. Met vijf knoppen wordt het venster wel iets breder; controleer dat even op een offscreen-screenshot (zoals in Sprint 2).

## Fase 5: packaging, CI, licenties en geheugen

Na deze fase bouwt de release-workflow 0.2.0 voor Windows en macOS, test hij de nieuwe routes in de bevroren app, en weten de geheugenbestanden van Claude Code hoe de providers werken.

### Stap 20 — Edit `packaging/uniconv.spec`

**Why:** trimesh leest JSON-sjablonen uit zijn eigen pakketmap. PyInstaller neemt die alleen mee als je het vraagt. De Typst- en resvg-binaries komen vanzelf mee, want alles uit `vendor/<tag>/` gaat al naar `bin/`. En de minimale macOS-versie moet kloppen met de wheels die de runner installeert (review #8).

```python
# BEFORE
from PyInstaller.utils.hooks import collect_dynamic_libs
...
datas = [
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_LICENSES.md"), "."),
    (str(vendor / "licenses"), "licenses"),
]
...
            "LSMinimumSystemVersion": "12.0",

# AFTER
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
...
datas = [
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_LICENSES.md"), "."),
    (str(vendor / "licenses"), "licenses"),
    (str(ROOT / "packaging" / "licenses"), "licenses"),  # resvg ships none in its zip
]
datas += collect_data_files("trimesh")  # trimesh/resources/*: glTF/3MF templates
...
            # PySide6 >= 6.10, pikepdf 10 and scipy wheels on macos-latest need macOS 14
            "LSMinimumSystemVersion": "14.0",
```

De lazy imports `import vtracer` en `import trimesh` binnen functies vindt PyInstaller zelf; scipy en pikepdf hebben hooks in `pyinstaller-hooks-contrib`. De smoke-test van stap 23 bewijst dat dit klopt.

### Stap 21 — Create `packaging/licenses/` en edit `THIRD_PARTY_LICENSES.md`

**Why:** de resvg-zips bevatten geen licentietekst (review #20), en elke nieuw meegeleverde component moet in de licentielijst staan.

**What changes:**

- `packaging/licenses/resvg-LICENSE-MIT.txt` en `resvg-LICENSE-APACHE.txt`: letterlijk `LICENSE-MIT` en `LICENSE-APACHE` uit de resvg-repo op tag `v0.49.0`.
- `THIRD_PARTY_LICENSES.md` krijgt per component naam, versie, licentie en bronlink: Typst 0.15.1 (Apache-2.0, `LICENSE` en `NOTICE` gaan mee via het manifest), resvg 0.49.0 (Apache-2.0 OR MIT), img2pdf (LGPL-3.0-or-later), pikepdf (MPL-2.0), vtracer (MIT), trimesh (MIT), scipy (BSD-3-Clause), networkx (BSD-3-Clause), lxml (BSD-3-Clause).
- Een alinea dat LibreOffice en Chrome/Edge **niet** worden meegeleverd, maar alleen worden aangeroepen als de gebruiker ze zelf heeft geïnstalleerd.

Alle licenties zijn verenigbaar met GPL-3.0-or-later; voor LGPL-3.0 (img2pdf) en MPL-2.0 (pikepdf) volstaat het meeleveren van de licentietekst en een bronverwijzing.

### Stap 22 — Edit `.github/workflows/ci.yml`

**Why:** de `otool -L`-controle uit ADR-001 moet ook de nieuwe binaries dekken. En de LibreOffice-tests hebben een runner met LibreOffice nodig. Die installatie duurt minuten, dus die tests draaien in een aparte job die niet bij elke push loopt.

```yaml
# BEFORE (macOS guard)
          for b in vendor/darwin-arm64/ffmpeg vendor/darwin-arm64/ffprobe; do
# AFTER
          for b in vendor/darwin-arm64/{ffmpeg,ffprobe,typst,resvg}; do
```

```yaml
# NEW trigger + job
on:
  push:
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: "17 3 * * 1"  # weekly: LibreOffice job also runs when nobody pushes

  libreoffice:
    if: github.event_name != 'pull_request'
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e ".[dev]"
      - name: Install LibreOffice (Windows)
        if: runner.os == 'Windows'
        run: choco install libreoffice-fresh -y --no-progress
      - name: Install LibreOffice (macOS)
        if: runner.os == 'macOS'
        run: |
          brew install --cask libreoffice
          xattr -dr com.apple.quarantine /Applications/LibreOffice.app || true
      - run: pytest -q -rs -m needs_libreoffice
```

De hoofd-job `test` blijft zoals hij is: Chrome en Edge staan al op de runners, dus de browsertests (`needs_browser`) draaien daar gewoon mee.

### Stap 23 — Edit `.github/workflows/release.yml`

**Why:** de bevroren app is wat gebruikers krijgen. Drie dingen kunnen alleen daar misgaan: Typst/resvg niet in `bin/`, trimesh-data niet meegenomen, en `freeze_support()` die het kindproces niet goed afhandelt (review #7). Elk krijgt een conversie in de smoke-test.

```bash
# appended to "Smoke test the frozen app", after the existing conversions
printf '# Titel\n\nTekst.\n' > smoke2.md
printf '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="red"/></svg>' > smoke.svg
printf 'solid t\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid t\n' > smoke.stl
"../$BIN" convert smoke2.md --to pdf --out out    # Pandoc + Typst
"../$BIN" convert smoke.png --to pdf --out out    # img2pdf (+ pikepdf)
"../$BIN" convert smoke.svg --to png --out out    # resvg
"../$BIN" convert smoke.png --to svg --out out    # vtracer in a child process: freeze_support
"../$BIN" convert smoke.stl --to glb --out out    # trimesh + scipy in a child process
for f in out/smoke2.pdf out/smoke.pdf out/smoke.png out/smoke.svg out/smoke.glb; do
  test -s "$f" || { echo "::error::missing $f"; exit 1; }
done
# a missing freeze_support() shows up as a runaway: no more than one UniConv process may remain
```

Voor de laatste regel zoekt een paar regels Python met `subprocess` (`tasklist` op Windows, `pgrep` op macOS) naar `UniConv`-processen die na de conversies nog draaien, en faalt als die er zijn. `smoke.png` als bron en `out/smoke.png` als uitvoer botsen niet: de bron staat in de werkmap van de test.

### Stap 24 — Edit `README.md`

**Why:** gebruikers moeten weten wat er bij is gekomen, wat ze zelf kunnen installeren voor betere PDF's, en dat macOS 12 en 13 niet meer werken.

**What changes:**

- De formatentabel krijgt SVG (bron en doel), PDF als doel bij Document en Data, DOC/PPT(X)/ODP/XLS/ODS als bron, en de familie 3D-model.
- Een korte sectie "Betere PDF's": met LibreOffice geïnstalleerd behouden Word, PowerPoint en Excel hun opmaak; met Chrome of Edge behoudt HTML zijn CSS. Zonder die apps werkt alles, met eenvoudigere opmaak.
- Systeemeisen: macOS 14 of nieuwer (review #8); de download is groter (\~+110 MB uitgepakt; review #21).
- Privacy: alles blijft lokaal, met twee uitzonderingen die de gebruiker zelf veroorzaakt: afbeeldingen met een `https://`-adres in Markdown/HTML worden opgehaald (review #22), en HTML via de browser laadt externe bestanden zoals een browser dat doet.
- In de configtabel de nieuwe secties `office`, `browser` en de nieuwe velden onder `image` en `document`.

### Stap 25 — Edit de geheugenbestanden van Claude Code

**Why:** de volgende sessie moet zonder dit document weten dat een familie nu providers heeft, waar processen geïsoleerd worden en welke apps gedetecteerd worden.

**What changes:**

- `docs/extension-plan-0.2.md`: export van dit plan (Markdown), zodat Claude Code per stap kan lezen, net als `docs/implementation-plan.md`.
- `.claude/decisions/ADR-003-providers-per-family.md`: context (review #6), besluit (geordende providers, gedeelde formaten, opties per sectie), alternatieven (één converter per familie met interne dispatch; aparte familie "PDF") en gevolgen (volgorde in `build_default_registry()` is gedrag).
- `CLAUDE.md`: Current Sprint wordt "0.2: gemiddelde conversies" met de fases als taken; module map met `office.py`, `browser.py`, `vector.py`, `model3d.py`, `core/isolate.py`, `core/apps.py`; key decisions met de regels "een engine die kan crashen of minuten rekent, draait via `run_isolated` of `run_tool`" en "LibreOffice en browsers worden gedetecteerd, nooit meegeleverd"; bij What NOT to do: "geen `registry.converter()` meer, gebruik `find()`".
- `src/uniconv/core/CLAUDE.md`, `src/uniconv/converters/CLAUDE.md`, `tests/CLAUDE.md`: interfaces en valkuilen uit dit plan (LibreOffice exitcode 0, resvg-abort, de tweestapsroute Pandoc → Typst, vtracer-tijden).
- `.claude/memory/session-log.md`: een entry per sessie, zoals nu.

## Tests

De tests bewijzen drie dingen: elk aangeboden paar levert een geldig bestand op, de juiste provider wint, en geen enkele invoer kan de app laten crashen of hangen. Elke review-fix heeft een test met het nummer in de naam of docstring. Schrijf de tests van een fase in die fase.

### Stap 26 — Edit `tests/conftest.py` en `pyproject.toml` (markers)

**Why:** nieuwe engines zijn soms afwezig (lokaal zonder `vendor/`, CI zonder LibreOffice). Tests die ze nodig hebben, moeten dan netjes overgeslagen worden. Nieuwe formaten hebben samplegenerators nodig, zodat de matrixtest ze automatisch meeneemt.

**What changes:**

- Markers `needs_typst`, `needs_resvg` (via `find_tool`) en `needs_libreoffice`, `needs_browser` (via `find_app`) in `pyproject.toml` en in `pytest_collection_modifyitems`, op dezelfde manier als `needs_pandoc`.
- `make_sample` kent: `svg` (vaste tekst, 240×120 met verloop en tekst), de zeven 3D-formaten (een scene van een kubus en een bol, geëxporteerd met trimesh in het testproces), `pptx` (via Pandoc), en `doc`, `xls`, `ppt`, `ods`, `odp` (via `soffice --convert-to` in een tijdelijke map; alleen aangeroepen als LibreOffice er is).
- Een fixture `registry_without(*classes)` die een registry bouwt waarin de genoemde providers als niet-beschikbaar geregistreerd zijn. Zo zijn de terugvalroutes ook te testen op een machine waar LibreOffice of Chrome wel staat.

### Stap 27 — Unit-tests in `tests/unit/`

| Bestand | Bewijst |
| --- | --- |
| `test_registry.py` (herschreven) | Twee nep-providers met hetzelfde paar: de eerst geregistreerde wint; een tweede definitie van `"pdf"` met een ander label geeft `ValueError` (#6); een bronformaat in twee families geeft `ValueError`; twee `Options`-modellen voor dezelfde sectie geven `ValueError`; een niet-beschikbare provider: zijn formaten worden herkend, hij biedt geen doelen aan, `hints()` geeft zijn `install_hint`; een familie zonder levende provider staat niet in `families()`; `default_options()` bevat `office` en `browser` |
| `test_detect.py` (uitgebreid) | Een met wachtwoord beveiligde `.docx` (gemaakt met msoffcrypto-tool) wordt DOCX, niet PPT (#13); `.3mf` (zip) wordt 3MF; een echte `.doc`, `.xls` en `.ppt` worden herkend; een `.pdf` geeft "kan alleen als doel" in elke familie |
| `test_isolate.py` (nieuw) | Geeft de returnwaarde terug; een `ConversionError` in het kind komt met dezelfde tekst terug; een `ValueError` wordt "Onverwachte fout"; `os.abort()` in het kind geeft de crashmelding en het testproces leeft nog; annuleren na 0,3 s stopt binnen 1 s; een time-out van 1 s stopt een slapend kind. De doelfuncties staan in `tests/unit/_isolate_targets.py`, omdat `spawn` ze op naam moet kunnen importeren |
| `test_apps.py` (nieuw) | `UNICONV_LIBREOFFICE` wint; op een gesimuleerde Windows (`sys.platform` en `ProgramFiles` gemonkeypatcht naar `tmp_path`) wordt `soffice.com` gekozen boven `soffice.exe`; op een gesimuleerde macOS wordt `~/Applications/...` gevonden; `PATH` als laatste; `find_app.cache_clear()` tussen tests |
| `test_tools.py` (uitgebreid) | `run_tool(..., cwd=tmp_path)` draait daar echt; een time-out gooit `ConversionTimeout` (subklasse van `ConversionError`) |
| `test_layering.py` | Ongewijzigd; omdat de test de mappen scant, vallen `isolate.py`, `apps.py` en de nieuwe converters er vanzelf onder |

### Stap 28 — Integratietests in `tests/integration/`

| Bestand | Bewijst |
| --- | --- |
| `test_matrix.py` (edit) | `_REG.converter(family).sources()` wordt `_REG.sources(family)`. Daardoor lopen alle nieuwe paren mee, ook 3D (42) en SVG, maar alleen voor providers die op die machine beschikbaar zijn |
| `test_image.py` (uitgebreid) | PNG → PDF: beeldstream is `/FlateDecode` (#1); JPG → PDF: beeldstream byte-identiek aan het bronbestand (#1); WebP met alpha → PDF slaagt (#18); geanimeerde GIF → PDF met 3 pagina's; EXIF-oriëntatie 6 → staande pagina |
| `test_pdf.py` (nieuw; `needs_pandoc`, `needs_typst`) | Markdown met afbeelding → A4 (595×842 pt) met 1 afbeelding; afbeelding via `../` en absoluut pad komt mee, ook als de testwerkmap ergens anders staat (bewijst de tweestapsroute); tekst bevat "Figuur"; ontbrekende afbeelding geeft een waarschuwing; met `registry_without(OfficeDocumentConverter)` kiest DOCX → PDF Pandoc en noemt de verlieshint LibreOffice (#12); idem HTML zonder browser (#11) |
| `test_office.py` (nieuw; `needs_libreoffice`) | DOCX met "één" in de naam, PPTX en ODT → PDF; XLSX met twee werkbladen → minstens 2 pagina's; `doc.odt` en `doc.rtf` na elkaar → twee correcte PDF's (#14); afgekapte DOCX en met wachtwoord beveiligde DOCX → "beschadigd of beveiligd met een wachtwoord" en niets in `out_dir` (#4, #13); `find()` voor DOCX → PDF geeft `OfficeDocumentConverter` |
| `test_browser.py` (nieuw; `needs_browser`) | HTML met `h1 { color: red }` → PDF waarin pypdfium2 rode pixels rendert (CSS behouden, #11); geen `browser-profile` buiten de jobmap; een pagina met een eindeloze `setTimeout`-lus levert toch een PDF binnen `page_timeout_ms` + marge (#15) |
| `test_vector.py` (nieuw; `needs_resvg`) | SVG 240×120 → PNG 512×256 (`svg_min_px`); SVG 200000×200000 → nette `ConversionError` en het testproces leeft (#2, volledig voorbeeld hieronder); onbekend lettertype → waarschuwing met de naam (#9); kapotte SVG → leesbare fout; `.svgz` → PNG; SVG → PDF zonder beeld-XObjects (vector); SVG met gekoppelde PNG → PDF met waarschuwing over de rasterterugval; alleen `sans-serif` → waarschuwing (#10); logo-PNG → SVG; foto van 4 MP → verkleind met waarschuwing (#3); annuleren van een trage tracing stopt binnen 1 s |
| `test_model3d.py` (nieuw) | Scene met 2 objecten → STL met waarschuwing "samengevoegd"; → glTF is één bestand met `data:` in de buffers; → OBJ maakt geen `.mtl` in `out_dir`; GLB → STL toont de assen-waarschuwing (#16); lege STL → "bevat geen 3D-geometrie" |

**Representatieve test** (`test_vector.py`): een SVG die resvg zou laten crashen, wordt vóór het renderen geweigerd. Het testproces moet daarna nog leven; dat was in de sandbox precies wat er misging met resvg-py.

```python
@pytest.mark.needs_resvg
def test_huge_svg_is_refused_without_crashing(runner, tmp_path, out_dir):
    """Review #2: resvg aborts on a 200000x200000 canvas; we must refuse it first."""
    src = tmp_path / "bom.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200000" height="200000">'
                   '<rect width="10" height="10"/></svg>', encoding="utf-8")

    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())

    assert result.status == "failed"
    assert "te groot" in result.error
    assert list(out_dir.iterdir()) == []          # nothing half-written reaches the user
    assert list(runner.workspace.root.iterdir()) == []  # job directory cleaned up
```

**Belangrijkste integratietest** (`test_pdf.py`): de voorrang van providers. Eén DOCX gaat twee keer door `runner.run()` met dezelfde `Job`: eerst met de gewone registry (als LibreOffice er is, kiest `find()` LibreOffice en is er geen verlieshint), daarna met `registry_without(OfficeDocumentConverter)` (Pandoc + Typst, en de hint noemt LibreOffice). Dat bewijst in één test de registry, de volgorde in `build_default_registry()` en de terugval.

### Stap 29 — Edit `tests/ui/test_main_window.py`

| Test | Bewijst |
| --- | --- |
| `test_five_family_buttons` | De knoppen zijn Afbeelding, Data, Document, Audio/video, 3D-model, in die volgorde |
| `test_hint_when_no_targets` | Met `registry_without(OfficeDocumentConverter)` toont een gedropte PPTX geen doelen en een statusregel met "LibreOffice" |
| `test_loss_hint_from_chosen_provider` | Bij SVG → JPG komt de verlieshint van `VectorConverter` ("vaste afmetingen"), niet van `ImageConverter` |

## Samenvatting

| Stap | Bestand | Actie | Wat verandert |
| --- | --- | --- | --- |
| 1 | `src/uniconv/__main__.py` | **Edit** | `multiprocessing.freeze_support()` als eerste regel |
| 2 | `src/uniconv/core/converter.py` | **Edit** | `NoOptions`, `options_key`, `install_hint`, `config_section()` |
| 3 | `src/uniconv/converters/formats.py` | **Create** | Gedeelde `Format`-constanten; `image.py`, `data.py`, `document.py` importeren ze |
| 4 | `src/uniconv/core/registry.py` | **Rewrite** | Providers per familie, voorrang, zwakke MIME's, `hints()`, opties per sectie |
| 5 | `core/jobs.py`, `cli.py`, `ui/main_window.py`, `ui/app.py` | **Edit** | Nieuwe registry-API; hints in de UI |
| 6 | `src/uniconv/core/isolate.py` | **Create** | `run_isolated()`: apart proces, annuleren, time-out, crashbestendig |
| 7 | `src/uniconv/core/apps.py` | **Create** | `find_app()` voor LibreOffice en Chrome/Edge/Chromium (**Audit** in CI) |
| 8 | `pyproject.toml`, `src/uniconv/__init__.py` | **Edit** | Versie 0.2.0; img2pdf, vtracer, trimesh, scipy, networkx, lxml; dev: pypdfium2, msoffcrypto-tool |
| 9 | `src/uniconv/converters/image.py` | **Edit** | Afbeelding → PDF via img2pdf, verliesvrij en met meerdere pagina's |
| 10 | `scripts/fetch_binaries.py` | **Edit** | Typst 0.15.1 en resvg 0.49.0 gepind; `.tar.xz`-ondersteuning |
| 11 | `.claude/decisions/ADR-002-typst-resvg-and-detected-apps.md` | **Create** | Bronnen en hashes; meeleveren tegenover detecteren |
| 12 | `src/uniconv/core/tools.py`, `src/uniconv/converters/document.py` | **Edit** | `cwd` in `run_tool`; PDF via Pandoc → Typst-bron → Typst (**Audit** Windows) |
| 13 | `src/uniconv/converters/office.py` (+ `core/errors.py`, `core/tools.py`) | **Create** / **Edit** | LibreOffice-providers voor Document en Data; `ConversionTimeout` (**Audit** `soffice.com`) |
| 14 | `src/uniconv/converters/browser.py` | **Create** | HTML → PDF via Chrome/Edge (**Audit** op beide OS'en) |
| 15 | `src/uniconv/core/registry.py` | **Edit** | Volgorde: Office en browser vóór Pandoc |
| 16 | `src/uniconv/converters/vector.py` (+ `converters/image.py`) | **Create** / **Edit** | SVG → raster/PDF, raster → SVG; `encode_raster()` en vier `ImageOptions`-velden |
| 17 | `src/uniconv/core/registry.py` | **Edit** | `VectorConverter` registreren |
| 18 | `src/uniconv/converters/model3d.py` | **Create** | Familie 3D-model via trimesh in een apart proces (**Audit** bevroren app) |
| 19 | `src/uniconv/core/registry.py` | **Edit** | `Model3DConverter` registreren |
| 20 | `packaging/uniconv.spec` | **Edit** | trimesh-data, `packaging/licenses`, macOS-minimum 14.0 |
| 21 | `packaging/licenses/resvg-LICENSE-*.txt`, `THIRD_PARTY_LICENSES.md` | **Create** / **Edit** | Licenties van alle nieuwe componenten |
| 22 | `.github/workflows/ci.yml` | **Edit** | `otool`-controle voor Typst en resvg; wekelijkse LibreOffice-job |
| 23 | `.github/workflows/release.yml` | **Edit** | Smoke-test van vijf nieuwe routes in de bevroren app |
| 24 | `README.md` | **Edit** | Formaten, "Betere PDF's", macOS 14+, privacy, nieuwe config |
| 25 | `docs/extension-plan-0.2.md`, `ADR-003-providers-per-family.md`, `CLAUDE.md`-bestanden, `session-log.md` | **Create** / **Edit** | Geheugen voor volgende sessies |
| 26 | `tests/conftest.py`, `pyproject.toml` | **Edit** | Vier nieuwe markers; samplegenerators; `registry_without()` |
| 27 | `tests/unit/` | **Create** / **Edit** | `test_registry` herschreven; `test_detect`, `test_tools` uitgebreid; `test_isolate`, `_isolate_targets`, `test_apps` nieuw |
| 28 | `tests/integration/` | **Create** / **Edit** | `test_matrix`, `test_image`, `test_document` (regel 82: `converter()` vervalt) aangepast; `test_pdf`, `test_office`, `test_browser`, `test_vector`, `test_model3d` nieuw |
| 29 | `tests/ui/test_main_window.py` | **Edit** | Vijf families, hint zonder doelen, verlieshint van de gekozen provider |

**Wat ik niet kon testen in de sandbox** en daarom als **Audit** in de stappen staat: `soffice.com` op Windows (stap 13), Chrome/Edge headless op echte Windows- en Mac-runners (stap 14), padnotatie van de Typst-route op Windows (stap 12), en de bevroren app met `spawn`, trimesh-data en scipy (stap 18 en 23). Elke audit heeft een CI-test die het antwoord geeft, en een terugval als het antwoord nee is.
