# dossier-preflight

Ce dossier va-t-il se faire refuser au guichet.

Pas de l'extraction, pas de la generation de document: de la CONFORMITE d'un dossier a un
referentiel externe, mesuree sur ce qui est VRAIMENT IMPRIME. Un champ AcroForm peut porter
une valeur qui ne s'imprime jamais. Le guichet, lui, lit la feuille.

## Ce que ca mesure

Neuf controles, chacun avec un seuil LU sur une courbe precision/rappel, pas choisi a la main.
Grille de 384 cellules (angle x dpi x qualite JPEG x bruit) x 3 graines = 1152 dossiers,
13 824 lectures d'images, 121 minutes sur 13 processus. Le seuil est choisi sur les graines 11
et 23; le chiffre ci-dessous est celui de la graine 37, jamais regardee avant.

| controle | ce qu'il attrape | capteur retenu | seuil | rappel | faux positifs par cible |
|---|---|---|---|---|---|
| champ_requis | un champ requis jamais rempli | encre ajoutee (seuil 128) | -0.345 | 1.000 | 0.00000 |
| case_obligatoire | une case obligatoire non cochee | disque central 0.30 du cote | -14.38 | 1.000 | 0.00000 |
| signature | une signature absente | composantes connexes | -342.1 | 1.000 | 0.00000 |
| validite | une piece perimee A L'HORLOGE CHOISIE | date lue par OCR pleine page | 0 (definition) | 1.000 | 0.00000 |
| coherence | la meme donnee divergente entre deux pieces | OCR de zone, jetons | 0.394 | 1.000 | 0.00000 |
| valeur_interdite | une valeur interdite qui reapparait | OCR pleine page, n-grammes | 0.721 | 0.997 | 0.00058 |
| resolution | un scan sous le plancher de lisibilite | echelle du recalage | -148.5 dpi | 1.000 | 0.00000 |
| page_coupee | une page tronquee | couverture de l'encre du vierge | 0.088 | 1.000 | 0.00000 |
| page_tournee | une page a l'envers | marge de correlation par quart de tour | 0.359 | 1.000 | 0.00000 |

Le chiffre qu'un utilisateur ressent n'est pas celui de la colonne de droite, c'est celui du
dossier entier: **4 dossiers sur 864 entierement sains portent au moins une alarme, soit
0,46%**, et les quatre viennent du controle des valeurs interdites.

Un dossier fautif est refuse au guichet: des mois de delai. Une gate qui crie pour rien perd
sa credibilite, et une regle qui crie au loup fait survoler toutes celles d'a cote. Les deux
couts ne sont pas du meme genre, et le point de fonctionnement est choisi avec cette asymetrie
declaree: rappel le plus haut tenable sous 0,2% de faux positifs par cible.

## Le domaine, et ce qui se passe dehors

**Numerisation a 150 dpi ou plus.** En dessous, le controle des valeurs interdites tombe a
0,042 de rappel et la coherence declenchait sur 84% des dossiers sains avant qu'elle
n'apprenne a se taire.

Sous le plancher, l'outil ne devine pas: le controle de resolution se declenche, et **tout
controle qui LIT s'abstient sur la piece concernee**, avec un verdict "indecidable" qui n'est
pas "conforme". Avant cette regle, la coherence criait sur 456 des 864 dossiers portant une
piece a 72 dpi, en comparant des jetons qu'elle n'avait pas su lire.

Le seuil de resolution est le seul a ne pas sortir de sa propre courbe: sa courbe le poserait
a 111 dpi, l'endroit qui separe le mieux la variante fautive du reste. Mais la question que ce
controle doit poser n'est pas "cette page est-elle a 72 dpi", c'est "cette page est-elle assez
nette pour que les AUTRES tiennent". Il est donc pose au plancher, moins 1% de marge, la marge
valant dix fois l'erreur maximale mesuree de l'estimateur de resolution (0,0133%).

`LIMITES.md` donne le detail par controle: rappel par facteur, pires cellules, pires
croisements de deux facteurs, matrice de diaphonie, et ce que la mesure ne couvre pas.

## Les deux duels entre capteurs

Le spike avait tranche a n=1 que l'encre etait le mauvais capteur pour du texte. **La grille
le contredit.**

Pour "ce champ requis est-il vide", quatre capteurs concurrents:

