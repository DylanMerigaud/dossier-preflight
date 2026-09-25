#!/usr/bin/env python3
"""T14 step 1 (perfect-recall-study/prereg/PREREG.md section 3, row X2): the print kit for the
real-scan session. This script builds PAPER'S DIGITAL ANCESTOR and never prints: T14's gate G2
("the kit is on the Brother") is Dylan's, and this script has no `lp` call anywhere in it.

WHAT IT WRITES, under --out (default $AR/x2/kit):
    S01.pdf .. S60.pdf     the 60 filled, stamped sheets (see "THE 60 SHEETS" below)
    checklist.pdf          Dylan's numbered capture instructions, plain English
    checklist.csv          the same lines, machine-readable: grid/realscan_ingest.py's pairing
                            key and the future manifest.csv's expected (identity, piece,
                            variant, mark_step, device, dpi) per capture
    cover.pdf              one page: print order, the printer, the fictional-names notice
    expected.json          {identity: [variant, ...]}, grid/analyze.py's --expected (T09)

THE 60 SHEETS (PREREG.md 3, X2 row). For id01 to id04: 13 base pieces (the 4 clean pieces of
the reference schema, plus preflight.fixtures.VARIANTS' nine v0.1.0 single-instance defects,
UNCHANGED from the published grid's own nine, not T08's per-role enumerate_variants()
superset: X2 exists to catch what the generator's own nine miss, not to multiply them) plus 2
mark sheets (a clean copy and an emptied copy of the piece the first required_field instance,
VARIANTS[1] "empty_required_field", empties: the I-9's City or Town field). 4 x (13 + 2) = 60.
Order: all of id01 and id02 first, so the first half (30 sheets, 82 of the 164 captures, one
identity is 41: 12 base sheets x 2 phone captures, 1 flatbed-only low_resolution capture, 2
mark sheets x 4 steps x 2 phone captures) is a complete set on its own.

WHY THE KIT SUPPRESSES THE FIXTURE'S OWN SIGNATURE. preflight.fixtures.build() bakes a
synthetic vector signature (preflight.fixtures._draw_signature) onto the I-9 piece for every
variant except missing_signature, because the degradation grid needs a REPRODUCIBLE mark to
degrade. A printed real-scan kit needs the opposite: the signature check exists to be tested
against Dylan's OWN hand on paper, not against a vector stroke that would print identically to
the "sign here" instruction it is meant to replace. Every kit build therefore passes
`without_signature=True` on the I-9 piece regardless of the variant (dataclasses.replace, never
a fixtures.py edit: T08 owns that file and this script only calls its public build()), except
that the check itself still requires "without_signature=True" for the one variant whose defect
IS the missing signature, where the effect is identical to what fixtures.py already did. Only
the I-9 template declares a signature field (templates/i9.yaml; fw9, fw9sp and cerfa14011
declare none), so this only ever changes the employment piece.

THE SHEET CODE. Every sheet carries a small printed code (S01..S60) in the bottom margin, so
grid/realscan_ingest.py can pair a capture back to its checklist line by OCR alone, without
trusting file names AirDrop or Apple Notes choose. WHERE, AND WHY IT IS SAFE:

  1. no declared AcroForm zone. Measured 2026-09-26, PDF-native points, origin bottom left, the
     same frame preflight.fixtures draws its overlay text in: the nearest declared field edge to
     the page's BOTTOM edge is 348.0 pt on the W-9, 312.0 on the Spanish W-9, 47.7 on the I-9
     (the tightest of the four; "nearest edge" as a single number, not a per-column table, means
     no declared rectangle's bottom edge is lower than this value AT ANY x, so a horizontal band
     entirely below it is clear of every field regardless of where across the width it sits),
     131.2 on the Cerfa. `stamp_rect()`'s field check reads the ACTUAL declared zones of
     whichever PDF it is about to stamp, never this comment, so a future template with a field
     genuinely reaching the bottom margin fails the kit build instead of a silent overlap.
  2. no PRE-PRINTED ink either, and a field-only check is not enough: the I-9 is a four-page
     form whose OWN footer ("Form I-9  Edition ...  Page 1 of 4") runs the full width of the
     page around 20 to 50 pt off the bottom edge, no AcroForm field there at all, yet a first
     stamp placed in that band (y in [10, 30] pt) came back unreadable or misread on every I-9
     sheet OCR-tested (measured 2026-09-26, grid/realscan_ingest.py's own pairing check: 33 of
     60 sheets mismatched, concentrated on the I-9 and, from a different cause, the Spanish
     W-9's own revision line). `stamp_rect()`'s second check renders the BLANK template (the
     tool's own reference image, preflight.render.render) and refuses a position with ANY dark
     pixel inside the stamp box, not just an estimate: measured, a 12 pt tall box ending 2 pt
     off the physical bottom edge is completely ink-free on all four corpus templates, which is
     why the stamp is smaller and lower than a first pass assumed.

Usage:
    python3 grid/realscan_kit.py --out /path/to/x2/kit
    python3 grid/realscan_kit.py --out /tmp/kit --identities fixtures/identities
"""
import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from grid.augraphy_render import target_role_and_fields
from preflight.fixtures import CLEAN, VARIANTS, build
from preflight.reference import load_reference

