"""grid/read_images.py: images read through the production path, in the grid's schema (T09).

The claim to hold: a raster fed to read_images is read EXACTLY as the command line reads the
PDF it was rasterised from. The only replaced step is the rasterisation itself, and the test
below shows it returns the same pixels render() would.
"""
import csv
import json
import os
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image

import grid.read_images as ri
import preflight.reading as production_reading
from preflight.__main__ import PRISTINE, ScannedPiece
from preflight.fixtures import build
from preflight.reading import read_piece
from preflight.render import render

ID = "id01"


@pytest.fixture(scope="module")
def id01_page(tmp_path_factory):
    """id01's clean W-9 as a PDF, and the raster render() makes of it at 200 dpi."""
    refs = ri.load_identities(ri.DEFAULT_IDENTITIES)
    ref = refs[ID]
    dest = str(tmp_path_factory.mktemp("t09"))
    piece = build(ref, "clean", dest).piece("tax")
    png = os.path.join(dest, "tax_dpi200.png")
    Image.fromarray(render(piece.pdf, dpi=200, page=piece.template.page)).save(png)
    return ref, piece, png


@pytest.fixture
def patched(monkeypatch):
    """ri._init() swaps preflight.reading.render; registering the original first makes the
    swap undone after the test."""
    monkeypatch.setattr(production_reading, "render", production_reading.render)
    ri._init(ri.DEFAULT_IDENTITIES)


def test_the_raster_adapter_returns_what_render_returns(id01_page):
    _, piece, png = id01_page
    assert np.array_equal(ri.raster_render(png, dpi=200),
                          render(piece.pdf, dpi=200, page=piece.template.page))
    # anything that is not a raster goes to the original, untouched
    assert np.array_equal(ri.raster_render(piece.pdf, dpi=200, page=piece.template.page),
                          render(piece.pdf, dpi=200, page=piece.template.page))


def _row(png, **over):
    row = {"image_path": png, "source": "g1", "identity": ID, "piece": "tax",
           "variant": "clean", "instance": "", "seed": "11", "dpi": "200", "capture": "",
           "mark_step": "", "ts": "2026-09-25T00:00:00+00:00", "field_ink_share": ""}
    row.update(over)
    return row


def test_a_raster_reads_exactly_as_the_command_line_reads_its_pdf(id01_page, patched):
    ref, piece, png = id01_page
    scanned = ScannedPiece("tax", piece.template, piece.pdf)
    truth = read_piece(scanned, replace(PRISTINE, dpi=200))          # python -m preflight
    line = ri.read_row(_row(png))
    assert "error" not in line, line.get("traceback")
    # compared as the JSONL holds it (tuples become lists), the form the analysis reads
    assert json.loads(json.dumps(line["reading"])) == json.loads(json.dumps(truth.dict()))
    # the grid schema, plus the source, the key fields and a ts
    for k in ("angle", "dpi", "jpeg", "sigma", "seed", "parasite", "identity", "variant",
              "piece", "seconds", "reading", "source", "jitter", "capture", "mark_step", "ts"):
        assert k in line, k
    assert (line["angle"], line["jpeg"], line["sigma"]) == (PRISTINE.angle, PRISTINE.jpeg,
                                                            PRISTINE.sigma)
    assert line["dpi"] == 200 and line["seed"] == 11 and line["source"] == "g1"
    assert line["capture"] is None and line["mark_step"] is None
    assert line["field_ink_share"] is None
    o = line["orientation"]
    assert o["quarter_turns"] == truth.quarter_turns and o["peak"] == truth.peak
    assert o["expected_quarter_turns"] == 0 and o["wrong_quarter_turn"] is False


def test_expected_quarter_turns():
    refs = ri.load_identities(ri.DEFAULT_IDENTITIES)
    cat = ri.catalog_of(refs)[ID]
    rotated = cat["rotated_page@tax"]
    assert ri.expected_quarter_turns(rotated, "g1") == 3      # what the published grid reads
    assert ri.expected_quarter_turns(rotated, "x2") is None   # turned by hand, direction unknown
    assert ri.expected_quarter_turns(cat["clean"], "g1") == 0
    assert ri.expected_quarter_turns(None, "x2") == 0


def _manifest(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_the_manifest_is_checked_before_anything_is_read(id01_page, tmp_path):
    refs = ri.load_identities(ri.DEFAULT_IDENTITIES)
    _, _, png = id01_page
    m = tmp_path / "m.csv"
    _manifest(m, [_row(png), _row(png)])
    with pytest.raises(SystemExit, match="same key"):
        ri.load_manifest(str(m), refs)
    _manifest(m, [_row(png, variant="no_such_variant")])
    with pytest.raises(SystemExit, match="unknown variant"):
        ri.load_manifest(str(m), refs)
    _manifest(m, [_row(png, source="g9")])
    with pytest.raises(SystemExit, match="source"):
        ri.load_manifest(str(m), refs)
    _manifest(m, [_row(str(tmp_path / "missing.png"))])
    with pytest.raises(SystemExit, match="image not found"):
        ri.load_manifest(str(m), refs)


def test_resume_skips_what_is_already_read(id01_page, tmp_path, capsys):
    _, _, png = id01_page
    m, out = tmp_path / "m.csv", tmp_path / "out.jsonl"
    _manifest(m, [_row(png), _row(png, seed="23")])
    assert ri.main([str(m), str(out), "--workers", "1", "--limit", "1"]) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    first = json.loads(lines[0])
    assert ri.row_key(first) == ri.row_key(_row(png)) or \
        ri.row_key(first) == ri.row_key(_row(png, seed="23"))
    capsys.readouterr()
    assert ri.main([str(m), str(out), "--workers", "1"]) == 0
    assert "1 already read, 1 to read" in capsys.readouterr().out
    assert len(out.read_text().splitlines()) == 2
    assert ri.main([str(m), str(out), "--workers", "1"]) == 0
    assert "2 already read, 0 to read" in capsys.readouterr().out
