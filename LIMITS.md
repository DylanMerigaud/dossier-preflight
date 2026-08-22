# Limits: where this tool stops working

A tool that does not say where it stops working is not measured, it is narrated.

## Nominal domain: scanning at 150 dpi or more

The operating points are chosen on the 864 pairs of this domain, not on the
1152 of the whole grid. That is not a way to hand ourselves nice numbers, it is a
mechanical consequence: a dossier is rejected as soon as ONE required field is empty,
so the dossier's score is that of its WORST field. Below the floor the Cerfa has fields
OCR cannot read, the CLEAN dossier then reaches the same score as the faulty one, and
no threshold separates them any more. The operating point would retreat until it fired
at nothing at all.

Below that floor the tool does not guess: the resolution check fires and says it cannot
read the page. Every section below also gives what the check does OUTSIDE the domain,
because hiding it would be lying about it.

Domains tried, from widest to narrowest, with the worst recall of the checks that
depend on OCR: dpi >= 96 -> 0.000, dpi >= 150 -> 0.997.

Measured over 1152 cell/seed pairs: angle (0, 0.25, 0.5, 1, 2, 4 deg) x
dpi (96, 150, 200, 300) x JPEG quality (30, 55, 75, 95) x noise sigma (0, 3, 6, 12),
three seeds per cell. Every check is evaluated at its operating point, chosen as the
highest recall holding a false positive rate under 0.2%.

The threshold is chosen on seeds 11 and 23, and the published figure is the one from
seed 37, never looked at beforehand. Choosing a threshold and reporting
its recall on the same draws always overestimates it.

A cell is declared OUTSIDE THE DOMAIN when recall there drops below 95%.

## What the measurement does not cover

- A single set of three forms (W-9, I-9, Cerfa 14011), page 1 of each. The figures do
  not transport as they are to a form whose typography or field framing differs. The
  Cerfa, whose fields are boxed character by character, is already markedly harder than
  the two American forms.
- ONE fictional dossier, ONE invented person, ONE defect per check. A recall of 1.000 is
  that of the same defect seen 864 times, not of 864 different defects.
- Words are only recorded inside the zones DECLARED by the AcroForm, expanded by 8 px. A
  forbidden value reappearing outside any declared field, in a handwritten note in the
  margin for instance, would not be seen.
- A form without an AcroForm is out of reach: all the geometry comes from the PDF's own
  declaration, nothing is measured by hand.
- The degradations are SYNTHETIC. A real scanner adds artefacts this grid does not
  imitate: page curvature, binding shadow, dust on the glass, rescreening moire. The
  grid bounds the domain, it does not prove it.
- DIRECT CONSEQUENCE ON THE INK SENSOR, and it is no longer a hypothesis: no degradation
  in this grid ADDS foreign ink inside a zone, so the sensor retained for required
  fields wins its duel on ground that favours it. A 528-reading probe put a number on
  what that ground was hiding on 2026-08-21 (parasitic-ink-probe/FINDING.md):
  as soon as at least 0.5% foreign ink enters the zone, that sensor declares an EMPTY
  field FILLED in 1.000 of cases [0.975, 1.000] over n=151, against 0.272 for the union
  of the word sensors, 0.185 full page and 0.106 per zone. These are false negatives,
  the expensive side of the asymmetry. The switch is a cliff sitting on the published
  threshold of 0.345%, and the two populations do not overlap by a single reading: the
  sensor fires 97 times out of 97 up to 0.323% added ink and 0 times out of 167 from
  0.380% on. No grey zone, a step. For that field 0.35% is a 9 x 8 px speck at 200 dpi,
  a piece of dust on the glass; a pen stroke barely spilling out of the neighbouring
  field already adds 0.61%.
  THE SENSOR AND THE THRESHOLD WERE NOT CHANGED, and that is the right call as long as
  the measurement is a probe: one field, two cells, three parasite shapes. It shows a
  choice was settled on biased ground, it is not enough to fix a threshold. Changing it
  requires replaying this grid with parasitic ink as a FIFTH FACTOR, and that is the
  first measurement job still open.
- Precision depends on prevalence. The curves give it at 10% faulty dossiers, an ASSUMED value and not a measured one.

## Outside-protocol follow-up: the only cell where the tool misses something

OUTSIDE THE PROTOCOL, and that has to be said before the numbers. The published
thresholds come from a strict rule: two seeds calibrate, the third is never looked
at before the number is written. This follow-up's seeds were drawn AFTER seeing
where the tool was missing, on a cell chosen because it was missing. They move no
threshold and enter no figure published elsewhere. They answer one question only:
was n=18 enough to conclude.

