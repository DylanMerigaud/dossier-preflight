#!/usr/bin/env python3
"""The first green test. The whole chain on a public blank form, zero real data.

    blank form -> half filled (invented person) -> render -> degrade
    -> deskew -> three sensors -> findings

THREE SENSORS, AND THAT IS THIS SPIKE'S MAIN RESULT. It took three passes:

  1. raw ink inside the zone reported 8 ticked boxes when nothing was ticked at all.
     Cause: the scan is rotated and it was compared against an upright reference.
     -> ANY coordinate-based check needs DESKEWING first.
  2. after deskewing the boxes are exact, but an EMPTY text field still read +2.44% ink
     (against +4.5 to +5.1 for a filled one): separable, but fragile.
     -> ink is the wrong sensor for TEXT.
  3. OCR word positions for text, differential ink for boxes: clean.

The blank form is not just a fixture, it is the REFERENCE IMAGE: every check is a differential
against it, and the pre-printed words read on the blank are subtracted, so the tool only ever
asserts something about what was ADDED.

A gift from AcroForm PDFs: they DECLARE their zones (23 rectangles on page 1 of the W-9), so no
coordinate is ever measured by hand.

    python3 spike/proof.py     # exit 0 if the three sensors agree
"""
import csv, io, os, subprocess, sys, unicodedata
import numpy as np
from PIL import Image, ImageFilter
from pypdf import PdfReader, PdfWriter

HERE = os.path.dirname(os.path.abspath(__file__))
BLANK_PDF = os.path.normpath(os.path.join(HERE, "..", "corpus", "fw9.pdf"))
DPI, MARGIN, SEED = 200, 6, 7
SKEW, SIGMA, BLUR, JPEG = 0.45, 6, 0.4, 55

FICTIONAL = {"f1_01[0]": "MARISOL QUISPE VARGAS",     # invented person
          "f1_07[0]": "128 RUE DES ACACIAS",
          "f1_08[0]": "COMMENTRY, FR 03600",
          "c1_1[0]":  "/1"}                         # only one box ticked
DELIBERATELY_EMPTY = "f1_11[0]"                            # injected defect: tax number never filled


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def declared_zones(pdf):
    """The fillable PDF declares where its fields are."""
    page = PdfReader(pdf).pages[0]
    H, s = float(page.mediabox.height), DPI / 72.0
    out = {}
    for an in page.get("/Annots", []):
        o = an.get_object()
        if o.get("/T") and "/Rect" in o:
            x0, y0, x1, y1 = [float(v) for v in o["/Rect"]]
            out[str(o["/T"])] = (int(x0*s), int((H-y1)*s), int(x1*s), int((H-y0)*s), str(o.get("/FT")))
    return out


def fill(dest):
    w = PdfWriter(clone_from=BLANK_PDF)
    w.set_need_appearances_writer(True)
    w.update_page_form_field_values(w.pages[0], FICTIONAL, auto_regenerate=True)
    w.write(dest)


def render(pdf, prefix):
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-f", "1", "-l", "1", pdf, prefix], check=True)
    return prefix + "-1.png"


def degrade(png, dest):
    im = Image.open(png).convert("RGB").rotate(SKEW, resample=Image.BICUBIC, fillcolor=(255,)*3)
    a = np.asarray(im).astype(np.int16)
    a += np.random.default_rng(SEED).normal(0, SIGMA, a.shape).astype(np.int16)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(BLUR)).save(dest, quality=JPEG)
    return dest


def deskew(jpg):
    """The angle that maximises the variance of the horizontal projection profile."""
    g = np.asarray(Image.open(jpg).convert("L"))
    def score(ang):
        B = np.asarray(Image.fromarray(g).rotate(ang, resample=Image.BILINEAR, fillcolor=255))
        return float(np.var((B < 160).sum(axis=1)))
    ang = max(np.arange(-1.5, 1.51, 0.05), key=score)
    return ang, np.asarray(Image.fromarray(g).rotate(ang, resample=Image.BICUBIC, fillcolor=255))


def ocr_words(png, language="eng", min_conf=40):
    out = subprocess.run(["tesseract", png, "stdout", "-l", language, "--psm", "11", "tsv"],
                         capture_output=True, text=True).stdout
    words = []
    for x in csv.DictReader(io.StringIO(out), delimiter="\t"):
        t = (x.get("text") or "").strip()
        if not t or float(x.get("conf", -1)) < min_conf:
            continue
        L, T, W, H = int(x["left"]), int(x["top"]), int(x["width"]), int(x["height"])
        words.append((t, L + W/2, T + H/2))
    return words


