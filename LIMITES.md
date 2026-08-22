# Limites: ou cet outil cesse de marcher

Un outil qui ne dit pas ou il cesse de marcher n'est pas mesure, il est raconte.

## Domaine nominal: numerisation a 150 dpi ou plus

Les points de fonctionnement sont choisis sur les 864 couples de ce domaine,
pas sur les 1152 de la grid entiere. Ce n'est pas une facon de se donner de
beaux chiffres, c'est une consequence mecanique: un dossier est refuse des qu'UN field
required est vide, donc le score du dossier est celui de son PIRE field. Sous le
floor, le Cerfa a des fields que l'OCR ne lit pas, le dossier SAIN atteint alors le
meme score que le dossier fautif, et aucun seuil ne les separe plus. Le point de
fonctionnement reculerait jusqu'a ne plus rien declencher du tout.

Sous ce floor l'outil ne devine pas: le check de resolution se fires et dit
qu'il ne sait pas read_piece la page. Chaque section ci-dessous donne aussi ce que le
check fait HORS domaine, parce que le cacher serait le mentir.

Domaines essayes, du plus large au plus etroit, avec le pire rappel des checks
qui dependent de l'OCR: dpi >= 96 -> 0.000, dpi >= 150 -> 0.997.

Mesure sur 1152 couples cell/seed: angle (0, 0.25, 0.5, 1, 2, 4 deg) x
dpi (96, 150, 200, 300) x qualite JPEG (30, 55, 75, 95) x bruit sigma (0, 3, 6, 12),
trois graines par cell. Chaque check est evalue a son point de fonctionnement,
choisi comme le rappel le plus haut tenant un taux de faux positifs sous 0.2%.

Le seuil est choisi sur les graines 11 et 23, et le chiffre publie est celui de la
seed 37, jamais regardee avant. Choisir un seuil et rapporter son
rappel sur les memes tirages le surestime toujours.

Une cell est declaree HORS DOMAINE quand le rappel y passe sous 95%.

## Ce que la mesure ne couvre pas

- Un seul jeu de trois formulaires (W-9, I-9, Cerfa 14011). Les chiffres ne se
  transportent pas tels quels sur un formulaire dont la typographie ou l'encadrement
  des fields differe. Le Cerfa, dont les fields sont encadres case par case, est deja
  nettement plus dur que les deux formulaires americains.
- Les words ne sont enregistres que dans les zones DECLAREES par l'AcroForm, dilatees
  de 8 px. Une value interdite qui reapparaitrait hors de tout field declare, dans une
  mention manuscrite en marge par exemple, ne serait pas vue.
- Un formulaire sans AcroForm est hors de portee: toute la geometry vient de la
  declaration du PDF, rien n'est mesure a la main.
- Les degradations sont SYNTHETIQUES. Un vrai scanner ajoute des artefacts que cette
  grid n'imite pas: courbure de page, ombre de reliure, poussiere sur la vitre,
  moire de retramage. La grid borne le domaine, elle ne le prouve pas.
- CONSEQUENCE DIRECTE SUR LE CAPTEUR D'ENCRE, et elle n'est plus une hypothese:
  aucune degradation de cette grid n'AJOUTE d'ink etrangere dans une zone, et le
  capteur retenu pour les fields required gagne donc son duel sur un terrain qui lui
  est favorable. Une sonde de 528 readings a mis des le 2026-08-21 un chiffre sur ce
  que ce terrain cachait (sonde-ink-parasite/CONSTAT-ENCRE-PARASITE.md): des qu'au
  moins 0,5% d'ink etrangere entre dans la zone, ce capteur declare REMPLI un field
  VIDE dans 1,000 des cas [0,975, 1,000] sur n=151, contre 0,272 pour l'union des
  sensors de words, 0,185 pleine page et 0,106 en zone. Ce sont des faux negatifs, le
  cote cher de l'asymetrie. La bascule est une falaise posee sur le seuil publie de
  0,345%, et les deux populations ne se chevauchent pas d'une seule reading: le
  capteur se fires 97 fois sur 97 jusqu'a 0,323% d'ink ajoutee et 0 fois sur
  167 a partir de 0,380%. Pas de zone grise, une marche. Pour ce field, 0,35% vaut
  une tache de 9 x 8 px a 200 dpi, une poussiere sur la vitre; un trait de stylo qui
  deborde a peine du field voisin ajoute deja 0,61%.
  LE CAPTEUR ET LE SEUIL N'ONT PAS ETE CHANGES, et c'est la bonne decision tant que
  la mesure est une sonde: un field, deux cellules, trois formes de parasite. Elle
  montre qu'un choix a ete tranche sur un terrain biaise, elle ne suffit pas a fixer
  un seuil. Le changer demande de rejouer cette grid avec l'ink parasite en
  CINQUIEME FACTEUR, et c'est le premier chantier de mesure qui reste ouvert.
