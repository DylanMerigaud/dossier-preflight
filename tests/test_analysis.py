"""The analysis arithmetic, tested on cases where the right answer can be worked out by hand.

These functions decide the published thresholds. A mistake here does not crash a test, it
publishes a wrong number that looks measured, which is worse.
"""
import math

from grid.analyze import (FP_BUDGET, VALIDATION_SEED, curve, measure, chosen_point,
                          split, wilson)


def test_wilson_brackets_the_proportion():
    low, high = wilson(3, 3)
    assert low < 1.0 <= high, "3 successes out of 3 do not prove a rate of 1.0"
    assert wilson(0, 3)[1] > 0.0, "0 successes out of 3 do not prove a rate of 0.0"
    low1, high1 = wilson(50, 100)
    low2, high2 = wilson(500, 1000)
    assert (high2 - low2) < (high1 - low1), "the interval must tighten as n grows"


def test_the_curve_runs_from_everything_to_nothing():
    pts = curve(pos=[3.0, 4.0, 5.0], neg=[0.0, 1.0, 2.0])
    assert pts[0]["recall"] == 1.0 and pts[0]["fpr"] == 1.0
    assert pts[-1]["recall"] == 0.0 and pts[-1]["fpr"] == 0.0


def test_a_perfect_separation_gives_a_perfect_point():
    pts = curve(pos=[10.0, 11.0], neg=[0.0, 1.0])
    perfect = [p for p in pts if p["recall"] == 1.0 and p["fpr"] == 0.0]
    assert perfect, "two disjoint populations must have a threshold that separates them"


def test_the_chosen_point_respects_the_false_positive_budget():
    """A higher recall never buys back going over budget."""
    pos = [1.0] * 50 + [9.0] * 50
    neg = [0.0] * 90 + [5.0] * 10        # 10% of the clean ones carry a high score
    pt = chosen_point(curve(pos, neg), budget=0.05)
    assert pt is not None
    assert pt["fpr"] <= 0.05
    assert pt["recall"] == 0.5, "the only tenable recall here is that of the 50 scores at 9.0"


def test_a_zero_budget_returns_a_null_recall_and_not_none():
    """There is always a threshold with zero false positives: the one that never fires.

    So it is never the absence of a point that flags an unusable check, it is too low a recall
    at the chosen point. Confusing the two would make a check look measured when it is simply
    mute.
    """
    pt = chosen_point(curve(pos=[1.0], neg=[2.0]), budget=0.0)
    assert pt is not None and pt["recall"] == 0.0 and pt["fpr"] == 0.0


def test_no_measurement_no_point():
    assert chosen_point([]) is None


def test_precision_depends_on_prevalence():
    pts = curve(pos=[10.0] * 100, neg=[0.0] * 99 + [10.0])
    p = [x for x in pts if x["recall"] == 1.0][-1]
    assert p["grid_precision"] > p["prevalence_precision"], (
        "at low prevalence the same false positive rate costs more precision")


def test_the_split_isolates_the_validation_seed():
    per_cell = {(0.0, 200, 95, 0.0, s): (1.0, 0.0) for s in (11, 23, VALIDATION_SEED)}
    cal, val = split(per_cell)
    assert len(cal) == 2 and len(val) == 1
    assert all(k[4] != VALIDATION_SEED for k in cal)


def test_measure_counts_what_strictly_exceeds_the_threshold():
    m = measure({(0.0, 200, 95, 0.0, 11): {"pos": {"a": 5.0}, "neg": {"a": 5.0, "b": 1.0}},
                 (0.0, 200, 95, 0.0, 23): {"pos": {"a": 7.0}, "neg": {"a": 1.0, "b": 1.0}}},
                threshold=5.0)
    assert m["tp"] == 1 and m["fp"] == 0
    assert math.isclose(m["recall"], 0.5) and m["fpr"] == 0.0


def test_the_per_dossier_rate_is_far_higher_than_the_per_target_rate():
    """This is the trap in the headline number: seventeen fields at 1% each do not make 1% of
    clean dossiers. A dossier cries as soon as ONE of its targets cries."""
    cells = {}
    for i in range(100):
        neg = {f"field{j}": (9.0 if (i % 10 == j) else 0.0) for j in range(10)}
        cells[(0.0, 200, 95, 0.0, i)] = {"pos": {"field0": 9.0}, "neg": neg}
    m = measure(cells, threshold=5.0)
    assert math.isclose(m["fpr"], 0.10), "one target in ten fires"
    assert math.isclose(m["dossier_fpr"], 1.0), "but every dossier carries an alarm"


def test_the_budget_is_declared_and_tight():
    """If this budget goes lax, the gate loses its credibility without anything failing."""
    assert 0 < FP_BUDGET <= 0.01
