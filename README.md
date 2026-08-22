# dossier-preflight

Is this dossier going to be rejected at the counter.

Not extraction, not document generation: the CONFORMITY of a dossier to an external reference,
measured on what is ACTUALLY PRINTED. An AcroForm field can carry a value that never prints.
The counter, for its part, reads the sheet.

A "dossier" is a set of supporting documents filed together with an administration, and a
"piece" is one document in it. Both words are kept untranslated throughout: they are the
subject, and "file" and "document" lose the relation between the two.

## What it measures

Nine checks, each with a threshold READ off a precision/recall curve, not picked by hand. A
grid of 384 cells (angle x dpi x JPEG quality x noise) x 3 seeds = 1152 dossiers, 13,824 image
readings, 121 minutes on 13 workers. The threshold is chosen on seeds 11 and 23; the figure
below is the one from seed 37, never looked at beforehand.

| check | what it catches | retained sensor | threshold | recall | false positives per target |
|---|---|---|---|---|---|
| required_field | a required field never filled | added ink (threshold 128) | -0.345 | 1.000 | 0.00000 |
| required_checkbox | a required box left unticked | central disc 0.30 of the side | -14.38 | 1.000 | 0.00000 |
| signature | a missing signature | connected components | -342.1 | 1.000 | 0.00000 |
| expiry | a piece expired AT THE CHOSEN CLOCK | date read by full-page OCR | 0 (definition) | 1.000 | 0.00000 |
| consistency | the same data diverging between two pieces | per zone OCR, tokens | 0.394 | 1.000 | 0.00000 |
| forbidden_value | a forbidden value reappearing | full-page OCR, n-grams | 0.721 | 0.997 | 0.00058 |
| resolution | a scan below the readability floor | registration scale | -148.5 dpi | 1.000 | 0.00000 |
| cropped_page | a truncated page | coverage of the blank's ink | 0.088 | 1.000 | 0.00000 |
| rotated_page | an upside-down page | correlation margin per quarter turn | 0.359 | 1.000 | 0.00000 |

**WHAT THIS TABLE DOES NOT COVER, AND IT HAS TO BE READ ALONGSIDE IT.** The dossiers are ONE
fictional dossier of four forms (W-9, its Spanish edition, I-9, Cerfa 14011, page 1 of each),
ONE invented person, ONE single defect per check, rendered through a SYNTHETIC noise model. No
real scan ever entered this measurement. The 1152 therefore measure the noise model and not the
world: a recall of 1.000 is that of the same defect seen 864 times, not of 864 different
defects. What these figures do not say: what the tool does on another form, on another way of
failing the same check, or on a real scanner glass with its dust, its binding shadow and its
page curvature. `LIMITS.md` details each of those holes, and one of them touches the sensor
that won its duel.

The number a user feels is not the one in the right-hand column, it is the one for the whole
dossier: **4 dossiers out of 864 entirely clean ones carry at least one alarm, that is 0.46%**,
and all four come from the forbidden-value check.

**And all four land on the Cerfa, which is why the Spanish W-9 is in the corpus.** With two
English forms and one French one, "French" and "boxed field layout" named the same object and
nothing could say which one the tool struggles with. The IRS publishes its own Spanish W-9: same
producer, same licence, same 23 declared zones, comb tax number of identical geometry. It varies
the language and holds the layout. It produces **zero** false alarms, and it lowered the
per-target rate of the forbidden-value check from 0.00058 to 0.00043 purely by adding clean
targets. So it is the Cerfa's character-by-character boxing that costs, not the language.

A faulty dossier is rejected at the counter: months of delay. A gate that cries for nothing
loses its credibility, and a rule that cries wolf makes every rule next to it get skimmed. The
two costs are not of the same kind, and the operating point is chosen with that asymmetry
declared: the highest recall tenable under 0.2% false positives per target.

## The domain, and what happens outside it

**Scanning at 150 dpi or more.** Below that, raw sensors, the forbidden-value check falls to
0.042 recall and consistency fires on 84% of clean dossiers. Those two figures do not describe
the product, they justify the rule that follows: they are measured WITHOUT abstention, because a
measurement cannot depend on the behaviour it is used to tune.

Below the floor the tool does not guess: the resolution check fires, and **every check that
READS abstains on the piece concerned**, with a verdict of "undecidable" that is not
"compliant". Before that rule, consistency cried on 456 of the 864 dossiers carrying a piece at
72 dpi, comparing tokens it had failed to read.

The resolution threshold is the only one that does not come from its own curve: its curve would
place it at 111 dpi, the spot that best separates the faulty variant from the rest. But the
question that check has to ask is not "is this page at 72 dpi", it is "is this page sharp enough
for the OTHERS to hold". It is therefore set at the floor, minus 1% of margin, the margin being
ten times the maximum measured error of the resolution estimator (0.0133%).

