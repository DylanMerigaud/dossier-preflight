"""The holdout predicates and the frozen scoring mode of grid/analyze.py (T09).

Three properties, each one a way the study around this tool could publish a wrong number:
  - the DEFAULT split is the published one, exactly (seeds 11 and 23 choose, 37 reports), so
    every number already published replays unchanged;
  - an expression can only compare key fields to literals: nothing in it is ever executed;
  - --frozen scores rows exactly as preflight.checks.evaluate() does with the same thresholds
    file, which is what the command line runs on a real dossier.
"""
import itertools
import json
import os
import sys

import pytest

import grid.analyze as analyze
from grid.predicates import KEY_FIELDS, Holdout, Predicate, PredicateError
from preflight.checks import evaluate
from preflight.fixtures import VARIANTS
from preflight.reading import Reading
from preflight.thresholds import FILE as SHIPPED


def key(seed=11, parasite=0.0, identity="reference", source="g0", jitter=False,
        capture=None, mark_step=None, angle=0.0, dpi=200, jpeg=95, sigma=0.0):
    return (angle, dpi, jpeg, sigma, seed, parasite, identity, source, jitter, capture,
            mark_step)


# ---------------------------------------------------------------- the expression language

def test_key_fields_keep_the_historical_positions():
    assert KEY_FIELDS[4] == "seed" and KEY_FIELDS[5] == "parasite"
    assert KEY_FIELDS[analyze.IDENTITY_INDEX] == "identity"


@pytest.mark.parametrize("text, k, expected", [
    ("seed != 37", key(seed=11), True),
    ("seed != 37", key(seed=37), False),
    ('source == "g1" and seed == 37', key(source="g1", seed=37), True),
    ('source == "g1" and seed == 37', key(source="g0", seed=37), False),
    ("seed in (11, 23)", key(seed=23), True),
    ("seed not in [11, 23]", key(seed=23), False),
    ('not (angle == 2.0 or dpi == 150)', key(angle=0.5, dpi=200), True),
    ('not (angle == 2.0 or dpi == 150)', key(dpi=150), False),
    ("150 < dpi <= 300", key(dpi=200), True),
    ("150 < dpi <= 300", key(dpi=150), False),
    ('identity != "id03"', key(identity="id03"), False),
    ("jitter", key(jitter=True), None),          # a bare name is not a predicate: refused
    ("jitter == True", key(jitter=True), True),
    ("parasite > 0", key(parasite=0.01), True),
    ("sigma >= -1", key(sigma=0.0), True),
    ("mark_step >= 1", key(mark_step=None), False),   # an ordering on a missing field is false
    ("mark_step in (1, 2, 3)", key(mark_step=2), True),
    ("capture == None", key(), True),
    ("True", key(), True),
])
def test_expressions(text, k, expected):
    if expected is None:
        with pytest.raises(PredicateError):
            Predicate(text)
        return
    assert Predicate(text)(k) is expected


@pytest.mark.parametrize("text", [
    "__import__('os').system('true')",
    "seed.__class__",
    "seed == open('x')",
    "seed + 1 == 12",
    "seed[0] == 1",
    "lambda: 1",
    "unknown == 1",
    "seed == (lambda: 1)()",
    "[x for x in (1,)]",
    "seed = 1",
    "seed == 37; import os",
])
def test_anything_but_a_comparison_of_fields_to_literals_is_refused(text):
    with pytest.raises(PredicateError):
        Predicate(text)


def test_the_fields_read_are_known_and_the_parasite_bypass_follows_them():
    assert Predicate('source == "g1" and seed == 37').fields == {"source", "seed"}
    assert not Holdout("seed != 37", "seed == 37").on_parasite
    assert Holdout("parasite == 0", "parasite > 0").on_parasite


# ---------------------------------------------------------------- the split

