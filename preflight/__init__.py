"""dossier-preflight: ce dossier va-t-il se faire refuser au guichet.

Trois proprietes portent tout le design, et elles viennent du spike:

  1. TOUT controle par coordonnees exige un REDRESSEMENT avant. L'encre brute lue dans une
     zone d'un scan tourne a annonce 8 cases cochees alors que rien n'etait coche.
  2. L'encre est le mauvais capteur pour du TEXTE. Un champ vide lit encore +2,44% d'encre
     contre +4,5 pour un champ rempli: separable, mais fragile. Les positions de mots OCR
     sont nettes (0 mot contre 3).
  3. Le formulaire vierge n'est pas une fixture, c'est l'IMAGE DE REFERENCE. Chaque controle
     est un differentiel contre lui, les mots pre-imprimes lus sur le vierge sont soustraits,
     et on n'affirme jamais que sur ce qui a ete AJOUTE.

Le repere canonique est le vierge rendu a CANON_DPI. Un scan y est ramene par recalage
(orientation, echelle, translation) avant qu'aucune coordonnee ne soit lue. Aucune coordonnee
n'est mesuree a la main: les AcroForm DECLARENT leurs zones.
"""
CANON_DPI = 200
