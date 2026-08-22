# dossier-preflight

Ce dossier va-t-il se faire refuser au filing.

Pas de l'extraction, pas de la generation de document: de la CONFORMITE d'un dossier a un
reference externe, mesuree sur ce qui est VRAIMENT IMPRIME. Un field AcroForm peut porter
une value qui ne s'imprime jamais. Le filing, lui, lit la feuille.

## Ce que ca mesure

Neuf checks, chacun avec un threshold LU sur une curve precision/recall, pas choisi a la main.
Grille de 384 cellules (angle x dpi x qualite JPEG x bruit) x 3 graines = 1152 dossiers,
13 824 readings d'images, 121 minutes sur 13 processus. Le threshold est choisi sur les graines 11
et 23; le chiffre ci-dessous est celui de la seed 37, jamais regardee avant.

| check | ce qu'il attrape | capteur retenu | threshold | recall | faux positifs par target |
|---|---|---|---|---|---|
| required_field | un field required jamais rempli | ink ajoutee (threshold 128) | -0.345 | 1.000 | 0.00000 |
| required_checkbox | une case obligatoire non cochee | disque central 0.30 du cote | -14.38 | 1.000 | 0.00000 |
| signature | une signature absente | components connexes | -342.1 | 1.000 | 0.00000 |
| expiry | une piece perimee A L'HORLOGE CHOISIE | date lue par OCR pleine page | 0 (definition) | 1.000 | 0.00000 |
| consistency | la meme data divergente entre deux pieces | OCR de zone, jetons | 0.394 | 1.000 | 0.00000 |
| forbidden_value | une value interdite qui reapparait | OCR pleine page, n-grammes | 0.721 | 0.997 | 0.00058 |
| resolution | un scan sous le floor de lisibilite | scale du recalage | -148.5 dpi | 1.000 | 0.00000 |
| cropped_page | une page tronquee | coverage de l'ink du blank | 0.088 | 1.000 | 0.00000 |
| rotated_page | une page a l'envers | marge de correlation par quarter_turns de tour | 0.359 | 1.000 | 0.00000 |

**CE QUE CE TABLEAU NE COUVRE PAS, ET IL FAUT LE LIRE AVEC LUI.** Les 1152 dossiers, ce sont
UN dossier fictif de trois formulaires (W-9, I-9, Cerfa 14011, page 1 pour chacun), UNE
person inventee, UN seul defaut par check, rendus 1152 fois a travers un modele de bruit
SYNTHETIQUE. Aucun scan reel n'est entre dans cette mesure. Les 1152 mesurent donc le modele
de bruit et pas le monde: un recall de 1,000 est celui du meme defaut revu 864 fois, pas celui
de 864 defauts differents. Ce que ces chiffres ne disent pas: ce que l'outil fait sur un autre
formulaire, sur une autre facon de rater le meme check, ou sur une vraie vitre de scanner
avec sa poussiere, son ombre de reliure et sa courbure de page. `LIMITES.md` detaille chacun
de ces trous, et l'un d'eux touche le capteur qui a gagne son duel.

Le chiffre qu'un utilisateur ressent n'est pas celui de la colonne de droite, c'est celui du
dossier entier: **4 dossiers sur 864 entierement sains portent au moins une alarme, soit
0,46%**, et les quatre viennent du check des values interdites.

Un dossier fautif est refuse au filing: des mois de delai. Une gate qui crie pour rien perd
sa credibilite, et une regle qui crie au loup fait survoler toutes celles d'a cote. Les deux
couts ne sont pas du meme genre, et le point de fonctionnement est choisi avec cette asymetrie
declaree: recall le plus haut tenable sous 0,2% de faux positifs par target.

## Le domain, et ce qui se passe dehors

**Numerisation a 150 dpi ou plus.** En dessous, sensors bruts, le check des values
interdites tombe a 0,042 de recall et la consistency se fires sur 84% des dossiers sains.
Ces deux chiffres ne decrivent pas le produit, ils justifient la regle qui suit: ils sont
mesures SANS l'abstention, parce qu'une mesure ne peut pas dependre du comportement qu'elle
sert a regler.

Sous le floor, l'outil ne devine pas: le check de resolution se fires, et **tout
check qui LIT s'abstient sur la piece concernee**, avec un verdict "indecidable" qui n'est
pas "conforme". Avant cette regle, la consistency criait sur 456 des 864 dossiers portant une
piece a 72 dpi, en comparant des jetons qu'elle n'avait pas su read_piece.

Le threshold de resolution est le seul a ne pas sortir de sa propre curve: sa curve le poserait
a 111 dpi, l'endroit qui separe le mieux la variant fautive du reste. Mais la question que ce
check doit poser n'est pas "cette page est-elle a 72 dpi", c'est "cette page est-elle assez
nette pour que les AUTRES tiennent". Il est donc pose au floor, moins 1% de marge, la marge
valant dix fois l'erreur maximale mesuree de l'estimateur de resolution (0,0133%).

