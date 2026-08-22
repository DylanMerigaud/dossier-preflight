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

### What is left, in order of importance to the product

1. **The fifth factor: parasitic ink in the grid.** The only thing that would allow changing the
   required-field sensor properly. Plan and budget below.
2. **Real scans.** Everything is synthetic. This is the repository's biggest external validity
   hole and no amount of grid closes it.
3. **The signature duel, still unsettled** (six settings at 1.000 and 0.0000). The same parasite
   settles it: a stroke in the signature zone separates ink from connected components, where the
   current grid cannot tell them apart.
4. **The angle hypothesis** on the forbidden-value corner. No new grid needed: same cell, same
   seed, fine deskew disabled, compare at equal rotation.

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

    108 cells x 3 new levels x 3 seeds x 12 readings = 11,664 readings
    11,664 x 6.8 / 13 / 60 = 102 minutes, about 1 h 45

    analysis set: 108 x 4 x 3 = 1,296 dossiers, against 864 today

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
