"""Les sensors bruts. Chacun rend une MESURE CONTINUE, jamais un verdict.

C'est delibere et c'est ce qui rend la grid lisible: un capteur qui rend deja un booleen a
enferme son seuil dans son code, et un seuil enferme ne se lit pas sur une curve. Ici la
grid enregistre les mesures, et l'analyse balaie les thresholds apres coup, sans recalculer une
seule image.

Quatre sensors, et le spike a deja tranche entre deux d'entre eux:
  ocr_words        positions de words. LE capteur du texte. Un field vide rend 0 mot.
  disc_ink    ink dans un disque au centre de la case, le trait de la case reste dehors.
                  LE capteur des boxes. Sur du texte il est fragile: un field VIDE lisait
                  encore +2,44% contre +4,5 pour un field rempli.
  ink_ratio      ink sur toute la zone. Concurrent de components pour la signature.
  components     components connexes de ce que le scan a AJOUTE au blank. Une signature
                  est une grosse composante etiree; le bruit est une nuee de miettes.
"""
import csv
import io
import os
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass

import numpy as np
from PIL import Image
from scipy import ndimage

from .deskew import ink, otsu
from .render import CACHE

INK_THRESHOLDS = (128, 160, 190)      # balayes par la grid, pas choisis a la main
DISC_RATIOS = (0.30, 0.42, 0.55, 0.70)


def normalize(texte):
    t = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Word:
    texte: str
    cx: float
    cy: float
    conf: float

    @property
    def norme(self):
        return normalize(self.texte)


def ocr_words(gris, language="eng", psm=11, min_conf=0.0):
    """Tous les words lus, avec leur confiance. Le filtrage par confiance vient APRES."""
    os.makedirs(CACHE, exist_ok=True)
    fd, chemin = tempfile.mkstemp(suffix=".png", dir=CACHE)
    os.close(fd)
    try:
        Image.fromarray(gris).save(chemin)
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        out = subprocess.run(["tesseract", chemin, "stdout", "-l", language, "--psm", str(psm),
                              "tsv"], capture_output=True, text=True, env=env).stdout
    finally:
        os.unlink(chemin)
    words = []
    for x in csv.DictReader(io.StringIO(out), delimiter="\t"):
        t = (x.get("text") or "").strip()
        try:
            conf = float(x.get("conf", -1))
        except ValueError:
            continue
        if not t or conf < min_conf:
            continue
        L, T, W, H = int(x["left"]), int(x["top"]), int(x["width"]), int(x["height"])
        words.append(Word(t, L + W / 2, T + H / 2, conf))
    return words


def added_words(words, preimprimes, rayon=22):
    """Ce que le scan a AJOUTE au blank, et rien d'autre.

    La soustraction se fait par TEXTE ET POSITION, pas par texte seul: dans le repere
    canonique les deux images sont superposees, donc un mot pre-imprime se retrouve au meme
    endroit. Soustraire par le texte seul ferait disparaitre un name de famille qui aurait le
    malheur de coincider avec un mot du formulaire.
    """
    par_texte = {}
    for m in preimprimes:
        par_texte.setdefault(m.norme, []).append((m.cx, m.cy))
    ajoutes = []
    for m in words:
        proches = par_texte.get(m.norme, ())
        if any((m.cx - x) ** 2 + (m.cy - y) ** 2 <= rayon * rayon for x, y in proches):
            continue
        ajoutes.append(m)
    return ajoutes


def _window(gris, zone):
    y0, y1 = max(0, zone.y0), min(gris.shape[0], zone.y1)
    x0, x1 = max(0, zone.x0), min(gris.shape[1], zone.x1)
    if y1 <= y0 or x1 <= x0:
        return None, (0, 0, 0, 0)
    return gris[y0:y1, x0:x1], (y0, x0, y1, x1)