Inside that domain the tool misses something in exactly one place, and it is named: the
forbidden-value check drops to **0.889 recall [0.807, 0.939] over 90 positives** in the
conjunction 300 dpi AND JPEG 95 AND noise 12 AND a deskew of 0.5 degrees or more. Below that
half degree, 30 out of 30. The upper bound of the interval stays below the 95% floor, so this is
not sampling noise. A control on the same cell at JPEG 30 returns 0.986: it really is the
compression, heavy compression erasing the sensor grain that light compression keeps. The part
of the mechanism that depends on the angle remains an untested hypothesis.

`LIMITS.md` gives the per-check detail: recall per factor, worst cells, worst two-factor
crossings, the crosstalk matrix, the outside-protocol follow-up on that cell, and what the
measurement does not cover.

## The two sensor duels

The spike had settled at n=1 that ink was the wrong sensor for text. **The grid contradicts
it.**

For "is this required field empty", four competing sensors:

| sensor | recall | false positives per target |
|---|---|---|
| added ink, threshold 128 (retained) | 1.000 | 0.0000 |
| full-page OCR + per zone OCR, min confidence 0 | 1.000 | 0.0003 |
| OCR alone, min confidence 10 and up | 0.000 | 0.0000 |

The spike's real culprit was not the sensor, it was its confidence floor at 40. A COMB field
(one box per character, the form declares it) reads "4/1)2" at confidence 38: all three digits
are there, but the separators break tesseract's word model. At confidence 40 that FILLED field
was declared empty. At confidence 0, OCR comes back level with ink.

Ink still wins, and it has to be said why it wins here: no degradation in this grid ADDS foreign
ink inside a zone. It wins on ground that favours it.

**And here is what that ground was hiding, measured separately.** A 528-reading probe laid
foreign ink (a speck, a fold shadow, a stroke from the neighbouring field) onto the page BEFORE
the degradations. As soon as at least 0.5% foreign ink enters the zone, on an EMPTY field:

| sensor | false negatives, an empty field declared filled | false positives, a filled field declared empty |
|---|---|---|
| ink, threshold 128 (RETAINED) | **1.000** [0.975, 1.000] | 0.000 [0.000, 0.014] |
| union, confidence 0 | 0.272 [0.207, 0.347] | 0.030 [0.015, 0.059] |
| full-page OCR | 0.185 [0.132, 0.255] | 0.136 [0.100, 0.183] |
| per zone OCR | 0.106 [0.066, 0.165] | 0.114 [0.081, 0.158] |

The retained sensor misses **100% of empty fields** under those conditions, and those are false
negatives, the expensive side of the asymmetry declared above: the counter rejects the dossier
and the tool said nothing. The switch is a cliff sitting exactly on the published threshold of
0.345%, and the two populations do NOT OVERLAP BY A SINGLE READING: the sensor fires 97 times
out of 97 up to 0.323% added ink, and 0 times out of 167 from 0.380% on. There is no grey zone,
there is a step. For that field of 15,770 canonical pixels, 0.35% is a 9 x 8 px speck at 200
dpi, that is, a piece of dust on the scanner glass. A pen stroke barely spilling out of the
neighbouring field already adds 0.61%.

**The grid has since been replayed with parasitic ink as a fifth factor, and the probe holds.**
Laid on the very field a variant emptied, over 27 cells and 3 seeds:

| sensor | recall, clean | @0.2% ink | @1% | @4% | false positives @4% |
|---|---|---|---|---|---|
| ink, threshold 128 (RETAINED) | 1.000 | 0.333 | **0.000** | **0.000** | 0.000 |
| union, confidence 0 | 1.000 | 0.778 | 0.679 | 0.519 | 0.296 |
| full-page OCR | 1.000 | 1.000 | 1.000 | 0.778 | 0.556 |
| per zone OCR | 1.000 | 0.778 | 0.679 | 0.630 | 0.481 |

Past 1% of foreign ink on the emptied field, the retained sensor is **completely blind**: every
such field is declared filled. In exchange it never once cries wolf, at any level. The word
sensors keep seeing, and start crying: at 4% they raise false alarms on 30 to 56% of clean pages,
which is the cost that destroys a gate rather than degrading it.

**The sensor was still not changed, and that is now a measured decision rather than a wait.** The
operating point is chosen on clean pages, deliberately: the four parasite levels exist in equal
proportion for statistical power, and choosing a threshold on the pooled set would silently
assume that three pages in four carry foreign ink. On clean pages ink still wins, so ink stays.
What changed is that the weakness is now published next to the strength: `thresholds.json`
carries `recall_with_ink_on_the_damaged_field` in the same object as `recall`, so nobody reads
the 1.000 without reading the 0.000.

If your scans come off a dirty glass, this is the row to weigh, and full-page OCR is the sensor
to prefer at the price of its false alarms. That trade is yours to make; the measurement is
here to make it with.

