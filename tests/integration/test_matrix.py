"""Every offered pair must produce a valid file. New formats are tested automatically."""

import filetype
import pytest

from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job
from uniconv.core.registry import build_default_registry

_REG = build_default_registry()
PAIRS = [
    (family, src, dst)
    for family, _ in _REG.families()
    for src in _REG.sources(family)
    for dst in _REG.targets(family, src)
]
# filetype cannot tell these apart from their container; checked by extension only.
_NO_MAGIC_CHECK: set[str] = set()


@pytest.mark.parametrize(("family", "src", "dst"), PAIRS, ids=lambda v: str(v))
def test_conversion_pair(family, src, dst, runner, make_sample, out_dir):
    sample = make_sample(src)
    [result] = runner.run(Job(family, dst, [sample], out_dir), CancelToken())

    assert result.status == "done", result.error
    assert result.output.parent == out_dir
    assert result.output.stat().st_size > 0
    fmt = _REG.format(dst)
    assert result.output.suffix == fmt.extensions[0]
    if fmt.mimes and dst not in _NO_MAGIC_CHECK:
        kind = filetype.guess(str(result.output))
        assert kind is not None and kind.mime in fmt.mimes
