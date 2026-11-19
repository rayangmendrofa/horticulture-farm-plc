"""Electrical drawings and I/O checkout sheet are consistent and up to date (phase 5)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "drawings"))


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    import make_drawings as M
    out = tmp_path_factory.mktemp("drawings")
    M.OUT_DIR, M.CHECKOUT_MD = out, out / "IO_CHECKOUT.md"
    assert M.main() == 0, "consistency checks failed (see output)"
    return M, out


def test_drw01_consistency(generated):
    """I/O matches farmsim/tags.py, every cross-reference resolves, every terminal is drawn and in the plan,
    every drawn device is in the parts list."""
    M, _ = generated
    assert M.consistency_checks() == []
    assert len(M.TERMINALS) == len({(t[0], t[1]) for t in M.TERMINALS}), "duplicate terminal"


def test_drw02_committed_outputs_are_current(generated):
    """docs/drawings and docs/IO_CHECKOUT.md are generated: rerun tools/drawings/make_drawings.py after a change."""
    M, out = generated
    for f in sorted(out.glob("GH1-E-*.svg")) + [out / "README.md"]:
        committed = ROOT / "docs" / "drawings" / f.name
        assert committed.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"), f.name
    assert (ROOT / "docs" / "IO_CHECKOUT.md").read_text(encoding="utf-8") == \
        (out / "IO_CHECKOUT.md").read_text(encoding="utf-8")


def test_drw03_checkout_covers_every_channel(generated):
    from farmsim import tags
    text = (generated[1] / "IO_CHECKOUT.md").read_text(encoding="utf-8")
    for tag in tags.DI_TAGS + tags.DO_TAGS + tags.AI_TAGS[:15] + tags.AO_TAGS:
        assert f"`{tag}`" in text, tag
