"""Ce qu'on MESURE sur une piece, une fois pour toutes, sans decider quoi que ce soit.

Une Lecture est serialisable et suffit a rejouer tous les controles a n'importe quel seuil.
C'est ce qui rend la grille de degradation abordable: 16 000 passages d'images une seule
fois, puis des milliers de points de fonctionnement balayes sur les mesures enregistrees.
Un capteur qui rendrait deja un booleen aurait enferme son seuil dans son code, et un seuil
enferme ne se lit pas sur une courbe.
"""
import hashlib
import json
import logging
import os
from dataclasses import dataclass, asdict, field

from .capteurs import (PARTS_DISQUE, SEUILS_ENCRE, Mot, composantes, encre_disque,
                       mots_ajoutes, mots_ocr, mots_zone_ocr, taux_encre)
from .degradation import appliquer
from .geometrie import zones_declarees
from .redressement import preparer
from .rendu import CACHE, rendre

logging.getLogger("pypdf").setLevel(logging.ERROR)

MARGE_ZONE = 8       # dilatation des zones avant lecture, en pixels du repere canonique
RAYON_PREIMPRIME = 22


@dataclass
class Lecture:
    piece: str
    gabarit: str
    angle: float
    quart: int
    dpi_source: float
    pic: float
    couverture: float
    marge_orientation: float
    mots: list = field(default_factory=list)        # OCR pleine page: (texte, cx, cy, conf, ajoute)
    zones_ocr: dict = field(default_factory=dict)   # OCR par zone: champ -> memes quintuplets
    cases: dict = field(default_factory=dict)       # champ -> {"part|seuil": delta}
    signatures: dict = field(default_factory=dict)  # champ -> {"seuil": [taux, n, aire, diag]}

    def dict(self):
        return asdict(self)

    @staticmethod
    def depuis(d):
        return Lecture(**d)

    def mots_zone(self, zone, conf_min=0.0, ajoutes_seulement=True, capteur="union"):
        """Les mots lus dans une zone, par l'un des trois capteurs de texte concurrents.

        "union" n'est pas un compromis mou: les deux capteurs echouent sur des champs
        DIFFERENTS (l'OCR pleine page ne voit rien dans NoCarteID du Cerfa, l'OCR de zone rate
        une case du numero fiscal eclate du W-9), donc leur union rate moins que chacun.
        """
        z = zone.dilatee(MARGE_ZONE)
        page = [m for m in self.mots if z.contient(m[1], m[2])]
        zonal = self.zones_ocr.get(zone.nom, [])
        source = {"page": page, "zone": zonal, "union": page + zonal}[capteur]
        # Deduplication a la maille de 16 px: en mode union les deux capteurs lisent le meme
        # mot a deux ou trois pixels pres, et le compter deux fois gonflerait le nombre de
        # caracteres lus, donc ferait passer pour rempli un champ qui ne l'est pas.
        vus, out = set(), []
        for t, cx, cy, c, aj in source:
            cle = (t.lower(), int(cx) // 16, int(cy) // 16)
            if c < conf_min or (ajoutes_seulement and not aj) or cle in vus:
                continue
            vus.add(cle)
            out.append((t, cx, cy, c))
        return out

    def tous_mots(self, conf_min=0.0, ajoutes_seulement=True):
        vus, out = set(), []
        for t, cx, cy, c, aj in list(self.mots) + [m for v in self.zones_ocr.values() for m in v]:
            if c < conf_min or (ajoutes_seulement and not aj) or (t, round(cx), round(cy)) in vus:
                continue
            vus.add((t, round(cx), round(cy)))
            out.append((t, cx, cy, c))
        return out


_MEMO_VIERGE = {}


def vierge(gabarit):
    """Le vierge rendu au repere canonique, avec ses mots pre-imprimes.

    Les mots du vierge vont sur le disque: sans ce cache, chaque processus de la grille
    repaie 2,8 s d'OCR par gabarit au demarrage, et il y a autant de processus que de coeurs.
    """
    cle = (gabarit.pdf, gabarit.page, gabarit.langue)
    if cle in _MEMO_VIERGE:
        return _MEMO_VIERGE[cle]
    img = rendre(gabarit.pdf, page=gabarit.page)
    zones = zones_declarees(gabarit.pdf, gabarit.page)
    os.makedirs(CACHE, exist_ok=True)
    empreinte = hashlib.sha1(f"v2|{cle}|{img.shape}".encode()).hexdigest()[:16]
    fichier = os.path.join(CACHE, f"mots-{empreinte}.json")
    if os.path.exists(fichier):
        d = json.load(open(fichier))
        mots = [Mot(*m) for m in d["page"]]
        par_zone = {k: [Mot(*m) for m in v] for k, v in d["zones"].items()}
    else:
        mots = mots_ocr(img, gabarit.langue)
        par_zone = {c: mots_zone_ocr(img, zones[c], gabarit.langue)
                    for c in gabarit.tous_champs if c in zones}
        tmp = fichier + f".{os.getpid()}"
        json.dump({"page": [[m.texte, m.cx, m.cy, m.conf] for m in mots],
                   "zones": {k: [[m.texte, m.cx, m.cy, m.conf] for m in v]
                             for k, v in par_zone.items()}}, open(tmp, "w"))
        os.replace(tmp, fichier)
    _MEMO_VIERGE[cle] = (img, mots, zones, par_zone)
    return _MEMO_VIERGE[cle]


def lire(piece, deg):
    """Rend, degrade, redresse, recale, mesure. Retour: Lecture.

    Rien ici ne compare a un referentiel et rien ne franchit un seuil: c'est deliberé.
    """
    img_vierge, mots_vierge, zones, _ = vierge(piece.gabarit)
    brut = rendre(piece.pdf, dpi=deg.dpi, page=piece.gabarit.page)
    prep = preparer(appliquer(brut, deg), img_vierge)
    cadre, scan, vierge_cadre = prep.cadre, prep.cadre.scan, prep.cadre.vierge
    ech = cadre.echelle

    # Les mots sont LUS a la resolution native puis leurs centres sont ramenes dans le repere
    # canonique: c'est ce repere qui porte les zones declarees et le format de la Lecture.
    def canon(mots):
        return [Mot(m.texte, *cadre.vers_canonique(m.cx, m.cy), m.conf) for m in mots]

    tous = canon(mots_ocr(scan, piece.gabarit.langue))
    ajoutes = {id(m) for m in mots_ajoutes(tous, mots_vierge, RAYON_PREIMPRIME)}
    # On ne garde que les mots tombant dans une zone DECLAREE, dilatee. Sans ce filtre la
    # grille ecrit 500 Mo de JSONL pour 36 Ko de mots utiles par page, et la contrepartie est
    # ecrite noir sur blanc dans LIMITES.md: une valeur interdite reapparaissant HORS de tout
    # champ declare ne sera pas vue.
    boites = [z.dilatee(MARGE_ZONE) for z in zones.values()]
    lec = Lecture(piece.id, piece.gabarit.nom, round(prep.angle, 3), prep.quart,
                  round(prep.dpi_source, 2), round(prep.pic, 4), round(prep.couverture, 4),
                  round(prep.marge_orientation, 4),
                  mots=[(m.texte, round(m.cx), round(m.cy), round(m.conf), id(m) in ajoutes)
                        for m in tous if any(b.contient(m.cx, m.cy) for b in boites)])

    for champ in piece.gabarit.tous_champs:
        z = zones.get(champ)
        if z is None:
            continue
        lus = canon(mots_zone_ocr(scan, cadre.zone(z), piece.gabarit.langue))
        aj = {id(m) for m in mots_ajoutes(lus, mots_vierge, RAYON_PREIMPRIME)}
        lec.zones_ocr[champ] = [(m.texte, round(m.cx), round(m.cy), round(m.conf), id(m) in aj)
                                for m in lus]

    for champ in piece.gabarit.cases.values():
        z = zones.get(champ)
        if z is None:
            continue
        zs = cadre.zone(z)
        lec.cases[champ] = {
            f"{p}|{s}": round(encre_disque(scan, zs, p, s) - encre_disque(vierge_cadre, zs, p, s), 3)
            for p in PARTS_DISQUE for s in SEUILS_ENCRE}
    for champ in piece.gabarit.signatures.values():
        z = zones.get(champ)
        if z is None:
            continue
        zs = cadre.zone(z)
        lec.signatures[champ] = {}
        for s in SEUILS_ENCRE:
            # Aire et diagonale sont ramenees en pixels CANONIQUES: sinon une signature lue a
            # 96 dpi aurait une diagonale deux fois plus courte que la meme a 200 dpi, et le
            # seuil ne voudrait plus rien dire d'une cellule a l'autre.
            n, aire, diag = composantes(scan, vierge_cadre, zs, s)
            lec.signatures[champ][str(s)] = [
                round(taux_encre(scan, zs, s) - taux_encre(vierge_cadre, zs, s), 3), n,
                round(aire * ech * ech), round(diag * ech, 1)]
    return lec