def test_the_default_split_is_the_published_one_on_every_key_shape():
    """The legacy rule was k[4] != 37 / k[4] == 37. Checked on the old five-, seven- and the
    new eleven-field keys, over every seed, source and level combination."""
    keys = [key(seed=s, parasite=p, source=src, jitter=j)
            for s, p, src, j in itertools.product((11, 23, 37), (0.0, 0.01), ("g0", "g1"),
                                                   (False, True))]
    keys += [k[:5] for k in keys] + [k[:7] for k in keys]
    per_cell = {k: {"pos": {}, "neg": {}} for k in keys}
    cal, val = analyze.split(per_cell)
    assert set(cal) == {k for k in keys if k[4] != analyze.VALIDATION_SEED}
    assert set(val) == {k for k in keys if k[4] == analyze.VALIDATION_SEED}
    assert analyze.split_by(per_cell, analyze.DEFAULT_HOLDOUT) == (cal, val)


def _toy_line(seed, source="g0", identity="reference", variant="clean", piece="tax",
              parasite=0.0, jitter=None, mark_step=None):
    r = Reading(piece, "fw9", 0.0, 0, 200.0, 0.9, 1.0, 0.0)
    line = {"angle": 0.0, "dpi": 200, "jpeg": 95, "sigma": 0.0, "seed": seed,
            "parasite": parasite, "identity": identity, "variant": variant, "piece": piece,
            "reading": r.dict()}
    if source != "g0":
        line["source"] = source
    if jitter is not None:
        line["jitter"] = jitter
    if mark_step is not None:
        line["mark_step"] = mark_step
    return line


def test_a_predicate_split_on_a_toy_file(tmp_path):
    """P4's shape: choose on G0 seeds 11 and 23, report on G1 seed 37. The rows it names on
    neither side (G0 seed 37, G1 seeds 11 and 23) stay out of both sets."""
    path = tmp_path / "toy.jsonl"
    lines = [_toy_line(s, src) for s in (11, 23, 37) for src in ("g0", "g1")]
    lines += [_toy_line(11, jitter=True), _toy_line(11, "x2", mark_step=0)]
    path.write_text("".join(json.dumps(l) + "\n" for l in lines))
    index = analyze.load(str(path))
    assert len(index) == 8, "source, jitter and mark_step must keep rows apart"
    assert key(seed=11) in index, "a line with none of the new fields keeps the G0 defaults"
    assert key(seed=11, jitter=True) in index
    assert key(seed=11, source="x2", mark_step=0) in index
    h = Holdout('source == "g0" and seed in (11, 23) and not jitter == True',
                'source == "g1" and seed == 37')
    per_cell = {k: {"pos": {}, "neg": {}} for k in index}
    cal, val = analyze.split(per_cell, h.calibrate, h.report)
    assert set(cal) == {key(seed=11), key(seed=23)}
    assert set(val) == {key(seed=37, source="g1")}
    assert {k for k in per_cell if h.keeps(k)} == set(cal) | set(val)


def test_a_parasite_fold_is_not_emptied_by_the_level_zero_cut():
    by_settings = {"reg": {key(seed=s, parasite=p): {"pos": {}, "neg": {}}
                           for s in (11, 37) for p in (0.0, 0.01)}}
    assert all(not k[5] for k in analyze.clean_pages(by_settings)["reg"])
    assert all(not k[5] for k in analyze.clean_pages(by_settings,
                                                     analyze.DEFAULT_HOLDOUT)["reg"])
    fold = Holdout("parasite == 0", "parasite > 0")
    kept = analyze.clean_pages(by_settings, fold)["reg"]
    assert len(kept) == 4
    cal, val = analyze.split_by(kept, fold)
    assert all(k[5] == 0 for k in cal) and all(k[5] > 0 for k in val) and val


# ---------------------------------------------------------------- the frozen mode

def _dossiers(readings, seeds=(11,)):
    return {key(seed=s): readings for s in seeds}