def disc(A, z, ratio=0.42):
    """Ink in a disc at the CENTRE of the box: the box outline stays outside."""
    x0, y0, x1, y1 = z[:4]
    cx, cy, rr = (x0+x1)/2, (y0+y1)/2, min(x1-x0, y1-y0) * ratio
    ya, yb, xa, xb = max(0, int(cy-rr)), int(cy+rr)+1, max(0, int(cx-rr)), int(cx+rr)+1
    c = A[ya:yb, xa:xb]
    if c.size == 0:
        return 0.0
    Y, X = np.ogrid[ya:yb, xa:xb]
    m = ((X-cx)**2 + (Y-cy)**2) <= rr*rr
    return float(((c < 160) & m).sum()) / max(1, m.sum()) * 100


def main():
    tmp = os.path.join(HERE, ".work")
    os.makedirs(tmp, exist_ok=True)
    filled = os.path.join(tmp, "filled.pdf")
    fill(filled)
    png_blank = render(BLANK_PDF, os.path.join(tmp, "blank"))
    png_clean = render(filled, os.path.join(tmp, "clean"))
    scan = degrade(png_clean, os.path.join(tmp, "scan.jpg"))
    angle, SCAN = deskew(scan)
    BLANK = np.asarray(Image.open(png_blank).convert("L"))
    straightened = os.path.join(tmp, "scan_deskewed.png")
    Image.fromarray(SCAN).save(straightened)

    zones = declared_zones(BLANK_PDF)
    words = ocr_words(straightened)
    preprinted = {t.lower() for t, _, _ in ocr_words(png_blank)}
    failures = []
    print(f"deskew: {angle:+.2f} deg (injected {-SKEW:+.2f})   declared zones: {len(zones)}\n")

    # C1 required text field: an ADDED WORD whose centre falls inside the zone
    print("=== C1 required fields (OCR positions) ===")
    expected = {"f1_01[0]": True, "f1_07[0]": True, "f1_08[0]": True, DELIBERATELY_EMPTY: False}
    for k, should_be_filled in expected.items():
        x0, y0, x1, y1, _ = zones[k]
        inside = [t for t, cx, cy in words
                  if x0 <= cx <= x1 and y0 <= cy <= y1 and t.lower() not in preprinted]
        seen_filled = bool(inside)
        ok = seen_filled == should_be_filled
        failures += [] if ok else [f"C1 {k}: expected filled={should_be_filled}, saw {seen_filled}"]
        print(f"  {'ok  ' if ok else 'FAIL'} {k:12s} {len(inside)} word(s) {str(inside)[:42]:44s}"
              f" {'filled' if seen_filled else 'EMPTY -> REJECT'}")

    # C2 is what is declared REALLY printed
    print("\n=== C2 values actually printed ===")
    read = norm(" ".join(t for t, _, _ in words))
    for v, should in [("MARISOL QUISPE VARGAS", True), ("128 RUE DES ACACIAS", True),
                      ("COMMENTRY", True), ("Request for Taxpayer", True), ("999-99-9999", False)]:
        seen = norm(v) in read
        ok = seen == should
        failures += [] if ok else [f"C2 {v}: expected {should}, saw {seen}"]
        print(f"  {'ok  ' if ok else 'FAIL'} {'PRESENT' if seen else 'ABSENT '}  {v}")

    # C3 checkboxes: differential ink inside the central disc
    print("\n=== C3 checkboxes (scan minus blank) ===")
    for k, z in sorted(zones.items()):
        if z[4] != "/Btn":
            continue
        d = disc(SCAN, z) - disc(BLANK, z)
        ticked, should = d > 8, (k in FICTIONAL)
        ok = ticked == should
        failures += [] if ok else [f"C3 {k}: expected ticked={should}, saw {ticked} (delta {d:+.1f})"]
        print(f"  {'ok  ' if ok else 'FAIL'} {k:10s} delta={d:+6.1f}  {'TICKED' if ticked else 'empty'}")

    print()
    if failures:
        for e in failures:
            print("FAIL:", e)
        return 1
    print(f"GREEN: {len(expected)} fields, 5 values, "
          f"{sum(1 for z in zones.values() if z[4] == '/Btn')} boxes, zero real data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
