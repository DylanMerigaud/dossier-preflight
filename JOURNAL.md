# Journal

## 2026-08-21

### What is green

    python3 spike/proof.py            exit 0, findings unchanged since the first commit
    python3 -m pytest tests/ -q       64 tests
    python3 grid/run.py               13,824 readings, 121 min on 13 workers
    python3 grid/analyze.py           9 curves, LIMITS.md, thresholds.json

The corpus went from one to three blank forms (W-9, I-9, Cerfa 14011*02), with a manifest gate
that fails in both directions. One fictional dossier of three pieces, one clean dossier and nine
variants each carrying ONE defect. Nine checks, each with a continuous score and a threshold read
off a curve.

### The grid's figures

384 cells (6 angles x 4 dpi x 4 JPEG qualities x 4 noise levels) x 3 seeds = 1152 dossiers, 864
of them inside the nominal domain. Threshold chosen on seeds 11 and 23, published figure measured
on seed 37, never looked at beforehand.

Nominal domain: **scanning at 150 dpi or more**. The eight checks other than forbidden values
hold 1.000 recall at 0.0000 false positives per target. Forbidden values hold 0.997 at 0.00058,
with 6 cells out of 288 below the 95% floor.

The rate a user feels: **4 dossiers out of 864 entirely clean ones carry at least one alarm,
0.46%**, all from the forbidden-value check.

Crosstalk measured over the whole grid: one single non-zero cell, required_checkbox at 2.1% on
the 72 dpi variant (the box is eight pixels across, the central disc no longer fits inside the
outline).

### The retained thresholds, and why those

| check | threshold | why that one |
|---|---|---|
| required_field | -0.345% added ink | ink sensor, duel winner at 0 false positives against 0.0003 for OCR |
| required_checkbox | delta -14.38 | disc at 0.30 of the side, ink threshold 128, best of the 12 settings |
| signature | diagonal -342 px | TIE, not broken, between ink and components; the choice is unsupported |
| expiry | 0 days | FROZEN BY DEFINITION, see below |
| consistency | 0.394 | fuzzy token overlap, per zone OCR, confidence 0 |
| forbidden_value | 0.721 similarity | the only check that does not hold 1.000 |
| resolution | -148.5 dpi | the OTHER checks' floor minus 1%, not its own curve |
| cropped_page | 0.088 | coverage of the blank's ink |
| rotated_page | 0.359 | correlation margin between quarter turns |

### What building it cost, and what is worth keeping

**Four times, a measurement nearly measured my own bug instead of the tool.** Every time the
symptom looked like a physical limit, and every time it was a manufacturing defect:

1. AcroForm filling on the XFA forms did not print three Cerfa fields and glued the others to
   their border. Text is now laid down by a vector overlay, at the position the form DECLARES.
2. COMB fields (one box per character, a flag the PDF declares) received the string continuously
   over the separators. Unreadable by construction.
3. Bringing the scan into a canonical 200 dpi frame resampled it, and destroyed small boxed text
   at 300 dpi. The blank comes to the scan now.
4. The required-field check measured the OCR CONFIDENCE of the best word. A border read as three
   vertical bars at confidence 97 made an EMPTY field look filled. It counts alphanumeric
   characters now.

**Three times, a loop manufactured flattering figures.** Excluding the awkward targets BEFORE
choosing the threshold gave 100% recall on the single surviving target. Defining certifiability
at full recall let one aberrant positive drag the threshold down to 0.11 similarity. Abstention
below the floor, left enabled during the domain search, made that domain fall from 150 to 96 dpi.
The rule that comes out of it: a measurement cannot depend on the behaviour it is used to tune.

**The expiry threshold was nearly fitted, and the two-clock test caught it.** The grid had moved
it to -207.5 days: the reference's healthy piece expires in 2027, so any threshold between -497
and -110 separates the data perfectly, and the optimiser took the middle of the plateau. The tool
would have declared a piece expired seven months before it was, with a recall of 1.000 to back it
up. That threshold encodes the MEANING of the word expired: it is frozen at zero, and a test
guards the invariant.

