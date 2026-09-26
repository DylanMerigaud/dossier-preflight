"""The failure metric thresholds.json carries, and the thresholds it must never move.

Since v0.2.0 `recall_with_ink_on_the_damaged_field` comes from the all-shapes targeted run
(grid/results/target_parasite_all_shapes.json), with its count per shape, and each check carries
its recall on an independent generator (grid/results/independent_generator.json). Adding a
measurement must never change a threshold `value`: perfect-recall-study's preregistration froze
them at v0.1.0.
"""
import json
import os
import subprocess

import pytest

from grid import analyze
from grid.target_parasite import summarize_by_shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _thresholds_at(ref):
    out = subprocess.run(["git", "-C", ROOT, "show", f"{ref}:thresholds.json"],
                         capture_output=True, text=True)
    if out.returncode:
        pytest.skip(f"{ref} not available in this checkout")
    return json.loads(out.stdout)["thresholds"]


def test_every_threshold_value_equals_v0_1_0():
    now = json.load(open(os.path.join(ROOT, "thresholds.json"), encoding="utf-8"))["thresholds"]
    then = _thresholds_at("v0.1.0")
    assert set(now) == set(then)
    assert {c: now[c]["value"] for c in now} == {c: then[c]["value"] for c in then}
    assert {c: now[c].get("measured_settings") for c in now} == \
        {c: then[c].get("measured_settings") for c in then}


def test_shipped_failure_metric_is_the_all_shapes_run():
    if not os.path.exists(analyze.TARGET_PARASITE_ALL_SHAPES):
        pytest.skip("all-shapes aggregate absent")
    th = json.load(open(os.path.join(ROOT, "thresholds.json"), encoding="utf-8"))["thresholds"]
    d = json.load(open(analyze.TARGET_PARASITE_ALL_SHAPES, encoding="utf-8"))
    for check, c in d["checks"].items():
        s = c["sensors"][analyze._sensor_of(c["sensors"])]
        want = {lv: round(v["variant"]["rate"], 4) for lv, v in s["pooled"].items()
                if float(lv)}
        assert th[check]["recall_with_ink_on_the_damaged_field"] == want, check
        detail = th[check]["ink_on_the_damaged_field"]
        assert set(detail["by_shape"]) == set(d["shapes"]) == {"fold", "speck", "stroke"}
        for shape, levels in detail["by_shape"].items():
            for lv, v in levels.items():
                assert v["n"] == s["by_shape"][shape][lv]["variant"]["n"]
                assert v["k"] == s["by_shape"][shape][lv]["variant"]["fired"]
    assert th["required_field"]["recall_on_an_independent_generator"][
        "recall_with_ink_in_the_emptied_field"]["n"] > 0


def test_summarize_by_shape_pools_and_splits():
    rows = []
    for shape, fires in (("fold", True), ("speck", False), ("stroke", False)):
        for side in ("variant", "clean"):
            rows.append({"variant": "empty_required_field", "zone": "City or Town",
                         "parasite": 0.01, "shape": shape, "side": side,
                         "fires": fires and side == "variant"})
    rows.append({"variant": "empty_required_field", "zone": "City or Town", "parasite": 0.0,
                 "shape": None, "side": "variant", "fires": True})
    out = summarize_by_shape(rows, None, fired=lambda r, ref, check, settings: r["fires"])
    ink = out["required_field"]["sensors"]["ink"]
    assert ink["pooled"]["0.01"]["variant"]["fired"] == 1
    assert ink["pooled"]["0.01"]["variant"]["n"] == 3
    assert ink["pooled"]["0.0"]["variant"]["n"] == 1
    assert ink["by_shape"]["fold"]["0.01"]["variant"]["fired"] == 1
    assert ink["by_shape"]["speck"]["0.01"]["variant"]["fired"] == 0
    assert "0.0" not in ink["by_shape"]["fold"]
