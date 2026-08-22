"""FOREIGN ink inside a zone: the ground the grid never put its sensors through.

The grid crosses angle, resolution, compression and noise. None of those four degradations ADDS
ink inside a zone: they move, blur or dirty the ink already there. Yet the sensor retained for
"is this required field empty" is precisely an ink sensor, which does not know what is written,
only that something is darker than before. It therefore won its duel on ground that favours it,
and that is what this module measures: how much foreign ink it takes for an EMPTY field to pass
for filled.

The direction of the error matters: an empty field declared filled is a FALSE NEGATIVE, the
counter rejects the dossier and nobody was warned. That is the expensive side of the asymmetry.

Three shapes, all physical, all laid down BEFORE degradation so they go through the same
rotation, noise and compression as the rest of the page:
  speck   a localised ink deposit, whose area is swept
  fold    the shadow of a crease, a dark band across the page
  stroke  a pen stroke starting in the neighbouring field and spilling over
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CANON_DPI = 200


def _zone_scan(zone, dpi):
    """A canonical zone brought back to the pixels of the clean render, before degradation."""
    e = dpi / CANON_DPI
    return (int(zone.x0 * e), int(zone.y0 * e), int(zone.x1 * e), int(zone.y1 * e))


def speck(grey, zone, dpi, fraction, rng, darkness=45):
    """An ink deposit covering `fraction` of the zone's area."""
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    area = max(1.0, (x1 - x0) * (y1 - y0) * fraction)
    ry = np.sqrt(area / (np.pi * 1.6))
    rx = ry * 1.6
    cx = rng.uniform(x0 + rx * 0.5, x1 - rx * 0.5) if x1 - x0 > 2 * rx else (x0 + x1) / 2
    cy = (y0 + y1) / 2 + rng.uniform(-0.15, 0.15) * (y1 - y0)
    im = Image.fromarray(grey)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=int(darkness))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(max(0.6, ry * 0.12))))


def fold(grey, zone, dpi, fraction, rng):
    """The shadow of a crease: a dark band across the whole page, gaussian profile.

    Here the sweep is over DARKNESS, not area: a shadow always covers the full width of the
    page, and what varies with the depth of the fold and the scanner's exposure is how dark it
    is. And there is a cliff: as long as the shadow leaves the paper above the sensor's
    binarisation threshold (128) it is perfectly invisible; as soon as it passes below, the
    whole band flips at once.
    """
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    h = grey.shape[0]
    strength = min(0.75, 0.15 + 10.0 * fraction)
    centre = (y0 + y1) / 2 + rng.uniform(-0.3, 0.3) * (y1 - y0)
    width = max(3.0, (y1 - y0) * 1.4)
    ys = np.arange(h, dtype=np.float32)
    profile = np.exp(-0.5 * ((ys - centre) / width) ** 2) * strength
    a = grey.astype(np.float32) * (1.0 - profile[:, None])
    return np.clip(a, 0, 255).astype(np.uint8)


def stroke(grey, zone, dpi, fraction, rng, darkness=40):
    """A pen stroke starting next door and spilling into the zone."""
    x0, y0, x1, y1 = _zone_scan(zone, dpi)
    height = y1 - y0
    thickness = max(1.5, height * (0.06 + 1.2 * fraction))
    penetration = min(1.0, 0.25 + 6.0 * fraction)
    xa = x0 - (x1 - x0) * 0.15
    xb = x0 + (x1 - x0) * penetration
    ya = y0 + rng.uniform(0.2, 0.8) * height
    yb = ya + rng.uniform(-0.3, 0.3) * height
    im = Image.fromarray(grey)
    ImageDraw.Draw(im).line([xa, ya, xb, yb], fill=int(darkness), width=int(round(thickness)))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(0.6)))


SHAPES = {"speck": speck, "fold": fold, "stroke": stroke}