Dans ce domain, l'outil manque quelque chose a un seul endroit, et il est nomme: le check
des values interdites descend a **0,889 de recall [0,807, 0,939] sur 90 positifs** dans la
conjonction 300 dpi ET JPEG 95 ET bruit 12 ET deskew de 0,5 degre ou plus. Sous ce demi
degre, 30 sur 30. La borne haute de l'intervalle reste sous le floor de 95%, donc ce n'est
pas du bruit d'echantillon. Un control a la meme cell en JPEG 30 rend 0,986: c'est bien la
compression, une compression forte effacant le grain du capteur qu'une compression legere
garde. La part du mecanisme qui tient a l'angle reste une hypothese non testee.

`LIMITES.md` donne le detail par check: recall par facteur, pires cellules, pires
croisements de deux factors, matrice de crosstalk, le suivi hors protocole de cette cell,
et ce que la mesure ne couvre pas.

## Les deux duels entre sensors

Le spike avait tranche a n=1 que l'ink etait le mauvais capteur pour du texte. **La grid
le contredit.**

Pour "ce field required est-il vide", quatre sensors concurrents:

| capteur | recall | faux positifs par target |
|---|---|---|
| ink ajoutee, threshold 128 (retenu) | 1.000 | 0.0000 |
| OCR pleine page + OCR de zone, confiance minimale 0 | 1.000 | 0.0003 |
| OCR seul, confiance minimale 10 et plus | 0.000 | 0.0000 |

Le vrai coupable du spike n'etait pas le capteur, c'etait son floor de confiance a 40. Un
field PEIGNE (une case par caractere, le formulaire le declare) se lit "4/1)2" avec une
confiance de 38: les trois chiffres sont la, mais les separateurs cassent le modele de mot de
tesseract. A confiance 40, ce field REMPLI etait declare vide. A confiance 0, l'OCR revient a
egalite avec l'ink.

L'ink gagne quand meme, et il faut dire pourquoi elle gagne ici: aucune degradation de cette
grid n'AJOUTE d'ink etrangere dans une zone. Elle gagne sur un terrain qui lui est
favorable.

**Et voila ce que ce terrain cachait, mesure a part.** Une sonde de 528 readings a pose de
l'ink etrangere (tache, ombre de pliure, trait du field voisin) sur la page AVANT les
degradations. Des qu'au moins 0,5% d'ink etrangere entre dans la zone, sur un field VIDE:

| capteur | faux negatifs, un field vide declare rempli | faux positifs, un field rempli declare vide |
|---|---|---|
| ink, threshold 128 (RETENU) | **1.000** [0.975, 1.000] | 0.000 [0.000, 0.014] |
| union, confiance 0 | 0.272 [0.207, 0.347] | 0.030 [0.015, 0.059] |
| OCR pleine page | 0.185 [0.132, 0.255] | 0.136 [0.100, 0.183] |
| OCR de zone | 0.106 [0.066, 0.165] | 0.114 [0.081, 0.158] |

Le capteur retenu rate **100% des fields vides** dans ces conditions, et ce sont des faux
negatifs, le cote cher de l'asymetrie declaree plus haut: le filing refuse le dossier et
l'outil n'a rien dit. La bascule est une falaise posee exactement sur le threshold publie de
0,345%, et les deux populations ne se chevauchent PAS D'UNE SEULE LECTURE: le capteur se
fires 97 fois sur 97 jusqu'a 0,323% d'ink ajoutee, et 0 fois sur 167 a partir de
0,380%. Il n'y a pas de zone grise, il y a une marche. Pour ce field de 15 770 pixels
canoniques, 0,35% vaut une
tache de 9 x 8 px a 200 dpi, c'est-a-dire une poussiere sur la vitre du scanner. Un trait de
stylo qui deborde a peine du field voisin ajoute deja 0,61%.

Le threshold et le capteur n'ont PAS ete changes, et c'est delibere: cette sonde porte sur un
seul field, deux cellules et trois formes de parasite dessinees a la main, n=151. Elle suffit
a montrer qu'un choix de conception a ete tranche sur un terrain biaise; elle ne suffit pas a
fixer un threshold. Le faire demanderait de rejouer la grid entiere avec l'ink parasite en
cinquieme facteur. En attendant, la ligne du tableau du duel qui dit 0,0000 de faux positifs
pour l'ink reste vraie, et elle ne dit rien de ce que coute son unique mode d'echec.

Pour "cette signature est-elle absente", ink differentielle contre components connexes:
**egalite**. Les six reglages rendent exactement 1,000 de recall et 0,0000 de faux positifs a
tous les dpi. Ce corpus ne les distingue pas, et le settings retenu n'est appuye par aucune
mesure. C'est un resultat, pas un vainqueur.

## Comment ca marche

Trois proprietes portent tout le design, et les trois ont ete payees.

**Le formulaire blank n'est pas une fixture, c'est l'IMAGE DE REFERENCE.** Chaque check est
un differentiel contre lui, les words pre-imprimes lus sur le blank sont soustraits par texte
ET position, et on n'affirme jamais que sur ce qui a ete AJOUTE.