- La precision depend de la prevalence. Les courbes la donnent a 10% de dossiers fautifs, value SUPPOSEE et non mesuree.

## Suivi hors protocole: la seule cell ou l'outil manque quelque chose

HORS PROTOCOLE, et il faut le dire avant les chiffres. Les thresholds publies sortent
d'une regle stricte: deux graines calibrent, la troisieme n'est jamais regardee
avant que le chiffre soit ecrit. Les graines de ce suivi ont ete tirees APRES
avoir vu ou l'outil manquait, sur une cell choisie parce qu'elle manquait.
Elles ne deplacent aucun seuil et n'entrent dans aucun chiffre publie ailleurs.
Elles repondent a une seule question: n=18 suffisait-il pour conclure.

Cellule: 300 dpi, JPEG 95, bruit sigma 12.0, check forbidden_value, seuil publie 0.7214.

| jeu | rappel | IC 95% | positifs |
|---|---|---|---|
| graines d'origine (11, 23, 37) | 0.8333 | [0.608, 0.942] | 18 |
| 12 graines neuves | 0.9028 | [0.813, 0.952] | 72 |
| CUMULE | 0.8889 | [0.807, 0.939] | 90 |

Le point estime remonte de 0.833 a 0.889, retour a la moyenne attendu d'un n=18, mais la borne HAUTE
reste a 0.939, sous le floor de 95%. Ce n'est
pas du bruit d'echantillon: le check manque vraiment quelque chose ici.

TEMOIN, et c'est lui qui rend les douze graines interpretables. Meme cell,
memes douze graines, seule la compression change:

- JPEG 95: 65/72 = 0.9028
- JPEG 30: 71/72 = 0.9861

Les graines neuves ne sont donc pas plus dures, c'est la compression. Une
compression FORTE efface le grain du capteur; une compression legere le garde, et
a haute resolution ce grain est assez fin pour se faire read_piece comme de la
structure de caractere. Cette partie du mecanisme est MESUREE.

LA FORME REELLE EST UNE CONJONCTION DE QUATRE FACTEURS, pas de deux:

- angle sous 0.5 deg: 30/30 = 1.0000
- angle a 0.5 deg ou plus: 50/60 = 0.8333

Une marche, pas une pente. La cell fautive est donc 300 dpi ET JPEG 95 ET
bruit 12.0 ET angle >= 0.5 deg. Le balayage a deux
facteurs ci-dessous ne peut pas la voir telle quelle: chaque paire moyenne sur
les deux facteurs restants, donc elle n'en montre que l'ombre. Il sert a la
TROUVER; c'est la liste des pires cellules, qui est deja a quatre facteurs, qui
la NOMME.

Reserve sur le mecanisme: la partie compression est mesuree par le temoin, la
partie angle est SUPPOSEE. L'hypothese est que c'est l'ampleur du
reechantillonnage qui compte et non sa presence, un deskew au-dela d'un
demi-degre etalant le grain fin dans l'epaisseur des traits. Elle n'est pas
testee. Le deskew applique bien une rotation bicubique des 0,25 deg aussi,
donc l'explication paresseuse (pas de reechantillonnage sous 0,5 deg) est fausse.

Reproduire: `python3 grid/corner_followup.py`.

## Diaphonie: qui crie sur le defaut du voisin

Chaque case donne la part des dossiers ou le check de la LIGNE se fires
alors que le defaut injecte appartient a la COLONNE. La diagonale est vide par
construction. Toutes les boxes ne sont pas des fautes: une page rognee emporte de
vrais fields, donc le check des fields required a raison d'y crier. Ce tableau
sert a split la consequence physique de la contamination.

Une LIGNE UNIFORME n'est pas de la crosstalk: c'est le taux de fond du check
qui reapparait. Les variantes partagent les pieces qu'elles n'abiment pas, donc
un check qui se fires a x% sur un dossier clean se fires a x% sur
toutes les colonnes. Ce qui se lit ici, ce sont les boxes qui DEPASSENT la ligne.

| check \ defaut | empty_required | unchecked_box | missing_signat | expired_date | diverging_addr | forbidden_valu | low_resolution | cropped_page | rotated_page |
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

Un point vaut zero declenchement sur 864 dossiers.

## consistency

Reglage retenu: min_conf=0.0, text_sensor=zone. Seuil 0.3939.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 0.958 [0.929, 0.976], declenchements sur dossier clean 0.8403 sur 288 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## cropped_page

Reglage retenu: aucun reglage. Seuil 0.08795.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 0.0000 sur 864 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## expiry

