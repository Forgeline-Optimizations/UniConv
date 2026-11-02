import json
import tomllib

import pandas as pd
import pytest
import xmltodict

from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job


def _convert(runner, src, target, out_dir):
    [result] = runner.run(Job("data", target, [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    return result


def _read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def test_csv_json_csv_round_trip(runner, make_sample, out_dir, tmp_path):
    src = make_sample("csv", text="id,naam,postcode\n1,Zoë,0123\n2,Jürgen,\n")
    as_json = _convert(runner, src, "json", out_dir).output
    records = json.loads(as_json.read_text(encoding="utf-8"))
    assert records == [{"id": 1, "naam": "Zoë", "postcode": "0123"},
                       {"id": 2, "naam": "Jürgen", "postcode": None}]
    back = _convert(runner, as_json, "csv", tmp_path / "back").output
    assert _read_csv(back).to_dict("records") == _read_csv(src).to_dict("records")


def test_csv_output_has_bom_for_excel(runner, make_sample, out_dir):
    out = _convert(runner, make_sample("json"), "csv", out_dir).output
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_cp1252_csv_is_read_with_warning(runner, make_sample, out_dir):
    """Review #5: CSV from a Dutch Windows Excel."""
    src = make_sample("csv", text="naam;stad\nRené;Liège\n", encoding="cp1252")
    result = _convert(runner, src, "json", out_dir)
    assert json.loads(result.output.read_text(encoding="utf-8")) == [
        {"naam": "René", "stad": "Liège"}]
    assert any("Windows-1252" in w for w in result.warnings)


def test_csv_with_bom_has_clean_first_column(runner, make_sample, out_dir):
    """Review #5: no column called 'ï»¿id'."""
    src = make_sample("csv", text="﻿id,naam\n1,a\n")
    records = json.loads(_convert(runner, src, "json", out_dir).output.read_text("utf-8"))
    assert list(records[0]) == ["id", "naam"]


def test_semicolon_csv(runner, make_sample, out_dir):
    src = make_sample("csv", text="a;b\n1;2\n3;4\n")
    records = json.loads(_convert(runner, src, "json", out_dir).output.read_text("utf-8"))
    assert records == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_xml_rows_to_csv(runner, make_sample, out_dir):
    """Review #8: descend through <root><row> wrappers to the list."""
    df = _read_csv(_convert(runner, make_sample("xml"), "csv", out_dir).output)
    assert df.to_dict("records") == [{"id": "1", "naam": "Zoë"}, {"id": "2", "naam": "Jürgen"}]


def test_nested_json_becomes_dotted_columns(runner, make_sample, out_dir):
    df = _read_csv(_convert(runner, make_sample("json"), "csv", out_dir).output)
    assert "adres.stad" in df.columns
    assert df["adres.stad"].tolist() == ["Delft", "Gent"]


def test_json_scalar_to_csv_fails_readably(runner, make_sample, out_dir):
    src = make_sample("json", text="42")
    [result] = runner.run(Job("data", "csv", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert "lijst van records" in result.error


def test_list_to_toml_is_wrapped_and_nulls_dropped(runner, make_sample, out_dir):
    src = make_sample("json", text='[{"a": 1, "b": null}]')
    result = _convert(runner, src, "toml", out_dir)
    assert tomllib.loads(result.output.read_text("utf-8")) == {"rows": [{"a": 1}]}
    assert any("rows" in w for w in result.warnings)
    assert any("null" in w for w in result.warnings)


def test_json_to_xml_has_single_root_and_valid_names(runner, make_sample, out_dir):
    src = make_sample("json", text='[{"first name": "Ann", "2nd": true}]')
    result = _convert(runner, src, "xml", out_dir)
    parsed = xmltodict.parse(result.output.read_text("utf-8"))
    assert parsed == {"root": {"row": {"first_name": "Ann", "_2nd": "true"}}}


def test_xlsx_round_trip_and_extra_sheets_warn(runner, out_dir, tmp_path):
    src = tmp_path / "boek.xlsx"
    with pd.ExcelWriter(src) as xw:
        pd.DataFrame({"x": [1, 2]}).to_excel(xw, sheet_name="Eerste", index=False)
        pd.DataFrame({"y": [3]}).to_excel(xw, sheet_name="Tweede", index=False)
    result = _convert(runner, src, "json", out_dir)
    assert json.loads(result.output.read_text("utf-8")) == [{"x": 1}, {"x": 2}]
    assert any("Eerste" in w for w in result.warnings)


def test_yaml_is_loaded_safely(runner, make_sample, out_dir):
    src = make_sample("yaml", text="!!python/object/apply:os.system ['echo hacked']\n")
    [result] = runner.run(Job("data", "json", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert not result.error.startswith("Onverwachte fout")


@pytest.mark.parametrize("bad", ["{not json", "[1, 2"])
def test_broken_json_fails_readably(runner, make_sample, out_dir, bad):
    [result] = runner.run(Job("data", "yaml", [make_sample("json", text=bad)], out_dir),
                          CancelToken())
    assert result.status == "failed"
    assert result.error.startswith("Kan sample.json niet lezen")
