# Duels between competing sensors

Each contender is judged at ITS OWN operating point, the one that holds the
false positive budget of 0.2%. Comparing two sensors at a common
threshold would compare a scale and not a sensor. The intervals are 95% Wilson
intervals: at three seeds per cell, the normal interval lies.

## consistency

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=zone **(retained)** | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=union | 0.4416 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=zone | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=union | 0.4416 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=zone | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=union | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=union | 0.4848 | 1.000 | 0.0017 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=10.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=20.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=40.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=40.0, text_sensor=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=union | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=union | 1.8 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| min_conf=0.0, text_sensor=zone **(retained)** | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 0.997 [0.98, 1.00] | 0.997 [0.98, 1.00] |
| min_conf=20.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=10.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=20.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=40.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=40.0, text_sensor=zone | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=zone | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=60.0, text_sensor=union | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=page | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=zone | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| min_conf=80.0, text_sensor=union | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Recall lost between level 0.0 and level 0.04: min_conf=20.0, text_sensor=zone +0.003, min_conf=0.0, text_sensor=zone +0.000, min_conf=0.0, text_sensor=union +0.000, min_conf=10.0, text_sensor=zone +0.000.

Same winner at every dpi: min_conf=0.0, text_sensor=zone.

## expiry

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retained)** | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=60.0, text_sensor=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=60.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=60.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=80.0, text_sensor=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=80.0, text_sensor=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=80.0, text_sensor=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retained)** | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=0.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=0.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=page | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=10.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=10.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=page | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=20.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=20.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=page | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=40.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=40.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=60.0, text_sensor=page | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=60.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=60.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=80.0, text_sensor=page | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.98, 1.00] |
| min_conf=80.0, text_sensor=zone | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| min_conf=80.0, text_sensor=union | 1.000 [1.00, 1.00] | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

Recall lost between level 0.0 and level 0.04: min_conf=0.0, text_sensor=page +0.000, min_conf=0.0, text_sensor=zone +0.000, min_conf=0.0, text_sensor=union +0.000, min_conf=10.0, text_sensor=page +0.000.

TIE, not broken: 18 settings return exactly the same recall (1.000) and the same false positive rate (0.0000) over the whole domain. This corpus and this grid do not tell them apart. The retained setting is the first of the list, and that choice is backed by no measurement: min_conf=0.0, text_sensor=page, min_conf=0.0, text_sensor=zone, min_conf=0.0, text_sensor=union, min_conf=10.0, text_sensor=page.

