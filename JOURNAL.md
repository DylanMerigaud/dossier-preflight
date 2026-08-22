# Journal

## 2026-08-21

### Ce qui est vert

    python3 spike/proof.py          exit 0, constats inchanges from_dict le premier commit
    python3 -m pytest tests/ -q      55 tests
    python3 grid/run.py         13 824 readings, 121 min sur 13 processus
    python3 grid/analyze.py       9 courbes, LIMITES.md, thresholds.json

Le corpus est passe de un a trois formulaires vierges (W-9, I-9, Cerfa 14011*02), avec une
gate de manifeste qui echoue dans les deux direction. Un dossier fictif de trois pieces, un dossier
clean et neuf variantes portant chacune UN defaut. Neuf checks, chacun avec un score continu
et un threshold lu sur une curve.

### Les chiffres de la grid

384 cellules (6 angles x 4 dpi x 4 qualites JPEG x 4 niveaux de bruit) x 3 graines = 1152
dossiers, dont 864 dans le domain nominal. Seuil choisi sur les graines 11 et 23, chiffre
publie mesure sur la seed 37, jamais regardee avant.

Domaine nominal: **numerisation a 150 dpi ou plus**. Les huit checks autres que les values
interdites tiennent 1,000 de recall a 0,0000 de faux positifs par target. Les values
interdites tiennent 0,997 a 0,00058, avec 6 cellules sur 288 sous le floor de 95%.

Taux que l'utilisateur ressent: **4 dossiers sur 864 entierement sains portent au moins une
alarme, 0,46%**, tous du check des values interdites.

Diaphonie mesuree sur toute la grid: une seule case non nulle, required_checkbox a 2,1% sur
la variant a 72 dpi (la case fait huit pixels de cote, le disque central ne tient plus dans
le trait).

### Les thresholds retenus, et pourquoi

| check | threshold | pourquoi celui-la |
|---|---|---|
| required_field | -0.345 % d'ink ajoutee | capteur d'ink, gagnant du duel a 0 faux positif contre 0,0003 pour l'OCR |
| required_checkbox | delta -14.38 | disque a 0,30 du cote, threshold d'ink 128, meilleur des 12 reglages |
| signature | diagonale -342 px | EGALITE non departagee entre ink et components, choix non appuye |
| expiry | 0 jour | FIGE PAR DEFINITION, voir plus bas |
| consistency | 0.394 | recouvrement de jetons blur, OCR de zone, confiance 0 |
| forbidden_value | 0.721 de ressemblance | seul check qui ne tient pas 1,000 |
| resolution | -148.5 dpi | floor des AUTRES checks moins 1%, pas sa propre curve |
| cropped_page | 0.088 | coverage de l'ink du blank |
| rotated_page | 0.359 | marge de correlation entre quarts de tour |

### Ce que la construction a coute, et qui vaut d'etre retenu

**Quatre fois, une mesure a failli measure mon propre bug plutot que l'outil.** A chaque fois
le symptome ressemblait a une limite physique, et a chaque fois c'etait un defaut de fabrique:

1. Le remplissage AcroForm sur les formulaires XFA n'imprimait pas trois fields du Cerfa et
   collait les autres a leur bordure. Le texte est desormais pose par un calque vectoriel, a
   la position que le formulaire DECLARE.
2. Les fields PEIGNE (une case par caractere, drapeau declare par le PDF) recevaient la chaine
   en continu par dessus les separateurs. Illisible par construction.
3. Ramener le scan a un repere canonique de 200 dpi le reechantillonnait, et detruisait le
   petit texte encadre a 300 dpi. Le blank vient au scan maintenant.
4. Le check des fields required mesurait la CONFIANCE OCR du meilleur mot. Une bordure lue
   comme trois barres verticales avec 97 de confiance faisait passer un field VIDE pour
   rempli. Il compte des caracteres alphanumeriques.

**Trois fois, une boucle a fabrique des chiffres flatteurs.** Exclure les cibles genantes AVANT
de choisir le threshold donnait 100% de recall sur la seule target survivante. Definir la
certifiability au recall plein laissait un positif aberrant trainer le threshold jusqu'a 0,11 de
ressemblance. L'abstention sous le floor, branchee pendant la recherche de domain, faisait
tomber ce domain de 150 a 96 dpi. La regle qui en sort: une mesure ne peut pas dependre du
comportement qu'elle sert a regler.

**Le threshold de expiry a failli etre fitte, et le test des deux clocks l'a attrape.** La
grid l'avait porte a -207,5 jours: la piece saine du reference expire en 2027, donc tout
threshold entre -497 et -110 separe parfaitement les donnees, et l'optimiseur a pris le milieu du
palier. L'outil aurait declare une piece perimee sept mois avant qu'elle le soit, avec un
recall de 1,000 a l'appui. Ce threshold encode le SENS du mot perime: il est fige a zero, et un
test garde l'invariant.

**Le spike avait tranche a n=1 dans le mauvais direction.** Il concluait que l'ink etait le
mauvais capteur pour du texte. Sur la grid, l'ink gagne le duel. Le coupable n'etait pas le
capteur mais son floor de confiance a 40, qui jetait des fields remplis mais mal lus.

### Ce qui reste

- **Le corner des values interdites est tranche, et il est REEL.** 12 graines neuves plus les 3
  d'origin, n=90: 0,889 de recall [0,807, 0,939]. Le point estime remonte de 0,833 (retour a
  la moyenne d'un n=18) mais la borne haute reste sous le floor. Un control a JPEG 30 sur les
  memes graines rend 0,986, donc c'est bien la compression et pas des graines dures. Et la
  shape reelle est une conjonction de QUATRE factors, pas de deux: 300 dpi ET JPEG 95 ET bruit
  12 ET angle superieur ou egal a 0,5 deg, avec une marche nette (30/30 en dessous, 50/60
  au-dessus). Le balayage a deux factors n'en voyait que l'ombre. Reste a faire: tester
  l'hypothese sur l'angle, qui suppose que c'est l'AMPLEUR du reechantillonnage qui compte et
  non sa presence (le deskew applique une rotation bicubique des 0,25 deg, donc
  l'explication paresseuse est deja exclue). Mesure hors protocole, elle ne deplace aucun
  threshold: `python3 grid/corner_followup.py`.
- **Le duel de la signature n'est pas tranche.** Il faudrait une degradation qui separe les
  deux sensors, par exemple un trait parasite dans la zone.
- **Aucune degradation de la grid n'ajoute d'ink etrangere.** C'est le terrain favorable du
  capteur d'ink, qui gagne pourtant le duel des fields required. Un tampon, une ombre de
  pliure, un trait qui deborde: a measure avant de faire confiance a ce capteur en vrai.
- **Un seul jeu de trois formulaires.** Les chiffres ne se transportent pas tels quels.
- **Les degradations sont synthetiques.** Ni courbure de page, ni ombre de reliure, ni
  poussiere, ni moire de retramage. La grid borne le domain, elle ne le prouve pas.
