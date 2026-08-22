"""Ramener un scan dans le repere du blank, AVANT que la moindre coordonnee soit lue.

Le spike a paye cette lecon: l'ink lue dans les zones d'un scan tourne de 0,45 deg a
annonce 8 boxes cochees sur 8 alors que rien n'etait coche. Un check par coordonnees sur
une page non redressee ne mesure pas ce qu'il croit measure.

Deux etages:

  deskew  axe puis angle fin, par maximisation de la variance du profil de projection
             horizontal, grossier puis fin. Trois pieges mesures le 2026-08-21 sur les
             cellules dures:
               - reduire d'un FACTEUR fixe (/8) donne 102 px de large a 96 dpi et l'angle
                 devient introuvable. On normalise a une LARGEUR target.
               - le seuil d'ink fixe a 160 rate les petits angles sur image reduite, parce
                 que le reechantillonnage eclaircit les traits. Otsu par image le corrige.
               - sur une page couchee a 90 deg le profil horizontal n'a plus de structure de
                 lignes: l'angle fin part chercher dans le vide et rend -0,15 au lieu de
                 -0,50. L'AXE se decide donc AVANT l'angle, par le meme critere.
             Cout 19 fois moindre que la recherche naive pleine page, meme angle trouve.

  register    orientation en quarts de tour, scale et translation, par correlation croisee
             contre le VIERGE. C'est ce qui rend le repere canonique independant du dpi de
             numerisation, et c'est aussi ce qui donne le dpi source estime et la coverage
             de page sans read_piece la moindre metadonnee (un vrai scan ne les a pas).
"""
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from . import CANON_DPI

PLAGE_ANGLE = 6.0          # la grid injecte jusqu'a 4 deg
LARGEUR_GROSSIER = 400
LARGEUR_FIN = 850
PAS_GROSSIER = 0.2
PAS_FIN = 0.05


def otsu(gris):
    """Seuil d'ink propre a l'image. Un seuil fixe ne survit pas au changement de dpi."""
    h = np.histogram(gris, bins=256, range=(0, 256))[0].astype(np.float64)
    tot = h.sum()
    w0 = np.cumsum(h)
    w1 = tot - w0
    m = np.cumsum(h * np.arange(256))
    with np.errstate(invalid="ignore", divide="ignore"):
        inter = (m[-1] * w0 / tot - m) ** 2 / (w0 * w1)
    return int(np.nanargmax(inter))


def ink(gris, seuil=None):
    return gris < (otsu(gris) if seuil is None else seuil)


def _width(gris, target):
    h, w = gris.shape
    if w <= target:
        return gris
    f = target / float(w)
    return np.asarray(Image.fromarray(gris).resize((int(w * f), int(h * f)), Image.BILINEAR))


def _profile_variance(gris, seuil, angle):
    if angle:
        gris = np.asarray(Image.fromarray(gris).rotate(angle, resample=Image.BILINEAR,
                                                       fillcolor=255))
    return float(np.var((gris < seuil).sum(axis=1)))


def deskew(gris, plage=PLAGE_ANGLE, axes=(0, 1)):
    """Retour: (quarter_turns d'axe, angle applique, image droite et debout).

    Le quarter_turns d'axe vaut 0 ou 1: il dit s'il a fallu coucher la page pour retrouver des lignes
    de texte horizontales. Le demi-tour (0 contre 180) n'est pas decidable ici, les deux ont
    exactement le meme profil de projection: c'est le recalage contre le blank qui tranche.
    """
    meilleur = None
    for axe in axes:
        tourne = np.rot90(gris, -axe) if axe else gris
        petit = _width(tourne, LARGEUR_GROSSIER)
        s = otsu(petit)
        ang = max(np.arange(-plage, plage + 1e-9, PAS_GROSSIER),
                  key=lambda a: _profile_variance(petit, s, a))
        v = _profile_variance(petit, s, ang)
        if meilleur is None or v > meilleur[0]:
            meilleur = (v, axe, ang, tourne)
    _, axe, grossier, tourne = meilleur
    moyen = _width(tourne, LARGEUR_FIN)
    sm = otsu(moyen)
    fin = max(np.arange(grossier - PAS_GROSSIER, grossier + PAS_GROSSIER + 1e-9, PAS_FIN),
              key=lambda a: _profile_variance(moyen, sm, a))
    if abs(fin) < 1e-9:
        return axe, 0.0, tourne
    return axe, float(fin), np.asarray(Image.fromarray(tourne).rotate(
        fin, resample=Image.BICUBIC, fillcolor=255))


