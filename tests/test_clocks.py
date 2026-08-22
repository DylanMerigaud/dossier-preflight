"""Deux clocks. La meme piece peut etre bonne pour un dossier et perimee pour l'autre.

C'est le motif de refus le plus injuste au filing: la piece etait valable quand le dossier a
ete monte, elle ne l'est plus le jour du depot. Un outil qui n'a qu'une clock implicite,
celle du jour ou il tourne, ne peut pas poser la question.
"""
from preflight.checks import evaluate


def crie_validite(readings, reference, name, clock):
    cons = evaluate(readings[name], reference, clock)
    return any(c.fires for c in cons if c.check == "expiry")


def test_la_piece_perimee_est_refusee_au_guichet(readings, reference):
    assert crie_validite(readings, reference, "expired_date", "filing")


def test_la_meme_piece_passe_a_la_date_de_recevabilite(readings, reference):
    """Meme fichier, meme instant, meme reading: seule l'clock change."""
    assert not crie_validite(readings, reference, "expired_date", "admissibility")


def test_le_dossier_sain_passe_aux_deux_horloges(readings, reference):
    assert not crie_validite(readings, reference, "clean", "filing")
    assert not crie_validite(readings, reference, "clean", "admissibility")


def test_les_deux_horloges_encadrent_bien_la_date_perimee(reference):
    """Sans cet encadrement le test precedent passerait pour une mauvaise raison."""
    perimee = reference.expiry["expired_expiry_date"]
    assert reference.clock("admissibility") < perimee < reference.clock("filing")
