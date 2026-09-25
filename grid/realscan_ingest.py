#!/usr/bin/env python3
"""T14 "after G2" step 1 (perfect-recall-study/prereg/PREREG.md section 3, row X2): turn the
AirDropped captures in an incoming folder into a manifest grid/read_images.py (T09) can read.

Usage:
    python3 grid/realscan_ingest.py INCOMING_DIR CHECKLIST.csv OUT_MANIFEST.csv \
        [--identities DIR] [--rendered-dir DIR] [--phone-dpi 300]

PIPELINE, in this order (T14):
  1. every file in INCOMING_DIR is timestamped by its CAPTURE TIME, read BEFORE any metadata is
     stripped: a PDF's own /CreationDate (Apple Notes "Scan Documents" writes one), or a raster
     capture's EXIF DateTimeOriginal / DateTime, or the file's mtime when neither exists. Files
     are ordered by this timestamp: the order Dylan actually captured them in, which is also
     checklist.csv's own line order absent a mistake.
  2. every file is rendered to a PNG: a PDF page through pdftoppm at --phone-dpi (default 300,
     grid/realscan_kit.py's own convention for a phone capture: T09's read_images.py treats a
     raster's dpi as whatever the manifest declares and never re-measures it from the file, so
     this is a real claim about the delivered pixels, not a placeholder); a raster file is
     opened and re-saved as-is (Pillow drops metadata on a save with no exif= kwarg).
  3. EXIF and GPS are stripped from the rendered PNG and the strip is VERIFIED, not assumed:
     Image.open(path).getexif() must come back empty or the file is refused.
  4. the ordered files are paired against checklist.csv's own order by OCR of the printed sheet
     code (grid/realscan_kit.py stamps S01..S60 in a margin the tool never reads), with ONE
     off-by-one shift tried at the first disagreement (align_sequences() below): a single
     missing or duplicated capture, and nothing more elaborate, is the failure mode this
     recovers from. A disagreement no single shift explains is left unpaired.
  5. each paired capture's identity is cross-checked by OCR of its piece's own "name" field
     against the checklist row's declared identity: a capture whose sheet code paired cleanly
     but whose printed name does not match is exactly the failure a code-only pairing cannot
     see (two sheets swapped in the pile, both codes legible and both individually valid). A
     single adjacent swap (this capture's name matches the NEXT or PREVIOUS checklist row
     instead) is corrected; anything else is excluded.
  6. $AR/x2/manifest.csv is written in T09's schema: image_path, source (x2), identity, piece,
     variant, instance, seed (blank: no seed concept on a real capture), dpi, capture,
     mark_step, ts (the CAPTURE time, step 1, in ISO 8601 UTC), plus mark_ink_share for every
     mark-step row (step_mark_ink_share() below): measured against that SAME sheet's own step-0
     capture, never against the blank template, because a hand-made mark's share only means
     anything against what was already on the page before the mark went on it (real paper,
     ink, a filled or emptied field, capture noise: all already differ from the blank by far
     more than the mark does).

EVERY EXCLUDED CAPTURE IS COUNTED, NEVER SILENTLY DROPPED (PREREG.md section 3, X2 row:
"Captures excluded at ingest (identity mismatch) are counted and reported"): OUT_MANIFEST +
".excluded.jsonl" carries one line per exclusion, with its reason.

TESTS ARE ON SYNTHETIC CAPTURES ONLY (tests/test_realscan_ingest.py): a kit sheet rendered to a
raster, a fabricated EXIF block with GPS written onto it, a slight rotation applied. Never on a
real photograph: none exists yet, this script and its tests run before Dylan has answered G1.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
from PIL import Image
from pypdf import PdfReader

from preflight.deskew import prepare
from preflight.geometry import declared_zones
from preflight.reading import blank
from preflight.reference import load_reference
from preflight.sensors import ink_ratio, normalize, ocr_zone_words

DEFAULT_IDENTITIES = os.path.join(ROOT, "fixtures", "identities")
RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff")
INCOMING_SUFFIXES = (".pdf",) + RASTER_SUFFIXES
SHEET_CODE_RE = re.compile(r"S\s*(\d{2})")
DARK = 128          # the shipped required_field sensor's own ink level (thresholds.json)
MANIFEST_FIELDS = ["image_path", "source", "identity", "piece", "variant", "instance", "seed",
                   "dpi", "capture", "mark_step", "ts", "mark_ink_share"]


# ---------------------------------------------------------------------------------------------
# 1. Capture time, read before anything is stripped
# ---------------------------------------------------------------------------------------------

def _pdf_creation_time(path):
    try:
        meta = PdfReader(path).metadata or {}
    except Exception:
        return None
    raw = meta.get("/CreationDate") if hasattr(meta, "get") else None
    if not raw:
        return None
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", str(raw))
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    try:
        return dt.datetime(y, mo, d, h, mi, s, tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _exif_time(path):
    try:
        exif = Image.open(path).getexif()
    except Exception:
        return None
    for tag in (36867, 306):                                  # DateTimeOriginal, DateTime
        v = exif.get(tag)
        if v:
            return _parse_exif_dt(v)
    try:
        exif_ifd = exif.get_ifd(0x8769)                        # the Exif sub-IFD
    except Exception:
        exif_ifd = {}
    v = exif_ifd.get(36867)
    return _parse_exif_dt(v) if v else None


def _parse_exif_dt(v):
    try:
        return dt.datetime.strptime(str(v), "%Y:%m:%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def capture_time(path):
    """The moment Dylan took this capture, read BEFORE any metadata is stripped. A PDF's own
    /CreationDate first, then a raster's EXIF, then the file's mtime: the last resort, never the
    first choice, because a mtime reflects when AirDrop wrote the file, not when the camera
    fired."""
    ext = os.path.splitext(path)[1].lower()
    found = _pdf_creation_time(path) if ext == ".pdf" else _exif_time(path)
    return found or dt.datetime.fromtimestamp(os.path.getmtime(path), tz=dt.timezone.utc)


# ---------------------------------------------------------------------------------------------
# 2 and 3. Render to PNG, strip and verify EXIF/GPS
# ---------------------------------------------------------------------------------------------

def render_to_png(path, dest_dir, phone_dpi=300):
    """A clean PNG with no metadata: a PDF page through pdftoppm, a raster re-saved as-is. The
    save itself is what strips EXIF (Pillow writes none unless told to); strip_exif() below
    verifies it rather than trusting that."""
    os.makedirs(dest_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(dest_dir, base + ".png")
    if path.lower().endswith(".pdf"):
        with tempfile.TemporaryDirectory() as t:
            prefix = os.path.join(t, "p")
            subprocess.run(["pdftoppm", "-r", str(phone_dpi), "-gray", "-png",
                            "-f", "1", "-l", "1", path, prefix], check=True)
            produced = [f for f in sorted(os.listdir(t)) if f.endswith(".png")]
            if not produced:
                raise RuntimeError(f"pdftoppm produced nothing for {path}")
            Image.open(os.path.join(t, produced[0])).convert("L").save(dest)
    else:
        Image.open(path).convert("L").save(dest)
    return dest


def strip_exif(png_path):
    """Re-save with no exif payload and VERIFY: getexif() must come back empty, or refuse. Never
    assumed from the format alone (a PNG can carry an eXIf chunk too). A plain re-encode with no
    exif= keyword is enough (Pillow copies no metadata unless told to): render_to_png() already
    does this on the way in, and this is the explicit, separately verified step T14 asks for."""
    Image.open(png_path).convert("L").save(png_path)
    left = Image.open(png_path).getexif()
    if left:
        raise RuntimeError(f"{png_path}: EXIF survived stripping: {dict(left)}")


# ---------------------------------------------------------------------------------------------
# 4. Pairing by sheet code, one off-by-one shift tolerated
# ---------------------------------------------------------------------------------------------

def ocr_sheet_code(png_path):
    """The printed code (grid/realscan_kit.py's stamp), or None if it cannot be read."""
    img = Image.open(png_path).convert("L")
    w, h = img.size
    # Bottom-right corner, wider than grid/realscan_kit.py's exact stamp box (a real capture's
    # crop and rotation are never pixel-perfect) but starting BELOW every corpus template's own
    # printed footer (a revision line, "Page 1 of 4"): measured 2026-09-26, a crop that also
    # swept in that footer text turned it into stray "S"+digit noise once whitelisted down to
    # S0-9, and either a wrong token matched the regex or the two overlapping texts garbled
    # into nothing. grid/realscan_kit.py's own stamp_rect() keeps the stamp inside a band with
    # no pre-printed ink at all (STAMP_MARGIN_BOTTOM_PT=2, STAMP_HEIGHT_PT=12 out of a 792 pt
    # page, y fraction from the top about 0.982 to 0.997): this crop starts at 0.98, just above
    # that band.
    crop = img.crop((int(w * 0.80), int(h * 0.98), w, h))
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        crop.save(tmp)
        # psm 7 ("single text line") mis-reads the code whenever the generous crop's other
        # text (a form's own footer, a revision line) creeps in: measured 2026-09-26 on a real
        # kit sheet, psm 7 returned "9 0" where psm 11 ("sparse text", the same mode
        # preflight.sensors.ocr_words uses for a whole page) correctly separated the stamp from
        # the footer noise and returned "S01" on its own line.
        out = subprocess.run(
            ["tesseract", tmp, "stdout", "-l", "eng", "--psm", "11",
             "-c", "tessedit_char_whitelist=S0123456789"],
            capture_output=True, text=True).stdout
    finally:
        os.unlink(tmp)
    m = SHEET_CODE_RE.search(out.upper())
    return f"S{m.group(1)}" if m else None


def align_sequences(observed, expected, matches=None):
    """Pair `observed[i]` against `expected[j]` in order, tolerating AT MOST ONE shift (one
    extra observed item with no expected match, or one expected item with no observed match) at
    the first disagreement, and only when that ONE shift explains EVERY later position too.

    Returns (pairs, unmatched_observed, unmatched_expected). `pairs` is a list of
    (observed_index, expected_index). A disagreement no single shift explains falls back to
    position-by-position matching: only positions that already agree are paired.

    `matches(o, e)` defaults to equality; the sheet-code pairing (step 4) and the identity
    cross-check (step 5) both call this, the second with a substring predicate.
    """
    matches = matches or (lambda o, e: o == e)
    n, m = len(observed), len(expected)
    lim = min(n, m)
    first = next((k for k in range(lim) if not matches(observed[k], expected[k])), None)
    if first is None and n == m:
        return list(zip(range(n), range(m))), [], []
    first = first if first is not None else lim

    def shifted(obs_off, exp_off):
        pairs = [(k, k) for k in range(first)]
        oi = ei = first
        while oi + obs_off < n and ei + exp_off < m:
            if not matches(observed[oi + obs_off], expected[ei + exp_off]):
                return None
            pairs.append((oi + obs_off, ei + exp_off))
            oi += 1
            ei += 1
        if oi + obs_off != n or ei + exp_off != m:
            return None
        return pairs

    drop_observed = shifted(1, 0)     # one extra capture at `first`: skip it, re-align after
    drop_expected = shifted(0, 1)     # one missing capture at `first`: skip that checklist line
    if drop_observed is not None and drop_expected is None:
        return drop_observed, [first], []
    if drop_expected is not None and drop_observed is None:
        return drop_expected, [], [first]

    pairs, unmatched_observed, unmatched_expected = [], [], []
    for k in range(lim):
        if matches(observed[k], expected[k]):
            pairs.append((k, k))
        else:
            unmatched_observed.append(k)
            unmatched_expected.append(k)
    unmatched_observed += list(range(lim, n))
    unmatched_expected += list(range(lim, m))
    return pairs, unmatched_observed, unmatched_expected


# ---------------------------------------------------------------------------------------------
# 5. Identity cross-check by OCR of the piece's own name field
# ---------------------------------------------------------------------------------------------

def ocr_identity_name(png_path, template):
    """The normalised text read in the template's "name" field, registered against the
    canonical blank the way the production path reads any real capture. None if the template
    declares no "name" role."""
    field = template.fields.get("name")
    if field is None:
        return None
    field_ids = field if isinstance(field, list) else [field]
    grey = np.asarray(Image.open(png_path).convert("L"))
    blank_img, _, zones, _ = blank(template)
    prep = prepare(grey, blank_img)
    words = []
    for fid in field_ids:
        zone = zones.get(fid)
        if zone is None:
            continue
        words += ocr_zone_words(prep.frame.scan, prep.frame.zone(zone), template.language)
    return normalize(" ".join(w.text for w in words))


def _name_matches(observed, expected):
    if not observed or not expected:
        return False
    return expected in observed or observed in expected


def check_identity(rendered, checklist_rows, pairs, refs):
    """For each sheet-code-paired capture, does the printed name match the row's declared
    identity? A single ADJACENT swap (this capture's name fits the next or previous checklist
    row instead) is corrected in place; anything else is reported as a mismatch and excluded.
    Returns (corrected_pairs, identity_excluded)."""
    corrected, excluded = [], []
    for idx, (oi, ei) in enumerate(pairs):
        row = checklist_rows[ei]
        ref = refs[row.identity]
        template = ref.templates[dict(ref.pieces)[row.piece]]
        observed = ocr_identity_name(rendered[oi][1], template)
        expected = normalize(ref.person["name"])
        if _name_matches(observed, expected):
            corrected.append((oi, ei))
            continue
        fixed = False
        for neighbour in (idx - 1, idx + 1):
            if 0 <= neighbour < len(pairs):
                _, nei = pairs[neighbour]
                nrow = checklist_rows[nei]
                nref = refs[nrow.identity]
                if _name_matches(observed, normalize(nref.person["name"])):
                    corrected.append((oi, nei))
                    fixed = True
                    break
        if not fixed:
            excluded.append({"reason": "identity mismatch", "file": rendered[oi][0],
                             "expected_identity": row.identity, "observed_name": observed,
                             "checklist_line": row.line})
    return corrected, excluded


# ---------------------------------------------------------------------------------------------
# 6. mark_ink_share: a mark-step capture against its OWN step-0 capture
# ---------------------------------------------------------------------------------------------

def step_mark_ink_share(step_png, step0_png, template, field_ids):
    """Ink added in the target field, measured against the SAME sheet's own step-0 capture, not
    the blank template. Each photograph is registered to the CANONICAL blank independently (the
    same registration read_piece uses in production), so the two ink_ratio readings are
    comparable even though the two photographs are not pixel-aligned with each other: unlike
    T11's field_ink_share (grid/augraphy_render.py), which diffs two frames sharing one exact
    pixel grid by construction, two independent real photographs of the same sheet never do."""
    if not field_ids:
        return None
    zones = declared_zones(template.pdf, template.page)
    rects = [zones[f] for f in field_ids if f in zones]
    if not rects:
        return None
    blank_img, _, _, _ = blank(template)

    def share(png_path):
        grey = np.asarray(Image.open(png_path).convert("L"))
        prep = prepare(grey, blank_img)
        return sum(ink_ratio(prep.frame.scan, prep.frame.zone(z), DARK) for z in rects) \
            / len(rects)

    return round(max(0.0, share(step_png) - share(step0_png)) / 100.0, 5)


# ---------------------------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Row:
    line: int
    sheet_code: str
    identity: str
    piece: str
    variant: str
    instance: str
    mark_step: str
    device: str
    dpi: str
    capture_index: str


def _load_checklist(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = [Row(int(r["line"]), r["sheet_code"], r["identity"], r["piece"], r["variant"],
                    r["instance"], r["mark_step"], r["device"], r["dpi"], r["capture_index"])
                for r in csv.DictReader(f)]
    rows.sort(key=lambda r: r.line)
    return rows


def build_manifest(incoming_dir, checklist_csv, out_manifest, identities_dir=DEFAULT_IDENTITIES,
                   rendered_dir=None, phone_dpi=300):
    rendered_dir = rendered_dir or os.path.join(os.path.dirname(os.path.abspath(out_manifest)),
                                                "rendered")
    checklist_rows = _load_checklist(checklist_csv)
    needed = sorted({r.identity for r in checklist_rows})
    refs = {i: load_reference(os.path.join(identities_dir, f"{i}.yaml")) for i in needed}

    files = sorted(
        (os.path.join(incoming_dir, f) for f in os.listdir(incoming_dir)
         if os.path.splitext(f)[1].lower() in INCOMING_SUFFIXES),
        key=capture_time)

    rendered = []                      # (source_path, png_path, capture_ts)
    for f in files:
        ts = capture_time(f)
        png = render_to_png(f, rendered_dir, phone_dpi)
        strip_exif(png)
        rendered.append((f, png, ts))

    observed_codes = [ocr_sheet_code(png) for _, png, _ in rendered]
    expected_codes = [r.sheet_code for r in checklist_rows]
    pairs, unmatched_obs, unmatched_exp = align_sequences(observed_codes, expected_codes)

    excluded = []
    for oi in unmatched_obs:
        excluded.append({"reason": "sheet code did not pair", "file": rendered[oi][0],
                         "ocr_code": observed_codes[oi]})
    for ei in unmatched_exp:
        excluded.append({"reason": "checklist line has no capture",
                         "checklist_line": checklist_rows[ei].line,
                         "expected_code": expected_codes[ei]})

    pairs, identity_excluded = check_identity(rendered, checklist_rows, pairs, refs)
    excluded += identity_excluded

    # step-0 image, per (identity, piece, variant) mark sheet, for mark_ink_share.
    step0_png = {}
    for oi, ei in pairs:
        row = checklist_rows[ei]
        if row.mark_step == "0":
            step0_png[(row.identity, row.piece, row.variant)] = rendered[oi][1]

    manifest_rows = []
    for oi, ei in pairs:
        row = checklist_rows[ei]
        source_path, png_path, ts = rendered[oi]
        line = {"image_path": png_path, "source": "x2", "identity": row.identity,
                "piece": row.piece, "variant": row.variant, "instance": row.instance,
                "seed": "", "dpi": row.dpi, "capture": f"{row.device}-{row.capture_index}",
                "mark_step": row.mark_step, "ts": ts.isoformat(), "mark_ink_share": ""}
        if row.mark_step != "":
            key = (row.identity, row.piece, row.variant)
            s0 = step0_png.get(key)
            if s0 and s0 != png_path:
                ref = refs[row.identity]
                template = ref.templates[dict(ref.pieces)[row.piece]]
                # checklist.csv's own `instance` column already names the role the mark sits
                # on (grid/realscan_kit.py's capture_rows(): both mark sheets share the one the
                # first required_field instance empties), so the field ids come straight from
                # the template's own declaration, never re-derived from a Variant here.
                field_ids = template.field_ids(row.instance) if row.instance in \
                    template.fields else ()
                line["mark_ink_share"] = step_mark_ink_share(png_path, s0, template, field_ids)
        manifest_rows.append(line)

    os.makedirs(os.path.dirname(os.path.abspath(out_manifest)) or ".", exist_ok=True)
    with open(out_manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(manifest_rows)
    excl_path = out_manifest + ".excluded.jsonl"
    with open(excl_path, "w", encoding="utf-8") as f:
        for e in excluded:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
    return {"captures": len(rendered), "paired": len(manifest_rows), "excluded": len(excluded)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("incoming")
    ap.add_argument("checklist")
    ap.add_argument("output")
    ap.add_argument("--identities", default=DEFAULT_IDENTITIES)
    ap.add_argument("--rendered-dir", default=None)
    ap.add_argument("--phone-dpi", type=int, default=300)
    a = ap.parse_args(argv)
    summary = build_manifest(a.incoming, a.checklist, a.output, a.identities, a.rendered_dir,
                             a.phone_dpi)
    print(f"{summary['captures']} captures, {summary['paired']} paired, "
         f"{summary['excluded']} excluded -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
