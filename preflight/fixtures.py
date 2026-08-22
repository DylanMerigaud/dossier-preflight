"""Un dossier SAIN, puis N variantes portant chacune UN SEUL defaut connu.

C'est la contrepartie de la grid: sans verite terrain il n'y a ni taux de vrai positif ni
taux de faux positif, donc pas de curve, donc pas de seuil lisible. Chaque variant nomme le
check qui DOIT crier, et le test exige que les autres se taisent. Un check qui crie sur
la variant du voisin est un faux positif, et un faux positif coute cher: une regle qui crie
au loup fait survoler toutes celles d'a cote.

Toutes les valeurs viennent du reference FICTIONAL. Aucune person reelle, aucune address
reelle, aucun document delivre a quiconque.

LE TEXTE EST IMPRIME PAR UN CALQUE, PAS PAR L'APPARENCE ACROFORM, et ce choix a ete paye.
Deux des trois formulaires du corpus portent une couche XFA (le W-9 et le Cerfa 14011), et
sur eux la generation d'apparence de pypdf est infidele: trois fields du Cerfa ne
s'imprimaient pas du tout, MARISOL sortait "SOL", et les valeurs restantes se collaient a la
bordure du field au point que l'OCR lisait "|LDES ACACIAS". La grid aurait alors mesure mes
bugs de remplissage et pas mes sensors. Le calque pose le texte a la position que l'AcroForm
DECLARE, en Helvetica, exactement comme une imprimante le ferait. Les boxes a cocher, elles,
restent remplies par l'AcroForm: leur apparence est fournie par le formulaire et elle rend
juste (delta d'ink +21 a +28 sur les trois pieces).
"""
import datetime as dt
import os
import re
from dataclasses import dataclass, field

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


@dataclass(frozen=True)
class Variant:
    """Un defaut, et un seul. `check` est celui qui doit se declencher."""
    name: str
    check: str
    piece: str = ""
    empty_fields: tuple = ()
    uncheck: tuple = ()
    without_signature: bool = False
    expired_date: bool = False
    replace: dict = field(default_factory=dict)     # role -> value fausse
    image: dict = field(default_factory=dict)         # surcharge de degradation


SAIN = Variant("clean", check="")