**The spike had settled at n=1 in the wrong direction.** It concluded ink was the wrong sensor
for text. On the grid, ink wins the duel. The culprit was not the sensor but its confidence floor
at 40, which threw away fields that were filled but badly read.

### The parasitic-ink probe, and the fault it revealed

The grid never ADDS foreign ink inside a zone, so the ink sensor won its duel on ground that
favours it. A 528-reading probe measured what that ground was hiding: as soon as at least 0.5%
foreign ink enters the zone, the retained sensor declares an EMPTY field FILLED in **1.000** of
cases [0.975, 1.000] over n=151, against 0.272 for the union of word sensors. Those are false
negatives, the expensive side of the asymmetry.

The switch is a cliff sitting on the published threshold of 0.345%, with **no overlap at all**:
97 firings out of 97 up to 0.323% added ink, 0 out of 167 from 0.380% on. For that field, 0.35%
is a 9 x 8 px speck at 200 dpi. A piece of dust.

The sensor and the threshold were NOT changed. The probe covers one field, two cells and three
hand-drawn shapes: it shows a choice was settled on biased ground, it does not fix a threshold.

### Two faults of the same family, found the same day

Both times a published number had been measured under a configuration other than the one that
ships, and both are now fixed structurally rather than case by case.

1. **A threshold in ink percent compared against a character count.** The fixture test passed an
   explicit `Settings()`, forcing the spike defaults on all nine checks, while thresholds.json
   carried a threshold read under `text_sensor=ink`. Two fields reading 0 characters therefore
   fired on every dossier, the clean one included. The test now goes through the production path.
2. **The resolution check's recall and false positive rate were measured at -110.99 and published
   next to -148.5.** At the shipped threshold the true rate was 100% of clean dossiers at 150 dpi.
   `remeasure()` now recomputes everything AT THE THRESHOLD WE PUBLISH, and the reading sentence
   is generated from the sensor actually retained instead of being carried over.

### The repository is packaged

LICENSE (MIT, with the corpus explicitly outside its scope), pyproject.toml, a real entry point
(`python -m preflight`), a CI workflow, and a README that no longer oversells: the caveat about
one fictional dossier and synthetic degradations now sits directly under the table, not sixty
lines below it.

The entry point returns **three verdicts and not two**, because a dossier defect and an
unreadable page call for opposite actions: 0 no finding, 1 redo the dossier, 2 redo the scan, 64
usage error. The clock is mandatory.

### The repository is now in English

It had been in French because nobody ever decided: the first file was `spike/preuve.py`, its
docstring was French because the brief was, and every session after matched the surrounding
style. That locked in a choice at commit 1 that was inherited six times without its cause ever
being checked, which is the exact pattern this repo spent the day hunting elsewhere.

Two steps. A mechanical rename first (288 terms, word boundaries, longest first), verified by the
64 tests and by republishing: the nine thresholds come back identical from the 37 MB of
measurements, which were migrated key by key rather than replayed for two hours. Then the prose,
rewritten by hand, because it carries the measurements behind every choice and a script would
have kept the words while losing the reasons.

`dossier` and `piece` stay untranslated: they are the subject. So do the AcroForm field names,
which are data from the forms themselves.

The rename introduced two traps, both caught before they could bite. `Template.field()` shadowed
`dataclasses.field` imported in the same module, and only worked by accident of declaration
order; it is `field_ids()` now. And `cadrer()` and `cadre` both mapped to `frame`, which would
have let a local variable shadow the function inside `prepare()`; a collision check on the
table's OUTPUTS caught it before it was applied.

## 2026-08-22

### The fifth factor ran, and it settles the ink sensor

27,612 readings now: 14,976 for the four-piece grid plus 12,636 for the parasite axis, 148
minutes. Plus a 2,592-reading targeted follow-up, 25 minutes. Everything inside the budget that
was set before launching.

