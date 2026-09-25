"""grid/realscan_ingest.py (T14 "after G2" step 1): pairing, EXIF stripping, mark_ink_share.

EVERY CAPTURE IN THIS FILE IS SYNTHETIC (T14's own scope: no real photograph exists yet, G1 is
Dylan's and this runs before he has answered it). A synthetic capture is one of
grid/realscan_kit.py's own built PDF sheets, rendered to a raster, given a fabricated EXIF block
with GPS, and rotated slightly: exactly the recipe named in the task, never a hand-drawn stand-in
image with no relation to a real capture's actual pipeline.
"""
import csv
import datetime as dt
import os

import numpy as np
import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

import grid.realscan_ingest as ing
import grid.realscan_kit as rk
from preflight.fixtures import CLEAN, build
from preflight.reference import load_reference
from preflight.render import render
from preflight.sensors import normalize


# ---------------------------------------------------------------------------------------------
# align_sequences: pure logic, no images
# ---------------------------------------------------------------------------------------------

def test_align_sequences_straight_match():
    obs = exp = ["S01", "S02", "S03"]
    pairs, uo, ue = ing.align_sequences(obs, exp)
    assert pairs == [(0, 0), (1, 1), (2, 2)]
    assert uo == [] and ue == []


def test_align_sequences_one_missing_capture():
    expected = ["S01", "S02", "S03", "S04"]
    observed = ["S01", "S02", "S04"]                  # S03 was never captured
    pairs, uo, ue = ing.align_sequences(observed, expected)
    assert pairs == [(0, 0), (1, 1), (2, 3)]
    assert uo == [] and ue == [2]


def test_align_sequences_one_duplicate_capture():
    expected = ["S01", "S02", "S03"]
    observed = ["S01", "S02", "S02", "S03"]            # S02 captured twice by mistake
    pairs, uo, ue = ing.align_sequences(observed, expected)
    assert pairs == [(0, 0), (1, 1), (3, 2)]
    assert uo == [2] and ue == []


def test_align_sequences_unreadable_code_with_no_single_shift_explanation():
    expected = ["S01", "S02", "S03"]
    observed = ["S01", None, "S03"]                    # S02 unreadable, not a shift
    pairs, uo, ue = ing.align_sequences(observed, expected)
    assert pairs == [(0, 0), (2, 2)]
    assert uo == [1] and ue == [1]


def test_align_sequences_never_guesses_an_ambiguous_shift():
    # both a drop-observed and a drop-expected shift would "work": neither is trusted alone.
    expected = ["S01", "S02"]
    observed = ["S01", "S02", "S02"]
    pairs, uo, ue = ing.align_sequences(observed, expected)
    # position 0 agrees; position 1 is where n != m first shows, handled by the fallback
    assert (0, 0) in pairs


def test_name_matches_is_substring_lenient():
    assert ing._name_matches("aurelien boucharenc", "boucharenc")
    assert not ing._name_matches("someone else", "boucharenc")
    assert not ing._name_matches("", "boucharenc")
    assert not ing._name_matches("boucharenc", "")


# ---------------------------------------------------------------------------------------------
# Synthetic captures: a kit sheet rendered, fake EXIF+GPS added, rotated slightly
# ---------------------------------------------------------------------------------------------

def _fake_exif(when="2026:09:26 08:00:00"):
    exif = Image.Exif()
    exif[306] = when
    exif[36867] = when
    exif[34853] = {1: "N", 2: (IFDRational(48, 1), IFDRational(51, 1), IFDRational(0, 1)),
                  3: "E", 4: (IFDRational(2, 1), IFDRational(21, 1), IFDRational(0, 1))}
    return exif


def _synthetic_capture(pdf_path, dest_path, when, rotate_deg=0.7):
    """A kit sheet, rendered, rotated a little, saved as a JPEG with a fabricated EXIF+GPS
    block: what a real phone photo's metadata looks like, never a real photograph.

    `expand=False`: a real capture goes through Apple Notes' "Scan Documents" (or the flatbed's
    own glass edge), both of which detect the document's own boundary and hand back a rectangle
    at the page's own aspect ratio, not a raw photo with the sensor's full field of view padded
    around a tilted page. expand=True would model the latter, and it moves the page's own
    corners inward from the image's own corners by an amount that grows with the canvas
    padding, which is exactly what a scanning app's own crop step removes before dossier-
    preflight or grid/realscan_ingest.py ever sees the file.
    """
    grey = render(pdf_path, dpi=300, page=1)
    img = Image.fromarray(grey).convert("L")
    if rotate_deg:
        img = img.rotate(rotate_deg, resample=Image.BICUBIC, fillcolor=255, expand=False)
    img.save(dest_path, exif=_fake_exif(when).tobytes())
    return dest_path


