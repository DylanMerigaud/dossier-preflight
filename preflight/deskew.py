"""Bring a scan into the blank's frame, BEFORE a single coordinate is read.

The spike paid for this lesson: ink measured inside the zones of a scan rotated by 0.45 deg
reported 8 ticked boxes out of 8 when nothing was ticked. A coordinate-based check on a page
that has not been deskewed does not measure what it thinks it measures.

Two stages:

  deskew    axis first, then fine angle, by maximising the variance of the horizontal
            projection profile, coarse then fine. Three traps measured 2026-08-21 on the hard
            cells:
              - downscaling by a fixed FACTOR (/8) gives 102 px of width at 96 dpi and the
                angle becomes impossible to find. Normalise to a TARGET WIDTH instead.
              - a fixed ink threshold of 160 misses small angles on a downscaled image,
                because resampling lightens the strokes. Per-image Otsu fixes it.
              - on a page lying at 90 deg the horizontal profile no longer has line structure:
                the fine angle search wanders and returns -0.15 instead of -0.50. The AXIS is
                therefore decided BEFORE the angle, by the same criterion.
            19 times cheaper than the naive full-page search, and it finds the same angle.

  register  orientation in quarter turns, scale and translation, by cross-correlation against
            the BLANK. This is what makes the canonical frame independent of the scanning dpi,
            and it is also what yields the estimated source dpi and the page coverage without
            reading a single piece of metadata (a real scan has none).
"""
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from . import CANON_DPI

ANGLE_RANGE = 6.0          # the grid injects up to 4 deg
COARSE_WIDTH = 400
FINE_WIDTH = 850
COARSE_STEP = 0.2
FINE_STEP = 0.05


def otsu(grey):
    """An ink threshold specific to the image. A fixed threshold does not survive a dpi change."""
    h = np.histogram(grey, bins=256, range=(0, 256))[0].astype(np.float64)
    total = h.sum()
    w0 = np.cumsum(h)
    w1 = total - w0
    m = np.cumsum(h * np.arange(256))
    with np.errstate(invalid="ignore", divide="ignore"):
        between = (m[-1] * w0 / total - m) ** 2 / (w0 * w1)
    return int(np.nanargmax(between))


def ink(grey, threshold=None):
    return grey < (otsu(grey) if threshold is None else threshold)


def _width(grey, target):
    h, w = grey.shape
    if w <= target:
        return grey
    f = target / float(w)
    return np.asarray(Image.fromarray(grey).resize((int(w * f), int(h * f)), Image.BILINEAR))


def _profile_variance(grey, threshold, angle):
    if angle:
        grey = np.asarray(Image.fromarray(grey).rotate(angle, resample=Image.BILINEAR,
                                                       fillcolor=255))
    return float(np.var((grey < threshold).sum(axis=1)))


def deskew(grey, span=ANGLE_RANGE, axes=(0, 1)):
    """Returns (axis quarter turn, applied angle, upright straightened image).

    The axis quarter turn is 0 or 1: it says whether the page had to be laid down to recover
    horizontal text lines. The half turn (0 against 180) is not decidable here, both have
    exactly the same projection profile: registration against the blank settles that.
    """
    best = None
    for axis in axes:
        turned = np.rot90(grey, -axis) if axis else grey
        small = _width(turned, COARSE_WIDTH)
        s = otsu(small)
        ang = max(np.arange(-span, span + 1e-9, COARSE_STEP),
                  key=lambda a: _profile_variance(small, s, a))
        v = _profile_variance(small, s, ang)
        if best is None or v > best[0]:
            best = (v, axis, ang, turned)
    _, axis, coarse, turned = best
    medium = _width(turned, FINE_WIDTH)
    sm = otsu(medium)
    fine = max(np.arange(coarse - COARSE_STEP, coarse + COARSE_STEP + 1e-9, FINE_STEP),
               key=lambda a: _profile_variance(medium, sm, a))
    if abs(fine) < 1e-9:
        return axis, 0.0, turned
    return axis, float(fine), np.asarray(Image.fromarray(turned).rotate(
        fine, resample=Image.BICUBIC, fillcolor=255))