Cell: 300 dpi, JPEG 95, noise sigma 12.0, check forbidden_value, published threshold 0.7214.

| set | recall | 95% CI | positives |
|---|---|---|---|
| original seeds (11, 23, 37) | 0.8333 | [0.608, 0.942] | 18 |
| 12 new seeds | 0.9028 | [0.813, 0.952] | 72 |
| COMBINED | 0.8889 | [0.807, 0.939] | 90 |

The point estimate climbs from 0.833 to 0.889, the regression to the mean expected of an n=18, but the UPPER
bound stays at 0.939, below the 95% floor. This is not
sampling noise: the check really does miss something here.

A CONTROL, and it is what makes the twelve seeds interpretable. Same cell, same
twelve seeds, only the compression changes:

- JPEG 95: 65/72 = 0.9028
- JPEG 30: 71/72 = 0.9861

So the new seeds are not harder, it is the compression. HEAVY compression erases
the sensor's grain; light compression keeps it, and at high resolution that grain
is fine enough to be read as character structure. That part of the mechanism is
MEASURED.

THE REAL SHAPE IS A CONJUNCTION OF FOUR FACTORS, not two:

- angle below 0.5 deg: 30/30 = 1.0000
- angle at 0.5 deg or above: 50/60 = 0.8333

A step, not a slope. The faulty cell is therefore 300 dpi AND JPEG 95 AND noise 12.0 AND angle >= 0.5 deg. The
two-factor sweep below cannot see it as such: each pair averages over the two
remaining factors, so it only shows its shadow. It serves to FIND it; it is the
list of worst cells, already four-factor, that NAMES it.

Reservation about the mechanism: the compression part is measured by the control,
the angle part is ASSUMED. The hypothesis is that what counts is the MAGNITUDE of
the resampling and not its presence, a deskew beyond half a degree smearing the
fine grain into the thickness of the strokes. It is not tested. The deskew does
apply a bicubic rotation from 0.25 deg on as well, so the lazy explanation (no
resampling below 0.5 deg) is verified false.

Reproduce: `python3 grid/corner_followup.py`.

## Crosstalk: who cries about the neighbour's defect

Each cell gives the share of dossiers where the check on the ROW fires while the
injected defect belongs to the COLUMN. The diagonal is empty by construction. Not
every cell is a fault: a cropped page takes real fields with it, so the
required-field check is right to cry there. This table serves to separate the
physical consequence from the contamination.

A UNIFORM ROW is not crosstalk: it is the check's background rate reappearing. The
variants share the pieces they do not damage, so a check firing at x% on a clean
dossier fires at x% on every column. What reads here are the cells that EXCEED the
row.

| check \ defect | empty_required | unchecked_box | missing_signat | expired_date | diverging_addr | forbidden_valu | low_resolution | cropped_page | rotated_page |
|---|---|---|---|---|---|---|---|---|---|
| consistency | . | . | . | . | . | . | . | . | . |
| cropped_page | . | . | . | . | . | . | . | . | . |
| expiry | . | . | . | . | . | . | . | . | . |
| forbidden_value | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 | . | 0.005 | 0.005 | 0.005 |
| required_checkbox | . | . | . | . | . | . | 0.021 | . | . |
| required_field | . | . | . | . | . | . | . | . | . |
| resolution | . | . | . | . | . | . | . | . | . |
| rotated_page | . | . | . | . | . | . | . | . | . |
| signature | . | . | . | . | . | . | . | . | . |

A dot means zero firings over 864 dossiers.

## consistency

Retained settings: min_conf=0.0, text_sensor=zone. Threshold 0.3939.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 0.958 [0.929, 0.976], firings on a clean dossier 0.8403 over 288 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## cropped_page

Retained settings: no settings. Threshold 0.08795.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 0.0000 over 864 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## expiry

Retained settings: min_conf=0.0, text_sensor=page. Threshold 0.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.566, 1.000], firings on a clean dossier 0.0000 over 2 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## forbidden_value

Retained settings: min_conf=0.0, text_sensor=page. Threshold 0.7214.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 0.991 | [0.980, 0.996] | 0.0009 | [0.0003, 0.0025] | 0.0052 | 576 |
| VALIDATION (seed 37, never seen) | 0.997 | [0.981, 0.999] | 0.0006 | [0.0001, 0.0033] | 0.0035 | 288 |
| overall | 0.993 | [0.985, 0.997] | 0.0008 | [0.0003, 0.0020] | 0.0046 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 6 out of 288.

