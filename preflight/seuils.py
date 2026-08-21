"""Les seuils vivent dans UN seul fichier, et chacun porte son origine.

Un seuil "spike" est une valeur de mise au point, pas une mesure: il a ete choisi a la main
sur un seul exemple. Un seuil "grille" a ete LU sur une courbe precision/rappel, et la ligne
le dit avec le taux de faux positifs qu'il tient. Tant que la colonne origine dit "spike",
l'outil n'est pas mesure, et le README ne doit pas pretendre le contraire.
"""
import json
import os

from .gabarits import RACINE

FICHIER = os.path.join(RACINE, "seuils.json")
_MEMO = {}


def charger_seuils(chemin=FICHIER):
    if chemin not in _MEMO:
        d = json.load(open(chemin, encoding="utf-8"))
        _MEMO[chemin] = {k: v["valeur"] for k, v in d["seuils"].items()}
    return _MEMO[chemin]


def brut(chemin=FICHIER):
    return json.load(open(chemin, encoding="utf-8"))
