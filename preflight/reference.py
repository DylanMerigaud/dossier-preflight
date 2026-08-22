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

    def value(self, role):
        """The expected value for a role, flattened address included."""
        p = self.person
        if role in p:
            return p[role]
        return p["address"][role]

    def clock(self, name):
        return self.clocks[name]


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
    return Reference(
        dossier=d["dossier"],
        clocks={k: _date(v) for k, v in d["clocks"].items()},
        person=d.get("person") or {},
        forbidden_values=tuple(str(v) for v in (d.get("forbidden_values") or ())),
        expiry={k: _date(v) for k, v in (d.get("expiry") or {}).items()},
        pieces=pieces,
        consistencies=tuple(d.get("consistencies") or ()),
        templates={t: load(t, root) for _, t in pieces},
    )
