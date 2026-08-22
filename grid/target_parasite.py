#!/usr/bin/env python3
"""Foreign ink laid ON the very field a check is meant to catch.

THIS EXISTS BECAUSE THE MAIN GRID ANSWERS A DIFFERENT QUESTION THAN THE ONE ASKED, and that was
found by reading its partial results, not by reading the plan. In the grid the parasite is drawn
among the zones a check watches, and the damaged target of a variant is one zone among several:
for required_field it is `employment / City or Town`, and over the 36 placements of the
experiment it is drawn exactly zero times. So the grid measures what foreign ink does to a check
in general, and it never once exercises the mechanism the probe found, which needs the ink to
land ON the emptied field so the ink sensor calls it filled.

For required_checkbox, signature and expiry the draw does hit the damaged target, so those three
are covered by the grid. required_field is not, and it is the headline question.

The design here is therefore deliberate and not random: the parasite goes exactly on the zone the
variant damaged. Both sides are read at each condition:

    recall           the variant's dossier: does the check still catch its own defect
    false positives  the clean dossier, same parasite, same place: does the check now cry

    27 cells (angle 0.5 x 3 dpi x 3 JPEG x 3 sigma) x 4 levels x 3 seeds x 5 variants x 2 sides

    python3 grid/target_parasite.py    # writes grid/results/target_parasite.json
"""
import collections
import itertools
import json
import os
import sys
import time
from dataclasses import replace
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from grid.analyze import damaged_targets, wilson
from grid.run import PARASITE_LEVELS, SEEDS
from preflight import parasite
from preflight.checks import CHECKS, Settings, evaluate, zones
from preflight.degradation import Degradation
from preflight.fixtures import VARIANTS, build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference
from preflight.thresholds import load_thresholds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "grid", ".fixtures")
CELLS = [(0.5, d, q, s) for d in (150, 200, 300) for q in (30, 75, 95) for s in (0.0, 6.0, 12.0)]

# The four text sensors of the required-field duel, each at its own operating point. The others
# are read at the published threshold of their check.
TEXT_SENSORS = {"ink": Settings(text_sensor="ink", ink_threshold=128),
                "union": Settings(text_sensor="union", min_conf=0.0),
                "page": Settings(text_sensor="page", min_conf=0.0),
                "zone": Settings(text_sensor="zone", min_conf=0.0)}

_STATE = {}


def _bootstrap():
    if _STATE:
        return
    ref = load_reference()
    _STATE["ref"] = ref
    _STATE["thresholds"] = load_thresholds()
    _STATE["pieces"] = {}
    for v in VARIANTS:
        d = build(ref, v.name, FIXTURES)
        for p in d.pieces:
            _STATE["pieces"][(v.name, p.id)] = p
    for _, name in ref.pieces:
        blank(ref.templates[name])


def targeted():
    """The variants whose damaged target is a zone the parasite can be laid on.

    forbidden_value is left out on purpose: its target is a VALUE read anywhere on the page, not
    a zone, so there is no "the field it damaged" to aim at and any placement would be arbitrary.
    """
    _bootstrap()
    ref = _STATE["ref"]
    out = []
    for v in VARIANTS:
        if not v.check or not v.piece or v.check == "forbidden_value":
            continue
        tpl = ref.templates[dict(ref.pieces)[v.piece]]
        declared = zones(tpl)
        names = sorted({t[1] for t in damaged_targets(v, ref) if t[1] in declared})
        if names:
            out.append((v, names[0]))
    return out


def task(job):
    cell, seed, level, variant_name, piece_id, zone_name, side = job
    _bootstrap()
    ref = _STATE["ref"]
    angle, dpi, jpeg, sigma = cell
    p = _STATE["pieces"][(variant_name if side == "variant" else "clean", piece_id)]
    deg = replace(Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed),
                  **p.image_override) if p.image_override else Degradation(
                      angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed)
    inject = None
    shape = None
    if level:
        shape = sorted(parasite.SHAPES)[seed % len(parasite.SHAPES)]
        z, f = zones(p.template)[zone_name], parasite.SHAPES[shape]

        def inject(grey, dpi_render, z=z, f=f, level=level, seed=seed):
            return f(grey.copy(), z, dpi_render, level, np.random.default_rng(seed))
    reading = read_piece(p, deg, parasite=inject)
    return {"cell": list(cell), "seed": seed, "parasite": level, "shape": shape,
            "variant": variant_name, "piece": piece_id, "zone": zone_name, "side": side,
            "reading": reading.dict()}


def main():
    _bootstrap()
    ref = _STATE["ref"]
    jobs = [(c, s, lv, v.name, v.piece, z, side)
            for v, z in targeted()
            for c in CELLS for s in SEEDS for lv in PARASITE_LEVELS
            for side in ("variant", "clean")]
    procs = max(1, (os.cpu_count() or 4) - 1)
    print(f"{len(jobs)} readings, {procs} workers")
    t0 = time.perf_counter()
    rows = []
    with Pool(procs) as pool:
        for i, row in enumerate(pool.imap_unordered(task, jobs), 1):
            rows.append(row)
            if i % 100 == 0:
                el = time.perf_counter() - t0
                print(f"  {i}/{len(jobs)}, {el/60:.1f} min, {el/i*(len(jobs)-i)/60:.1f} min left",
                      flush=True)
    print(f"finished in {(time.perf_counter()-t0)/60:.1f} min")

    out = {"what": "foreign ink laid ON the field the variant damaged",
           "cells": len(CELLS), "levels": list(PARASITE_LEVELS), "seeds": list(SEEDS),
           "checks": {}}
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        v = next(x for x in VARIANTS if x.name == r["variant"])
        by[v.check][(r["parasite"], r["side"])].append(r)
    for check, groups in by.items():
        sensors = TEXT_SENSORS if check == "required_field" else {"published": None}
        out["checks"][check] = {"zone": groups[list(groups)[0]][0]["zone"], "sensors": {}}
        for sname, settings in sensors.items():
            per_level = {}
            for (level, side), rs in sorted(groups.items()):
                hits = n = 0
                for r in rs:
                    from preflight.reading import Reading
                    findings = evaluate({r["piece"]: Reading.from_dict(r["reading"])}, ref,
                                        "filing", settings, checks=[check])
                    fired = any(c.fires for c in findings if str(c.target) == r["zone"]
                                or check in ("consistency",))
                    n += 1
                    hits += fired
                per_level.setdefault(level, {})[side] = {
                    "fired": hits, "n": n, "rate": hits / max(1, n),
                    "ci": list(wilson(hits, max(1, n)))}
            out["checks"][check]["sensors"][sname] = {str(k): v for k, v in sorted(per_level.items())}
    dest = os.path.join(ROOT, "grid", "results", "target_parasite.json")
    json.dump(out, open(dest, "w"), indent=2)
    for check, d in sorted(out["checks"].items()):
        print(f"\n{check}  (parasite on {d['zone']})")
        for sname, lv in d["sensors"].items():
            recalls = ", ".join(f"{k}:{v['variant']['rate']:.3f}" for k, v in lv.items())
            fps = ", ".join(f"{k}:{v['clean']['rate']:.3f}" for k, v in lv.items())
            print(f"   {sname:8s} recall {recalls}")
            print(f"   {'':8s} FP     {fps}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
