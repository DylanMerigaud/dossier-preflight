"""Thresholds live in ONE file, and each one carries where it came from.

A "spike" threshold is a tuning value, not a measurement: it was picked by hand on a single
example. A "grid" threshold was READ off a precision/recall curve, and its row says so along
with the false positive rate it holds. As long as the origin column says "spike", the tool is
not measured, and the README must not pretend otherwise.
"""
import json
import os

from .templates import ROOT

FILE = os.path.join(ROOT, "thresholds.json")
_MEMO = {}


def _read(path):
    if path not in _MEMO:
        _MEMO[path] = json.load(open(path, encoding="utf-8"))
    return _MEMO[path]


def load_thresholds(path=FILE):
    return {k: v["value"] for k, v in _read(path)["thresholds"].items()}


def load_settings(path=FILE):
    """The MEASURED settings, per check.

    Without this return path the grid would pick a sensor and the code would keep using a
    different one: the A/B duel would only ever produce a table. A missing setting leaves the
    spike value in place, and the threshold's origin then says it is not measured.

    This is not hypothetical. It is exactly how the crosstalk bug of 2026-08-21 happened: the
    fixture test passed an explicit Settings(), which forced the spike defaults on all nine
    checks, while thresholds.json carried a threshold read under a different sensor. A
    threshold and its sensor are one pair, and reading one without the other compares an ink
    percentage against a character count.
    """
    return {k: dict(v.get("measured_settings") or {})
            for k, v in _read(path)["thresholds"].items()}


def raw(path=FILE):
    return _read(path)
