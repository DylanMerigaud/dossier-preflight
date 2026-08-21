# Duels entre capteurs concurrents

Chaque concurrent est juge a SON propre point de fonctionnement, celui qui tient
le budget de faux positifs de 0.2%. Comparer deux capteurs a un seuil
commun comparerait une echelle et pas un capteur. Les intervalles sont des
intervalles de Wilson a 95%: a trois graines par cellule, l'intervalle normal ment.

## case_obligatoire

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| part_disque=0.3, seuil_encre=128 **(retenu)** | -14.38 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.3, seuil_encre=160 | -15.42 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.3, seuil_encre=190 | -16.88 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.42, seuil_encre=128 | -7.622 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.42, seuil_encre=160 | -10.96 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.42, seuil_encre=190 | -11.86 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.55, seuil_encre=128 | -7.651 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.7, seuil_encre=128 | -6.538 | 1.000 | 0.0012 | 0.997 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| part_disque=0.55, seuil_encre=160 | -5.797 | 0.835 | 0.0000 | 0.837 [0.79, 0.88] | 0.667 [0.61, 0.72] | 1.000 [0.99, 1.00] |
| part_disque=0.55, seuil_encre=190 | -5.412 | 0.819 | 0.0006 | 0.833 [0.79, 0.87] | 0.622 [0.56, 0.68] | 1.000 [0.99, 1.00] |
| part_disque=0.7, seuil_encre=160 | 0.7475 | 0.611 | 0.0000 | 0.833 [0.79, 0.87] | 0.000 [0.00, 0.01] | 1.000 [0.99, 1.00] |
| part_disque=0.7, seuil_encre=190 | 5.057 | 0.156 | 0.0006 | 0.476 [0.42, 0.53] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Meme gagnant a tous les dpi: part_disque=0.3, seuil_encre=128.

## champ_requis

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| capteur_texte=union, conf_min=0.0 | -1 | 1.000 | 0.0003 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| capteur_texte=encre, seuil_encre=128 **(retenu)** | -0.345 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| capteur_texte=encre, seuil_encre=160 | -0.59 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| capteur_texte=encre, seuil_encre=190 | -0.5895 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| capteur_texte=page, conf_min=0.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=page, conf_min=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=page, conf_min=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=page, conf_min=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=page, conf_min=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=page, conf_min=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=0.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=zone, conf_min=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=union, conf_min=10.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=union, conf_min=20.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=union, conf_min=40.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=union, conf_min=60.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| capteur_texte=union, conf_min=80.0 | 1 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Le gagnant CHANGE selon le dpi: 150 dpi -> capteur_texte=encre, seuil_encre=128, 200 dpi -> capteur_texte=union, conf_min=0.0, 300 dpi -> capteur_texte=encre, seuil_encre=128. Le reglage retenu est celui qui tient le mieux sur l'ensemble du domaine, pas celui qui gagne une colonne.

## coherence

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| conf_min=0.0, capteur_texte=zone **(retenu)** | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=0.0, capteur_texte=union | 0.4416 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=10.0, capteur_texte=zone | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=10.0, capteur_texte=union | 0.4416 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=20.0, capteur_texte=zone | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=20.0, capteur_texte=union | 0.3939 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=40.0, capteur_texte=union | 0.4848 | 1.000 | 0.0017 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=0.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=10.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=20.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=40.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=40.0, capteur_texte=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=60.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=60.0, capteur_texte=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=60.0, capteur_texte=union | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=80.0, capteur_texte=page | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=80.0, capteur_texte=zone | 2 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |
| conf_min=80.0, capteur_texte=union | 1.8 | 0.000 | 0.0000 | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] | 0.000 [0.00, 0.01] |

Meme gagnant a tous les dpi: conf_min=0.0, capteur_texte=zone.

