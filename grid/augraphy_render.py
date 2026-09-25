#!/usr/bin/env python3
"""T11, arm A3: the independent generator (Augraphy 8.2.6 default pipeline, unmodified).

This script runs in the SEPARATE venv `.venv-augraphy`, never in the main `.venv`. Augraphy's
own dependency chain (opencv, scikit-image, scipy) is unrelated to dossier-preflight's checks,
so the modules this script imports from `preflight` are deliberately narrow: `fixtures`,
`reference`, `templates`, `render`, `degradation`, `deskew` and `geometry` only. None of those
import `preflight.sensors` or `preflight.checks`, so none of them need scipy through this
package (Augraphy pulls its own scipy in anyway; the constraint this script actually respects
is "no import of preflight.checks / preflight.sensors here", which would pull in the OCR and
scoring code this arm does not use).

WHAT THIS PRODUCES, per perfect-recall-study/prereg/PREREG.md section 3.3: for every identity
(fixtures/identities/id01.yaml..id06.yaml) x page (4 clean pieces + 45 single-defect instances,
preflight.fixtures.enumerate_variants) x dpi (150, 200, 300) x seed (11, 23, 37): one augmented
PNG, one manifest.csv row (the schema T09 will read: image_path, source, identity, piece,
variant, instance, seed, dpi, capture, mark_step, ts, field_ink_share; source is always "g1"
here), and one augmentations.jsonl line naming the augmentation classes that fired on that
image. 6 x 49 x 3 x 3 = 2,646 of each.

THE RENDER, before Augraphy ever sees the page:
  1. pdftoppm at the page's EFFECTIVE dpi: the outer dpi loop (150, 200, 300), unless this
     variant's own image override forces a different one (low_resolution forces 72, exactly as
     grid/run.py's `replace(base, **p.image_override)` overrides the cell's dpi for that one
     variant). The same disk-cached call as the production path: preflight.render.render().
  2. The variant's page-geometry override (crop for cropped_page, quarter_turns for
     rotated_page; nothing for every other variant) is applied through
     preflight.degradation.apply(), called with angle, sigma and jpeg neutral (0, 0, 100) and
     blur forced to 0 so the ONLY effect is the crop or the turn: A3 varies dpi and seed, not
     G0's angle/jpeg/noise/blur factors, and the low_resolution variant's effect is entirely
     the dpi override above. This is "the render before Augraphy", used both as the frame
     Augraphy augments and as the reference field_ink_share diffs against.
  3. random.seed(seed), numpy.random.seed(seed), cv2.setRNGSeed(seed), THEN
     augraphy.default_augraphy_pipeline() is constructed and called. Both the pipeline's own
     random structure and its per-call parameter draws come from this seeded state, so a seed
     reproduces the same pipeline as well as the same draws from it. The pipeline is
     UNMODIFIED: no augmentation is added, removed or reweighted.
  4. The pipeline's `augment()` return dict carries the final image under the "output" key, NOT
     "image" (that key is a copy of the INPUT, kept by the library for its own bookkeeping; the
     class result lives in data["post"][-1].result, exposed as out["output"] -- checked against
     augraphy 8.2.6's own augmentationpipeline.py before this script trusted it). Augraphy
     returns colour (paper tint, colour ink augmentations can produce a 3-channel array even
     from a greyscale input); this script converts back to a single 8-bit greyscale channel
     before saving, matching the greyscale convention every other image in this repo uses
     (preflight.render.render always returns a 2D uint8 array).

WHICH AUGMENTATIONS FIRED, for augmentations.jsonl: augraphy 8.2.6 exposes this itself in the
augment() return dict, under "log": parallel lists "augmentation_name" and
"augmentation_status". A pipeline step built from a OneOf or an AugmentationSequence (the
library's only two structural wrapper classes) logs the wrapper itself as fired, immediately
followed by a second entry per member it ran (OneOf: the one it picked; AugmentationSequence:
every member it declares, unconditionally); augmentations_fired() below keeps every fired name
except those two wrapper class names, which is exactly the set of augmentation CLASSES that
actually touched the page.

field_ink_share (H1, PREREG.md section 4.1): the share of the variant's TARGET field's pixels
dark at level 128 (the ink level the shipped required_field threshold itself uses) in the
augmented image and NOT dark at level 128 in the un-augmented render of the very same page
(step 2 above, before Augraphy), after registering the augmented image onto that un-augmented
render with dossier-preflight's OWN registration code: preflight.deskew.deskew() and
preflight.deskew.register(), called DIRECTLY rather than through the prepare() convenience
wrapper, and restricted to axis 0 and quarter turn 0. The two images being registered are the
SAME page before and after Augraphy, so no rotation or quarter turn between them is possible by
construction (Augraphy's default pipeline never introduces one); prepare()'s own default search
over both axes is built for a real, possibly-misoriented SCAN, and on a heavily textured
Augraphy output it can lock the wrong one, measured on the full A3 run: about 15 percent of the
rows that should carry a field_ink_share (every non-clean, non-page-geometry variant) came back
with the zone's mapped rectangle landing entirely off-frame (a negative or out-of-bounds
region), read as "not measured", because the coarse profile-variance axis picker occasionally
favours Augraphy's own texture over the page's actual text lines. Restricting both calls to the
one axis and one quarter turn that must be correct removes that failure mode: rerun with the
fix (--recompute-ink-share, which reuses the saved images and does not call Augraphy again),
269 of 1,782 rows moved from None to a value; a genuinely different residual, 149 rows, remained
None. Every one of 40 sampled residual rows shares one trait register() cannot correct for: the
AUGMENTED image is not just textured, it is a DIFFERENT SHAPE from its own pre-Augraphy
reference (the coarse-then-refine search only ever recovers a uniform scale plus a translation,
never an independent x and y scale), concentrated on seed 37 (128 of 149) and on 150 dpi (104 of
149): whichever augmentation the seed 37 draw includes that pads or reflows the canvas does so
enough, at the fewest available pixels, to defeat a similarity transform. None here is the
honest answer, not a bug to chase further: a wrong number from a registration forced onto a
page it cannot actually align would be worse than reporting the row as not measured, and RQ2's
own protocols already read a missing cell as excluded rather than as a synthetic zero.

prep.frame.zone(z) carries a zone declared in the pre-Augraphy render's own pixel coordinates
(preflight.geometry.declared_zones at the render's own dpi: the two images share that dpi and
that page-geometry override, since both come from the exact same pre-Augraphy array) into the
same aligned frame, and prep.frame.blank comes back as that render warped pixel-for-pixel onto
the augmented image's frame (prep.frame.scan). No extra resampling code is written here:
registering the pair IS what produces the pixel-aligned pair the diff needs.

The "target field" is the field or region the touched check actually reads: the emptied
role's field(s) for required_field (a role can span several field ids, e.g. the W-9's combed
tax_id: the union of their zones is the target, matching PREREG 3.2's "one instance, three
positive targets"); the unticked box's zone for required_checkbox; the one signature zone for
signature; the expiring date field's zone for expiry; the replaced field's zone for consistency
and for forbidden_value. It is null for a clean page and for the three page-geometry checks
(resolution, cropped_page, rotated_page), which judge the whole frame, not one field; those are
exactly the three variants whose render carries a crop or a quarter turn, so every
field_ink_share this script DOES compute is on a page with no such transform, and the
declared-zone coordinates line up with the pre-Augraphy render with no extra bookkeeping.

`instance` in the manifest is the same role this section names: the field/box/signature/date
role the check reads, taken directly from the Variant's own dataclass fields (empty_fields,
uncheck, replace, or the template's required_signatures / dates), never parsed out of the
variant name string. It is empty for "clean" and for the three page-geometry variants.

Usage:
    python3 grid/augraphy_render.py OUT_DIR
    python3 grid/augraphy_render.py OUT_DIR --pilot 6      # smoke test, a handful of images
    python3 grid/augraphy_render.py OUT_DIR --workers 4
Resumable: a (identity, variant, piece, dpi, seed) row already in OUT_DIR/manifest.csv is
skipped; re-running with the same OUT_DIR only produces what is missing.
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from preflight.degradation import Degradation, apply as degrade
from preflight.deskew import build_frame, deskew, register
from preflight.fixtures import CLEAN, build, enumerate_variants
from preflight.geometry import declared_zones
from preflight.reference import load_reference
from preflight.render import render

DEFAULT_IDENTITIES = os.path.join(ROOT, "fixtures", "identities")
DPIS = (150, 200, 300)
SEEDS = (11, 23, 37)
DARK = 128          # the shipped required_field sensor's own ink level

MANIFEST_FIELDS = ["image_path", "source", "identity", "piece", "variant", "instance",
                    "seed", "dpi", "capture", "mark_step", "ts", "field_ink_share"]


def _load_identities(identities_dir):
    refs = {}
    for name in sorted(os.listdir(identities_dir)):
        if not name.endswith(".yaml"):
            continue
        ref = load_reference(os.path.join(identities_dir, name))
        refs[ref.identity] = ref
    if not refs:
        raise ValueError(f"no identity file (*.yaml) found in {identities_dir}")
    return refs


def build_all_pieces(ref, dest):
    """{(variant_name, piece_id): BuiltPiece}, and {variant_name: Variant}, for one identity.

    Mirrors grid/run.py's _bootstrap(): every variant enumerate_variants() names (CLEAN
    included, under the name "clean") is built once, every piece it touches cached on disk
    under a name keyed by (identity, variant, piece), reused on every later run of this script
    for the same identity.
    """
    variants = enumerate_variants(ref)
    pieces, by_name = {}, {}
    for v in variants:
        by_name[v.name] = v
        d = build(ref, v, dest)
        for p in d.pieces:
            pieces[(v.name, p.id)] = p
    return pieces, by_name


def pages_to_render(ref):
    """The 49 (variant_name, piece_id) couples this identity's schema declares: 4 clean pieces
    plus every single-defect instance, exactly preflight.fixtures' own pieces_to_read() couples
    (grid/run.py), just derived here instead of imported (that function is keyed to the grid's
    global bootstrap state, which this script does not share)."""
    variants = enumerate_variants(ref)
    couples = [("clean", pid) for pid, _ in ref.pieces]
    couples += [(v.name, v.piece) for v in variants if v.check]
    return couples


def render_dpi_for(piece, cell_dpi):
    return piece.image_override.get("dpi", cell_dpi)


def page_transform(piece, dpi):
    """The render BEFORE Augraphy: pdftoppm at the effective dpi, then the variant's own
    page-geometry override (crop, quarter turns) and nothing else. Neutral on every field
    other than crop/quarter_turns: angle 0, sigma 0, blur 0, jpeg 100 are all no-ops in
    preflight.degradation.apply()."""
    raw = render(piece.pdf, dpi=dpi, page=piece.template.page)
    deg = Degradation(angle=0.0, dpi=dpi, jpeg=100, sigma=0.0, blur=0.0, seed=0,
                      quarter_turns=piece.image_override.get("quarter_turns", 0),
                      crop=piece.image_override.get("crop", 0.0))
    return degrade(raw, deg)


def target_role_and_fields(var, tpl):
    """(role, field_ids) the check for this variant reads, or (None, ()) when it reads the
    whole frame rather than one field (clean, resolution, cropped_page, rotated_page: the same
    three checks whose variant carries a page-geometry override)."""
    if var.check == "required_field":
        role = var.empty_fields[0]
        return role, tpl.field_ids(role)
    if var.check == "required_checkbox":
        role = var.uncheck[0]
        return role, (tpl.boxes[role],)
    if var.check == "signature":
        role = tpl.required_signatures[0]
        return role, (tpl.signatures[role],)
    if var.check == "expiry":
        role = next(r for r, k in tpl.dates.items() if k == "expiration")
        return role, tpl.field_ids(role)
    if var.check in ("consistency", "forbidden_value"):
        role = next(iter(var.replace))
        return role, tpl.field_ids(role)
    return None, ()


def field_ink_share(augmented, reference, pdf, page, dpi, field_ids):
    """Share of the target field's pixels dark (level 128) in `augmented` and not dark in
    `reference` (the un-augmented render of the same page), after registering `augmented` onto
    `reference` with dossier-preflight's own registration code, restricted to axis 0 and
    quarter turn 0 (see the module docstring: the two images share the same nominal orientation
    by construction, and letting the search consider a turn risks locking the wrong one on a
    heavily textured Augraphy output). None when there is no target field. See the module
    docstring for the full reasoning."""
    if not field_ids:
        return None
    zones = declared_zones(pdf, page=page, dpi=dpi)
    rects = [zones[f] for f in field_ids if f in zones]
    if not rects:
        return None
    _, _, straight = deskew(augmented, axes=(0,))
    reg = register(straight, reference, quarters=(0,))
    frame = build_frame(straight, reference, reg)
    scan, ref_in_frame = frame.scan, frame.blank
    mask = np.zeros(scan.shape, dtype=bool)
    for z in rects:
        mz = frame.zone(z)
        y0, y1 = max(0, mz.y0), min(scan.shape[0], mz.y1)
        x0, x1 = max(0, mz.x0), min(scan.shape[1], mz.x1)
        if y1 > y0 and x1 > x0:
            mask[y0:y1, x0:x1] = True
    area = int(mask.sum())
    if area == 0:
        return None
    added_dark = (scan < DARK) & (ref_in_frame >= DARK) & mask
    return round(float(added_dark.sum()) / area, 5)


# augraphy's own base/ package has exactly two STRUCTURAL wrapper classes, never an image
# effect on their own: OneOf (picks one member) and AugmentationSequence (runs every member in
# order). Checked directly against augraphy 8.2.6's augmentationpipeline.py: apply_phase() logs
# a fired wrapper's own name AND then, right after, every one of ITS members by name too (a
# OneOf logs the single member it picked; an AugmentationSequence logs its WHOLE declared list,
# which the library does unconditionally, not filtered to the members that individually chose
# to run). Keeping the wrapper name in the fired set would report "OneOf" or
# "AugmentationSequence" as if either were itself a visible effect on the page.
_WRAPPER_CLASSES = {"OneOf", "AugmentationSequence"}


def augmentations_fired(log):
    """The augmentation CLASS NAMES that actually ran, from augraphy's own augment() log:
    every name whose status is True, excluding the two structural wrapper classes (see
    _WRAPPER_CLASSES above)."""
    names = log.get("augmentation_name", []) if log else []
    status = log.get("augmentation_status", []) if log else []
    return sorted({n for n, s in zip(names, status) if s and n not in _WRAPPER_CLASSES})


def augment_one(grey, seed):
    """Seed random/numpy/cv2, build augraphy's UNMODIFIED default pipeline, run it, and return
    (greyscale uint8 image, list of augmentation class names that fired)."""
    import cv2
    from augraphy import default_augraphy_pipeline

    random.seed(seed)
    np.random.seed(seed)
    cv2.setRNGSeed(seed)
    pipeline = default_augraphy_pipeline()
    out = pipeline.augment(grey.copy())
    image = out["output"]
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.uint8), augmentations_fired(out.get("log"))


def already_done(manifest_path):
    done = set()
    if os.path.exists(manifest_path):
        with open(manifest_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["identity"], row["variant"], row["piece"],
                          int(row["dpi"]), int(row["seed"])))
    return done


# Per-worker cache, exactly grid/run.py's _bootstrap() idiom: a spawned Pool worker is a
# long-lived process that calls task() once per job it is handed, so a module-level global
# populated on the FIRST call and reused on every later one avoids re-parsing the identity
# YAML and re-touching all 184 (variant, piece) cache files on every one of the 2,646 rows.
# Building a Reference or a BuiltPiece is not itself expensive; what would be expensive is
# doing it 2,646 times instead of once per identity per worker.
_PIECES = {}    # identity -> {(variant_name, piece_id): BuiltPiece}
_BY_NAME = {}   # identity -> {variant_name: Variant}


def _bootstrap(identity, identities_dir, fixtures_cache):
    if identity in _PIECES:
        return
    ref = _load_identities(identities_dir)[identity]
    _PIECES[identity], _BY_NAME[identity] = build_all_pieces(ref, fixtures_cache)


def task(job):
    """One (identity, variant, piece, dpi, seed) row: render, augment, measure, save."""
    from PIL import Image

    (identity, identities_dir, fixtures_cache, img_dir, variant_name, piece_id, dpi,
     seed) = job
    _bootstrap(identity, identities_dir, fixtures_cache)
    piece = _PIECES[identity][(variant_name, piece_id)]
    var = CLEAN if variant_name == "clean" else _BY_NAME[identity][variant_name]

    render_dpi = render_dpi_for(piece, dpi)
    reference = page_transform(piece, render_dpi)
    augmented, fired = augment_one(reference, seed)

    role, field_ids = target_role_and_fields(var, piece.template)
    share = None
    if field_ids:
        share = field_ink_share(augmented, reference, piece.template.pdf,
                                piece.template.page, render_dpi, field_ids)

    safe_variant = variant_name.replace(os.sep, "_")
    out_dir = os.path.join(img_dir, identity, safe_variant)
    os.makedirs(out_dir, exist_ok=True)
    image_path = os.path.join(out_dir, f"{piece_id}_dpi{dpi}_seed{seed}.png")
    tmp = image_path + f".{os.getpid()}.tmp"
    Image.fromarray(augmented).save(tmp, format="PNG")
    os.replace(tmp, image_path)

    import datetime as dt
    ts = dt.datetime.now(dt.timezone.utc).isoformat()
    # "dpi" is the NOMINAL cell value (150, 200 or 300), never the effective render dpi a
    # variant's own image override may substitute (72 for low_resolution): the same convention
    # grid/run.py's own JSONL lines use for a page-defect variant's dpi field.
    row = {"image_path": image_path, "source": "g1", "identity": identity, "piece": piece_id,
          "variant": variant_name, "instance": role or "", "seed": seed, "dpi": dpi,
          "capture": "", "mark_step": "", "ts": ts,
          "field_ink_share": "" if share is None else share}
    aug_line = {"image_path": image_path, "identity": identity, "piece": piece_id,
               "variant": variant_name, "seed": seed, "dpi": dpi,
               "augmentations": fired, "ts": ts}
    return row, aug_line


def build_tasks(identities, identities_dir, fixtures_cache, img_dir, dpis, seeds):
    tasks = []
    for identity, ref in identities.items():
        for variant_name, piece_id in pages_to_render(ref):
            for dpi in dpis:
                for seed in seeds:
                    tasks.append((identity, identities_dir, fixtures_cache, img_dir,
                                  variant_name, piece_id, dpi, seed))
    return tasks


def _recompute_ink_task(job):
    """One manifest row: reload its saved augmented PNG (Augraphy is NOT re-run) and its cheap
    pre-Augraphy reference (a pdftoppm render plus the variant's own page-geometry override, no
    augmentation), and recompute field_ink_share with the axis-locked registration. Used by
    --recompute-ink-share to fix every row after the axis bug (see field_ink_share's docstring)
    without paying for the ~90-minute Augraphy pass again."""
    from PIL import Image

    identity, identities_dir, fixtures_cache, variant_name, piece_id, dpi, image_path = job
    _bootstrap(identity, identities_dir, fixtures_cache)
    piece = _PIECES[identity][(variant_name, piece_id)]
    var = CLEAN if variant_name == "clean" else _BY_NAME[identity][variant_name]
    render_dpi = render_dpi_for(piece, dpi)
    role, field_ids = target_role_and_fields(var, piece.template)
    if not field_ids:
        return image_path, role or "", None
    reference = page_transform(piece, render_dpi)
    augmented = np.asarray(Image.open(image_path).convert("L"))
    share = field_ink_share(augmented, reference, piece.template.pdf, piece.template.page,
                            render_dpi, field_ids)
    return image_path, role or "", share


def recompute_ink_shares(out_dir, identities_dir, workers):
    """Rewrite every field_ink_share in OUT_DIR/manifest.csv with the axis-locked
    registration, for every row whose check reads one field (every row target_role_and_fields
    gives a non-empty result for). Standardises the WHOLE file on the fixed method, including
    rows that already had a value under the old, occasionally-wrong-axis one: their images are
    unchanged, so re-scoring them costs little and removes any doubt about which method
    produced which number."""
    manifest_path = os.path.join(out_dir, "manifest.csv")
    fixtures_cache = os.path.join(out_dir, "fixtures_cache")
    rows = []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    jobs, indices = [], []
    for i, r in enumerate(rows):
        if r["variant"] == "clean":
            continue
        jobs.append((r["identity"], identities_dir, fixtures_cache, r["variant"], r["piece"],
                    int(r["dpi"]), r["image_path"]))
        indices.append(i)
    print(f"{len(rows)} rows, {len(jobs)} to (re)score, {workers} workers")
    t0 = time.perf_counter()
    with Pool(workers) as pool:
        for n, (idx, (image_path, role, share)) in enumerate(
                zip(indices, pool.imap(_recompute_ink_task, jobs)), 1):
            assert rows[idx]["image_path"] == image_path
            rows[idx]["instance"] = role
            rows[idx]["field_ink_share"] = "" if share is None else share
            if n % 200 == 0 or n == len(jobs):
                elapsed = time.perf_counter() - t0
                print(f"  {n}/{len(jobs)} rescored, {elapsed/60:.1f} min elapsed", flush=True)
    tmp = manifest_path + ".rescoring.tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, manifest_path)
    with_share = sum(1 for r in rows if r["field_ink_share"] != "")
    print(f"done: {with_share} of {len(rows)} rows carry a field_ink_share -> {manifest_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", help="e.g. $AR/a3")
    ap.add_argument("--identities", default=DEFAULT_IDENTITIES)
    ap.add_argument("--dpis", default=",".join(str(d) for d in DPIS))
    ap.add_argument("--seeds", default=",".join(str(s) for s in SEEDS))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    ap.add_argument("--pilot", type=int, default=0, help="only process the first N rows")
    ap.add_argument("--recompute-ink-share", action="store_true",
                    help="rewrite every field_ink_share in an existing manifest.csv with the "
                         "axis-locked registration (see field_ink_share docstring), reusing "
                         "the already-saved images; does not call Augraphy again")
    a = ap.parse_args()

    if a.recompute_ink_share:
        return recompute_ink_shares(a.out_dir, a.identities, a.workers)

    dpis = tuple(int(x) for x in a.dpis.split(","))
    seeds = tuple(int(x) for x in a.seeds.split(","))
    img_dir = os.path.join(a.out_dir, "img")
    fixtures_cache = os.path.join(a.out_dir, "fixtures_cache")
    manifest_path = os.path.join(a.out_dir, "manifest.csv")
    aug_path = os.path.join(a.out_dir, "augmentations.jsonl")
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(fixtures_cache, exist_ok=True)

    identities = _load_identities(a.identities)
    tasks = build_tasks(identities, a.identities, fixtures_cache, img_dir, dpis, seeds)
    total = len(tasks)
    done = already_done(manifest_path)
    remaining = [t for t in tasks
                if (t[0], t[4], t[5], t[6], t[7]) not in done]
    if a.pilot:
        remaining = remaining[:a.pilot]
    print(f"{total} rows declared, {len(done)} already done, {len(remaining)} to run, "
         f"{a.workers} workers")
    if not remaining:
        return 0

    manifest_exists = os.path.exists(manifest_path)
    t0 = time.perf_counter()
    with open(manifest_path, "a", newline="", encoding="utf-8") as mf, \
        open(aug_path, "a", encoding="utf-8") as af, \
        Pool(a.workers) as pool:
        writer = csv.DictWriter(mf, fieldnames=MANIFEST_FIELDS)
        if not manifest_exists:
            writer.writeheader()
        for i, (row, aug_line) in enumerate(pool.imap_unordered(task, remaining), 1):
            writer.writerow(row)
            mf.flush()
            af.write(json.dumps(aug_line, ensure_ascii=False) + "\n")
            af.flush()
            if i % 25 == 0 or i == len(remaining):
                elapsed = time.perf_counter() - t0
                left = elapsed / i * (len(remaining) - i)
                print(f"  {i}/{len(remaining)} rows, {elapsed/60:.1f} min elapsed, "
                     f"{left/60:.1f} min left", flush=True)
    print(f"finished in {(time.perf_counter() - t0)/60:.1f} min -> {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
