"""G0j, arm A2 (T10): continuous per-page jitter on top of a cell.

perfect-recall-study/prereg/PREREG.md (tag prereg-v1, section 3) names the jitter this file
must reproduce: angle offset U(-0.1, +0.1) degrees, translation dx and dy U(-3, +3) pixels at
200 dpi scaled to the cell dpi, a fresh blur draw U(0.3, 0.5), a JPEG quality offset integer
U(-5, +5) clipped to [10, 100]; drawn once per page, in that order, from default_rng(seed);
translation applied after the rotation and before the noise.

Two properties are non-negotiable, per T10's own done line: jitter OFF must replay the
published grid (A0) exactly, byte for byte; jitter ON must give different readings for
different seeds even in a noise-free cell (sigma=0), which is the whole point of A2 over A1
(perfect-recall-study prereg/PREREG.md P2: "a seed that means something").
"""
import json
import os
from dataclasses import replace

import numpy as np
import pytest

import grid.run as run
from grid.run import CELL_SETS, key as run_key
from preflight.degradation import Degradation, apply
from preflight.fixtures import CLEAN, build
from preflight.reading import blank, read_piece
from preflight.reference import ROOT

MEASUREMENTS = os.path.join(ROOT, "grid", "measurements", "measurements.jsonl")


def _page():
    """A page with structure (two dark bars on a white field), not a blank canvas: a pure
    translation or blur is a no-op on a blank page and would prove nothing."""
    page = np.full((400, 300), 255, dtype=np.uint8)
    page[100:120, 40:260] = 0
    page[220:240, 40:260] = 0
    return page


# --- Degradation.key() -------------------------------------------------------------------

def test_degradation_key_distinguishes_jitter():
    off = Degradation(angle=0.5, dpi=200, jpeg=95, sigma=0.0, seed=11, jitter=False)
    on = Degradation(angle=0.5, dpi=200, jpeg=95, sigma=0.0, seed=11, jitter=True)
    assert off.key() != on.key()


def test_degradation_jitter_defaults_off():
    assert Degradation().jitter is False


# --- apply(): pixel-level behaviour -------------------------------------------------------

def test_apply_jitter_off_ignores_seed_in_a_noise_free_cell():
    """The control: with jitter off and sigma=0, nothing left in Degradation reads the seed, so
    two seeds must produce the identical page. If this test fails, jitter=False is not the
    no-op T10 requires."""
    page = _page()
    base = Degradation(angle=0.5, dpi=200, jpeg=95, sigma=0.0, jitter=False)
    a = apply(page, replace(base, seed=11))
    b = apply(page, replace(base, seed=23))
    assert np.array_equal(a, b)


def test_apply_jitter_on_differs_by_seed_in_a_noise_free_cell():
    """The property T10 exists to add: with jitter on, sigma=0 no longer means seed-independent,
    because the jitter draw itself is seeded. This is what makes A2 answer whether a re-run
    seed only redraws noise (P2)."""
    page = _page()
    base = Degradation(angle=0.5, dpi=200, jpeg=95, sigma=0.0, jitter=True)
    a = apply(page, replace(base, seed=11))
    b = apply(page, replace(base, seed=23))
    assert not np.array_equal(a, b)


def test_apply_jitter_on_is_deterministic_for_the_same_seed():
    page = _page()
    deg = Degradation(angle=0.5, dpi=200, jpeg=95, sigma=0.0, seed=11, jitter=True)
    assert np.array_equal(apply(page, deg), apply(page, deg))


@pytest.mark.parametrize("seed", [11, 23, 37])
def test_apply_jitter_on_matches_a_hand_replay_of_the_draw_order(seed):
    """Pins the draw order PREREG.md declares (angle, dx, dy, blur, jpeg offset) so a reordering
    would fail here even though it might still pass the two tests above."""
    page = _page()
    dpi = 300
    deg = Degradation(angle=0.5, dpi=dpi, jpeg=95, sigma=0.0, seed=seed, jitter=True)
    rng = np.random.default_rng(seed)
    angle = 0.5 + rng.uniform(-0.1, 0.1)
    scale = dpi / 200.0
    dx = rng.uniform(-3.0, 3.0) * scale
    dy = rng.uniform(-3.0, 3.0) * scale
    blur = rng.uniform(0.3, 0.5)
    jpeg = int(np.clip(95 + int(rng.integers(-5, 6)), 10, 100))

    from PIL import Image, ImageFilter
    im = Image.fromarray(page)
    im = im.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    im = im.transform(im.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy),
                      resample=Image.BICUBIC, fillcolor=255)
    a = np.asarray(im).astype(np.int16)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if jpeg < 100:
        import io
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=jpeg)
        buf.seek(0)
        im = Image.open(buf).convert("L")
    expected = np.asarray(im)

    assert np.array_equal(apply(page, deg), expected)


