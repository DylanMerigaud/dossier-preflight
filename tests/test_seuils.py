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
