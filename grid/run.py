#!/usr/bin/env python3
"""La grid de degradation. Elle produced les MESURES, elle ne decide rien.

    angle (0, 0.25, 0.5, 1, 2, 4 deg)  x  dpi (96, 150, 200, 300)
      x  qualite JPEG (30, 55, 75, 95)  x  bruit sigma (0, 3, 6, 12)   x  N graines

Soit 384 cellules. Pour chaque cell et chaque seed on lit le dossier SAIN (trois pieces)
et les neuf variantes a defaut unique (une piece modifiee chacune): douze readings, et une
ligne JSONL par reading. Rien n'est compare a un threshold ici, c'est delibere: l'analyse balaie
ensuite des milliers de points de fonctionnement sur ces mesures sans retoucher une image.

    python3 grid/run.py                 # grid complete, reprend ou elle s'est arretee
    python3 grid/run.py --pilote 8      # 8 cellules, pour verifier le cout avant de tout run
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
from preflight.fixtures import VARIANTS, build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference

ANGLES = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
DPIS = (96, 150, 200, 300)
JPEGS = (30, 55, 75, 95)
SIGMAS = (0.0, 3.0, 6.0, 12.0)
SEEDS = (11, 23, 37)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "grid", "mesures")
FIXTURES = os.path.join(ROOT, "grid", ".fixtures")

_REF = None
_PIECES = None


def _amorcer():
    """Chaque processus construit ses fixtures une fois et rechauffe les vierges."""
    global _REF, _PIECES
    if _REF is not None:
        return
    _REF = load_reference()
    _PIECES = {}
    for v in VARIANTS:
        d = build(_REF, v.name, FIXTURES)
        for p in d.pieces:
            _PIECES[(v.name, p.id)] = p
    for _, g in _REF.pieces:
        blank(_REF.templates[g])


def pieces_to_read():
    """Les douze couples (variant, piece) a read_piece par cell et par seed.

    Une variant ne touche qu'UNE piece: les deux autres sont identiques a celles du dossier
    clean et leur reading est reprise telle quelle a l'analyse. Sans cette economie la grid
    couterait trente readings par cell au lieu de douze.
    """
    _amorcer()
    couples = [("clean", p) for p, _ in _REF.pieces]
    couples += [(v.name, v.piece) for v in VARIANTS if v.check]
    return couples


def task(tache):
    cell, seed = tache
    angle, dpi, jpeg, sigma = cell
    _amorcer()
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed)
    lignes = []
    for nom_var, piece_id in pieces_to_read():
        p = _PIECES[(nom_var, piece_id)]
        deg = replace(base, **p.image_override) if p.image_override else base
        t = time.perf_counter()
        lec = read_piece(p, deg)
        lignes.append({"angle": angle, "dpi": dpi, "jpeg": jpeg, "sigma": sigma,
                       "seed": seed, "variant": nom_var, "piece": piece_id,
                       "seconds": round(time.perf_counter() - t, 2), "reading": lec.dict()})
    return lignes


def key(l):
    return (l["angle"], l["dpi"], l["jpeg"], l["sigma"], l["seed"], l["variant"], l["piece"])


def already_done(path):
    faites = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ligne in f:
                try:
                    faites.add(key(json.loads(ligne)))
                except (ValueError, KeyError):
                    continue
    return faites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilote", type=int, default=0, help="ne traiter que N cellules")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--sortie", default=os.path.join(OUTPUT, "mesures.jsonl"))
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.sortie), exist_ok=True)
    cellules = list(itertools.product(ANGLES, DPIS, JPEGS, SIGMAS))
    if a.pilote:
        pas = max(1, len(cellules) // a.pilote)
        cellules = cellules[::pas][:a.pilote]
    taches = [(c, g) for c in cellules for g in SEEDS]

    _amorcer()          # les fixtures sont construites UNE fois, avant tout fork
    faites = already_done(a.sortie)
    attendu = len(pieces_to_read())
    restantes = [t for t in taches
                 if sum(1 for f in faites if f[:5] == (t[0][0], t[0][1], t[0][2], t[0][3], t[1]))
                 < attendu]
    print(f"{len(cellules)} cellules x {len(SEEDS)} graines x {attendu} readings "
          f"= {len(taches) * attendu} readings")
    print(f"{len(faites)} deja faites, {len(restantes)} taches restantes, {a.procs} processus")
    if not restantes:
        return 0

    t0 = time.perf_counter()
    with open(a.sortie, "a", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, lignes in enumerate(pool.imap_unordered(task, restantes), 1):
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
