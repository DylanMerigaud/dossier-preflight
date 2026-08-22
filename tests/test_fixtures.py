"""Chaque variante porte UN defaut: le controle vise doit crier, les autres doivent se taire.

La seconde moitie de cette phrase est celle qui compte. Un controle qui crie sur la variante
du voisin est un faux positif, et un faux positif coute la credibilite de toute la gate: une
regle qui crie au loup fait survoler celles d'a cote.
"""
import pytest

from preflight.controles import CONTROLES, evaluer
from preflight.fixtures import VARIANTES

# Une seule tolerance, et elle est CHIFFREE par la grille, pas supposee.
#
# Elle couvrait autrefois champ_requis et coherence sur la variante a 72 dpi. Les deux sont
# sorties, chacune pour une raison mesuree:
#   champ_requis: la grille a retenu le capteur d'ENCRE, qui ne demande pas a lire. Diaphonie
#     mesuree sur resolution_basse: 0/864 dossiers du domaine.
#   coherence: les controles qui LISENT s'abstiennent desormais sur une piece sous le
#     plancher, au lieu de comparer des jetons qu'ils n'ont pas su lire. Avant cette regle,
#     456/864. Apres, 0/864.
#
# Reste case_obligatoire, 18/864 soit 2,1%. La piece fiscal de cette variante est rendue a
# 72 dpi: la case c1_1[0] y fait huit pixels de cote, et le disque central qui mesure son
# encre ne tient plus dans le trait. Ce controle ne lit pas, donc il ne s'abstient pas, et
# etendre l'abstention a tout controle par coordonnees le desactiverait entre 96 et 148 dpi
# ou la grille le mesure pourtant a 1,000 de rappel. La tolerance est donc le bon endroit
# pour porter ce reste, et son chiffre est dans LIMITES.md.
#
# La cellule des fixtures est l'une des 270 sur 288 ou ce declenchement ne se produit pas: le
# test passerait meme sans cette ligne, et c'est precisement pourquoi il faut l'ecrire. Un
# test vert par chance de tirage encode une affirmation que la grille contredit ailleurs.
TOLERE = {"resolution_basse": {"case_obligatoire"}}


def declenches(lectures, referentiel, nom, horloge="guichet"):
    """Aucun reglage n'est passe: on veut le chemin de PRODUCTION, celui qui lit seuils.json.

    Un test qui passerait Reglages() court-circuiterait les capteurs et les seuils mesures par
    la grille et testerait les valeurs de spike, c'est-a-dire pas le produit.
    """
    cons = evaluer(lectures[nom], referentiel, horloge)
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
