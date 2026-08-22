"""Un threshold doit dire d'ou il vient. Tant qu'il dit "spike", l'outil n'est pas mesure."""
from preflight.checks import CHECKS
from preflight.thresholds import raw, load_thresholds

ORIGINES = {"spike", "provisoire", "definition", "grid"}


def test_chaque_controle_a_un_seuil():
    assert set(load_thresholds()) == set(CHECKS)


def test_chaque_seuil_declare_son_origine_et_sa_lecture():
    for name, s in raw()["thresholds"].items():
        assert s["origin"] in ORIGINES, f"{name}: origin inconnue {s['origin']!r}"
        assert s["reading"].strip(), f"{name}: threshold sans phrase de reading"


def test_un_seuil_mesure_cite_sa_courbe():
    """Une value qui se dit mesuree doit pointer la mesure, sinon elle se dit mesuree pour rien."""
    for name, s in raw()["thresholds"].items():
        if s["origin"] == "grid":
            assert s.get("curve"), f"{name}: origin grid sans reference de curve"
            assert "false_positives" in s, f"{name}: origin grid sans rate de wrong positifs tenu"


def test_un_seuil_de_definition_ne_se_fitte_pas():
    """Le piege central de "read_piece le threshold sur la curve", et il a ete paye.

    "Perime" veut dire que la date est passee: ce threshold vaut zero jour, il encode du direction, il
    n'est pas un parametre. Laisse libre, l'optimiseur l'avait porte a -207,5 jours parce que
    la piece saine du reference expire en 2027 et que tout threshold entre -497 et -110 separe
    alors parfaitement les donnees. L'outil aurait declare une piece perimee sept mois avant
    qu'elle le soit, avec un recall de 1,000 a l'appui. Une curve ne connait que les donnees
    qu'on lui a donnees.
    """
    v = raw()["thresholds"]["expiry"]
    assert v["origin"] == "definition"
    assert v["value"] == 0.0, "un jour de plus ou de moins ici change le direction du mot perime"
    assert v.get("why_frozen"), "un threshold fige sans raison ecrite se fera refitter"
