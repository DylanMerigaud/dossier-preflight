"""Six fictional identities, the exhaustive per-instance enumeration, and the plumbing that
carries an identity through the grid's key.

perfect-recall-study/prereg/PREREG.md (tag prereg-v1, section 3.2) declares the arithmetic this
repo must reproduce: 45 defect instances per identity, 9 for each W-9 edition, 15 for the I-9,
12 for the Cerfa. These tests are the count, not a restatement of it: a change to templates.py
that quietly grows or shrinks a required list is caught here before it disagrees with a number
already tagged and pushed.
"""
import collections
import os
import tempfile

import pytest

from preflight.degradation import Degradation
from preflight.fixtures import CLEAN, VARIANTS, build, enumerate_variants
from preflight.reading import blank, read_piece
from preflight.reference import ROOT, load_reference
from grid.analyze import DEFAULT_IDENTITY as ANALYZE_DEFAULT_IDENTITY, sweep
from grid.run import DEFAULT_IDENTITY as RUN_DEFAULT_IDENTITY, key as run_key

IDENTITIES_DIR = os.path.join(ROOT, "fixtures", "identities")
IDENTITY_FILES = sorted(f for f in os.listdir(IDENTITIES_DIR) if f.endswith(".yaml"))

# The exact arithmetic of PREREG.md section 3.2, by piece and by check.
EXPECTED_BY_PIECE = {"tax": 9, "tax_es": 9, "employment": 15, "identity": 12}
EXPECTED_BY_CHECK = {"required_field": 22, "required_checkbox": 4, "signature": 1, "expiry": 2,
                     "consistency": 1, "forbidden_value": 3, "resolution": 4,
                     "cropped_page": 4, "rotated_page": 4}
EXPECTED_TOTAL = 45


def test_six_identity_files_exist():
    assert len(IDENTITY_FILES) == 6, IDENTITY_FILES


@pytest.mark.parametrize("fname", IDENTITY_FILES + ["reference.yaml"])
def test_enumerate_variants_count_matches_prereg(fname):
    """45 defect instances per identity, prereg-v1's own arithmetic, reproduced by a script
    reading the templates and not by hand-counting."""
    path = (os.path.join(ROOT, "fixtures", "reference.yaml") if fname == "reference.yaml"
            else os.path.join(IDENTITIES_DIR, fname))
    ref = load_reference(path)
    instances = [v for v in enumerate_variants(ref) if v.check]
    assert len(instances) == EXPECTED_TOTAL, (
        f"{ref.identity}: {len(instances)} instances, prereg-v1 declares {EXPECTED_TOTAL}")
    by_piece = collections.Counter(v.piece for v in instances)
    assert dict(by_piece) == EXPECTED_BY_PIECE, f"{ref.identity}: {dict(by_piece)}"
    by_check = collections.Counter(v.check for v in instances)
    assert dict(by_check) == EXPECTED_BY_CHECK, f"{ref.identity}: {dict(by_check)}"
    # One CLEAN plus the defect instances, no duplicate names.
    names = [v.name for v in enumerate_variants(ref)]
    assert len(names) == len(set(names)), f"{ref.identity}: duplicate variant name"
    assert names[0] == "clean"


def test_enumerate_variants_names_never_collide_with_the_legacy_nine():
    """VARIANTS (v0.1.0, imported by grid/target_parasite.py) and enumerate_variants() share a
    module: their names must never collide, or a lookup by name would silently pick either."""
    ref = load_reference()
    legacy = {v.name for v in VARIANTS}
    exhaustive = {v.name for v in enumerate_variants(ref)}
    overlap = legacy & exhaustive
    assert overlap == {"clean"}, f"unexpected name collision: {overlap}"


