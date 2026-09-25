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
from preflight.fixtures import VARIANTS, build, enumerate_variants
from preflight.reading import read_piece, blank
from preflight.reference import load_reference

ANGLES = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)
DPIS = (96, 150, 200, 300)
JPEGS = (30, 55, 75, 95)
SIGMAS = (0.0, 3.0, 6.0, 12.0)
SEEDS = (11, 23, 37)

# The single default identity's name, fixtures/reference.yaml's own (preflight.reference
# derives it from the file's stem). Readings produced with no --identities carry this value, so
# an old measurements.jsonl line with no "identity" field (A0, written before this existed)
# reads back as exactly this same constant everywhere it is defaulted.
DEFAULT_IDENTITY = "reference"

# T08's reduced cell set (plan section 2.1), ALREADY CUT to the 30,000-reading cap declared in
# perfect-recall-study/prereg/PREREG.md section 3.3: JPEG 55 dropped first, sigma 6 kept. Not
# the default: the default grid keeps running the full ANGLES x DPIS x JPEGS x SIGMAS cross
# unless --cells R is passed.
CELL_SETS = {
    "R": ((0.0, 0.5, 2.0), (150, 200, 300), (95,), (0.0, 6.0)),
}

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

_REFS = None            # {identity: Reference}
_PIECES = None          # {(identity, variant_name, piece_id): BuiltPiece}
_VARIANTS = None        # {identity: tuple[Variant, ...]}


def _load_identities(identities_dir):
    """{identity: Reference}. With no directory, the single default reference, DEFAULT_IDENTITY.

    load_reference() derives an identity from the file name, so id01.yaml through id06.yaml
    produce "id01" through "id06" with no further bookkeeping here.
    """
    if identities_dir is None:
        ref = load_reference()
        return {ref.identity: ref}
    refs = {}
    for name in sorted(os.listdir(identities_dir)):
        if not name.endswith(".yaml"):
            continue
        ref = load_reference(os.path.join(identities_dir, name))
        refs[ref.identity] = ref
    if not refs:
        raise ValueError(f"no identity file (*.yaml) found in {identities_dir}")
    return refs


def _bootstrap(identities_dir=None):
    """Every worker builds its fixtures once and warms up the blanks, for every identity.

    identities_dir travels inside every job (see task()), not through a bare module global:
    multiprocessing on this machine spawns workers rather than forking them, and a spawned
    worker re-imports this module from scratch, so a value only ASSIGNED at run time in the
    parent (as opposed to passed as an argument) never reaches it.

    With no --identities, this is exactly v0.1.0's bootstrap: one reference, VARIANTS (nine
    single-defect instances), the same fixture cache the published grid used. With
    --identities, every identity gets the EXHAUSTIVE enumeration of enumerate_variants().
    """
    global _REFS, _PIECES, _VARIANTS
    if _REFS is not None:
        return
    _REFS = _load_identities(identities_dir)
    _VARIANTS = ({DEFAULT_IDENTITY: VARIANTS} if identities_dir is None
                 else {identity: enumerate_variants(ref) for identity, ref in _REFS.items()})
    _PIECES = {}
    for identity, ref in _REFS.items():
        for v in _VARIANTS[identity]:
            d = build(ref, v, FIXTURES)
            for p in d.pieces:
                _PIECES[(identity, v.name, p.id)] = p
        for _, name in ref.pieces:
            blank(ref.templates[name])


def pieces_to_read(identity):
    """The (variant, piece) pairs to read per cell, per seed, for ONE identity.

    Thirteen for the default identity (v0.1.0's nine variants, a variant only touching one
    piece so the other three are the clean dossier's and reused). Forty-nine under
    --identities: four clean pieces plus the 45 defect instances enumerate_variants() derives
    for this identity's schema (perfect-recall-study prereg/PREREG.md section 3.2).
    """
    _bootstrap()
    ref = _REFS[identity]
    variants = _VARIANTS[identity]
    couples = [("clean", p) for p, _ in ref.pieces]
    couples += [(v.name, v.piece) for v in variants if v.check]
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
    """`job` may carry the exact (variant, piece) couples to read; None means every one of them.

    That is what makes --backfill worth having: producing one missing reading must not cost the
    others that sit next to it in the same task.

    identities_dir rides inside the job (see _bootstrap's docstring for why): a spawned worker
    has no other way to learn it.
    """
    cell, seed, level, identity, identities_dir, couples = job
    angle, dpi, jpeg, sigma = cell
    _bootstrap(identities_dir)
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed)
    lines = []
    for variant_name, piece_id in (couples if couples is not None else pieces_to_read(identity)):
        p = _PIECES[(identity, variant_name, piece_id)]
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
                      "parasite_zone": zone_name, "identity": identity,
                      "variant": variant_name, "piece": piece_id,
                      "seconds": round(time.perf_counter() - t, 2), "reading": reading.dict()})
    return lines


