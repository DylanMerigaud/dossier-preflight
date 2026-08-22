"""Encre ETRANGERE dans une zone: le terrain que la grille n'a jamais fait subir a ses capteurs.

La grille croise angle, resolution, compression et bruit. Aucune de ces quatre degradations
n'AJOUTE d'encre dans une zone: elles deplacent, floutent ou salissent celle qui y est deja.
Or le capteur retenu pour "ce champ requis est-il vide" est justement un capteur d'encre, qui
ne sait pas ce qui est ecrit mais seulement qu'il y a quelque chose de plus sombre qu'avant.
Il a donc gagne son duel sur un terrain qui lui est favorable, et c'est ce que ce module
mesure: de combien d'encre etrangere a-t-on besoin pour qu'un champ VIDE passe pour rempli.

Le sens de l'erreur compte: un champ vide declare rempli est un FAUX NEGATIF, le guichet
refuse le dossier et personne n'a ete prevenu. C'est le cote cher de l'asymetrie.

Trois formes, toutes physiques, toutes posees AVANT la degradation pour qu'elles subissent la
meme rotation, le meme bruit et la meme compression que le reste de la page:
  tache    un depot d'encre localise, dont on balaie la surface
  pliure   l'ombre d'un pli, bande sombre en travers de la page
  trait    un trait de stylo parti du champ voisin et qui deborde
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CANON_DPI = 200


def _zone_scan(zone, dpi):
    """Une zone canonique ramenee aux pixels du rendu propre, avant degradation."""
    e = dpi / CANON_DPI
    return (int(zone.x0 * e), int(zone.y0 * e), int(zone.x1 * e), int(zone.y1 * e))


def tache(gris, zone, dpi, fraction, rng, noirceur=45):
    """Un depot d'encre couvrant `fraction` de la surface de la zone."""
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    aire = max(1.0, (x1 - x0) * (y1 - y0) * fraction)
    ry = np.sqrt(aire / (np.pi * 1.6))
    rx = ry * 1.6
    cx = rng.uniform(x0 + rx * 0.5, x1 - rx * 0.5) if x1 - x0 > 2 * rx else (x0 + x1) / 2
    cy = (y0 + y1) / 2 + rng.uniform(-0.15, 0.15) * (y1 - y0)
    im = Image.fromarray(gris)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=int(noirceur))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(max(0.6, ry * 0.12))))


def pliure(gris, zone, dpi, fraction, rng):
    """L'ombre d'un pli: bande sombre en travers de toute la page, profil gaussien.

    Ici le balayage porte sur la NOIRCEUR, pas sur la surface: une ombre couvre toujours toute
    la largeur de la page, ce qui varie avec la profondeur du pli et l'exposition du scanner
    c'est a quel point elle est sombre. Et il y a une falaise: tant que l'ombre laisse le
    papier au-dessus du seuil de binarisation du capteur (128), elle est parfaitement
    invisible; des qu'elle passe dessous, toute la bande bascule d'un coup.
    """
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    h = gris.shape[0]
    force = min(0.75, 0.15 + 10.0 * fraction)
    centre = (y0 + y1) / 2 + rng.uniform(-0.3, 0.3) * (y1 - y0)
    largeur = max(3.0, (y1 - y0) * 1.4)
    ys = np.arange(h, dtype=np.float32)
    profil = np.exp(-0.5 * ((ys - centre) / largeur) ** 2) * force
    a = gris.astype(np.float32) * (1.0 - profil[:, None])
    return np.clip(a, 0, 255).astype(np.uint8)


def trait(gris, zone, dpi, fraction, rng, noirceur=40):
    """Un trait de stylo parti d'a cote et qui deborde dans la zone."""
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    hauteur = y1 - y0
    ep = max(1.5, hauteur * (0.06 + 1.2 * fraction))
    penetration = min(1.0, 0.25 + 6.0 * fraction)
    xa = x0 - (x1 - x0) * 0.15
    xb = x0 + (x1 - x0) * penetration
    ya = y0 + rng.uniform(0.2, 0.8) * hauteur
    yb = ya + rng.uniform(-0.3, 0.3) * hauteur
    im = Image.fromarray(gris)
    ImageDraw.Draw(im).line([xa, ya, xb, yb], fill=int(noirceur), width=int(round(ep)))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(0.6)))


FORMES = {"tache": tache, "pliure": pliure, "trait": trait}