def disc_ink(gris, zone, part=0.42, seuil=160):
    """Encre dans un disque au CENTRE de la case: le trait de la case reste dehors."""
    cx, cy = (zone.x0 + zone.x1) / 2, (zone.y0 + zone.y1) / 2
    rr = min(zone.largeur, zone.hauteur) * part
    ya, yb = max(0, int(cy - rr)), min(gris.shape[0], int(cy + rr) + 1)
    xa, xb = max(0, int(cx - rr)), min(gris.shape[1], int(cx + rr) + 1)
    if yb <= ya or xb <= xa:
        return 0.0
    Y, X = np.ogrid[ya:yb, xa:xb]
    m = ((X - cx) ** 2 + (Y - cy) ** 2) <= rr * rr
    if not m.any():
        return 0.0
    return float(((gris[ya:yb, xa:xb] < seuil) & m).sum()) / int(m.sum()) * 100


def ink_ratio(gris, zone, seuil=160):
    f, _ = _window(gris, zone)
    if f is None or f.size == 0:
        return 0.0
    return float((f < seuil).sum()) / f.size * 100


def added(gris, blank, zone, seuil=160):
    """Masque des pixels que le scan a NOIRCIS par rapport au blank, dans la zone."""
    a, frame = _window(gris, zone)
    b, _ = _window(blank, zone)
    if a is None or b is None or a.shape != b.shape:
        return None
    return (a < seuil) & ~(b < seuil)


def components(gris, blank, zone, seuil=160, aire_min=8):
    """Composantes connexes de l'added. Retour: (nombre, aire max, diagonale max).

    Une signature manuscrite est UNE grosse composante etiree. Le bruit de compression est
    une nuee de miettes, et c'est exactement ce que aire_min elimine.
    """
    m = added(gris, blank, zone, seuil)
    if m is None or not m.any():
        return 0, 0, 0.0
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if n == 0:
        return 0, 0, 0.0
    aires = np.bincount(lab.ravel())[1:]
    garde = np.nonzero(aires >= aire_min)[0]
    if garde.size == 0:
        return 0, 0, 0.0
    plus_grande = garde[int(np.argmax(aires[garde]))] + 1
    ys, xs = np.nonzero(lab == plus_grande)
    diag = float(np.hypot(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1))
    return int(garde.size), int(aires[garde].max()), diag


def words_in(words, zone, marge=8):
    z = zone.expanded(marge)
    return [m for m in words if z.contains(m.cx, m.cy)]


def ocr_zone_words(gris, zone, language="eng", psm=11, marge=6, agrandir=1):
    """OCR de la ZONE SEULE, coordonnees ramenees dans le repere de la page.

    Concurrent direct de l'OCR pleine page, et le duel n'est pas theorique: sur le Cerfa
    14011, dont les fields sont encadres, l'OCR pleine page en psm 11 lit "108600" pour
    "03600" en avalant la bordure, et ne voit rien du tout dans NoCarteID. Le meme field
    decoupe et lu seul rend "AB1234567" sans une faute. En echange il coute un appel tesseract
    par field au lieu d'un par page: c'est a la grid de dire ou le prix vaut la peine.

    psm 11 sans agrandissement, mesure le 2026-08-21 sur les 25 fields du dossier a render
    propre: ressemblance moyenne a la value attendue 0,911 contre 0,858 pour l'OCR pleine
    page, 1 echec contre 2. psm 7 (ligne unique) tombe a 0,817 et psm 13 a 0,768. Agrandir la
    vignette x2 avant l'OCR degrade tout (0,765): tesseract fait deja son propre
    reechantillonnage et le notre ne fait qu'ajouter du blur.
    """
    z = zone.expanded(marge)
    y0, y1 = max(0, z.y0), min(gris.shape[0], z.y1)
    x0, x1 = max(0, z.x0), min(gris.shape[1], z.x1)
    if y1 - y0 < 4 or x1 - x0 < 4:
        return []
    crop = gris[y0:y1, x0:x1]
    if agrandir > 1:
        crop = np.asarray(Image.fromarray(crop).resize(
            (crop.shape[1] * agrandir, crop.shape[0] * agrandir), Image.LANCZOS))
    ech = agrandir
    return [Word(m.texte, x0 + m.cx / ech, y0 + m.cy / ech, m.conf)
            for m in ocr_words(crop, language, psm=psm)]
