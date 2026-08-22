"""Le point d'entree rend TROIS verdicts, et il ne doit jamais en ecraser deux dans un.

Un defaut de dossier et une page illisible appellent des gestes opposes au guichet: refaire
le dossier, ou refaire le scan. Un code de sortie binaire dirait "ton dossier a un defaut" a
quelqu'un dont le dossier est peut-etre parfait et le scan mauvais.

Le test des deux horloges est ici en BOUT DE CHAINE, et pas seulement au niveau des controles:
c'est la seule propriete de ce depot que rien d'autre n'outille, et elle ne sert a rien si la
ligne de commande la perd en route.
"""
import pytest

from preflight.__main__ import main
from preflight.fixtures import construire
from preflight.gabarits import RACINE


@pytest.fixture(scope="module")
def dossiers(referentiel, tmp_path_factory):
    """Les PDF sur disque, comme un utilisateur les aurait: des fichiers, pas des objets."""
    dest = str(tmp_path_factory.mktemp("cli"))
    return {nom: {p.id: p.pdf for p in construire(referentiel, nom, dest).pieces}
            for nom in ("sain", "date_perimee")}


def lancer(dossiers, variante, horloge, pieces=None, extra=()):
    chemins = dossiers[variante]
    args = [f"{RACINE}/fixtures/referentiel.yaml", "--horloge", horloge]
    for pid in (pieces or chemins):
        args += ["--piece", f"{pid}={chemins[pid]}"]
    return main(args + list(extra))


def test_une_piece_perimee_au_guichet_est_un_defaut_de_dossier(dossiers, capsys):
    assert lancer(dossiers, "date_perimee", "guichet") == 1
    sortie = capsys.readouterr().out
    assert "DEFAUTS DE DOSSIER" in sortie
    assert "validite" in sortie


def test_la_meme_piece_passe_a_l_autre_horloge(dossiers, capsys):
    """LE test des deux horloges, de bout en bout. Meme dossier, meme instant, meme fichier:
    seule l'horloge change, et le verdict bascule. Si ce test tombe en meme temps que le
    precedent, la CLI a perdu l'horloge; s'il tombe seul, c'est le controle de validite."""
    assert lancer(dossiers, "date_perimee", "recevabilite") == 0
    assert "Aucun controle ne se declenche" in capsys.readouterr().out


def test_une_page_illisible_n_est_pas_un_defaut_de_dossier(dossiers, capsys):
    """Sortie 2 et pas 1: le dossier est sain, c'est le scan qui ne se lit pas. Et le mot
    "conforme" ne doit jamais apparaitre a la place de "indecidable"."""
    assert lancer(dossiers, "sain", "guichet", pieces=["identite"], extra=["--dpi", "96"]) == 2
    sortie = capsys.readouterr().out
    assert "NE SAIT PAS LIRE" in sortie and "ABSTENTIONS" in sortie
    assert "DEFAUTS DE DOSSIER" not in sortie


def test_une_piece_non_fournie_est_dite_non_jugee(dossiers, capsys):
    """Se taire sur une piece absente serait la declarer conforme."""
    assert lancer(dossiers, "sain", "guichet", pieces=["fiscal"]) == 0
    sortie = capsys.readouterr().out
    assert "NON FOURNIES" in sortie and "emploi" in sortie and "identite" in sortie


# Les cas ci-dessous ne lisent aucun PDF: ils coutent zero seconde d'OCR.

def test_l_horloge_est_obligatoire():
    """Sans elle l'outil prendrait une date implicite et jetterait la propriete en silence.
    Le code est 64 (EX_USAGE) et pas 2, qui veut dire "je ne sais pas lire"."""
    with pytest.raises(SystemExit) as e:
        main([f"{RACINE}/fixtures/referentiel.yaml", "--piece", "fiscal=/dev/null"])
    assert e.value.code == 64


def test_une_horloge_inconnue_nomme_celles_qui_existent():
    with pytest.raises(SystemExit) as e:
        main([f"{RACINE}/fixtures/referentiel.yaml", "--horloge", "demain",
              "--piece", "fiscal=/dev/null"])
    assert "guichet" in str(e.value.code) and "recevabilite" in str(e.value.code)


def test_une_date_iso_tient_lieu_d_horloge(dossiers):
    """Toutes les horloges utiles ne sont pas declarees d'avance."""
    assert lancer(dossiers, "date_perimee", "2026-01-01", pieces=["emploi"]) == 0
    assert lancer(dossiers, "date_perimee", "2026-12-31", pieces=["emploi"]) == 1


def test_une_piece_non_declaree_est_refusee():
    with pytest.raises(SystemExit) as e:
        main([f"{RACINE}/fixtures/referentiel.yaml", "--horloge", "guichet",
              "--piece", "passeport=/dev/null"])
    assert "non declaree" in str(e.value.code)


def test_sans_piece_il_ne_fabrique_pas_de_fixture():
    """Un point d'entree qui generait son propre dossier aurait l'air de marcher sur un vrai."""
    with pytest.raises(SystemExit) as e:
        main([f"{RACINE}/fixtures/referentiel.yaml", "--horloge", "guichet"])
    assert "aucune piece fournie" in str(e.value.code)