DEFAULT_IDENTITIES = os.path.join(ROOT, "fixtures", "identities")
X2_IDENTITIES = ("id01", "id02", "id03", "id04")

# The v0.1.0 nine, unchanged (module docstring): NOT T08's enumerate_variants() superset.
DEFECTS = VARIANTS[1:]
assert [v.check for v in DEFECTS] == [
    "required_field", "required_checkbox", "signature", "expiry", "consistency",
    "forbidden_value", "resolution", "cropped_page", "rotated_page"], \
    "grid/realscan_kit.py assumes VARIANTS' v0.1.0 order; preflight/fixtures.py changed under it"

# "The piece the first required_field instance empties" (T14 step 1): VARIANTS[1] itself.
MARK_DEFECT = DEFECTS[0]
assert MARK_DEFECT.name == "empty_required_field" and MARK_DEFECT.piece == "employment" \
    and MARK_DEFECT.empty_fields == ("city",)
MARK_PIECE = MARK_DEFECT.piece

SIGNING_PIECE = "employment"     # only templates/i9.yaml declares a signature field

TEMPLATE_LABEL = {"tax": "W-9", "tax_es": "W-9 (Spanish)", "employment": "I-9",
                  "identity": "Cerfa 14011"}
DEFECT_LABEL = {
    "empty_required_field": "City or Town field left blank",
    "unchecked_box": "status box left unticked",
    "missing_signature": "signature left blank",
    "expired_date": "expiration date set in the past",
    "diverging_address": "street name does not match the W-9",
    "forbidden_value": "SSN set to the form's own example number",
    "low_resolution": "flatbed only, 75 dpi",
    "cropped_page": "bottom fifth covered before capture",
    "rotated_page": "turned a quarter turn before capture",
}
MARK_FIELD_LABEL = "the City or Town field"

# Physical action Dylan takes before EVERY capture of a defect sheet (empty string: none).
PHYSICAL_ACTION = {
    "rotated_page": "turn the sheet a quarter turn, then",
    "cropped_page": "cover the bottom fifth with a blank sheet, then",
}

# The stamp: see the module docstring for the measurement behind these numbers.
STAMP_MARGIN_RIGHT_PT = 24
STAMP_MARGIN_BOTTOM_PT = 2
STAMP_WIDTH_PT = 60
STAMP_HEIGHT_PT = 12
STAMP_SAFETY_PT = 4
STAMP_FONT_SIZE = 9
STAMP_INK_DPI = 300           # the blank-ink check renders at the same dpi ingest OCRs a phone
                              # capture at, so "clear at this resolution" is the claim that
                              # actually matters
STAMP_INK_THRESHOLD = 200     # a pixel this dark or darker counts as ink (preflight.deskew's
                              # own light-side convention: 255 is paper white)
GLYPH_WIDTH = 0.6      # mean Helvetica character width, in em (matches preflight.fixtures)

PAGE_W, PAGE_H = 612.0, 792.0   # US letter, points
MARGIN = 54.0


# ---------------------------------------------------------------------------------------------
# The sheet code stamp
# ---------------------------------------------------------------------------------------------

