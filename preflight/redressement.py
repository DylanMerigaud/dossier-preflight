"""Ramener un scan dans le repere du vierge, AVANT que la moindre coordonnee soit lue.

Le spike a paye cette lecon: l'encre lue dans les zones d'un scan tourne de 0,45 deg a
annonce 8 cases cochees sur 8 alors que rien n'etait coche. Un controle par coordonnees sur
une page non redressee ne mesure pas ce qu'il croit mesurer.

Deux etages:

  redresser  axe puis angle fin, par maximisation de la variance du profil de projection
             horizontal, grossier puis fin. Trois pieges mesures le 2026-08-21 sur les
             cellules dures:
               - reduire d'un FACTEUR fixe (/8) donne 102 px de large a 96 dpi et l'angle
                 devient introuvable. On normalise a une LARGEUR cible.
               - le seuil d'encre fixe a 160 rate les petits angles sur image reduite, parce
                 que le reechantillonnage eclaircit les traits. Otsu par image le corrige.
               - sur une page couchee a 90 deg le profil horizontal n'a plus de structure de
                 lignes: l'angle fin part chercher dans le vide et rend -0,15 au lieu de
                 -0,50. L'AXE se decide donc AVANT l'angle, par le meme critere.
             Cout 19 fois moindre que la recherche naive pleine page, meme angle trouve.

  recaler    orientation en quarts de tour, echelle et translation, par correlation croisee
             contre le VIERGE. C'est ce qui rend le repere canonique independant du dpi de
             numerisation, et c'est aussi ce qui donne le dpi source estime et la couverture
             de page sans lire la moindre metadonnee (un vrai scan ne les a pas).
"""
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from . import CANON_DPI

PLAGE_ANGLE = 6.0          # la grille injecte jusqu'a 4 deg
LARGEUR_GROSSIER = 400
LARGEUR_FIN = 850
PAS_GROSSIER = 0.2
PAS_FIN = 0.05


def otsu(gris):
    """Seuil d'encre propre a l'image. Un seuil fixe ne survit pas au changement de dpi."""
    h = np.histogram(gris, bins=256, range=(0, 256))[0].astype(np.float64)
    tot = h.sum()
    w0 = np.cumsum(h)
    w1 = tot - w0
    m = np.cumsum(h * np.arange(256))
    with np.errstate(invalid="ignore", divide="ignore"):
        inter = (m[-1] * w0 / tot - m) ** 2 / (w0 * w1)
    return int(np.nanargmax(inter))


def encre(gris, seuil=None):
    return gris < (otsu(gris) if seuil is None else seuil)


def _largeur(gris, cible):
    h, w = gris.shape
    if w <= cible:
        return gris
    f = cible / float(w)
    return np.asarray(Image.fromarray(gris).resize((int(w * f), int(h * f)), Image.BILINEAR))


def _variance_profil(gris, seuil, angle):
    if angle:
        gris = np.asarray(Image.fromarray(gris).rotate(angle, resample=Image.BILINEAR,
                                                       fillcolor=255))
    return float(np.var((gris < seuil).sum(axis=1)))


def redresser(gris, plage=PLAGE_ANGLE, axes=(0, 1)):
    """Retour: (quart d'axe, angle applique, image droite et debout).

    Le quart d'axe vaut 0 ou 1: il dit s'il a fallu coucher la page pour retrouver des lignes
    de texte horizontales. Le demi-tour (0 contre 180) n'est pas decidable ici, les deux ont
    exactement le meme profil de projection: c'est le recalage contre le vierge qui tranche.
    """
    meilleur = None
    for axe in axes:
        tourne = np.rot90(gris, -axe) if axe else gris
        petit = _largeur(tourne, LARGEUR_GROSSIER)
        s = otsu(petit)
        ang = max(np.arange(-plage, plage + 1e-9, PAS_GROSSIER),
                  key=lambda a: _variance_profil(petit, s, a))
        v = _variance_profil(petit, s, ang)
        if meilleur is None or v > meilleur[0]:
            meilleur = (v, axe, ang, tourne)
    _, axe, grossier, tourne = meilleur
    moyen = _largeur(tourne, LARGEUR_FIN)
    sm = otsu(moyen)
    fin = max(np.arange(grossier - PAS_GROSSIER, grossier + PAS_GROSSIER + 1e-9, PAS_FIN),
              key=lambda a: _variance_profil(moyen, sm, a))
    if abs(fin) < 1e-9:
        return axe, 0.0, tourne
    return axe, float(fin), np.asarray(Image.fromarray(tourne).rotate(
        fin, resample=Image.BICUBIC, fillcolor=255))


