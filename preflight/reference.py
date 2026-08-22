"""Le reference FICTIONAL: ce que le dossier est cense dire, et selon quelle clock."""
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
    raise ValueError(f"date illisible: {s!r}")


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
        """La value attendue pour un role, address aplatie comprise."""
        p = self.person
        if role in p:
            return p[role]
        return p["address"][role]

    def clock(self, name):
        return self.clocks[name]


def load_reference(chemin=None, racine=ROOT):
    """`dossier`, `clocks` et `pieces` sont required, le reste ne l'est pas.

    `person` et `expiry` ne servent qu'a REMPLIR des fixtures, jamais a evaluate: aucun
    check ne les lit. Les exiger obligerait quelqu'un qui veut juger ses propres scans a
    inventer une identity pour satisfaire le chargeur, ce qui est exactement l'inverse de ce
    que ce depot promet. `forbidden_values` et `consistencies`, eux, sont lus par les checks
    mais un dossier peut legitimement n'en declarer aucun.
    """
    chemin = chemin or os.path.join(racine, "fixtures", "reference.yaml")
    d = yaml.safe_load(open(chemin, encoding="utf-8"))
    pieces = tuple((p["id"], p["template"]) for p in d["pieces"])
    return Reference(
        dossier=d["dossier"],
        clocks={k: _date(v) for k, v in d["clocks"].items()},
        person=d.get("person") or {},
        forbidden_values=tuple(str(v) for v in (d.get("forbidden_values") or ())),
        expiry={k: _date(v) for k, v in (d.get("expiry") or {}).items()},
        pieces=pieces,
        consistencies=tuple(d.get("consistencies") or ()),
        templates={g: load(g, racine) for _, g in pieces},
    )