| capteur | rappel | faux positifs par cible |
|---|---|---|
| encre ajoutee, seuil 128 (retenu) | 1.000 | 0.0000 |
| OCR pleine page + OCR de zone, confiance minimale 0 | 1.000 | 0.0003 |
| OCR seul, confiance minimale 10 et plus | 0.000 | 0.0000 |

Le vrai coupable du spike n'etait pas le capteur, c'etait son plancher de confiance a 40. Un
champ PEIGNE (une case par caractere, le formulaire le declare) se lit "4/1)2" avec une
confiance de 38: les trois chiffres sont la, mais les separateurs cassent le modele de mot de
tesseract. A confiance 40, ce champ REMPLI etait declare vide. A confiance 0, l'OCR revient a
egalite avec l'encre.

L'encre gagne quand meme, et il faut dire pourquoi elle gagne ici: aucune degradation de cette
grille n'AJOUTE d'encre etrangere dans une zone. Un tampon, une ombre de pliure, un trait qui
deborde du champ voisin feraient dire a ce capteur qu'un champ vide est rempli, c'est-a-dire un
faux negatif, le cote cher de l'asymetrie. Elle gagne sur un terrain qui lui est favorable.

Pour "cette signature est-elle absente", encre differentielle contre composantes connexes:
**egalite**. Les six reglages rendent exactement 1,000 de rappel et 0,0000 de faux positifs a
tous les dpi. Ce corpus ne les distingue pas, et le reglage retenu n'est appuye par aucune
mesure. C'est un resultat, pas un vainqueur.

## Comment ca marche

Trois proprietes portent tout le design, et les trois ont ete payees.

**Le formulaire vierge n'est pas une fixture, c'est l'IMAGE DE REFERENCE.** Chaque controle est
un differentiel contre lui, les mots pre-imprimes lus sur le vierge sont soustraits par texte
ET position, et on n'affirme jamais que sur ce qui a ete AJOUTE.

**Les AcroForm DECLARENT leurs zones.** 23 rectangles sur la page 1 du W-9. Aucune coordonnee
n'est mesuree a la main, aucune n'est devinee. Le formulaire declare aussi quels champs sont
des peignes, quel etat vaut "coche", et combien de caracteres il accepte.

**Le vierge vient au scan, pas l'inverse.** Ramener un scan dans un repere canonique a 200 dpi
le reechantillonne des que sa resolution differe, et ca detruit le petit texte encadre: sur le
Cerfa, un scan a 300 dpi rendait 0 caractere lisible dans trois champs qui en rendaient 14, 5
et 10 a 200 dpi ou l'echelle vaut exactement 1. Les trois filtres de reechantillonnage
echouaient pareil, donc ce n'etait pas le filtre. La grille aurait mesure ce reechantillonnage
et conclu, faux, que l'outil casse a 300 dpi. Le scan reste natif; le vierge, rendu propre et
synthetique, vient a lui.

Avant tout controle par coordonnees, la page est redressee (axe d'abord, puis angle fin) et
recalee sur le vierge par correlation croisee, ce qui donne gratuitement l'orientation, la
resolution source estimee et la couverture de page. Sans redressement, l'encre lue dans les
zones d'un scan tourne de 0,45 degre annonce 8 cases cochees sur 8 alors que rien n'est coche.

## Lancer

    python3 spike/preuve.py                    # le premier cas vert, autonome
    python3 -m pytest tests/ -q                # 55 tests
    python3 grille/lancer.py                   # la grille, ~2 h sur 13 processus, reprenable
    python3 grille/analyser.py --publier       # lit les seuils sur les courbes, ecrit LIMITES.md

Outillage local uniquement: tesseract, pdftoppm, pypdf, PIL, numpy, scipy, matplotlib. Aucun
service distant, aucune depense.

## Le corpus

Trois formulaires VIERGES tels que leur administration les publie: W-9 (IRS) et I-9 (USCIS),
domaine public 17 U.S.C. 105, et Cerfa 14011*02 (service-public.fr, Licence Ouverte 2.0
Etalab). Producteur, source, date de recuperation, licence et sha256 dans `corpus/CORPUS.md`,
avec un test qui echoue dans les deux sens.

Jamais un document delivre a quelqu'un. Un document delivre ne se caviarde pas completement:
le code-barres 2D encode l'identite et survit au rectangle noir, la couche de texte reste
intacte dessous, et restent les metadonnees XMP, l'historique d'incremental update et
l'empreinte du scanner. Les dossiers de test sont remplis d'un referentiel entierement fictif.