## signature

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| seuil_encre=128, capteur_signature=composantes **(retenu)** | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| seuil_encre=128, capteur_signature=encre | -3.822 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| seuil_encre=160, capteur_signature=composantes | -342.1 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| seuil_encre=160, capteur_signature=encre | -4.043 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| seuil_encre=190, capteur_signature=composantes | -342.7 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| seuil_encre=190, capteur_signature=encre | -4.226 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

EGALITE, non departage: 6 reglages rendent exactement le meme rappel (1.000) et le meme taux de faux positifs (0.0000) sur l'ensemble du domaine. Ce corpus et cette grille ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: seuil_encre=128, capteur_signature=composantes, seuil_encre=128, capteur_signature=encre, seuil_encre=160, capteur_signature=composantes, seuil_encre=160, capteur_signature=encre.

## valeur_interdite

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| conf_min=0.0, capteur_texte=page **(retenu)** | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| conf_min=0.0, capteur_texte=zone | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| conf_min=0.0, capteur_texte=union | 0.7214 | 0.991 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.979 [0.96, 0.99] |
| conf_min=10.0, capteur_texte=page | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| conf_min=10.0, capteur_texte=zone | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| conf_min=10.0, capteur_texte=union | 0.7434 | 0.917 | 0.0009 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.740 [0.69, 0.79] |
| conf_min=20.0, capteur_texte=page | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| conf_min=20.0, capteur_texte=zone | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| conf_min=20.0, capteur_texte=union | 0.8487 | 0.908 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 0.712 [0.66, 0.76] |
| conf_min=40.0, capteur_texte=page | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| conf_min=40.0, capteur_texte=zone | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| conf_min=40.0, capteur_texte=union | 0.8237 | 0.905 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.701 [0.65, 0.75] |
| conf_min=60.0, capteur_texte=page | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| conf_min=60.0, capteur_texte=zone | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| conf_min=60.0, capteur_texte=union | 0.8237 | 0.903 | 0.0000 | 1.000 [0.99, 1.00] | 0.990 [0.97, 1.00] | 0.694 [0.64, 0.74] |
| conf_min=80.0, capteur_texte=page | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |
| conf_min=80.0, capteur_texte=zone | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |
| conf_min=80.0, capteur_texte=union | 0.8237 | 0.686 | 0.0000 | 0.965 [0.94, 0.98] | 0.403 [0.35, 0.46] | 0.694 [0.64, 0.74] |

EGALITE, non departage: 3 reglages rendent exactement le meme rappel (0.991) et le meme taux de faux positifs (0.0009) sur l'ensemble du domaine. Ce corpus et cette grille ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: conf_min=0.0, capteur_texte=page, conf_min=0.0, capteur_texte=zone, conf_min=0.0, capteur_texte=union.

## validite

| reglage | seuil | rappel global | fpr global | rappel 150 dpi | rappel 200 dpi | rappel 300 dpi |
|---|---|---|---|---|---|---|
| conf_min=0.0, capteur_texte=page **(retenu)** | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=0.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=0.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=10.0, capteur_texte=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=10.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=10.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=20.0, capteur_texte=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=20.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=20.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=40.0, capteur_texte=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=40.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=40.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=60.0, capteur_texte=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=60.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=60.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=80.0, capteur_texte=page | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=80.0, capteur_texte=zone | -207.5 | 1.000 | 0.0000 | 1.000 [0.98, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |
| conf_min=80.0, capteur_texte=union | -207.5 | 1.000 | 0.0000 | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] | 1.000 [0.99, 1.00] |

EGALITE, non departage: 18 reglages rendent exactement le meme rappel (1.000) et le meme taux de faux positifs (0.0000) sur l'ensemble du domaine. Ce corpus et cette grille ne les distinguent pas. Le reglage retenu est le premier de la liste, et ce choix n'est appuye par aucune mesure: conf_min=0.0, capteur_texte=page, conf_min=0.0, capteur_texte=zone, conf_min=0.0, capteur_texte=union, conf_min=10.0, capteur_texte=page.

