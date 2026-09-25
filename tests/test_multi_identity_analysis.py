"""The analysis on multi-identity, every-instance data (the A1 and A2 shape), on TOY data.

The readings here are labels, not images: grid.analyze.target_scores is replaced by a table
lookup, so each test states exactly which target scores what and checks the bookkeeping around
it (pooling, per-identity references, completeness, the crosstalk columns). The OCR itself is
covered elsewhere; what these tests guard is arithmetic that a real run would only show as a
wrong number.
"""
import os
from dataclasses import replace

import pytest

import grid.analyze as analyze
import grid.run as run
from preflight.fixtures import VARIANTS, _content_tag, enumerate_variants
from preflight.reference import ROOT, load_reference

IDS = os.path.join(ROOT, "fixtures", "identities")
REG = ("toy",)


@pytest.fixture
def refs():
    return {i: load_reference(os.path.join(IDS, f"{i}.yaml")) for i in ("id01", "id02")}


@pytest.fixture
def fake_scores(monkeypatch):
    """target_scores(readings, ref, check, reg) -> readings[check], and a log of which
    Reference each call received, keyed by the reading's own identity label."""
    calls = []

    def target_scores(readings, ref, check, reg, clock="filing", abstention=False):
        calls.append((readings["who"], ref.identity))
        return dict(readings.get(check, {}))
    monkeypatch.setattr(analyze, "target_scores", target_scores)
    monkeypatch.setattr(analyze, "combinations", lambda check: [REG])
    return calls


def _key(identity, seed=11):
    return (0.0, 200, 95, 0.0, seed, 0.0, identity)


def _dossiers(refs, scores_for):
    """Every enumerated variant of every identity, readings = scores_for(identity, variant)."""
    out = {}
    for identity, ref in refs.items():
        d = {}
        for v in enumerate_variants(ref):
            d[v.name] = dict(scores_for(identity, v), who=identity)
        out[_key(identity)] = d
    return out


def test_sweep_counts_two_instances_on_the_same_target_twice(refs, fake_scores):
    """Expiry at 1 day and at 365 days past damage the SAME field. Keyed by target alone, the
    second instance overwrote the first and each cell counted one positive instead of two."""
    target = ("employment", "Exp Date mmddyyyy")

    def scores_for(identity, v):
        return {"expiry": {target: 5.0 if v.check == "expiry" else -5.0}}
    dossiers = _dossiers(refs, scores_for)
    swept = analyze.sweep(dossiers, refs["id01"], "expiry",
                          catalog={n: v for r in refs.values()
                                   for n, v in analyze.variant_catalog(r).items()},
                          ref_of=refs.__getitem__)
    for key in dossiers:
        pos = swept[REG][key]["pos"]
        assert len(pos) == 2, pos
        assert {k[0] for k in pos} == {"expired_date@employment.expiry_date.1d",
                                        "expired_date@employment.expiry_date.365d"}


def test_sweep_pools_every_instance_and_scores_each_row_on_its_own_identity(refs, fake_scores):
    """22 required-field instances per identity, each damaging its own field(s): every damaged
    target is a positive, nothing else is, and every call got the row's own Reference."""
    def scores_for(identity, v):
        tpl = refs[identity].templates[dict(refs[identity].pieces)[v.piece]] if v.piece else None
        damaged = {(v.piece, c) for role in v.empty_fields for c in tpl.field_ids(role)}
        return {"required_field": {t: 1.0 for t in damaged} | {("tax", "clean-field"): -1.0}}
    dossiers = _dossiers(refs, scores_for)
    swept = analyze.sweep(dossiers, refs["id01"], "required_field",
                          catalog=analyze.variant_catalog(refs["id01"]),
                          ref_of=refs.__getitem__)
    expected = sum(len(analyze.damaged_targets(v, refs["id01"]))
                   for v in enumerate_variants(refs["id01"]) if v.check == "required_field")
    for key in dossiers:
        pos = swept[REG][key]["pos"]
        assert len(pos) == expected
        assert all(x == 1.0 for x in pos.values()), "an undamaged target leaked into positives"
    assert fake_scores and all(who == got for who, got in fake_scores), (
        "a row was scored against another identity's Reference")


