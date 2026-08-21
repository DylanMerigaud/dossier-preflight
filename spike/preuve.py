#!/usr/bin/env python3
"""Premier test vert. Chaine complete sur un formulaire public vierge, zero donnee reelle.

    formulaire vierge -> rempli a moitie (personne inventee) -> rendu -> degrade
    -> redresse -> trois capteurs -> constats

TROIS CAPTEURS, ET C'EST LE RESULTAT PRINCIPAL DE CE SPIKE. Il a fallu trois passes:

  1. l'encre brute dans la zone a annonce 8 cases cochees alors que rien n'etait coche.
     Cause: le scan est tourne et il etait compare a une reference droite.
     -> TOUT controle par coordonnees exige un REDRESSEMENT d'abord.
  2. apres redressement les cases sont exactes, mais un champ texte VIDE lisait encore
     +2,44% d'encre (contre +4,5 a +5,1 pour un champ rempli): separable, mais fragile.
     -> l'encre est le mauvais capteur pour du TEXTE.
  3. positions de mots OCR pour le texte, encre differentielle pour les cases: net.

Le formulaire vierge n'est pas qu'une fixture, c'est l'IMAGE DE REFERENCE: chaque controle
est un differentiel contre lui, et les mots pre-imprimes lus sur le vierge sont soustraits,
donc on n'affirme jamais que sur ce qui a ete AJOUTE.

Cadeau des formulaires AcroForm: ils DECLARENT leurs zones (23 rectangles sur la page 1 du
W-9), donc aucune coordonnee ne se mesure a la main.

    python3 spike/preuve.py     # exit 0 si les trois capteurs sont d'accord
"""
import csv, io, os, subprocess, sys, unicodedata
import numpy as np
from PIL import Image, ImageFilter
from pypdf import PdfReader, PdfWriter

ICI = os.path.dirname(os.path.abspath(__file__))
VIERGE_PDF = os.path.normpath(os.path.join(ICI, "..", "corpus", "fw9.pdf"))
DPI, MARGE, SEED = 200, 6, 7
SKEW, SIGMA, FLOU, JPEG = 0.45, 6, 0.4, 55

FICTIF = {"f1_01[0]": "MARISOL QUISPE VARGAS",     # personne inventee
          "f1_07[0]": "128 RUE DES ACACIAS",
          "f1_08[0]": "COMMENTRY, FR 03600",
          "c1_1[0]":  "/1"}                         # une seule case cochee
VIDE_EXPRES = "f1_11[0]"                            # defaut injecte: numero fiscal jamais rempli


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def zones_declarees(pdf):
    """Le PDF fillable declare lui-meme ou sont ses champs."""
    page = PdfReader(pdf).pages[0]
    H, s = float(page.mediabox.height), DPI / 72.0
    out = {}
    for an in page.get("/Annots", []):
        o = an.get_object()
        if o.get("/T") and "/Rect" in o:
            x0, y0, x1, y1 = [float(v) for v in o["/Rect"]]
            out[str(o["/T"])] = (int(x0*s), int((H-y1)*s), int(x1*s), int((H-y0)*s), str(o.get("/FT")))
    return out


def remplir(dest):
    w = PdfWriter(clone_from=VIERGE_PDF)
    w.set_need_appearances_writer(True)
    w.update_page_form_field_values(w.pages[0], FICTIF, auto_regenerate=True)
    w.write(dest)


def rendre(pdf, prefixe):
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-f", "1", "-l", "1", pdf, prefixe], check=True)
    return prefixe + "-1.png"


def degrader(png, dest):
    im = Image.open(png).convert("RGB").rotate(SKEW, resample=Image.BICUBIC, fillcolor=(255,)*3)
    a = np.asarray(im).astype(np.int16)
    a += np.random.default_rng(SEED).normal(0, SIGMA, a.shape).astype(np.int16)
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(FLOU)).save(dest, quality=JPEG)
    return dest


def redresser(jpg):
    """L'angle qui maximise la variance du profil de projection horizontal."""
    g = np.asarray(Image.open(jpg).convert("L"))
    def score(ang):
        B = np.asarray(Image.fromarray(g).rotate(ang, resample=Image.BILINEAR, fillcolor=255))
        return float(np.var((B < 160).sum(axis=1)))
    ang = max(np.arange(-1.5, 1.51, 0.05), key=score)
    return ang, np.asarray(Image.fromarray(g).rotate(ang, resample=Image.BICUBIC, fillcolor=255))


