#!/usr/bin/env python3
"""The degradation grid. It produces the MEASUREMENTS, it decides nothing.

    angle (0, 0.25, 0.5, 1, 2, 4 deg)  x  dpi (96, 150, 200, 300)
      x  JPEG quality (30, 55, 75, 95)  x  noise sigma (0, 3, 6, 12)   x  N seeds

That is 384 cells. For every cell and every seed it reads the CLEAN dossier (three pieces) and
the nine single-defect variants (one edited piece each): twelve readings, one JSONL line per
reading. Nothing is compared to a threshold here, and that is deliberate: the analysis then
sweeps thousands of operating points over those measurements without touching a single image.

    python3 grid/run.py               # full grid, resumes where it stopped
    python3 grid/run.py --pilot 8     # 8 cells, to check the cost before running everything
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
    """The twelve (variant, piece) pairs to read per cell and per seed.

    A variant only touches ONE piece: the other two are identical to the clean dossier's and
    their reading is reused as is by the analysis. Without that saving the grid would cost
    thirty readings per cell instead of twelve.
    """
    _bootstrap()
    couples = [("clean", p) for p, _ in _REF.pieces]
    couples += [(v.name, v.piece) for v in VARIANTS if v.check]
    return couples


def task(job):
    cell, seed = job
    angle, dpi, jpeg, sigma = cell
    _bootstrap()
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed)
    lines = []
    for variant_name, piece_id in pieces_to_read():
        p = _PIECES[(variant_name, piece_id)]
        deg = replace(base, **p.image_override) if p.image_override else base
        t = time.perf_counter()
        reading = read_piece(p, deg)
        lines.append({"angle": angle, "dpi": dpi, "jpeg": jpeg, "sigma": sigma,
                      "seed": seed, "variant": variant_name, "piece": piece_id,
                      "seconds": round(time.perf_counter() - t, 2), "reading": reading.dict()})
    return lines


def key(line):
    return (line["angle"], line["dpi"], line["jpeg"], line["sigma"], line["seed"], line["variant"], line["piece"])


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
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    cells = list(itertools.product(ANGLES, DPIS, JPEGS, SIGMAS))
    if a.pilot:
        step = max(1, len(cells) // a.pilot)
        cells = cells[::step][:a.pilot]
    tasks = [(c, g) for c in cells for g in SEEDS]

    _bootstrap()          # fixtures are built ONCE, before any fork
    done = already_done(a.output)
    expected = len(pieces_to_read())
    remaining = [t for t in tasks
                 if sum(1 for f in done if f[:5] == (t[0][0], t[0][1], t[0][2], t[0][3], t[1]))
                 < expected]
    print(f"{len(cells)} cells x {len(SEEDS)} seeds x {expected} readings "
          f"= {len(tasks) * expected} readings")
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