Worst CROSSINGS of two factors. An axis-by-axis reading can lie by omission:
three marginal values all above the floor can cross into a cell that falls
below it.

- dpi x sigma = [300, 12.0]: recall 0.931 [0.848, 0.970] over 72 positives
- angle x jpeg = [1.0, 95]: recall 0.944 [0.819, 0.985] over 36 positives
- angle x sigma = [2.0, 12.0]: recall 0.944 [0.819, 0.985] over 36 positives
- dpi x jpeg = [300, 95]: recall 0.944 [0.866, 0.978] over 72 positives

Clean targets that fire AT THE RETAINED THRESHOLD, the ones that cost credibility:

- identity / A COMPLETER: 4 times out of 864

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 0.042 [0.024, 0.071], firings on a clean dossier 0.0000 over 1728 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

Frontier per factor, number of fallen cells over the total:

- angle: 0.0 -> 0/48, 0.25 -> 1/48, 0.5 -> 0/48, 1.0 -> 2/48, 2.0 -> 2/48, 4.0 -> 1/48
- dpi: 150 -> 0/96, 200 -> 0/96, 300 -> 6/96
- jpeg: 30 -> 0/72, 55 -> 1/72, 75 -> 1/72, 95 -> 4/72
- sigma: 0.0 -> 0/72, 3.0 -> 0/72, 6.0 -> 1/72, 12.0 -> 5/72

The worst cells (angle, dpi, jpeg, sigma) and their recall:

- angle 0.25, 300 dpi, JPEG 55, sigma 12.0: recall 0.67 over 3 seeds
- angle 1.0, 300 dpi, JPEG 95, sigma 6.0: recall 0.67 over 3 seeds
- angle 1.0, 300 dpi, JPEG 95, sigma 12.0: recall 0.67 over 3 seeds
- angle 2.0, 300 dpi, JPEG 75, sigma 12.0: recall 0.67 over 3 seeds
- angle 2.0, 300 dpi, JPEG 95, sigma 12.0: recall 0.67 over 3 seeds
- angle 4.0, 300 dpi, JPEG 95, sigma 12.0: recall 0.67 over 3 seeds

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 0.993 [0.96, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 0.986 [0.95, 1.00], 2.0 -> 0.986 [0.95, 1.00], 4.0 -> 0.993 [0.96, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 0.979 [0.96, 0.99]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 0.995 [0.97, 1.00], 75 -> 0.995 [0.97, 1.00], 95 -> 0.981 [0.95, 0.99]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 0.995 [0.97, 1.00], 12.0 -> 0.977 [0.95, 0.99]

## required_checkbox

Retained settings: disc_ratio=0.3, ink_threshold=128. Threshold -14.38.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 0.0000 over 864 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## required_field

Retained settings: text_sensor=ink, ink_threshold=128. Threshold -0.345.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0003] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0007] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0002] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 0.0000 over 5760 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## resolution

Retained settings: no settings. Threshold -148.5.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 1.0000 over 864 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

For THIS check, those firings outside the domain are not false positives:
it is exactly its job. It is there to say that a page scanned below the
floor must not be judged by the others.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## rotated_page

Retained settings: no settings. Threshold 0.3585.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 0.0000 over 864 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## signature

Retained settings: ink_threshold=128, signature_sensor=components. Threshold -342.1.

| set | recall | 95% CI | false positives per target | 95% CI | per clean dossier | positives |
|---|---|---|---|---|---|---|
| calibration (seeds 11 and 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, never seen) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| overall | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

The per-dossier rate is the one the user feels: the probability that at least one
alarm goes off on an entirely clean dossier. It is the one that decides whether
the gate stays credible.

Cells below the floor: 0 out of 288.

Outside the domain (dpi < 150), RAW SENSORS, that is, what the tool
would do if it had no abstention rule: recall 1.000 [0.987, 1.000], firings on a clean dossier 0.0000 over 288 targets.
Those figures therefore do not describe the product, they justify the rule: in
production a check that READS abstains below the floor instead of producing
what is read here. They are deliberately raw-sensor measurements, because a
measurement cannot depend on the behaviour it is used to tune.

No cell of the explored domain drops below the floor.

Recall per factor, at the retained threshold:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

