"""dossier-preflight: ce dossier va-t-il se faire refuser au filing.

Trois proprietes portent tout le design, et elles viennent du spike:

  1. TOUT check par coordonnees exige un REDRESSEMENT avant. L'ink brute lue dans une
     zone d'un scan tourne a annonce 8 boxes cochees alors que rien n'etait coche.
  2. L'ink est le mauvais capteur pour du TEXTE. Un field vide lit encore +2,44% d'ink
     contre +4,5 pour un field rempli: separable, mais fragile. Les positions de words OCR
     sont nettes (0 mot contre 3).
  3. Le formulaire blank n'est pas une fixture, c'est l'IMAGE DE REFERENCE. Chaque check
     est un differentiel contre lui, les words pre-imprimes lus sur le blank sont soustraits,
     et on n'affirme jamais que sur ce qui a ete AJOUTE.

Le repere canonique est le blank render a CANON_DPI. Un scan y est ramene par recalage
(orientation, scale, translation) avant qu'aucune coordonnee ne soit lue. Aucune coordonnee
n'est mesuree a la main: les AcroForm DECLARENT leurs zones.
"""
CANON_DPI = 200
