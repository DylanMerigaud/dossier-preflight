# Limites: ou cet outil cesse de marcher

Un outil qui ne dit pas ou il cesse de marcher n'est pas mesure, il est raconte.

## Domaine nominal: numerisation a 150 dpi ou plus

Les points de fonctionnement sont choisis sur les 864 couples de ce domaine,
pas sur les 1152 de la grille entiere. Ce n'est pas une facon de se donner de
beaux chiffres, c'est une consequence mecanique: un dossier est refuse des qu'UN champ
requis est vide, donc le score du dossier est celui de son PIRE champ. Sous le
plancher, le Cerfa a des champs que l'OCR ne lit pas, le dossier SAIN atteint alors le
meme score que le dossier fautif, et aucun seuil ne les separe plus. Le point de
fonctionnement reculerait jusqu'a ne plus rien declencher du tout.

Sous ce plancher l'outil ne devine pas: le controle de resolution se declenche et dit
qu'il ne sait pas lire la page. Chaque section ci-dessous donne aussi ce que le
controle fait HORS domaine, parce que le cacher serait le mentir.

Domaines essayes, du plus large au plus etroit, avec le pire rappel des controles
qui dependent de l'OCR: dpi >= 96 -> 0.000, dpi >= 150 -> 0.997.

Mesure sur 1152 couples cellule/graine: angle (0, 0.25, 0.5, 1, 2, 4 deg) x
dpi (96, 150, 200, 300) x qualite JPEG (30, 55, 75, 95) x bruit sigma (0, 3, 6, 12),
trois graines par cellule. Chaque controle est evalue a son point de fonctionnement,
choisi comme le rappel le plus haut tenant un taux de faux positifs sous 0.2%.

Le seuil est choisi sur les graines 11 et 23, et le chiffre publie est celui de la
graine 37, jamais regardee avant. Choisir un seuil et rapporter son
rappel sur les memes tirages le surestime toujours.

Une cellule est declaree HORS DOMAINE quand le rappel y passe sous 95%.

## Ce que la mesure ne couvre pas

- Un seul jeu de trois formulaires (W-9, I-9, Cerfa 14011). Les chiffres ne se
  transportent pas tels quels sur un formulaire dont la typographie ou l'encadrement
  des champs differe. Le Cerfa, dont les champs sont encadres case par case, est deja
  nettement plus dur que les deux formulaires americains.
- Les mots ne sont enregistres que dans les zones DECLAREES par l'AcroForm, dilatees
  de 8 px. Une valeur interdite qui reapparaitrait hors de tout champ declare, dans une
  mention manuscrite en marge par exemple, ne serait pas vue.
- Un formulaire sans AcroForm est hors de portee: toute la geometrie vient de la
  declaration du PDF, rien n'est mesure a la main.
- Les degradations sont SYNTHETIQUES. Un vrai scanner ajoute des artefacts que cette
  grille n'imite pas: courbure de page, ombre de reliure, poussiere sur la vitre,
  moire de retramage. La grille borne le domaine, elle ne le prouve pas.
- CONSEQUENCE DIRECTE SUR LE CAPTEUR D'ENCRE, et elle est genante parce que ce capteur
  gagne son duel: aucune degradation de cette grille n'AJOUTE d'encre etrangere dans
  une zone. Un tampon, une ombre de pliure, un trait de stylo qui deborde du champ
  voisin feraient dire a ce capteur qu'un champ vide est rempli, c'est-a-dire un faux
  negatif, le cote cher de l'asymetrie. Il gagne ici sur un terrain qui lui est
  favorable, et le dire fait partie du resultat. Le capteur de mots, lui, ne confond
  pas une tache avec une valeur, et son point de fonctionnement mesure est juste a
  cote (voir le duel).
- La precision depend de la prevalence. Les courbes la donnent a 10% de dossiers fautifs, valeur SUPPOSEE et non mesuree.

## case_obligatoire

Reglage retenu: part_disque=0.3, seuil_encre=128. Seuil -14.38.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 0.0000 sur 864 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## champ_requis

Reglage retenu: capteur_texte=encre, seuil_encre=128. Seuil -0.345.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0003] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0007] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0002] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 0.0000 sur 5760 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## coherence

