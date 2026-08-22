"""Un template relie un ROLE metier (name, address, signature) au field que le PDF declare.

C'est la seule couche ou un name de field apparait, et ces noms ne sont pas devines: ils
sortent de l'AcroForm. Aucune coordonnee n'est ecrite a la main nulle part.
"""
import os
from dataclasses import dataclass, field

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Template:
    name: str
    pdf: str
    page: int
    language: str
    fields: dict
    boxes: dict
    signatures: dict
    required: tuple
    required_boxes: tuple
    required_signatures: tuple
    dates: dict = field(default_factory=dict)
    date_format: str = "fr"

    def field(self, role):
        """Toujours un tuple: certains formulaires eclatent une value sur plusieurs boxes."""
        v = self.fields[role]
        return tuple(v) if isinstance(v, list) else (v,)

    @property
    def all_fields(self):
        return tuple(c for role in self.fields for c in self.field(role))


def load(name, racine=ROOT):
    d = yaml.safe_load(open(os.path.join(racine, "templates", f"{name}.yaml"), encoding="utf-8"))
    return Template(name=name, pdf=os.path.join(racine, "corpus", d["pdf"]), page=d.get("page", 1),
                   language=d.get("language", "eng"), fields=d.get("fields") or {},
                   boxes=d.get("boxes") or {}, signatures=d.get("signatures") or {},
                   required=tuple(d.get("required") or ()),
                   required_boxes=tuple(d.get("required_boxes") or ()),
                   required_signatures=tuple(d.get("required_signatures") or ()),
                   dates=d.get("dates") or {}, date_format=d.get("date_format", "fr"))
