import os
import sys
from dataclasses import replace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.degradation import Degradation
from preflight.fixtures import VARIANTS, build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference

# The spike's cell: page skewed, noisy, recompressed. A test that only ran on a perfect render
# would prove nothing about what the tool claims to do.
# This point is PROVISIONAL until LIMITES.md gives the per-check breakdown floor: it is chosen
# above the assumed floor, not measured as being above it.
CELL = Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0, seed=11)


@pytest.fixture(scope="session")
def reference():
    return load_reference()


@pytest.fixture(scope="session")
def readings(reference, tmp_path_factory):
    """The dossier's twelve readings: the clean one in full, then the piece each variant edits.

    Twelve and not thirty: a variant only touches one piece, the other two are the clean
    dossier's and are reused as they are.
    """
    dest = str(tmp_path_factory.mktemp("fixtures"))
    for _, name in reference.pieces:
        blank(reference.templates[name])
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
