#!/usr/bin/env python3
"""The degradation grid. It produces the MEASUREMENTS, it decides nothing.

    angle (0, 0.25, 0.5, 1, 2, 4 deg)  x  dpi (96, 150, 200, 300)
      x  JPEG quality (30, 55, 75, 95)  x  noise sigma (0, 3, 6, 12)   x  N seeds

That is 384 cells. For every cell and every seed it reads the CLEAN dossier (four pieces) and
the nine single-defect variants (one edited piece each): thirteen readings, one JSONL line per
reading. Nothing is compared to a threshold here, and that is deliberate: the analysis then
sweeps thousands of operating points over those measurements without touching a single image.

    python3 grid/run.py               # full grid, resumes where it stopped
    python3 grid/run.py --pilot 8     # 8 cells, to check the cost before running everything
"""
import argparse
import collections
import hashlib
import itertools
import json
import os
import sys
import time
from dataclasses import replace
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from preflight import parasite
from preflight.checks import zones
from preflight.degradation import Degradation
from preflight.fixtures import VARIANTS, build
from preflight.reading import read_piece, blank
from preflight.reference import load_reference

ANGLES = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
DPIS = (96, 150, 200, 300)
JPEGS = (30, 55, 75, 95)
SIGMAS = (0.0, 3.0, 6.0, 12.0)
SEEDS = (11, 23, 37)

# THE FIFTH FACTOR: foreign ink. The four factors above move, blur or dirty the ink already on
# the page; none of them ADDS any. That is the ground the ink sensor won its duel on, and a
# 528-reading probe measured what it was hiding: past 0.5% added ink in a zone, that sensor
# calls an empty field filled in 1.000 of cases. Levels straddle the cliff the probe found at
# 0.345% added ink, so the sweep sees below it, across it and well past it.
PARASITE_LEVELS = (0.0, 0.002, 0.01, 0.04)

# The fractional sub-grid crossed fully with the new factor. The four old factors are already
# established by the full grid; the unknown is the parasite dose, so they are thinned and it is
# not. Full crossing would have cost 14,976 readings per level, over four hours.
SUB_ANGLES = (0.0, 0.5, 2.0, 4.0)
SUB_DPIS = (150, 200, 300)
SUB_JPEGS = (30, 75, 95)
SUB_SIGMAS = (0.0, 6.0, 12.0)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "grid", "measurements")
FIXTURES = os.path.join(ROOT, "grid", ".fixtures")

_REF = None
_PIECES = None


def _bootstrap():
    """Every worker builds its fixtures once and warms up the blanks."""
    global _REF, _PIECES
    if _REF is not None:
        return
    _REF = load_reference()
    _PIECES = {}
    for v in VARIANTS:
        d = build(_REF, v.name, FIXTURES)
        for p in d.pieces:
            _PIECES[(v.name, p.id)] = p
    for _, name in _REF.pieces:
        blank(_REF.templates[name])


def pieces_to_read():
    """The thirteen (variant, piece) pairs to read per cell and per seed.

    A variant only touches ONE piece: the other three are identical to the clean dossier's and
    their reading is reused as is by the analysis. Without that saving the grid would cost
    forty readings per cell instead of thirteen.
    """
    _bootstrap()
    couples = [("clean", p) for p, _ in _REF.pieces]
    couples += [(v.name, v.piece) for v in VARIANTS if v.check]
    return couples


def watched_zones(template):
    """The zones a check actually looks at, grouped by check. Everything else measures nothing.

    THIS GROUPING IS THE WHOLE REASON THE PILOT WAS RUN. Drawing the parasite uniformly among
    the DECLARED zones looked reasonable and was not: a form declares far more zones than any
    check reads (the I-9 declares dozens), so 26 placements out of 36 landed where nothing is
    measured, zero landed on a signature and zero on an expiry date. Two hours of compute would
    have answered nothing about the signature duel, which is one of the reasons for running this
    at all.
    """
    out = {}
    for role in template.required:
        out.setdefault("required_field", []).extend(template.field_ids(role))
    for role in template.required_boxes:
        out.setdefault("required_checkbox", []).append(template.boxes[role])
    for role in template.required_signatures:
        out.setdefault("signature", []).append(template.signatures[role])
    for role, kind in template.dates.items():
        if kind == "expiration":
            out.setdefault("expiry", []).extend(template.field_ids(role))
    declared = zones(template)
    return {k: sorted(z for z in v if z in declared) for k, v in out.items() if v}


def _draw(seed, level, piece_id, template):
    """Which shape lands where, drawn deterministically and STRATIFIED BY CHECK.

    Placement stays random rather than fixed on one target, because that is how dust behaves and
    because it must exercise every check and not only the one the probe looked at. But it is
    drawn among the zones a check WATCHES, and the check family is rotated so each family a piece
    carries gets a comparable share. Uniform over declared zones wasted three quarters of the
    compute; see watched_zones().

    The placement does NOT depend on the cell, and that is deliberate: it makes the parasite a
    proper factor. If it moved with angle or dpi, a cell's recall could differ because of where
    the speck landed rather than because of the cell, and the four old factors would stop being
    comparable across levels.

    The draw goes through sha1 and not hash(): hash() is salted per process, so the same cell
    would have carried a different parasite from one run to the next and nothing would replay.
    """
    key = f"{seed}|{level}|{piece_id}".encode()
    rng = np.random.default_rng(int(hashlib.sha1(key).hexdigest()[:12], 16))
    shape = sorted(parasite.SHAPES)[int(rng.integers(len(parasite.SHAPES)))]
    watched = watched_zones(template)
    families = sorted(watched)
    # Rotate the family on the draw index rather than drawing it, so the rare families (one
    # signature, one expiry date) are guaranteed their share instead of depending on luck.
    # The index counts the levels ACTUALLY USED, not PARASITE_LEVELS: including the zero level
    # in the stride made the rotation step by 4 over a 4-family piece, so index 0 never came up
    # and the expiry date was never touched. Caught by re-running the coverage check, not by
    # reading the code.
    used = [x for x in PARASITE_LEVELS if x]
    idx = SEEDS.index(seed) * len(used) + used.index(level)
    family = families[idx % len(families)]
    candidates = watched[family]
    return shape, candidates[int(rng.integers(len(candidates)))]