def _escape(t):
    return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def field_rects(pdf_path, page):
    """Every declared AcroForm rectangle, PDF-native points (origin bottom left): the frame
    preflight.fixtures draws its overlay text in. Read straight off the PDF rather than through
    preflight.geometry.declared_zones(), which flips to image convention (origin top left) for
    the tool's OWN reading path: mixing frames here would be exactly the hand-measured-looking
    coordinate mistake this repo otherwise refuses to have anywhere."""
    rects = []
    for an in PdfReader(pdf_path).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if "/Rect" in o:
            rects.append(tuple(float(v) for v in o["/Rect"]))
    return rects


def _blank_ink_fraction(pdf_path, page, x0, y0, x1, y1, dpi=STAMP_INK_DPI, margin=STAMP_SAFETY_PT):
    """Share of dark pixels inside (x0,y0,x1,y1) (PDF-native points, safety-expanded), rendered
    from `pdf_path` at `dpi`: called on the blank template directly (the tool's own reference
    image, preflight/__init__.py's own words) when checking a template in isolation, and on a
    FILLED sheet from within stamp_pdf(), which is the stricter of the two (a filled page
    carries every static footer and boilerplate the blank does, plus whatever values a variant
    placed, so clearing ink there clears it against the blank too). Answers the question the
    field check cannot: is anything already printed here, field or not."""
    from preflight.render import render
    img = render(pdf_path, dpi=dpi, page=page)
    h, w = img.shape
    scale = dpi / 72.0
    px_x0 = max(0, int((x0 - margin) * scale))
    px_x1 = min(w, int((x1 + margin) * scale))
    px_y0 = max(0, h - int((y1 + margin) * scale))
    px_y1 = min(h, h - int((y0 - margin) * scale))
    if px_y1 <= px_y0 or px_x1 <= px_x0:
        return 0.0
    crop = img[px_y0:px_y1, px_x0:px_x1]
    return float((crop < STAMP_INK_THRESHOLD).sum()) / crop.size


def stamp_rect(pdf_path, page=1):
    """Where the sheet code goes on THIS pdf: bottom right, checked against its OWN declared
    zones AND its own pre-printed ink, never assumed from another template's layout. Raises
    instead of drawing over either (module docstring, "THE SHEET CODE")."""
    w = float(PdfReader(pdf_path).pages[page - 1].mediabox.width)
    x1 = w - STAMP_MARGIN_RIGHT_PT
    x0 = x1 - STAMP_WIDTH_PT
    y0 = STAMP_MARGIN_BOTTOM_PT
    y1 = y0 + STAMP_HEIGHT_PT
    overlapping = []
    for (fx0, fy0, fx1, fy1) in field_rects(pdf_path, page):
        if (x0 - STAMP_SAFETY_PT < fx1 and x1 + STAMP_SAFETY_PT > fx0
                and y0 - STAMP_SAFETY_PT < fy1 and y1 + STAMP_SAFETY_PT > fy0):
            overlapping.append((fx0, fy0, fx1, fy1))
    if overlapping:
        raise RuntimeError(f"{pdf_path}: the sheet-code stamp box ({x0:.1f},{y0:.1f})-"
                           f"({x1:.1f},{y1:.1f}) overlaps {len(overlapping)} declared field(s), "
                           f"e.g. {overlapping[0]}; the kit refuses to build")
    ink = _blank_ink_fraction(pdf_path, page, x0, y0, x1, y1)
    if ink > 0.0:
        raise RuntimeError(f"{pdf_path}: the sheet-code stamp box ({x0:.1f},{y0:.1f})-"
                           f"({x1:.1f},{y1:.1f}) sits over pre-printed ink (dark fraction "
                           f"{ink:.4f}) on the blank template; the kit refuses to build")
    return x0, y0, x1, y1


