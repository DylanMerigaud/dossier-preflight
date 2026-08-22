"""Two clocks. The same piece can be good for one dossier and expired for the other.

This is the most unfair rejection reason at the counter: the piece was valid when the dossier
was assembled, and it is not on the day it is filed. A tool with only one implicit clock, the
day it happens to run, cannot even ask the question.
"""
from preflight.checks import evaluate


def expiry_fires(readings, reference, name, clock):
    findings = evaluate(readings[name], reference, clock)
    return any(c.fires for c in findings if c.check == "expiry")


def test_the_expired_piece_is_rejected_at_filing(readings, reference):
    assert expiry_fires(readings, reference, "expired_date", "filing")


def test_the_same_piece_passes_at_the_admissibility_date(readings, reference):
    """Same file, same instant, same reading: only the clock changes."""
    assert not expiry_fires(readings, reference, "expired_date", "admissibility")


def test_a_clean_dossier_passes_at_both_clocks(readings, reference):
    assert not expiry_fires(readings, reference, "clean", "filing")
    assert not expiry_fires(readings, reference, "clean", "admissibility")


def test_the_two_clocks_really_straddle_the_expiry_date(reference):
    """Without that bracketing the previous test would pass for the wrong reason."""
    expired = reference.expiry["expired_expiry_date"]
    assert reference.clock("admissibility") < expired < reference.clock("filing")