def mots_ocr(png, langue="eng", conf_min=40):
    out = subprocess.run(["tesseract", png, "stdout", "-l", langue, "--psm", "11", "tsv"],
                         capture_output=True, text=True).stdout
    mots = []
    for x in csv.DictReader(io.StringIO(out), delimiter="\t"):
        t = (x.get("text") or "").strip()
        if not t or float(x.get("conf", -1)) < conf_min:
            continue
        L, T, W, H = int(x["left"]), int(x["top"]), int(x["width"]), int(x["height"])
        mots.append((t, L + W/2, T + H/2))
    return mots


def disque(A, z, part=0.42):
    """Encre dans un disque au CENTRE de la case: le trait de la case reste dehors."""
    x0, y0, x1, y1 = z[:4]
    cx, cy, rr = (x0+x1)/2, (y0+y1)/2, min(x1-x0, y1-y0) * part
    ya, yb, xa, xb = max(0, int(cy-rr)), int(cy+rr)+1, max(0, int(cx-rr)), int(cx+rr)+1
    c = A[ya:yb, xa:xb]
    if c.size == 0:
        return 0.0
    Y, X = np.ogrid[ya:yb, xa:xb]
    m = ((X-cx)**2 + (Y-cy)**2) <= rr*rr
    return float(((c < 160) & m).sum()) / max(1, m.sum()) * 100


def main():
    tmp = os.path.join(ICI, ".travail")
    os.makedirs(tmp, exist_ok=True)
    rempli = os.path.join(tmp, "rempli.pdf")
    remplir(rempli)
    png_vierge = rendre(VIERGE_PDF, os.path.join(tmp, "vierge"))
    png_propre = rendre(rempli, os.path.join(tmp, "propre"))
    scan = degrader(png_propre, os.path.join(tmp, "scan.jpg"))
    angle, SCAN = redresser(scan)
    VIERGE = np.asarray(Image.open(png_vierge).convert("L"))
    redresse = os.path.join(tmp, "scan_redresse.png")
    Image.fromarray(SCAN).save(redresse)

    zones = zones_declarees(VIERGE_PDF)
    mots = mots_ocr(redresse)
    preimprime = {t.lower() for t, _, _ in mots_ocr(png_vierge)}
    echecs = []
    print(f"redressement: {angle:+.2f} deg (injecte {-SKEW:+.2f})   zones declarees: {len(zones)}\n")

    # C1 champ texte requis: un MOT AJOUTE dont le centre tombe dans la zone
    print("=== C1 champs requis (positions OCR) ===")
    attendu = {"f1_01[0]": True, "f1_07[0]": True, "f1_08[0]": True, VIDE_EXPRES: False}
    for k, doit_etre_rempli in attendu.items():
        x0, y0, x1, y1, _ = zones[k]
        dedans = [t for t, cx, cy in mots
                  if x0 <= cx <= x1 and y0 <= cy <= y1 and t.lower() not in preimprime]
        rempli_vu = bool(dedans)
        ok = rempli_vu == doit_etre_rempli
        echecs += [] if ok else [f"C1 {k}: attendu rempli={doit_etre_rempli}, vu {rempli_vu}"]
        print(f"  {'ok ' if ok else 'ECHEC'} {k:12s} {len(dedans)} mot(s) {str(dedans)[:42]:44s}"
              f" {'rempli' if rempli_vu else 'VIDE -> REFUS'}")

    # C2 ce qui est declare est-il VRAIMENT imprime
    print("\n=== C2 valeurs vraiment imprimees ===")
    lu = norm(" ".join(t for t, _, _ in mots))
    for v, doit in [("MARISOL QUISPE VARGAS", True), ("128 RUE DES ACACIAS", True),
                    ("COMMENTRY", True), ("Request for Taxpayer", True), ("999-99-9999", False)]:
        vu = norm(v) in lu
        ok = vu == doit
        echecs += [] if ok else [f"C2 {v}: attendu {doit}, vu {vu}"]
        print(f"  {'ok ' if ok else 'ECHEC'} {'PRESENT' if vu else 'ABSENT '}  {v}")

    # C3 cases: encre differentielle dans le disque central
    print("\n=== C3 cases a cocher (scan moins vierge) ===")
    for k, z in sorted(zones.items()):
        if z[4] != "/Btn":
            continue
        d = disque(SCAN, z) - disque(VIERGE, z)
        cochee, doit = d > 8, (k in FICTIF)
        ok = cochee == doit
        echecs += [] if ok else [f"C3 {k}: attendu cochee={doit}, vu {cochee} (delta {d:+.1f})"]
        print(f"  {'ok ' if ok else 'ECHEC'} {k:10s} delta={d:+6.1f}  {'COCHEE' if cochee else 'vide'}")

    print()
    if echecs:
        for e in echecs:
            print("ECHEC:", e)
        return 1
    print(f"VERT: {len(attendu)} champs, 5 valeurs, "
          f"{sum(1 for z in zones.values() if z[4] == '/Btn')} cases, zero donnee reelle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
