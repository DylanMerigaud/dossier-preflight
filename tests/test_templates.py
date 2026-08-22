"""Un template qui pointe un field inexistant ne fait pas planter l'outil: il le rend muet.

Le check boucle sur les zones declarees, ne trouve rien, et ne dit rien. Un field required
disparu du template devient donc un field qu'on ne verifie plus, en silence, ce qui est
exactement la panne qu'un outil de conformite ne peut pas se permettre. D'ou cette gate, qui
ne coute aucun OCR.
"""
import pytest

from preflight.geometry import declared_zones
from preflight.reference import load_reference

REF = load_reference()
GABARITS = [(name, g) for name, g in REF.templates.items()]


@pytest.mark.parametrize("name,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_tous_les_champs_mappes_existent_dans_l_acroform(name, gab):
    declarees = declared_zones(gab.pdf, gab.page)
    manquants = [c for c in gab.all_fields if c not in declarees]
    manquants += [c for c in gab.boxes.values() if c not in declarees]
    manquants += [c for c in gab.signatures.values() if c not in declarees]
    assert not manquants, f"{name}: fields absents du PDF: {manquants}"


@pytest.mark.parametrize("name,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_une_case_a_cocher_n_est_pas_un_bouton_poussoir(name, gab):
    """Le Cerfa 14011 porte deux poussoirs Imprimer et Reinitialiser, declares /Btn comme les
    vraies boxes. En mapper un comme case obligatoire donnerait un check qui crie toujours:
    un poussoir ne se coche jamais, par construction."""
    declarees = declared_zones(gab.pdf, gab.page)
    faux = [c for c in gab.boxes.values() if declarees[c].genre != "/Btn"]
    assert not faux, f"{name}: ces boxes ne sont pas des boxes a cocher: " + str(
        [(c, declarees[c].genre) for c in faux])


@pytest.mark.parametrize("name,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_les_roles_requis_sont_tous_mappes(name, gab):
    inconnus = [r for r in gab.required if r not in gab.fields]
    inconnus += [r for r in gab.required_boxes if r not in gab.boxes]
    inconnus += [r for r in gab.required_signatures if r not in gab.signatures]
    assert not inconnus, f"{name}: roles required sans field: {inconnus}"


@pytest.mark.parametrize("name,gab", GABARITS, ids=[n for n, _ in GABARITS])
def test_le_referentiel_sait_remplir_chaque_role(name, gab):
    """Un role que le reference ne sait pas remplir produirait une fixture a field vide,
    donc un defaut qu'on n'a pas voulu injecter et qu'on prendrait pour un faux positif."""
    speciaux = {"signature_date", "expiry_date", "address", "city"}
    for role in gab.fields:
        if role in speciaux or role in gab.dates:
            continue
        REF.value(role)


def test_les_coherences_pointent_des_pieces_et_des_champs_reels():
    pieces = dict(REF.pieces)
    for coh in REF.consistencies:
        assert len(coh["readings"]) >= 2, "une consistency a moins de deux readings ne compare rien"
        for l in coh["readings"]:
            assert l["piece"] in pieces, f"consistency sur une piece inconnue: {l['piece']}"
            assert l["field"] in REF.templates[pieces[l["piece"]]].fields, (
                f"consistency sur un field inconnu: {l['piece']}.{l['field']}")