@dataclass(frozen=True)
class Recalage:
    quart: int             # quarts de tour a appliquer au scan pour le remettre droit
    echelle: float         # facteur applique au scan pour atteindre le repere canonique
    dx: int
    dy: int
    pic: float             # pic de correlation croisee normalise, 0 a 1
    couverture: float      # fraction de l'encre du vierge que le cadre du scan recouvre
    dpi_source: float      # CANON_DPI / echelle, estime sans lire aucune metadonnee
    pics: tuple = ()       # meilleur pic par quart evalue, pour la marge d'orientation


def _correlation(a, b):
    """Pic de correlation croisee normalisee entre deux cartes d'encre, et son decalage."""
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


def _redim(gris, echelle):
    h, w = gris.shape
    return np.asarray(Image.fromarray(gris).resize(
        (max(1, int(round(w * echelle))), max(1, int(round(h * echelle)))), Image.BILINEAR))


def recaler(gris, vierge, ratios=(0.78, 0.84, 0.90, 0.96, 1.0, 1.04), travail=480,
            quarts=(0, 1, 2, 3), affinages=((0.06, 7, 720), (0.012, 7, 720))):
    """Orientation, echelle et translation qui collent le scan sur le vierge.

    Tout se joue sur des cartes d'encre reduites a `travail` pixels de large: la correlation
    y coute quelques millisecondes. L'echelle de base vient du rapport des hauteurs, et les
    ratios balaient autour, vers le bas surtout, parce qu'une page ROGNEE fait croire a une
    echelle trop grande: rogner 18% de la hauteur fait surestimer l'echelle de 22%.

    Le balayage grossier seul ne suffit pas. Son pas de 6% laisse 2,4% d'erreur d'echelle,
    soit 53 px de derive en bas d'une page de 2200 px: assez pour que les zones declarees
    tombent une ligne trop bas et que le disque d'une case rate la case. Mesure le
    2026-08-21: sans affinage, la page rognee declenchait a tort le controle des cases
    obligatoires (delta d'encre +6,7 au lieu de +21,1) et celui des champs requis. Deux
    passes d'affinage ramenent l'erreur d'echelle sous 0,2%.
    """
    H, W = vierge.shape
    meilleur = None
    par_quart = {}

    def essayer(ref, f, tourne, quart, ech):
        dy, dx, pic = _correlation(ref, encre(_redim(tourne, ech * f)).astype(np.float32))
        par_quart[quart] = max(par_quart.get(quart, 0.0), pic)
        return (pic, quart, ech, dx / f, dy / f, tourne)

    f = travail / float(W)
    ref = encre(_redim(vierge, f)).astype(np.float32)
    for quart in quarts:
        tourne = np.rot90(gris, -quart) if quart else gris
        base = H / float(tourne.shape[0])
        for r in ratios:
            c = essayer(ref, f, tourne, quart, base * r)
            if meilleur is None or c[0] > meilleur[0]:
                meilleur = c
    for demi, n, larg in affinages:
        _, quart, ech, _, _, tourne = meilleur
        f = larg / float(W)
        ref = encre(_redim(vierge, f)).astype(np.float32)
        for r in np.linspace(1 - demi, 1 + demi, n):
            c = essayer(ref, f, tourne, quart, ech * r)
            if c[0] > meilleur[0]:
                meilleur = c
    pic, quart, ech, dx, dy, tourne = meilleur
    par_quart = tuple(sorted(par_quart.items()))
    h, w = tourne.shape
    y0, x0 = max(0, int(round(dy))), max(0, int(round(dx)))
    y1, x1 = min(H, int(round(dy + h * ech))), min(W, int(round(dx + w * ech)))
    enc_ref = encre(vierge)
    dedans = int(enc_ref[y0:y1, x0:x1].sum()) if (y1 > y0 and x1 > x0) else 0
    return Recalage(quart, float(ech), int(round(dx)), int(round(dy)), pic,
                    dedans / max(1, int(enc_ref.sum())), CANON_DPI / float(ech), par_quart)


