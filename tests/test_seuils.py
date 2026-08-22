"""Un seuil doit dire d'ou il vient. Tant qu'il dit "spike", l'outil n'est pas mesure."""
from preflight.controles import CONTROLES
from preflight.seuils import brut, charger_seuils

ORIGINES = {"spike", "provisoire", "definition", "grille"}


def test_chaque_controle_a_un_seuil():
    assert set(charger_seuils()) == set(CONTROLES)


def test_chaque_seuil_declare_son_origine_et_sa_lecture():
    for nom, s in brut()["seuils"].items():
        assert s["origine"] in ORIGINES, f"{nom}: origine inconnue {s['origine']!r}"
        assert s["lecture"].strip(), f"{nom}: seuil sans phrase de lecture"


def test_un_seuil_mesure_cite_sa_courbe():
    """Une valeur qui se dit mesuree doit pointer la mesure, sinon elle se dit mesuree pour rien."""
    for nom, s in brut()["seuils"].items():
        if s["origine"] == "grille":
            assert s.get("courbe"), f"{nom}: origine grille sans reference de courbe"
            assert "faux_positifs" in s, f"{nom}: origine grille sans taux de faux positifs tenu"


def test_un_seuil_de_definition_ne_se_fitte_pas():
    """Le piege central de "lire le seuil sur la courbe", et il a ete paye.

    "Perime" veut dire que la date est passee: ce seuil vaut zero jour, il encode du sens, il
    n'est pas un parametre. Laisse libre, l'optimiseur l'avait porte a -207,5 jours parce que
    la piece saine du referentiel expire en 2027 et que tout seuil entre -497 et -110 separe
    alors parfaitement les donnees. L'outil aurait declare une piece perimee sept mois avant
    qu'elle le soit, avec un rappel de 1,000 a l'appui. Une courbe ne connait que les donnees
    qu'on lui a donnees.
    """
    v = brut()["seuils"]["validite"]
    assert v["origine"] == "definition"
    assert v["valeur"] == 0.0, "un jour de plus ou de moins ici change le sens du mot perime"
    assert v.get("pourquoi_fige"), "un seuil fige sans raison ecrite se fera refitter"
