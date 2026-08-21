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


def _lire(chemin):
    if chemin not in _MEMO:
        _MEMO[chemin] = json.load(open(chemin, encoding="utf-8"))
    return _MEMO[chemin]


def charger_seuils(chemin=FICHIER):
    return {k: v["valeur"] for k, v in _lire(chemin)["seuils"].items()}


def charger_reglages(chemin=FICHIER):
    """Les reglages MESURES, par controle.

    Sans ce chemin de retour, la grille choisirait un capteur et le code continuerait d'en
    utiliser un autre: le duel A/B ne servirait qu'a produire un tableau. Un reglage absent
    laisse la valeur de spike, et l'origine du seuil dit alors qu'il n'est pas mesure.
    """
    return {k: dict(v.get("reglage_mesure") or {})
            for k, v in _lire(chemin)["seuils"].items()}


def brut(chemin=FICHIER):
    return _lire(chemin)