**The nine thresholds did not move.** One number did: the forbidden-value false positive rate
fell from 0.00058 to 0.00043, and the reason is arithmetic rather than behavioural. The Spanish
W-9 added clean targets and no false alarms, so the same 4 alarms are now divided by a larger
denominator.

**The corpus experiment answered its question.** All 4 false alarms still land on the Cerfa and
none on the Spanish W-9. Since that form varies the language while holding the layout, the cost
is the Cerfa's character-by-character boxing and not the fact of not being English. That is the
whole reason the third language went in, and it is the kind of question no amount of extra cells
could have answered.

**The ink sensor is blind past 1% of foreign ink, and it is now published as such.** On the very
field a variant emptied, over 27 cells and 3 seeds:

    ink (retained)   1.000 clean, 0.333 at 0.2%, 0.000 at 1%, 0.000 at 4%, and 0.000 false
                     positives at every level
    union            1.000 / 0.778 / 0.679 / 0.519, but 0.296 false positives at 4%
    full-page OCR    1.000 / 1.000 / 1.000 / 0.778, and 0.556 false positives at 4%
    per zone OCR     1.000 / 0.778 / 0.679 / 0.630, and 0.481 false positives at 4%

The sensor was not changed. The threshold is chosen on clean pages, deliberately: the four levels
exist in equal proportion for statistical power, and picking a threshold on the pooled set would
silently assume three pages in four carry foreign ink. On clean pages ink still wins, so ink
stays, and that is a result rather than an omission. What changed is that the weakness travels
with the strength: thresholds.json carries `recall_with_ink_on_the_damaged_field` inside the same
object as `recall`.

### Three things this run taught that are worth more than the numbers

**A verification you do not re-run after fixing only verifies your intention.** The parasite draw
rotated the check family on an index that counted the zero level, so it stepped by four over a
four-family piece and index zero never came up: the expiry date got zero placements. I did not
see it by re-reading the code I had just written. I saw it by re-running the coverage check after
correcting the first fault. That is the most transportable result of the night.

**A pilot is not a formality, it is a chance to find out the experiment aims elsewhere.** The
first draw was uniform over the DECLARED zones, which sounded reasonable. A form declares far
more zones than any check reads: 26 placements out of 36 landed where nothing is measured, and
neither a signature nor an expiry date was ever touched. Two hours of compute would have answered
nothing about the signature duel.

**And the corrected plan still aimed slightly beside the question.** Stratified by check, the
parasite lands on a zone the check watches, but a variant's damaged target is one zone among
several: for required_field it was never drawn at all. So the grid measures what foreign ink does
to a check in general and never exercises the masking mechanism, which needs the ink ON the
emptied field. Found by reading the partial results, not by reading the plan.
`grid/target_parasite.py` closes exactly that gap, and it is where the 0.000 above comes from.

The same shape of fault appeared once more at publication time: `recall_under_foreign_ink` read
1.000, because it came from the grid where the parasite rarely lands on the damaged field. A true
number with a false meaning, next to the very figure it was supposed to qualify. There are now
two fields with names that say which is which.

### What is left, in order of importance to the product

1. **Real scans.** Everything is synthetic. This is the repository's biggest external validity
   hole and no amount of grid closes it. It is now clearly the first thing to do.
2. **The signature duel is still not settled between the two sensors**, although the parasite did
   move the check itself: connected components hold 1.000 up to 1% of foreign ink and fall to
   0.333 at 4%, with zero false alarms throughout. What has not been done is re-running the duel
   between components and differential ink under the parasite, which is the comparison that would
   finally separate them.
3. **The angle hypothesis** on the forbidden-value corner. No new grid needed: same cell, same
   seed, fine deskew disabled, compare at equal rotation.
4. **A fourth language, or a form without an AcroForm.** The Spanish W-9 broke the
   language/layout confound; a form whose fields are boxed but written in English would close the
   other half of it.

