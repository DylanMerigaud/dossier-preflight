"""What a counter actually receives: a page that is skewed, noisy, blurred and recompressed.

The order matters and it mirrors the physical chain: the sheet is laid down crooked
(rotation), the sensor adds its noise, the optics blur, the driver compresses to JPEG.
"""
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image, ImageFilter

from . import CANON_DPI


@dataclass(frozen=True)
class Degradation:
    """One cell of the grid. `dpi` is the SCANNING dpi, not the canonical frame."""
    angle: float = 0.0
    dpi: int = CANON_DPI
    jpeg: int = 95
    sigma: float = 0.0
    blur: float = 0.4
    seed: int = 0
    quarter_turns: int = 0   # coarse rotation in quarter turns: 0, 1, 2, 3
    crop: float = 0.0        # fraction of the height cut off at the bottom, truncated page

    def key(self):
        return (f"a{self.angle}_d{self.dpi}_q{self.jpeg}_s{self.sigma}"
                f"_f{self.blur}_g{self.seed}_t{self.quarter_turns}_r{self.crop}")

    def dict(self):
        return asdict(self)


def apply(grey, deg):
    """Degrade a page ALREADY rendered at the wanted dpi. Returns uint8 (H, W).

    Every field is a no-op at its neutral value, so Degradation(angle=0, jpeg=100, sigma=0,
    blur=0) returns the page untouched. That is what the command line uses on real scans: the
    grid degrades, production does not.
    """
    im = Image.fromarray(grey)
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
        buffer = io.BytesIO()
        im.save(buffer, format="JPEG", quality=deg.jpeg)
        buffer.seek(0)
        im = Image.open(buffer).convert("L")
    return np.asarray(im)
