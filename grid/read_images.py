#!/usr/bin/env python3
"""Readings of IMAGES (an independent generator's pages, real captures), in the grid's schema.

    python3 grid/read_images.py MANIFEST.csv OUT.jsonl [--identities DIR] [--workers N]

MANIFEST is a CSV with the columns
    image_path, source, identity, piece, variant, instance, seed, dpi, capture, mark_step, ts
(extra columns such as field_ink_share are carried through to the line). `source` is g1 (the
Augraphy pages of grid/augraphy_render.py), x2 (real captures) or naf. `dpi` is the row's
nominal dpi: the dpi the page is read at.

EACH IMAGE GOES THROUGH THE PRODUCTION READING PATH, the one `python -m preflight` runs on a
real dossier: a preflight.__main__.ScannedPiece handed to preflight.reading.read_piece() with
replace(PRISTINE, dpi=<row dpi>). No degradation is applied (PRISTINE is the identity), the
deskew, the orientation and registration search, the OCR and every sensor are the shipped ones.
Nothing in that path is changed here, including its known weak spot: preflight.deskew's
coarse-then-refine search can settle on the wrong quarter turn (it refines only the quarter that
wins the coarse round, and on a real archival page prepare() chose quarter turn 3 on an upright
page). The paper measures the tool as it is, so this script does not correct it; it RECORDS, on
every line, what the production path says about orientation and registration (the "orientation"
object below), so the analysis can count how often it happens.

ONE STEP IS NOT THE COMMAND LINE'S, AND IT IS THE INPUT ADAPTER. The command line takes a PDF and
rasterises it with pdftoppm (preflight.render.render). An image is already a raster. Wrapping it
in a PDF so that pdftoppm could rasterise it again was measured before this was written: poppler
resamples an embedded image even at exactly 1:1 (dpi of the page equal to the dpi of the
image), and changed 42% of the pixels of an A3 page (mean absolute difference 7 grey levels;
99% of the pixels of a random image). That would put a blur in front of the tool that no real
raster input goes through. So, in the worker processes only, preflight.reading.render is
replaced by a function that returns an image file exactly as render() returns its own cached
PNG (PIL open, convert("L"), numpy array) and delegates everything else (the blank templates,
which are PDFs) to the original. Every step after the raster is the production one.

THE LINE is grid/run.py's line (the key fields, "seconds", "reading": Reading.dict()), so
grid/analyze.py reads it with no special case, plus:
    source, jitter (false), capture, mark_step, instance, image_path, image_ts (the manifest's
    ts), every other manifest column (field_ink_share for g1), ts (UTC, when THIS reading was
    taken), and "orientation": quarter_turns, expected_quarter_turns, wrong_quarter_turn, peak,
    orientation_margin, angle, coverage, source_dpi.
angle, jpeg and sigma are PRISTINE's (0.0, 100, 0.0): the degradation this script applied,
which is none. parasite is 0.0: no ink is injected here, whatever ink an image carries is its
own.

expected_quarter_turns is what an upright reading of the row must report: 0, except for the
rotated_page variant, where G1 applied the variant's own quarter turn q before Augraphy (so the
reading must undo it: (4 - q) % 4, the value the published grid reads, 3 for q = 1) and a real
capture was turned by hand in a direction the manifest does not carry (None; then
wrong_quarter_turn means "reported upright").

Resumable: a row whose (source, identity, variant, piece, dpi, seed, capture, mark_step) is
already in OUT is skipped. A row that raises is reported with its traceback, written to
OUT.errors.jsonl, left out of OUT (so the next run retries it), and the exit code is 1.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
import traceback
from dataclasses import replace
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
from PIL import Image

import preflight.reading as production_reading
from preflight.__main__ import PRISTINE, ScannedPiece
from preflight.fixtures import BY_NAME, enumerate_variants
from preflight.reading import blank, read_piece
from preflight.reference import load_reference

DEFAULT_IDENTITIES = os.path.join(ROOT, "fixtures", "identities")
REQUIRED = ("image_path", "source", "identity", "piece", "variant", "instance", "seed", "dpi",
            "capture", "mark_step", "ts")
SOURCES = ("g1", "x2", "naf")
RASTER_SUFFIXES = (".png", ".tif", ".tiff", ".jpg", ".jpeg")

_REFS = None
_CATALOG = None
_PDF_RENDER = production_reading.render


def raster_render(path, dpi=None, page=1, cache=None):
    """The input adapter (module docstring): an image file comes back as render() returns its
    own cached raster; anything else (a PDF) goes to the original render()."""
    if str(path).lower().endswith(RASTER_SUFFIXES):
        return np.asarray(Image.open(path).convert("L"))
    if dpi is None:
        return _PDF_RENDER(path, page=page, cache=cache)
    return _PDF_RENDER(path, dpi=dpi, page=page, cache=cache)


def load_identities(identities_dir):
    refs = {}
    for name in sorted(os.listdir(identities_dir)):
        if name.endswith(".yaml"):
            r = load_reference(os.path.join(identities_dir, name))
            refs[r.identity] = r
    if not refs:
        raise SystemExit(f"no identity file (*.yaml) found in {identities_dir}")
    return refs


def catalog_of(refs):
    """{identity: {variant name: Variant}}: the legacy nine plus every enumerated instance."""
    return {i: {**BY_NAME, **{v.name: v for v in enumerate_variants(r)}} for i, r in refs.items()}


def _init(identities_dir):
    global _REFS, _CATALOG
    _REFS = load_identities(identities_dir)
    _CATALOG = catalog_of(_REFS)
    production_reading.render = raster_render
    for ref in _REFS.values():
        for _, name in ref.pieces:
            blank(ref.templates[name])


def _int_or_none(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


def _float_or_none(v):
    v = (v or "").strip()
    return float(v) if v else None


def _str_or_none(v):
    v = (v or "").strip()
    return v or None


def row_key(d):
    """The resume key, from a manifest row or from a written line (same field names)."""
    def norm(v, f):
        return f(v) if isinstance(v, str) else v
    return (d["source"], d["identity"], d["variant"], d["piece"],
            norm(d["dpi"], _int_or_none), norm(d["seed"], _int_or_none),
            norm(d.get("capture"), _str_or_none), norm(d.get("mark_step"), _int_or_none))


def expected_quarter_turns(variant, source):
    q = (variant.image or {}).get("quarter_turns", 0) if variant is not None else 0
    if not q:
        return 0
    return (4 - q) % 4 if source == "g1" else None


def orientation(reading, expected):
    wrong = (reading.quarter_turns != expected) if expected is not None \
        else reading.quarter_turns == 0
    return {"quarter_turns": reading.quarter_turns, "expected_quarter_turns": expected,
            "wrong_quarter_turn": bool(wrong), "peak": reading.peak,
            "orientation_margin": reading.orientation_margin, "angle": reading.angle,
            "coverage": reading.coverage, "source_dpi": reading.source_dpi}


def read_row(row):
    """One manifest row -> one grid line (or an error record)."""
    try:
        ref = _REFS[row["identity"]]
        template = ref.templates[dict(ref.pieces)[row["piece"]]]
        dpi = _int_or_none(row["dpi"])
        piece = ScannedPiece(row["piece"], template, os.path.abspath(row["image_path"]))
        t = time.perf_counter()
        reading = read_piece(piece, replace(PRISTINE, dpi=dpi))
        seconds = round(time.perf_counter() - t, 2)
        variant = _CATALOG[row["identity"]].get(row["variant"])
        line = {"angle": PRISTINE.angle, "dpi": dpi, "jpeg": PRISTINE.jpeg,
                "sigma": PRISTINE.sigma, "seed": _int_or_none(row["seed"]), "parasite": 0.0,
                "parasite_shape": None, "parasite_zone": None,
                "identity": row["identity"], "variant": row["variant"], "piece": row["piece"],
                "source": row["source"], "jitter": False,
                "capture": _str_or_none(row["capture"]),
                "mark_step": _int_or_none(row["mark_step"]),
                "instance": _str_or_none(row["instance"]),
                "image_path": row["image_path"], "image_ts": row["ts"]}
        for k, v in row.items():
            if k not in REQUIRED and k not in line:
                line[k] = _float_or_none(v) if k.endswith("_share") else _str_or_none(v)
        line["orientation"] = orientation(reading,
                                          expected_quarter_turns(variant, row["source"]))
        line["seconds"] = seconds
        line["ts"] = dt.datetime.now(dt.timezone.utc).isoformat()
        line["reading"] = reading.dict()
        return line
    except Exception as e:          # reported by the parent, never swallowed
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc(),
                "row": row, "ts": dt.datetime.now(dt.timezone.utc).isoformat()}


def load_manifest(path, refs):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or ())]
        if missing:
            raise SystemExit(f"{path}: missing column(s) {', '.join(missing)}")
        rows = list(reader)
    catalog = catalog_of(refs)
    seen, problems = {}, []
    for i, r in enumerate(rows, 2):
        if r["source"] not in SOURCES:
            problems.append(f"line {i}: source {r['source']!r} not in {SOURCES}")
        if r["identity"] not in refs:
            problems.append(f"line {i}: identity {r['identity']!r} has no reference file")
            continue
        if r["piece"] not in dict(refs[r["identity"]].pieces):
            problems.append(f"line {i}: piece {r['piece']!r} not declared by the reference")
        if r["variant"] != "clean" and r["variant"] not in catalog[r["identity"]]:
            problems.append(f"line {i}: unknown variant {r['variant']!r}")
        if not _int_or_none(r["dpi"]):
            problems.append(f"line {i}: no dpi")
        if not os.path.exists(r["image_path"]):
            problems.append(f"line {i}: image not found {r['image_path']}")
        k = row_key(r)
        if k in seen:
            problems.append(f"line {i}: same key as line {seen[k]} {k}")
        seen[k] = i
    if problems:
        raise SystemExit(f"{path}: {len(problems)} problem(s), nothing read:\n  "
                         + "\n  ".join(problems[:20]))
    return rows


def already_done(path):
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(row_key(json.loads(line)))
                except (ValueError, KeyError):
                    continue
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("manifest")
    ap.add_argument("output")
    ap.add_argument("--identities", default=DEFAULT_IDENTITIES,
                    help="directory of identity YAML files (default fixtures/identities)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--limit", type=int, default=0,
                    help="only read the first N rows still to do (a smoke test)")
    a = ap.parse_args(argv)
    identities = os.path.abspath(a.identities)

    refs = load_identities(identities)
    rows = load_manifest(a.manifest, refs)
    done = already_done(a.output)
    todo = [r for r in rows if row_key(r) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(rows)} manifest rows, {len(done)} already read, {len(todo)} to read, "
          f"{a.workers} workers", flush=True)
    if not todo:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.output)) or ".", exist_ok=True)
    for ref in refs.values():                    # the blanks' OCR cache, once, before any fork
        for _, name in ref.pieces:
            blank(ref.templates[name])

    t0 = time.perf_counter()
    n_ok = n_err = n_wrong = 0
    seconds = []
    errors_path = a.output + ".errors.jsonl"
    with open(a.output, "a", encoding="utf-8") as out, \
            Pool(a.workers, initializer=_init, initargs=(identities,)) as pool:
        for i, line in enumerate(pool.imap_unordered(read_row, todo), 1):
            if "error" in line:
                n_err += 1
                sys.stderr.write(f"ERROR {line['row']['image_path']}: {line['error']}\n"
                                 f"{line['traceback']}\n")
                with open(errors_path, "a", encoding="utf-8") as e:
                    e.write(json.dumps(line, ensure_ascii=False) + "\n")
                continue
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
            n_ok += 1
            n_wrong += line["orientation"]["wrong_quarter_turn"]
            seconds.append(line["seconds"])
            if i % 25 == 0 or i == len(todo):
                elapsed = time.perf_counter() - t0
                print(f"  {i}/{len(todo)} rows, {elapsed / 60:.1f} min elapsed, "
                      f"{elapsed / i * (len(todo) - i) / 60:.1f} min left", flush=True)
    wall = time.perf_counter() - t0
    print(f"finished: {n_ok} read, {n_err} error(s), {n_wrong} wrong quarter turn(s), "
          f"{wall:.1f} s wall, {wall / max(1, n_ok + n_err):.2f} s wall per image, "
          f"{(sum(seconds) / len(seconds)) if seconds else 0:.2f} worker-s per image "
          f"-> {a.output}", flush=True)
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
