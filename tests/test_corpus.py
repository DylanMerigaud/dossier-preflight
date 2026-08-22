"""Tests sur le corpus: verifie que corpus/ et corpus/CORPUS.md restent synchronises.

Trois desynchronisations possibles, un test par cas:
  - un fichier PDF present dans corpus/ sans ligne dans le manifeste
  - une ligne du manifeste sans fichier correspondant dans corpus/
  - un sha256 du manifeste qui ne correspond plus au fichier

    python3 -m pytest tests/ -q
"""
import hashlib
import os

ICI = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ICI)
CORPUS_DIR = os.path.join(ROOT, "corpus")
MANIFESTE = os.path.join(CORPUS_DIR, "CORPUS.md")


def lire_manifeste():
    """Parse le tableau markdown de corpus/CORPUS.md en liste de dicts.

    Split sur '|', ignore la ligne d'entete et la ligne de separation '---'.
    Une assertion garde le manifeste non vide: sur un corpus vide, les trois
    tests qui suivent passeraient sinon trivialement.
    """
    with open(MANIFESTE, encoding="utf-8") as f:
        lignes_brutes = f.readlines()

    entetes = None
    lignes_donnees = []
    for ligne in lignes_brutes:
        ligne = ligne.strip()
        if not ligne.startswith("|"):
            continue
        cellules = [c.strip() for c in ligne.strip("|").split("|")]
        if entetes is None:
            entetes = cellules
            continue
        if all(set(c) <= {"-"} for c in cellules):
            continue  # ligne de separation |---|---|...|
        lignes_donnees.append(dict(zip(entetes, cellules)))

    assert lignes_donnees, "manifeste vide: corpus/CORPUS.md ne declare aucun formulaire"
    return lignes_donnees


def fichiers_pdf_du_corpus():
    return {f for f in os.listdir(CORPUS_DIR) if f.lower().endswith(".pdf")}


def sha256_fichier(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def test_aucun_pdf_du_corpus_nest_absent_du_manifeste():
    fichiers_manifeste = {l["fichier"] for l in lire_manifeste()}
    fichiers_disque = fichiers_pdf_du_corpus()
    orphelins = fichiers_disque - fichiers_manifeste
    assert not orphelins, (
        f"PDF present dans corpus/ sans ligne dans CORPUS.md: {sorted(orphelins)}"
    )


def test_aucune_ligne_du_manifeste_ne_pointe_vers_un_fichier_absent():
    fichiers_disque = fichiers_pdf_du_corpus()
    manquants = [l["fichier"] for l in lire_manifeste() if l["fichier"] not in fichiers_disque]
    assert not manquants, (
        f"ligne(s) du manifeste sans fichier correspondant dans corpus/: {manquants}"
    )


def test_le_sha256_du_manifeste_correspond_au_fichier_reel():
    incoherences = []
    for l in lire_manifeste():
        path = os.path.join(CORPUS_DIR, l["fichier"])
        if not os.path.isfile(path):
            continue  # couvert par le test precedent, pas de double-echec ici
        reel = sha256_fichier(path)
        attendu = l["sha256"]
        if reel != attendu:
            incoherences.append(f"{l['fichier']}: manifeste={attendu} reel={reel}")
    assert not incoherences, "sha256 incoherent(s) avec le manifeste: " + "; ".join(incoherences)
