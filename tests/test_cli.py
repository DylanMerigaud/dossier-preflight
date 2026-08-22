"""The entry point returns THREE verdicts, and it must never collapse two into one.

A dossier defect and an unreadable page call for opposite actions at the counter: redo the
dossier, or redo the scan. A binary exit code would tell someone whose dossier may be perfect
and whose scan is bad that their dossier has a defect.

The two-clock test lives here at the END OF THE CHAIN, and not only at check level: it is the
one property this repo tools and nothing else does, and it is worth nothing if the command
line loses it on the way.
"""
import pytest

from preflight.__main__ import main
from preflight.fixtures import build
from preflight.templates import ROOT


@pytest.fixture(scope="module")
def dossiers(reference, tmp_path_factory):
    """The PDFs on disk, as a user would have them: files, not objects."""
    dest = str(tmp_path_factory.mktemp("cli"))
    return {name: {p.id: p.pdf for p in build(reference, name, dest).pieces}
            for name in ("clean", "expired_date")}


def run(dossiers, variant, clock, pieces=None, extra=()):
    paths = dossiers[variant]
    args = [f"{ROOT}/fixtures/reference.yaml", "--clock", clock]
    for pid in (pieces or paths):
        args += ["--piece", f"{pid}={paths[pid]}"]
    return main(args + list(extra))


def test_an_expired_piece_at_filing_is_a_dossier_defect(dossiers, capsys):
    assert run(dossiers, "expired_date", "filing") == 1
    out = capsys.readouterr().out
    assert "DOSSIER DEFECTS" in out
    assert "expiry" in out


def test_the_same_piece_passes_at_the_other_clock(dossiers, capsys):
    """THE two-clock test, end to end. Same dossier, same instant, same file: only the clock
    changes and the verdict flips. If this falls at the same time as the previous one, the CLI
    lost the clock; if it falls alone, it is the expiry check."""
    assert run(dossiers, "expired_date", "admissibility") == 0
    assert "No check fires" in capsys.readouterr().out


def test_an_unreadable_page_is_not_a_dossier_defect(dossiers, capsys):
    """Exit 2 and not 1: the dossier is clean, it is the scan that cannot be read. And the
    word "compliant" must never appear where "undecidable" belongs."""
    assert run(dossiers, "clean", "filing", pieces=["identity"], extra=["--dpi", "96"]) == 2
    out = capsys.readouterr().out
    assert "CANNOT READ" in out and "ABSTENTIONS" in out
    assert "DOSSIER DEFECTS" not in out


def test_a_piece_not_supplied_is_reported_as_not_judged(dossiers, capsys):
    """Staying silent about an absent piece would amount to declaring it compliant."""
    assert run(dossiers, "clean", "filing", pieces=["tax"]) == 0
    out = capsys.readouterr().out
    assert "NOT SUPPLIED" in out and "employment" in out and "identity" in out


# The cases below read no PDF at all: they cost zero seconds of OCR.

def test_the_clock_is_mandatory():
    """Without it the tool would take an implicit date and throw the property away in
    silence. The code is 64 (EX_USAGE) and not 2, which means "I cannot read"."""
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--piece", "tax=/dev/null"])
    assert e.value.code == 64


def test_an_unknown_clock_names_the_ones_that_exist():
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "tomorrow",
              "--piece", "tax=/dev/null"])
    assert "filing" in str(e.value.code) and "admissibility" in str(e.value.code)


def test_an_iso_date_can_stand_in_for_a_clock(dossiers):
    """Not every useful clock is declared in advance."""
    assert run(dossiers, "expired_date", "2026-01-01", pieces=["employment"]) == 0
    assert run(dossiers, "expired_date", "2026-12-31", pieces=["employment"]) == 1


def test_an_undeclared_piece_is_refused():
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "filing",
              "--piece", "passport=/dev/null"])
    assert "not declared" in str(e.value.code)


def test_without_a_piece_it_does_not_manufacture_a_fixture():
    """An entry point that generated its own dossier would look like it works on a real one."""
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "filing"])
    assert "no piece supplied" in str(e.value.code)