def stamp_pdf(src_path, dest_path, code):
    """Merge the sheet code onto the DECLARED field page of src_path (always page 1 on the four
    corpus templates, preflight.templates' own "page" key) and write ONLY that page to
    dest_path: three of the four corpus PDFs are multi-page government documents (the W-9 and
    its Spanish edition ship 6 pages, the I-9 ships 4, all instructions after the one page that
    carries the fields), and `PdfWriter(clone_from=src_path)` would otherwise clone every one of
    them into the printed sheet, turning a single physical page into a multi-page print job.
    Vector Helvetica, the same technique preflight.fixtures._stamp uses: a base-14 font, nothing
    to embed, nothing to install."""
    reader = PdfReader(src_path)
    w = PdfWriter()
    w.add_page(reader.pages[0])
    page = w.pages[0]
    x0, y0, x1, y1 = stamp_rect(src_path, 1)
    base = y0 + (STAMP_HEIGHT_PT - STAMP_FONT_SIZE) / 2 + STAMP_FONT_SIZE * 0.22
    ops = (f"BT /F1 {STAMP_FONT_SIZE} Tf 1 0 0 1 {x0 + 4:.1f} {base:.1f} Tm "
          f"({_escape(code)}) Tj ET\n")
    overlay = PdfWriter()
    blank = overlay.add_blank_page(float(page.mediabox.width), float(page.mediabox.height))
    stream = DecodedStreamObject()
    stream.set_data(ops.encode("latin-1", "replace"))
    blank[NameObject("/Contents")] = overlay._add_object(stream)
    blank[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")})})})
    tmp = dest_path + f".{os.getpid()}.overlay"
    overlay.write(tmp)
    page.merge_page(PdfReader(tmp).pages[0])
    os.unlink(tmp)
    out_tmp = dest_path + f".{os.getpid()}.tmp"
    w.write(out_tmp)
    os.replace(out_tmp, dest_path)


# ---------------------------------------------------------------------------------------------
# The sheet plan: one SheetSpec per physical page, in print/capture order
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SheetSpec:
    kind: str              # "clean" | "defect" | "mark"
    piece: str
    build_variant: object   # the Variant fixtures.build() takes (signature-suppressed)
    canonical_variant: str  # the name grid/analyze.py's catalog recognises ("clean" or a
                            # DEFECTS name): what goes in checklist.csv / expected.json
    label: str
    sign: bool
    must_not_sign: bool
    physical_action: str
    device: str             # "phone" | "flatbed" | "mark"
    flatbed_dpi: int


def identity_sheet_specs(ref):
    """The 13 base + 2 mark sheet specs for one identity, print/capture order."""
    specs = []
    for pid, _ in ref.pieces:
        signing = pid == SIGNING_PIECE
        var = replace(CLEAN, name="clean_unsigned", piece=SIGNING_PIECE,
                     without_signature=True) if signing else CLEAN
        specs.append(SheetSpec("clean", pid, var, "clean", f"{TEMPLATE_LABEL[pid]}, clean",
                               sign=signing, must_not_sign=False, physical_action="",
                               device="phone", flatbed_dpi=0))
    for d in DEFECTS:
        must_not_sign = d.name == "missing_signature"
        signing = d.piece == SIGNING_PIECE and not must_not_sign
        var = replace(d, without_signature=True) if d.piece == SIGNING_PIECE else d
        device = "flatbed" if d.name == "low_resolution" else "phone"
        specs.append(SheetSpec(
            "defect", d.piece, var, d.name, f"{TEMPLATE_LABEL[d.piece]}, {DEFECT_LABEL[d.name]}",
            sign=signing, must_not_sign=must_not_sign,
            physical_action=PHYSICAL_ACTION.get(d.name, ""), device=device,
            flatbed_dpi=75 if device == "flatbed" else 0))
    mark_clean = replace(CLEAN, name="mark_clean", piece=SIGNING_PIECE, without_signature=True)
    mark_empty = replace(MARK_DEFECT, name="mark_empty", without_signature=True)
    specs.append(SheetSpec(
        "mark", SIGNING_PIECE, mark_clean, "clean",
        f"{TEMPLATE_LABEL[SIGNING_PIECE]}, clean (mark sheet)", sign=True, must_not_sign=False,
        physical_action="", device="mark", flatbed_dpi=0))
    specs.append(SheetSpec(
        "mark", SIGNING_PIECE, mark_empty, MARK_DEFECT.name,
        f"{TEMPLATE_LABEL[SIGNING_PIECE]}, {MARK_FIELD_LABEL} emptied (mark sheet)",
        sign=True, must_not_sign=False, physical_action="", device="mark", flatbed_dpi=0))
    assert len(specs) == 15
    return specs


@dataclass(frozen=True)
class Sheet:
    code: str
    identity: str
    spec: object
    pdf_path: str


def build_sheets(identities_dir, build_dir, out_dir):
    """Every one of the 60 sheets, built, stamped, and written to out_dir as
    <code>-<identity>-<piece>-<slug>.pdf. Returns the ordered list of Sheet.

    fixtures.build() always materialises all 4 pieces of a dossier for whichever variant it is
    given, even though a given SheetSpec only needs one of them: three of the four "clean"
    specs (tax, tax_es, identity) all pass the SAME `build_variant` (the literal CLEAN object,
    the module's own singleton), so a per-identity cache keyed by the variant's name avoids
    rebuilding that dossier three times over to keep one piece each time.
    """
    os.makedirs(out_dir, exist_ok=True)
    sheets = []
    n = 0
    for identity in X2_IDENTITIES:
        ref = load_reference(os.path.join(identities_dir, f"{identity}.yaml"))
        dossier_cache = {}      # build_variant.name -> Dossier, built at most once per identity
        for spec in identity_sheet_specs(ref):
            n += 1
            code = f"S{n:02d}"
            key = spec.build_variant.name
            if key not in dossier_cache:
                dossier_cache[key] = build(ref, spec.build_variant, build_dir, reuse=False)
            built_pdf = dossier_cache[key].piece(spec.piece).pdf
            slug = spec.label.lower().replace(" ", "_").replace(",", "").replace("(", "") \
                .replace(")", "")
            final = os.path.join(out_dir, f"{code}-{identity}-{spec.piece}-{slug}.pdf")
            stamp_pdf(built_pdf, final, code)
            sheets.append(Sheet(code, identity, spec, final))
    assert n == 60, f"expected 60 sheets, built {n}"
    return sheets


# ---------------------------------------------------------------------------------------------
# Captures: one per phone/flatbed photograph, globally numbered (the checklist's own numbering)
# ---------------------------------------------------------------------------------------------

def capture_rows(sheets, refs):
    """One dict per capture, in checklist order. `refs` is {identity: Reference}, used only to
    resolve the `instance` role via grid.augraphy_render.target_role_and_fields (the same
    derivation T11 already uses, reused rather than reinvented)."""
    rows = []
    n = 0

    def role_of(spec, identity):
        if spec.canonical_variant == "clean":
            return ""
        tpl = refs[identity].templates[dict(refs[identity].pieces)[spec.piece]]
        # spec.build_variant keeps the original .check (dataclasses.replace only touches
        # without_signature and, for the mark sheets, .name): target_role_and_fields reads the
        # same role off it as it would off the un-renamed VARIANTS/DEFECTS entry.
        role, _ = target_role_and_fields(spec.build_variant, tpl)
        return role or ""

    for sheet in sheets:
        spec = sheet.spec
        if spec.device == "mark":
            # Both mark sheets (the clean copy AND the emptied copy) are marked in the SAME
            # place, the field the first required_field instance empties: role_of() would give
            # "" for the clean one (its canonical_variant is "clean", the same name a plain
            # clean sheet carries, which correctly has no target field), but a MARK sheet always
            # has one, regardless of which copy it is.
            instance = MARK_DEFECT.empty_fields[0]
        else:
            instance = role_of(spec, sheet.identity)
        if spec.device == "phone":
            for i in (1, 2):
                n += 1
                rows.append({"line": n, "sheet_code": sheet.code, "identity": sheet.identity,
                            "piece": spec.piece, "variant": spec.canonical_variant,
                            "instance": instance, "mark_step": "", "device": "phone",
                            "dpi": 300, "capture_index": i, "sign": spec.sign,
                            "must_not_sign": spec.must_not_sign,
                            "physical_action": spec.physical_action, "label": spec.label})
        elif spec.device == "flatbed":
            n += 1
            rows.append({"line": n, "sheet_code": sheet.code, "identity": sheet.identity,
                        "piece": spec.piece, "variant": spec.canonical_variant,
                        "instance": instance, "mark_step": "", "device": "flatbed",
                        "dpi": spec.flatbed_dpi, "capture_index": 1, "sign": spec.sign,
                        "must_not_sign": spec.must_not_sign,
                        "physical_action": spec.physical_action, "label": spec.label})
        elif spec.device == "mark":
            for step in (0, 1, 2, 3):
                for i in (1, 2):
                    n += 1
                    rows.append({
                        "line": n, "sheet_code": sheet.code, "identity": sheet.identity,
                        "piece": spec.piece, "variant": spec.canonical_variant,
                        "instance": instance, "mark_step": step, "device": "phone",
                        "dpi": 300, "capture_index": i, "sign": spec.sign,
                        "must_not_sign": spec.must_not_sign, "physical_action": "",
                        "label": spec.label})
    return rows


CAPTURE_FIELDS = ["line", "sheet_code", "identity", "piece", "variant", "instance",
                  "mark_step", "device", "dpi", "capture_index", "sign", "must_not_sign",
                  "physical_action", "label"]


def write_checklist_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAPTURE_FIELDS)
        w.writeheader()
        w.writerows(rows)


