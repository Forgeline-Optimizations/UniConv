import json

import pytest
from pydantic import ValidationError

from uniconv.config import AppConfig, load_config, save_user_overrides, write_reference_copy


def test_missing_file_gives_code_defaults(tmp_path):
    cfg = load_config(tmp_path / "config.json")
    assert cfg == AppConfig()
    assert cfg.behavior.overwrite == "rename"


def test_override_wins_and_rest_stays_default(tmp_path):
    f = tmp_path / "config.json"
    f.write_text(json.dumps({"behavior": {"overwrite": "skip"}}), encoding="utf-8")
    cfg = load_config(f)
    assert cfg.behavior.overwrite == "skip"
    assert cfg.limits.timeout_seconds == 900


@pytest.mark.parametrize("content", ['{"behavior": {"bogus": 1}}', "{not json", '{"version": "x"}'])
def test_invalid_file_is_moved_aside_and_defaults_are_used(tmp_path, content):
    f = tmp_path / "config.json"
    f.write_text(content, encoding="utf-8")
    cfg = load_config(f)
    assert cfg == AppConfig()
    assert not f.exists()
    assert (tmp_path / "config.invalid.json").read_text(encoding="utf-8") == content


def test_save_user_overrides_writes_only_the_change(tmp_path):
    f = tmp_path / "sub" / "config.json"
    save_user_overrides(f, {"paths": {"output_mode": "beside_source"}})
    save_user_overrides(f, {"behavior": {"overwrite": "overwrite"}})
    assert json.loads(f.read_text(encoding="utf-8")) == {
        "paths": {"output_mode": "beside_source"},
        "behavior": {"overwrite": "overwrite"},
    }


def test_save_user_overrides_refuses_invalid_value_without_touching_file(tmp_path):
    f = tmp_path / "config.json"
    f.write_text('{"behavior": {"overwrite": "skip"}}', encoding="utf-8")
    with pytest.raises(ValidationError):
        save_user_overrides(f, {"behavior": {"overwrite": "sometimes"}})
    assert json.loads(f.read_text(encoding="utf-8")) == {"behavior": {"overwrite": "skip"}}


def test_reference_copy_lists_family_defaults(tmp_path, registry):
    write_reference_copy(tmp_path, registry.default_options())
    ref = json.loads((tmp_path / "config.defaults.json").read_text(encoding="utf-8"))
    assert ref["limits"]["max_input_mb"] == 4096
    assert ref["defaults"]["image"]["jpeg_quality"] == 90
