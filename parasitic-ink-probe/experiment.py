#!/usr/bin/env python3
"""The required-field duel replayed on ground the grid did not cover.

Question: how much FOREIGN ink does it take for an EMPTY field to pass for filled, and do the
four competing sensors resist it equally.

The parasite is laid on the CLEAN render, before degradation, so it then goes through the same
rotation, noise, blur and compression as the rest of the page: which is what a speck or a fold
shadow would do on a sheet that is scanned afterwards.

    python3 experiment.py --procs 13
"""
import argparse
import collections
import itertools
import json
import os
import sys
from dataclasses import replace
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "src"))

import numpy as np

import preflight.reading as PL
from preflight import parasite
from preflight.checks import Settings, evaluate
from preflight.degradation import Degradation
from preflight.fixtures import build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference
from preflight.thresholds import load_thresholds
from preflight.checks import zones

PIECE = "employment"
FIELD = "City or Town"        # the field the empty_required_field variant leaves empty
VARIANTS = ("empty_required_field", "clean")
SHAPES = ("speck", "fold", "stroke")
INTENSITIES = (0.001, 0.002, 0.005, 0.01, 0.02, 0.035, 0.05)
CELLS = (Degradation(angle=0.25, dpi=200, jpeg=95, sigma=0.0),
            Degradation(angle=0.5, dpi=200, jpeg=55, sigma=6.0))
SEEDS = (11, 23, 37, 101, 102, 103)

# The four contenders, each at ITS OWN operating point as measured by the grid.
SENSORS = {"ink": Settings(text_sensor="ink", ink_threshold=128),
            "union": Settings(text_sensor="union", min_conf=0.0),
            "page": Settings(text_sensor="page", min_conf=0.0),
            "zone": Settings(text_sensor="zone", min_conf=0.0)}
# Each sensor's threshold, read off the published grid for ink, and by the same rule for the
# word sensors (the duel in LIMITS.md puts them at -1 character).
SEUILS = {"ink": None, "union": -1.0, "page": -1.0, "zone": -1.0}

_STATE = {}
_APPLIQUER = PL.apply


def _amorcer():
    if _STATE:
        return
    ref = load_reference()
    dest = os.path.join(HERE, "fixtures")
    _STATE["ref"] = ref
    _STATE["pieces"] = {v: build(ref, v, dest).piece(PIECE) for v in VARIANTS}
    _STATE["zone"] = zones(ref.templates["i9"])[FIELD]
    _STATE["ink_threshold"] = load_thresholds()["required_field"]
    blank(ref.templates["i9"])


def _patch(shape, intensity, seed):
    """Inject the parasite between the clean render and the degradation."""
    z, f = _STATE["zone"], parasite.SHAPES.get(shape)

    def apply(grey, deg):
        if f is not None and intensity > 0:
            grey = f(grey.copy(), z, deg.dpi, intensity, np.random.default_rng(seed))
        return _APPLIQUER(grey, deg)
    PL.apply = apply


def task(task):
    variant, shape, intensity, i_cell, seed = task
    _amorcer()
    _patch(shape, intensity, seed)
    try:
        deg = replace(CELLS[i_cell], seed=seed)
        lec = read_piece(_STATE["pieces"][variant], deg)
    finally:
        PL.apply = _APPLIQUER
    ref = _STATE["ref"]
    line = {"variant": variant, "shape": shape, "intensity": intensity,
             "cell": i_cell, "seed": seed,
             "added_ink": lec.field_ink.get(FIELD, {}).get("128")}
    for name, reg in SENSORS.items():
        cons = [c for c in evaluate({PIECE: lec}, ref, "filing", reg,
                                   checks=["required_field"]) if c.target == FIELD]
        if not cons:
            continue
        threshold = _STATE["ink_threshold"] if SEUILS[name] is None else SEUILS[name]
        line[name] = {"score": cons[0].score, "fires": cons[0].score > threshold,
                      "detail": cons[0].detail[:30]}
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--output", default=os.path.join(HERE, "results.jsonl"))
    a = ap.parse_args()
    _amorcer()
    conditions = [(None, 0.0)] + [(f, i) for f in SHAPES for i in INTENSITIES]
    tasks = [(v, f, i, c, g)
              for v in VARIANTS for (f, i) in conditions
              for c in range(len(CELLS)) for g in SEEDS]
    print(f"{len(tasks)} readings, {len(conditions)} conditions x {len(VARIANTS)} variantes "
          f"x {len(CELLS)} cells x {len(SEEDS)} graines")
    with open(a.output, "w", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, line in enumerate(pool.imap_unordered(task, tasks), 1):
            f.write(json.dumps(line) + "\n")
            if i % 60 == 0:
                print(f"  {i}/{len(tasks)}", flush=True)
    print(f"-> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
