"""Ce qu'un guichet recoit vraiment: une page tournee, bruitee, floue, recompressee.

L'ordre compte et il imite la chaine physique: la feuille est posee de travers (rotation),
le capteur ajoute son bruit, l'optique floute, le pilote compresse en JPEG.
"""
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image, ImageFilter

from . import CANON_DPI


@dataclass(frozen=True)
class Degradation:
    """Une cellule de la grille. dpi est le dpi de NUMERISATION, pas le repere canonique."""
    angle: float = 0.0
    dpi: int = CANON_DPI
    jpeg: int = 95
    sigma: float = 0.0
    flou: float = 0.4
    graine: int = 0
    quart: int = 0          # rotation grossiere en quarts de tour: 0, 1, 2, 3
    rogne: float = 0.0      # fraction de la hauteur coupee en bas, page tronquee

    def cle(self):
        return (f"a{self.angle}_d{self.dpi}_q{self.jpeg}_s{self.sigma}"
                f"_f{self.flou}_g{self.graine}_t{self.quart}_r{self.rogne}")

    def dict(self):
        return asdict(self)


def appliquer(gris, deg):
    """Applique la degradation a une page DEJA rendue au dpi voulu. Retour: uint8 (H, W)."""
    im = Image.fromarray(gris)
    if deg.quart:
        im = im.rotate(-90 * deg.quart, expand=True, fillcolor=255)
    if deg.rogne:
        h = im.size[1]
        im = im.crop((0, 0, im.size[0], max(1, int(h * (1.0 - deg.rogne)))))
    if deg.angle:
        im = im.rotate(deg.angle, resample=Image.BICUBIC, fillcolor=255)
    a = np.asarray(im).astype(np.int16)
    if deg.sigma:
        a = a + np.random.default_rng(deg.graine).normal(0, deg.sigma, a.shape).astype(np.int16)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if deg.flou:
        im = im.filter(ImageFilter.GaussianBlur(deg.flou))
    if deg.jpeg < 100:
        import io
        tampon = io.BytesIO()
        im.save(tampon, format="JPEG", quality=deg.jpeg)
        tampon.seek(0)
        im = Image.open(tampon).convert("L")
    return np.asarray(im)