MARK_STEP_TEXT = {
    0: "capture with no mark",
    1: f"add a pencil dot about 1 mm inside {MARK_FIELD_LABEL}, then capture",
    2: f"add a pen stroke about 5 mm inside {MARK_FIELD_LABEL}, then capture",
    3: f"lightly rub a pencil over about 1 cm square inside {MARK_FIELD_LABEL}, then capture",
}


def checklist_lines(rows, n_captures, first_half_end):
    """(text, size, bold, gap_after) blocks for write_text_pdf(): the header, then one block per
    sheet (a short unnumbered action line) with its numbered capture lines under it."""
    blocks = [
        ("Real-scan checklist (X2)", 18, True, 4),
        (f"{n_captures} captures total.", 12, True, 0),
        (f"The first half is complete on its own and ends at line {first_half_end}.", 11,
         False, 2),
        ("Each capture: phone in Apple Notes, \"Scan Documents\", default", 11, False, 0),
        ("settings, saved as PDF. AirDrop every file to the incoming folder.", 11, False, 2),
        ("Optional: also scan the same sheet on the flatbed (grayscale),", 10, False, 0),
        ("once at 150 dpi and once at 300 dpi.", 10, False, 10),
    ]
    last_sheet = None
    for r in rows:
        if r["sheet_code"] != last_sheet:
            last_sheet = r["sheet_code"]
            action = []
            if r["sign"]:
                action.append("sign with the name printed on the form")
            if r["must_not_sign"]:
                action.append("do not sign")
            if r["physical_action"]:
                text = r["physical_action"]
                suffix = ", then"
                action.append(text[:-len(suffix)] if text.endswith(suffix) else text)
            header = f"{r['sheet_code']}  {r['label']}"
            if action:
                header += "  -  " + ", ".join(action)
            blocks.append((header, 12, True, 1))
        if r["mark_step"] != "":
            text = f"  {r['line']:>3}. " + MARK_STEP_TEXT[r["mark_step"]] + \
                (" (step " + str(r["mark_step"]) + ", " + ("1st" if r["capture_index"] == 1
                                                           else "2nd") + " capture)")
        elif r["device"] == "flatbed":
            text = f"  {r['line']:>3}. capture on the flatbed only, {r['dpi']} dpi"
        else:
            text = (f"  {r['line']:>3}. capture ({'1st' if r['capture_index'] == 1 else '2nd'} "
                   f"of two)")
        blocks.append((text, 11, False, 0))
    return blocks


