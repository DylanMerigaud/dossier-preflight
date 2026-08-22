"""A template pointing at a field that does not exist does not crash the tool: it mutes it.

The check loops over the declared zones, finds nothing, and says nothing. A required field that
disappeared from the template therefore becomes a field nobody verifies any more, silently,
which is exactly the failure a compliance tool cannot afford. Hence this gate, which costs no
OCR at all.
"""
import pytest

from preflight.geometry import declared_zones
from preflight.reference import load_reference

REF = load_reference()
TEMPLATES = [(name, t) for name, t in REF.templates.items()]


@pytest.mark.parametrize("name,tpl", TEMPLATES, ids=[n for n, _ in TEMPLATES])
def test_every_mapped_field_exists_in_the_acroform(name, tpl):
    declared = declared_zones(tpl.pdf, tpl.page)
    missing = [c for c in tpl.all_fields if c not in declared]
    missing += [c for c in tpl.boxes.values() if c not in declared]
    missing += [c for c in tpl.signatures.values() if c not in declared]
    assert not missing, f"{name}: fields absent from the PDF: {missing}"


@pytest.mark.parametrize("name,tpl", TEMPLATES, ids=[n for n, _ in TEMPLATES])
def test_a_checkbox_is_not_a_push_button(name, tpl):
    """Cerfa 14011 carries two push buttons, Imprimer and Reinitialiser, declared /Btn just
    like the real boxes. Mapping one as a required checkbox would give a check that always
    fires: a push button is never ticked, by construction."""
    declared = declared_zones(tpl.pdf, tpl.page)
    wrong = [c for c in tpl.boxes.values() if declared[c].kind != "/Btn"]
    assert not wrong, f"{name}: these are not checkboxes: " + str(
        [(c, declared[c].kind) for c in wrong])


@pytest.mark.parametrize("name,tpl", TEMPLATES, ids=[n for n, _ in TEMPLATES])
def test_every_required_role_is_mapped(name, tpl):
    unknown = [r for r in tpl.required if r not in tpl.fields]
    unknown += [r for r in tpl.required_boxes if r not in tpl.boxes]
    unknown += [r for r in tpl.required_signatures if r not in tpl.signatures]
    assert not unknown, f"{name}: required roles with no field: {unknown}"


@pytest.mark.parametrize("name,tpl", TEMPLATES, ids=[n for n, _ in TEMPLATES])
def test_the_reference_can_fill_every_role(name, tpl):
    """A role the reference cannot fill would produce a fixture with an empty field, that is,
    a defect nobody meant to inject and that would be read as a false positive."""
    special = {"signature_date", "expiry_date", "address", "city"}
    for role in tpl.fields:
        if role in special or role in tpl.dates:
            continue
        REF.value(role)


def test_consistencies_point_at_real_pieces_and_fields():
    pieces = dict(REF.pieces)
    for cons in REF.consistencies:
        assert len(cons["readings"]) >= 2, "a consistency with fewer than two sides compares nothing"
        for side in cons["readings"]:
            assert side["piece"] in pieces, f"consistency on an unknown piece: {side['piece']}"
            assert side["field"] in REF.templates[pieces[side["piece"]]].fields, (
                f"consistency on an unknown field: {side['piece']}.{side['field']}")
