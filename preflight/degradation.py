"""Ce qu'un filing recoit vraiment: une page tournee, bruitee, floue, recompressee.

L'ordre compte et il imite la chaine physique: la feuille est posee de travers (rotation),
le capteur ajoute son bruit, l'optique floute, le pilote compresse en JPEG.
"""
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image, ImageFilter

from . import CANON_DPI


@dataclass(frozen=True)
class Degradation:
    """Une cell de la grid. dpi est le dpi de NUMERISATION, pas le repere canonique."""
    angle: float = 0.0
    dpi: int = CANON_DPI
    jpeg: int = 95
    sigma: float = 0.0
    blur: float = 0.4
    seed: int = 0
    quarter_turns: int = 0          # rotation grossiere en quarts de tour: 0, 1, 2, 3
    crop: float = 0.0      # fraction de la hauteur coupee en bas, page tronquee

    def key(self):
        return (f"a{self.angle}_d{self.dpi}_q{self.jpeg}_s{self.sigma}"
                f"_f{self.blur}_g{self.seed}_t{self.quarter_turns}_r{self.crop}")

    def dict(self):
        return asdict(self)


def apply(gris, deg):
    """Applique la degradation a une page DEJA rendue au dpi voulu. Retour: uint8 (H, W)."""
    im = Image.fromarray(gris)
    if deg.quarter_turns:
        im = im.rotate(-90 * deg.quarter_turns, expand=True, fillcolor=255)
    if deg.crop:
        h = im.size[1]
        im = im.crop((0, 0, im.size[0], max(1, int(h * (1.0 - deg.crop)))))
    if deg.angle:
        im = im.rotate(deg.angle, resample=Image.BICUBIC, fillcolor=255)
    a = np.asarray(im).astype(np.int16)
    if deg.sigma:
        a = a + np.random.default_rng(deg.seed).normal(0, deg.sigma, a.shape).astype(np.int16)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if deg.blur:
        im = im.filter(ImageFilter.GaussianBlur(deg.blur))
    if deg.jpeg < 100:
        import io
        tampon = io.BytesIO()
        im.save(tampon, format="JPEG", quality=deg.jpeg)
        tampon.seek(0)
        im = Image.open(tampon).convert("L")
    return np.asarray(im)
