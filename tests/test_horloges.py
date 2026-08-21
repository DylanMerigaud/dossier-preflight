"""Deux horloges. La meme piece peut etre bonne pour un dossier et perimee pour l'autre.

C'est le motif de refus le plus injuste au guichet: la piece etait valable quand le dossier a
ete monte, elle ne l'est plus le jour du depot. Un outil qui n'a qu'une horloge implicite,
celle du jour ou il tourne, ne peut pas poser la question.
"""
from preflight.controles import Reglages, evaluer


def crie_validite(lectures, referentiel, nom, horloge):
    cons = evaluer(lectures[nom], referentiel, horloge, Reglages())
    return any(c.declenche for c in cons if c.controle == "validite")


def test_la_piece_perimee_est_refusee_au_guichet(lectures, referentiel):
    assert crie_validite(lectures, referentiel, "date_perimee", "guichet")


def test_la_meme_piece_passe_a_la_date_de_recevabilite(lectures, referentiel):
    """Meme fichier, meme instant, meme lecture: seule l'horloge change."""
    assert not crie_validite(lectures, referentiel, "date_perimee", "recevabilite")


def test_le_dossier_sain_passe_aux_deux_horloges(lectures, referentiel):
    assert not crie_validite(lectures, referentiel, "sain", "guichet")
    assert not crie_validite(lectures, referentiel, "sain", "recevabilite")


def test_les_deux_horloges_encadrent_bien_la_date_perimee(referentiel):
    """Sans cet encadrement le test precedent passerait pour une mauvaise raison."""
    perimee = referentiel.validite["date_expiration_perimee"]
    assert referentiel.horloge("recevabilite") < perimee < referentiel.horloge("guichet")
