"""Un template qui pointe un field inexistant ne fait pas planter l'outil: il le rend muet.

Le check boucle sur les zones declared, ne trouve rien, et ne dit rien. Un field required
disparu du template devient donc un field qu'on ne verifie plus, en silence, ce qui est
exactement la panne qu'un outil de conformite ne peut pas se permettre. D'ou cette gate, qui
ne coute aucun OCR.
"""
import pytest

from preflight.geometry import declared_zones
from preflight.reference import load_reference

REF = load_reference()
GABARITS = [(name, g) for name, g in REF.templates.items()]


@pytest.mark.parametrize("name,tpl", GABARITS, ids=[n for n, _ in GABARITS])
def test_tous_les_champs_mappes_existent_dans_l_acroform(name, tpl):
    declared = declared_zones(tpl.pdf, tpl.page)
    manquants = [c for c in tpl.all_fields if c not in declared]
    manquants += [c for c in tpl.boxes.values() if c not in declared]
    manquants += [c for c in tpl.signatures.values() if c not in declared]
    assert not manquants, f"{name}: fields absents du PDF: {manquants}"


@pytest.mark.parametrize("name,tpl", GABARITS, ids=[n for n, _ in GABARITS])
def test_une_case_a_cocher_n_est_pas_un_bouton_poussoir(name, tpl):
    """Le Cerfa 14011 porte deux poussoirs Imprimer et Reinitialiser, declares /Btn comme les
    vraies boxes. En mapper un comme case obligatoire donnerait un check qui crie toujours:
    un poussoir ne se coche jamais, par construction."""
    declared = declared_zones(tpl.pdf, tpl.page)
    wrong = [c for c in tpl.boxes.values() if declared[c].kind != "/Btn"]
    assert not wrong, f"{name}: ces boxes ne sont pas des boxes a cocher: " + str(
        [(c, declared[c].kind) for c in wrong])


@pytest.mark.parametrize("name,tpl", GABARITS, ids=[n for n, _ in GABARITS])
def test_les_roles_requis_sont_tous_mappes(name, tpl):
    inconnus = [r for r in tpl.required if r not in tpl.fields]
    inconnus += [r for r in tpl.required_boxes if r not in tpl.boxes]
    inconnus += [r for r in tpl.required_signatures if r not in tpl.signatures]
    assert not inconnus, f"{name}: roles required sans field: {inconnus}"


@pytest.mark.parametrize("name,tpl", GABARITS, ids=[n for n, _ in GABARITS])
def test_le_referentiel_sait_remplir_chaque_role(name, tpl):
    """Un role que le reference ne sait pas remplir produirait une fixture a field vide,
    donc un defaut qu'on n'a pas voulu injecter et qu'on prendrait pour un wrong positif."""
    speciaux = {"signature_date", "expiry_date", "address", "city"}
    for role in tpl.fields:
        if role in speciaux or role in tpl.dates:
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
