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
import hashlib
import json
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
    # Days the expiry date is placed BEFORE the filing clock, when set: 1 or 365 (the two
    # magnitudes the enumeration in enumerate_variants() injects). None means "use the fixed
    # expired_expiry_date of the reference instead", the v0.1.0 behaviour, unchanged.
    expired_days: "int | None" = None


CLEAN = Variant("clean", check="")

# ONE INSTANCE PER DEFECT, on the single reference identity of v0.1.0. Kept EXACTLY as it was,
# name for name: grid/target_parasite.py and the tests in tests/test_fixtures.py import this
# tuple directly and depend on its shape, and the published grid (A0) was measured against it.
# enumerate_variants() below is the exhaustive, per-identity superset this v0.1.0 tuple is now
# one slice of.
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

# The social security or taxpayer number roles a piece must carry for the form's own example
# number (999-99-9999, forbidden_values[0]) to be a defect that fits it at all. The Cerfa
# declares neither, so it carries no forbidden_value instance: measured against templates.py,
# not guessed.
FORBIDDEN_VALUE_ROLES = ("tax_id", "ssn")

# The three page-level defects, one instance per piece under the exhaustive enumeration. Same
# overrides as the v0.1.0 variants above, generalised from "the tax piece only" to "every piece".
PAGE_DEFECTS = (
    ("low_resolution", "resolution", {"dpi": 72}),
    ("cropped_page", "cropped_page", {"crop": 0.18}),
    ("rotated_page", "rotated_page", {"quarter_turns": 1}),
)


def _forbidden_value_role(tpl):
    for role in FORBIDDEN_VALUE_ROLES:
        if role in tpl.fields:
            return role
    return None


def enumerate_variants(ref):
    """Every single-defect instance this reference's pieces declare, one Variant each.

    Unlike VARIANTS (one instance per check, the v0.1.0 grid), this walks every ROLE the
    templates declare, for every piece: every required field emptied in turn, every required
    checkbox unticked, one missing signature per signed piece, expiry at 1 day and at 365 days
    past the filing clock, one disagreement per declared consistency pair (placed on the second
    reading of the pair, as v0.1.0 placed it on the Cerfa side), the forbidden value on each
    piece that carries a social security or taxpayer number field, and the three page defects
    on each piece. The rule and its arithmetic are prereg-v1's (perfect-recall-study
    prereg/PREREG.md section 3.2): 45 instances on the four pieces this repo ships.

    Variant NAMES do not carry the identity: they describe WHICH field of WHICH piece is
    touched, a purely structural fact that is the same for every identity sharing this schema.
    The identity enters through the key a caller stores the reading under, not through the
    name, so pooling two identities' readings for "empty_required_field@tax.name" is exactly
    pooling the same instance measured twice.
    """
    out = [CLEAN]
    for piece_id, template_name in ref.pieces:
        tpl = ref.templates[template_name]
        for role in tpl.required:
            out.append(Variant(f"empty_required_field@{piece_id}.{role}", "required_field",
                                piece=piece_id, empty_fields=(role,)))
        for role in tpl.required_boxes:
            out.append(Variant(f"unchecked_box@{piece_id}.{role}", "required_checkbox",
                                piece=piece_id, uncheck=(role,)))
        for role in tpl.required_signatures:
            out.append(Variant(f"missing_signature@{piece_id}.{role}", "signature",
                                piece=piece_id, without_signature=True))
        for role, kind in tpl.dates.items():
            if kind != "expiration":
                continue
            for days in (1, 365):
                out.append(Variant(f"expired_date@{piece_id}.{role}.{days}d", "expiry",
                                    piece=piece_id, expired_days=days))
        role = _forbidden_value_role(tpl)
        if role is not None and ref.forbidden_values:
            # Only the form's own example number is injected, never the rest of
            # forbidden_values, exactly as v0.1.0 injected only "999-99-9999" and never
            # "A COMPLETER".
            out.append(Variant(f"forbidden_value@{piece_id}", "forbidden_value",
                                piece=piece_id, replace={role: ref.forbidden_values[0]}))
        for name, check, override in PAGE_DEFECTS:
            out.append(Variant(f"{name}@{piece_id}", check, piece=piece_id, image=dict(override)))
    for cons in ref.consistencies:
        piece_id = cons["readings"][-1]["piece"]
        # An identity that already lives on the replacement street would carry NO disagreement
        # at all, and every "missed" positive of this instance would be a correct silence.
        if str(ref.value(cons["data"])).strip().upper() == "DES TILLEULS":
            raise ValueError(f"{ref.identity}: its own {cons['data']} is the injected "
                             "disagreement value, the consistency instance would be no defect")
        out.append(Variant(f"diverging_{cons['data']}@{piece_id}", "consistency",
                            piece=piece_id, replace={cons["data"]: "DES TILLEULS"}))
    return tuple(out)


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
            if var.piece == piece_id and var.expired_days is not None:
                # The exhaustive enumeration's two magnitudes: the date is computed off the
                # FILING clock itself, not off a fixed expired_expiry_date, so it stays "1 day
                # past" or "365 days past" for whatever clock this identity declares.
                v = _fmt(ref.clocks["filing"] - dt.timedelta(days=var.expired_days),
                         tpl.date_format)
            else:
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
            v = f"{a['city']}, {ref.country} {a['postal_code']}"
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


