#!/usr/bin/env python3
"""Read the thresholds OFF the curves, do not pick them by hand.

Input: the grid's raw measurements. Output: one precision/recall curve per check, the retained
operating point, the breakdown floor, and the A/B duel tables.

THE ASYMMETRY IS DECLARED HERE, IN NUMBERS, because an operating point chosen without it is
chosen at random:

  a FALSE NEGATIVE is the counter rejecting the dossier. Months of delay, a summons to start
  again, sometimes a document to request again from a foreign administration.
  a FALSE POSITIVE is the gate crying on a clean dossier. It does not cost a delay, it costs
  the gate's CREDIBILITY, and a rule that cries wolf makes every rule next to it get skimmed.
  It is the only cost that destroys the tool instead of degrading it.

Hence the rule: take the HIGHEST ATTAINABLE RECALL under a held false positive budget, and the
budget is written down in plain sight (FP_BUDGET), not assumed. It is per check and per
dossier: with nine checks, a clean dossier has roughly 9 times that budget of a chance to raise
an alarm for nothing, and that is the number the user actually feels.

    python3 grid/analyze.py
"""
import argparse
import collections
import csv
import itertools
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.sensors import DISC_RATIOS, INK_THRESHOLDS
from preflight.checks import CHECKS, NUISANCES, Settings, evaluate
from preflight.fixtures import BY_NAME, VARIANTS
from preflight.reading import Reading
from preflight.reference import load_reference

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "grid", "results")

# False positive budget PER TARGET (a field, a box, a forbidden value), not per dossier. A
# dossier carries seventeen required fields: the rate a user FEELS is the one of the whole
# dossier, roughly seventeen times this one, and it is measured and published separately under
# the name of per-dossier rate. Declaring one while believing you are talking about the other
# is the most common way to announce a gate safer than it is.
FP_BUDGET = 0.002
VALIDATION_SEED = 37     # never looked at to choose a threshold, only to report it
RECALL_FLOOR = 0.95        # below this recall a cell is declared outside the domain
PREVALENCE = 0.10          # ASSUMED share of genuinely faulty dossiers, for precision

# Swept down to 0. A COMB field (one box per character, the form declares it) reads "4/1)2" at
# confidence 38: all three digits are there, but the separators break tesseract's word model and
# collapse its confidence. A floor at 40 would throw away a FILLED field, that is, manufacture a
# false positive on a clean dossier, on the side that destroys the gate's credibility. Since
# confidence is applied at ANALYSIS time and not in the grid, widening it costs not one image.
CONF_MINS = (0.0, 10.0, 20.0, 40.0, 60.0, 80.0)
TEXT_SENSORS = ("page", "zone", "union")
SIGNATURE_SENSORS = ("components", "ink")

SWEPT_VALUES = {"min_conf": CONF_MINS, "text_sensor": TEXT_SENSORS,
           "disc_ratio": DISC_RATIOS, "ink_threshold": INK_THRESHOLDS,
           "signature_sensor": SIGNATURE_SENSORS}

MINUS_INF = -1e18


def combinations(check):
    """The settings that change something FOR THIS CHECK, and only those.

    The required-field check is the only one crossing two sensor families that do not have the
    same knobs: OCR confidence means nothing to an ink sensor, and an ink threshold means
    nothing to a word sensor. Crossing them anyway would multiply an already long sweep by six
    without producing a single extra point.
    """
    if check == "required_field":
        return ([Settings(text_sensor=t, min_conf=c)
                 for t in TEXT_SENSORS for c in CONF_MINS]
                + [Settings(text_sensor="ink", ink_threshold=e) for e in INK_THRESHOLDS])
    names = NUISANCES[check]
    if not names:
        return [Settings()]
    return [Settings(**dict(zip(names, v)))
            for v in itertools.product(*[SWEPT_VALUES[n] for n in names])]


def load(path):
    """index[(angle, dpi, jpeg, sigma, seed)][variant][piece] = Reading"""
    index = collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            key = (d["angle"], d["dpi"], d["jpeg"], d["sigma"], d["seed"])
            index[key][d["variant"]][d["piece"]] = Reading.from_dict(d["reading"])
    return index


def complete_dossiers(index):
    """A variant's dossier = the edited piece, plus the two pieces of the clean dossier.

    Incomplete cells are dropped silently: the grid resumes where it stopped, and a
    half-written cell would manufacture a false negative that does not exist.
    """
    expected = {v.name for v in VARIANTS}
    out = {}
    for key, by_variant in index.items():
        if not expected <= set(by_variant):
            continue
        clean = by_variant["clean"]
        if len(clean) < 3:
            continue
        d = {"clean": clean}
        for v in VARIANTS:
            if v.check:
                d[v.name] = dict(clean, **by_variant[v.name])
        out[key] = d
    return out


def target_scores(readings, ref, check, reg, clock="filing", abstention=False):
    """The score of EVERY target of the check: a field, a box, a forbidden value.

    This is the right unit of measurement, and choosing it changes the result. Run at dossier
    level, the required-field check only has two possible operating points (cry as soon as one
    field out of seventeen is unreadable, or never cry) because its score is the WORST of its
    fields. Per target the curve genuinely exists, the negatives are seventeen times more
    numerous so the false positive rate is measurable, and above all one can say WHICH field is
    not certifiable instead of condemning the whole check.
    """
    return {(c.piece, str(c.target)): c.score
            for c in evaluate(readings, ref, clock, reg, checks=[check],
                             abstention=abstention)
            if c.score is not None}


def dossier_score(readings, ref, check, reg, clock="filing"):
    """The dossier's worst finding. A dossier is rejected as soon as ONE piece is wrong."""
    return max(target_scores(readings, ref, check, reg, clock).values(), default=MINUS_INF)


def damaged_targets(var, ref):
    """What the variant ACTUALLY damages, declared and not guessed.

    Without this list the positive class would be "the whole faulty dossier" and the sixteen
    intact fields it carries would count as missed positives.
    """
    if not var.check:
        return set()
    tpl = ref.templates[dict(ref.pieces)[var.piece]] if var.piece else None
    if var.empty_fields:
        return {(var.piece, c) for role in var.empty_fields for c in tpl.field_ids(role)}
    if var.uncheck:
        return {(var.piece, tpl.boxes[role]) for role in var.uncheck}
    if var.without_signature:
        return {(var.piece, c) for c in tpl.signatures.values()}
    if var.expired_date:
        return {(var.piece, c) for role, kind in tpl.dates.items() if kind == "expiration"
                for c in tpl.field_ids(role)}
    if var.check == "forbidden_value":
        injected = {str(v) for v in var.replace.values()}
        return {(var.piece, v) for v in ref.forbidden_values if v in injected}
    if var.check == "consistency":
        return {(f"{a['piece']}+{b['piece']}", cons["data"])
                for cons in ref.consistencies
                for a, b in itertools.combinations(cons["readings"], 2)}
    return {(var.piece, "")}          # resolution, cropped page, rotated page


