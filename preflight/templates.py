"""A template ties a business ROLE (last name, address, signature) to the field the PDF declares.

This is the only layer where a PDF field name appears, and those names are not guessed: they
come out of the AcroForm. No coordinate is written by hand anywhere.
"""
import os
from dataclasses import dataclass, field as dc_field

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
    dates: dict = dc_field(default_factory=dict)
    date_format: str = "fr"

    def field_ids(self, role):
        """Always a tuple: some forms split one value across several boxes.

        Named field_ids and not field on purpose. `dataclasses.field` is imported in this
        module, and a method called `field` would shadow it for anything declared after it in
        the class body. It happens to work today only because `dates` is annotated before the
        method is defined, which is the kind of ordering nobody should have to know about.
        """
        v = self.fields[role]
        return tuple(v) if isinstance(v, list) else (v,)

    @property
    def all_fields(self):
        return tuple(c for role in self.fields for c in self.field_ids(role))


def load(name, root=ROOT):
    d = yaml.safe_load(open(os.path.join(root, "templates", f"{name}.yaml"), encoding="utf-8"))
    return Template(name=name, pdf=os.path.join(root, "corpus", d["pdf"]), page=d.get("page", 1),
                    language=d.get("language", "eng"), fields=d.get("fields") or {},
                    boxes=d.get("boxes") or {}, signatures=d.get("signatures") or {},
                    required=tuple(d.get("required") or ()),
                    required_boxes=tuple(d.get("required_boxes") or ()),
                    required_signatures=tuple(d.get("required_signatures") or ()),
                    dates=d.get("dates") or {}, date_format=d.get("date_format", "fr"))
