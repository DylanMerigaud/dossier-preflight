"""Le referentiel FICTIF: ce que le dossier est cense dire, et selon quelle horloge."""
import datetime as dt
import os
from dataclasses import dataclass

import yaml

from .gabarits import RACINE, charger


def _date(s):
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(str(s), f).date()
        except ValueError:
            pass
    raise ValueError(f"date illisible: {s!r}")


@dataclass(frozen=True)
class Referentiel:
    dossier: str
    horloges: dict
    personne: dict
    valeurs_interdites: tuple
    validite: dict
    pieces: tuple
    coherences: tuple
    gabarits: dict

    def valeur(self, role):
        """La valeur attendue pour un role, adresse aplatie comprise."""
        p = self.personne
        if role in p:
            return p[role]
        return p["adresse"][role]

    def horloge(self, nom):
        return self.horloges[nom]


def charger_referentiel(chemin=None, racine=RACINE):
    """`dossier`, `horloges` et `pieces` sont requis, le reste ne l'est pas.

    `personne` et `validite` ne servent qu'a REMPLIR des fixtures, jamais a evaluer: aucun
    controle ne les lit. Les exiger obligerait quelqu'un qui veut juger ses propres scans a
    inventer une identite pour satisfaire le chargeur, ce qui est exactement l'inverse de ce
    que ce depot promet. `valeurs_interdites` et `coherences`, eux, sont lus par les controles
    mais un dossier peut legitimement n'en declarer aucun.
    """
    chemin = chemin or os.path.join(racine, "fixtures", "referentiel.yaml")
    d = yaml.safe_load(open(chemin, encoding="utf-8"))
    pieces = tuple((p["id"], p["gabarit"]) for p in d["pieces"])
    return Referentiel(
        dossier=d["dossier"],
        horloges={k: _date(v) for k, v in d["horloges"].items()},
        personne=d.get("personne") or {},
        valeurs_interdites=tuple(str(v) for v in (d.get("valeurs_interdites") or ())),
        validite={k: _date(v) for k, v in (d.get("validite") or {}).items()},
        pieces=pieces,
        coherences=tuple(d.get("coherences") or ()),
        gabarits={g: charger(g, racine) for _, g in pieces},
    )