VARIANTS = (
    SAIN,
    Variant("empty_required_field", "required_field", piece="employment", empty_fields=("city",)),
    Variant("unchecked_box", "required_checkbox", piece="tax", uncheck=("status",)),
    Variant("missing_signature", "signature", piece="employment", without_signature=True),
    Variant("expired_date", "expiry", piece="employment", expired_date=True),
    Variant("diverging_address", "consistency", piece="identity",
             replace={"street_name": "DES TILLEULS"}),
    Variant("forbidden_value", "forbidden_value", piece="employment",
             replace={"ssn": "999-99-9999"}),
    # 72 dpi est SOUS le plus bas dpi de la grid (96): sans ca la variant ferait doublon
    # avec l'axe dpi de la grid et ne mesurerait rien de neuf.
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
    """L'etat "coche" n'est pas devine: il est declare par l'apparence du widget.

    Le W-9 dit /1, le I-9 dit /On. Ecrire l'un des deux en dur casserait l'autre en silence,
    et une case qui reste vide alors qu'on l'a cochee fabrique un faux defaut.
    """
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == field:
            ap = o.get("/AP", {}).get("/N", {})
            etats = [k for k in (ap.keys() if hasattr(ap, "keys") else []) if k != "/Off"]
            if etats:
                return etats[0]
    return "/1"


def _pdf_rect(pdf, field, page):
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == field:
            return [float(v) for v in o["/Rect"]]
    raise KeyError(field)


def _escape(t):
    return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


GLYPH_WIDTH = 0.6      # largeur moyenne d'un caractere Helvetica, en em


def _draw_text(x0, y0, x1, y1, value, peigne=0):
    """Le texte pose a la position DECLAREE par le field, comme une imprimante le poserait.

    UN CHAMP PEIGNE S'IMPRIME UNE CASE A LA FOIS, et le formulaire le declare lui-meme
    (drapeau /Ff bit 25). Le W-9 peigne son number tax, le I-9 son number de securite
    sociale, le Cerfa cinq fields dont le number de carte. Poser la chaine en continu par
    dessus les separateurs produit un field qu'aucun OCR ne lit: mesure le 2026-08-21, le
    number de carte du Cerfa rendait 0 caractere lisible pleine page et "| | | | | | | |" en
    OCR de zone, c'est-a-dire les separateurs seuls. La grid aurait mesure cette faute
    d'impression et conclu, faux, que le check des fields required ne tient pas.
    """
    if not value:
        return ""
    haut = y1 - y0
    if peigne:
        case = (x1 - x0) / peigne
        corps = max(5.0, min(haut * 0.58, case * 1.25))
        base = y0 + (haut - corps) / 2 + corps * 0.22
        ops = []
        for i, c in enumerate(value[:peigne]):
            if c == " ":
                continue
            centre = x0 + case * (i + 0.5) - corps * GLYPH_WIDTH / 2
            ops.append(f"BT /F1 {corps:.1f} Tf 1 0 0 1 {centre:.1f} {base:.1f} Tm "
                       f"({_escape(c)}) Tj ET")
        return "\n".join(ops) + "\n"
    corps = max(6.0, min(11.0, haut * 0.58))
    base = y0 + (haut - corps) / 2 + corps * 0.22
    return (f"BT /F1 {corps:.1f} Tf 1 0 0 1 {x0 + 3:.1f} {base:.1f} Tm "
            f"({_escape(value)}) Tj ET\n")


def _draw_signature(x0, y0, x1, y1, seed=11):
    """Une signature manuscrite: un trait unique, continu, etire.

    Dessine en vectoriel dans le PDF, pas peint sur l'image: la fixture reste un PDF, et la
    signature traverse donc la meme chaine de degradation que le reste de la page.
    """
    import random
    r = random.Random(seed)
    marge_x, marge_y = (x1 - x0) * 0.12, (y1 - y0) * 0.22
    ax, bx = x0 + marge_x, x1 - marge_x
    cy = (y0 + y1) / 2
    amp = max(4.0, (y1 - y0) / 2 - marge_y)
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
    """Les fields qui se remplissent UNE CASE PAR CARACTERE, tels que le PDF les declare."""
    out = {}
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if o.get("/T") is None or o.get("/MaxLen") is None:
            continue
        if int(o.get("/Ff", 0) or 0) & COMB_FLAG:
            out[str(o["/T"])] = int(o["/MaxLen"])
    return out


def _place(vals, fields, value, maxlen):
    """Ecrit une value dans un ou plusieurs fields, en respectant le MaxLen DECLARE.

    Le formulaire dit lui-meme combien de caracteres il accepte: le W-9 eclate le number
    tax sur trois boxes de 3, 2 et 4, le Cerfa veut une date de naissance en 8 caracteres
    sans separateur. Ignorer ce MaxLen fait tronquer silencieusement par pypdf, et la fixture
    porte alors un defaut qu'on n'a pas voulu.
    """
    if len(fields) > 1:
        morceaux = re.split(r"[^0-9A-Za-z]+", value)
        for c, m in zip(fields, morceaux):
            vals[c] = m
        return
    c = fields[0]
    m = maxlen.get(c)
    if m is not None and len(value) > m:
        value = re.sub(r"[^0-9A-Za-z]", "", value)[:m]
    vals[c] = value


def _values(ref, gab, var, piece_id):
    """Ce que la piece doit porter, defaut de la variant compris."""
    vals = {}
    maxlen = _maxlen(gab.pdf, gab.page)
    for role in gab.fields:
        if var.piece == piece_id and role in var.empty_fields:
            continue
        if var.piece == piece_id and role in var.replace:
            v = var.replace[role]
        elif role in gab.dates and gab.dates[role] == "expiration":
            perime = var.piece == piece_id and var.expired_date
            v = _fmt(ref.expiry["expired_expiry_date" if perime else "valid_expiry_date"],
                     gab.date_format)
        elif role == "signature_date":
            v = _fmt(ref.clocks["filing"], gab.date_format)
        elif role == "birth_date":
            v = _fmt(dt.datetime.strptime(ref.value("birth_date"), "%d/%m/%Y").date(),
                     gab.date_format)
        elif role == "address":
            a = ref.person["address"]
            v = f"{a['number']} {a['street_type']} {a['street_name']}"
        elif role == "city" and gab.name == "fw9":
            a = ref.person["address"]
            v = f"{a['city']}, FR {a['postal_code']}"
        else:
            v = ref.value(role)
        _place(vals, gab.field(role), str(v), maxlen)
    return vals


def _stamp(w, page_no, ops, tampon):
    """Fusionne un calque vectoriel sur la page. Helvetica est une police de base du format
    PDF: rien a embarquer, rien a installer, et poppler la rend partout."""
    page = w.pages[page_no - 1]
    calque = PdfWriter()
    blank = calque.add_blank_page(float(page.mediabox.width), float(page.mediabox.height))
    flux = DecodedStreamObject()
    flux.set_data(ops.encode("latin-1", "replace"))
    blank[NameObject("/Contents")] = calque._add_object(flux)
    blank[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")})})})
    calque.write(tampon)
    page.merge_page(PdfReader(tampon).pages[0])
    os.unlink(tampon)


def build(ref, variant, dest, reutiliser=True):
    """Materialise le dossier: un PDF rempli par piece, plus les surcharges d'image.

    `reutiliser` sert la grid: les fixtures sont deterministes, le parent les construit une
    fois et les douze processus se contentent de les relire. Sans ca les processus se
    marchent dessus sur le fichier de calque temporaire.
    """
    var = BY_NAME[variant] if isinstance(variant, str) else variant
    os.makedirs(dest, exist_ok=True)
    pieces = []
    for piece_id, nom_gab in ref.pieces:
        gab = ref.templates[nom_gab]
        chemin = os.path.join(dest, f"{var.name}-{piece_id}.pdf")
        if reutiliser and os.path.exists(chemin):
            pieces.append(BuiltPiece(piece_id, gab, chemin,
                                          dict(var.image) if var.piece == piece_id else {}))
            continue
        vals = _values(ref, gab, var, piece_id)
        for role, field in gab.boxes.items():
            if not (var.piece == piece_id and role in var.uncheck):
                vals[field] = _checked_state(gab.pdf, field, gab.page)
        boxes = {c: v for c, v in vals.items() if c in gab.boxes.values()}
        w = PdfWriter(clone_from=gab.pdf)
        w.set_need_appearances_writer(True)
        if boxes:
            w.update_page_form_field_values(w.pages[gab.page - 1], boxes, auto_regenerate=True)
        peignes = _combs(gab.pdf, gab.page)
        ops = "".join(_draw_text(*_pdf_rect(gab.pdf, field, gab.page), value,
                                   peignes.get(field, 0))
                      for field, value in vals.items() if field not in boxes)
        if gab.signatures and not (var.piece == piece_id and var.without_signature):
            ops += "".join(_draw_signature(*_pdf_rect(gab.pdf, field, gab.page))
                           for field in gab.signatures.values())
        if ops:
            _stamp(w, gab.page, ops,
                     os.path.join(dest, f"{var.name}-{piece_id}-calque-{os.getpid()}.pdf"))
        tampon = chemin + f".{os.getpid()}"
        w.write(tampon)
        os.replace(tampon, chemin)
        surcharge = dict(var.image) if var.piece == piece_id else {}
        pieces.append(BuiltPiece(piece_id, gab, chemin, surcharge))
    return Dossier(var.name, var.check, tuple(pieces))
