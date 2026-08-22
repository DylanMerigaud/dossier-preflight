"""Chaque variant porte UN defaut: le check vise doit crier, les autres doivent se taire.

La seconde moitie de cette phrase est celle qui compte. Un check qui crie sur la variant
du voisin est un faux positif, et un faux positif coute la credibilite de toute la gate: une
regle qui crie au loup fait survoler celles d'a cote.
"""
import pytest

from preflight.checks import CHECKS, evaluate
from preflight.fixtures import VARIANTS

# Une seule tolerance, et elle est CHIFFREE par la grid, pas supposee.
#
# Elle couvrait autrefois required_field et consistency sur la variant a 72 dpi. Les deux sont
# sorties, chacune pour une raison mesuree:
#   required_field: la grid a retenu le capteur d'ENCRE, qui ne demande pas a read_piece. Diaphonie
#     mesuree sur low_resolution: 0/864 dossiers du domaine.
#   consistency: les checks qui LISENT s'abstiennent desormais sur une piece sous le
#     floor, au lieu de comparer des jetons qu'ils n'ont pas su read_piece. Avant cette regle,
#     456/864. Apres, 0/864.
#
# Reste required_checkbox, 18/864 soit 2,1%. La piece tax de cette variant est rendue a
# 72 dpi: la case c1_1[0] y fait huit pixels de cote, et le disque central qui mesure son
# ink ne tient plus dans le trait. Ce check ne lit pas, donc il ne s'abstient pas, et
# etendre l'abstention a tout check par coordonnees le desactiverait entre 96 et 148 dpi
# ou la grid le mesure pourtant a 1,000 de rappel. La tolerance est donc le bon endroit
# pour porter ce reste, et son chiffre est dans LIMITES.md.
#
# La cell des fixtures est l'une des 270 sur 288 ou ce declenchement ne se produit pas: le
# test passerait meme sans cette ligne, et c'est precisement pourquoi il faut l'ecrire. Un
# test vert par chance de tirage encode une affirmation que la grid contredit ailleurs.
TOLERATED = {"low_resolution": {"required_checkbox"}}


def declenches(readings, reference, name, clock="filing"):
    """Aucun reglage n'est passe: on veut le chemin de PRODUCTION, celui qui lit thresholds.json.

    Un test qui passerait Settings() court-circuiterait les sensors et les thresholds mesures par
    la grid et testerait les valeurs de spike, c'est-a-dire pas le produit.
    """
    cons = evaluate(readings[name], reference, clock)
    return {c for c in CHECKS if any(x.fires for x in cons if x.check == c)}


def test_le_dossier_sain_ne_declenche_rien(readings, reference):
    assert declenches(readings, reference, "clean") == set()


@pytest.mark.parametrize("variant", [v for v in VARIANTS if v.check], ids=lambda v: v.name)
def test_le_controle_vise_se_declenche(readings, reference, variant):
    assert variant.check in declenches(readings, reference, variant.name)


@pytest.mark.parametrize("variant", [v for v in VARIANTS if v.check], ids=lambda v: v.name)
def test_les_autres_controles_se_taisent(readings, reference, variant):
    autres = declenches(readings, reference, variant.name) - {variant.check}
    assert autres <= TOLERATED.get(variant.name, set()), f"crosstalk: {sorted(autres)}"


def test_chaque_controle_est_couvert_par_une_variante():
    """Un check sans variant n'a ni vrai positif ni faux negatif mesurable."""
    vises = {v.check for v in VARIANTS if v.check}
    assert vises == set(CHECKS)
