"""Un seuil doit dire d'ou il vient. Tant qu'il dit "spike", l'outil n'est pas mesure."""
from preflight.checks import CHECKS
from preflight.thresholds import raw, load_thresholds

ORIGINES = {"spike", "provisoire", "definition", "grid"}


def test_chaque_controle_a_un_seuil():
    assert set(load_thresholds()) == set(CHECKS)


def test_chaque_seuil_declare_son_origine_et_sa_lecture():
    for name, s in raw()["thresholds"].items():
        assert s["origine"] in ORIGINES, f"{name}: origine inconnue {s['origine']!r}"
        assert s["reading"].strip(), f"{name}: seuil sans phrase de reading"


def test_un_seuil_mesure_cite_sa_courbe():
    """Une value qui se dit mesuree doit pointer la mesure, sinon elle se dit mesuree pour rien."""
    for name, s in raw()["thresholds"].items():
        if s["origine"] == "grid":
            assert s.get("curve"), f"{name}: origine grid sans reference de curve"
            assert "faux_positifs" in s, f"{name}: origine grid sans taux de faux positifs tenu"


def test_un_seuil_de_definition_ne_se_fitte_pas():
    """Le piege central de "read_piece le seuil sur la curve", et il a ete paye.

    "Perime" veut dire que la date est passee: ce seuil vaut zero jour, il encode du sens, il
    n'est pas un parametre. Laisse libre, l'optimiseur l'avait porte a -207,5 jours parce que
    la piece saine du reference expire en 2027 et que tout seuil entre -497 et -110 separe
    alors parfaitement les donnees. L'outil aurait declare une piece perimee sept mois avant
    qu'elle le soit, avec un rappel de 1,000 a l'appui. Une curve ne connait que les donnees
    qu'on lui a donnees.
    """
    v = raw()["thresholds"]["expiry"]
    assert v["origine"] == "definition"
    assert v["value"] == 0.0, "un jour de plus ou de moins ici change le sens du mot perime"
    assert v.get("pourquoi_fige"), "un seuil fige sans raison ecrite se fera refitter"
