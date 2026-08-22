"""One CLEAN dossier, then N variants each carrying ONE single known defect.

This is the counterpart of the grid: without ground truth there is no true positive rate and
no false positive rate, therefore no curve, therefore no readable threshold. Each variant names
the check that MUST fire, and the test demands that the others stay silent. A check that fires
on its neighbour's variant is a false positive, and a false positive is expensive: a rule that
cries wolf makes every rule next to it get skimmed.

Every value comes from the FICTIONAL reference. No real person, no real address, no document
ever issued to anybody.

TEXT IS PRINTED BY AN OVERLAY, NOT BY THE ACROFORM APPEARANCE, and that choice was paid for.
Two of the three corpus forms carry an XFA layer (the W-9 and Cerfa 14011), and on those
pypdf's appearance generation is unfaithful: three Cerfa fields did not print at all, MARISOL
came out as "SOL", and the remaining values stuck to the field border so badly that OCR read
"|LDES ACACIAS". The grid would then have measured my filling bugs and not my sensors. The
overlay places the text at the position the AcroForm DECLARES, in Helvetica, exactly as a
printer would. Checkboxes, by contrast, stay filled through the AcroForm: their appearance is
supplied by the form and it renders correctly (ink delta +21 to +28 on all three pieces).
"""
import datetime as dt
import os
import re
from dataclasses import dataclass, field

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


@dataclass(frozen=True)
class Variant:
    """One defect, and one only. `check` is the one that must fire."""
    name: str
    check: str
    piece: str = ""
    empty_fields: tuple = ()
    uncheck: tuple = ()
    without_signature: bool = False
    expired_date: bool = False
    replace: dict = field(default_factory=dict)   # role -> wrong value
    image: dict = field(default_factory=dict)     # degradation override


CLEAN = Variant("clean", check="")

VARIANTS = (
    CLEAN,
    Variant("empty_required_field", "required_field", piece="employment", empty_fields=("city",)),
    Variant("unchecked_box", "required_checkbox", piece="tax", uncheck=("status",)),
    Variant("missing_signature", "signature", piece="employment", without_signature=True),
    Variant("expired_date", "expiry", piece="employment", expired_date=True),
    Variant("diverging_address", "consistency", piece="identity",
             replace={"street_name": "DES TILLEULS"}),
    Variant("forbidden_value", "forbidden_value", piece="employment",
             replace={"ssn": "999-99-9999"}),
    # 72 dpi is BELOW the grid's lowest dpi (96): without that the variant would duplicate
    # the grid's dpi axis and measure nothing new.
    Variant("low_resolution", "resolution", piece="tax", image={"dpi": 72}),
    Variant("cropped_page", "cropped_page", piece="tax", image={"crop": 0.18}),
    Variant("rotated_page", "rotated_page", piece="tax", image={"quarter_turns": 1}),
)

BY_NAME = {v.name: v for v in VARIANTS}
TARGETED_CHECKS = tuple(v.check for v in VARIANTS if v.check)


@dataclass(frozen=True)
class BuiltPiece:
    id: str
    template: object
    pdf: str
    image_override: dict


@dataclass(frozen=True)
class Dossier:
    variant: str
    targeted_check: str
    pieces: tuple

    def piece(self, ident):
        for p in self.pieces:
            if p.id == ident:
                return p
        raise KeyError(ident)


def _fmt(date, shape):
    return date.strftime("%m/%d/%Y" if shape == "us" else "%d/%m/%Y")


def _checked_state(pdf, field, page):
    """The "ticked" state is not guessed: it is declared by the widget's appearance.

    The W-9 says /1, the I-9 says /On. Hard-coding either one would break the other in silence,
    and a box that stays empty after being ticked manufactures a defect nobody asked for.
    """
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == field:
            ap = o.get("/AP", {}).get("/N", {})
            states = [k for k in (ap.keys() if hasattr(ap, "keys") else []) if k != "/Off"]
            if states:
                return states[0]
    return "/1"


def _pdf_rect(pdf, field, page):
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == field:
            return [float(v) for v in o["/Rect"]]
    raise KeyError(field)


def _escape(t):
    return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


GLYPH_WIDTH = 0.6      # mean width of a Helvetica character, in em