@dataclass(frozen=True)
class Registration:
    quarter_turns: int             # quarts de tour a apply au scan pour le remettre droit
    scale: float         # facteur applique au scan pour atteindre le repere canonique
    dx: int
    dy: int
    peak: float             # peak de correlation croisee normalise, 0 a 1
    coverage: float      # fraction de l'ink du blank que le frame du scan recouvre
    source_dpi: float      # CANON_DPI / scale, estime sans read_piece aucune metadonnee
    pics: tuple = ()       # meilleur peak par quarter_turns evalue, pour la marge d'orientation


def _correlation(a, b):
    """Pic de correlation croisee normalisee entre deux cartes d'ink, et son decalage."""
    H = max(a.shape[0], b.shape[0])
    W = max(a.shape[1], b.shape[1])
    A = np.zeros((H, W), np.float32)
    B = np.zeros((H, W), np.float32)
    A[:a.shape[0], :a.shape[1]] = a
    B[:b.shape[0], :b.shape[1]] = b
    na, nb = np.linalg.norm(A), np.linalg.norm(B)
    if na == 0 or nb == 0:
        return 0, 0, 0.0
    c = np.fft.irfft2(np.fft.rfft2(A) * np.conj(np.fft.rfft2(B)), s=(H, W))
    dy, dx = divmod(int(np.argmax(c)), W)
    if dy > H // 2:
        dy -= H
    if dx > W // 2:
        dx -= W
    return dy, dx, float(c.max() / (na * nb))