# ---------------------------------------------------------------------------------------------
# Hand-rolled text PDFs (checklist.pdf, cover.pdf): reportlab is NOT a dependency of this repo
# (pyproject.toml says so explicitly) and must not become one for the kit's own paperwork
# either, so this mirrors preflight.fixtures' own technique: vector Helvetica, base-14, nothing
# to embed.
# ---------------------------------------------------------------------------------------------

def _font_resource():
    return DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")}),
            NameObject("/F1B"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica-Bold")})})})


def _wrap(text, size):
    """Greedy word wrap to the usable page width, at GLYPH_WIDTH's Helvetica approximation (the
    same one preflight.fixtures uses to size comb text). "Short lines" is the checklist's own
    requirement (T14 step 2): enforced here by wrapping, not by hand-trimming every label and
    instruction string until it happens to fit."""
    usable = PAGE_W - 2 * MARGIN
    max_chars = max(1, int(usable / (size * GLYPH_WIDTH)))
    words = text.split(" ")
    lines, cur = [], ""
    for word in words:
        cand = f"{cur} {word}".strip()
        if len(cand) > max_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    lines.append(cur)
    return lines


def write_text_pdf(path, blocks):
    """blocks: (text, size, bold, gap_after_pt). Paginates automatically; a line too long for
    the page width wraps onto continuation lines at the same size instead of running off the
    page (see _wrap())."""
    w = PdfWriter()
    y = [PAGE_H - MARGIN]
    ops = []

    def flush():
        page = w.add_blank_page(PAGE_W, PAGE_H)
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1", "replace"))
        page[NameObject("/Contents")] = w._add_object(stream)
        page[NameObject("/Resources")] = _font_resource()

    def emit(line_text, bold, size, leading):
        if y[0] - leading < MARGIN:
            flush()
            ops.clear()
            y[0] = PAGE_H - MARGIN
        font = "/F1B" if bold else "/F1"
        ops.append(f"BT {font} {size} Tf 1 0 0 1 {MARGIN:.1f} {y[0]:.1f} Tm "
                  f"({_escape(line_text)}) Tj ET")
        y[0] -= leading

    for text, size, bold, gap_after in blocks:
        leading = size + 5
        wrapped = _wrap(text, size)
        for i, line_text in enumerate(wrapped):
            extra = gap_after if i == len(wrapped) - 1 else 0
            emit(line_text, bold, size, leading + extra)
    if ops:
        flush()
    w.write(path)


def write_cover_pdf(path, printer_name):
    blocks = [
        ("Perfect-recall real-scan kit (X2)", 18, True, 8),
        ("Print order", 13, True, 4),
        ("S01 to S60, in order: all of id01 and id02 first (30 sheets, a complete set on its "
         "own), then id03 and id04.", 11, False, 6),
        ("Printer", 13, True, 4),
        (f"{printer_name}", 11, False, 6),
        ("Fictional data", 13, True, 4),
        ("Every name, address and identifier on these forms is invented "
         "(fixtures/make_identities.py, seed 20260925). No real person, no document ever "
         "issued to anybody.", 11, False, 0),
    ]
    write_text_pdf(path, blocks)


# ---------------------------------------------------------------------------------------------
# expected.json (T09's grid/analyze.py --expected): the variants X2 carries per identity
# ---------------------------------------------------------------------------------------------

def write_expected_json(path):
    names = sorted({d.name for d in DEFECTS})
    json.dump({identity: names for identity in X2_IDENTITIES}, open(path, "w", encoding="utf-8"),
              indent=2, sort_keys=True)


# ---------------------------------------------------------------------------------------------

def build_kit(out_dir, identities_dir=DEFAULT_IDENTITIES, build_dir=None, printer_name=
             "Brother HL-L2375DW"):
    build_dir = build_dir or os.path.join(out_dir, "_build")
    refs = {i: load_reference(os.path.join(identities_dir, f"{i}.yaml")) for i in X2_IDENTITIES}
    sheets = build_sheets(identities_dir, build_dir, out_dir)
    rows = capture_rows(sheets, refs)
    n_captures = len(rows)
    first_half_rows = [r for r in rows if r["identity"] in ("id01", "id02")]
    first_half_end = first_half_rows[-1]["line"] if first_half_rows else 0
    write_checklist_csv(rows, os.path.join(out_dir, "checklist.csv"))
    write_text_pdf(os.path.join(out_dir, "checklist.pdf"),
                   checklist_lines(rows, n_captures, first_half_end))
    write_cover_pdf(os.path.join(out_dir, "cover.pdf"), printer_name)
    write_expected_json(os.path.join(out_dir, "expected.json"))
    phone_captures = sum(1 for r in rows if r["device"] == "phone")
    flatbed_mandatory = sum(1 for r in rows if r["device"] == "flatbed")
    return {"sheets": len(sheets), "captures": n_captures, "phone_captures": phone_captures,
           "flatbed_mandatory": flatbed_mandatory, "first_half_end": first_half_end}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="e.g. $AR/x2/kit")
    ap.add_argument("--identities", default=DEFAULT_IDENTITIES)
    ap.add_argument("--printer", default="Brother HL-L2375DW")
    a = ap.parse_args(argv)
    summary = build_kit(os.path.abspath(a.out), os.path.abspath(a.identities),
                        printer_name=a.printer)
    print(f"{summary['sheets']} sheets, {summary['captures']} captures "
         f"({summary['phone_captures']} phone, {summary['flatbed_mandatory']} flatbed-only), "
         f"first half ends at line {summary['first_half_end']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
