"""Ce qu'on MESURE sur une piece, une fois pour toutes, sans decider quoi que ce soit.

Une Reading est serialisable et suffit a rejouer tous les checks a n'importe quel seuil.
C'est ce qui rend la grid de degradation abordable: 16 000 passages d'images une seule
fois, puis des milliers de points de fonctionnement balayes sur les mesures enregistrees.
Un capteur qui rendrait deja un booleen aurait enferme son seuil dans son code, et un seuil
enferme ne se lit pas sur une curve.
"""
import hashlib
import json
import logging
import os
from dataclasses import dataclass, asdict, field

from .sensors import (DISC_RATIOS, INK_THRESHOLDS, Word, components, disc_ink,
                       added_words, ocr_words, ocr_zone_words, ink_ratio)
from .degradation import apply
from .geometry import declared_zones
from .deskew import prepare
from .render import CACHE, render

logging.getLogger("pypdf").setLevel(logging.ERROR)

ZONE_MARGIN = 8       # dilatation des zones avant reading, en pixels du repere canonique
PREPRINTED_RADIUS = 22


@dataclass
class Reading:
    piece: str
    template: str
    angle: float
    quarter_turns: int
    source_dpi: float
    peak: float
    coverage: float
    orientation_margin: float
    words: list = field(default_factory=list)        # OCR pleine page: (texte, cx, cy, conf, ajoute)
    zone_words_by_field: dict = field(default_factory=dict)   # OCR par zone: field -> memes quintuplets
    boxes: dict = field(default_factory=dict)       # field -> {"part|seuil": delta}
    field_ink: dict = field(default_factory=dict)  # field texte -> {"seuil": delta d'ink
    signatures: dict = field(default_factory=dict)  # field -> {"seuil": [taux, n, aire, diag]}

    def dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return Reading(**d)

    def zone_words(self, zone, min_conf=0.0, ajoutes_seulement=True, capteur="union"):
        """Les words lus dans une zone, par l'un des trois sensors de texte concurrents.

        "union" n'est pas un compromis mou: les deux sensors echouent sur des fields
        DIFFERENTS (l'OCR pleine page ne voit rien dans NoCarteID du Cerfa, l'OCR de zone rate
        une case du number tax eclate du W-9), donc leur union rate moins que chacun.
        """
        z = zone.expanded(ZONE_MARGIN)
        page = [m for m in self.words if z.contains(m[1], m[2])]
        zonal = self.zone_words_by_field.get(zone.name, [])
        source = {"page": page, "zone": zonal, "union": page + zonal}[capteur]
        # Deduplication a la maille de 16 px: en mode union les deux sensors lisent le meme
        # mot a deux ou trois pixels pres, et le compter deux fois gonflerait le nombre de
        # caracteres lus, donc ferait passer pour rempli un field qui ne l'est pas.
        vus, out = set(), []
        for t, cx, cy, c, aj in source:
            key = (t.lower(), int(cx) // 16, int(cy) // 16)
            if c < min_conf or (ajoutes_seulement and not aj) or key in vus:
                continue
            vus.add(key)
            out.append((t, cx, cy, c))
        return out

    def all_words(self, min_conf=0.0, ajoutes_seulement=True):
        vus, out = set(), []
        for t, cx, cy, c, aj in list(self.words) + [m for v in self.zone_words_by_field.values() for m in v]:
            if c < min_conf or (ajoutes_seulement and not aj) or (t, round(cx), round(cy)) in vus:
                continue
            vus.add((t, round(cx), round(cy)))
            out.append((t, cx, cy, c))
        return out


_BLANK_MEMO = {}


def blank(template):
    """Le blank render au repere canonique, avec ses words pre-imprimes.

    Les words du blank vont sur le disque: sans ce cache, chaque processus de la grid
    repaie 2,8 s d'OCR par template au demarrage, et il y a autant de processus que de coeurs.
    """
    key = (template.pdf, template.page, template.language)
    if key in _BLANK_MEMO:
        return _BLANK_MEMO[key]
    img = render(template.pdf, page=template.page)
    zones = declared_zones(template.pdf, template.page)
    os.makedirs(CACHE, exist_ok=True)
    empreinte = hashlib.sha1(f"v2|{key}|{img.shape}".encode()).hexdigest()[:16]
    fichier = os.path.join(CACHE, f"words-{empreinte}.json")
    if os.path.exists(fichier):
        d = json.load(open(fichier))
        words = [Word(*m) for m in d["page"]]
        par_zone = {k: [Word(*m) for m in v] for k, v in d["zones"].items()}
    else:
        words = ocr_words(img, template.language)
        par_zone = {c: ocr_zone_words(img, zones[c], template.language)
                    for c in template.all_fields if c in zones}
        tmp = fichier + f".{os.getpid()}"
        json.dump({"page": [[m.texte, m.cx, m.cy, m.conf] for m in words],
                   "zones": {k: [[m.texte, m.cx, m.cy, m.conf] for m in v]
                             for k, v in par_zone.items()}}, open(tmp, "w"))
        os.replace(tmp, fichier)
    _BLANK_MEMO[key] = (img, words, zones, par_zone)
    return _BLANK_MEMO[key]


def read_piece(piece, deg):
    """Rend, degrade, redresse, recale, mesure. Retour: Reading.

    Rien ici ne compare a un reference et rien ne franchit un seuil: c'est delibere.
    """
    img_vierge, mots_vierge, zones, _ = blank(piece.template)
    raw = render(piece.pdf, dpi=deg.dpi, page=piece.template.page)
    prep = prepare(apply(raw, deg), img_vierge)
    frame, scan, vierge_cadre = prep.frame, prep.frame.scan, prep.frame.blank
    ech = frame.scale

    # Les words sont LUS a la resolution native puis leurs centres sont ramenes dans le repere
    # canonique: c'est ce repere qui porte les zones declarees et le format de la Reading.
    def canon(words):
        return [Word(m.texte, *frame.to_canonical(m.cx, m.cy), m.conf) for m in words]

    tous = canon(ocr_words(scan, piece.template.language))
    ajoutes = {id(m) for m in added_words(tous, mots_vierge, PREPRINTED_RADIUS)}
    # On ne garde que les words tombant dans une zone DECLAREE, expanded. Sans ce filtre la
    # grid ecrit 500 Mo de JSONL pour 36 Ko de words utiles par page, et la contrepartie est
    # ecrite noir sur blanc dans LIMITES.md: une value interdite reapparaissant HORS de tout
    # field declare ne sera pas vue.
    boites = [z.expanded(ZONE_MARGIN) for z in zones.values()]
    lec = Reading(piece.id, piece.template.name, round(prep.angle, 3), prep.quarter_turns,
                  round(prep.source_dpi, 2), round(prep.peak, 4), round(prep.coverage, 4),
                  round(prep.orientation_margin, 4),
                  words=[(m.texte, round(m.cx), round(m.cy), round(m.conf), id(m) in ajoutes)
                        for m in tous if any(b.contains(m.cx, m.cy) for b in boites)])

    for field in piece.template.all_fields:
        z = zones.get(field)
        if z is None:
            continue
        lus = canon(ocr_zone_words(scan, frame.zone(z), piece.template.language))
        aj = {id(m) for m in added_words(lus, mots_vierge, PREPRINTED_RADIUS)}
        lec.zone_words_by_field[field] = [(m.texte, round(m.cx), round(m.cy), round(m.conf), id(m) in aj)
                                for m in lus]
        # L'ENCRE sur un field TEXTE, troisieme concurrent du duel des sensors de texte.
        # Le spike l'avait deja mise en cause a n=1 (un field vide lisait +2,44% contre +4,5 a
        # +5,1 pour un rempli, separable mais fragile); la grid rejoue le duel en grand.
        zs = frame.zone(z)
        lec.field_ink[field] = {
            str(sl): round(ink_ratio(scan, zs, sl) - ink_ratio(vierge_cadre, zs, sl), 3)
            for sl in INK_THRESHOLDS}

    for field in piece.template.boxes.values():
        z = zones.get(field)
        if z is None:
            continue
        zs = frame.zone(z)
        lec.boxes[field] = {
            f"{p}|{s}": round(disc_ink(scan, zs, p, s) - disc_ink(vierge_cadre, zs, p, s), 3)
            for p in DISC_RATIOS for s in INK_THRESHOLDS}
    for field in piece.template.signatures.values():
        z = zones.get(field)
        if z is None:
            continue
        zs = frame.zone(z)
        lec.signatures[field] = {}
        for s in INK_THRESHOLDS:
            # Aire et diagonale sont ramenees en pixels CANONIQUES: sinon une signature lue a
            # 96 dpi aurait une diagonale deux fois plus courte que la meme a 200 dpi, et le
            # seuil ne voudrait plus rien dire d'une cell a l'autre.
            n, aire, diag = components(scan, vierge_cadre, zs, s)
            lec.signatures[field][str(s)] = [
                round(ink_ratio(scan, zs, s) - ink_ratio(vierge_cadre, zs, s), 3), n,
                round(aire * ech * ech), round(diag * ech, 1)]
    return lec
