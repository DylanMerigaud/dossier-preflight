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
    chemin = chemin or os.path.join(racine, "fixtures", "referentiel.yaml")
    d = yaml.safe_load(open(chemin, encoding="utf-8"))
    pieces = tuple((p["id"], p["gabarit"]) for p in d["pieces"])
    return Referentiel(
        dossier=d["dossier"],
        horloges={k: _date(v) for k, v in d["horloges"].items()},
        personne=d["personne"],
        valeurs_interdites=tuple(str(v) for v in d["valeurs_interdites"]),
        validite={k: _date(v) for k, v in d["validite"].items()},
        pieces=pieces,
        coherences=tuple(d.get("coherences") or ()),
        gabarits={g: charger(g, racine) for _, g in pieces},
    )