### Experiment plan for the fifth factor, and its budget

Written BEFORE launching, because the budget is not mine to decide.

**Cost model, calibrated on the existing run.** 13,824 readings took 121 minutes on 13 workers,
that is 6.8 seconds of worker time per reading, and a wall-clock time of
`readings x 6.8 / 13 / 60` minutes. The model reproduces the known run to within a minute.

**A full crossing is refused.** Adding K parasite levels across the whole grid costs 13,824 x K
readings: even K=2 is 27,648 readings, 241 minutes, over four hours, and K=2 only buys "none" and
one level, which measures nothing about the dose. Rejected on budget.

**The design retained is fractional on the existing factors and full on the new one.** The
existing grid already establishes how each check behaves across angle, dpi, JPEG and noise. What
is unknown is only how parasite dose moves the score distributions, so the four old factors are
thinned and the new one is crossed fully against what remains:

    angle   0, 0.5, 2, 4          (4 of 6)
    dpi     150, 200, 300         (3, the nominal domain)
    JPEG    30, 75, 95            (3 of 4)
    sigma   0, 6, 12              (3 of 4)
    = 108 cells

    parasite   none, 0.6%, 2%, 8% of added ink in the touched zone   (4 levels)
    seeds      11, 23, 37, unchanged: threshold chosen on 11 and 23, published on 37

**The "none" level is not re-measured.** The existing measurements.jsonl already covers those 108
cells at parasite=none, on the same three seeds, produced by the same code. Reusing them costs
zero and keeps the comparison exact.

    108 cells x 3 new levels x 3 seeds x 13 readings = 12,636 readings
    12,636 x 6.8 / 13 / 60 = 110 minutes, about 1 h 50

    analysis set: 108 x 4 x 3 = 1,296 dossiers, against 864 today

**Revised for the fourth piece.** The Spanish W-9 makes a dossier 13 readings instead of 12, so
the figures above went from 11,664 to 12,636 readings and from 102 to 110 minutes. It also made
every task of the existing 13,824-reading file one reading short: exactly 1,152 readings missing
(384 cells x 3 seeds x the one new piece). Re-running those tasks whole would have cost two hours
to reproduce readings that already exist and are deterministic, so `--backfill` produces only what
is missing, for about ten minutes. The cost model predicted ten and the run confirmed it.

**Placement.** One parasite per piece per dossier, its shape drawn from the seed among the probe's
three (speck, fold shadow, neighbouring stroke), its position drawn among that piece's DECLARED
zones. Random placement rather than a fixed target, because that is how dust behaves and because
it exercises all nine checks instead of only the one the probe looked at. The cost is uneven
statistical power per check, and that will be reported per check rather than averaged away.

**Order of operations.** The parasite is laid on the CLEAN render, BEFORE degradation, so it goes
through the same rotation, noise, blur and compression as the page. `parasitic-ink-probe/parasite.py`
already has the three shapes calibrated and is reused as it is.

**What gets re-read.** ALL nine thresholds, on the new curves. A fifth factor moves every check's
operating point, and recalibrating only one would leave the other eight tuned for a world that no
longer exists.

**What is not decided in advance.** The sensor retained for `required_field` is the one the new
curves designate. `union` is a hypothesis to test, not a conclusion to implement. If `ink` wins
again, it stays, and that is a result.

**A pilot runs first.** `grid/run.py --pilot 4` on the new axis, to check the cost model against
reality before committing the 102 minutes. If the measured cost per reading exceeds the model by
more than 30%, the design is thinned again before the full run rather than after it.

## 2026-09-25

The domain rule now reads the calibration seeds, not the held-out seed. `choose_domain` picked
the 150 dpi floor by minimising `r["validation"]["recall"]`, the very number the held-out
protocol exists to report untouched: the floor was chosen on data it was then validated against.
Fixed to `r["calibration"]["recall"]`. Same floor, 150 dpi; the printed worst recall at that floor
moves from 0.997 to 0.991, because it now reads the calibration seeds (11, 23) instead of the
held-out one (37). No threshold in `thresholds.json` changed.