@dataclass(frozen=True)
class Cadre:
    """Le scan a SA resolution, et le vierge amene jusqu'a lui.

    C'EST L'INVERSE DE CE QU'ON FAIT D'INSTINCT, et le renversement est une mesure, pas un
    gout. Ramener le scan dans un repere canonique a 200 dpi oblige a le reechantillonner des
    que sa resolution differe, et ce reechantillonnage detruit le petit texte encadre: sur le
    Cerfa 14011, un scan a 300 dpi rendait 0 caractere lisible dans trois champs qui en
    rendaient 14, 5 et 10 a 200 dpi, ou l'echelle vaut exactement 1. Les trois filtres
    (bilineaire, bicubique, Lanczos) echouaient pareil, donc ce n'etait pas le filtre.
    La grille aurait alors mesure mon reechantillonnage et conclu, faux, que l'outil casse a
    300 dpi. Le vierge, lui, est un rendu propre et synthetique: le reechantillonner ne coute
    rien.

    Les coordonnees ENREGISTREES restent canoniques: seuls les pixels lus sont natifs.
    """
    scan: object            # scan redresse, resolution native
    vierge: object          # vierge amene dans le meme cadre, meme forme
    echelle: float          # scan -> canonique
    dx: int
    dy: int

    def zone(self, z):
        """Une zone canonique traduite en coordonnees du scan."""
        from .geometrie import Zone
        return Zone(z.nom, z.page,
                    int(round((z.x0 - self.dx) / self.echelle)),
                    int(round((z.y0 - self.dy) / self.echelle)),
                    int(round((z.x1 - self.dx) / self.echelle)),
                    int(round((z.y1 - self.dy) / self.echelle)), z.genre)

    def vers_canonique(self, x, y):
        return self.dx + x * self.echelle, self.dy + y * self.echelle


def cadrer(gris, vierge, rec):
    """Le vierge redessine dans le cadre du scan. Ce qui manque reste blanc."""
    tourne = np.rot90(gris, -rec.quart) if rec.quart else gris
    h, w = tourne.shape
    mis = _redim(vierge, 1.0 / rec.echelle)
    oy, ox = int(round(-rec.dy / rec.echelle)), int(round(-rec.dx / rec.echelle))
    toile = np.full((h, w), 255, np.uint8)
    ys, xs = max(0, oy), max(0, ox)
    ye, xe = min(h, oy + mis.shape[0]), min(w, ox + mis.shape[1])
    if ye > ys and xe > xs:
        toile[ys:ye, xs:xe] = mis[ys - oy:ye - oy, xs - ox:xe - ox]
    return Cadre(tourne, toile, rec.echelle, rec.dx, rec.dy)


@dataclass(frozen=True)
class Preparation:
    """Tout ce qu'on sait d'un scan une fois le vierge amene sur lui."""
    cadre: object
    angle: float               # angle de redressement applique
    quart: int                 # quarts de tour qu'il a fallu remettre, 0 si la page etait droite
    echelle: float
    dpi_source: float          # dpi de numerisation estime, sans metadonnee
    pic: float
    couverture: float          # 1.0 si la page est entiere
    marge_orientation: float   # pic du quart retenu moins pic du quart 0 d'origine


def preparer(gris, vierge):
    """Chaine complete, du scan brut au repere canonique.

    L'axe sort du redressement, le demi-tour sort du recalage: une fois la page debout, seuls
    les quarts 0 et 2 restent a departager, et ils ont exactement le meme profil de
    projection. La marge d'orientation compare le quart retenu au quart 0 D'ORIGINE: c'est
    elle qui donne au controle "page tournee" un score continu, donc une courbe, au lieu d'un
    booleen sans seuil a lire.
    """
    axe, angle, droit = redresser(gris)
    rec = recaler(droit, vierge, quarts=(0, 2))
    quart = (axe + rec.quart) % 4
    if quart == 0:
        pic0 = rec.pic
    elif axe == 0:
        pic0 = dict(rec.pics).get(0, 0.0)
    else:
        _, _, droit0 = redresser(gris, axes=(0,))
        pic0 = recaler(droit0, vierge, quarts=(0,)).pic
    return Preparation(cadrer(droit, vierge, rec), angle, quart, float(rec.echelle),
                       rec.dpi_source, rec.pic, rec.couverture, float(rec.pic - pic0))