def test_cache_isolates_identities():
    """Two identities built into the SAME cache directory must never share a file: before this
    fix the cache path carried no identity, so a second person silently reused the first one's
    PDFs (T08's blocker, preflight/fixtures.py build())."""
    ref1 = load_reference(os.path.join(IDENTITIES_DIR, "id01.yaml"))
    ref2 = load_reference(os.path.join(IDENTITIES_DIR, "id02.yaml"))
    with tempfile.TemporaryDirectory() as dest:
        d1 = build(ref1, CLEAN, dest)
        d2 = build(ref2, CLEAN, dest)
        p1, p2 = d1.piece("tax").pdf, d2.piece("tax").pdf
        assert p1 != p2, "two identities built into the same cache share a path"
        assert open(p1, "rb").read() != open(p2, "rb").read(), (
            "two identities built into the same cache share their PDF bytes")


def test_the_default_identity_constants_agree():
    """grid/run.py and grid/analyze.py each default a missing "identity" field independently
    (one writes readings, the other reads them back): they must default to the same constant,
    and it must be what load_reference() derives for fixtures/reference.yaml itself."""
    assert RUN_DEFAULT_IDENTITY == ANALYZE_DEFAULT_IDENTITY
    assert RUN_DEFAULT_IDENTITY == load_reference().identity


def test_the_key_round_trips():
    """identity is appended LAST to the key grid/run.py writes: seed stays at index 4 and
    parasite at index 5 (the analysis relies on both positions, see grid/analyze.py's AXIS_INDEX
    and split()). A line with no "identity" field, exactly the shape of every line already
    published in A0, defaults to the same constant on every such line."""
    line = {"angle": 0.5, "dpi": 200, "jpeg": 95, "sigma": 0.0, "seed": 11, "parasite": 0.0,
            "identity": "id03", "variant": "clean", "piece": "tax"}
    k = run_key(line)
    assert k[4] == 11 and k[5] == 0.0 and k[6] == "id03"
    old_line = dict(line)
    del old_line["identity"]
    k_old = run_key(old_line)
    assert k_old[6] == RUN_DEFAULT_IDENTITY
    # Two old-format lines for different pieces of the same reading default identically.
    old_line2 = dict(old_line, piece="identity")
    assert run_key(old_line2)[6] == run_key(old_line)[6]


def test_sweep_pools_every_instance_of_a_check():
    """The core of T08's fix: sweep() must pool positives from EVERY variant that damages a
    given check, not stop at the first one a fixed catalog happens to declare. Real PDFs, real
    OCR, on two required_field instances that touch two DIFFERENT pieces: a sweep that only
    ever saw one variant per check (the v0.1.0 behaviour) could never show both at once.
    """
    ref = load_reference(os.path.join(IDENTITIES_DIR, "id01.yaml"))
    variants = enumerate_variants(ref)
    v_tax = next(v for v in variants if v.name == "empty_required_field@tax.name")
    v_identity = next(v for v in variants
                      if v.name == "empty_required_field@identity.card_number")
    for _, template_name in ref.pieces:
        blank(ref.templates[template_name])
    cell = Degradation(angle=0.0, dpi=200, jpeg=95, sigma=0.0, seed=11)
    with tempfile.TemporaryDirectory() as dest:
        clean = build(ref, CLEAN, dest)
        dossier_tax = build(ref, v_tax, dest)
        dossier_identity = build(ref, v_identity, dest)
        clean_readings = {"tax": read_piece(clean.piece("tax"), cell),
                          "identity": read_piece(clean.piece("identity"), cell)}
        tax_readings = dict(clean_readings, tax=read_piece(dossier_tax.piece("tax"), cell))
        identity_readings = dict(clean_readings,
                                 identity=read_piece(dossier_identity.piece("identity"), cell))

    key = (0.0, 200, 95, 0.0, 11, 0.0, ref.identity)
    dossiers = {key: {"clean": clean_readings, v_tax.name: tax_readings,
                      v_identity.name: identity_readings}}
    swept = sweep(dossiers, ref, "required_field")
    assert swept, "no settings produced a sweep at all"
    found_both = any(
        {piece for _, piece, _ in per_cell[key]["pos"]} >= {"tax", "identity"}
        for per_cell in swept.values())
    assert found_both, (
        "sweep() did not pool positives from both required_field variants: it is still "
        "stopping at the first one, the exact limitation T08 fixes")
