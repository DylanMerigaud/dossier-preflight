"""PDF to greyscale image, with a disk cache: the same page at the same dpi renders once."""
import hashlib
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image

from . import CANON_DPI

CACHE = os.environ.get("PREFLIGHT_CACHE",
                       os.path.join(tempfile.gettempdir(), "preflight-cache"))


def _key(pdf, dpi, page):
    st = os.stat(pdf)
    raw = f"{os.path.abspath(pdf)}|{st.st_mtime_ns}|{st.st_size}|{dpi}|{page}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def render(pdf, dpi=CANON_DPI, page=1, cache=None):
    """One page as greyscale uint8. Returns a numpy array of shape (H, W)."""
    directory = cache or CACHE
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, f"{_key(pdf, dpi, page)}.png")
    if not os.path.exists(dest):
        with tempfile.TemporaryDirectory(dir=directory) as t:
            prefix = os.path.join(t, "p")
            subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png",
                            "-f", str(page), "-l", str(page), pdf, prefix], check=True)
            produced = [f for f in sorted(os.listdir(t)) if f.endswith(".png")]
            if not produced:
                raise RuntimeError(f"pdftoppm produced nothing for {pdf} page {page}")
            os.replace(os.path.join(t, produced[0]), dest)
    return np.asarray(Image.open(dest).convert("L"))
