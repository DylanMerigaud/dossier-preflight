"""L'arithmetique de l'analyse, testee sur des cas ou la bonne reponse se calcule a la main.

Ces fonctions decident des thresholds publies. Une erreur ici ne fait pas planter un test, elle
publie un chiffre faux avec l'air d'avoir ete mesure, ce qui est pire.
"""
import math

from grid.analyze import (FP_BUDGET, VALIDATION_SEED, curve, measure, chosen_point,
                             split, wilson)


def test_wilson_encadre_la_proportion():
    bas, haut = wilson(3, 3)
    assert bas < 1.0 <= haut, "3 succes sur 3 ne prouvent pas un taux de 1.0"
    assert wilson(0, 3)[1] > 0.0, "0 succes sur 3 ne prouvent pas un taux de 0.0"
    bas1, haut1 = wilson(50, 100)
    bas2, haut2 = wilson(500, 1000)
    assert (haut2 - bas2) < (haut1 - bas1), "l'intervalle doit se resserrer avec n"


def test_la_courbe_va_du_tout_au_rien():
    pts = curve(pos=[3.0, 4.0, 5.0], neg=[0.0, 1.0, 2.0])
    assert pts[0]["rappel"] == 1.0 and pts[0]["fpr"] == 1.0
    assert pts[-1]["rappel"] == 0.0 and pts[-1]["fpr"] == 0.0


def test_une_separation_parfaite_donne_un_point_parfait():
    pts = curve(pos=[10.0, 11.0], neg=[0.0, 1.0])
    parfaits = [p for p in pts if p["rappel"] == 1.0 and p["fpr"] == 0.0]
    assert parfaits, "deux populations disjointes doivent avoir un seuil qui les separe"


def test_le_point_retenu_respecte_le_budget_de_faux_positifs():
    """Un rappel plus haut ne rachete jamais un depassement du budget."""
    pos = [1.0] * 50 + [9.0] * 50
    neg = [0.0] * 90 + [5.0] * 10        # 10% des sains portent un score eleve
    pt = chosen_point(curve(pos, neg), budget=0.05)
    assert pt is not None
    assert pt["fpr"] <= 0.05
    assert pt["rappel"] == 0.5, "le seul rappel tenable ici est celui des 50 scores a 9.0"


def test_un_budget_a_zero_rend_un_rappel_nul_et_pas_none():
    """Il existe toujours un seuil a zero faux positif: celui qui ne fires jamais.

    Ce n'est donc jamais l'absence de point qui signale un check inutilisable, c'est un
    rappel trop bas au point retenu. Confondre les deux ferait croire qu'un check est
    mesure alors qu'il est simplement muet.
    """
    pt = chosen_point(curve(pos=[1.0], neg=[2.0]), budget=0.0)
    assert pt is not None and pt["rappel"] == 0.0 and pt["fpr"] == 0.0


def test_pas_de_mesure_pas_de_point():
    assert chosen_point([]) is None


def test_la_precision_depend_de_la_prevalence():
    pts = curve(pos=[10.0] * 100, neg=[0.0] * 99 + [10.0])
    p = [x for x in pts if x["rappel"] == 1.0][-1]
    assert p["precision_grille"] > p["precision_prevalence"], (
        "a prevalence basse, un meme taux de faux positifs coute plus cher en precision")


def test_la_separation_isole_la_graine_de_validation():
    par_cellule = {(0.0, 200, 95, 0.0, g): (1.0, 0.0) for g in (11, 23, VALIDATION_SEED)}
    cal, val = split(par_cellule)
    assert len(cal) == 2 and len(val) == 1
    assert all(k[4] != VALIDATION_SEED for k in cal)


def test_mesurer_compte_ce_qui_depasse_strictement_le_seuil():
    m = measure({(0.0, 200, 95, 0.0, 11): {"pos": {"a": 5.0}, "neg": {"a": 5.0, "b": 1.0}},
                 (0.0, 200, 95, 0.0, 23): {"pos": {"a": 7.0}, "neg": {"a": 1.0, "b": 1.0}}},
                seuil=5.0)
    assert m["tp"] == 1 and m["fp"] == 0
    assert math.isclose(m["rappel"], 0.5) and m["fpr"] == 0.0


def test_le_taux_par_dossier_est_bien_plus_haut_que_le_taux_par_cible():
    """C'est le piege du chiffre annonce: dix-sept fields a 1% chacun ne font pas 1% de
    dossiers propres. Un dossier crie des qu'UNE de ses cibles crie."""
    cellules = {}
    for i in range(100):
        neg = {f"field{j}": (9.0 if (i % 10 == j) else 0.0) for j in range(10)}
        cellules[(0.0, 200, 95, 0.0, i)] = {"pos": {"champ0": 9.0}, "neg": neg}
    m = measure(cellules, seuil=5.0)
    assert math.isclose(m["fpr"], 0.10), "une target sur dix se fires"
    assert math.isclose(m["fpr_dossier"], 1.0), "mais tous les dossiers portent une alarme"


def test_le_budget_est_declare_et_serre():
    """Si ce budget devient laxiste, la gate perd sa credibilite sans que rien n'echoue."""
    assert 0 < FP_BUDGET <= 0.01