@pytest.fixture(scope="module")
def stamped_sheets(tmp_path_factory):
    """Two real kit sheets (id01's employment piece, clean and empty_required_field), stamped
    exactly as grid/realscan_kit.py stamps the real kit, PLUS their sheet codes: the minimum
    needed to exercise pairing, identity OCR and mark_ink_share without paying for the full
    60-sheet build test_realscan_kit.py already covers."""
    build_dir = str(tmp_path_factory.mktemp("build"))
    out_dir = str(tmp_path_factory.mktemp("sheets"))
    ref = load_reference(os.path.join(rk.DEFAULT_IDENTITIES, "id01.yaml"))
    clean_var = rk.replace(CLEAN, name="clean_unsigned", piece="employment",
                           without_signature=True)
    empty_var = rk.replace(rk.MARK_DEFECT, name="mark_empty", without_signature=True)
    clean_pdf = build(ref, clean_var, build_dir, reuse=False).piece("employment").pdf
    empty_pdf = build(ref, empty_var, build_dir, reuse=False).piece("employment").pdf
    clean_out = os.path.join(out_dir, "S01.pdf")
    empty_out = os.path.join(out_dir, "S02.pdf")
    rk.stamp_pdf(clean_pdf, clean_out, "S01")
    rk.stamp_pdf(empty_pdf, empty_out, "S02")
    return {"clean": clean_out, "empty": empty_out, "ref": ref, "out_dir": out_dir}


def test_capture_time_reads_exif_before_any_stripping(stamped_sheets, tmp_path):
    capture = _synthetic_capture(stamped_sheets["clean"], str(tmp_path / "cap.jpg"),
                                 "2026:09:26 08:15:30", rotate_deg=0)
    ts = ing.capture_time(capture)
    assert ts == dt.datetime(2026, 9, 26, 8, 15, 30, tzinfo=dt.timezone.utc)


def test_capture_time_falls_back_to_mtime_with_no_exif(tmp_path):
    p = tmp_path / "plain.png"
    Image.fromarray(np.full((10, 10), 255, dtype="uint8")).save(p)
    ts = ing.capture_time(str(p))
    assert abs((ts - dt.datetime.now(dt.timezone.utc)).total_seconds()) < 60


def test_render_and_strip_exif_removes_gps(stamped_sheets, tmp_path):
    capture = _synthetic_capture(stamped_sheets["clean"], str(tmp_path / "cap.jpg"),
                                 "2026:09:26 08:00:00", rotate_deg=0.7)
    assert Image.open(capture).getexif()          # the fixture actually carries EXIF
    png = ing.render_to_png(capture, str(tmp_path / "rendered"))
    ing.strip_exif(png)
    assert not Image.open(png).getexif()


def test_strip_exif_raises_if_it_somehow_survived(tmp_path, monkeypatch):
    """The guard is not decorative: if the re-save somehow still left EXIF behind (a future
    Pillow default change, an unexpected format), strip_exif() must refuse rather than hand
    back a file it did not actually verify."""
    p = tmp_path / "sneaky.jpg"
    Image.fromarray(np.full((10, 10), 255, dtype="uint8")).save(p, exif=_fake_exif().tobytes())
    real_open = Image.open
    calls = {"n": 0}

    def open_that_lies_on_the_verification_read(path, *a, **kw):
        calls["n"] += 1
        im = real_open(path, *a, **kw)
        if calls["n"] >= 2:      # the post-save verification call in strip_exif()
            monkeypatch.setattr(im, "getexif", lambda: {34853: "still here"})
        return im

    monkeypatch.setattr(ing.Image, "open", open_that_lies_on_the_verification_read)
    with pytest.raises(RuntimeError, match="EXIF survived"):
        ing.strip_exif(str(p))


def test_ocr_sheet_code_reads_the_stamp_through_a_slight_rotation(stamped_sheets, tmp_path):
    capture = _synthetic_capture(stamped_sheets["clean"], str(tmp_path / "cap.jpg"),
                                 "2026:09:26 08:00:00", rotate_deg=0.7)
    png = ing.render_to_png(capture, str(tmp_path / "rendered"))
    assert ing.ocr_sheet_code(png) == "S01"


def test_ocr_identity_name_matches_id01(stamped_sheets, tmp_path):
    capture = _synthetic_capture(stamped_sheets["clean"], str(tmp_path / "cap.jpg"),
                                 "2026:09:26 08:00:00", rotate_deg=0)
    png = ing.render_to_png(capture, str(tmp_path / "rendered"))
    ref = stamped_sheets["ref"]
    template = ref.templates[dict(ref.pieces)["employment"]]
    observed = ing.ocr_identity_name(png, template)
    assert ing._name_matches(observed, normalize(ref.person["name"]))


# ---------------------------------------------------------------------------------------------
# End to end: a small checklist.csv, a small incoming/ folder, build_manifest()
# ---------------------------------------------------------------------------------------------

CHECKLIST_HEADER = rk.CAPTURE_FIELDS


def _write_checklist(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHECKLIST_HEADER)
        w.writeheader()
        w.writerows(rows)


