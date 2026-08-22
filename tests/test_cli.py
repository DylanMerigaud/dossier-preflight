"""Le point d'entree rend TROIS verdicts, et il ne doit jamais en ecraser deux dans un.

Un defaut de dossier et une page illisible appellent des gestes opposes au filing: refaire
le dossier, ou refaire le scan. Un code de sortie binaire dirait "ton dossier a un defaut" a
quelqu'un dont le dossier est peut-etre parfait et le scan mauvais.

Le test des deux clocks est ici en BOUT DE CHAINE, et pas seulement au niveau des checks:
c'est la seule propriete de ce depot que rien d'autre n'outille, et elle ne sert a rien si la
ligne de commande la perd en route.
"""
import pytest

from preflight.__main__ import main
from preflight.fixtures import build
from preflight.templates import ROOT


@pytest.fixture(scope="module")
def dossiers(reference, tmp_path_factory):
    """Les PDF sur disque, comme un utilisateur les aurait: des fichiers, pas des objets."""
    dest = str(tmp_path_factory.mktemp("cli"))
    return {name: {p.id: p.pdf for p in build(reference, name, dest).pieces}
            for name in ("clean", "expired_date")}


def run(dossiers, variant, clock, pieces=None, extra=()):
    chemins = dossiers[variant]
    args = [f"{ROOT}/fixtures/reference.yaml", "--clock", clock]
    for pid in (pieces or chemins):
        args += ["--piece", f"{pid}={chemins[pid]}"]
    return main(args + list(extra))


def test_une_piece_perimee_au_guichet_est_un_defaut_de_dossier(dossiers, capsys):
    assert run(dossiers, "expired_date", "filing") == 1
    sortie = capsys.readouterr().out
    assert "DEFAUTS DE DOSSIER" in sortie
    assert "expiry" in sortie


def test_la_meme_piece_passe_a_l_autre_horloge(dossiers, capsys):
    """LE test des deux clocks, de bout en bout. Meme dossier, meme instant, meme fichier:
    seule l'clock change, et le verdict bascule. Si ce test tombe en meme temps que le
    precedent, la CLI a perdu l'clock; s'il tombe seul, c'est le check de expiry."""
    assert run(dossiers, "expired_date", "admissibility") == 0
    assert "Aucun check ne se fires" in capsys.readouterr().out


def test_une_page_illisible_n_est_pas_un_defaut_de_dossier(dossiers, capsys):
    """Sortie 2 et pas 1: le dossier est clean, c'est le scan qui ne se lit pas. Et le mot
    "conforme" ne doit jamais apparaitre a la place de "indecidable"."""
    assert run(dossiers, "clean", "filing", pieces=["identity"], extra=["--dpi", "96"]) == 2
    sortie = capsys.readouterr().out
    assert "NE SAIT PAS LIRE" in sortie and "ABSTENTIONS" in sortie
    assert "DEFAUTS DE DOSSIER" not in sortie


def test_une_piece_non_fournie_est_dite_non_jugee(dossiers, capsys):
    """Se taire sur une piece absente serait la declarer conforme."""
    assert run(dossiers, "clean", "filing", pieces=["tax"]) == 0
    sortie = capsys.readouterr().out
    assert "NON FOURNIES" in sortie and "employment" in sortie and "identity" in sortie


# Les cas ci-dessous ne lisent aucun PDF: ils coutent zero seconde d'OCR.

def test_l_horloge_est_obligatoire():
    """Sans elle l'outil prendrait une date implicite et jetterait la propriete en silence.
    Le code est 64 (EX_USAGE) et pas 2, qui veut dire "je ne sais pas read_piece"."""
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--piece", "tax=/dev/null"])
    assert e.value.code == 64


def test_une_horloge_inconnue_nomme_celles_qui_existent():
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "demain",
              "--piece", "tax=/dev/null"])
    assert "filing" in str(e.value.code) and "admissibility" in str(e.value.code)


def test_une_date_iso_tient_lieu_d_horloge(dossiers):
    """Toutes les clocks utiles ne sont pas declarees d'avance."""
    assert run(dossiers, "expired_date", "2026-01-01", pieces=["employment"]) == 0
    assert run(dossiers, "expired_date", "2026-12-31", pieces=["employment"]) == 1


def test_une_piece_non_declaree_est_refusee():
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "filing",
              "--piece", "passeport=/dev/null"])
    assert "non declaree" in str(e.value.code)


def test_sans_piece_il_ne_fabrique_pas_de_fixture():
    """Un point d'entree qui generait son propre dossier aurait l'air de marcher sur un vrai."""
    with pytest.raises(SystemExit) as e:
        main([f"{ROOT}/fixtures/reference.yaml", "--clock", "filing"])
    assert "aucune piece fournie" in str(e.value.code)