def test_an_enumerated_instance_that_abstains_does_not_fall_back_to_every_target(
        refs, fake_scores):
    """v0.1.0's fallback (no damaged target scored: take every target) stays for the nine
    legacy names only. On an enumerated instance it would count the filled fields as misses."""
    def scores_for(identity, v):
        return {"required_field": {("tax", "some-filled-field"): -1.0,
                                   ("employment", "another-filled-field"): -1.0}}
    dossiers = _dossiers({"id01": refs["id01"]}, scores_for)
    swept = analyze.sweep(dossiers, refs["id01"], "required_field", ref_of=refs.__getitem__)
    assert swept[REG][_key("id01")]["pos"] == {}


def test_complete_dossiers_requires_every_declared_variant(refs):
    """Completeness is DECLARED per identity, never inferred from the file: a variant missing
    from every cell must empty those cells, not quietly leave the denominator."""
    names = {i: frozenset(v.name for v in enumerate_variants(r)) for i, r in refs.items()}
    four = {p: object() for p, _ in refs["id01"].pieces}
    index = {}
    for identity in refs:
        index[_key(identity)] = {n: dict(four) if n == "clean" else {"tax": object()}
                                 for n in names[identity]}
    dropped = sorted(names["id02"] - {"clean"})[0]
    del index[_key("id02")][dropped]
    out = analyze.complete_dossiers(index, refs["id01"], names.__getitem__)
    assert set(out) == {_key("id01")}
    assert set(out[_key("id01")]) == names["id01"]


def test_complete_dossiers_default_is_the_legacy_nine(refs):
    four = {p: object() for p, _ in refs["id01"].pieces}
    index = {_key(analyze.DEFAULT_IDENTITY): {v.name: dict(four) for v in VARIANTS}}
    out = analyze.complete_dossiers(index, refs["id01"])
    assert set(out[_key(analyze.DEFAULT_IDENTITY)]) == {v.name for v in VARIANTS}


def test_crosstalk_on_multi_identity_data(refs, fake_scores):
    """The crosstalk used to iterate the nine legacy names against ONE reference, which on
    A1-shaped data is a KeyError at best. Columns stay the legacy labels, each pooling every
    instance of its check, one trial per (dossier, instance), each on its own Reference."""
    fires_on = "unchecked_box@employment.status"

    def scores_for(identity, v):
        return {"required_field": {("x", "y"): 1.0 if v.name == fires_on else -1.0}}
    dossiers = {}
    for seed in (11, 23):
        for identity, ref in refs.items():
            dossiers[_key(identity, seed)] = {
                v.name: dict(scores_for(identity, v), who=identity)
                for v in enumerate_variants(ref)}
    catalog = analyze.variant_catalog(refs["id01"])
    results = {"required_field": {"settings": REG, "threshold": 0.0}}
    out = analyze.crosstalk(dossiers, refs["id01"], results, catalog=catalog,
                            ref_of=refs.__getitem__)["required_field"]
    per_check = {}
    for v in enumerate_variants(refs["id01"]):
        if v.check:
            per_check[v.check] = per_check.get(v.check, 0) + 1
    assert "empty_required_field" not in out, "the diagonal must stay empty"
    assert list(out) == [v.name for v in VARIANTS if v.check and v.check != "required_field"]
    for name, row in out.items():
        check = analyze.BY_NAME[name].check
        assert row["n"] == per_check[check] * len(dossiers), (name, row)
    assert out["unchecked_box"]["rate"] == pytest.approx(1 / per_check["required_checkbox"])
    assert all(r["rate"] == 0 for n, r in out.items() if n != "unchecked_box")
    assert fake_scores and all(who == got for who, got in fake_scores)


def test_the_fixture_cache_tag_follows_the_identity_content(refs):
    """An identity edited after a first build must not be served its stale PDFs."""
    ref = refs["id01"]
    moved = replace(ref, person=dict(ref.person, name="ELSEWHERE"))
    assert _content_tag(ref) != _content_tag(moved)
    assert _content_tag(ref) == _content_tag(load_reference(os.path.join(IDS, "id01.yaml")))


def test_run_bootstrap_refuses_a_second_identity_set(monkeypatch):
    """A worker bootstrapped for one set of identities must not serve it for another."""
    monkeypatch.setattr(run, "_REFS", {})
    monkeypatch.setattr(run, "_BOOTED_WITH", "/a")
    run._bootstrap("/a")
    with pytest.raises(RuntimeError):
        run._bootstrap("/b")