def _row(line, code, identity, piece, variant, instance, mark_step, device, dpi, idx, sign,
        must_not_sign):
    return {"line": line, "sheet_code": code, "identity": identity, "piece": piece,
           "variant": variant, "instance": instance, "mark_step": mark_step, "device": device,
           "dpi": dpi, "capture_index": idx, "sign": sign, "must_not_sign": must_not_sign,
           "physical_action": "", "label": f"{piece} {variant}"}


def test_build_manifest_end_to_end_on_synthetic_captures(stamped_sheets, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    checklist = tmp_path / "checklist.csv"
    out_manifest = tmp_path / "manifest.csv"

    rows = [
        _row(1, "S01", "id01", "employment", "clean", "", "", "phone", 300, 1, True, False),
        _row(2, "S01", "id01", "employment", "clean", "", "", "phone", 300, 2, True, False),
        _row(3, "S02", "id01", "employment", "empty_required_field", "city", "", "phone", 300,
             1, True, False),
    ]
    _write_checklist(checklist, rows)

    _synthetic_capture(stamped_sheets["clean"], str(incoming / "img1.jpg"),
                       "2026:09:26 08:00:00", rotate_deg=0.4)
    _synthetic_capture(stamped_sheets["clean"], str(incoming / "img2.jpg"),
                       "2026:09:26 08:00:05", rotate_deg=-0.3)
    _synthetic_capture(stamped_sheets["empty"], str(incoming / "img3.jpg"),
                       "2026:09:26 08:00:10", rotate_deg=0.2)

    summary = ing.build_manifest(str(incoming), str(checklist), str(out_manifest),
                                 identities_dir=rk.DEFAULT_IDENTITIES)
    assert summary["captures"] == 3
    assert summary["paired"] == 3
    assert summary["excluded"] == 0

    with open(out_manifest, newline="", encoding="utf-8") as f:
        manifest_rows = list(csv.DictReader(f))
    assert len(manifest_rows) == 3
    for r in manifest_rows:
        assert r["source"] == "x2" and r["identity"] == "id01" and r["piece"] == "employment"
        assert r["seed"] == ""
        assert r["dpi"] == "300"
        # capture time survives into ts, in ISO 8601
        dt.datetime.fromisoformat(r["ts"])
    variants = sorted(r["variant"] for r in manifest_rows)
    assert variants == ["clean", "clean", "empty_required_field"]


def test_build_manifest_reports_a_missing_capture(stamped_sheets, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    checklist = tmp_path / "checklist.csv"
    out_manifest = tmp_path / "manifest.csv"
    rows = [
        _row(1, "S01", "id01", "employment", "clean", "", "", "phone", 300, 1, True, False),
        _row(2, "S02", "id01", "employment", "empty_required_field", "city", "", "phone", 300,
             1, True, False),
    ]
    _write_checklist(checklist, rows)
    # only S02 was ever captured: S01's checklist line has no photo
    _synthetic_capture(stamped_sheets["empty"], str(incoming / "img1.jpg"),
                       "2026:09:26 08:00:00", rotate_deg=0)

    summary = ing.build_manifest(str(incoming), str(checklist), str(out_manifest),
                                 identities_dir=rk.DEFAULT_IDENTITIES)
    assert summary["captures"] == 1
    assert summary["paired"] == 1
    assert summary["excluded"] == 1
    with open(str(out_manifest) + ".excluded.jsonl", encoding="utf-8") as f:
        import json
        excl = [json.loads(l) for l in f]
    assert excl[0]["reason"] == "checklist line has no capture"


def test_mark_ink_share_measures_against_step_zero_not_the_blank(stamped_sheets, tmp_path):
    """A pen stroke added to the SAME sheet between step 0 and step 1 must read a positive
    share; the identical image against itself must read ~0."""
    ref = stamped_sheets["ref"]
    template = ref.templates[dict(ref.pieces)["employment"]]
    field_ids = template.field_ids("city")

    step0_png = str(tmp_path / "step0.png")
    step1_png = str(tmp_path / "step1.png")
    grey = render(stamped_sheets["empty"], dpi=300, page=1)
    Image.fromarray(grey).convert("L").save(step0_png)

    # a synthetic "pen stroke": darken a small block inside the city field's own canonical zone
    from preflight.deskew import prepare
    from preflight.reading import blank as blank_fn
    blank_img, _, zones, _ = blank_fn(template)
    prep = prepare(grey, blank_img)
    z = prep.frame.zone(zones[field_ids[0]])
    marked = grey.copy()
    cy, cx = (z.y0 + z.y1) // 2, (z.x0 + z.x1) // 2
    marked[cy - 4:cy + 4, cx - 10:cx + 10] = 0
    Image.fromarray(marked).convert("L").save(step1_png)

    share_same = ing.step_mark_ink_share(step0_png, step0_png, template, field_ids)
    share_marked = ing.step_mark_ink_share(step1_png, step0_png, template, field_ids)
    assert share_same == 0.0
    assert share_marked > share_same
    assert share_marked > 0.0