@dataclass(frozen=True)
class Registration:
    quarter_turns: int      # quarter turns to apply to the scan to set it upright
    scale: float            # factor applied to the scan to reach the canonical frame
    dx: int
    dy: int
    peak: float             # normalised cross-correlation peak, 0 to 1
    coverage: float         # fraction of the blank's ink that the scan's frame covers
    source_dpi: float       # CANON_DPI / scale, estimated without reading any metadata
    peaks: tuple = ()       # best peak per quarter turn tried, for the orientation margin


def _correlation(a, b):
    """Normalised cross-correlation peak between two ink maps, and its offset."""
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


def _resize(grey, scale):
    h, w = grey.shape
    return np.asarray(Image.fromarray(grey).resize(
        (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.BILINEAR))


def register(grey, blank, ratios=(0.78, 0.84, 0.90, 0.96, 1.0, 1.04), width=480,
             quarters=(0, 1, 2, 3), refinements=((0.06, 7, 720), (0.012, 7, 720))):
    """Orientation, scale and translation that stick the scan onto the blank.

    Everything happens on ink maps downscaled to `width` pixels: correlation there costs a few
    milliseconds. The base scale comes from the ratio of heights, and the ratios sweep around
    it, mostly downwards, because a CROPPED page makes the scale look too large: cropping 18%
    of the height overestimates the scale by 22%.

    The coarse sweep alone is not enough. Its 6% step leaves 2.4% of scale error, which is 53
    px of drift at the bottom of a 2200 px page: enough for the declared zones to land one line
    too low and for a checkbox disc to miss its box. Measured 2026-08-21: without refinement the
    cropped page wrongly fired the required-checkbox check (ink delta +6.7 instead of +21.1) and
    the required-field one. Two refinement passes bring the scale error under 0.2%.
    """
    H, W = blank.shape
    best = None
    per_quarter = {}

    def attempt(ref, f, turned, quarter_turns, scale):
        dy, dx, peak = _correlation(ref, ink(_resize(turned, scale * f)).astype(np.float32))
        per_quarter[quarter_turns] = max(per_quarter.get(quarter_turns, 0.0), peak)
        return (peak, quarter_turns, scale, dx / f, dy / f, turned)

    f = width / float(W)
    ref = ink(_resize(blank, f)).astype(np.float32)
    for quarter_turns in quarters:
        turned = np.rot90(grey, -quarter_turns) if quarter_turns else grey
        base = H / float(turned.shape[0])
        for r in ratios:
            c = attempt(ref, f, turned, quarter_turns, base * r)
            if best is None or c[0] > best[0]:
                best = c
    for half, n, w in refinements:
        _, quarter_turns, scale, _, _, turned = best
        f = w / float(W)
        ref = ink(_resize(blank, f)).astype(np.float32)
        for r in np.linspace(1 - half, 1 + half, n):
            c = attempt(ref, f, turned, quarter_turns, scale * r)
            if c[0] > best[0]:
                best = c
    peak, quarter_turns, scale, dx, dy, turned = best
    peaks = tuple(sorted(per_quarter.items()))
    h, w = turned.shape
    y0, x0 = max(0, int(round(dy))), max(0, int(round(dx)))
    y1, x1 = min(H, int(round(dy + h * scale))), min(W, int(round(dx + w * scale)))
    blank_ink = ink(blank)
    inside = int(blank_ink[y0:y1, x0:x1].sum()) if (y1 > y0 and x1 > x0) else 0
    return Registration(quarter_turns, float(scale), int(round(dx)), int(round(dy)), peak,
                        inside / max(1, int(blank_ink.sum())), CANON_DPI / float(scale), peaks)


@dataclass(frozen=True)
class Frame:
    """The scan at ITS resolution, and the blank brought to it.

    THIS IS THE OPPOSITE OF THE INSTINCTIVE CHOICE, and the reversal is a measurement, not a
    preference. Bringing the scan into a canonical 200 dpi frame forces a resample whenever its
    resolution differs, and that resampling destroys small boxed text: on Cerfa 14011, a scan at
    300 dpi returned 0 readable characters in three fields that returned 14, 5 and 10 at 200
    dpi, where the scale is exactly 1. All three filters (bilinear, bicubic, Lanczos) failed the
    same way, so it was not the filter. The grid would then have measured my own resampling and
    concluded, wrongly, that the tool breaks at 300 dpi. The blank, by contrast, is a clean
    synthetic render: resampling it costs nothing.

    The RECORDED coordinates stay canonical: only the pixels read are native.
    """
    scan: object            # deskewed scan, native resolution
    blank: object           # blank brought into the same frame, same shape
    scale: float            # scan -> canonical
    dx: int
    dy: int

    def zone(self, z):
        """A canonical zone translated into scan coordinates."""
        from .geometry import Zone
        return Zone(z.name, z.page,
                    int(round((z.x0 - self.dx) / self.scale)),
                    int(round((z.y0 - self.dy) / self.scale)),
                    int(round((z.x1 - self.dx) / self.scale)),
                    int(round((z.y1 - self.dy) / self.scale)), z.kind)

    def to_canonical(self, x, y):
        return self.dx + x * self.scale, self.dy + y * self.scale


def build_frame(grey, blank, reg):
    """The blank redrawn inside the scan's frame. What is missing stays white."""
    turned = np.rot90(grey, -reg.quarter_turns) if reg.quarter_turns else grey
    h, w = turned.shape
    scaled = _resize(blank, 1.0 / reg.scale)
    oy, ox = int(round(-reg.dy / reg.scale)), int(round(-reg.dx / reg.scale))
    canvas = np.full((h, w), 255, np.uint8)
    ys, xs = max(0, oy), max(0, ox)
    ye, xe = min(h, oy + scaled.shape[0]), min(w, ox + scaled.shape[1])
    if ye > ys and xe > xs:
        canvas[ys:ye, xs:xe] = scaled[ys - oy:ye - oy, xs - ox:xe - ox]
    return Frame(turned, canvas, reg.scale, reg.dx, reg.dy)


@dataclass(frozen=True)
class Preparation:
    """Everything known about a scan once the blank has been brought onto it."""
    frame: object
    angle: float                # deskew angle applied
    quarter_turns: int          # quarter turns that had to be undone, 0 if the page was upright
    scale: float
    source_dpi: float           # estimated scanning dpi, without metadata
    peak: float
    coverage: float             # 1.0 if the whole page is there
    orientation_margin: float   # peak of the chosen quarter turn minus peak of the original 0


def prepare(grey, blank):
    """The full chain, from raw scan to canonical frame.

    The axis comes out of the deskew, the half turn comes out of the registration: once the
    page is upright only quarters 0 and 2 remain to be told apart, and they have exactly the
    same projection profile. The orientation margin compares the chosen quarter turn to the
    ORIGINAL quarter 0: that is what gives the "rotated page" check a continuous score, and
    therefore a curve, instead of a boolean with no threshold to read.
    """
    axis, angle, straight = deskew(grey)
    reg = register(straight, blank, quarters=(0, 2))
    quarter_turns = (axis + reg.quarter_turns) % 4
    if quarter_turns == 0:
        peak0 = reg.peak
    elif axis == 0:
        peak0 = dict(reg.peaks).get(0, 0.0)
    else:
        _, _, straight0 = deskew(grey, axes=(0,))
        peak0 = register(straight0, blank, quarters=(0,)).peak
    return Preparation(build_frame(straight, blank, reg), angle, quarter_turns, float(reg.scale),
                       reg.source_dpi, reg.peak, reg.coverage, float(reg.peak - peak0))