Reglage retenu: min_conf=0.0, text_sensor=page. Seuil 0.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.566, 1.000], declenchements sur dossier clean 0.0000 sur 2 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## forbidden_value

Reglage retenu: min_conf=0.0, text_sensor=page. Seuil 0.7214.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 0.991 | [0.980, 0.996] | 0.0009 | [0.0003, 0.0025] | 0.0052 | 576 |
| VALIDATION (seed 37, jamais vue) | 0.997 | [0.981, 0.999] | 0.0006 | [0.0001, 0.0033] | 0.0035 | 288 |
| ensemble | 0.993 | [0.985, 0.997] | 0.0008 | [0.0003, 0.0020] | 0.0046 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 6 sur 288.

Pires CROISEMENTS de deux facteurs. Une reading axe par axe peut mentir par
omission: trois valeurs marginales toutes au-dessus du floor peuvent se
croiser en une cell qui passe dessous.

- dpi x sigma = [300, 12.0]: rappel 0.931 [0.848, 0.970] sur 72 positifs
- angle x jpeg = [1.0, 95]: rappel 0.944 [0.819, 0.985] sur 36 positifs
- angle x sigma = [2.0, 12.0]: rappel 0.944 [0.819, 0.985] sur 36 positifs
- dpi x jpeg = [300, 95]: rappel 0.944 [0.866, 0.978] sur 72 positifs

Cibles saines qui se declenchent AU SEUIL RETENU, celles qui coutent la credibilite:

- identity / A COMPLETER: 4 fois sur 864

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 0.042 [0.024, 0.071], declenchements sur dossier clean 0.0000 sur 1728 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

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

## required_checkbox

Reglage retenu: disc_ratio=0.3, ink_threshold=128. Seuil -14.38.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 0.0000 sur 864 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## required_field

Reglage retenu: text_sensor=ink, ink_threshold=128. Seuil -0.345.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0003] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0007] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0002] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 0.0000 sur 5760 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## resolution

Reglage retenu: aucun reglage. Seuil -148.5.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 1.0000 sur 864 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Pour CE check, ces declenchements hors domaine ne sont pas des faux
positifs: c'est exactement son task. Il est la pour dire qu'une page
numerisee sous le floor ne doit pas etre jugee par les autres.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## rotated_page

Reglage retenu: aucun reglage. Seuil 0.3585.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0022] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0015] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 0.0000 sur 864 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

## signature

Reglage retenu: ink_threshold=128, signature_sensor=components. Seuil -342.1.

| jeu | rappel | IC 95% | faux positifs par target | IC 95% | par dossier clean | positifs |
|---|---|---|---|---|---|---|
| calibration (graines 11 et 23) | 1.000 | [0.993, 1.000] | 0.0000 | [0.0000, 0.0066] | 0.0000 | 576 |
| VALIDATION (seed 37, jamais vue) | 1.000 | [0.987, 1.000] | 0.0000 | [0.0000, 0.0132] | 0.0000 | 288 |
| ensemble | 1.000 | [0.996, 1.000] | 0.0000 | [0.0000, 0.0044] | 0.0000 | 864 |

Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au
moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si
la gate reste credible.

Cellules sous le floor: 0 sur 288.

Hors domaine (dpi < 150), CAPTEURS BRUTS, c'est-a-dire ce que l'outil ferait
s'il n'avait pas la regle d'abstention: rappel 1.000 [0.987, 1.000], declenchements sur dossier clean 0.0000 sur 288 cibles.
Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: en
production, un check qui LIT s'abstient sous le floor au lieu de produire
ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une mesure
ne peut pas dependre du comportement qu'elle sert a regler.

Aucune cell du domaine explore ne passe sous le floor.

Rappel par facteur, au seuil retenu:

- angle: 0.0 -> 1.000 [0.97, 1.00], 0.25 -> 1.000 [0.97, 1.00], 0.5 -> 1.000 [0.97, 1.00], 1.0 -> 1.000 [0.97, 1.00], 2.0 -> 1.000 [0.97, 1.00], 4.0 -> 1.000 [0.97, 1.00]
- dpi: 150 -> 1.000 [0.99, 1.00], 200 -> 1.000 [0.99, 1.00], 300 -> 1.000 [0.99, 1.00]
- jpeg: 30 -> 1.000 [0.98, 1.00], 55 -> 1.000 [0.98, 1.00], 75 -> 1.000 [0.98, 1.00], 95 -> 1.000 [0.98, 1.00]
- sigma: 0.0 -> 1.000 [0.98, 1.00], 3.0 -> 1.000 [0.98, 1.00], 6.0 -> 1.000 [0.98, 1.00], 12.0 -> 1.000 [0.98, 1.00]

