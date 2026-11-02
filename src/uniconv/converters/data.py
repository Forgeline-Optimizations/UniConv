"""Data family. Two shapes: tables (CSV, XLSX) and trees (JSON, YAML, TOML, XML).

Within a shape conversion is lossless; between shapes one rule each way, so no pair needs
its own code.
"""

import csv
import io
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pandas as pd
import tomli_w
import xmltodict
import yaml
from pydantic import BaseModel, ConfigDict, Field

from uniconv.core.converter import ConversionContext, Converter, Format
from uniconv.core.errors import ConversionError


class DataOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: str = "auto"          # or an explicit codec name such as "utf-8" or "cp1252"
    csv_delimiter: str = Field(",", min_length=1, max_length=1)
    indent: int = Field(2, ge=0, le=8)


_TABULAR = {"csv", "xlsx"}
_XML_NAME = re.compile(r"^[A-Za-z_][\w.\-]*$")


class DataConverter(Converter):
    family = "data"
    family_label = "Data"
    Options = DataOptions
    formats = (
        Format("csv", "CSV", (".csv",)),
        Format("xlsx", "Excel", (".xlsx",),
               ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)),
        Format("json", "JSON", (".json",)),
        Format("yaml", "YAML", (".yaml", ".yml")),
        Format("toml", "TOML", (".toml",)),
        Format("xml", "XML", (".xml",)),
    )

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if source not in _TABULAR and target in _TABULAR:
            out.append("Geneste data wordt platgeslagen tot kolommen (bijv. adres.stad).")
        if source == "xlsx":
            out.append("Alleen het eerste werkblad wordt meegenomen; opmaak en formules niet.")
        if target == "toml":
            out.append("TOML kent geen lege waarden (null); die worden weggelaten.")
        if source == "xml" and target != "xml":
            out.append("XML-attributen worden velden met een @-prefix.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        opts: DataOptions = ctx.options  # type: ignore[assignment]
        data = _load(ctx.input_path, ctx.source.key, opts, ctx)
        ctx.cancel.raise_if_cancelled()
        if ctx.target.key in _TABULAR and not isinstance(data, pd.DataFrame):
            data = _tree_to_frame(data)
        elif ctx.target.key not in _TABULAR and isinstance(data, pd.DataFrame):
            data = json.loads(data.to_json(orient="records", date_format="iso",
                                           force_ascii=False))
        ctx.cancel.raise_if_cancelled()
        _dump(data, ctx.output_path, ctx.target.key, opts, ctx)


# ---- reading ---------------------------------------------------------------------------

def _read_text(path: Path, opts: DataOptions, ctx: ConversionContext) -> str:
    raw = path.read_bytes()
    if opts.encoding != "auto":
        try:
            return raw.decode(opts.encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise ConversionError(f"Kan bestand niet lezen als {opts.encoding}: {exc}") from exc
    try:
        return raw.decode("utf-8-sig")  # also strips the BOM Excel adds (review #5)
    except UnicodeDecodeError:
        ctx.warn("Bestand is geen UTF-8 en is gelezen als Windows-1252.")
        return raw.decode("cp1252", errors="replace")


def _read_csv(text: str) -> pd.DataFrame:
    try:
        sep = csv.Sniffer().sniff(text[:64_000], delimiters=",;\t|").delimiter
    except csv.Error:
        sep = ","  # one column, or too irregular to guess
    # Everything as text first: "007" postcodes and "NA" (Namibia) must survive.
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    return _infer_types(df)


def _infer_types(df: pd.DataFrame) -> pd.DataFrame:
    """Make numeric columns numeric, but never at the cost of a leading zero."""
    out = df.copy()
    for col in out.columns:
        values = out[col].astype(str)
        present = values[values != ""]
        if present.empty or present.str.match(r"^[+-]?0\d").any():
            out[col] = out[col].replace("", None)
            continue
        numbers = pd.to_numeric(present, errors="coerce")
        if numbers.notna().all():
            converted = pd.to_numeric(out[col].replace("", None), errors="coerce")
            if (converted.dropna() % 1 == 0).all():
                converted = converted.astype("Int64")
            out[col] = converted
        else:
            out[col] = out[col].replace("", None)
    return out


def _load(path: Path, key: str, opts: DataOptions, ctx: ConversionContext) -> Any:
    try:
        match key:
            case "xlsx":
                with pd.ExcelFile(path, engine="openpyxl") as book:
                    if len(book.sheet_names) > 1:
                        ctx.warn(f"Alleen het eerste werkblad ({book.sheet_names[0]}) is "
                                 "geconverteerd.")
                    return pd.read_excel(book, sheet_name=0)
            case "csv":
                return _read_csv(_read_text(path, opts, ctx))
            case "json":
                return json.loads(_read_text(path, opts, ctx))
            case "yaml":
                return yaml.safe_load(_read_text(path, opts, ctx))  # never yaml.load
            case "toml":
                return tomllib.loads(_read_text(path, opts, ctx))
            case "xml":
                return xmltodict.parse(_read_text(path, opts, ctx))
    except ConversionError:
        raise
    except Exception as exc:  # pandas, openpyxl, expat and friends raise many types
        raise ConversionError(f"Kan {path.name} niet lezen: {_first_line(exc)}") from exc
    raise ConversionError(f"Onbekend dataformaat: {key}")


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


# ---- shape changes ---------------------------------------------------------------------

def _tree_to_frame(data: Any) -> pd.DataFrame:
    # unwrap {"root": {"row": [...]}} (XML) or {"items": [...]} (API exports) (review #8)
    while isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))
    if isinstance(data, dict):
        data = [data]  # a single record becomes one row
    if isinstance(data, list) and data and all(isinstance(r, dict) for r in data):
        df = pd.json_normalize(data)
        for col in df.columns:  # lists left in cells would be written as Python reprs
            if df[col].map(lambda v: isinstance(v, list | dict)).any():
                df[col] = df[col].map(
                    lambda v: json.dumps(v, ensure_ascii=False, default=str)
                    if isinstance(v, list | dict) else v
                )
        return df
    raise ConversionError("Deze data is geen lijst van records en past daarom niet in een tabel.")


