"""Run the checks on a REAL dossier: your own scans, not fixtures.

    python -m preflight fixtures/reference.yaml \
        --clock filing \
        --piece tax=scans/w9.pdf --piece employment=scans/i9.pdf

THREE VERDICTS AND NOT TWO, and that is the most recent measurement result in this repo. A
check that READS abstains on a piece below the resolution floor: its finding carries a score
of None, which means UNDECIDABLE and never "compliant". The two call for opposite actions at
the counter: a defect says REDO THE DOSSIER, an unreadable page says REDO THE SCAN. Collapsing
both into one exit code would tell someone whose dossier may be perfect and whose scan is bad
that their dossier has a defect.

    0   no finding
    1   at least one DOSSIER DEFECT, that is, any check other than resolution
    2   no dossier defect, but the tool cannot read: resolution fired and/or checks abstained
    64  usage error (EX_USAGE), so it cannot be confused with 2

The resolution check sits on the SCAN side and not the DOSSIER side, and that is not a matter
of taste: LIMITES.md already says so for that check alone, it answers "I cannot read this
page" and not "this page is at fault". Filing it under defects would return 1 on a possibly
perfect dossier that was badly scanned. Abstention has exactly the same condition as that
check firing (both read the same floor), so a code reserved for abstention alone would never
occur: the two share code 2, and the text tells them apart.

THE CLOCK IS MANDATORY, and that is not ceremony. The same piece is good for one dossier and
expired for another at the very same instant: the reference declares its clocks by name
(filing, admissibility) and a tool that silently took today's date would throw away the one
property this repo tools and others do not.

KNOWN LIMIT OF --dpi. This is the RASTERISATION dpi of the PDF, not the capture dpi of the
scan. On a PDF that already contains an image, asking for 300 here does not recreate
information the scanner never captured: the page is rendered larger, and the resolution check
then estimates the resolution of the RENDER. Rasterising high therefore does not push a bad
scan past the floor, it moves the question. The default is CANON_DPI, the resolution of the
canonical frame, and it is the value under which every figure in LIMITES.md was measured.
"""
import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, replace

from . import CANON_DPI
from .checks import CHECKS, evaluate
from .degradation import Degradation
from .templates import ROOT
from .reading import read_piece, blank
from .reference import load_reference


@dataclass(frozen=True)
class ScannedPiece:
    """The minimum `read_piece()` asks for. Deliberately not the BuiltPiece of fixtures.py:
    the production path must not depend on the synthetic dossier generator, or the entry point
    would only ever run on manufactured dossiers while looking like it works on a real one."""
    id: str
    template: object
    pdf: str


# No degradation at all: no rotation, no noise, no blur, no recompression. `apply()` then
# returns the page exactly as it was rasterised. The grid degrades, production does not.
PRISTINE = Degradation(angle=0.0, jpeg=100, sigma=0.0, blur=0.0)

# The only check that, by firing, talks about the SCAN and not the DOSSIER.
SCAN_SIDE = "resolution"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        """argparse exits 2 by default, and 2 means "I cannot read" here."""
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(64)


def _clock(ref, value):
    """A name declared by the reference, or an ISO date. Never an implicit today."""
    if value in ref.clocks:
        return ref, value
    try:
        date = dt.date.fromisoformat(value)
    except ValueError:
        known = ", ".join(sorted(ref.clocks)) or "none"
        raise SystemExit(f"unknown clock {value!r}. Declared clocks: {known}. "
                         f"Otherwise give an ISO date (YYYY-MM-DD).")
    return replace(ref, clocks={**ref.clocks, value: date}), value


def _pieces(ref, pairs):
    """id=path, validated against what the reference declares."""
    declared = dict(ref.pieces)
    out = {}
    for c in pairs:
        if "=" not in c:
            raise SystemExit(f"--piece expects id=path, got {c!r}")
        pid, path = c.split("=", 1)
        if pid not in declared:
            raise SystemExit(f"piece {pid!r} is not declared by the reference. "
                             f"Declared: {', '.join(declared)}")
        if not os.path.exists(path):
            raise SystemExit(f"piece {pid!r}: file not found {path!r}")
        out[pid] = ScannedPiece(pid, ref.templates[declared[pid]], os.path.abspath(path))
    return out


def sort_findings(findings):
    """Three piles: dossier defect, unreadable page, and the rest."""
    defects = [c for c in findings if c.fires and c.check != SCAN_SIDE]
    unreadable = [c for c in findings
                  if (c.fires and c.check == SCAN_SIDE) or c.score is None]
    silent = [c for c in findings if not c.fires and c.score is not None]
    return defects, unreadable, silent


def _lines(findings):
    return [f"  {c.check:17s} {c.piece:12s} {str(c.target)[:26]:28s} {c.detail}"
            for c in sorted(findings, key=lambda c: (c.piece, c.check))]


