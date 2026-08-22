#!/usr/bin/env python3
"""FOLLOW-UP measurement on the only cell of the nominal domain where the tool misses something.

OUTSIDE THE PROTOCOL, and that has to be said before the numbers. The grid publishes its
thresholds under a strict rule: two seeds calibrate, the third is never looked at before the
number is written. These seeds were drawn AFTER seeing where the tool was missing, on a cell
chosen because it was missing. They therefore cannot move a threshold nor enter any published
figure: they answer one question only, the one about sample size.

    n=18 on the original seeds gave 0.833, with an interval so wide that nobody could say
    whether the check really missed or three unlucky draws had simply followed each other.

Two sets, twelve new seeds each, one single thing changing between them:
    corner   300 dpi, JPEG 95, noise 12
    control  300 dpi, JPEG 30, noise 12
The control is what separates "my seeds are hard" from "it is the compression". Without it the
twelve new seeds prove nothing.

    python3 grid/corner_followup.py    # writes grid/results/followup.json
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grid.analyze import load, damaged_targets, complete_dossiers, target_scores, wilson
from preflight.checks import measured_settings
from preflight.fixtures import VARIANTS
from preflight.reference import load_reference
from preflight.thresholds import load_thresholds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "forbidden_value"
CORNER = (300, 95, 12.0)          # dpi, JPEG quality, noise sigma
ANGLE_STEP = 0.5                  # the angle at which recall drops off


def recalls(dossiers, ref, settings, threshold, targets, var):
    """Returns (tp, n, per angle)."""
    by_angle = collections.defaultdict(lambda: [0, 0])
    tp = n = 0
    for key, dossier in dossiers.items():
        scores = target_scores(dossier[var.name], ref, CHECK, settings)
        pos = {k: v for k, v in scores.items() if k in targets} or scores
        for x in pos.values():
            n += 1
            tp += x > threshold
            g = by_angle[key[0]]
            g[0] += x > threshold
            g[1] += 1
    return tp, n, {a: tuple(g) for a, g in sorted(by_angle.items())}


def main():
    ref = load_reference()
    threshold = load_thresholds()[CHECK]
    settings = measured_settings()[CHECK]
    var = next(v for v in VARIANTS if v.check == CHECK)
    targets = damaged_targets(var, ref)
    base = os.path.join(ROOT, "grid", "measurements")

    sets = {}
    main_set = complete_dossiers(load(os.path.join(base, "measurements.jsonl")))
    # Level 0 only: this follow-up measures a cell of the ORIGINAL grid, and the fifth factor
    # added three parasited copies of that same cell to the same file. Pooling them would mix
    # two different questions and quietly quadruple n.
    sets["original"] = {k: v for k, v in main_set.items()
                        if (k[1], k[2], k[3]) == CORNER and not k[5]}
    for name, path in (("corner", "followup/corner.jsonl"),
                       ("control", "followup/control.jsonl")):
        sets[name] = complete_dossiers(load(os.path.join(base, path)))

    out = {"check": CHECK, "threshold": threshold, "settings": settings.text_sensor,
           "corner": {"dpi": CORNER[0], "jpeg": CORNER[1], "sigma": CORNER[2]},
           "outside_protocol": "seeds drawn after seeing where the tool was missing; they move "
                               "no threshold and enter no published figure",
           "sets": {}}
    for name, d in sets.items():
        tp, n, by_angle = recalls(d, ref, settings, threshold, targets, var)
        below = [g for a, g in by_angle.items() if a < ANGLE_STEP]
        above = [g for a, g in by_angle.items() if a >= ANGLE_STEP]
        out["sets"][name] = {
            "n_pairs": len(d), "tp": tp, "n": n, "recall": tp / max(1, n),
            "ci": list(wilson(tp, n)),
            "by_angle": {str(a): list(g) for a, g in by_angle.items()},
            "angle_below_step": [sum(g[0] for g in below), sum(g[1] for g in below)],
            "angle_above_step": [sum(g[0] for g in above), sum(g[1] for g in above)],
        }
    o, c = out["sets"]["original"], out["sets"]["corner"]
    tp, n = o["tp"] + c["tp"], o["n"] + c["n"]
    below = [o["angle_below_step"][i] + c["angle_below_step"][i] for i in (0, 1)]
    above = [o["angle_above_step"][i] + c["angle_above_step"][i] for i in (0, 1)]
    out["combined"] = {"tp": tp, "n": n, "recall": tp / n, "ci": list(wilson(tp, n)),
                       "angle_below_step": below + [below[0] / below[1]],
                       "angle_above_step": above + [above[0] / above[1]],
                       "angle_step": ANGLE_STEP}
    dest = os.path.join(ROOT, "grid", "results", "followup.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"corner q95  {c['tp']}/{c['n']} = {c['recall']:.4f} {[round(x, 3) for x in c['ci']]}")
    print(f"control q30 {out['sets']['control']['tp']}/{out['sets']['control']['n']} = "
          f"{out['sets']['control']['recall']:.4f}")
    print(f"COMBINED    {tp}/{n} = {tp/n:.4f} {[round(x, 3) for x in out['combined']['ci']]}")
    print(f"  angle < {ANGLE_STEP}: {below[0]}/{below[1]}   "
          f"angle >= {ANGLE_STEP}: {above[0]}/{above[1]}")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