def wilson(successes, n, z=1.96):
    """Wilson interval. At n=3 seeds per cell, the normal interval lies."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def curve(pos, neg):
    """Every operating point, from the most lax to the strictest.

    The candidate thresholds are the OBSERVED scores: between two neighbouring scores no
    threshold changes anything, and inventing others would only fatten the file.
    """
    thresholds = sorted({s for s in list(pos) + list(neg) if s > MINUS_INF})
    if not thresholds:
        return []
    margins = [thresholds[0] - 1.0]
    margins += [(a + b) / 2 for a, b in zip(thresholds, thresholds[1:])]
    margins += [thresholds[-1] + 1.0]
    pts = []
    for t in margins:
        tp = sum(1 for s in pos if s > t)
        fp = sum(1 for s in neg if s > t)
        recall = tp / len(pos) if pos else 0.0
        fpr = fp / len(neg) if neg else 0.0
        grid_prec = tp / (tp + fp) if (tp + fp) else 1.0
        num = PREVALENCE * recall
        real_prec = num / (num + (1 - PREVALENCE) * fpr) if (num + (1 - PREVALENCE) * fpr) else 1.0
        pts.append({"threshold": t, "recall": recall, "fpr": fpr,
                    "grid_precision": grid_prec, "prevalence_precision": real_prec,
                    "tp": tp, "fp": fp, "n_pos": len(pos), "n_neg": len(neg)})
    return pts


def precisions(recall, fpr):
    """Precision at the grid's composition (one faulty for one clean) and at the assumed
    prevalence. The second is the one that counts, and it is harsher."""
    num = PREVALENCE * recall
    return {"grid_precision": recall / (recall + fpr) if (recall + fpr) else 1.0,
            "prevalence_precision": num / (num + (1 - PREVALENCE) * fpr)
            if (num + (1 - PREVALENCE) * fpr) else 1.0}


def chosen_point(pts, budget=FP_BUDGET):
    """The highest recall under the false positive budget. Nothing more, nothing less.

    There is ALWAYS a point under any budget: the one that never fires, at zero recall. So it
    is never the absence of a point that flags an unusable check, it is too low a recall at the
    chosen point, and that is what LIMITS.md has to say.
    """
    if not pts:
        return None
    affordable = [p for p in pts if p["fpr"] <= budget]
    if not affordable:
        return None
    best = max(affordable, key=lambda p: (p["recall"], -p["fpr"]))
    # At equal recall, take the threshold in the middle of the plateau: a threshold pressed
    # against an observed value flips on the first pixel of noise in a future measurement.
    plateau = [p for p in affordable
              if p["recall"] == best["recall"] and p["fpr"] == best["fpr"]]
    return plateau[len(plateau) // 2]


def sweep(dossiers, ref, check):
    """For each settings, the per-target scores, cell by cell.

    Returns: {settings: {cell_key: {"pos": {target: score}, "neg": {target: score}}}}
    The positives are the targets the variant damages; the negatives are ALL the targets of the
    clean dossier, which gives the false positive rate the statistical power it lacked.
    """
    var = next(v for v in VARIANTS if v.check == check)
    targets = damaged_targets(var, ref)
    out = {}
    for reg in combinations(check):
        per_cell = {}
        for key, d in dossiers.items():
            all_scores = target_scores(d[var.name], ref, check, reg)
            pos = {k: v for k, v in all_scores.items() if k in targets} or all_scores
            per_cell[key] = {"pos": pos,
                             "neg": target_scores(d["clean"], ref, check, reg)}
        out[reg] = per_cell
    return out


def flatten(per_cell):
    pos = [x for v in per_cell.values() for x in v["pos"].values()]
    neg = [x for v in per_cell.values() for x in v["neg"].values()]
    return pos, neg


def split(per_cell):
    """Calibration against validation.

    Choosing a threshold on data and then reporting its recall on the SAME data always
    overestimates it: the threshold has lodged itself in the noise of those particular draws.
    Two seeds calibrate, the third is never looked at before the number is written.
    """
    cal = {k: v for k, v in per_cell.items() if k[4] != VALIDATION_SEED}
    val = {k: v for k, v in per_cell.items() if k[4] == VALIDATION_SEED}
    return cal, val


def measure(per_cell, threshold):
    """Two false positive rates, and both are needed.

    Per target: the probability that ONE clean field is declared empty. That is the one the
    threshold is chosen on, because it is the elementary decision.
    Per dossier: the probability that AT LEAST ONE alarm goes off on an entirely clean dossier.
    That is the one the user feels, and it is the one that decides whether they keep believing
    the gate. The second is roughly the first multiplied by the number of targets.
    """
    pos, neg = flatten(per_cell)
    tp = sum(1 for x in pos if x > threshold)
    fp = sum(1 for x in neg if x > threshold)
    hit = sum(1 for v in per_cell.values() if any(x > threshold for x in v["neg"].values()))
    n_d = len(per_cell)
    return {"threshold": threshold, "recall": tp / len(pos) if pos else 0.0,
            "fpr": fp / len(neg) if neg else 0.0, "tp": tp, "fp": fp,
            "n_pos": len(pos), "n_neg": len(neg), "n_dossiers": n_d,
            "dossier_fpr": hit / n_d if n_d else 0.0,
            "recall_ci": wilson(tp, len(pos)), "fpr_ci": wilson(fp, len(neg)),
            "dossier_fpr_ci": wilson(hit, n_d)}


def certifiability(per_cell):
    """Which targets the tool can certify, and which it must refuse to judge.

    THIS COMPUTATION DOES NOT TOUCH THE OPERATING POINT, and it took a mistake to understand
    why. Excluding the awkward targets BEFORE choosing the threshold creates a loop: fewer
    negatives, therefore a more permissive threshold is affordable, therefore a recall of 100%
    displayed on the single surviving target. On the forbidden-value check that loop produced a
    threshold of 0.11 similarity, a value at which anything resembles anything, with five
    targets out of six excluded and a perfect score. That was make-up.

    The threshold is therefore chosen on ALL targets. This computation only serves to EXPLAIN
    the number obtained: when a check plateaus it is almost always two or three fields that cap
    it, and naming them beats condemning the whole check. What such a field calls for is the
    tool answering "I cannot read this field" instead of "this field is empty": same sensor,
    opposite consequences at the counter.
    """
    pos, _ = flatten(per_cell)
    if not pos:
        return {}, {}
    ordered = sorted(pos)
    full_recall = ordered[min(len(ordered) - 1,
                              int(round((1 - RECALL_FLOOR) * len(ordered))))] - 1e-9
    count, seen = collections.Counter(), collections.Counter()
    for v in per_cell.values():
        for target, score in v["neg"].items():
            seen[target] += 1
            if score > full_recall:
                count[target] += 1
    rate = {c: count[c] / seen[c] for c in seen}
    return ({c: t for c, t in rate.items() if t <= FP_BUDGET},
            {c: t for c, t in sorted(rate.items(), key=lambda kv: -kv[1]) if t > FP_BUDGET})


def restricted_to_certifiable(per_cell, kept, check):
    """A SECONDARY figure, labelled as such: what the check is worth if it is only asked about
    the targets it can certify. Never the headline number, never in thresholds.json."""
    if not kept or len(kept) == len(next(iter(per_cell.values()))["neg"]):
        return None
    subset = restrict(per_cell, kept)
    cal, val = split(subset)
    pos, neg = flatten(cal)
    pt = chosen_point(curve(pos, neg))
    if pt is None:
        return None
    m = measure(val, pt["threshold"])
    m["kept_targets"] = len(kept)
    m["total_targets"] = len(next(iter(per_cell.values()))["neg"])
    return m


def restrict(per_cell, kept):
    return {key: {"pos": v["pos"],
                  "neg": {k: x for k, x in v["neg"].items() if k in kept}}
            for key, v in per_cell.items()}


def noisy_targets(per_cell, threshold, n=8):
    """Which CLEAN targets fire, and how often. The actionable list.

    A globally unusable check is almost always a check that two or three fields make unusable.
    Naming those fields beats condemning the check.
    """
    count = collections.Counter()
    seen = collections.Counter()
    for v in per_cell.values():
        for target, score in v["neg"].items():
            seen[target] += 1
            if score > threshold:
                count[target] += 1
    return [(c, count[c], seen[c]) for c, _ in count.most_common(n)]


def settings_summary(per_cell):
    """The curve and the point are computed on the CALIBRATION set alone."""
    cal, _ = split(per_cell)
    pos, neg = flatten(cal)
    pts = curve(pos, neg)
    return pts, chosen_point(pts)


def by_factor(per_cell, threshold):
    """Recall and false positives per value of each factor, at the retained threshold."""
    axes = {"angle": 0, "dpi": 1, "jpeg": 2, "sigma": 3}
    out = {}
    for name, i in axes.items():
        groups = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        for key, v in per_cell.items():
            g = groups[key[i]]
            g[0] += sum(1 for x in v["pos"].values() if x > threshold)
            g[1] += len(v["pos"])
            g[2] += sum(1 for x in v["neg"].values() if x > threshold)
            g[3] += len(v["neg"])
            g[4] += any(x > threshold for x in v["neg"].values())
            g[5] += 1
        out[name] = {val: {"recall": g[0] / max(1, g[1]), "n": g[1],
                          "fpr": g[2] / max(1, g[3]),
                          "dossier_fpr": g[4] / max(1, g[5]),
                          "ci": wilson(g[0], g[1])}
                    for val, g in sorted(groups.items())}
    return out


def floor(per_cell, threshold, minimum=RECALL_FLOOR):
    """The cells where recall drops below the floor. One cell = 3 seeds.

    A tool that does not say where it stops working is not measured, it is narrated.
    """
    groups = collections.defaultdict(lambda: [0, 0])
    for (a, d, q, s, _), v in per_cell.items():
        g = groups[(a, d, q, s)]
        g[0] += sum(1 for x in v["pos"].values() if x > threshold)
        g[1] += len(v["pos"])
    fallen_cells = {c: (g[0] / max(1, g[1]), g[1]) for c, g in groups.items()
               if g[0] / max(1, g[1]) < minimum}
    return fallen_cells, len(groups)


AXES = ("angle", "dpi", "jpeg", "sigma")


def worst_conjunctions(per_cell, threshold, how_many=3):
    """The worst CROSSINGS of two factors, not just the worst values of each.

    A marginal reading can lie by omission. On forbidden values, recall says 0.979 at 300 dpi,
    0.981 at JPEG 95 and 0.977 at sigma 12: none of those three values crosses the floor, and
    one concludes the check is fine everywhere. Crossed, they make a cell below the floor. The
    sign runs against intuition, and that is what makes it interesting: recall drops as quality
    RISES, because heavy compression erases the sensor's grain while light compression keeps it,
    and at high resolution that grain is fine enough to be read as character structure. That
    part of the mechanism is measured by a control, see grid/corner_followup.py.

    THIS SWEEP ONLY SEES THE SHADOW OF THE CELL, and that has to be known while reading it. The
    real shape of that particular defect is a conjunction of FOUR factors (300 dpi AND JPEG 95
    AND noise 12 AND angle at or above 0.5 deg: 30/30 below that angle, 50/60 above). A pair
    averages over the two remaining factors, so it always attenuates what it shows. Going to
    three and four factors would blow up the number of buckets and drop n to 15 per bucket,
    which would make the intervals useless. The two-factor sweep therefore serves to FIND the
    cell; it is the list of worst cells, already four-factor, that NAMES it.
    """
    out = {}
    for i, a in enumerate(AXES):
        for b in AXES[i + 1:]:
            ia, ib = AXES.index(a), AXES.index(b)
            groups = collections.defaultdict(lambda: [0, 0])
            for key, v in per_cell.items():
                g = groups[(key[ia], key[ib])]
                g[0] += sum(1 for x in v["pos"].values() if x > threshold)
                g[1] += len(v["pos"])
            ranked = sorted(((k, g[0] / max(1, g[1]), g[1], wilson(g[0], g[1]))
                             for k, g in groups.items()), key=lambda t: t[1])
            out[f"{a} x {b}"] = [{"values": list(k), "recall": r, "n": n, "ci": list(ci)}
                                 for k, r, n, ci in ranked[:how_many]]
    return out


def frontier(fallen_cells, all_cells):
    """The readable frontier: per factor, the value at which things start falling."""
    axes = ["angle", "dpi", "jpeg", "sigma"]
    out = {}
    for i, name in enumerate(axes):
        count = collections.Counter(c[i] for c in fallen_cells)
        total = collections.Counter(c[i] for c in all_cells)
        out[name] = {v: (count.get(v, 0), total[v]) for v in sorted(total)}
    return out


def plot(results, path):
    if not results:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(results)
    cols = 3
    lines = (n + cols - 1) // cols
    fig, axes = plt.subplots(lines, cols, figsize=(4.6 * cols, 3.8 * lines))
    for ax, (check, r) in zip(axes.ravel(), sorted(results.items())):
        for label, pts, bold in r["curves"]:
            xs = [p["recall"] for p in pts]
            ys = [p["prevalence_precision"] for p in pts]
            ax.plot(xs, ys, linewidth=2.0 if bold else 0.8,
                    alpha=1.0 if bold else 0.35, label=label if bold else None)
        pt = r["point"]
        if pt:
            ax.plot([pt["recall"]], [pt["prevalence_precision"]], "o", color="crimson", zorder=5)
            ax.annotate(f"threshold {pt['threshold']:.3g}\nrecall {pt['recall']:.3f}\nfpr {pt['fpr']:.4f}",
                        (pt["recall"], pt["prevalence_precision"]), fontsize=7,
                        xytext=(-4, -34), textcoords="offset points", color="crimson")
        ax.axvline(RECALL_FLOOR, color="gray", linestyle=":", linewidth=0.8)
        ax.set_title(check, fontsize=10)
        ax.set_xlabel("recall")
        ax.set_ylabel(f"precision at {PREVALENCE:.0%} prevalence")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.2)
        if any(g for _, _, g in r["curves"]):
            ax.legend(fontsize=7, loc="lower left")
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(f"Precision/recall per check, {results[list(results)[0]]['n_cells']} "
                 f"cells x 3 seeds, false positive budget {FP_BUDGET:.1%}", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    return path


# The checks that genuinely depend on what OCR manages to read. They are the ones defining the
# useful resolution floor, not the resolution check itself.
OCR_DEPENDENT = ("required_field", "expiry", "consistency", "forbidden_value")


def crosstalk(dossiers, ref, results):
    """Does check c fire when the defect belongs to ANOTHER check.

    The tests already demanded this, but on a single cell. The grid measures it everywhere,
    because it is the half that counts: a check that cries about its neighbour's defect casts
    doubt on the neighbour, and a rule that cries wolf makes the ones next to it get skimmed.

    The table is not made only of faults. A CROPPED page takes real fields with it: the
    required-field check is right to cry there. What the table gives is the means to separate a
    physical consequence from a contamination.
    """
    out = {}
    for check, r in results.items():
        reg, threshold = r["settings"], r["threshold"]
        lines = {}
        for v in VARIANTS:
            if not v.check or v.check == check:
                continue
            n = fired = 0
            for d in dossiers.values():
                # HERE abstention is ON: crosstalk measures the behaviour of the PRODUCT, not
                # the raw capability of the sensors.
                scores = target_scores(d[v.name], ref, check, reg, abstention=True)
                n += 1
                fired += any(x > threshold for x in scores.values())
            lines[v.name] = {"rate": fired / max(1, n), "n": n, "ci": wilson(fired, n)}
        out[check] = lines
    return out


def dpi_estimator_error(dossiers):
    """The maximum relative error of the dpi estimator, measured on the clean dossiers."""
    worst = 0.0
    for (_, dpi, _, _, _), d in dossiers.items():
        for reading in d["clean"].values():
            worst = max(worst, abs(reading.source_dpi - dpi) / dpi)
    return worst


def remeasure(r, threshold):
    """Recompute everything AT THE THRESHOLD WE PUBLISH. Otherwise we publish a recall measured
    somewhere else.

    The resolution check's threshold is not the one from its own curve: it is raised to the
    others' floor. Without this recomputation, thresholds.json announced "false positives
    0.0000" next to a value at which that was false (33% of clean targets at 150 dpi). Same
    family of fault as the reading sentence outliving its sensor: a number measured under one
    configuration, published next to another.
    """
    pc = r["_per_cell"]
    cal, val = split(pc)
    fallen_cells, n_cel = floor(pc, threshold)
    r.update({"threshold": threshold,
              "calibration": measure(cal, threshold), "validation": measure(val, threshold),
              "overall": measure(pc, threshold),
              "factors": by_factor(pc, threshold),
              "conjunctions": worst_conjunctions(pc, threshold),
              "fallen_cells": fallen_cells, "n_cells": n_cel,
              "frontier": frontier(fallen_cells, {c[:4] for c in pc}),
              "noisy_targets": noisy_targets(pc, threshold)})
    return r


def operational_floor(results, domain, dossiers):
    """The resolution check's threshold is not read off ITS OWN curve. And that is the point.

    Its curve would place it between 72 dpi (the faulty variant) and 96 dpi (the grid's lowest
    dpi), that is, at the spot that best separates those two populations. But the question this
    check has to ask is not "is this page at 72 dpi", it is "is this page sharp enough for the
    OTHER checks to hold". Its threshold is therefore read off the BREAKDOWN FLOOR of the checks
    that depend on OCR: the lowest dpi where all of them keep their recall above the floor.

    An accepted consequence, and it has to be said: if that floor sits above the grid's lowest
    dpi, then CLEAN dossiers scanned too low will fire this check. That is not a false positive,
    it is the check doing its job: we refuse to rule on a page we cannot read. Confusing it with
    a false positive would amount to staying silent exactly when we do not know.
    """
    # The threshold sits BELOW the floor, not on it. A scan at exactly 150 dpi estimates at
    # 149.98: with the threshold placed right on 150 it fired on all 288 clean dossiers scanned
    # at the floor itself. The margin is ten times the worst measured error of the estimator, at
    # least 1%, which stays forty times finer than the gap between two grid dpi values.
    error = dpi_estimator_error(dossiers)
    margin = max(0.01, 10 * error)
    floor_dpi = domain
    threshold_dpi = domain * (1 - margin)
    dpis = sorted(results["resolution"]["factors"]["dpi"])
    detail = {c: {d: round(results[c]["factors"]["dpi"][d]["recall"], 3) for d in dpis}
              for c in OCR_DEPENDENT if c in results}
    pr = results["resolution"]["point"]
    return {"threshold": -float(threshold_dpi),
            "point": dict(pr or {}, threshold=-float(threshold_dpi)),
            "floor_dpi": floor_dpi,
            "estimator_margin": margin,
            "max_estimator_error": error,
            "own_curve_threshold": (pr or {}).get("threshold"),
            "dependent_recall_by_dpi": detail}


DOMAINS = (96, 150, 200, 300)


def definition_thresholds():
    """The thresholds that are never FITTED, because they are not parameters.

    "Expired" means the date has passed: the threshold is zero days, full stop. Letting the grid
    choose it gave -207.5 days, and it was the two-clock test that caught it: the reference's
    healthy piece expires in 2027, so any threshold between -497 and -110 separates the data
    perfectly, and the optimiser took the middle of the plateau. The tool would have declared a
    piece expired seven months before it was, with a recall of 1.000 to back it up.

    This is the central trap of "read the threshold off the curve": a curve only knows the data
    it was given, and it will move a threshold that encodes MEANING without hesitating. The grid
    stays useful on these checks, but to answer a different question: the threshold being fixed
    by definition, what recall does it hold and at what price.
    """
    from preflight.thresholds import raw
    return {k for k, v in raw()["thresholds"].items() if v["origin"] == "definition"}


def subgrid(by_settings, keep):
    return {settings: {key: v for key, v in pc.items() if keep(key)}
            for settings, pc in by_settings.items()}


def analyze_check(by_settings, check, output=None):
    """Retain the best settings within budget, measure, look for the floor.

    Takes the ALREADY computed sweep: the nominal domain search tries four sub-grids and there
    is no reason to go over the same images four times, nor even over the same scores.
    """
    ranking = []
    for reg, per_cell in by_settings.items():
        if not per_cell:
            continue
        pts, pt = settings_summary(per_cell)
        ranking.append((reg, per_cell, pts, pt))
    if not ranking:
        return None
    affordable = [c for c in ranking if c[3] is not None]
    winner = max(affordable or ranking,
                  key=lambda c: (c[3]["recall"] if c[3] else -1, -(c[3]["fpr"] if c[3] else 1)))
    reg, per_cell, pts, pt = winner
    if not pts:
        return None
    frozen = check in definition_thresholds()
    if frozen:
        from preflight.thresholds import load_thresholds
        imposed = float(load_thresholds()[check])
        # With the threshold imposed, the sweep only serves to choose the SENSOR: keep the one
        # that recalls best AT THAT THRESHOLD, not the one that would recall best elsewhere.
        def note(c):
            m = measure(split(c[1])[0], imposed)
            return (m["recall"], -m["fpr"])
        reg, per_cell, pts, pt = max(ranking, key=note)
        m = measure(split(per_cell)[0], imposed)
        pt = dict(m, threshold=imposed, **precisions(m["recall"], m["fpr"]))
    kept, excluded = certifiability(per_cell)
    threshold = pt["threshold"] if pt else max(p["threshold"] for p in pts)
    cal, val = split(per_cell)
    fallen_cells, n_cel = floor(per_cell, threshold)
    if output:
        with open(os.path.join(output, f"pr_{check}.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pts[0].keys()))
            w.writeheader()
            w.writerows(pts)
    return {
        "settings": reg, "settings_text": settings_name(reg, check), "point": pt,
        "threshold": threshold, "n_cells": n_cel,
        "calibration": measure(cal, threshold), "validation": measure(val, threshold),
        "overall": measure(per_cell, threshold),
        "curves": [(settings_name(r, check), p, r == reg) for r, _, p, _ in ranking],
        "factors": by_factor(per_cell, threshold),
        "fallen_cells": fallen_cells, "frontier": frontier(fallen_cells, {c[:4] for c in per_cell}),
        "noisy_targets": noisy_targets(per_cell, threshold),
        "threshold_frozen_by_definition": frozen,
        "uncertifiable_targets": [(f"{a} / {b}", round(t, 4)) for (a, b), t in excluded.items()],
        "restricted": restricted_to_certifiable(per_cell, kept, check),
        "ranking": [{"settings": settings_name(r, check),
                        "recall": (q or {}).get("recall"), "fpr": (q or {}).get("fpr"),
                        "threshold": (q or {}).get("threshold")}
                       for r, pc, _, q in sorted(
                           ranking, key=lambda c: -((c[3] or {}).get("recall", -1)))],
        "_ranking": ranking,
        "_per_cell": per_cell,
        "conjunctions": worst_conjunctions(per_cell, threshold),
    }


def choose_domain(sweeps, checks):
    """The nominal domain: the lowest dpi where the checks that READ hold their floor.

    Without this step, the operating point of every text check is decided by the cells where the
    page is unreadable, and it retreats until it fires at nothing. The reason is mechanical: a
    dossier is rejected as soon as ONE required field is empty, so the dossier's score is that
    of its worst field; at 96 dpi the Cerfa has fields OCR cannot read, the CLEAN dossier then
    reaches the same score as the faulty one, and under a tight false positive budget no
    threshold separates them any more.

    Loosening the budget would erase the problem without solving it. The right move is to say
    where the tool declares itself competent, and to REFUSE TO CONCLUDE below that: which is the
    role of the resolution check, whose threshold comes from precisely here.
    """
    needed = [c for c in OCR_DEPENDENT if c in checks]
    attempts = []
    for dpi_min in DOMAINS:
        first = next(iter(sweeps.values()), {})
        empty = all(not any(k[1] >= dpi_min for k in pc) for pc in first.values()) if first \
            else True
        if empty:
            attempts.append((dpi_min, None))
            continue
        if not needed:
            attempts.append((dpi_min, 1.0))
            continue
        worst = 1.0
        for c in needed:
            r = analyze_check(subgrid(sweeps[c], lambda k: k[1] >= dpi_min), c)
            worst = min(worst, 0.0 if r is None else r["validation"]["recall"])
        attempts.append((dpi_min, worst))
        if worst >= RECALL_FLOOR:
            return dpi_min, attempts
    # No domain holds the floor. Then keep the LEAST BAD one, never the narrowest: falling back
    # on the narrowest domain would amount to answering "300 dpi" to a question the measurement
    # said no to everywhere, and doing so on the least data.
    valid = [(d, r) for d, r in attempts if r is not None]
    if not valid:
        return DOMAINS[0], attempts
    return max(valid, key=lambda x: x[1])[0], attempts


PHRASES = {
    "required_field": lambda r, v: (
        f"fires if the zone carries less than {-v:.3f}% ink ADDED relative to the blank "
        f"(ink threshold {r.ink_threshold})" if r.text_sensor == "ink" else
        f"fires if fewer than {-v:.0f} added alphanumeric character(s) are read in the zone "
        f"by the {r.text_sensor} sensor above {r.min_conf:.0f} confidence"),
    "required_checkbox": lambda r, v: (
        f"fires if the ink delta of the central disc (radius {r.disc_ratio} of the side, ink "
        f"threshold {r.ink_threshold}) is below {-v:+.2f}"),
    "signature": lambda r, v: (
        f"fires if the largest added component is less than {-v:.0f} px of canonical diagonal"
        if r.signature_sensor == "components" else
        f"fires if the zone carries less than {-v:.2f}% added ink"),
    "expiry": lambda r, v: "fires as soon as the date read has passed at the chosen clock",
    "consistency": lambda r, v: (
        f"fires if the worst token of the smaller reading is less than {1 - v:.3f} similar to "
        f"the best token of the other piece"),
    "forbidden_value": lambda r, v: (
        f"fires if a run of added words is more than {v:.3f} similar to a forbidden value"),
    "cropped_page": lambda r, v: (
        f"fires if more than {v:.2%} of the blank's ink falls outside the scan's frame"),
    "rotated_page": lambda r, v: (
        f"fires if a quarter turn beats the original quarter by more than {v:.3f} of "
        f"correlation"),
}


def reading_sentence(check, reg, value, defaut=""):
    """The sentence is REGENERATED at every publication, from the sensor actually retained.

    A sentence carried over as is outlives the sensor it describes. That happened here: after the
    grid retained ink for required fields, thresholds.json kept saying
    dire "moins de 1 caractere alphanumerique", et un lecteur pouvait croire que -0,345 etait
    "fewer than 1 alphanumeric character", and a reader could believe -0.345 was a character
    count when it is an ink percentage. A wrong unit inside a true sentence is more dangerous
    than a missing sentence.
    """
    f = PHRASES.get(check)
    return f(reg, value) if f else defaut


def _useful_settings(reg, check):
    """Only the knobs that ACTUALLY act on the retained settings.

    The ink sensor ignores OCR confidence: recording it next to that sensor would suggest it had
    been chosen when it decided nothing.
    """
    names = NUISANCES[check]
    if check == "required_field":
        names = ("text_sensor", "ink_threshold") if reg.text_sensor == "ink" \
            else ("text_sensor", "min_conf")
    return {n: getattr(reg, n) for n in names}


def _jsonable(v):
    """Cells are (angle, dpi, jpeg, sigma) tuples: JSON will not take such keys."""
    if isinstance(v, dict):
        return {(str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k):
                _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def settings_name(reg, check):
    if check == "required_field":
        return (f"text_sensor=ink, ink_threshold={reg.ink_threshold}"
                if reg.text_sensor == "ink"
                else f"text_sensor={reg.text_sensor}, min_conf={reg.min_conf}")
    names = NUISANCES[check]
    return ", ".join(f"{n}={getattr(reg, n)}" for n in names) or "no settings"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measurements", default=os.path.join(ROOT, "grid", "measurements", "measurements.jsonl"))
    ap.add_argument("--output", default=RESULTS)
    ap.add_argument("--checks", nargs="*", default=list(CHECKS))
    ap.add_argument("--publish", action="store_true",
                    help="write LIMITS.md and thresholds.json at the repo root")
    a = ap.parse_args()
    os.makedirs(a.output, exist_ok=True)

    ref = load_reference()
    index = load(a.measurements)
    dossiers = complete_dossiers(index)
    cells = {c[:4] for c in dossiers}
    print(f"{len(dossiers)} complete cell/seed pairs, {len(cells)} distinct cells")

    sweeps = {}
    for check in a.checks:
        t = time.perf_counter()
        sweeps[check] = sweep(dossiers, ref, check)
        print(f"  sweep {check:17s} {len(sweeps[check]):3d} settings, "
              f"{time.perf_counter() - t:5.1f}s", flush=True)

    domain, attempts = choose_domain(sweeps, a.checks)
    retained = {k: v for k, v in dossiers.items() if k[1] >= domain}
    print(f"nominal domain retained: dpi >= {domain} ({len(retained)} pairs). Attempts: "
          + ", ".join(f"{d} dpi -> " + ("no data" if r is None else
                                        f"worst recall {r:.3f}") for d, r in attempts))
    if all((r or 0) < RECALL_FLOOR for _, r in attempts):
        print(f"  NO domain holds the {RECALL_FLOOR:.0%} floor: the retained domain is the "
              "least bad one, not a safe domain.")

    results = {}
    for check in a.checks:
        r = analyze_check(subgrid(sweeps[check], lambda k: k[1] >= domain), check, a.output)
        if r is None:
            print(f"  {check:17s} NO usable measurement")
            continue
        r["domain"] = domain
        outside = subgrid(sweeps[check], lambda k: k[1] < domain)[r["settings"]]
        r["outside_domain"] = measure(outside, r["threshold"]) if outside else None
        results[check] = r
        v, c = r["validation"], r["calibration"]
        print(f"  {check:17s} {r['settings_text']:42s} threshold={r['threshold']:9.4g} "
              f"calib recall={c['recall']:.3f} fpr={c['fpr']:.4f} | "
              f"VALID recall={v['recall']:.3f} fpr={v['fpr']:.4f} | "
              f"outside domain {len(r['fallen_cells'])}/{r['n_cells']}")

    if "resolution" in results:
        results["resolution"].update(operational_floor(results, domain, retained))
        r = remeasure(results["resolution"], results["resolution"]["threshold"])
        r["point"] = dict(r["validation"], threshold=r["threshold"],
                          **precisions(r["validation"]["recall"], r["validation"]["fpr"]))
        print(f"  {'resolution':17s} threshold raised to {r['threshold']:.4g} = floor "
              f"{r['floor_dpi']} dpi minus {r['estimator_margin']:.1%} margin "
              f"(max measured estimator error {r['max_estimator_error']:.4%})")
    t = time.perf_counter()
    crossed = crosstalk(retained, ref, results)
    print(f"  crosstalk measured over the whole grid in {time.perf_counter() - t:.0f}s")
    if not results:
        print("no usable check, nothing to plot")
        return 1
    plot(results, os.path.join(a.output, "curves.png"))
    json.dump({c: {k: _jsonable(v) for k, v in r.items()
                   if k not in ("curves", "settings", "_ranking", "_per_cell")}
               for c, r in results.items()},
              open(os.path.join(a.output, "resume.json"), "w"), indent=2, default=str)
    write_duels(results, os.path.join(a.output, "duels.md"))
    json.dump(_jsonable(crossed), open(os.path.join(a.output, "crosstalk.json"), "w"), indent=2)
    root = ROOT if a.publish else a.output
    write_limits(results, os.path.join(root, "LIMITS.md"), len(dossiers),
                 domain, len(retained), attempts, crossed)
    if a.publish:
        write_thresholds(results, os.path.join(ROOT, "thresholds.json"))
    print(f"-> {a.output}/curves.png, {root}/LIMITS.md, {a.output}/duels.md"
          + (", thresholds.json published" if a.publish
             else ", thresholds.json NOT published (--publish)"))
    return 0


def duel_by_dpi(ranking, check):
    """Does the winner change with dpi. It is the only honest way to settle a duel.

    Each contender is judged at ITS OWN operating point (the one that holds the false positive
    budget), not at the neighbour's threshold: comparing two sensors at a common threshold
    compares a scale, not a sensor.
    """
    dpis = sorted({c[1] for _, pc, _, _ in ranking for c in pc})
    lines = []
    for reg, per_cell, _, pt in ranking:
        if pt is None:
            continue
        line = {"settings": settings_name(reg, check), "threshold": pt["threshold"],
                 "global": (pt["recall"], pt["fpr"])}
        for dpi in dpis:
            subset = {k: v for k, v in per_cell.items() if k[1] == dpi}
            m = measure(subset, pt["threshold"])
            line[dpi] = (m["recall"], m["fpr"], m["recall_ci"])
        lines.append(line)
    return dpis, sorted(lines, key=lambda l: -l["global"][0])


def write_duels(results, path):
    lines = ["# Duels between competing sensors", "",
             "Each contender is judged at ITS OWN operating point, the one that holds the",
             f"false positive budget of {FP_BUDGET:.1%}. Comparing two sensors at a common",
             "threshold would compare a scale and not a sensor. The intervals are 95% Wilson",
             "intervals: at three seeds per cell, the normal interval lies.",
             ""]
    for check in sorted(results):
        r = results[check]
        if not NUISANCES[check]:
            continue
        dpis, table = duel_by_dpi(r["_ranking"], check)
        if not table:
            continue
        lines += [f"## {check}", "",
                  "| settings | threshold | global recall | global fpr | "
                  + " | ".join(f"recall {d} dpi" for d in dpis) + " |",
                  "|---|---|---|---|" + "---|" * len(dpis)]
        for l in table:
            cells = " | ".join(f"{l[d][0]:.3f} [{l[d][2][0]:.2f}, {l[d][2][1]:.2f}]" for d in dpis)
            mark = " **(retained)**" if l["settings"] == r["settings_text"] else ""
            lines.append(f"| {l['settings']}{mark} | {l['threshold']:.4g} | "
                         f"{l['global'][0]:.3f} | {l['global'][1]:.4f} | {cells} |")
        # Ties at equal recall are broken by false positive rate, otherwise the "winner" is
        # simply the first of the list, which means nothing.
        winners = {d: max(table, key=lambda l: (l[d][0], -l[d][1]))["settings"] for d in dpis}
        # A tie is a result, not a victory. Announcing "sensor X wins" when two sensors return
        # exactly the same numbers everywhere is narrating a measurement that never happened.
        top = max(l["global"] for l in table)
        tied = [l["settings"] for l in table if l["global"] == top]
        if len(tied) > 1:
            lines += ["", f"TIE, not broken: {len(tied)} settings return exactly the same "
                      f"recall ({top[0]:.3f}) and the same false positive rate ({top[1]:.4f}) "
                      "over the whole domain. This corpus and this grid do not tell them apart. "
                      "The retained setting is the first of the list, and that choice is backed "
                      "by no measurement: " + ", ".join(tied[:4]) + "."]
        elif len(set(winners.values())) > 1:
            lines += ["", "The winner CHANGES with dpi: "
                      + ", ".join(f"{d} dpi -> {g}" for d, g in winners.items())
                      + ". The retained setting is the one that holds best over the whole "
                        "domain, not the one that wins a column."]
        else:
            lines += ["", f"Same winner at every dpi: {next(iter(winners.values()))}."]
        lines.append("")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def write_limits(results, path, n_pairs, domain, n_retained, attempts, crossed=None):
    l = ["# Limits: where this tool stops working", "",
         "A tool that does not say where it stops working is not measured, it is narrated.",
         "",
         f"## Nominal domain: scanning at {domain} dpi or more", "",
         f"The operating points are chosen on the {n_retained} pairs of this domain, not on the",
         f"{n_pairs} of the whole grid. That is not a way to hand ourselves nice numbers, it is a",
         "mechanical consequence: a dossier is rejected as soon as ONE required field is empty,",
         "so the dossier's score is that of its WORST field. Below the floor the Cerfa has fields",
         "OCR cannot read, the CLEAN dossier then reaches the same score as the faulty one, and",
         "no threshold separates them any more. The operating point would retreat until it fired",
         "at nothing at all.",
         "",
         "Below that floor the tool does not guess: the resolution check fires and says it cannot",
         "read the page. Every section below also gives what the check does OUTSIDE the domain,",
         "because hiding it would be lying about it.",
         "",
         "Domains tried, from widest to narrowest, with the worst recall of the checks that",
         "depend on OCR: "
         + ", ".join(f"dpi >= {d} -> " + ("no data" if r is None else f"{r:.3f}")
                     for d, r in attempts)
         + ".",
         "",
         f"Measured over {n_pairs} cell/seed pairs: angle (0, 0.25, 0.5, 1, 2, 4 deg) x",
         "dpi (96, 150, 200, 300) x JPEG quality (30, 55, 75, 95) x noise sigma (0, 3, 6, 12),",
         "three seeds per cell. Every check is evaluated at its operating point, chosen as the",
         f"highest recall holding a false positive rate under {FP_BUDGET:.1%}.",
         "",
         "The threshold is chosen on seeds 11 and 23, and the published figure is the one from",
         f"seed {VALIDATION_SEED}, never looked at beforehand. Choosing a threshold and reporting",
         "its recall on the same draws always overestimates it.",
         "",
         f"A cell is declared OUTSIDE THE DOMAIN when recall there drops below {RECALL_FLOOR:.0%}.",
         "",
         "## What the measurement does not cover", "",
         "- A single set of three forms (W-9, I-9, Cerfa 14011), page 1 of each. The figures do",
         "  not transport as they are to a form whose typography or field framing differs. The",
         "  Cerfa, whose fields are boxed character by character, is already markedly harder than",
         "  the two American forms.",
         "- ONE fictional dossier, ONE invented person, ONE defect per check. A recall of 1.000 is",
         "  that of the same defect seen 864 times, not of 864 different defects.",
         "- Words are only recorded inside the zones DECLARED by the AcroForm, expanded by 8 px. A",
         "  forbidden value reappearing outside any declared field, in a handwritten note in the",
         "  margin for instance, would not be seen.",
         "- A form without an AcroForm is out of reach: all the geometry comes from the PDF's own",
         "  declaration, nothing is measured by hand.",
         "- The degradations are SYNTHETIC. A real scanner adds artefacts this grid does not",
         "  imitate: page curvature, binding shadow, dust on the glass, rescreening moire. The",
         "  grid bounds the domain, it does not prove it.",
         "- DIRECT CONSEQUENCE ON THE INK SENSOR, and it is no longer a hypothesis: no degradation",
         "  in this grid ADDS foreign ink inside a zone, so the sensor retained for required",
         "  fields wins its duel on ground that favours it. A 528-reading probe put a number on",
         "  what that ground was hiding on 2026-08-21 (parasitic-ink-probe/FINDING.md):",
         "  as soon as at least 0.5% foreign ink enters the zone, that sensor declares an EMPTY",
         "  field FILLED in 1.000 of cases [0.975, 1.000] over n=151, against 0.272 for the union",
         "  of the word sensors, 0.185 full page and 0.106 per zone. These are false negatives,",
         "  the expensive side of the asymmetry. The switch is a cliff sitting on the published",
         "  threshold of 0.345%, and the two populations do not overlap by a single reading: the",
         "  sensor fires 97 times out of 97 up to 0.323% added ink and 0 times out of 167 from",
         "  0.380% on. No grey zone, a step. For that field 0.35% is a 9 x 8 px speck at 200 dpi,",
         "  a piece of dust on the glass; a pen stroke barely spilling out of the neighbouring",
         "  field already adds 0.61%.",
         "  THE SENSOR AND THE THRESHOLD WERE NOT CHANGED, and that is the right call as long as",
         "  the measurement is a probe: one field, two cells, three parasite shapes. It shows a",
         "  choice was settled on biased ground, it is not enough to fix a threshold. Changing it",
         "  requires replaying this grid with parasitic ink as a FIFTH FACTOR, and that is the",
         "  first measurement job still open.",
         "- Precision depends on prevalence. The curves give it at "
         f"{PREVALENCE:.0%} faulty dossiers, an ASSUMED value and not a measured one.",
         ""]
    followup = os.path.join(ROOT, "grid", "results", "followup.json")
    if os.path.exists(followup):
        d = json.load(open(followup))
        c, t, cu = d["sets"]["corner"], d["sets"]["control"], d["combined"]
        co = d["corner"]
        l += ["## Outside-protocol follow-up: the only cell where the tool misses something", "",
              "OUTSIDE THE PROTOCOL, and that has to be said before the numbers. The published",
              "thresholds come from a strict rule: two seeds calibrate, the third is never looked",
              "at before the number is written. This follow-up's seeds were drawn AFTER seeing",
              "where the tool was missing, on a cell chosen because it was missing. They move no",
              "threshold and enter no figure published elsewhere. They answer one question only:",
              "was n=18 enough to conclude.", "",
              f"Cell: {co['dpi']} dpi, JPEG {co['jpeg']}, noise sigma {co['sigma']}, check "
              f"{d['check']}, published threshold {d['threshold']}.", "",
              "| set | recall | 95% CI | positives |",
              "|---|---|---|---|",
              f"| original seeds (11, 23, 37) | {d['sets']['original']['recall']:.4f} | "
              f"[{d['sets']['original']['ci'][0]:.3f}, {d['sets']['original']['ci'][1]:.3f}] | "
              f"{d['sets']['original']['n']} |",
              f"| 12 new seeds | {c['recall']:.4f} | [{c['ci'][0]:.3f}, "
              f"{c['ci'][1]:.3f}] | {c['n']} |",
              f"| COMBINED | {cu['recall']:.4f} | [{cu['ci'][0]:.3f}, {cu['ci'][1]:.3f}] | "
              f"{cu['n']} |", "",
              f"The point estimate climbs from {d['sets']['original']['recall']:.3f} to "
              f"{cu['recall']:.3f}, the regression to the mean expected of an n=18, but the UPPER",
              f"bound stays at {cu['ci'][1]:.3f}, below the {RECALL_FLOOR:.0%} floor. This is not",
              "sampling noise: the check really does miss something here.", "",
              "A CONTROL, and it is what makes the twelve seeds interpretable. Same cell, same",
              "twelve seeds, only the compression changes:", "",
              f"- JPEG {co['jpeg']}: {c['tp']}/{c['n']} = {c['recall']:.4f}",
              f"- JPEG 30: {t['tp']}/{t['n']} = {t['recall']:.4f}", "",
              "So the new seeds are not harder, it is the compression. HEAVY compression erases",
              "the sensor's grain; light compression keeps it, and at high resolution that grain",
              "is fine enough to be read as character structure. That part of the mechanism is",
              "MEASURED.", "",
              "THE REAL SHAPE IS A CONJUNCTION OF FOUR FACTORS, not two:", "",
              f"- angle below {cu['angle_step']} deg: {cu['angle_below_step'][0]}/"
              f"{cu['angle_below_step'][1]} = {cu['angle_below_step'][2]:.4f}",
              f"- angle at {cu['angle_step']} deg or above: {cu['angle_above_step'][0]}/"
              f"{cu['angle_above_step'][1]} = {cu['angle_above_step'][2]:.4f}", "",
              f"A step, not a slope. The faulty cell is therefore {co['dpi']} dpi AND JPEG "
              f"{co['jpeg']} AND noise {co['sigma']} AND angle >= {cu['angle_step']} deg. The",
              "two-factor sweep below cannot see it as such: each pair averages over the two",
              "remaining factors, so it only shows its shadow. It serves to FIND it; it is the",
              "list of worst cells, already four-factor, that NAMES it.", "",
              "Reservation about the mechanism: the compression part is measured by the control,",
              "the angle part is ASSUMED. The hypothesis is that what counts is the MAGNITUDE of",
              "the resampling and not its presence, a deskew beyond half a degree smearing the",
              "fine grain into the thickness of the strokes. It is not tested. The deskew does",
              "apply a bicubic rotation from 0.25 deg on as well, so the lazy explanation (no",
              "resampling below 0.5 deg) is verified false.",
              "", "Reproduce: `python3 grid/corner_followup.py`.", ""]

    if crossed:
        names = [v.name for v in VARIANTS if v.check]
        l += ["## Crosstalk: who cries about the neighbour's defect", "",
              "Each cell gives the share of dossiers where the check on the ROW fires while the",
              "injected defect belongs to the COLUMN. The diagonal is empty by construction. Not",
              "every cell is a fault: a cropped page takes real fields with it, so the",
              "required-field check is right to cry there. This table serves to separate the",
              "physical consequence from the contamination.", "",
              "A UNIFORM ROW is not crosstalk: it is the check's background rate reappearing. The",
              "variants share the pieces they do not damage, so a check firing at x% on a clean",
              "dossier fires at x% on every column. What reads here are the cells that EXCEED the",
              "row.",
              "",
              "| check \\ defect | " + " | ".join(n[:14] for n in names) + " |",
              "|---|" + "---|" * len(names)]
        for check in sorted(crossed):
            cells = []
            for n in names:
                d = crossed[check].get(n)
                cells.append("." if d is None else
                             ("." if d["rate"] == 0 else f"{d['rate']:.3f}"))
            l.append(f"| {check} | " + " | ".join(cells) + " |")
        l += ["", "A dot means zero firings over "
              f"{next(iter(next(iter(crossed.values())).values()))['n']} dossiers.", ""]

    for check in sorted(results):
        r = results[check]
        pt = r["point"]
        l += [f"## {check}", ""]
        if pt is None:
            l += ["No usable measurement for this check.", ""]
            continue
        if r["validation"]["recall"] < RECALL_FLOOR:
            l += [f"WARNING: under the false positive budget of {FP_BUDGET:.1%}, the best",
                  f"attainable recall is {r['validation']['recall']:.3f}, below the",
                  f"{RECALL_FLOOR:.0%} floor. This check lets faulty dossiers through more often",
                  "than it should: it must not be presented as a guarantee.", ""]
        c, v, e = r["calibration"], r["validation"], r["overall"]
        l += [f"Retained settings: {r['settings_text']}. Threshold {r['threshold']:.4g}.", "",
              "| set | recall | 95% CI | false positives per target | 95% CI | "
              "per clean dossier | positives |",
              "|---|---|---|---|---|---|---|"]
        for label, m in (("calibration (seeds 11 and 23)", c),
                         ("VALIDATION (seed 37, never seen)", v), ("overall", e)):
            l.append(f"| {label} | {m['recall']:.3f} | [{m['recall_ci'][0]:.3f}, "
                     f"{m['recall_ci'][1]:.3f}] | {m['fpr']:.4f} | [{m['fpr_ci'][0]:.4f}, "
                     f"{m['fpr_ci'][1]:.4f}] | {m['dossier_fpr']:.4f} | {m['n_pos']} |")
        l += ["",
              "The per-dossier rate is the one the user feels: the probability that at least one",
              "alarm goes off on an entirely clean dossier. It is the one that decides whether",
              "the gate stays credible.", "",
              f"Cells below the floor: {len(r['fallen_cells'])} out of {r['n_cells']}.", ""]
        nc = r.get("uncertifiable_targets") or []
        if nc:
            l += ["Targets that cap this check, with the share of CLEAN dossiers where they fire",
                  "at the threshold it would take to miss nothing:", ""]
            for name, rate in nc:
                l.append(f"- {name}: {rate:.1%}")
            l += ["", "On those targets the tool's right answer is not \"this field is empty\" but",
                  "\"I cannot read this field\": same sensor, opposite consequences at the counter.",
                  "They stay inside the headline figure above, they are not removed to flatter",
                  "it.", ""]
        rr = r.get("restricted")
        if rr:
            l += ["A SECONDARY figure, not to be confused with the headline one: if this check is",
                  f"only asked about the {rr['kept_targets']} targets out of {rr['total_targets']}",
                  f"it can certify, it holds a recall of {rr['recall']:.3f} at {rr['fpr']:.4f}",
                  "false positives per target.", ""]
        conj = r.get("conjunctions") or {}
        worst = sorted(((k, c[0]) for k, c in conj.items() if c), key=lambda t: t[1]["recall"])
        if worst and worst[0][1]["recall"] < 1.0:
            l += ["Worst CROSSINGS of two factors. An axis-by-axis reading can lie by omission:",
                  "three marginal values all above the floor can cross into a cell that falls",
                  "below it.", ""]
            for name, c in worst[:4]:
                if c["recall"] >= 1.0:
                    continue
                l.append(f"- {name} = {c['values']}: recall {c['recall']:.3f} "
                         f"[{c['ci'][0]:.3f}, {c['ci'][1]:.3f}] over {c['n']} positives"
                         + ("  <- upper bound below the floor"
                            if c["ci"][1] < RECALL_FLOOR else ""))
            l.append("")
        cf = r.get("noisy_targets") or []
        if cf:
            l += ["Clean targets that fire AT THE RETAINED THRESHOLD, the ones that cost "
                  "credibility:", ""]
            for target, count, total in cf[:6]:
                l.append(f"- {target[0]} / {target[1]}: {count} times out of {total}")
            l.append("")
        h = r.get("outside_domain")
        if h and h["n_pos"]:
            l += [f"Outside the domain (dpi < {r['domain']}), RAW SENSORS, that is, what the tool",
                  "would do if it had no abstention rule: recall "
                  f"{h['recall']:.3f} [{h['recall_ci'][0]:.3f}, {h['recall_ci'][1]:.3f}], "
                  f"firings on a clean dossier {h['fpr']:.4f} over {h['n_neg']} targets.",
                  "Those figures therefore do not describe the product, they justify the rule: in",
                  "production a check that READS abstains below the floor instead of producing",
                  "what is read here. They are deliberately raw-sensor measurements, because a",
                  "measurement cannot depend on the behaviour it is used to tune.", ""]
            if check == "resolution":
                l += ["For THIS check, those firings outside the domain are not false positives:",
                      "it is exactly its job. It is there to say that a page scanned below the",
                      "floor must not be judged by the others.", ""]
        if r["fallen_cells"]:
            l += ["Frontier per factor, number of fallen cells over the total:", ""]
            for name, vals in r["frontier"].items():
                l.append("- " + name + ": "
                         + ", ".join(f"{v} -> {a}/{b}" for v, (a, b) in vals.items()))
            l.append("")
            worst_cells = sorted(r["fallen_cells"].items(), key=lambda kv: kv[1][0])[:6]
            l += ["The worst cells (angle, dpi, jpeg, sigma) and their recall:", ""]
            for c, (rec, n) in worst_cells:
                l.append(f"- angle {c[0]}, {c[1]} dpi, JPEG {c[2]}, sigma {c[3]}: "
                         f"recall {rec:.2f} over {n} seeds")
            l.append("")
        else:
            l += ["No cell of the explored domain drops below the floor.", ""]
        l += ["Recall per factor, at the retained threshold:", ""]
        for name, vals in r["factors"].items():
            l.append("- " + name + ": " + ", ".join(
                f"{v} -> {d['recall']:.3f} [{d['ci'][0]:.2f}, {d['ci'][1]:.2f}]"
                for v, d in vals.items()))
        l.append("")
    open(path, "w", encoding="utf-8").write("\n".join(l) + "\n")


def write_thresholds(results, path):
    d = json.load(open(path, encoding="utf-8"))
    for check, r in results.items():
        pt = r["point"]
        if pt is None:
            continue
        measurements = {
            "recall": round(r["validation"]["recall"], 4),
            "false_positives": round(r["validation"]["fpr"], 5),
            "measured_with": "seed 37, never used to choose the threshold",
            "settings": r["settings_text"],
            "measured_settings": _useful_settings(r["settings"], check),
            "curve": f"grid/results/pr_{check}.csv",
            "cells_under_floor": f"{len(r['fallen_cells'])}/{r['n_cells']}",
            "nominal_domain_dpi": r.get("domain"),
        }
        if r.get("threshold_frozen_by_definition"):
            d["thresholds"][check].update(measurements)
            d["thresholds"][check]["reading"] = reading_sentence(
                check, r["settings"], float(r["threshold"]),
                d["thresholds"][check].get("reading", ""))
            continue
        d["thresholds"][check] = {
            "value": round(float(r["threshold"]), 4),
            "origin": "grid",
            "reading": reading_sentence(check, r["settings"], float(r["threshold"]),
                                        d["thresholds"].get(check, {}).get("reading", "")),
            "settings": r["settings_text"],
            "measured_settings": _useful_settings(r["settings"], check),
            "recall": round(r["validation"]["recall"], 4),
            "false_positives": round(r["validation"]["fpr"], 5),
            "measured_with": "seed 37, never used to choose the threshold",
            "curve": f"grid/results/pr_{check}.csv",
            "cells_under_floor": f"{len(r['fallen_cells'])}/{r['n_cells']}",
            "nominal_domain_dpi": r.get("domain"),
        }
        if "floor_dpi" in r:
            d["thresholds"][check].update({
                "value": round(float(r["threshold"]), 4),
                "reading": f"fires below {-r['threshold']:.1f} estimated dpi, that is the floor "
                           f"of {r['floor_dpi']} dpi minus a margin of "
                           f"{r['estimator_margin']:.1%}; the floor is read off the recall of "
                           "the checks that depend on OCR and not off this check's own curve, "
                           "and the margin covers ten times the maximum measured error of the "
                           f"estimator ({r['max_estimator_error']:.4%})",
                "own_curve_threshold": r["own_curve_threshold"],
                "dependent_recall_by_dpi": r["dependent_recall_by_dpi"]})
    d["measured_on"] = "2026-08-21"
    d["false_positive_budget"] = FP_BUDGET
    json.dump(d, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
