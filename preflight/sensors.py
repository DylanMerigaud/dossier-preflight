"""The raw sensors. Each returns a CONTINUOUS MEASUREMENT, never a verdict.

That is deliberate, and it is what makes the grid readable: a sensor that already returned a
boolean would have locked its threshold inside its own code, and a locked threshold cannot be
read off a curve. Here the grid records measurements and the analysis sweeps thresholds
afterwards, without recomputing a single image.

Four sensors, and the spike already settled the duel between two of them:
  ocr_words   word positions. THE text sensor. An empty field returns 0 words.
  disc_ink    ink in a disc at the centre of the box, so the box outline stays outside.
              THE checkbox sensor. On text it is fragile: an EMPTY field still read +2.44%
              against +4.5% for a filled one.
  ink_ratio   ink over the whole zone. Competes with `components` for signatures.
  components  connected components of what the scan ADDED to the blank. A signature is one
              large elongated component; noise is a cloud of crumbs.
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

INK_THRESHOLDS = (128, 160, 190)      # swept by the grid, not chosen by hand
DISC_RATIOS = (0.30, 0.42, 0.55, 0.70)


def normalize(text):
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Word:
    text: str
    cx: float
    cy: float
    conf: float

    @property
    def normalized(self):
        return normalize(self.text)


def ocr_words(grey, language="eng", psm=11, min_conf=0.0):
    """Every word read, with its confidence. Confidence filtering happens LATER.

    Later and not here, because the confidence floor is a swept parameter: the grid measured
    that a COMB field (one box per character, the form declares it) reads "4/1)2" at
    confidence 38, so a floor at 40 throws away a FILLED field. Baking a floor in here would
    have hidden that behind a sensor.
    """
    os.makedirs(CACHE, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".png", dir=CACHE)
    os.close(fd)
    try:
        Image.fromarray(grey).save(path)
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        out = subprocess.run(["tesseract", path, "stdout", "-l", language, "--psm", str(psm),
                              "tsv"], capture_output=True, text=True, env=env).stdout
    finally:
        os.unlink(path)
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


def added_words(words, preprinted, radius=22):
    """What the scan ADDED to the blank, and nothing else.

    The subtraction is done by TEXT AND POSITION, not by text alone: in the canonical frame
    the two images are superimposed, so a pre-printed word lands in the same place. Subtracting
    by text alone would delete a surname unlucky enough to coincide with a word of the form.
    """
    by_text = {}
    for m in preprinted:
        by_text.setdefault(m.normalized, []).append((m.cx, m.cy))
    added_only = []
    for m in words:
        nearby = by_text.get(m.normalized, ())
        if any((m.cx - x) ** 2 + (m.cy - y) ** 2 <= radius * radius for x, y in nearby):
            continue
        added_only.append(m)
    return added_only


def _window(grey, zone):
    y0, y1 = max(0, zone.y0), min(grey.shape[0], zone.y1)
    x0, x1 = max(0, zone.x0), min(grey.shape[1], zone.x1)
    if y1 <= y0 or x1 <= x0:
        return None, (0, 0, 0, 0)
    return grey[y0:y1, x0:x1], (y0, x0, y1, x1)


def disc_ink(grey, zone, ratio=0.42, threshold=160):
    """Ink in a disc at the CENTRE of the box, so the box outline stays outside."""
    cx, cy = (zone.x0 + zone.x1) / 2, (zone.y0 + zone.y1) / 2
    rr = min(zone.width, zone.height) * ratio
    ya, yb = max(0, int(cy - rr)), min(grey.shape[0], int(cy + rr) + 1)
    xa, xb = max(0, int(cx - rr)), min(grey.shape[1], int(cx + rr) + 1)
    if yb <= ya or xb <= xa:
        return 0.0
    Y, X = np.ogrid[ya:yb, xa:xb]
    m = ((X - cx) ** 2 + (Y - cy) ** 2) <= rr * rr
    if not m.any():
        return 0.0
    return float(((grey[ya:yb, xa:xb] < threshold) & m).sum()) / int(m.sum()) * 100


def ink_ratio(grey, zone, threshold=160):
    f, _ = _window(grey, zone)
    if f is None or f.size == 0:
        return 0.0
    return float((f < threshold).sum()) / f.size * 100


def added(grey, blank, zone, threshold=160):
    """Mask of the pixels the scan DARKENED relative to the blank, inside the zone."""
    a, frame = _window(grey, zone)
    b, _ = _window(blank, zone)
    if a is None or b is None or a.shape != b.shape:
        return None
    return (a < threshold) & ~(b < threshold)


def components(grey, blank, zone, threshold=160, min_area=8):
    """Connected components of what was added. Returns (count, max area, max diagonal).

    A handwritten signature is ONE large elongated component. Compression noise is a cloud of
    crumbs, and that is exactly what min_area removes.
    """
    m = added(grey, blank, zone, threshold)
    if m is None or not m.any():
        return 0, 0, 0.0
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if n == 0:
        return 0, 0, 0.0
    areas = np.bincount(lab.ravel())[1:]
    kept = np.nonzero(areas >= min_area)[0]
    if kept.size == 0:
        return 0, 0, 0.0
    largest = kept[int(np.argmax(areas[kept]))] + 1
    ys, xs = np.nonzero(lab == largest)
    diag = float(np.hypot(ys.max() - ys.min() + 1, xs.max() - xs.min() + 1))
    return int(kept.size), int(areas[kept].max()), diag


def words_in(words, zone, margin=8):
    z = zone.expanded(margin)
    return [m for m in words if z.contains(m.cx, m.cy)]


def ocr_zone_words(grey, zone, language="eng", psm=11, margin=6, upscale=1):
    """OCR of the ZONE ALONE, coordinates mapped back into the page frame.

    A direct competitor of full-page OCR, and the duel is not theoretical: on Cerfa 14011,
    whose fields are boxed character by character, full-page OCR at psm 11 reads "108600" for
    "03600" by swallowing the border, and sees nothing at all inside NoCarteID. The same field
    cropped and read on its own returns "AB1234567" without a mistake. In exchange it costs one
    tesseract call per field instead of one per page: it is the grid's job to say where that
    price is worth paying.

    psm 11 without upscaling, measured 2026-08-21 over the 25 fields of the dossier on a clean
    render: mean similarity to the expected value 0.911 against 0.858 for full-page OCR, 1
    failure against 2. psm 7 (single line) drops to 0.817 and psm 13 to 0.768. Upscaling the
    crop x2 before OCR degrades everything (0.765): tesseract already does its own resampling
    and ours only adds blur.
    """
    z = zone.expanded(margin)
    y0, y1 = max(0, z.y0), min(grey.shape[0], z.y1)
    x0, x1 = max(0, z.x0), min(grey.shape[1], z.x1)
    if y1 - y0 < 4 or x1 - x0 < 4:
        return []
    crop = grey[y0:y1, x0:x1]
    if upscale > 1:
        crop = np.asarray(Image.fromarray(crop).resize(
            (crop.shape[1] * upscale, crop.shape[0] * upscale), Image.LANCZOS))
    scale = upscale
    return [Word(m.text, x0 + m.cx / scale, y0 + m.cy / scale, m.conf)
            for m in ocr_words(crop, language, psm=psm)]
