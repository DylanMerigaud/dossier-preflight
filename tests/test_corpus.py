"""Corpus gate: corpus/ and corpus/CORPUS.md must stay in sync.

Three possible desynchronisations, one test each:
  - a PDF present in corpus/ with no row in the manifest
  - a manifest row with no matching file in corpus/
  - a manifest sha256 that no longer matches the file

This is what makes redistributing the forms defensible: every file names its producer, its
source, the date it was retrieved and its licence, and the gate fails in BOTH directions so
neither the files nor the manifest can drift alone.

    python3 -m pytest tests/ -q
"""
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS_DIR = os.path.join(ROOT, "corpus")
MANIFEST = os.path.join(CORPUS_DIR, "CORPUS.md")


def read_manifest():
    """Parse the markdown table of corpus/CORPUS.md into a list of dicts.

    Split on '|', skip the header row and the '---' separator row. An assertion keeps the
    manifest non-empty: on an empty corpus the three tests below would otherwise pass
    trivially.
    """
    with open(MANIFEST, encoding="utf-8") as f:
        raw_lines = f.readlines()

    headers = None
    rows = []
    for line in raw_lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if headers is None:
            headers = cells
            continue
        if all(set(c) <= {"-"} for c in cells):
            continue  # separator row |---|---|...|
        rows.append(dict(zip(headers, cells)))

    assert rows, "empty manifest: corpus/CORPUS.md declares no form at all"
    return rows


def corpus_pdfs():
    return {f for f in os.listdir(CORPUS_DIR) if f.lower().endswith(".pdf")}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def test_no_corpus_pdf_is_missing_from_the_manifest():
    listed = {r["file"] for r in read_manifest()}
    on_disk = corpus_pdfs()
    orphans = on_disk - listed
    assert not orphans, f"PDF present in corpus/ with no row in CORPUS.md: {sorted(orphans)}"


def test_no_manifest_row_points_at_a_missing_file():
    on_disk = corpus_pdfs()
    missing = [r["file"] for r in read_manifest() if r["file"] not in on_disk]
    assert not missing, f"manifest row(s) with no matching file in corpus/: {missing}"


def test_the_manifest_sha256_matches_the_real_file():
    mismatches = []
    for r in read_manifest():
        path = os.path.join(CORPUS_DIR, r["file"])
        if not os.path.isfile(path):
            continue  # covered by the previous test, no double failure here
        actual = sha256_of(path)
        expected = r["sha256"]
        if actual != expected:
            mismatches.append(f"{r['file']}: manifest={expected} actual={actual}")
    assert not mismatches, "sha256 mismatch with the manifest: " + "; ".join(mismatches)