def _content_tag(ref):
    """Ten hex characters that change whenever what a fixture PRINTS could change: every value
    of the reference (person, clocks, expiry, consistencies, forbidden values, signature seed,
    pieces) and the source of this module, which decides how they are printed."""
    payload = json.dumps({"dossier": ref.dossier, "clocks": ref.clocks, "person": ref.person,
                          "forbidden_values": ref.forbidden_values, "expiry": ref.expiry,
                          "pieces": ref.pieces, "consistencies": ref.consistencies,
                          "signature_seed": ref.signature_seed},
                         sort_keys=True, default=str).encode()
    with open(__file__, "rb") as f:
        payload += f.read()
    return hashlib.sha1(payload).hexdigest()[:10]


def build(ref, variant, dest, reuse=True):
    """Materialise the dossier: one filled PDF per piece, plus the image overrides.

    `reuse` serves the grid: fixtures are deterministic, the parent builds them once and the
    twelve workers just read them back. Without it the workers step on each other over the
    temporary overlay file.
    """
    var = BY_NAME[variant] if isinstance(variant, str) else variant
    os.makedirs(dest, exist_ok=True)
    tag = _content_tag(ref)
    pieces = []
    for piece_id, template_name in ref.pieces:
        tpl = ref.templates[template_name]
        # The identity goes FIRST in the cache file name. Without it a second identity built
        # into the same `dest` silently reused the first one's PDFs: same variant name, same
        # piece id, same path, a different person's dossier never actually rendered. The
        # content tag after it closes the same hole one level down: an identity file edited,
        # or this module changed, after a first build would otherwise be served its stale PDFs.
        path = os.path.join(dest, f"{ref.identity}-{tag}-{var.name}-{piece_id}.pdf")
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
            ops += "".join(_draw_signature(*_pdf_rect(tpl.pdf, field, tpl.page),
                                           seed=ref.signature_seed)
                           for field in tpl.signatures.values())
        if ops:
            _stamp(w, tpl.page, ops,
                     path[:-len(".pdf")] + f"-overlay-{os.getpid()}.pdf")
        buffer = path + f".{os.getpid()}"
        w.write(buffer)
        os.replace(buffer, path)
        override = dict(var.image) if var.piece == piece_id else {}
        pieces.append(BuiltPiece(piece_id, tpl, path, override))
    return Dossier(var.name, var.check, tuple(pieces))