**Les AcroForm DECLARENT leurs zones.** 23 rectangles sur la page 1 du W-9. Aucune coordonnee
n'est mesuree a la main, aucune n'est devinee. Le formulaire declare aussi quels fields sont
des peignes, quel etat vaut "coche", et combien de caracteres il accepte.

**Le blank vient au scan, pas l'inverse.** Ramener un scan dans un repere canonique a 200 dpi
le reechantillonne des que sa resolution differe, et ca detruit le petit texte encadre: sur le
Cerfa, un scan a 300 dpi rendait 0 caractere lisible dans trois fields qui en rendaient 14, 5
et 10 a 200 dpi ou l'scale vaut exactement 1. Les trois filtres de reechantillonnage
echouaient pareil, donc ce n'etait pas le filtre. La grid aurait mesure ce reechantillonnage
et conclu, faux, que l'outil casse a 300 dpi. Le scan reste natif; le blank, render propre et
synthetique, vient a lui.

Avant tout check par coordonnees, la page est redressee (axe d'abord, puis angle fin) et
recalee sur le blank par correlation croisee, ce qui donne gratuitement l'orientation, la
resolution source estimee et la coverage de page. Sans deskew, l'ink lue dans les
zones d'un scan tourne de 0,45 degre annonce 8 boxes cochees sur 8 alors que rien n'est coche.

## Installer

Deux dependances sont SYSTEME et pip ne les installe pas: tesseract, avec les donnees de
language `eng` ET `fra` (le Cerfa est en francais, et sans `fra` ses fields sortent VIDES sans
message d'erreur, ce qui ressemble a un defaut de dossier et n'en est pas un), et poppler pour
`pdftoppm`.

    brew install tesseract tesseract-lang poppler          # macOS
    apt-get install tesseract-ocr tesseract-ocr-fra poppler-utils   # Debian

    pip install -e .            # le coeur
    pip install -e ".[dev]"     # avec pytest
    pip install -e ".[grid]"  # avec matplotlib, seulement pour plot les courbes

Mesure et tests sur Python 3.12.8, tesseract 5.5.1, poppler 26.04. Le floor declare est
3.10 et n'a pas ete teste.

## Lancer sur un dossier a soi

    python3 -m preflight fixtures/reference.yaml \
        --clock filing \
        --piece tax=scans/w9.pdf \
        --piece employment=scans/i9.pdf \
        --piece identity=scans/cerfa.pdf

L'clock est obligatoire. C'est la seule propriete de ce depot que rien d'autre n'outille:
la meme piece est bonne pour un dossier et perimee pour l'autre au meme instant, et un outil
qui prendrait la date du jour en silence la jetterait. Passer un name declare par le
reference (`filing`, `admissibility`) ou une date ISO.

Trois verdicts et pas deux, parce que deux appellent des gestes opposes:

| code | verdict | quoi faire |
|---|---|---|
| 0 | aucun constat | rien, et ce n'est pas une garantie: voir `LIMITES.md` |
| 1 | defaut de dossier | refaire le DOSSIER |
| 2 | l'outil ne sait pas read_piece | refaire le SCAN |
| 64 | erreur d'usage | corriger la ligne de commande |

Le code 2 couvre deux choses de la meme famille: le check de resolution qui se fires,
et les checks qui se sont ABSTENUS sur une piece sous le floor. Une abstention porte un
score nul qui vaut indecidable, jamais conforme. Le check de resolution est du cote scan et
pas du cote dossier parce que c'est deja ce qu'il repond, "je ne sais pas read_piece cette page" et
pas "cette page est fautive".

`--json` pour une sortie machine, `--tout` pour voir aussi les checks qui se taisent.

## Lancer le banc de mesure

    python3 spike/proof.py                    # le premier cas vert, autonome
    python3 -m pytest tests/ -q                # 64 tests, environ 2 min 20 (ils rendent et OCRisent)
    python3 grid/run.py                   # la grid, ~2 h sur 13 processus, reprenable
    python3 grid/analyze.py --publier       # lit les thresholds sur les courbes, ecrit LIMITES.md
    python3 grid/corner_followup.py               # le suivi hors protocole d'une cell

Outillage local uniquement. Aucun service distant, aucune depense.

## Le corpus

Trois formulaires VIERGES tels que leur administration les publie: W-9 (IRS) et I-9 (USCIS),
domain public 17 U.S.C. 105, et Cerfa 14011*02 (service-public.fr, Licence Ouverte 2.0
Etalab). Producteur, source, date de recuperation, licence et sha256 dans `corpus/CORPUS.md`,
avec un test qui echoue dans les deux direction.

Jamais un document delivre a quelqu'un. Un document delivre ne se caviarde pas completement:
le code-barres 2D encode l'identity et survit au rectangle noir, la couche de texte reste
intacte dessous, et restent les metadonnees XMP, l'historique d'incremental update et
l'empreinte du scanner. Les dossiers de test sont remplis d'un reference entierement fictif.
