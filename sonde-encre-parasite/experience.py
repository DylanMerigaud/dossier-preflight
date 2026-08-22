#!/usr/bin/env python3
"""Le duel des champs requis rejoue sur un terrain que la grille ne couvrait pas.

Question: de combien d'encre ETRANGERE a-t-on besoin pour qu'un champ VIDE passe pour rempli,
et les quatre capteurs concurrents y resistent-ils pareil.

Le parasite est pose sur le rendu PROPRE, avant degradation, donc il subit ensuite la meme
rotation, le meme bruit, le meme flou et la meme compression que le reste de la page: c'est ce
que ferait un tampon ou une ombre de pliure sur une feuille qu'on numerise ensuite.

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
import preflight.lecture as PL
from preflight.controles import Reglages, evaluer
from preflight.degradation import Degradation
from preflight.fixtures import construire
from preflight.lecture import lire, vierge
from preflight.referentiel import charger_referentiel
from preflight.seuils import charger_seuils
from preflight.controles import zones

PIECE = "emploi"
CHAMP = "City or Town"          # le champ que la variante champ_requis_vide laisse vide
VARIANTES = ("champ_requis_vide", "sain")
FORMES = ("tache", "pliure", "trait")
INTENSITES = (0.001, 0.002, 0.005, 0.01, 0.02, 0.035, 0.05)
CELLULES = (Degradation(angle=0.25, dpi=200, jpeg=95, sigma=0.0),
            Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0))
GRAINES = (11, 23, 37, 101, 102, 103)

# Les quatre concurrents, chacun a SON point de fonctionnement mesure par la grille.
CAPTEURS = {"encre": Reglages(capteur_texte="encre", seuil_encre=128),
            "union": Reglages(capteur_texte="union", conf_min=0.0),
            "page": Reglages(capteur_texte="page", conf_min=0.0),
            "zone": Reglages(capteur_texte="zone", conf_min=0.0)}
# Seuil de chaque capteur, lu sur la grille publiee pour l'encre, et sur la meme regle pour
# les capteurs de mots (le duel de LIMITES.md les donne a -1 caractere).
SEUILS = {"encre": None, "union": -1.0, "page": -1.0, "zone": -1.0}

_ETAT = {}
_APPLIQUER = PL.appliquer


def _amorcer():
    if _ETAT:
        return
    ref = charger_referentiel()
    dest = os.path.join(ICI, "fixtures")
    _ETAT["ref"] = ref
    _ETAT["pieces"] = {v: construire(ref, v, dest).piece(PIECE) for v in VARIANTES}
    _ETAT["zone"] = zones(ref.gabarits["i9"])[CHAMP]
    _ETAT["seuil_encre"] = charger_seuils()["champ_requis"]
    vierge(ref.gabarits["i9"])


def _patch(forme, intensite, graine):
    """Injecte le parasite entre le rendu propre et la degradation."""
    z, f = _ETAT["zone"], parasite.FORMES.get(forme)

    def appliquer(gris, deg):
        if f is not None and intensite > 0:
            gris = f(gris.copy(), z, deg.dpi, intensite, np.random.default_rng(graine))
        return _APPLIQUER(gris, deg)
    PL.appliquer = appliquer


def travail(tache):
    variante, forme, intensite, i_cell, graine = tache
    _amorcer()
    _patch(forme, intensite, graine)
    try:
        deg = replace(CELLULES[i_cell], graine=graine)
        lec = lire(_ETAT["pieces"][variante], deg)
    finally:
        PL.appliquer = _APPLIQUER
    ref = _ETAT["ref"]
    ligne = {"variante": variante, "forme": forme, "intensite": intensite,
             "cellule": i_cell, "graine": graine,
             "encre_ajoutee": lec.encre_champs.get(CHAMP, {}).get("128")}
    for nom, reg in CAPTEURS.items():
        cons = [c for c in evaluer({PIECE: lec}, ref, "guichet", reg,
                                   controles=["champ_requis"]) if c.cible == CHAMP]
        if not cons:
            continue
        seuil = _ETAT["seuil_encre"] if SEUILS[nom] is None else SEUILS[nom]
        ligne[nom] = {"score": cons[0].score, "declenche": cons[0].score > seuil,
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
              for v in VARIANTES for (f, i) in conditions
              for c in range(len(CELLULES)) for g in GRAINES]
    print(f"{len(taches)} lectures, {len(conditions)} conditions x {len(VARIANTES)} variantes "
          f"x {len(CELLULES)} cellules x {len(GRAINES)} graines")
    with open(a.sortie, "w", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, ligne in enumerate(pool.imap_unordered(travail, taches), 1):
            f.write(json.dumps(ligne) + "\n")
            if i % 60 == 0:
                print(f"  {i}/{len(taches)}", flush=True)
    print(f"-> {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