Reglage retenu: conf_min=0.0, capteur_texte=zone. Seuil 0.3939.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 0.958 [0.929, 0.976], declenchements sur dossier sain 0.8403 sur 288 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## page_coupee

Reglage retenu: aucun reglage. Seuil 0.08795.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 0.0000 sur 864 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## page_tournee

Reglage retenu: aucun reglage. Seuil 0.3585.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 0.0000 sur 864 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## resolution

Reglage retenu: aucun reglage. Seuil -150.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 1.0000 sur 864 cibles.

Pour CE controle, ces declenchements hors domaine ne sont pas des faux
positifs: c'est exactement son travail. Il est la pour dire qu'une page
numerisee sous le plancher ne doit pas etre jugee par les autres.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## signature

Reglage retenu: seuil_encre=128, capteur_signature=composantes. Seuil -342.1.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.987, 1.000], declenchements sur dossier sain 0.0000 sur 288 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## valeur_interdite

Reglage retenu: conf_min=0.0, capteur_texte=page. Seuil 0.7214.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 0.991 | [0.980, 0.996] | 0.0009 | [0.0003, 0.0025] | 0.0052 | 576 |
| VALIDATION (graine 37, jamais vue) | 0.997 | [0.981, 0.999] | 0.0006 | [0.0001, 0.0033] | 0.0035 | 288 |
| ensemble | 0.993 | [0.985, 0.997] | 0.0008 | [0.0003, 0.0020] | 0.0046 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 6 sur 288.

Cibles saines qui se declenchent AU SEUIL RETENU, celles qui coutent la credibilite:

- identite / A COMPLETER: 4 fois sur 864

Hors domaine (dpi < 150), au meme seuil: rappel 0.042 [0.024, 0.071], declenchements sur dossier sain 0.0000 sur 1728 cibles.

Frontiere par facteur, nombre de cellules tombees sur le total:

- angle: 0.0 -> 0/48, 0.25 -> 1/48, 0.5 -> 0/48, 1.0 -> 2/48, 2.0 -> 2/48, 4.0 -> 1/48
- dpi: 150 -> 0/96, 200 -> 0/96, 300 -> 6/96
- jpeg: 30 -> 0/72, 55 -> 1/72, 75 -> 1/72, 95 -> 4/72
- sigma: 0.0 -> 0/72, 3.0 -> 0/72, 6.0 -> 1/72, 12.0 -> 5/72

Les pires cellules (angle, dpi, jpeg, sigma) et leur rappel:

- angle 0.25, 300 dpi, JPEG 55, sigma 12.0: rappel 0.67 sur 3 graines
- angle 1.0, 300 dpi, JPEG 95, sigma 6.0: rappel 0.67 sur 3 graines
- angle 1.0, 300 dpi, JPEG 95, sigma 12.0: rappel 0.67 sur 3 graines
- angle 2.0, 300 dpi, JPEG 75, sigma 12.0: rappel 0.67 sur 3 graines
- angle 2.0, 300 dpi, JPEG 95, sigma 12.0: rappel 0.67 sur 3 graines
- angle 4.0, 300 dpi, JPEG 95, sigma 12.0: rappel 0.67 sur 3 graines

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 0.993 [0.96, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 0.986 [0.95, 1.00], 2.0 -> 0.986 [0.95, 1.00], 4.0 -> 0.993 [0.96, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 0.979 [0.96, 0.99]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 0.995 [0.97, 1.00], 75 -> 0.995 [0.97, 1.00], 95 -> 0.981 [0.95, 0.99]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 0.995 [0.97, 1.00], 12.0 -> 0.977 [0.95, 0.99]

## validite

Reglage retenu: conf_min=0.0, capteur_texte=page. Seuil -207.5.

| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | par dossier sain | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (graine 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si
la gate reste credible.

Cellules sous le plancher: 0 sur 288.

Hors domaine (dpi < 150), au meme seuil: rappel 1.000 [0.566, 1.000], declenchements sur dossier sain 0.0000 sur 2 cibles.

Aucune cellule du domaine explore ne passe sous le plancher.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

