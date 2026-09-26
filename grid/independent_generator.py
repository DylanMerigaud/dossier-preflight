#!/usr/bin/env python3
"""Import what an independent generator measured at the shipped thresholds, for thresholds.json.

The grid's own recall comes from the generator the thresholds were chosen on. perfect-recall-study
ran a second, independent one (arm A3: Augraphy 8.2.6's default pipeline, unmodified, on the
rendered pages of six fictional identities) and scored it at the thresholds as shipped, with no
refit. This script copies those counts, with their source, into
grid/results/independent_generator.json, which `grid/analyze.py --publish` reads so that
thresholds.json carries them next to each recall. It reads the study's committed output; it
measures nothing itself.

    python3 grid/independent_generator.py ../perfect-recall-study/results/hypotheses.json
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "grid", "results", "independent_generator.json")


def build(hypotheses, source, sha256, commit):
    cells = hypotheses["a3_cells_at_shipped_thresholds"]
    h1 = hypotheses["hypotheses"]["H1"]
    checks = {}
    for check, c in sorted(cells.items()):
        row = {"false_alarms": {"k": c["fp"], "n": c["n_neg"],
                                "rate": round(c["fp"] / c["n_neg"], 4) if c["n_neg"] else None,
                                "unit": "clean targets"}}
        if c["n"]:
            row["recall"] = {"k": c["k"], "n": c["n"], "rate": round(c["k"] / c["n"], 4),
                             "wilson_95": [round(x, 4) for x in c["interval"]["wilson_95"]]}
        checks[check] = row
    rf = checks["required_field"]
    rf["recall"]["condition"] = "pages with less than 0.05% ink in the emptied field"
    rf["recall_with_ink_in_the_emptied_field"] = {
        "k": h1["k"], "n": h1["n"], "rate": round(h1["k"] / h1["n"], 4),
        "wilson_95": [round(x, 4) for x in h1["interval"]["wilson_95"]],
        "condition": "pages where Augraphy laid at least 0.5% ink in the emptied field",
        "pages_not_measured": h1["instances_share_not_measured"],
        "unit": h1["unit"]}
    return {"what": "the shipped thresholds scored, with no refit, on an independent generator",
            "generator": "Augraphy 8.2.6 default_augraphy_pipeline(), unmodified (arm A3)",
            "source": source, "source_sha256": sha256, "source_commit": commit,
            "thresholds_sha256": hypotheses["meta"]["thresholds_sha256"],
            "checks": checks}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("hypotheses", help="perfect-recall-study results/hypotheses.json")
    ap.add_argument("--out", default=DEST)
    a = ap.parse_args()
    raw = open(a.hypotheses, "rb").read()
    study = os.path.dirname(os.path.dirname(os.path.abspath(a.hypotheses)))
    commit = subprocess.run(["git", "-C", study, "log", "-1", "--format=%H", "--",
                             "results/hypotheses.json"], capture_output=True, text=True,
                            check=True).stdout.strip()
    out = build(json.loads(raw), "perfect-recall-study results/hypotheses.json",
                hashlib.sha256(raw).hexdigest(), commit)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
