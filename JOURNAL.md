# Journal

## 2026-08-21

### Ce qui est vert

    python3 spike/preuve.py          exit 0, constats inchanges depuis le premier commit
    python3 -m pytest tests/ -q      55 tests
    python3 grille/lancer.py         13 824 lectures, 121 min sur 13 processus
    python3 grille/analyser.py       9 courbes, LIMITES.md, seuils.json

Le corpus est passe de un a trois formulaires vierges (W-9, I-9, Cerfa 14011*02), avec une
gate de manifeste qui echoue dans les deux sens. Un dossier fictif de trois pieces, un dossier
sain et neuf variantes portant chacune UN defaut. Neuf controles, chacun avec un score continu
et un seuil lu sur une courbe.

### Les chiffres de la grille

384 cellules (6 angles x 4 dpi x 4 qualites JPEG x 4 niveaux de bruit) x 3 graines = 1152
dossiers, dont 864 dans le domaine nominal. Seuil choisi sur les graines 11 et 23, chiffre
publie mesure sur la graine 37, jamais regardee avant.

Domaine nominal: **numerisation a 150 dpi ou plus**. Les huit controles autres que les valeurs
interdites tiennent 1,000 de rappel a 0,0000 de faux positifs par cible. Les valeurs
interdites tiennent 0,997 a 0,00058, avec 6 cellules sur 288 sous le plancher de 95%.

Taux que l'utilisateur ressent: **4 dossiers sur 864 entierement sains portent au moins une
alarme, 0,46%**, tous du controle des valeurs interdites.

Diaphonie mesuree sur toute la grille: une seule case non nulle, case_obligatoire a 2,1% sur
la variante a 72 dpi (la case fait huit pixels de cote, le disque central ne tient plus dans
le trait).

### Les seuils retenus, et pourquoi

| controle | seuil | pourquoi celui-la |
|---|---|---|
| champ_requis | -0.345 % d'encre ajoutee | capteur d'encre, gagnant du duel a 0 faux positif contre 0,0003 pour l'OCR |
| case_obligatoire | delta -14.38 | disque a 0,30 du cote, seuil d'encre 128, meilleur des 12 reglages |
| signature | diagonale -342 px | EGALITE non departagee entre encre et composantes, choix non appuye |
| validite | 0 jour | FIGE PAR DEFINITION, voir plus bas |
| coherence | 0.394 | recouvrement de jetons flou, OCR de zone, confiance 0 |
| valeur_interdite | 0.721 de ressemblance | seul controle qui ne tient pas 1,000 |
| resolution | -148.5 dpi | plancher des AUTRES controles moins 1%, pas sa propre courbe |
| page_coupee | 0.088 | couverture de l'encre du vierge |
| page_tournee | 0.359 | marge de correlation entre quarts de tour |

### Ce que la construction a coute, et qui vaut d'etre retenu

**Quatre fois, une mesure a failli mesurer mon propre bug plutot que l'outil.** A chaque fois
le symptome ressemblait a une limite physique, et a chaque fois c'etait un defaut de fabrique:

1. Le remplissage AcroForm sur les formulaires XFA n'imprimait pas trois champs du Cerfa et
   collait les autres a leur bordure. Le texte est desormais pose par un calque vectoriel, a
   la position que le formulaire DECLARE.
2. Les champs PEIGNE (une case par caractere, drapeau declare par le PDF) recevaient la chaine
   en continu par dessus les separateurs. Illisible par construction.
3. Ramener le scan a un repere canonique de 200 dpi le reechantillonnait, et detruisait le
   petit texte encadre a 300 dpi. Le vierge vient au scan maintenant.
4. Le controle des champs requis mesurait la CONFIANCE OCR du meilleur mot. Une bordure lue
   comme trois barres verticales avec 97 de confiance faisait passer un champ VIDE pour
   rempli. Il compte des caracteres alphanumeriques.

**Trois fois, une boucle a fabrique des chiffres flatteurs.** Exclure les cibles genantes AVANT
de choisir le seuil donnait 100% de rappel sur la seule cible survivante. Definir la
certifiabilite au rappel plein laissait un positif aberrant trainer le seuil jusqu'a 0,11 de
ressemblance. L'abstention sous le plancher, branchee pendant la recherche de domaine, faisait
tomber ce domaine de 150 a 96 dpi. La regle qui en sort: une mesure ne peut pas dependre du
comportement qu'elle sert a regler.

**Le seuil de validite a failli etre fitte, et le test des deux horloges l'a attrape.** La
grille l'avait porte a -207,5 jours: la piece saine du referentiel expire en 2027, donc tout
seuil entre -497 et -110 separe parfaitement les donnees, et l'optimiseur a pris le milieu du
palier. L'outil aurait declare une piece perimee sept mois avant qu'elle le soit, avec un
rappel de 1,000 a l'appui. Ce seuil encode le SENS du mot perime: il est fige a zero, et un
test garde l'invariant.

**Le spike avait tranche a n=1 dans le mauvais sens.** Il concluait que l'encre etait le
mauvais capteur pour du texte. Sur la grille, l'encre gagne le duel. Le coupable n'etait pas le
capteur mais son plancher de confiance a 40, qui jetait des champs remplis mais mal lus.

### Ce qui reste

- **Le coin (300 dpi, JPEG 95, bruit 12) des valeurs interdites** est a 0,833 de rappel sur 18
  positifs seulement, borne haute de l'intervalle sous le plancher. Le signe est a l'envers de
  l'intuition: une compression forte efface le grain du capteur, une compression legere le
  garde, et a haute resolution ce grain se fait lire comme de la structure de caractere. La
  suite est plus de graines sur ce coin, pas un seuil qui bouge.
- **Le duel de la signature n'est pas tranche.** Il faudrait une degradation qui separe les
  deux capteurs, par exemple un trait parasite dans la zone.
- **Aucune degradation de la grille n'ajoute d'encre etrangere.** C'est le terrain favorable du
  capteur d'encre, qui gagne pourtant le duel des champs requis. Un tampon, une ombre de
  pliure, un trait qui deborde: a mesurer avant de faire confiance a ce capteur en vrai.
- **Un seul jeu de trois formulaires.** Les chiffres ne se transportent pas tels quels.
- **Les degradations sont synthetiques.** Ni courbure de page, ni ombre de reliure, ni
  poussiere, ni moire de retramage. La grille borne le domaine, elle ne le prouve pas.