def test_the_frozen_mode_equals_evaluate_on_the_same_rows(readings, reference):
    """Every target the frozen mode scores carries the score and the verdict evaluate() gives
    it with the shipped file (settings=None: the measured settings, as the command line runs)."""
    rows = analyze.frozen_rows(_dossiers(readings), reference, SHIPPED)
    assert rows
    by_variant = {}
    for r in rows:
        by_variant.setdefault(r["variant"], {})[(r["check"], r["piece"], r["target"])] = r
    for name, got in by_variant.items():
        truth = {(c.check, c.piece, str(c.target)): c
                 for c in evaluate(readings[name], reference, "filing")}
        for t, r in got.items():
            assert t in truth, (name, t)
            assert r["score"] == truth[t].score and r["fires"] == truth[t].fires, (name, t)
            assert r["abstained"] == (truth[t].score is None)
    # every clean target of every check is a negative, and nothing else is
    clean = [(c.check, c.piece, str(c.target))
             for c in evaluate(readings["clean"], reference, "filing")]
    assert sorted(by_variant["clean"]) == sorted(clean)
    assert not any(r["positive"] for r in rows if r["variant"] == "clean")
    # a variant contributes positives to ITS check only
    for r in rows:
        if r["positive"]:
            assert analyze.BY_NAME[r["variant"]].check == r["check"]


def test_the_frozen_report_counts_what_fires(readings, reference):
    rows = analyze.frozen_rows(_dossiers(readings, (11, 23)), reference, SHIPPED)
    report = analyze.frozen_report(rows, SHIPPED)
    for check, m in report.items():
        mine = [r for r in rows if r["check"] == check and not r["abstained"]]
        assert m["tp"] == sum(r["fires"] for r in mine if r["positive"])
        assert m["fp"] == sum(r["fires"] for r in mine if not r["positive"])
        assert m["n_pos"] == sum(r["positive"] for r in mine)
        assert m["n_pos_abstained"] == sum(
            1 for r in rows if r["check"] == check and r["positive"] and r["abstained"])


def _toy_file(readings, path, seeds=(11, 23, 37)):
    edited = {v.name: v.piece for v in VARIANTS if v.check}
    with open(path, "w", encoding="utf-8") as f:
        for s in seeds:
            for name, pieces in readings.items():
                for piece, r in pieces.items():
                    if name != "clean" and piece != edited[name]:
                        continue
                    f.write(json.dumps({"angle": 0.0, "dpi": 200, "jpeg": 95, "sigma": 0.0,
                                        "seed": s, "variant": name, "piece": piece,
                                        "reading": r.dict()}) + "\n")


def _main(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["analyze.py"] + args)
    return analyze.main()


def test_the_frozen_command_line(readings, reference, tmp_path, monkeypatch):
    path = tmp_path / "toy.jsonl"
    _toy_file(readings, path)
    out, rows_csv = tmp_path / "frozen.json", tmp_path / "rows.csv"
    assert _main(monkeypatch, ["--measurements", str(path), "--frozen", SHIPPED,
                               "--report-on", "seed == 37", "--frozen-out", str(out),
                               "--frozen-rows", str(rows_csv)]) == 0
    got = json.loads(out.read_text())
    assert got["n_dossiers"] == 1 and got["report_on"] == "seed == 37"
    rows = analyze.frozen_rows(_dossiers(readings, (37,)), reference, SHIPPED)
    want = json.loads(json.dumps(analyze._jsonable(analyze.frozen_report(rows, SHIPPED)),
                                 default=str))
    assert got["checks"] == want
    assert len(rows_csv.read_text().splitlines()) == len(rows) + 1


def test_the_default_flags_and_the_explicit_published_split_write_the_same_bytes(
        readings, tmp_path, monkeypatch):
    """The whole analysis, run twice on the same toy file: once with no flag, once with the
    published split spelled out. Every file it writes must be byte-identical (the plot aside,
    whose bytes carry matplotlib's own metadata)."""
    path = tmp_path / "toy.jsonl"
    _toy_file(readings, path)
    a, b = tmp_path / "a", tmp_path / "b"
    assert _main(monkeypatch, ["--measurements", str(path), "--output", str(a)]) == 0
    assert _main(monkeypatch, ["--measurements", str(path), "--output", str(b),
                               "--calibrate-on", "seed != 37",
                               "--report-on", "seed == 37"]) == 0
    names = sorted(n for n in os.listdir(a) if n != "curves.png")
    assert names == sorted(n for n in os.listdir(b) if n != "curves.png")
    assert "resume.json" in names and "LIMITS.md" in names
    for n in names:
        assert (a / n).read_bytes() == (b / n).read_bytes(), n