def task(job):
    """`job` may carry the exact (variant, piece) couples to read; None means all thirteen.

    That is what makes --backfill worth having: producing one missing reading must not cost the
    thirteen that sit next to it in the same task.
    """
    cell, seed, level, couples = job
    angle, dpi, jpeg, sigma = cell
    _bootstrap()
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed)
    lines = []
    for variant_name, piece_id in (couples if couples is not None else pieces_to_read()):
        p = _PIECES[(variant_name, piece_id)]
        deg = replace(base, **p.image_override) if p.image_override else base
        shape = zone_name = None
        inject = None
        if level:
            shape, zone_name = _draw(seed, level, piece_id, p.template)
            z, f = zones(p.template)[zone_name], parasite.SHAPES[shape]
            # The rng of the injection itself is seeded on the cell too, so two cells do not
            # place the very same speck at the very same pixel.
            def inject(grey, dpi_render, z=z, f=f, seed=seed):
                return f(grey.copy(), z, dpi_render, level, np.random.default_rng(seed))
        t = time.perf_counter()
        reading = read_piece(p, deg, parasite=inject)
        lines.append({"angle": angle, "dpi": dpi, "jpeg": jpeg, "sigma": sigma,
                      "seed": seed, "parasite": level, "parasite_shape": shape,
                      "parasite_zone": zone_name,
                      "variant": variant_name, "piece": piece_id,
                      "seconds": round(time.perf_counter() - t, 2), "reading": reading.dict()})
    return lines


def key(line):
    return (line["angle"], line["dpi"], line["jpeg"], line["sigma"], line["seed"],
            line.get("parasite", 0.0), line["variant"], line["piece"])


def already_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(key(json.loads(line)))
                except (ValueError, KeyError):
                    continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0, help="only process N cells")
    ap.add_argument("--procs", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--output", default=os.path.join(OUTPUT, "measurements.jsonl"))
    ap.add_argument("--parasite", action="store_true",
                    help="the fifth factor: the fractional sub-grid crossed with the parasite "
                         "levels, appended to the same file")
    ap.add_argument("--backfill", action="store_true",
                    help="only produce the readings missing from the output file, without "
                         "re-running the tasks it already holds")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    if a.parasite:
        cells = list(itertools.product(SUB_ANGLES, SUB_DPIS, SUB_JPEGS, SUB_SIGMAS))
        levels = [x for x in PARASITE_LEVELS if x]
    else:
        cells = list(itertools.product(ANGLES, DPIS, JPEGS, SIGMAS))
        levels = [0.0]
    if a.pilot:
        step = max(1, len(cells) // a.pilot)
        cells = cells[::step][:a.pilot]
    tasks = [(c, g, l, None) for c in cells for g in SEEDS for l in levels]

    _bootstrap()          # fixtures are built ONCE, before any fork
    done = already_done(a.output)
    expected = len(pieces_to_read())
    # BACKFILL exists because adding a fourth piece to the dossier made every task of the
    # existing 13,824-reading file one reading short. Re-running those tasks whole would have
    # cost two hours to reproduce readings that are already there and deterministic; the missing
    # piece alone costs ten minutes. The rest of the file is reused untouched.
    if a.backfill:
        want = {(c[0], c[1], c[2], c[3], g, l, v, p)
                for c in cells for g in SEEDS for l in levels
                for v, p in pieces_to_read()}
        missing = want - done
        by_task = collections.defaultdict(list)
        for k in missing:
            by_task[(k[:4], k[4], k[5])].append((k[6], k[7]))
        remaining = [(c, g, l, tuple(sorted(v))) for (c, g, l), v in sorted(by_task.items())]
        print(f"backfill: {len(missing)} readings missing over {len(want)}, "
              f"{len(remaining)} tasks touched")
    else:
        remaining = [t for t in tasks
                     if sum(1 for f in done
                            if f[:6] == (t[0][0], t[0][1], t[0][2], t[0][3], t[1], t[2]))
                     < expected]
        print(f"{len(cells)} cells x {len(SEEDS)} seeds x {len(levels)} parasite level(s) x "
              f"{expected} readings = {len(tasks) * expected} readings")
    print(f"{len(done)} already done, {len(remaining)} tasks left, {a.procs} workers")
    if not remaining:
        return 0

    t0 = time.perf_counter()
    with open(a.output, "a", encoding="utf-8") as f, Pool(a.procs) as pool:
        for i, lines in enumerate(pool.imap_unordered(task, remaining), 1):
            for l in lines:
                f.write(json.dumps(l, ensure_ascii=False) + "\n")
            f.flush()
            if i % 10 == 0 or i == len(remaining):
                elapsed = time.perf_counter() - t0
                left = elapsed / i * (len(remaining) - i)
                print(f"  {i}/{len(remaining)} tasks, {elapsed/60:.1f} min elapsed, "
                      f"{left/60:.1f} min left", flush=True)
    print(f"finished in {(time.perf_counter() - t0)/60:.1f} min -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
