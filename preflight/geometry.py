"""Zones come from the PDF itself. No coordinate is measured by hand."""
import os
from dataclasses import dataclass

from pypdf import PdfReader

from . import CANON_DPI


@dataclass(frozen=True)
class Zone:
    """A rectangle declared by the AcroForm, in canonical-frame pixels."""
    name: str
    page: int
    x0: int
    y0: int
    x1: int
    y1: int
    kind: str          # /Tx text field, /Btn checkbox, /Push push button, /Ch list

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0

    def expanded(self, margin):
        return Zone(self.name, self.page, self.x0 - margin, self.y0 - margin,
                    self.x1 + margin, self.y1 + margin, self.kind)

    def contains(self, cx, cy):
        return self.x0 <= cx <= self.x1 and self.y0 <= cy <= self.y1


def declared_zones(pdf, page=1, dpi=CANON_DPI):
    """The rectangles the form declares, converted to screen pixels.

    A PDF has its origin bottom left and an image has it top left: hence the H - y.
    """
    p = PdfReader(pdf).pages[page - 1]
    H, s = float(p.mediabox.height), dpi / 72.0
    out = {}
    for an in p.get("/Annots", []) or []:
        o = an.get_object()
        if not (o.get("/T") and "/Rect" in o):
            continue
        x0, y0, x1, y1 = [float(v) for v in o["/Rect"]]
        out[str(o["/T"])] = Zone(str(o["/T"]), page, int(x0 * s), int((H - y1) * s),
                                 int(x1 * s), int((H - y0) * s), _kind(o))
    return out


def _kind(o):
    """A push button is not a checkbox.

    Cerfa 14011 carries two push buttons, "Imprimer" and "Reinitialiser", declared /Btn just
    like the real boxes. Counting them as boxes pollutes the false positive rate of the
    required-checkbox check: by construction they will never be ticked. The /Ff flag tells
    them apart (bit 17 push button, bit 16 radio button).
    """
    ft = str(o.get("/FT"))
    if ft != "/Btn":
        return ft
    ff = int(o.get("/Ff", 0) or 0)
    if ff & (1 << 16):
        return "/Push"
    if ff & (1 << 15):
        return "/Radio"
    return "/Btn"


def page_size(pdf, page=1, dpi=CANON_DPI):
    p = PdfReader(pdf).pages[page - 1]
    s = dpi / 72.0
    return int(float(p.mediabox.width) * s), int(float(p.mediabox.height) * s)


def page_inches(pdf, page=1):
    p = PdfReader(pdf).pages[page - 1]
    return float(p.mediabox.width) / 72.0, float(p.mediabox.height) / 72.0
