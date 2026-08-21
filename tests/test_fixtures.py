"""Chaque variante porte UN defaut: le controle vise doit crier, les autres doivent se taire.

La seconde moitie de cette phrase est celle qui compte. Un controle qui crie sur la variante
du voisin est un faux positif, et un faux positif coute la credibilite de toute la gate: une
regle qui crie au loup fait survoler celles d'a cote.
"""
import pytest

from preflight.controles import CONTROLES, Reglages, evaluer
from preflight.fixtures import VARIANTES

# Sous le plancher de resolution le texte est VRAIMENT illisible: les controles de texte qui
# se declenchent alors ne sont pas des faux positifs, c'est le plancher qui se manifeste. Le
# dire ici, explicitement et pour cette variante seule, vaut mieux que de les ignorer partout.
TOLERE = {"resolution_basse": {"champ_requis", "coherence"}}


def declenches(lectures, referentiel, nom, horloge="guichet"):
    cons = evaluer(lectures[nom], referentiel, horloge, Reglages())
    return {c for c in CONTROLES if any(x.declenche for x in cons if x.controle == c)}


def test_le_dossier_sain_ne_declenche_rien(lectures, referentiel):
    assert declenches(lectures, referentiel, "sain") == set()


@pytest.mark.parametrize("variante", [v for v in VARIANTES if v.controle], ids=lambda v: v.nom)
def test_le_controle_vise_se_declenche(lectures, referentiel, variante):
    assert variante.controle in declenches(lectures, referentiel, variante.nom)


@pytest.mark.parametrize("variante", [v for v in VARIANTES if v.controle], ids=lambda v: v.nom)
def test_les_autres_controles_se_taisent(lectures, referentiel, variante):
    autres = declenches(lectures, referentiel, variante.nom) - {variante.controle}
    assert autres <= TOLERE.get(variante.nom, set()), f"diaphonie: {sorted(autres)}"


def test_chaque_controle_est_couvert_par_une_variante():
    """Un controle sans variante n'a ni vrai positif ni faux negatif mesurable."""
    vises = {v.controle for v in VARIANTES if v.controle}
    assert vises == set(CONTROLES)