## forbidden_value

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retained)** | 0.7214 | 0.991 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=0.0, text_sensor=zone | 0.7214 | 0.991 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=0.0, text_sensor=union | 0.7214 | 0.991 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=10.0, text_sensor=page | 0.7434 | 0.917 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| min_conf=10.0, text_sensor=zone | 0.7434 | 0.917 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| min_conf=10.0, text_sensor=union | 0.7434 | 0.917 | 0.0007 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| min_conf=20.0, text_sensor=page | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| min_conf=20.0, text_sensor=zone | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| min_conf=20.0, text_sensor=union | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| min_conf=40.0, text_sensor=page | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| min_conf=40.0, text_sensor=zone | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| min_conf=40.0, text_sensor=union | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| min_conf=60.0, text_sensor=page | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| min_conf=60.0, text_sensor=zone | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| min_conf=60.0, text_sensor=union | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| min_conf=80.0, text_sensor=page | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |
| min_conf=80.0, text_sensor=zone | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |
| min_conf=80.0, text_sensor=union | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retained)** | 0.993 [0.98, 1.00] | 0.969 [0.94, 0.98] | 0.988 [0.97, 1.00] | 0.957 [0.93, 0.97] |
| min_conf=0.0, text_sensor=zone | 0.993 [0.98, 1.00] | 0.969 [0.94, 0.98] | 0.988 [0.97, 1.00] | 0.957 [0.93, 0.97] |
| min_conf=0.0, text_sensor=union | 0.993 [0.98, 1.00] | 0.969 [0.94, 0.98] | 0.988 [0.97, 1.00] | 0.957 [0.93, 0.97] |
| min_conf=10.0, text_sensor=page | 0.913 [0.89, 0.93] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.914 [0.88, 0.94] |
| min_conf=10.0, text_sensor=zone | 0.913 [0.89, 0.93] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.914 [0.88, 0.94] |
| min_conf=10.0, text_sensor=union | 0.913 [0.89, 0.93] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.914 [0.88, 0.94] |
| min_conf=20.0, text_sensor=page | 0.904 [0.88, 0.92] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.910 [0.87, 0.94] |
| min_conf=20.0, text_sensor=zone | 0.904 [0.88, 0.92] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.910 [0.87, 0.94] |
| min_conf=20.0, text_sensor=union | 0.904 [0.88, 0.92] | 0.944 [0.91, 0.96] | 0.914 [0.88, 0.94] | 0.910 [0.87, 0.94] |
| min_conf=40.0, text_sensor=page | 0.897 [0.87, 0.92] | 0.941 [0.91, 0.96] | 0.904 [0.87, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=40.0, text_sensor=zone | 0.897 [0.87, 0.92] | 0.941 [0.91, 0.96] | 0.904 [0.87, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=40.0, text_sensor=union | 0.897 [0.87, 0.92] | 0.941 [0.91, 0.96] | 0.904 [0.87, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=60.0, text_sensor=page | 0.895 [0.87, 0.91] | 0.941 [0.91, 0.96] | 0.901 [0.86, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=60.0, text_sensor=zone | 0.895 [0.87, 0.91] | 0.941 [0.91, 0.96] | 0.901 [0.86, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=60.0, text_sensor=union | 0.895 [0.87, 0.91] | 0.941 [0.91, 0.96] | 0.901 [0.86, 0.93] | 0.910 [0.87, 0.94] |
| min_conf=80.0, text_sensor=page | 0.688 [0.66, 0.72] | 0.809 [0.76, 0.85] | 0.747 [0.70, 0.79] | 0.802 [0.76, 0.84] |
| min_conf=80.0, text_sensor=zone | 0.688 [0.66, 0.72] | 0.809 [0.76, 0.85] | 0.747 [0.70, 0.79] | 0.802 [0.76, 0.84] |
| min_conf=80.0, text_sensor=union | 0.688 [0.66, 0.72] | 0.809 [0.76, 0.85] | 0.747 [0.70, 0.79] | 0.802 [0.76, 0.84] |

Recall lost between level 0.0 and level 0.04: min_conf=0.0, text_sensor=page +0.036, min_conf=0.0, text_sensor=zone +0.036, min_conf=0.0, text_sensor=union +0.036, min_conf=10.0, text_sensor=page -0.000.

TIE, not broken: 3 settings return exactly the same recall (0.991) and the same false positive rate (0.0007) over the whole domain. This corpus and this grid do not tell them apart. The retained setting is the first of the list, and that choice is backed by no measurement: min_conf=0.0, text_sensor=page, min_conf=0.0, text_sensor=zone, min_conf=0.0, text_sensor=union.

## required_checkbox

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| disc_ratio=0.3, ink_threshold=128 **(retained)** | -14.38 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.3, ink_threshold=160 | -15.42 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.3, ink_threshold=190 | -16.88 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=128 | -7.622 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=160 | -10.49 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=190 | -11.86 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=128 | -7.425 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=128 | -6.085 | 0.993 | 0.0000 | 0.990 [0.97, 1.00] | 0.983 [0.96, 0.99] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=160 | -6.783 | 0.946 | 0.0017 | 0.837 [0.79, 0.88] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=190 | -5.412 | 0.819 | 0.0004 | 0.833 [0.79, 0.87] | 0.622 [0.56, 0.68] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=160 | -0.179 | 0.720 | 0.0017 | 0.833 [0.79, 0.87] | 0.309 [0.26, 0.36] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=190 | 5.057 | 0.156 | 0.0004 | 0.476 [0.42, 0.53] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| disc_ratio=0.3, ink_threshold=128 **(retained)** | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.336 [0.29, 0.39] |
| disc_ratio=0.3, ink_threshold=160 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.333 [0.28, 0.39] |
| disc_ratio=0.3, ink_threshold=190 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.333 [0.28, 0.39] |
| disc_ratio=0.42, ink_threshold=128 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.438 [0.39, 0.49] |
| disc_ratio=0.42, ink_threshold=160 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.574 [0.52, 0.63] |
| disc_ratio=0.42, ink_threshold=190 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.515 [0.46, 0.57] |
| disc_ratio=0.55, ink_threshold=128 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.534 [0.48, 0.59] |
| disc_ratio=0.7, ink_threshold=128 | 0.991 [0.98, 1.00] | 1.000 [0.99, 1.00] | 0.994 [0.98, 1.00] | 0.623 [0.57, 0.67] |
| disc_ratio=0.55, ink_threshold=160 | 0.946 [0.93, 0.96] | 0.667 [0.61, 0.72] | 0.799 [0.75, 0.84] | 0.512 [0.46, 0.57] |
| disc_ratio=0.55, ink_threshold=190 | 0.818 [0.79, 0.84] | 0.559 [0.50, 0.61] | 0.660 [0.61, 0.71] | 0.386 [0.33, 0.44] |
| disc_ratio=0.7, ink_threshold=160 | 0.714 [0.68, 0.74] | 0.509 [0.46, 0.56] | 0.565 [0.51, 0.62] | 0.395 [0.34, 0.45] |
| disc_ratio=0.7, ink_threshold=190 | 0.159 [0.14, 0.18] | 0.080 [0.06, 0.11] | 0.123 [0.09, 0.16] | 0.117 [0.09, 0.16] |

Recall lost between level 0.0 and level 0.04: disc_ratio=0.3, ink_threshold=160 +0.667, disc_ratio=0.3, ink_threshold=190 +0.667, disc_ratio=0.3, ink_threshold=128 +0.664, disc_ratio=0.42, ink_threshold=128 +0.562.

TIE, not broken: 7 settings return exactly the same recall (1.000) and the same false positive rate (0.0000) over the whole domain. This corpus and this grid do not tell them apart. The retained setting is the first of the list, and that choice is backed by no measurement: disc_ratio=0.3, ink_threshold=128, disc_ratio=0.3, ink_threshold=160, disc_ratio=0.3, ink_threshold=190, disc_ratio=0.42, ink_threshold=128.

## required_field

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| text_sensor=union, min_conf=0.0 | -0.5 | 1.000 | 0.0016 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=128 **(retained)** | -0.345 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=160 | -0.59 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=190 | -0.5895 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=page, min_conf=0.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=0.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| text_sensor=union, min_conf=0.0 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=128 **(retained)** | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=160 | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=190 | 1.000 [1.00, 1.00] | 0.991 [0.97, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=page, min_conf=0.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=10.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=20.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=40.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=60.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=page, min_conf=80.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=0.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=10.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=20.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=40.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=60.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=zone, min_conf=80.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=10.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=20.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=40.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=60.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| text_sensor=union, min_conf=80.0 | 0.000 [0.00, 0.00] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Recall lost between level 0.0 and level 0.04: text_sensor=union, min_conf=0.0 +0.000, text_sensor=ink, ink_threshold=128 +0.000, text_sensor=ink, ink_threshold=160 +0.000, text_sensor=ink, ink_threshold=190 +0.000.

The winner CHANGES with dpi: 150 dpi -> text_sensor=ink, ink_threshold=128, 200 dpi -> text_sensor=union, min_conf=0.0, 300 dpi -> text_sensor=ink, ink_threshold=128. The retained setting is the one that holds best over the whole domain, not the one that wins a column.

## signature

| settings | threshold | global recall | global fpr | recall 150 dpi | recall 200 dpi | recall 300 dpi |
|---|---|---|---|---|---|---|
| ink_threshold=128, signature_sensor=components **(retained)** | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=128, signature_sensor=ink | -3.822 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=components | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=ink | -4.043 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=components | -342.7 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=ink | -4.226 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

By parasite level (fraction of foreign ink laid in a watched zone before degradation):

| settings | recall @ 0.0 | recall @ 0.002 | recall @ 0.01 | recall @ 0.04 |
|---|---|---|---|---|
| ink_threshold=128, signature_sensor=components **(retained)** | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=128, signature_sensor=ink | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=components | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=ink | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=components | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 0.994 [0.98, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=ink | 1.000 [1.00, 1.00] | 1.000 [0.99, 1.00] | 0.756 [0.71, 0.80] | 1.000 [0.99, 1.00] |

Recall lost between level 0.0 and level 0.04: ink_threshold=128, signature_sensor=components +0.000, ink_threshold=128, signature_sensor=ink +0.000, ink_threshold=160, signature_sensor=components +0.000, ink_threshold=160, signature_sensor=ink +0.000.

TIE, not broken: 6 settings return exactly the same recall (1.000) and the same false positive rate (0.0000) over the whole domain. This corpus and this grid do not tell them apart. The retained setting is the first of the list, and that choice is backed by no measurement: ink_threshold=128, signature_sensor=components, ink_threshold=128, signature_sensor=ink, ink_threshold=160, signature_sensor=components, ink_threshold=160, signature_sensor=ink.