def _text(findings, ref, clock_name, dpi, supplied, missing, show_all):
    defects, unreadable, silent = sort_findings(findings)
    l = [f"dossier {ref.dossier}, clock {clock_name} ({ref.clock(clock_name)}), "
         f"{len(supplied)} piece(s) rendered at {dpi} dpi"]
    if missing:
        l += ["", "PIECES NOT SUPPLIED, therefore NOT JUDGED (no finding concerns them): "
              + ", ".join(sorted(missing))]
    if defects:
        l += ["", f"DOSSIER DEFECTS ({len(defects)}). The counter would reject this, "
              "REDO THE DOSSIER:"] + _lines(defects)
        if {c.check for c in defects} & {"cropped_page", "rotated_page"}:
            l += ["", "A cropped or rotated page can come from the SCAN and not from the "
                  "dossier. These two checks sit on the dossier side because the grid measures "
                  "them on genuinely damaged pages, not because we know what damaged them."]
    if unreadable:
        abstained = [c for c in unreadable if c.score is None]
        l += ["", f"THE TOOL CANNOT READ ({len(unreadable)}). This is NOT \"compliant\", "
              "REDO THE SCAN:"] + _lines(unreadable)
        if abstained:
            l += ["", f"{len(abstained)} of these findings are ABSTENTIONS: the check refused "
                  "to rule on a piece below the resolution floor. Undecidable does not mean "
                  "compliant."]
        if defects:
            l += ["", "WARNING: some checks stayed silent because they could not read. The "
                  "list of defects above is therefore not complete."]
    if show_all:
        l += ["", f"DID NOT FIRE ({len(silent)}):"] + _lines(silent)
    l.append("")
    if not defects and not unreadable:
        l += ["No check fires.",
              "THIS IS NOT A GUARANTEE. The recall and false positive rate of every check, the",
              "domain where they hold, and what the measurement does not cover are all in",
              "LIMITES.md. In particular: the measurement rests on ONE fictional dossier of",
              "three forms degraded SYNTHETICALLY, and no real scan ever entered it."]
    return "\n".join(l)


def main(argv=None):
    ap = Parser(prog="python -m preflight",
                description="Counter rejection checks, run on your own scans.",
                epilog="Exit codes: 0 no finding, 1 dossier defect, "
                       "2 unreadable page or abstaining check, 64 usage error.")
    ap.add_argument("reference", help="YAML describing the expected dossier and its pieces")
    ap.add_argument("--piece", action="append", default=[], metavar="ID=PATH",
                    help="the scan of a piece declared by the reference, repeatable")
    ap.add_argument("--clock", required=True, metavar="NAME|YYYY-MM-DD",
                    help="MANDATORY: a clock name from the reference, or an ISO date. "
                         "A piece that is good at one date is expired at another.")
    ap.add_argument("--dpi", type=int, default=CANON_DPI,
                    help=f"rasterisation dpi of the PDF, not the capture dpi of the scan "
                         f"(default {CANON_DPI})")
    ap.add_argument("--root", default=ROOT,
                    help="directory holding templates/ and corpus/ (default: the repo root)")
    ap.add_argument("--all", action="store_true", dest="show_all",
                    help="also list the checks that do not fire")
    ap.add_argument("--json", action="store_true", help="machine readable output")
    a = ap.parse_args(argv)

    if not a.piece:
        raise SystemExit("no piece supplied. Give at least one --piece ID=PATH. This entry "
                         "point reads real scans, it does not generate a fixture.")
    ref = load_reference(a.reference, root=a.root)
    ref, clock_name = _clock(ref, a.clock)
    pieces = _pieces(ref, a.piece)
    missing = {p for p, _ in ref.pieces} - set(pieces)

    for _, template_name in ref.pieces:
        blank(ref.templates[template_name])
    readings = {pid: read_piece(p, replace(PRISTINE, dpi=a.dpi)) for pid, p in pieces.items()}
    findings = evaluate(readings, ref, clock_name)
    defects, unreadable, _ = sort_findings(findings)

    if a.json:
        print(json.dumps({
            "dossier": ref.dossier, "clock": clock_name,
            "clock_date": str(ref.clock(clock_name)), "render_dpi": a.dpi,
            "pieces_judged": sorted(pieces), "pieces_not_supplied": sorted(missing),
            "checks": list(CHECKS),
            "verdict": "defect" if defects else ("unreadable" if unreadable else "no_finding"),
            "findings": [{"check": c.check, "piece": c.piece, "target": str(c.target),
                          "score": c.score, "fires": c.fires,
                          "undecidable": c.score is None, "detail": c.detail}
                         for c in findings]}, ensure_ascii=False, indent=2))
    else:
        print(_text(findings, ref, clock_name, a.dpi, pieces, missing, a.show_all))
    return 1 if defects else (2 if unreadable else 0)


if __name__ == "__main__":
    sys.exit(main())
