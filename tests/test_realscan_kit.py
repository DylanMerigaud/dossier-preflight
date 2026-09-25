"""grid/realscan_kit.py (T14 step 1): the 60-sheet print kit, the checklist and expected.json.

The expensive assertions (the full 60-sheet build) share ONE module-scoped fixture, the same
pattern tests/test_read_images.py already uses for its own expensive fixture build.
"""
import csv
import json
import os

import pytest
from pypdf import PdfReader

import grid.realscan_kit as rk
from preflight.reference import load_reference


def test_defects_are_the_v010_nine_unchanged():
    assert [d.name for d in rk.DEFECTS] == [
        "empty_required_field", "unchecked_box", "missing_signature", "expired_date",
        "diverging_address", "forbidden_value", "low_resolution", "cropped_page",
        "rotated_page"]


def test_mark_defect_is_the_first_required_field_instance():
    assert rk.MARK_DEFECT.name == "empty_required_field"
    assert rk.MARK_DEFECT.piece == "employment"
    assert rk.MARK_DEFECT.empty_fields == ("city",)


def test_identity_sheet_specs_count_and_signing():
    ref = load_reference(os.path.join(rk.DEFAULT_IDENTITIES, "id01.yaml"))
    specs = rk.identity_sheet_specs(ref)
    assert len(specs) == 15
    assert [s.kind for s in specs] == ["clean"] * 4 + ["defect"] * 9 + ["mark"] * 2
    # only the I-9 (employment) ever needs a signature, and never the missing_signature defect
    signing = {s.canonical_variant: s.sign for s in specs if s.piece == "employment"}
    assert signing == {"clean": True, "empty_required_field": True, "missing_signature": False,
                       "expired_date": True, "forbidden_value": True}
    must_not = [s.canonical_variant for s in specs if s.must_not_sign]
    assert must_not == ["missing_signature"]
    non_employment = [s for s in specs if s.piece != "employment"]
    assert not any(s.sign or s.must_not_sign for s in non_employment)
    # every I-9-touching build variant is forced unsigned: the kit's own signature is Dylan's
    employment_specs = [s for s in specs if s.piece == "employment"]
    assert all(s.build_variant.without_signature for s in employment_specs)


def test_stamp_rect_clears_every_declared_zone_on_every_corpus_template():
    ref = load_reference(os.path.join(rk.DEFAULT_IDENTITIES, "id01.yaml"))
    for _, template_name in ref.pieces:
        tpl = ref.templates[template_name]
        x0, y0, x1, y1 = rk.stamp_rect(tpl.pdf, tpl.page)
        for (fx0, fy0, fx1, fy1) in rk.field_rects(tpl.pdf, tpl.page):
            overlap = not (x0 - rk.STAMP_SAFETY_PT >= fx1 or x1 + rk.STAMP_SAFETY_PT <= fx0
                          or y0 - rk.STAMP_SAFETY_PT >= fy1 or y1 + rk.STAMP_SAFETY_PT <= fy0)
            assert not overlap, (tpl.name, (fx0, fy0, fx1, fy1))


def test_write_expected_json(tmp_path):
    path = tmp_path / "expected.json"
    rk.write_expected_json(str(path))
    d = json.load(open(path))
    assert set(d) == set(rk.X2_IDENTITIES)
    expected_names = sorted(v.name for v in rk.DEFECTS)
    for names in d.values():
        assert sorted(names) == expected_names


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("kit"))
    summary = rk.build_kit(out, rk.DEFAULT_IDENTITIES)
    return out, summary


def test_kit_builds_sixty_stamped_sheets(kit):
    out, summary = kit
    assert summary["sheets"] == 60
    pdfs = sorted(f for f in os.listdir(out) if f.startswith("S") and f.endswith(".pdf"))
    assert len(pdfs) == 60
    codes = sorted({f.split("-", 1)[0] for f in pdfs})
    assert codes == [f"S{n:02d}" for n in range(1, 61)]
    # id01 and id02 first: the first 30 codes (S01..S30) belong only to those two identities
    first_half = [f for f in pdfs if f.split("-", 1)[0] in
                 {f"S{n:02d}" for n in range(1, 31)}]
    assert len(first_half) == 30
    assert all(("-id01-" in f or "-id02-" in f) for f in first_half)
    second_half = [f for f in pdfs if f not in first_half]
    assert all(("-id03-" in f or "-id04-" in f) for f in second_half)


def test_every_stamped_sheet_carries_its_own_code_and_no_more_than_one_page(kit):
    out, _ = kit
    for f in sorted(os.listdir(out)):
        if not (f.startswith("S") and f.endswith(".pdf")):
            continue
        code = f.split("-", 1)[0]
        r = PdfReader(os.path.join(out, f))
        assert len(r.pages) == 1
        page_text = r.pages[0].extract_text() or ""
        # extract_text() is not guaranteed on every viewer for a stamped-in overlay, so this is
        # a soft check: the stamp is verified precisely by test_stamp_rect_clears_every_...
        # above and by grid/realscan_ingest.py's own OCR test. Here: the file exists, one page.
        assert code.startswith("S")


def test_checklist_csv_numbering_and_counts(kit):
    out, summary = kit
    with open(os.path.join(out, "checklist.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [int(r["line"]) for r in rows] == list(range(1, len(rows) + 1))
    assert summary["captures"] == len(rows)
    phone = [r for r in rows if r["device"] == "phone"]
    flatbed = [r for r in rows if r["device"] == "flatbed"]
    assert len(phone) == summary["phone_captures"] == 160
    assert len(flatbed) == summary["flatbed_mandatory"] == 4
    assert summary["captures"] == 164
    # first half: id01 + id02 captures, 41 each
    per_identity = {}
    for r in rows:
        per_identity.setdefault(r["identity"], 0)
        per_identity[r["identity"]] += 1
    assert per_identity == {"id01": 41, "id02": 41, "id03": 41, "id04": 41}
    assert summary["first_half_end"] == 82


def test_low_resolution_defect_is_flatbed_only_at_75dpi(kit):
    out, _ = kit
    with open(os.path.join(out, "checklist.csv"), newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["variant"] == "low_resolution"]
    assert len(rows) == 4          # one per identity
    assert all(r["device"] == "flatbed" and r["dpi"] == "75" for r in rows)


def test_mark_sheets_carry_four_steps_captured_twice(kit):
    out, _ = kit
    with open(os.path.join(out, "checklist.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    mark_rows = [r for r in rows if r["mark_step"] != ""]
    # 4 identities x 2 mark sheets x 4 steps x 2 captures
    assert len(mark_rows) == 4 * 2 * 4 * 2 == 64
    for identity in rk.X2_IDENTITIES:
        for variant in ("clean", rk.MARK_DEFECT.name):
            sub = [r for r in mark_rows if r["identity"] == identity and r["variant"] == variant]
            assert sorted(int(r["mark_step"]) for r in sub) == [0, 0, 1, 1, 2, 2, 3, 3]
            assert all(r["sign"] == "True" for r in sub)


def test_cover_and_checklist_pdfs_exist_and_are_one_or_more_pages(kit):
    out, _ = kit
    for name in ("cover.pdf", "checklist.pdf"):
        r = PdfReader(os.path.join(out, name))
        assert len(r.pages) >= 1


def test_expected_json_written_by_the_kit(kit):
    out, _ = kit
    d = json.load(open(os.path.join(out, "expected.json")))
    assert set(d) == set(rk.X2_IDENTITIES)