def test_jpeg_offset_is_clipped_to_10_100():
    """A seed that would push the offset past the bound must land exactly on it, not wrap."""
    page = _page()
    for seed in range(200):
        deg = Degradation(angle=0.0, dpi=200, jpeg=95, sigma=0.0, seed=seed, jitter=True)
        rng = np.random.default_rng(seed)
        rng.uniform(-0.1, 0.1)          # angle
        rng.uniform(-3.0, 3.0)          # dx
        rng.uniform(-3.0, 3.0)          # dy
        rng.uniform(0.3, 0.5)           # blur
        offset = int(rng.integers(-5, 6))
        assert 10 <= int(np.clip(95 + offset, 10, 100)) <= 100


# --- jitter off replays the published grid (A0) exactly -----------------------------------

MEASUREMENTS_MISSING = not os.path.exists(MEASUREMENTS)
# grid/measurements/ is git-ignored (see .gitignore): the 14,976-line A0 file is a local data
# artifact, present on a machine that ran the published grid, never guaranteed in a fresh clone
# or worktree. Skipping when it is absent matches how T08 verifies its own byte-identical
# replay: a manual check against local data, not a pytest assumption a fresh checkout cannot
# meet. Run with the file present (the main checkout has it) to exercise this for real.


def _committed_line(angle, dpi, jpeg, sigma, seed, variant, piece):
    with open(MEASUREMENTS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if (d["angle"] == angle and d["dpi"] == dpi and d["jpeg"] == jpeg
                    and d["sigma"] == sigma and d["seed"] == seed
                    and d["variant"] == variant and d["piece"] == piece):
                return d
    raise AssertionError(f"no committed line for a{angle} d{dpi} q{jpeg} s{sigma} g{seed} "
                         f"{variant}/{piece}")


@pytest.fixture(scope="module")
def clean_dossier(reference, tmp_path_factory):
    dest = str(tmp_path_factory.mktemp("jitter-replay"))
    for _, name in reference.pieces:
        blank(reference.templates[name])
    return build(reference, CLEAN, dest)


@pytest.mark.skipif(MEASUREMENTS_MISSING, reason="grid/measurements/measurements.jsonl is "
                    "git-ignored local data, absent from this checkout")
@pytest.mark.parametrize("angle,dpi,jpeg,sigma,seed,piece", [
    # High-fidelity cells only (jpeg 95, sigma 0): a harsh cell (low dpi, heavy JPEG, noise)
    # makes Tesseract itself less deterministic across tesseract versions, which is an
    # environment property of OCR, not of this file's jitter=False no-op claim.
    (0.0, 200, 95, 0.0, 11, "tax"),
    (0.0, 200, 95, 0.0, 23, "tax"),
    (0.0, 300, 95, 0.0, 37, "employment"),
    (2.0, 300, 95, 0.0, 11, "employment"),
])
def test_jitter_off_replays_a_published_a0_line_exactly(clean_dossier, angle, dpi, jpeg, sigma,
                                                         seed, piece):
    """Degradation(jitter=False) must reproduce A0 (the committed v0.1.0 grid) byte for byte:
    adding the jitter field and its draw is a strict no-op when jitter stays off. Real render,
    real degrade, real OCR, no shortcuts, exactly as run.py's task() would produce the line."""
    committed = _committed_line(angle, dpi, jpeg, sigma, seed, "clean", piece)
    p = clean_dossier.piece(piece)
    base = Degradation(angle=angle, dpi=dpi, jpeg=jpeg, sigma=sigma, seed=seed, jitter=False)
    deg = replace(base, **p.image_override) if p.image_override else base
    reading = read_piece(p, deg)
    # Round-tripped through JSON like run.py's own line (json.dumps then json.loads): the
    # committed dict is already loads()'d, and json has no tuple, only a list.
    got = json.loads(json.dumps(reading.dict(), ensure_ascii=False))
    assert got == committed["reading"]


# --- grid/run.py: --jitter, the line dict, the resume key ---------------------------------

def test_run_key_appends_jitter_after_piece():
    """The resume key: identity is appended last before T10 (seed stays index 4, parasite index
    5); jitter goes one index further still, so every pre-T10 index keeps its meaning and an
    old line with no "jitter" field defaults to False, exactly like the identity default."""
    line = {"angle": 0.0, "dpi": 200, "jpeg": 95, "sigma": 0.0, "seed": 11, "parasite": 0.0,
            "identity": "id03", "variant": "clean", "piece": "tax", "jitter": True}
    k = run_key(line)
    assert k[4] == 11 and k[5] == 0.0 and k[6] == "id03"
    assert k[-1] is True

    old_line = dict(line)
    del old_line["jitter"]
    k_old = run_key(old_line)
    assert k_old[:-1] == k[:-1]
    assert k_old[-1] is False


class _FakePiece:
    image_override = None
    template = "fake-template"


def test_task_threads_jitter_onto_the_degradation_and_the_line(monkeypatch):
    """--jitter travels through the job tuple (a spawned worker has no other way to see argparse
    state) onto the Degradation passed to read_piece, and onto the written line. Every line also
    carries ts now (T07's done line), needed by T31's tag-time check."""
    seen_degs = []

    class _FakeReading:
        def dict(self):
            return {"peak": 1.0}

    def fake_read_piece(piece, deg, parasite=None):
        seen_degs.append(deg)
        return _FakeReading()

    monkeypatch.setattr(run, "read_piece", fake_read_piece)
    monkeypatch.setattr(run, "_REFS", {"idX": object()})
    monkeypatch.setattr(run, "_VARIANTS", {"idX": ()})
    monkeypatch.setattr(run, "_PIECES", {("idX", "clean", "tax"): _FakePiece()})
    monkeypatch.setattr(run, "_BOOTED_WITH", None)

    job = ((0.0, 200, 95, 0.0), 11, 0.0, "idX", None, True, (("clean", "tax"),))
    lines = run.task(job)

    assert len(lines) == 1
    line = lines[0]
    assert line["jitter"] is True
    assert "ts" in line and isinstance(line["ts"], str) and line["ts"]
    assert seen_degs[0].jitter is True


def test_task_jitter_off_is_unaffected(monkeypatch):
    class _FakeReading:
        def dict(self):
            return {"peak": 1.0}

    seen_degs = []

    def fake_read_piece(piece, deg, parasite=None):
        seen_degs.append(deg)
        return _FakeReading()

    monkeypatch.setattr(run, "read_piece", fake_read_piece)
    monkeypatch.setattr(run, "_REFS", {"idX": object()})
    monkeypatch.setattr(run, "_VARIANTS", {"idX": ()})
    monkeypatch.setattr(run, "_PIECES", {("idX", "clean", "tax"): _FakePiece()})
    monkeypatch.setattr(run, "_BOOTED_WITH", None)

    job = ((0.0, 200, 95, 0.0), 11, 0.0, "idX", None, False, (("clean", "tax"),))
    lines = run.task(job)
    assert lines[0]["jitter"] is False
    assert seen_degs[0].jitter is False


# --- the reduced cell set R, after the PREREG cap cut --------------------------------------

def test_cells_R_is_the_18_cell_prereg_cut():
    """perfect-recall-study prereg/PREREG.md (tag prereg-v1, section 3.3): the full R (36 cells,
    JPEG {55, 95}) exceeds the 30,000-reading cap for A1 and A2; the recorded cut drops JPEG 55.
    R must therefore already BE the cut, 18 cells: angle {0, 0.5, 2} x dpi {150, 200, 300} x
    JPEG {95} x sigma {0, 6}."""
    angles, dpis, jpegs, sigmas = CELL_SETS["R"]
    assert angles == (0.0, 0.5, 2.0)
    assert dpis == (150, 200, 300)
    assert jpegs == (95,)
    assert sigmas == (0.0, 6.0)
    import itertools
    cells = list(itertools.product(angles, dpis, jpegs, sigmas))
    assert len(cells) == 18, len(cells)
