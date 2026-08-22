"""Rendu PDF vers image grise, avec cache disque: la meme page au meme dpi ne se rend qu'une fois."""
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
    """Page rendue en niveaux de gris, uint8. Retour: tableau numpy (H, W)."""
    rep = cache or CACHE
    os.makedirs(rep, exist_ok=True)
    dest = os.path.join(rep, f"{_key(pdf, dpi, page)}.png")
    if not os.path.exists(dest):
        with tempfile.TemporaryDirectory(dir=rep) as t:
            prefixe = os.path.join(t, "p")
            subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png",
                            "-f", str(page), "-l", str(page), pdf, prefixe], check=True)
            produit = [f for f in sorted(os.listdir(t)) if f.endswith(".png")]
            if not produit:
                raise RuntimeError(f"pdftoppm n'a rien produit pour {pdf} page {page}")
            os.replace(os.path.join(t, produit[0]), dest)
    return np.asarray(Image.open(dest).convert("L"))
