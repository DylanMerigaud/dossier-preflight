# Le capteur d'ink s'effondre des qu'une ink etrangere entre dans la zone

Mesure du 2026-08-21, hors depot, sur `git archive` du commit 3a4e682. Rien n'a ete ecrit
dans l'arbre. Reproduire: `experience.py --procs 13` puis les agregats de ce fichier.

## La question

La grid croise angle, resolution, compression et bruit. Aucune de ces quatre degradations
n'AJOUTE d'ink dans une zone: elles deplacent, floutent ou salissent celle qui y est deja.
Or le capteur retenu pour "ce field required est-il vide" est un capteur d'ink, qui ne sait
pas ce qui est ecrit mais seulement qu'il y a quelque chose de plus sombre qu'avant. Il a
gagne son duel sur un terrain qui lui est favorable.

## Le protocole

Trois formes d'ink etrangere, posees sur le render PROPRE avant degradation, donc subissant
ensuite la meme rotation, le meme bruit, le meme blur et la meme compression que la page:
tache (depot localise), pliure (ombre de pli en travers), trait (stylo du field voisin qui
deborde). Champ target: `employment` / `City or Town`, celui que la variant `empty_required_field`
laisse vide. Deux cellules (0,25 deg / 200 dpi / JPEG 95 / bruit 0 et 0,5 deg / 200 dpi /
JPEG 55 / bruit 6), six graines, sept intensites plus un control sans parasite. 528 readings.

Temoin sans parasite: 0 faux negatif et 0 faux positif pour les quatre sensors. Le banc est
clean.

## Le resultat, sur ink etrangere reelle (au moins 0,5% ajoute dans la zone)

FAUX NEGATIFS, un field VIDE declare rempli. Le filing refuse le dossier et person n'a
prevenu: c'est le cote cher de l'asymetrie declaree par le projet.

| capteur | faux negatifs | IC 95% | n |
|---|---|---|---|
| ink (RETENU par la grid) | **1.000** | [0.975, 1.000] | 151 |
| union | 0.272 | [0.207, 0.347] | 151 |
| page | 0.185 | [0.132, 0.255] | 151 |
| zone | 0.106 | [0.066, 0.165] | 151 |

FAUX POSITIFS, un field REMPLI declare vide, memes conditions. C'est le prix a payer:

| capteur | faux positifs | IC 95% | n |
|---|---|---|---|
| ink | 0.000 | [0.000, 0.014] | 264 |
| union | 0.030 | [0.015, 0.059] | 264 |
| zone | 0.114 | [0.081, 0.158] | 264 |
| page | 0.136 | [0.100, 0.183] | 264 |

## La bascule est exactement au threshold publie

Le threshold retenu est 0,345% d'ink ajoutee. Mesure, par value d'ink reellement ajoutee:

    0,00 a 0,32%  ->  se fires 97 fois sur 97
    0,38% et plus ->  se fires  0 fois sur 151

Pas de zone grise: une falaise. Pour ce field de 415 x 38 = 15 770 px canoniques, 0,35% vaut
55 pixels, c'est-a-dire une tache d'environ 9 x 8 px a 200 dpi. Une poussiere sur la vitre du
scanner suffit. Un trait de stylo qui deborde a peine du field voisin ajoute deja 0,61%.

L'ombre de pliure a un comportement a part et il est instructif: tant qu'elle laisse le papier
au-dessus du threshold de binarisation (128), elle est parfaitement invisible au capteur, puis
toute la bande bascule d'un coup (0,00% d'ink ajoutee, puis 39%, puis 100%).

## Ce que les sensors de words ratent, eux

Leur mode d'echec n'est pas le meme et il est non monotone: une tache de la bonne taille se
fait LIRE comme des lettres. A l'intensity 0,020, l'OCR de zone rend "FS ee en ee, Be" et
conclut que le field est rempli (1 declenchement sur 12), alors qu'il rend une chaine vide et
se fires 12 fois sur 12 aux intensites voisines, plus petites comme plus grandes. Un
capteur de words ne confond pas une tache avec une value en general, mais il le fait parfois.

## Ce que je recommande, et ce que ca coute

Passer le check des fields required de `ink` a `union`. Sur la grid publiee, `union`
(confiance minimale 0) tenait deja 1,000 de recall, avec 0,0003 de faux positifs par target
contre 0,0000 pour l'ink: le cout est de trois cibles sur dix mille. En echange, sous ink
etrangere, les faux negatifs passent de 1,000 a 0,272, et les faux positifs de 0,000 a 0,030.

`zone` fait mieux encore sur les faux negatifs (0,106) mais paie 0,114 de faux positifs, ce
qui est cher pour la credibilite de la gate. `union` est le meilleur compromis compte tenu de
l'asymetrie declaree.

## Ce que cette mesure n'est pas

Une sonde ciblee, pas une grid. Un seul field, deux cellules, trois formes de parasite
dessinees par moi, n=151 et n=264. Elle suffit a montrer qu'une decision de conception a ete
prise sur un terrain biaise; elle ne suffit pas a fixer un threshold. Si le capteur change, c'est
la grid complete qui doit le confirmer, avec l'ink parasite ajoutee comme cinquieme
facteur.
