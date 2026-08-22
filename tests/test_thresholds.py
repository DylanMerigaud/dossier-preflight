"""A threshold must say where it comes from. As long as it says "spike", the tool is not measured."""
from preflight.checks import CHECKS
from preflight.thresholds import raw, load_thresholds

ORIGINS = {"spike", "provisional", "definition", "grid"}


def test_every_check_has_a_threshold():
    assert set(load_thresholds()) == set(CHECKS)


def test_every_threshold_declares_its_origin_and_how_to_read_it():
    for name, s in raw()["thresholds"].items():
        assert s["origin"] in ORIGINS, f"{name}: unknown origin {s['origin']!r}"
        assert s["reading"].strip(), f"{name}: threshold with no reading sentence"


def test_a_measured_threshold_cites_its_curve():
    """A value claiming to be measured must point at the measurement, or it claims it for nothing."""
    for name, s in raw()["thresholds"].items():
        if s["origin"] == "grid":
            assert s.get("curve"), f"{name}: origin grid with no curve reference"
            assert "false_positives" in s, f"{name}: origin grid with no held false positive rate"


def test_a_definition_threshold_is_never_fitted():
    """The central trap of "read the threshold off the curve", and it was paid for.

    "Expired" means the date has passed: this threshold is zero days, it encodes MEANING, it is
    not a parameter. Left free, the optimiser had moved it to -207.5 days because the
    reference's healthy piece expires in 2027 and any threshold between -497 and -110 separates
    the data perfectly. The tool would have declared a piece expired seven months before it was,
    with a recall of 1.000 to back it up. A curve only knows the data it was given.
    """
    v = raw()["thresholds"]["expiry"]
    assert v["origin"] == "definition"
    assert v["value"] == 0.0, "one day either way here changes the meaning of the word expired"
    assert v.get("why_frozen"), "a frozen threshold with no written reason will get refitted"