def _draw_text(x0, y0, x1, y1, value, comb=0):
    """Text placed at the position the field DECLARES, the way a printer would place it.

    A COMB FIELD PRINTS ONE BOX AT A TIME, and the form declares that itself (/Ff flag bit 25).
    The W-9 combs its tax number, the I-9 its social security number, the Cerfa five fields
    including the card number. Laying the string down continuously over the separators produces
    a field no OCR can read: measured 2026-08-21, the Cerfa card number returned 0 readable
    characters full page and "| | | | | | | |" in per zone OCR, that is, the separators alone.
    The grid would have measured that printing mistake and concluded, wrongly, that the
    required-field check does not hold.
    """
    if not value:
        return ""
    height = y1 - y0
    if comb:
        cell = (x1 - x0) / comb
        size = max(5.0, min(height * 0.58, cell * 1.25))
        base = y0 + (height - size) / 2 + size * 0.22
        ops = []
        for i, c in enumerate(value[:comb]):
            if c == " ":
                continue
            centre = x0 + cell * (i + 0.5) - size * GLYPH_WIDTH / 2
            ops.append(f"BT /F1 {size:.1f} Tf 1 0 0 1 {centre:.1f} {base:.1f} Tm "
                       f"({_escape(c)}) Tj ET")
        return "\n".join(ops) + "\n"
    size = max(6.0, min(11.0, height * 0.58))
    base = y0 + (height - size) / 2 + size * 0.22
    return (f"BT /F1 {size:.1f} Tf 1 0 0 1 {x0 + 3:.1f} {base:.1f} Tm "
            f"({_escape(value)}) Tj ET\n")


def _draw_signature(x0, y0, x1, y1, seed=11):
    """A handwritten signature: one single continuous stretched stroke.

    Drawn as vectors inside the PDF, not painted onto the image: the fixture stays a PDF, so
    the signature goes through the same degradation chain as the rest of the page.
    """
    import random
    r = random.Random(seed)
    margin_x, margin_y = (x1 - x0) * 0.12, (y1 - y0) * 0.22
    ax, bx = x0 + margin_x, x1 - margin_x
    cy = (y0 + y1) / 2
    amp = max(4.0, (y1 - y0) / 2 - margin_y)
    n = 5
    ops = ["0 0 0 RG", "1.3 w", "1 J", "1 j", f"{ax:.1f} {cy:.1f} m"]
    for i in range(n):
        px = ax + (bx - ax) * (i + 1) / n
        qx = ax + (bx - ax) * (i + 0.35) / n
        rx = ax + (bx - ax) * (i + 0.7) / n
        ops.append(f"{qx:.1f} {cy + r.uniform(0.5, 1.0) * amp:.1f} "
                   f"{rx:.1f} {cy - r.uniform(0.5, 1.0) * amp:.1f} "
                   f"{px:.1f} {cy + r.uniform(-0.3, 0.3) * amp:.1f} c")
    ops.append("S")
    return "\n".join(ops) + "\n"


COMB_FLAG = 1 << 24


def _maxlen(pdf, page):
    out = {}
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if o.get("/T") is not None and o.get("/MaxLen") is not None:
            out[str(o["/T"])] = int(o["/MaxLen"])
    return out


def _combs(pdf, page):
    """The fields that fill ONE BOX PER CHARACTER, exactly as the PDF declares them."""
    out = {}
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if o.get("/T") is None or o.get("/MaxLen") is None:
            continue
        if int(o.get("/Ff", 0) or 0) & COMB_FLAG:
            out[str(o["/T"])] = int(o["/MaxLen"])
    return out


def _place(vals, fields, value, maxlen):
    """Write a value into one or several fields, respecting the DECLARED MaxLen.

    The form says itself how many characters it accepts: the W-9 splits the tax number over
    three boxes of 3, 2 and 4, the Cerfa wants a birth date in 8 characters with no separator.
    Ignoring that MaxLen makes pypdf truncate silently, and the fixture then carries a defect
    nobody asked for.
    """
    if len(fields) > 1:
        parts = re.split(r"[^0-9A-Za-z]+", value)
        for c, m in zip(fields, parts):
            vals[c] = m
        return
    c = fields[0]
    m = maxlen.get(c)
    if m is not None and len(value) > m:
        value = re.sub(r"[^0-9A-Za-z]", "", value)[:m]
    vals[c] = value