def _resize(gris, scale):
    h, w = gris.shape
    return np.asarray(Image.fromarray(gris).resize(
        (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.BILINEAR))


def register(gris, blank, ratios=(0.78, 0.84, 0.90, 0.96, 1.0, 1.04), task=480,
            quarts=(0, 1, 2, 3), affinages=((0.06, 7, 720), (0.012, 7, 720))):
    """Orientation, scale et translation qui collent le scan sur le blank.

    Tout se joue sur des cartes d'ink reduites a `task` pixels de large: la correlation
    y coute quelques millisecondes. L'scale de base vient du rapport des hauteurs, et les
    ratios balaient autour, vers le bas surtout, parce qu'une page ROGNEE fait croire a une
    scale trop grande: rogner 18% de la hauteur fait surestimer l'scale de 22%.

    Le balayage grossier seul ne suffit pas. Son pas de 6% laisse 2,4% d'erreur d'scale,
    soit 53 px de derive en bas d'une page de 2200 px: assez pour que les zones declarees
    tombent une ligne trop bas et que le disque d'une case rate la case. Mesure le
    2026-08-21: sans affinage, la page rognee declenchait a tort le check des boxes
    obligatoires (delta d'ink +6,7 au lieu de +21,1) et celui des fields required. Deux
    passes d'affinage ramenent l'erreur d'scale sous 0,2%.
    """
    H, W = blank.shape
    meilleur = None
    par_quart = {}

    def essayer(ref, f, tourne, quarter_turns, ech):
        dy, dx, peak = _correlation(ref, ink(_resize(tourne, ech * f)).astype(np.float32))
        par_quart[quarter_turns] = max(par_quart.get(quarter_turns, 0.0), peak)
        return (peak, quarter_turns, ech, dx / f, dy / f, tourne)

    f = task / float(W)
    ref = ink(_resize(blank, f)).astype(np.float32)
    for quarter_turns in quarts:
        tourne = np.rot90(gris, -quarter_turns) if quarter_turns else gris
        base = H / float(tourne.shape[0])
        for r in ratios:
            c = essayer(ref, f, tourne, quarter_turns, base * r)
            if meilleur is None or c[0] > meilleur[0]:
                meilleur = c
    for demi, n, larg in affinages:
        _, quarter_turns, ech, _, _, tourne = meilleur
        f = larg / float(W)
        ref = ink(_resize(blank, f)).astype(np.float32)
        for r in np.linspace(1 - demi, 1 + demi, n):
            c = essayer(ref, f, tourne, quarter_turns, ech * r)
            if c[0] > meilleur[0]:
                meilleur = c
    peak, quarter_turns, ech, dx, dy, tourne = meilleur
    par_quart = tuple(sorted(par_quart.items()))
    h, w = tourne.shape
    y0, x0 = max(0, int(round(dy))), max(0, int(round(dx)))
    y1, x1 = min(H, int(round(dy + h * ech))), min(W, int(round(dx + w * ech)))
    enc_ref = ink(blank)
    dedans = int(enc_ref[y0:y1, x0:x1].sum()) if (y1 > y0 and x1 > x0) else 0
    return Registration(quarter_turns, float(ech), int(round(dx)), int(round(dy)), peak,
                    dedans / max(1, int(enc_ref.sum())), CANON_DPI / float(ech), par_quart)


@dataclass(frozen=True)
class Frame:
    """Le scan a SA resolution, et le blank amene jusqu'a lui.

    C'EST L'INVERSE DE CE QU'ON FAIT D'INSTINCT, et le renversement est une mesure, pas un
    gout. Ramener le scan dans un repere canonique a 200 dpi oblige a le reechantillonner des
    que sa resolution differe, et ce reechantillonnage detruit le petit texte encadre: sur le
    Cerfa 14011, un scan a 300 dpi rendait 0 caractere lisible dans trois fields qui en
    rendaient 14, 5 et 10 a 200 dpi, ou l'scale vaut exactement 1. Les trois filtres
    (bilineaire, bicubique, Lanczos) echouaient pareil, donc ce n'etait pas le filtre.
    La grid aurait alors mesure mon reechantillonnage et conclu, faux, que l'outil casse a
    300 dpi. Le blank, lui, est un render propre et synthetique: le reechantillonner ne coute
    rien.

    Les coordonnees ENREGISTREES restent canoniques: seuls les pixels lus sont natifs.
    """
    scan: object            # scan redresse, resolution native
    blank: object          # blank amene dans le meme frame, meme shape
    scale: float          # scan -> canonique
    dx: int
    dy: int

    def zone(self, z):
        """Une zone canonique traduite en coordonnees du scan."""
        from .geometry import Zone
        return Zone(z.name, z.page,
                    int(round((z.x0 - self.dx) / self.scale)),
                    int(round((z.y0 - self.dy) / self.scale)),
                    int(round((z.x1 - self.dx) / self.scale)),
                    int(round((z.y1 - self.dy) / self.scale)), z.genre)

    def to_canonical(self, x, y):
        return self.dx + x * self.scale, self.dy + y * self.scale


def build_frame(gris, blank, rec):
    """Le blank redessine dans le frame du scan. Ce qui manque reste blanc."""
    tourne = np.rot90(gris, -rec.quarter_turns) if rec.quarter_turns else gris
    h, w = tourne.shape
    mis = _resize(blank, 1.0 / rec.scale)
    oy, ox = int(round(-rec.dy / rec.scale)), int(round(-rec.dx / rec.scale))
    toile = np.full((h, w), 255, np.uint8)
    ys, xs = max(0, oy), max(0, ox)
    ye, xe = min(h, oy + mis.shape[0]), min(w, ox + mis.shape[1])
    if ye > ys and xe > xs:
        toile[ys:ye, xs:xe] = mis[ys - oy:ye - oy, xs - ox:xe - ox]
    return Frame(tourne, toile, rec.scale, rec.dx, rec.dy)


@dataclass(frozen=True)
class Preparation:
    """Tout ce qu'on sait d'un scan une fois le blank amene sur lui."""
    frame: object
    angle: float               # angle de deskew applique
    quarter_turns: int                 # quarts de tour qu'il a fallu remettre, 0 si la page etait droite
    scale: float
    source_dpi: float          # dpi de numerisation estime, sans metadonnee
    peak: float
    coverage: float          # 1.0 si la page est entiere
    orientation_margin: float   # peak du quarter_turns retenu moins peak du quarter_turns 0 d'origine


def prepare(gris, blank):
    """Chaine complete, du scan raw au repere canonique.

    L'axe sort du deskew, le demi-tour sort du recalage: une fois la page debout, seuls
    les quarts 0 et 2 restent a departager, et ils ont exactement le meme profil de
    projection. La marge d'orientation compare le quarter_turns retenu au quarter_turns 0 D'ORIGINE: c'est
    elle qui donne au check "page tournee" un score continu, donc une curve, au lieu d'un
    booleen sans seuil a read_piece.
    """
    axe, angle, droit = deskew(gris)
    rec = register(droit, blank, quarts=(0, 2))
    quarter_turns = (axe + rec.quarter_turns) % 4
    if quarter_turns == 0:
        pic0 = rec.peak
    elif axe == 0:
        pic0 = dict(rec.pics).get(0, 0.0)
    else:
        _, _, droit0 = deskew(gris, axes=(0,))
        pic0 = register(droit0, blank, quarts=(0,)).peak
    return Preparation(build_frame(droit, blank, rec), angle, quarter_turns, float(rec.scale),
                       rec.source_dpi, rec.peak, rec.coverage, float(rec.peak - pic0))
