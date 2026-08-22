"""Les thresholds vivent dans UN seul fichier, et chacun porte son origine.

Un seuil "spike" est une value de mise au point, pas une mesure: il a ete choisi a la main
sur un seul exemple. Un seuil "grid" a ete LU sur une curve precision/rappel, et la ligne
le dit avec le taux de faux positifs qu'il tient. Tant que la colonne origine dit "spike",
l'outil n'est pas mesure, et le README ne doit pas pretendre le contraire.
"""
import json
import os

from .templates import ROOT

FILE = os.path.join(ROOT, "thresholds.json")
_MEMO = {}


def _read(chemin):
    if chemin not in _MEMO:
        _MEMO[chemin] = json.load(open(chemin, encoding="utf-8"))
    return _MEMO[chemin]


def load_thresholds(chemin=FILE):
    return {k: v["value"] for k, v in _read(chemin)["thresholds"].items()}


def load_settings(chemin=FILE):
    """Les reglages MESURES, par check.

    Sans ce chemin de retour, la grid choisirait un capteur et le code continuerait d'en
    utiliser un autre: le duel A/B ne servirait qu'a produire un tableau. Un reglage absent
    laisse la value de spike, et l'origine du seuil dit alors qu'il n'est pas mesure.
    """
    return {k: dict(v.get("reglage_mesure") or {})
            for k, v in _read(chemin)["thresholds"].items()}


def raw(chemin=FILE):
    return _read(chemin)
