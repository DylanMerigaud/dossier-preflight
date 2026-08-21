import os
import sys
from dataclasses import replace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.degradation import Degradation
from preflight.fixtures import VARIANTES, construire
from preflight.lecture import lire, vierge
from preflight.referentiel import charger_referentiel

# La cellule du spike: page de travers, bruitee, recompressee. Un test qui ne tournerait que
# sur un rendu parfait ne prouverait rien de ce que l'outil pretend faire.
# Ce point est PROVISOIRE tant que LIMITES.md n'a pas donne le plancher de panne par
# controle: il est choisi au-dessus du plancher suppose, pas mesure comme etant au-dessus.
CELLULE = Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0, graine=11)


@pytest.fixture(scope="session")
def referentiel():
    return charger_referentiel()


@pytest.fixture(scope="session")
def lectures(referentiel, tmp_path_factory):
    """Les douze lectures du dossier: le sain en entier, puis la piece modifiee par variante.

    Douze et pas trente: une variante ne touche qu'une piece, les deux autres sont celles du
    dossier sain et se reprennent telles quelles.
    """
    dest = str(tmp_path_factory.mktemp("fixtures"))
    for _, g in referentiel.pieces:
        vierge(referentiel.gabarits[g])
    dossiers = {v.nom: construire(referentiel, v.nom, dest) for v in VARIANTES}
    sain = {p.id: lire(p, CELLULE) for p in dossiers["sain"].pieces}
    out = {"sain": sain}
    for v in VARIANTES:
        if not v.controle:
            continue
        p = dossiers[v.nom].piece(v.piece)
        deg = replace(CELLULE, **p.surcharge_image) if p.surcharge_image else CELLULE
        out[v.nom] = dict(sain, **{v.piece: lire(p, deg)})
    return out
