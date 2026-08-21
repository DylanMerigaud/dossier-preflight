"""Un dossier SAIN, puis N variantes portant chacune UN SEUL defaut connu.

C'est la contrepartie de la grille: sans verite terrain il n'y a ni taux de vrai positif ni
taux de faux positif, donc pas de courbe, donc pas de seuil lisible. Chaque variante nomme le
controle qui DOIT crier, et le test exige que les autres se taisent. Un controle qui crie sur
la variante du voisin est un faux positif, et un faux positif coute cher: une regle qui crie
au loup fait survoler toutes celles d'a cote.

Toutes les valeurs viennent du referentiel FICTIF. Aucune personne reelle, aucune adresse
reelle, aucun document delivre a quiconque.

LE TEXTE EST IMPRIME PAR UN CALQUE, PAS PAR L'APPARENCE ACROFORM, et ce choix a ete paye.
Deux des trois formulaires du corpus portent une couche XFA (le W-9 et le Cerfa 14011), et
sur eux la generation d'apparence de pypdf est infidele: trois champs du Cerfa ne
s'imprimaient pas du tout, MARISOL sortait "SOL", et les valeurs restantes se collaient a la
bordure du champ au point que l'OCR lisait "|LDES ACACIAS". La grille aurait alors mesure mes
bugs de remplissage et pas mes capteurs. Le calque pose le texte a la position que l'AcroForm
DECLARE, en Helvetica, exactement comme une imprimante le ferait. Les cases a cocher, elles,
restent remplies par l'AcroForm: leur apparence est fournie par le formulaire et elle rend
juste (delta d'encre +21 a +28 sur les trois pieces).
"""
import datetime as dt
import os
import re
from dataclasses import dataclass, field

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


@dataclass(frozen=True)
class Variante:
    """Un defaut, et un seul. `controle` est celui qui doit se declencher."""
    nom: str
    controle: str
    piece: str = ""
    vider: tuple = ()
    decocher: tuple = ()
    sans_signature: bool = False
    date_perimee: bool = False
    remplacer: dict = field(default_factory=dict)     # role -> valeur fausse
    image: dict = field(default_factory=dict)         # surcharge de degradation


SAIN = Variante("sain", controle="")

VARIANTES = (
    SAIN,
    Variante("champ_requis_vide", "champ_requis", piece="emploi", vider=("ville",)),
    Variante("case_non_cochee", "case_obligatoire", piece="fiscal", decocher=("statut",)),
    Variante("signature_absente", "signature", piece="emploi", sans_signature=True),
    Variante("date_perimee", "validite", piece="emploi", date_perimee=True),
    Variante("adresse_divergente", "coherence", piece="identite",
             remplacer={"nom_voie": "DES TILLEULS"}),
    Variante("valeur_interdite", "valeur_interdite", piece="emploi",
             remplacer={"numero_secu": "999-99-9999"}),
    # 72 dpi est SOUS le plus bas dpi de la grille (96): sans ca la variante ferait doublon
    # avec l'axe dpi de la grille et ne mesurerait rien de neuf.
    Variante("resolution_basse", "resolution", piece="fiscal", image={"dpi": 72}),
    Variante("page_coupee", "page_coupee", piece="fiscal", image={"rogne": 0.18}),
    Variante("page_tournee", "page_tournee", piece="fiscal", image={"quart": 1}),
)

PAR_NOM = {v.nom: v for v in VARIANTES}
CONTROLES_VISES = tuple(v.controle for v in VARIANTES if v.controle)


@dataclass(frozen=True)
class PieceMaterielle:
    id: str
    gabarit: object
    pdf: str
    surcharge_image: dict


@dataclass(frozen=True)
class Dossier:
    variante: str
    controle_vise: str
    pieces: tuple

    def piece(self, ident):
        for p in self.pieces:
            if p.id == ident:
                return p
        raise KeyError(ident)


def _fmt(date, forme):
    return date.strftime("%m/%d/%Y" if forme == "us" else "%d/%m/%Y")


def _etat_coche(pdf, champ, page):
    """L'etat "coche" n'est pas devine: il est declare par l'apparence du widget.

    Le W-9 dit /1, le I-9 dit /On. Ecrire l'un des deux en dur casserait l'autre en silence,
    et une case qui reste vide alors qu'on l'a cochee fabrique un faux defaut.
    """
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == champ:
            ap = o.get("/AP", {}).get("/N", {})
            etats = [k for k in (ap.keys() if hasattr(ap, "keys") else []) if k != "/Off"]
            if etats:
                return etats[0]
    return "/1"


def _rect_pdf(pdf, champ, page):
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if str(o.get("/T")) == champ:
            return [float(v) for v in o["/Rect"]]
    raise KeyError(champ)


def _echapper(t):
    return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _trace_texte(x0, y0, x1, y1, valeur):
    """Le texte pose a la position DECLAREE par le champ, comme une imprimante le poserait."""
    if not valeur:
        return ""
    haut = y1 - y0
    corps = max(6.0, min(11.0, haut * 0.58))
    base = y0 + (haut - corps) / 2 + corps * 0.22
    return (f"BT /F1 {corps:.1f} Tf 1 0 0 1 {x0 + 3:.1f} {base:.1f} Tm "
            f"({_echapper(valeur)}) Tj ET\n")


def _trace_signature(x0, y0, x1, y1, graine=11):
    """Une signature manuscrite: un trait unique, continu, etire.

    Dessine en vectoriel dans le PDF, pas peint sur l'image: la fixture reste un PDF, et la
    signature traverse donc la meme chaine de degradation que le reste de la page.
    """
    import random
    r = random.Random(graine)
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


