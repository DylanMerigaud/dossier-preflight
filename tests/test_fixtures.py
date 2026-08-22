"""Each variant carries ONE defect: the targeted check must fire, the others must stay silent.

The second half of that sentence is the one that matters. A check that fires on its
neighbour's variant is a false positive, and a false positive costs the credibility of the
whole gate: a rule that cries wolf makes every rule next to it get skimmed.
"""
import pytest

from preflight.checks import CHECKS, evaluate
from preflight.fixtures import VARIANTS

# One single tolerance, and it is MEASURED by the grid, not assumed.
#
# It used to cover required_field and consistency on the 72 dpi variant. Both left, each for a
# measured reason:
#   required_field: the grid retained the INK sensor, which does not ask to read anything.
#     Crosstalk measured on low_resolution: 0/864 dossiers of the domain.
#   consistency: checks that READ now abstain on a piece below the floor, instead of comparing
#     tokens they failed to read. Before that rule, 456/864. After it, 0/864.
#
# What remains is required_checkbox, 18/864, that is 2.1%. This variant's tax piece is rendered
# at 72 dpi: box c1_1[0] is eight pixels across there, and the central disc that measures its
# ink no longer fits inside the outline. This check does not read, so it does not abstain, and
# extending abstention to every coordinate-based check would disable it between 96 and 148 dpi
# where the grid nevertheless measures it at 1.000 recall. The tolerance is therefore the right
# place to carry that remainder, and its figure is in LIMITS.md.
#
# The fixture cell is one of the 270 out of 288 where this firing does not happen: the test
# would pass even without this line, and that is exactly why the line must be written. A test
# that is green by luck of the draw encodes a claim the grid contradicts elsewhere.
TOLERATED = {"low_resolution": {"required_checkbox"}}


def fired(readings, reference, name, clock="filing"):
    """No settings are passed: we want the PRODUCTION path, the one that reads thresholds.json.

    A test passing Settings() would short-circuit the sensors and thresholds the grid measured
    and would test the spike values instead, which is to say not the product.
    """
    findings = evaluate(readings[name], reference, clock)
    return {c for c in CHECKS if any(x.fires for x in findings if x.check == c)}


def test_a_clean_dossier_fires_nothing(readings, reference):
    assert fired(readings, reference, "clean") == set()


@pytest.mark.parametrize("variant", [v for v in VARIANTS if v.check], ids=lambda v: v.name)
def test_the_targeted_check_fires(readings, reference, variant):
    assert variant.check in fired(readings, reference, variant.name)


@pytest.mark.parametrize("variant", [v for v in VARIANTS if v.check], ids=lambda v: v.name)
def test_the_other_checks_stay_silent(readings, reference, variant):
    others = fired(readings, reference, variant.name) - {variant.check}
    assert others <= TOLERATED.get(variant.name, set()), f"crosstalk: {sorted(others)}"


def test_every_check_is_covered_by_a_variant():
    """A check with no variant has neither a measurable true positive nor a false negative."""
    targeted = {v.check for v in VARIANTS if v.check}
    assert targeted == set(CHECKS)