def key(line):
    # identity appended LAST, seed at index 4 and parasite at index 5 unchanged: an old line
    # with no "identity" field (every line of A0) reads back as DEFAULT_IDENTITY, the same
    # constant on every such line, so grouping by this key is unaffected for old data.
    return (line["angle"], line["dpi"], line["jpeg"], line["sigma"], line["seed"],
            line.get("parasite", 0.0), line.get("identity", DEFAULT_IDENTITY),
            line["variant"], line["piece"])


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
    ap.add_argument("--identities", default=None,
                    help="directory of identity YAML files (fixtures/make_identities.py's "
                         "output). Default: the single fixtures/reference.yaml, exactly as "
                         "v0.1.0 ran, so the published grid keeps replaying with no flags.")
    ap.add_argument("--cells", choices=sorted(CELL_SETS), default=None,
                    help="a named reduced cell set (perfect-recall-study prereg/PREREG.md "
                         "section 3.3) instead of the full ANGLES x DPIS x JPEGS x SIGMAS cross")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    if a.parasite:
        cells = list(itertools.product(SUB_ANGLES, SUB_DPIS, SUB_JPEGS, SUB_SIGMAS))
        levels = [x for x in PARASITE_LEVELS if x]
    elif a.cells:
        cells = list(itertools.product(*CELL_SETS[a.cells]))
        levels = [0.0]
    else:
        cells = list(itertools.product(ANGLES, DPIS, JPEGS, SIGMAS))
        levels = [0.0]
    if a.pilot:
        step = max(1, len(cells) // a.pilot)
        cells = cells[::step][:a.pilot]

    _bootstrap(a.identities)          # fixtures are built ONCE, before any fork
    identities = sorted(_REFS)
    tasks = [(c, g, l, identity, a.identities, None)
             for c in cells for g in SEEDS for l in levels for identity in identities]

    done = already_done(a.output)
    expected_by_identity = {identity: len(pieces_to_read(identity)) for identity in identities}
    # BACKFILL exists because adding a fourth piece to the dossier made every task of the
    # existing 13,824-reading file one reading short. Re-running those tasks whole would have
    # cost two hours to reproduce readings that are already there and deterministic; the missing
    # piece alone costs ten minutes. The rest of the file is reused untouched.
    if a.backfill:
        want = {(c[0], c[1], c[2], c[3], g, l, identity, v, p)
                for c in cells for g in SEEDS for l in levels
                for identity in identities for v, p in pieces_to_read(identity)}
        missing = want - done
        by_task = collections.defaultdict(list)
        for k in missing:
            by_task[(k[:4], k[4], k[5], k[6])].append((k[7], k[8]))
        remaining = [(c, g, l, identity, a.identities, tuple(sorted(v)))
                     for (c, g, l, identity), v in sorted(by_task.items())]
        print(f"backfill: {len(missing)} readings missing over {len(want)}, "
              f"{len(remaining)} tasks touched")
    else:
        remaining = [t for t in tasks
                     if sum(1 for f in done
                            if f[:4] == t[0] and f[4] == t[1] and f[5] == t[2] and f[6] == t[3])
                     < expected_by_identity[t[3]]]
        total = len(cells) * len(SEEDS) * len(levels) * sum(expected_by_identity.values())
        print(f"{len(cells)} cells x {len(SEEDS)} seeds x {len(levels)} parasite level(s) x "
              f"{len(identities)} identit{'y' if len(identities) == 1 else 'ies'} = "
              f"{total} readings")
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
