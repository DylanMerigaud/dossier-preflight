"""Les zones viennent du PDF lui-meme. Aucune coordonnee mesuree a la main."""
import os
from dataclasses import dataclass

from pypdf import PdfReader

from . import CANON_DPI


@dataclass(frozen=True)
class Zone:
    """Rectangle declare par l'AcroForm, en pixels du repere canonique."""
    nom: str
    page: int
    x0: int
    y0: int
    x1: int
    y1: int
    genre: str          # /Tx champ texte, /Btn case a cocher, /Push bouton, /Ch liste

    @property
    def largeur(self):
        return self.x1 - self.x0

    @property
    def hauteur(self):
        return self.y1 - self.y0

    def dilatee(self, marge):
        return Zone(self.nom, self.page, self.x0 - marge, self.y0 - marge,
                    self.x1 + marge, self.y1 + marge, self.genre)

    def contient(self, cx, cy):
        return self.x0 <= cx <= self.x1 and self.y0 <= cy <= self.y1


def zones_declarees(pdf, page=1, dpi=CANON_DPI):
    """Les rectangles que le formulaire declare, convertis en pixels ecran.

    Le PDF a son origine en bas a gauche et l'image en haut a gauche: d'ou le H - y.
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
                                 int(x1 * s), int((H - y0) * s), _genre(o))
    return out


def _genre(o):
    """Un bouton poussoir n'est pas une case a cocher.

    Le Cerfa 14011 porte deux poussoirs "Imprimer" et "Reinitialiser" declares /Btn comme les
    vraies cases. Les compter comme des cases pollue le taux de faux positifs du controle des
    cases obligatoires: ils ne seront jamais coches, par construction. Le drapeau /Ff les
    distingue (bit 17 poussoir, bit 16 bouton radio).
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


def taille_page(pdf, page=1, dpi=CANON_DPI):
    p = PdfReader(pdf).pages[page - 1]
    s = dpi / 72.0
    return int(float(p.mediabox.width) * s), int(float(p.mediabox.height) * s)


def pouces_page(pdf, page=1):
    p = PdfReader(pdf).pages[page - 1]
    return float(p.mediabox.width) / 72.0, float(p.mediabox.height) / 72.0
