#!/usr/bin/env python3
"""Six FICTIONAL identities, the exact schema of fixtures/reference.yaml, seed 20260925.

Composed from two hand-written lists of uncommon given names and surnames below, invented
street names, and identifiers in ranges the administration never issues: SSN area 666 or 000
(the SSA has never assigned either), card numbers of the reference's own shape but never its
series. No real person, no document ever issued to anybody, exactly like reference.yaml.

    python3 fixtures/make_identities.py            # writes id01.yaml .. id06.yaml
"""
import argparse
import datetime as dt
import os
import random

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "fixtures", "identities")
SEED = 20260925

# Uncommon, clearly invented given names and surnames: nothing here is a public figure or a
# name search engines return as belonging to one real, identifiable person.
GIVEN_NAMES = [
    "AURELIEN", "MARINETTE", "ROSALBA", "THEODULE", "WILFRIDA", "ANSELME",
]
SURNAMES = [
    "BOUCHARENC", "FAVREUIL", "LANGOUET", "MERZOUGUI", "OSTROWSKI", "PELLARIN",
]
STREET_TYPES = ["RUE", "ALLEE", "IMPASSE", "CHEMIN", "SQUARE", "PLACE"]
STREET_NAMES = [
    "DES GRILLONS", "DU MOULIN PERSE", "DES CORMORANS BLEUS", "DE LA FONTAINE ROMPUE",
    "DES TISSERANDS", "DU CLOS BRIQUET",
]
# (city, postal code): small towns, never the reference's own COMMENTRY / 03600.
CITIES = [
    ("VOUZIERS", "08400"), ("ARGENTAT", "19400"), ("BAZAS", "33430"),
    ("CONFOLENS", "16500"), ("DECAZEVILLE", "12300"), ("LOUDEAC", "22600"),
]


def _fmt(d):
    return d.strftime("%d/%m/%Y")


def _ssn(rng, area):
    """AAA-GG-SSSS, the same shape as reference.yaml's tax_id and ssn. area is 666 or 000, an
    SSA area the administration has never issued, per the task's fictional-identity rule."""
    group = rng.randint(1, 99)
    serial = rng.randint(1, 9999)
    return f"{area:03d}-{group:02d}-{serial:04d}"


def _card_number(rng):
    """Two letters, seven digits: the same shape as reference.yaml's AB1234567, never its
    value, and never a real Cerfa series."""
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    digits = "".join(str(rng.randint(0, 9)) for _ in range(7))
    return f"{letters}{digits}"


def build_identity(i, rng):
    """The i-th identity (0-indexed), same top-level keys as reference.yaml plus
    signature_seed, a distinct integer per identity so every dossier gets its own handwriting
    (preflight/fixtures.py's _draw_signature used to hard-code seed 11 for every dossier)."""
    given, surname = GIVEN_NAMES[i], SURNAMES[i]
    street_type = STREET_TYPES[i % len(STREET_TYPES)]
    street_name = STREET_NAMES[i]
    city, postal = CITIES[i]
    area = 666 if i % 2 == 0 else 0
    # Six distinct, plausible-looking birth dates: never the reference's own 14/03/1991.
    birth = dt.date(1968 + i * 3, 1 + (i * 5) % 12, 1 + (i * 7) % 27)
    # The two clocks: kept identical to reference.yaml across every identity, so the two-clock
    # mechanism (filing rejects, admissibility accepts the same piece) means the same thing for
    # all seven files and nothing about it needs re-deriving per identity.
    filing = dt.date(2026, 8, 21)
    admissibility = dt.date(2026, 2, 10)
    # valid_expiry_date / expired_expiry_date still serve the ONE v0.1.0-shaped "expired_date"
    # variant (VARIANTS, unchanged): the exhaustive enumeration's own two expiry instances are
    # computed off the filing clock directly (preflight/fixtures.py), not off these fields.
    valid_expiry = dt.date(2027, 6, 1 + i)
    expired_expiry = dt.date(2026, 5, 1 + i)
    return {
        "dossier": f"DP-2026-{500 + i:04d}",
        "clocks": {"filing": _fmt(filing), "admissibility": _fmt(admissibility)},
        "person": {
            "name": surname,
            "first_name": given,
            "birth_date": _fmt(birth),
            "birth_city": city,
            "tax_id": _ssn(rng, area),
            "ssn": _ssn(rng, area),
            "card_number": _card_number(rng),
            "address": {
                "number": str(10 + i * 7),
                "street_type": street_type,
                "street_name": street_name,
                "postal_code": postal,
                "city": city,
            },
        },
        "forbidden_values": ["999-99-9999", "A COMPLETER"],
        "expiry": {"valid_expiry_date": _fmt(valid_expiry),
                   "expired_expiry_date": _fmt(expired_expiry)},
        "pieces": [
            {"id": "tax", "template": "fw9"},
            {"id": "tax_es", "template": "fw9sp"},
            {"id": "employment", "template": "i9"},
            {"id": "identity", "template": "cerfa14011"},
        ],
        "consistencies": [
            {"data": "street_name",
             "readings": [{"piece": "tax", "field": "address"},
                          {"piece": "identity", "field": "street_name"}]},
        ],
        "signature_seed": 100 + i * 11,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--n", type=int, default=6)
    a = ap.parse_args()
    if a.n > len(GIVEN_NAMES):
        raise SystemExit(f"only {len(GIVEN_NAMES)} given names on file, cannot make {a.n}")
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(SEED)
    header = ("# FICTIONAL IDENTITY, generated by fixtures/make_identities.py, seed "
               f"{SEED}. Invented person, invented address, no document ever issued to "
               "anybody. SSN area 666 or 000, never a real range.\n")
    for i in range(a.n):
        d = build_identity(i, rng)
        path = os.path.join(a.out, f"id{i + 1:02d}.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(header)
            yaml.safe_dump(d, f, sort_keys=False, allow_unicode=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
