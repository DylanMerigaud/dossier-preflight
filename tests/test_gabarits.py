"""Un gabarit qui pointe un champ inexistant ne fait pas planter l'outil: il le rend muet.

Le controle boucle sur les zones declarees, ne trouve rien, et ne dit rien. Un champ requis
disparu du gabarit devient donc un champ qu'on ne verifie plus, en silence, ce qui est
exactement la panne qu'un outil de conformite ne peut pas se permettre. D'ou cette gate, qui
ne coute aucun OCR.
"""
import pytest

from preflight.geometrie import zones_declarees
from preflight.referentiel import charger_referentiel

REF = charger_referentiel()
GABARITS = [(nom, g) for nom, g in REF.gabarits.items()]


@pytest.mark.parametrize("nom,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_tous_les_champs_mappes_existent_dans_l_acroform(nom, gab):
    declarees = zones_declarees(gab.pdf, gab.page)
    manquants = [c for c in gab.tous_champs if c not in declarees]
    manquants += [c for c in gab.cases.values() if c not in declarees]
    manquants += [c for c in gab.signatures.values() if c not in declarees]
    assert not manquants, f"{nom}: champs absents du PDF: {manquants}"


@pytest.mark.parametrize("nom,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_une_case_a_cocher_n_est_pas_un_bouton_poussoir(nom, gab):
    """Le Cerfa 14011 porte deux poussoirs Imprimer et Reinitialiser, declares /Btn comme les
    vraies cases. En mapper un comme case obligatoire donnerait un controle qui crie toujours:
    un poussoir ne se coche jamais, par construction."""
    declarees = zones_declarees(gab.pdf, gab.page)
    faux = [c for c in gab.cases.values() if declarees[c].genre != "/Btn"]
    assert not faux, f"{nom}: ces cases ne sont pas des cases a cocher: " + str(
        [(c, declarees[c].genre) for c in faux])


@pytest.mark.parametrize("nom,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_les_roles_requis_sont_tous_mappes(nom, gab):
    inconnus = [r for r in gab.requis if r not in gab.champs]
    inconnus += [r for r in gab.cases_requises if r not in gab.cases]
    inconnus += [r for r in gab.signatures_requises if r not in gab.signatures]
    assert not inconnus, f"{nom}: roles requis sans champ: {inconnus}"


@pytest.mark.parametrize("nom,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_le_referentiel_sait_remplir_chaque_role(nom, gab):
    """Un role que le referentiel ne sait pas remplir produirait une fixture a champ vide,
    donc un defaut qu'on n'a pas voulu injecter et qu'on prendrait pour un faux positif."""
    speciaux = {"date_signature", "date_expiration", "adresse", "ville"}
    for role in gab.champs:
        if role in speciaux or role in gab.dates:
            continue
        REF.valeur(role)


def test_les_coherences_pointent_des_pieces_et_des_champs_reels():
    pieces = dict(REF.pieces)
    for coh in REF.coherences:
        assert len(coh["lectures"]) >= 2, "une coherence a moins de deux lectures ne compare rien"
        for l in coh["lectures"]:
            assert l["piece"] in pieces, f"coherence sur une piece inconnue: {l['piece']}"
            assert l["champ"] in REF.gabarits[pieces[l["piece"]]].champs, (
                f"coherence sur un champ inconnu: {l['piece']}.{l['champ']}")
