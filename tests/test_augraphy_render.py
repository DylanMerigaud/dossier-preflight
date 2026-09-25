"""grid/augraphy_render.py (T11, arm A3): the pure logic, plus one augraphy-dependent smoke
test.

Most of this file needs no augraphy at all: which field a variant targets, what "fired" means
in augraphy's own log format, and the field_ink_share registration math are ordinary Python and
dossier-preflight code, so they run under the MAIN venv's `pytest tests -q` like everything
else. The one test that calls augment_one() needs the real package and is skipped there
(pytest.importorskip), and runs for real only under `.venv-augraphy`.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grid.augraphy_render import (augmentations_fired, field_ink_share, page_transform,
                                  pages_to_render, render_dpi_for, target_role_and_fields)
from preflight.degradation import Degradation
from preflight.fixtures import CLEAN, build, enumerate_variants
from preflight.geometry import declared_zones, page_size
from preflight.reference import load_reference
from preflight.templates import load as load_template


def test_augmentations_fired_keeps_only_true_non_wrapper():
    log = {"augmentation_name": ["InkColorSwap", "LinesDegradation", "OneOf", "Dithering",
                                 "AugmentationSequence", "Folding"],
          "augmentation_status": [True, False, True, True, True, True]}
    assert augmentations_fired(log) == ["Dithering", "Folding", "InkColorSwap"]


def test_augmentations_fired_handles_no_log():
    assert augmentations_fired(None) == []
    assert augmentations_fired({}) == []


def test_target_role_and_fields_required_field_is_the_emptied_role():
    tpl = load_template("fw9")
    var = next(v for v in enumerate_variants(load_reference())
              if v.check == "required_field" and v.piece == "tax" and v.empty_fields == ("tax_id",))
    role, field_ids = target_role_and_fields(var, tpl)
    assert role == "tax_id"
    # the W-9 combs the tax number over three boxes: the target is every one of them.
    assert field_ids == ("f1_11[0]", "f1_12[0]", "f1_13[0]")
    assert all(f in declared_zones(tpl.pdf, tpl.page) for f in field_ids)


def test_target_role_and_fields_checkbox_signature_expiry():
    ref = load_reference()
    variants = enumerate_variants(ref)
    tpl_i9 = load_template("i9")

    box = next(v for v in variants if v.check == "required_checkbox" and v.piece == "employment")
    role, field_ids = target_role_and_fields(box, tpl_i9)
    assert role == "status" and field_ids == (tpl_i9.boxes["status"],)

    sig = next(v for v in variants if v.check == "signature")
    role, field_ids = target_role_and_fields(sig, tpl_i9)
    assert role == "employee" and field_ids == (tpl_i9.signatures["employee"],)

    exp = next(v for v in variants if v.check == "expiry" and ".1d" in v.name)
    role, field_ids = target_role_and_fields(exp, tpl_i9)
    assert role == "expiry_date"
    assert field_ids == tpl_i9.field_ids("expiry_date")


def test_target_role_and_fields_null_for_clean_and_page_geometry():
    ref = load_reference()
    tpl = load_template("fw9")
    assert target_role_and_fields(CLEAN, tpl) == (None, ())
    low_res = next(v for v in enumerate_variants(ref)
                   if v.check == "resolution" and v.piece == "tax")
    assert target_role_and_fields(low_res, tpl) == (None, ())


def test_pages_to_render_is_49_for_the_shipped_reference():
    # 4 clean pieces + 45 single-defect instances, prereg-v1 section 3.2's arithmetic.
    assert len(pages_to_render(load_reference())) == 49


def test_page_transform_is_a_noop_without_an_override(tmp_path):
    ref = load_reference()
    d = build(ref, CLEAN, str(tmp_path))
    piece = next(p for p in d.pieces if p.id == "tax")
    from preflight.render import render
    raw = render(piece.pdf, dpi=150, page=piece.template.page)
    out = page_transform(piece, 150)
    assert np.array_equal(raw, out), "no crop or quarter turn: the render must pass through"


def test_page_transform_applies_crop_and_quarter_turns(tmp_path):
    ref = load_reference()
    variants = enumerate_variants(ref)
    cropped = next(v for v in variants if v.check == "cropped_page" and v.piece == "tax")
    rotated = next(v for v in variants if v.check == "rotated_page" and v.piece == "tax")

    d = build(ref, cropped, str(tmp_path))
    piece = next(p for p in d.pieces if p.id == "tax")
    out = page_transform(piece, 150)
    from preflight.render import render
    raw = render(piece.pdf, dpi=150, page=piece.template.page)
    assert out.shape[0] < raw.shape[0] and out.shape[1] == raw.shape[1]

    d = build(ref, rotated, str(tmp_path))
    piece = next(p for p in d.pieces if p.id == "tax")
    out = page_transform(piece, 150)
    raw = render(piece.pdf, dpi=150, page=piece.template.page)
    assert out.shape == (raw.shape[1], raw.shape[0]), "one quarter turn swaps H and W"


def test_render_dpi_for_overrides_only_when_declared():
    class P:
        image_override = {}
    assert render_dpi_for(P(), 200) == 200
    P.image_override = {"dpi": 72}
    assert render_dpi_for(P(), 200) == 72


def test_field_ink_share_finds_ink_inside_the_zone_and_not_outside():
    """The registration math, without Augraphy: draw a dark patch inside the W-9 name field's
    own declared zone in a synthetic "augmented" copy of a blank white page, none of it
    outside, and check field_ink_share reports a large share for that field and (on a second
    page with the patch moved outside the zone) None or a near-zero share elsewhere."""
    tpl = load_template("fw9")
    dpi = 150
    w, h = page_size(tpl.pdf, tpl.page, dpi)
    zone = declared_zones(tpl.pdf, tpl.page, dpi)["f1_01[0]"]   # the "name" field

    reference = np.full((h, w), 255, dtype=np.uint8)
    # A plain white page has no ink at all: Otsu's threshold search (used by deskew/register)
    # is undefined on a perfectly uniform image. A thin printed-looking border, well clear of
    # the watched zone, gives it something real to lock onto, the way an actual form page does.
    reference[10:14, :] = 0
    reference[-14:-10, :] = 0
    reference[:, 10:14] = 0
    reference[:, -14:-10] = 0
    augmented_inside = reference.copy()
    augmented_inside[zone.y0:zone.y1, zone.x0:zone.x1] = 0

    share = field_ink_share(augmented_inside, reference, tpl.pdf, tpl.page, dpi, ("f1_01[0]",))
    assert share is not None and share > 0.9, "painting the whole zone black must read close to 1.0"

    augmented_outside = reference.copy()
    oy0, oy1 = min(h - 1, zone.y1 + 40), min(h, zone.y1 + 80)
    if oy1 > oy0:
        augmented_outside[oy0:oy1, zone.x0:zone.x1] = 0
    share_outside = field_ink_share(augmented_outside, reference, tpl.pdf, tpl.page, dpi,
                                    ("f1_01[0]",))
    assert share_outside is not None and share_outside < 0.05, \
        "ink drawn outside the zone must not count as ink inside it"


def test_field_ink_share_is_locked_to_axis_zero_and_quarter_zero():
    """Regression for the bug measured on the full A3 run: about 15 percent of rows that
    should carry a field_ink_share came back None because prepare()'s own axis search (built
    for a possibly-misoriented real scan) locked onto a texture's vertical grain instead of the
    page's actual horizontal lines, and the target zone landed entirely off-frame. The fix reads
    the axes and quarters field_ink_share actually passes to deskew()/register(), which is the
    real guarantee (the two images being compared are the SAME page before and after Augraphy,
    so no rotation between them is possible by construction); a call spy proves the source has
    not drifted back to the unrestricted prepare() path."""
    import grid.augraphy_render as mod

    calls = []
    real_deskew = mod.deskew

    def spy_deskew(grey, *a, **k):
        calls.append(k.get("axes", a[0] if a else None))
        return real_deskew(grey, *a, **k)

    tpl = load_template("fw9")
    dpi = 150
    zone = declared_zones(tpl.pdf, tpl.page, dpi)["f1_01[0]"]
    page = np.full(page_size(tpl.pdf, tpl.page, dpi)[::-1], 255, dtype=np.uint8)
    page[10:14, :] = 0
    page[:, 10:14] = 0
    augmented = page.copy()
    augmented[zone.y0:zone.y1, zone.x0:zone.x1] = 0

    mod.deskew = spy_deskew
    try:
        share = field_ink_share(augmented, page, tpl.pdf, tpl.page, dpi, ("f1_01[0]",))
    finally:
        mod.deskew = real_deskew

    assert calls == [(0,)], "field_ink_share must call deskew() with axes=(0,) only"
    assert share is not None and share > 0.8


def test_field_ink_share_none_with_no_field_ids():
    tpl = load_template("fw9")
    page = np.full((100, 100), 255, dtype=np.uint8)
    assert field_ink_share(page, page, tpl.pdf, tpl.page, 150, ()) is None


def test_augment_one_smoke():
    """The one test that needs augraphy itself: skipped under the main venv."""
    pytest.importorskip("augraphy")
    from grid.augraphy_render import augment_one
    grey = np.full((300, 220), 255, dtype=np.uint8)
    grey[100:120, 40:180] = 0   # a line of "printed" text to give the pipeline something to touch
    image, fired = augment_one(grey, seed=11)
    assert image.shape == grey.shape
    assert image.dtype == np.uint8
    assert isinstance(fired, list)
    # Re-running the SAME seed on the SAME input must reproduce the SAME image: that is the
    # whole point of seeding random/numpy/cv2 before building the pipeline.
    image2, fired2 = augment_one(grey, seed=11)
    assert np.array_equal(image, image2)
    assert fired == fired2
