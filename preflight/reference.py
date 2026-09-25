"""The FICTIONAL reference: what the dossier is supposed to say, and against which clock."""
import datetime as dt
import os
from dataclasses import dataclass

import yaml

from .templates import ROOT, load


def _date(s):
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(str(s), f).date()
        except ValueError:
            pass
    raise ValueError(f"unreadable date: {s!r}")


@dataclass(frozen=True)
class Reference:
    dossier: str
    clocks: dict
    person: dict
    forbidden_values: tuple
    expiry: dict
    pieces: tuple
    consistencies: tuple
    templates: dict
    # IDENTITY, not part of v0.1.0's schema: derived from the file name, never declared in the
    # YAML itself, so fixtures/reference.yaml stays byte-identical and its identity is
    # "reference". A file under fixtures/identities/ named id01.yaml carries identity "id01".
    identity: str = "reference"
    # The signature fixture used to draw on a HARD-CODED seed 11 (preflight/fixtures.py), so
    # every dossier carried the same handwriting regardless of who filed it. Optional and
    # defaulted to 11 so fixtures/reference.yaml, which never declares it, keeps the exact
    # signature it always had.
    signature_seed: int = 11

    def value(self, role):
        """The expected value for a role, flattened address included."""
        p = self.person
        if role in p:
            return p[role]
        return p["address"][role]

    def clock(self, name):
        return self.clocks[name]

    @property
    def country(self):
        """The 2-letter code printed next to the city on the W-9's foreign address line.

        Optional, under person.address, defaulting to "FR": fixtures/reference.yaml never
        declares it and keeps reading as "FR", exactly as the hard-coded value it replaces.
        """
        return (self.person.get("address") or {}).get("country", "FR")


def load_reference(path=None, root=ROOT):
    """`dossier`, `clocks` and `pieces` are required, the rest is not.

    `person` and `expiry` only ever serve to FILL fixtures, never to evaluate: no check reads
    them. Requiring them would force anyone who just wants to judge their own scans to invent
    an identity to satisfy the loader, which is the exact opposite of what this repo promises.
    `forbidden_values` and `consistencies` are read by checks, but a dossier can legitimately
    declare none of either.
    """
    path = path or os.path.join(root, "fixtures", "reference.yaml")
    d = yaml.safe_load(open(path, encoding="utf-8"))
    pieces = tuple((p["id"], p["template"]) for p in d["pieces"])
    identity = os.path.splitext(os.path.basename(path))[0]
    return Reference(
        dossier=d["dossier"],
        clocks={k: _date(v) for k, v in d["clocks"].items()},
        person=d.get("person") or {},
        forbidden_values=tuple(str(v) for v in (d.get("forbidden_values") or ())),
        expiry={k: _date(v) for k, v in (d.get("expiry") or {}).items()},
        pieces=pieces,
        consistencies=tuple(d.get("consistencies") or ()),
        templates={t: load(t, root) for _, t in pieces},
        identity=identity,
        signature_seed=int(d.get("signature_seed", 11)),
    )
