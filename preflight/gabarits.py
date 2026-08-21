"""Un gabarit relie un ROLE metier (nom, adresse, signature) au champ que le PDF declare.

C'est la seule couche ou un nom de champ apparait, et ces noms ne sont pas devines: ils
sortent de l'AcroForm. Aucune coordonnee n'est ecrite a la main nulle part.
"""
import os
from dataclasses import dataclass, field

import yaml

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Gabarit:
    nom: str
    pdf: str
    page: int
    langue: str
    champs: dict
    cases: dict
    signatures: dict
    requis: tuple
    cases_requises: tuple
    signatures_requises: tuple
    dates: dict = field(default_factory=dict)
    format_date: str = "fr"

    def champ(self, role):
        """Toujours un tuple: certains formulaires eclatent une valeur sur plusieurs cases."""
        v = self.champs[role]
        return tuple(v) if isinstance(v, list) else (v,)

    @property
    def tous_champs(self):
        return tuple(c for role in self.champs for c in self.champ(role))


def charger(nom, racine=RACINE):
    d = yaml.safe_load(open(os.path.join(racine, "gabarits", f"{nom}.yaml"), encoding="utf-8"))
    return Gabarit(nom=nom, pdf=os.path.join(racine, "corpus", d["pdf"]), page=d.get("page", 1),
                   langue=d.get("langue", "eng"), champs=d.get("champs") or {},
                   cases=d.get("cases") or {}, signatures=d.get("signatures") or {},
                   requis=tuple(d.get("requis") or ()),
                   cases_requises=tuple(d.get("cases_requises") or ()),
                   signatures_requises=tuple(d.get("signatures_requises") or ()),
                   dates=d.get("dates") or {}, format_date=d.get("format_date", "fr"))
