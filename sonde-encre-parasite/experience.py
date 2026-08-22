#!/usr/bin/env python3
"""Le duel des fields required rejoue sur un terrain que la grid ne couvrait pas.

Question: de combien d'ink ETRANGERE a-t-on besoin pour qu'un field VIDE passe pour rempli,
et les quatre sensors concurrents y resistent-ils pareil.

Le parasite est pose sur le render PROPRE, avant degradation, donc il subit ensuite la meme
rotation, le meme bruit, le meme blur et la meme compression que le reste de la page: c'est ce
que ferait un buffer ou une ombre de pliure sur une feuille qu'on numerise ensuite.

    python3 experience.py --procs 13
"""
import argparse
import collections
import itertools
import json
import os
import sys
from dataclasses import replace
from multiprocessing import Pool

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(ICI, "src"))

import numpy as np

import parasite
import preflight.reading as PL
from preflight.checks import Settings, evaluate
from preflight.degradation import Degradation
from preflight.fixtures import build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference
from preflight.thresholds import load_thresholds
from preflight.checks import zones

PIECE = "employment"
CHAMP = "City or Town"          # le field que la variant empty_required_field laisse vide
VARIANTS = ("empty_required_field", "clean")
FORMES = ("tache", "pliure", "trait")
INTENSITES = (0.001, 0.002, 0.005, 0.01, 0.02, 0.035, 0.05)
CELLULES = (Degradation(angle=0.25, dpi=200, jpeg=95, sigma=0.0),
            Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0))
SEEDS = (11, 23, 37, 101, 102, 103)

# Les quatre concurrents, chacun a SON point de fonctionnement mesure par la grid.
CAPTEURS = {"ink": Settings(text_sensor="ink", ink_threshold=128),
            "union": Settings(text_sensor="union", min_conf=0.0),
            "page": Settings(text_sensor="page", min_conf=0.0),
            "zone": Settings(text_sensor="zone", min_conf=0.0)}
# Seuil de chaque capteur, lu sur la grid publiee pour l'ink, et sur la meme regle pour
# les sensors de words (le duel de LIMITES.md les donne a -1 caractere).
SEUILS = {"ink": None, "union": -1.0, "page": -1.0, "zone": -1.0}

_ETAT = {}
_APPLIQUER = PL.apply


def _amorcer():
    if _ETAT:
        return
    ref = load_reference()
    dest = os.path.join(ICI, "fixtures")
    _ETAT["ref"] = ref
    _ETAT["pieces"] = {v: build(ref, v, dest).piece(PIECE) for v in VARIANTS}
    _ETAT["zone"] = zones(ref.templates["i9"])[CHAMP]
    _ETAT["ink_threshold"] = load_thresholds()["required_field"]
    blank(ref.templates["i9"])


def _patch(shape, intensity, seed):
    """Injecte le parasite entre le render propre et la degradation."""
    z, f = _ETAT["zone"], parasite.FORMES.get(shape)

    def apply(grey, deg):
        if f is not None and intensity > 0:
            grey = f(grey.copy(), z, deg.dpi, intensity, np.random.default_rng(seed))
        return _APPLIQUER(grey, deg)
    PL.apply = apply


def task(tache):
    variant, shape, intensity, i_cell, seed = tache
    _amorcer()
    _patch(shape, intensity, seed)
    try:
        deg = replace(CELLULES[i_cell], seed=seed)
        lec = read_piece(_ETAT["pieces"][variant], deg)
    finally:
        PL.apply = _APPLIQUER
    ref = _ETAT["ref"]
    ligne = {"variant": variant, "shape": shape, "intensity": intensity,
             "cell": i_cell, "seed": seed,
             "added_ink": lec.field_ink.get(CHAMP, {}).get("128")}
    for name, reg in CAPTEURS.items():
        cons = [c for c in evaluate({PIECE: lec}, ref, "filing", reg,
                                   checks=["required_field"]) if c.target == CHAMP]
        if not cons:
            continue
        threshold = _ETAT["ink_threshold"] if SEUILS[name] is None else SEUILS[name]
        ligne[name] = {"score": cons[0].score, "fires": cons[0].score > threshold,
                      "detail": cons[0].detail[:30]}
    return ligne


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--sortie", default=os.path.join(ICI, "resultats.jsonl"))
    a = ap.parse_args()
    _amorcer()
    conditions = [(None, 0.0)] + [(f, i) for f in FORMES for i in INTENSITES]
    taches = [(v, f, i, c, g)
              for v in VARIANTS for (f, i) in conditions
              for c in range(len(CELLULES)) for g in SEEDS]
    print(f"{len(taches)} readings, {len(conditions)} conditions x {len(VARIANTS)} variantes "
          f"x {len(CELLULES)} cellules x {len(SEEDS)} graines")
    with open(a.sortie, "w", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, ligne in enumerate(pool.imap_unordered(task, taches), 1):
            f.write(json.dumps(ligne) + "\n")
            if i % 60 == 0:
                print(f"  {i}/{len(taches)}", flush=True)
    print(f"-> {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
