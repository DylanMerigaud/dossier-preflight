#!/usr/bin/env python3
"""La grille de degradation. Elle produit les MESURES, elle ne decide rien.

    angle (0, 0.25, 0.5, 1, 2, 4 deg)  x  dpi (96, 150, 200, 300)
      x  qualite JPEG (30, 55, 75, 95)  x  bruit sigma (0, 3, 6, 12)   x  N graines

Soit 384 cellules. Pour chaque cellule et chaque graine on lit le dossier SAIN (trois pieces)
et les neuf variantes a defaut unique (une piece modifiee chacune): douze lectures, et une
ligne JSONL par lecture. Rien n'est compare a un seuil ici, c'est delibere: l'analyse balaie
ensuite des milliers de points de fonctionnement sur ces mesures sans retoucher une image.

    python3 grille/lancer.py                 # grille complete, reprend ou elle s'est arretee
    python3 grille/lancer.py --pilote 8      # 8 cellules, pour verifier le cout avant de tout lancer
"""
import argparse
import itertools
import json
import os
import sys
import time
from dataclasses import replace
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.degradation import Degradation
from preflight.fixtures import VARIANTES, construire
from preflight.lecture import lire, vierge
from preflight.referentiel import charger_referentiel

ANGLES = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
DPIS = (96, 150, 200, 300)
JPEGS = (30, 55, 75, 95)
SIGMAS = (0.0, 3.0, 6.0, 12.0)
GRAINES = (11, 23, 37)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE = os.path.join(RACINE, "grille", "mesures")
FIXTURES = os.path.join(RACINE, "grille", ".fixtures")

_REF = None
_PIECES = None


def _amorcer():
    """Chaque processus construit ses fixtures une fois et rechauffe les vierges."""
    global _REF, _PIECES
    if _REF is not None:
        return
    _REF = charger_referentiel()
    _PIECES = {}
    for v in VARIANTES:
        d = construire(_REF, v.nom, FIXTURES)
        for p in d.pieces:
            _PIECES[(v.nom, p.id)] = p
    for _, g in _REF.pieces:
        vierge(_REF.gabarits[g])


def a_lire():
    """Les douze couples (variante, piece) a lire par cellule et par graine.

    Une variante ne touche qu'UNE piece: les deux autres sont identiques a celles du dossier
    sain et leur lecture est reprise telle quelle a l'analyse. Sans cette economie la grille
    couterait trente lectures par cellule au lieu de douze.
    """
    _amorcer()
    couples = [("sain", p) for p, _ in _REF.pieces]
    couples += [(v.nom, v.piece) for v in VARIANTES if v.controle]
    return couples


def travail(tache):
    cellule, graine = tache
    angle, dpi, jpeg, sigma = cellule
    _amorcer()
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, graine=graine)
    lignes = []
    for nom_var, piece_id in a_lire():
        p = _PIECES[(nom_var, piece_id)]
        deg = replace(base, **p.surcharge_image) if p.surcharge_image else base
        t = time.perf_counter()
        lec = lire(p, deg)
        lignes.append({"angle": angle, "dpi": dpi, "jpeg": jpeg, "sigma": sigma,
                       "graine": graine, "variante": nom_var, "piece": piece_id,
                       "secondes": round(time.perf_counter() - t, 2), "lecture": lec.dict()})
    return lignes


def cle(l):
    return (l["angle"], l["dpi"], l["jpeg"], l["sigma"], l["graine"], l["variante"], l["piece"])


def deja_faites(chemin):
    faites = set()
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            for ligne in f:
                try:
                    faites.add(cle(json.loads(ligne)))
                except (ValueError, KeyError):
                    continue
    return faites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilote", type=int, default=0, help="ne traiter que N cellules")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--sortie", default=os.path.join(SORTIE, "mesures.jsonl"))
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.sortie), exist_ok=True)
    cellules = list(itertools.product(ANGLES, DPIS, JPEGS, SIGMAS))
    if a.pilote:
        pas = max(1, len(cellules) // a.pilote)
        cellules = cellules[::pas][:a.pilote]
    taches = [(c, g) for c in cellules for g in GRAINES]

    _amorcer()          # les fixtures sont construites UNE fois, avant tout fork
    faites = deja_faites(a.sortie)
    attendu = len(a_lire())
    restantes = [t for t in taches
                 if sum(1 for f in faites if f[:5] == (t[0][0], t[0][1], t[0][2], t[0][3], t[1]))
                 < attendu]
    print(f"{len(cellules)} cellules x {len(GRAINES)} graines x {attendu} lectures "
          f"= {len(taches) * attendu} lectures")
    print(f"{len(faites)} deja faites, {len(restantes)} taches restantes, {a.procs} processus")
    if not restantes:
        return 0

    t0 = time.perf_counter()
    with open(a.sortie, "a", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, lignes in enumerate(pool.imap_unordered(travail, restantes), 1):
            for l in lignes:
                f.write(json.dumps(l, ensure_ascii=False) + "\n")
            f.flush()
            if i % 10 == 0 or i == len(restantes):
                ecoule = time.perf_counter() - t0
                reste = ecoule / i * (len(restantes) - i)
                print(f"  {i}/{len(restantes)} taches, {ecoule/60:.1f} min ecoulees, "
                      f"{reste/60:.1f} min restantes", flush=True)
    print(f"termine en {(time.perf_counter() - t0)/60:.1f} min -> {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
