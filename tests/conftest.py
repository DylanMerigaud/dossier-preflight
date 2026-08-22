import os
import sys
from dataclasses import replace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.degradation import Degradation
from preflight.fixtures import VARIANTS, build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference

# La cell du spike: page de travers, bruitee, recompressee. Un test qui ne tournerait que
# sur un render parfait ne prouverait rien de ce que l'outil pretend faire.
# Ce point est PROVISOIRE tant que LIMITES.md n'a pas donne le floor de panne par
# check: il est choisi au-dessus du floor suppose, pas mesure comme etant au-dessus.
CELL = Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0, seed=11)


@pytest.fixture(scope="session")
def reference():
    return load_reference()


@pytest.fixture(scope="session")
def readings(reference, tmp_path_factory):
    """Les douze readings du dossier: le clean en entier, puis la piece modifiee par variant.

    Douze et pas trente: une variant ne touche qu'une piece, les deux autres sont celles du
    dossier clean et se reprennent telles quelles.
    """
    dest = str(tmp_path_factory.mktemp("fixtures"))
    for _, g in reference.pieces:
        blank(reference.templates[g])
    dossiers = {v.name: build(reference, v.name, dest) for v in VARIANTS}
    clean = {p.id: read_piece(p, CELL) for p in dossiers["clean"].pieces}
    out = {"clean": clean}
    for v in VARIANTS:
        if not v.check:
            continue
        p = dossiers[v.name].piece(v.piece)
        deg = replace(CELL, **p.image_override) if p.image_override else CELL
        out[v.name] = dict(clean, **{v.piece: read_piece(p, deg)})
    return out