def _values(ref, tpl, var, piece_id):
    """What the piece must carry, the variant's defect included."""
    vals = {}
    maxlen = _maxlen(tpl.pdf, tpl.page)
    for role in tpl.fields:
        if var.piece == piece_id and role in var.empty_fields:
            continue
        if var.piece == piece_id and role in var.replace:
            v = var.replace[role]
        elif role in tpl.dates and tpl.dates[role] == "expiration":
            expired = var.piece == piece_id and var.expired_date
            v = _fmt(ref.expiry["expired_expiry_date" if expired else "valid_expiry_date"],
                     tpl.date_format)
        elif role == "signature_date":
            v = _fmt(ref.clocks["filing"], tpl.date_format)
        elif role == "birth_date":
            v = _fmt(dt.datetime.strptime(ref.value("birth_date"), "%d/%m/%Y").date(),
                     tpl.date_format)
        elif role == "address":
            a = ref.person["address"]
            v = f"{a['number']} {a['street_type']} {a['street_name']}"
        elif role == "city" and tpl.name in ("fw9", "fw9sp"):
            a = ref.person["address"]
            v = f"{a['city']}, FR {a['postal_code']}"
        else:
            v = ref.value(role)
        _place(vals, tpl.field_ids(role), str(v), maxlen)
    return vals


def _stamp(w, page_no, ops, buffer):
    """Merge a vector overlay onto the page. Helvetica is a base PDF font: nothing to embed,
    nothing to install, and poppler renders it everywhere."""
    page = w.pages[page_no - 1]
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
    overlay.write(buffer)
    page.merge_page(PdfReader(buffer).pages[0])
    os.unlink(buffer)


def build(ref, variant, dest, reuse=True):
    """Materialise the dossier: one filled PDF per piece, plus the image overrides.

    `reuse` serves the grid: fixtures are deterministic, the parent builds them once and the
    twelve workers just read them back. Without it the workers step on each other over the
    temporary overlay file.
    """
    var = BY_NAME[variant] if isinstance(variant, str) else variant
    os.makedirs(dest, exist_ok=True)
    pieces = []
    for piece_id, template_name in ref.pieces:
        tpl = ref.templates[template_name]
        path = os.path.join(dest, f"{var.name}-{piece_id}.pdf")
        if reuse and os.path.exists(path):
            pieces.append(BuiltPiece(piece_id, tpl, path,
                                          dict(var.image) if var.piece == piece_id else {}))
            continue
        vals = _values(ref, tpl, var, piece_id)
        for role, field in tpl.boxes.items():
            if not (var.piece == piece_id and role in var.uncheck):
                vals[field] = _checked_state(tpl.pdf, field, tpl.page)
        boxes = {c: v for c, v in vals.items() if c in tpl.boxes.values()}
        w = PdfWriter(clone_from=tpl.pdf)
        w.set_need_appearances_writer(True)
        if boxes:
            w.update_page_form_field_values(w.pages[tpl.page - 1], boxes, auto_regenerate=True)
        combs = _combs(tpl.pdf, tpl.page)
        ops = "".join(_draw_text(*_pdf_rect(tpl.pdf, field, tpl.page), value,
                                 combs.get(field, 0))
                      for field, value in vals.items() if field not in boxes)
        if tpl.signatures and not (var.piece == piece_id and var.without_signature):
            ops += "".join(_draw_signature(*_pdf_rect(tpl.pdf, field, tpl.page))
                           for field in tpl.signatures.values())
        if ops:
            _stamp(w, tpl.page, ops,
                     os.path.join(dest, f"{var.name}-{piece_id}-overlay-{os.getpid()}.pdf"))
        buffer = path + f".{os.getpid()}"
        w.write(buffer)
        os.replace(buffer, path)
        override = dict(var.image) if var.piece == piece_id else {}
        pieces.append(BuiltPiece(piece_id, tpl, path, override))
    return Dossier(var.name, var.check, tuple(pieces))