def _maxlen(pdf, page):
    out = {}
    for an in PdfReader(pdf).pages[page - 1].get("/Annots", []) or []:
        o = an.get_object()
        if o.get("/T") is not None and o.get("/MaxLen") is not None:
            out[str(o["/T"])] = int(o["/MaxLen"])
    return out


def _poser(vals, champs, valeur, maxlen):
    """Ecrit une valeur dans un ou plusieurs champs, en respectant le MaxLen DECLARE.

    Le formulaire dit lui-meme combien de caracteres il accepte: le W-9 eclate le numero
    fiscal sur trois cases de 3, 2 et 4, le Cerfa veut une date de naissance en 8 caracteres
    sans separateur. Ignorer ce MaxLen fait tronquer silencieusement par pypdf, et la fixture
    porte alors un defaut qu'on n'a pas voulu.
    """
    if len(champs) > 1:
        morceaux = re.split(r"[^0-9A-Za-z]+", valeur)
        for c, m in zip(champs, morceaux):
            vals[c] = m
        return
    c = champs[0]
    m = maxlen.get(c)
    if m is not None and len(valeur) > m:
        valeur = re.sub(r"[^0-9A-Za-z]", "", valeur)[:m]
    vals[c] = valeur


def _valeurs(ref, gab, var, piece_id):
    """Ce que la piece doit porter, defaut de la variante compris."""
    vals = {}
    maxlen = _maxlen(gab.pdf, gab.page)
    for role in gab.champs:
        if var.piece == piece_id and role in var.vider:
            continue
        if var.piece == piece_id and role in var.remplacer:
            v = var.remplacer[role]
        elif role in gab.dates and gab.dates[role] == "expiration":
            perime = var.piece == piece_id and var.date_perimee
            v = _fmt(ref.validite["date_expiration_perimee" if perime else "date_expiration_saine"],
                     gab.format_date)
        elif role == "date_signature":
            v = _fmt(ref.horloges["guichet"], gab.format_date)
        elif role == "date_naissance":
            v = _fmt(dt.datetime.strptime(ref.valeur("date_naissance"), "%d/%m/%Y").date(),
                     gab.format_date)
        elif role == "adresse":
            a = ref.personne["adresse"]
            v = f"{a['numero']} {a['type_voie']} {a['nom_voie']}"
        elif role == "ville" and gab.nom == "fw9":
            a = ref.personne["adresse"]
            v = f"{a['ville']}, FR {a['code_postal']}"
        else:
            v = ref.valeur(role)
        _poser(vals, gab.champ(role), str(v), maxlen)
    return vals


def _apposer(w, page_no, ops, tampon):
    """Fusionne un calque vectoriel sur la page. Helvetica est une police de base du format
    PDF: rien a embarquer, rien a installer, et poppler la rend partout."""
    page = w.pages[page_no - 1]
    calque = PdfWriter()
    vierge = calque.add_blank_page(float(page.mediabox.width), float(page.mediabox.height))
    flux = DecodedStreamObject()
    flux.set_data(ops.encode("latin-1", "replace"))
    vierge[NameObject("/Contents")] = calque._add_object(flux)
    vierge[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica")})})})
    calque.write(tampon)
    page.merge_page(PdfReader(tampon).pages[0])
    os.unlink(tampon)


def construire(ref, variante, dest, reutiliser=True):
    """Materialise le dossier: un PDF rempli par piece, plus les surcharges d'image.

    `reutiliser` sert la grille: les fixtures sont deterministes, le parent les construit une
    fois et les douze processus se contentent de les relire. Sans ca les processus se
    marchent dessus sur le fichier de calque temporaire.
    """
    var = PAR_NOM[variante] if isinstance(variante, str) else variante
    os.makedirs(dest, exist_ok=True)
    pieces = []
    for piece_id, nom_gab in ref.pieces:
        gab = ref.gabarits[nom_gab]
        chemin = os.path.join(dest, f"{var.nom}-{piece_id}.pdf")
        if reutiliser and os.path.exists(chemin):
            pieces.append(PieceMaterielle(piece_id, gab, chemin,
                                          dict(var.image) if var.piece == piece_id else {}))
            continue
        vals = _valeurs(ref, gab, var, piece_id)
        for role, champ in gab.cases.items():
            if not (var.piece == piece_id and role in var.decocher):
                vals[champ] = _etat_coche(gab.pdf, champ, gab.page)
        cases = {c: v for c, v in vals.items() if c in gab.cases.values()}
        w = PdfWriter(clone_from=gab.pdf)
        w.set_need_appearances_writer(True)
        if cases:
            w.update_page_form_field_values(w.pages[gab.page - 1], cases, auto_regenerate=True)
        ops = "".join(_trace_texte(*_rect_pdf(gab.pdf, champ, gab.page), valeur)
                      for champ, valeur in vals.items() if champ not in cases)
        if gab.signatures and not (var.piece == piece_id and var.sans_signature):
            ops += "".join(_trace_signature(*_rect_pdf(gab.pdf, champ, gab.page))
                           for champ in gab.signatures.values())
        if ops:
            _apposer(w, gab.page, ops,
                     os.path.join(dest, f"{var.nom}-{piece_id}-calque-{os.getpid()}.pdf"))
        tampon = chemin + f".{os.getpid()}"
        w.write(tampon)
        os.replace(tampon, chemin)
        surcharge = dict(var.image) if var.piece == piece_id else {}
        pieces.append(PieceMaterielle(piece_id, gab, chemin, surcharge))
    return Dossier(var.nom, var.controle, tuple(pieces))