def _drop_nulls(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        out, dropped = {}, False
        for k, v in value.items():
            if v is None:
                dropped = True
                continue
            out[k], d = _drop_nulls(v)
            dropped |= d
        return out, dropped
    if isinstance(value, list):
        items = [_drop_nulls(v) for v in value if v is not None]
        return [v for v, _ in items], any(d for _, d in items) or len(items) != len(value)
    return value, False


def _xml_safe(value: Any, renamed: list[str]) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            name = str(k)
            if not name.startswith(("@", "#")) and not _XML_NAME.match(name):
                fixed = re.sub(r"[^\w.\-]", "_", name)
                name = fixed if _XML_NAME.match(fixed) else f"_{fixed}"
                renamed.append(str(k))
            out[name] = _xml_safe(v, renamed)
        return out
    if isinstance(value, list):
        return [_xml_safe(v, renamed) for v in value]
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


# ---- writing ---------------------------------------------------------------------------

def _dump(data: Any, path: Path, key: str, opts: DataOptions, ctx: ConversionContext) -> None:
    try:
        match key:
            case "csv":
                data.to_csv(path, index=False, sep=opts.csv_delimiter,
                            encoding="utf-8-sig")  # BOM: Excel shows accents correctly
            case "xlsx":
                data.to_excel(path, index=False, engine="openpyxl")
            case "json":
                text = json.dumps(data, indent=opts.indent or None, ensure_ascii=False,
                                  default=str)
                path.write_text(text + "\n", encoding="utf-8")
            case "yaml":
                text = yaml.safe_dump(_jsonable(data), sort_keys=False, allow_unicode=True)
                path.write_text(text, encoding="utf-8")
            case "toml":
                if not isinstance(data, dict):
                    ctx.warn("TOML vereist een object: de lijst staat onder de sleutel 'rows'.")
                    data = {"rows": data}
                data, dropped = _drop_nulls(data)
                if dropped:
                    ctx.warn("Lege waarden (null) zijn weggelaten: TOML kent die niet.")
                path.write_text(tomli_w.dumps(data), encoding="utf-8")
            case "xml":
                if isinstance(data, list):
                    data = {"root": {"row": data}}
                elif not (isinstance(data, dict) and len(data) == 1
                          and not isinstance(next(iter(data.values())), list)):
                    data = {"root": data}  # {"rows": [...]} would give one root per item
                renamed: list[str] = []
                data = _xml_safe(data, renamed)
                if renamed:
                    ctx.warn("Sommige veldnamen zijn aangepast tot geldige XML-namen.")
                ctx.warn("Er worden geen XML-attributen gemaakt; alle velden zijn elementen.")
                text = xmltodict.unparse(data, pretty=True, indent=" " * (opts.indent or 2))
                path.write_text(text, encoding="utf-8")
            case _:
                raise ConversionError(f"Onbekend dataformaat: {key}")
    except ConversionError:
        raise
    except (ValueError, TypeError, OSError) as exc:
        raise ConversionError(f"Kan niet schrijven als {key.upper()}: {_first_line(exc)}") from exc


def _jsonable(data: Any) -> Any:
    """YAML's safe_dump refuses some types (e.g. pandas scalars); JSON round-trip cleans them."""
    return json.loads(json.dumps(data, default=str))
