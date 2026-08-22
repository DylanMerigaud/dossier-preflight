# Duels entre sensors concurrents

Chaque concurrent est juge a SON propre point de fonctionnement, celui qui tient
le budget de faux positifs de 0.2%. Comparer deux sensors a un seuil
commun comparerait une scale et pas un capteur. Les intervalles sont des
intervalles de Wilson a 95%: a trois graines par cell, l'intervalle normal ment.

## consistency

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=zone **(retenu)** | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
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

Meme gagnant a tous les dpi: min_conf=0.0, text_sensor=zone.

## expiry

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retenu)** | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
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

EGALITE, non departage: 18 reglages rendent exactement le meme rappel (1.000) et le meme taux de faux positifs (0.0000) sur l'ensemble du domaine. Ce corpus et cette grid ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: min_conf=0.0, text_sensor=page, min_conf=0.0, text_sensor=zone, min_conf=0.0, text_sensor=union, min_conf=10.0, text_sensor=page.

## forbidden_value

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| min_conf=0.0, text_sensor=page **(retenu)** | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=0.0, text_sensor=zone | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=0.0, text_sensor=union | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| min_conf=10.0, text_sensor=page | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| min_conf=10.0, text_sensor=zone | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| min_conf=10.0, text_sensor=union | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
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

EGALITE, non departage: 3 reglages rendent exactement le meme rappel (0.991) et le meme taux de faux positifs (0.0009) sur l'ensemble du domaine. Ce corpus et cette grid ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: min_conf=0.0, text_sensor=page, min_conf=0.0, text_sensor=zone, min_conf=0.0, text_sensor=union.

## required_checkbox

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| disc_ratio=0.3, ink_threshold=128 **(retenu)** | -14.38 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.3, ink_threshold=160 | -15.42 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.3, ink_threshold=190 | -16.88 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=128 | -7.622 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=160 | -10.96 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.42, ink_threshold=190 | -11.86 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=128 | -7.651 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=128 | -6.538 | 1.000 | 0.0012 | 0.997 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=160 | -5.797 | 0.835 | 0.0000 | 0.837 [0.79, 0.88] | 0.667 [0.61, 0.72] | 1.000 [0.99, 1.00] |
| disc_ratio=0.55, ink_threshold=190 | -5.412 | 0.819 | 0.0006 | 0.833 [0.79, 0.87] | 0.622 [0.56, 0.68] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=160 | 0.7475 | 0.611 | 0.0000 | 0.833 [0.79, 0.87] | 0.000 [0.00, 0.01] | 1.000 [0.99, 1.00] |
| disc_ratio=0.7, ink_threshold=190 | 5.057 | 0.156 | 0.0006 | 0.476 [0.42, 0.53] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Meme gagnant a tous les dpi: disc_ratio=0.3, ink_threshold=128.

## required_field

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| text_sensor=union, min_conf=0.0 | -1 | 1.000 | 0.0003 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| text_sensor=ink, ink_threshold=128 **(retenu)** | -0.345 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
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

Le gagnant CHANGE selon le dpi: 150 dpi -> text_sensor=ink, ink_threshold=128, 200 dpi -> text_sensor=union, min_conf=0.0, 300 dpi -> text_sensor=ink, ink_threshold=128. Le reglage retenu est celui qui tient le mieux sur l'ensemble du domaine, pas celui qui gagne une colonne.

## signature

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| ink_threshold=128, signature_sensor=components **(retenu)** | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=128, signature_sensor=ink | -3.822 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=components | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=160, signature_sensor=ink | -4.043 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=components | -342.7 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| ink_threshold=190, signature_sensor=ink | -4.226 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

EGALITE, non departage: 6 reglages rendent exactement le meme rappel (1.000) et le meme taux de faux positifs (0.0000) sur l'ensemble du domaine. Ce corpus et cette grid ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: ink_threshold=128, signature_sensor=components, ink_threshold=128, signature_sensor=ink, ink_threshold=160, signature_sensor=components, ink_threshold=160, signature_sensor=ink.