`complete_dossiers` also carried a literal `len(clean) < 3` from the three-piece corpus; the
dossier has carried four pieces since the Spanish W-9 was added, and every complete cell already
has four clean readings, so the fix (`len(clean) < len(ref.pieces)`) changes nothing observable,
only the source of truth for the count. Three stale comments in `grid/run.py` (module docstring,
the parasite sub-grid cost estimate, `pieces_to_read`'s docstring) and one in `grid/analyze.py`'s
`complete_dossiers` docstring still said three pieces and twelve readings; corrected to four and
thirteen. `grid/run.py:232`'s backfill comment, which correctly describes the file's state before
the fourth piece was backfilled, was left as written.

**Identities and every defect instance** (for perfect-recall-study's arm A1). One reference
identity meant one instance per check: `VARIANTS` carried nine single-defect fixtures, the
fixture cache had no identity in its path so a second person would silently reuse the first
one's PDFs, and `sweep` took only the first variant matching a check. `enumerate_variants(ref)`
walks every required field, checkbox, signature, expiry magnitude (1 and 365 days past the
filing clock), consistency pair and page defect the four pieces declare: 45 instances per
identity (9 W-9, 9 Spanish W-9, 15 I-9, 12 Cerfa), matching perfect-recall-study's
`prereg/PREREG.md` section 3.2 exactly, by piece and by check, for all six new fictional
identities (`fixtures/make_identities.py`, seed 20260925) and for the reference identity alike.
`VARIANTS` itself is untouched, name for name: `grid/target_parasite.py` still imports it
directly. The build cache now keys on identity first (`{identity}-{variant}-{piece}.pdf`), the
signature fixture draws on the identity's own `signature_seed` instead of a hard-coded 11, and
the W-9's foreign-address line reads the identity's own country instead of a hard-coded "FR".
`grid/run.py --identities DIR --cells R` and `grid/analyze.py --identities DIR` thread the
identity through the key everywhere it is used (`key()`, `load()`, `complete_dossiers`), and
`sweep` now pools positives across every variant of a check instead of stopping at the first
one a fixed catalog declares. With no `--identities`, both scripts take the single default
reference exactly as v0.1.0 did: replayed `python3 grid/analyze.py --publish` on the committed
A0 file and `git status --short grid/results` showed only `curves.png` (matplotlib-version
noise, reverted), `thresholds.json` and `LIMITS.md` unchanged.

**The review of that change found four counting faults, none visible on A0.** (1) `sweep` keyed a
positive by target alone, so the two expiry instances (1 and 365 days past), which damage the
same field, overwrote each other: one positive per cell where two were measured. Positives are
now keyed (variant, piece, target); a one-cell smoke run on the six identities counts 36 expiry
positives over 18 dossiers, not 18. (2) The v0.1.0 fallback (no damaged target scored: every
target of the check becomes a positive) would, on an enumerated instance, count the filled
fields as missed positives; it stays for the nine legacy names only. (3) `crosstalk` still
iterated the nine legacy names against one reference, a KeyError on every-instance data; its
columns keep the legacy labels, each pooling every instance of its check, scored on the row's
own identity. (4) `complete_dossiers` inferred the expected variants from whatever the file held,
so a variant that failed everywhere would leave the denominators silently; the expectation is
now declared (legacy nine by default, each identity's `enumerate_variants()` under
`--identities`), and `analyze.py` refuses a file carrying an identity it has no reference for.
The fixture cache name also carries a content tag of the identity and of `preflight/fixtures.py`,
so an edited identity is never served stale PDFs. `AXIS_INDEX` stays without identity: identity
is a replicate axis like the seed (`IDENTITY_INDEX = 6`), and a factor row for it would have
changed A0's LIMITS.md. The A0 `--publish` replay is again byte-identical but for `curves.png`.