For "is this signature missing", differential ink against connected components: **a tie**. All
six settings return exactly 1.000 recall and 0.0000 false positives at every dpi. This corpus
does not tell them apart, and the retained setting is backed by no measurement. That is a
result, not a victory.

## How it works

Three properties carry the whole design, and all three were paid for.

**The blank form is not a fixture, it is the REFERENCE IMAGE.** Every check is a differential
against it, the pre-printed words read on the blank are subtracted by text AND position, and the
tool only ever asserts something about what was ADDED.

**AcroForms DECLARE their zones.** 23 rectangles on page 1 of the W-9. No coordinate is measured
by hand, none is guessed. The form also declares which fields are combs, which state counts as
"ticked", and how many characters it accepts.

**The blank comes to the scan, not the other way round.** Bringing a scan into a canonical 200
dpi frame resamples it whenever its resolution differs, and that destroys small boxed text: on
the Cerfa, a scan at 300 dpi returned 0 readable characters in three fields that returned 14, 5
and 10 at 200 dpi, where the scale is exactly 1. All three resampling filters failed the same
way, so it was not the filter. The grid would have measured that resampling and concluded,
wrongly, that the tool breaks at 300 dpi. The scan stays native; the blank, a clean synthetic
render, comes to it.

Before any coordinate-based check, the page is deskewed (axis first, then fine angle) and
registered onto the blank by cross-correlation, which yields the orientation, the estimated
source resolution and the page coverage for free. Without deskewing, ink measured in the zones
of a scan rotated by 0.45 degrees reports 8 ticked boxes out of 8 when nothing is ticked.

## Install

Two dependencies are SYSTEM ones and pip installs neither: tesseract, with the `eng` AND `fra`
language data (the Cerfa is in French, and without `fra` its fields come out EMPTY with no error
message, which looks like a dossier defect and is not one), and poppler for `pdftoppm`.

    brew install tesseract tesseract-lang poppler                    # macOS
    apt-get install tesseract-ocr tesseract-ocr-fra poppler-utils    # Debian

    pip install -e .            # the core
    pip install -e ".[dev]"     # with pytest
    pip install -e ".[grid]"    # with matplotlib, only to plot the curves

Measured and tested on Python 3.12.8, tesseract 5.5.1, poppler 26.04. The declared floor is 3.10
and has not been tested.

## Run it on your own dossier

    python3 -m preflight fixtures/reference.yaml \
        --clock filing \
        --piece tax=scans/w9.pdf \
        --piece employment=scans/i9.pdf \
        --piece identity=scans/cerfa.pdf

The clock is mandatory. It is the one property of this repo that nothing else tools: the same
piece is good for one dossier and expired for another at the very same instant, and a tool that
silently took today's date would throw it away. Pass a name declared by the reference (`filing`,
`admissibility`) or an ISO date.

Three verdicts and not two, because two of them call for opposite actions:

| code | verdict | what to do |
|---|---|---|
| 0 | no finding | nothing, and it is not a guarantee: see `LIMITS.md` |
| 1 | dossier defect | REDO THE DOSSIER |
| 2 | the tool cannot read | REDO THE SCAN |
| 64 | usage error | fix the command line |

Code 2 covers two things of the same family: the resolution check firing, and the checks that
ABSTAINED on a piece below the floor. An abstention carries a null score meaning undecidable,
never compliant. The resolution check sits on the scan side and not the dossier side because
that is already what it answers, "I cannot read this page" and not "this page is at fault".

`--json` for machine output, `--all` to also see the checks that stay silent.

## Run the measurement rig

    python3 spike/proof.py            # the first green case, standalone
    python3 -m pytest tests/ -q       # 64 tests, about 2 min 20 (they render and OCR)
    python3 grid/run.py               # the grid, ~2 h on 13 workers, resumable
    python3 grid/run.py --parasite    # the fifth factor, ~2 h 30
    python3 grid/target_parasite.py   # foreign ink on the field a check must catch, ~25 min
    python3 grid/analyze.py --publish # reads the thresholds off the curves, writes LIMITS.md
    python3 grid/corner_followup.py   # the outside-protocol follow-up on one cell

Local tooling only. No remote service, no spend.

## The corpus

Three BLANK forms exactly as their administration publishes them: W-9 (IRS) and I-9 (USCIS),
public domain 17 U.S.C. 105, and Cerfa 14011*02 (service-public.fr, Etalab Open Licence 2.0).
Producer, source, retrieval date, licence and sha256 in `corpus/CORPUS.md`, with a test that
fails in both directions.

Never a document issued to somebody. An issued document cannot be fully redacted: the 2D barcode
encodes the identity and survives the black rectangle, the text layer stays intact underneath,
and there remain the XMP metadata, the incremental update history and the scanner fingerprint.
The test dossiers are filled from an entirely fictional reference.
