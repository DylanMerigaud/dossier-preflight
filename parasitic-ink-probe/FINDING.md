# The ink sensor collapses as soon as foreign ink enters the zone

Measured 2026-08-21, outside the repository, on a `git archive` of commit 3a4e682. Nothing was
written into the working tree. Reproduce: `experiment.py --procs 13`, then the aggregates in this
file.

## The question

The grid crosses angle, resolution, compression and noise. None of those four degradations ADDS
ink inside a zone: they move, blur or dirty the ink already there. Yet the sensor retained for
"is this required field empty" is an ink sensor, which does not know what is written, only that
something is darker than before. It won its duel on ground that favours it.

## The protocol

Three shapes of foreign ink, laid on the CLEAN render before degradation, so they then go through
the same rotation, noise, blur and compression as the page: speck (localised deposit), fold (a
crease shadow across the page), stroke (a pen from the neighbouring field spilling over). Target
field: `employment` / `City or Town`, the one the `empty_required_field` variant leaves empty. Two
cells (0.25 deg / 200 dpi / JPEG 95 / noise 0, and 0.5 deg / 200 dpi / JPEG 55 / noise 6), six
seeds, seven intensities plus a control with no parasite. 528 readings.

Control with no parasite: 0 false negatives and 0 false positives for all four sensors. The bench
is sound.

## The result, on real foreign ink (at least 0.5% added)

FALSE NEGATIVES, an EMPTY field declared filled. The counter rejects the dossier and nobody was
warned: this is the expensive side of the asymmetry the project declares.

| sensor | false negatives | 95% CI | n |
|---|---|---|---|
| ink (RETAINED by the grid) | **1.000** | [0.975, 1.000] | 151 |
| union | 0.272 | [0.207, 0.347] | 151 |
| page | 0.185 | [0.132, 0.255] | 151 |
| zone | 0.106 | [0.066, 0.165] | 151 |

FALSE POSITIVES, a FILLED field declared empty, same conditions. This is the price to pay:

| sensor | false positives | 95% CI | n |
|---|---|---|---|
| ink | 0.000 | [0.000, 0.014] | 264 |
| union | 0.030 | [0.015, 0.059] | 264 |
| zone | 0.114 | [0.081, 0.158] | 264 |
| page | 0.136 | [0.100, 0.183] | 264 |

## The switch sits exactly on the published threshold

The retained threshold is 0.345% added ink. Measured, by the ink actually added:

    up to 0.323%      fires 97 times out of 97
    from 0.380% on    fires  0 times out of 167
    in between        zero readings, the two populations do not overlap at all

Not a grey zone: a cliff. For that field of 415 x 38 = 15,770 canonical pixels, 0.35% is 55
pixels, that is a speck of about 9 x 8 px at 200 dpi. A piece of dust on the scanner glass is
enough. A pen stroke barely spilling out of the neighbouring field already adds 0.61%.

The fold shadow behaves differently and it is instructive: as long as it leaves the paper above
the binarisation threshold (128) it is perfectly invisible to the sensor, then the whole band
flips at once (0.00% added ink, then 39%, then 100%).

## What the word sensors miss, for their part

Their failure mode is not the same and it is non-monotonic: a speck of the right size gets READ
as letters. At intensity 0.020, per zone OCR returns "FS ee en ee, Be" and concludes the field is
filled (1 firing out of 12), while it returns an empty string and fires 12 times out of 12 at
neighbouring intensities, both smaller and larger. A word sensor does not confuse a speck with a
value in general, but it does sometimes.

## What this recommends, and what it costs

Moving the required-field check from `ink` to `union`. On the published grid, `union` (minimum
confidence 0) already held 1.000 recall, at 0.0003 false positives per target against 0.0000 for
ink: the cost is three targets in ten thousand. In exchange, under foreign ink, false negatives
go from 1.000 to 0.272 and false positives from 0.000 to 0.030.

`zone` does better still on false negatives (0.106) but pays 0.114 in false positives, which is
expensive for the gate's credibility. `union` is the best compromise given the declared asymmetry.

## What this is not

A probe, not a grid: one field, two cells, three parasite shapes drawn by hand, n=151. It shows a
design choice was settled on biased ground; it is not enough to fix a threshold. Changing the
sensor requires replaying the whole grid with parasitic ink as a fifth factor.
