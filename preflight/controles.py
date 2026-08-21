"""Les controles: du refus de guichet, pas de l'extraction.

Chacun rend un SCORE CONTINU oriente dans le meme sens (plus haut = plus de raison de
refuser) et le compare a un seuil. Cette orientation unique est ce qui permet de tracer une
courbe precision/rappel par controle et d'y LIRE le point de fonctionnement, au lieu de
choisir un nombre a la main.

LA PERTE EST ASYMETRIQUE, ET ELLE EST DECLAREE ICI:
  un FAUX NEGATIF, c'est le guichet qui refuse le dossier: des mois de delai, une convocation
  a reprendre, parfois une piece a redemander a une administration etrangere.
  un FAUX POSITIF, c'est la gate qui crie sur un dossier sain: on cesse de la croire, et une
  regle qui crie au loup fait survoler toutes celles d'a cote.
Le premier coute plus cher que le second, mais le second detruit l'outil. Le point de
fonctionnement retenu vise donc le rappel le plus haut ATTEIGNABLE a taux de faux positifs
tenu, et ce taux tenu est ecrit dans seuils.json a cote de chaque valeur.
"""
import datetime as dt
import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from .capteurs import normaliser
from .geometrie import zones_declarees

CONTROLES = ("champ_requis", "case_obligatoire", "signature", "validite", "coherence",
             "valeur_interdite", "resolution", "page_coupee", "page_tournee")


@dataclass(frozen=True)
class Reglages:
    """Les parametres de nuisance que la grille balaie, pas des seuils de decision."""
    conf_min: float = 40.0
    part_disque: float = 0.42
    seuil_encre: int = 160
    capteur_signature: str = "composantes"     # "composantes" ou "encre", duel A/B
    capteur_texte: str = "union"               # "page", "zone", "union" ou "encre", duel A/B


@dataclass(frozen=True)
class Constat:
    controle: str
    piece: str
    cible: str
    score: float          # None quand le controle ne peut pas conclure
    declenche: bool
    detail: str = ""


def _alnum(mots):
    """Le nombre de caracteres alphanumeriques AJOUTES lus dans la zone.

    C'est la mesure du controle "champ requis", et elle a remplace "confiance du mot le plus
    sur" apres mesure: sur le Cerfa, l'OCR de zone lit les bordures du champ comme trois
    barres verticales avec une confiance de 97. La confiance disait donc "ce champ est
    rempli" sur un champ VIDE, ce qui est un faux negatif, le cote cher de l'asymetrie. Une
    barre verticale ne porte aucun caractere alphanumerique; un nom en porte treize.
    """
    return sum(len(re.sub(r"[^0-9A-Za-z]", "", m[0])) for m in mots)


def _cle(t):
    return re.sub(r"[^0-9a-z]", "", normaliser(t))


def _jetons(textes):
    return {j for t in textes for j in re.findall(r"[0-9a-z]+", normaliser(t)) if len(j) >= 2}


def _recouvrement(a, b):
    """Est-ce que tout ce que dit la plus petite lecture est aussi dit par la plus grande.

    Deux choix, tous deux payes par la mesure:
      - ressemblance et non egalite. Le Cerfa fait lire "LDES ACACIAS": la bordure gauche du
        champ se colle au mot, et un recouvrement de jetons EXACT tombe alors a 0,50 sur un
        dossier SAIN. "ldes" contre "des" ressemble a 0,86.
      - le PIRE jeton et non la moyenne. Sur l'adresse divergente, la moyenne est tiree vers
        le haut par les jetons qui coincident encore et la separation tombe a 0,07 contre
        0,37. Le pire jeton donne 0,14 contre 0,73: c'est la divergence d'UNE donnee qu'on
        cherche, pas la ressemblance globale de deux pieces.
    """
    if not a or not b:
        return 0.0
    petit, grand = (a, b) if len(a) <= len(b) else (b, a)
    return min(max(_similarite(x, y) for y in grand) for x in petit)


def _similarite(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _meilleur_ngram(mots, cible, n_max=4):
    """La meilleure ressemblance entre une valeur cherchee et une suite de mots lus.

    Le filtre de longueur n'est pas une optimisation gratuite: deux chaines dont les
    longueurs different d'un facteur deux ne peuvent pas se ressembler a plus de 2/3, donc
    les comparer ne peut pas changer le maximum. Il fait tenir le balayage de la grille en
    minutes au lieu d'heures.
    """
    but = _cle(cible)
    if not but or not mots:
        return 0.0
    textes = [m[0] for m in sorted(mots, key=lambda m: (m[2] // 20, m[1]))]
    cles = [_cle(t) for t in textes]
    best = 0.0
    for n in range(1, min(n_max, len(cles)) + 1):
        for i in range(len(cles) - n + 1):
            bout = "".join(cles[i:i + n])
            if not bout or not (0.5 * len(but) <= len(bout) <= 2.0 * len(but)):
                continue
            best = max(best, _similarite(bout, but))
    return best


_MEMO_ZONES = {}


def zones(gab):
    cle = (gab.pdf, gab.page)
    if cle not in _MEMO_ZONES:
        _MEMO_ZONES[cle] = zones_declarees(gab.pdf, gab.page)
    return _MEMO_ZONES[cle]


def _lire_date(lec, gab, champ, reg):
    """La date telle qu'elle est VRAIMENT imprimee, pas celle que le PDF pretend porter."""
    z = zones(gab).get(champ)
    if z is None:
        return None, ""
    mots = lec.mots_zone(z, reg.conf_min, capteur=reg.capteur_texte)
    brut = " ".join(m[0] for m in sorted(mots, key=lambda m: m[1]))
    chiffres = re.sub(r"\D", "", brut)
    if len(chiffres) != 8:
        return None, brut
    forme = "%m%d%Y" if gab.format_date == "us" else "%d%m%Y"
    try:
        return dt.datetime.strptime(chiffres, forme).date(), brut
    except ValueError:
        return None, brut


# Chaque controle ne depend que d'une poignee de reglages. L'analyse s'en sert pour ne
# balayer que ce qui compte: balayer les 288 combinaisons pour les neuf controles couterait
# 288 evaluations completes la ou 12 suffisent au controle des champs requis.
NUISANCES = {
    "champ_requis": ("conf_min", "capteur_texte", "seuil_encre"),
    "case_obligatoire": ("part_disque", "seuil_encre"),
    "signature": ("seuil_encre", "capteur_signature"),
    "validite": ("conf_min", "capteur_texte"),
    "coherence": ("conf_min", "capteur_texte"),
    "valeur_interdite": ("conf_min", "capteur_texte"),
    "resolution": (),
    "page_coupee": (),
    "page_tournee": (),
}


def reglages_mesures():
    """Les reglages que la grille a retenus, un par controle. Fallback: les valeurs de spike."""
    from .seuils import charger_reglages
    base = Reglages()
    return {c: replace(base, **{k: v for k, v in (charger_reglages().get(c) or {}).items()
                                if hasattr(base, k)})
            for c in CONTROLES}


def evaluer(lectures, ref, horloge="guichet", reg=None, seuils=None, controles=None):
    """Tous les constats d'un dossier, a une horloge et un jeu de seuils donnes.

    `controles` restreint le calcul: l'analyse de la grille appelle ce meme code un controle
    a la fois, pour qu'il n'existe jamais deux implementations d'un controle, celle qui
    tourne et celle qui est mesuree.
    """
    from .seuils import charger_seuils
    seuils = seuils or charger_seuils()
    actifs = set(controles) if controles is not None else set(CONTROLES)
    # reg=None veut dire "prends ce que la grille a mesure", et c'est le mode normal. La grille
    # elle-meme passe un reglage explicite, puisque c'est justement ce qu'elle balaie.
    par_controle = {c: reg for c in CONTROLES} if reg is not None else reglages_mesures()
    date_ref = ref.horloge(horloge)
    out = []
    for piece_id, nom_gab in ref.pieces:
        lec = lectures.get(piece_id)
        if lec is None:
            continue
        gab = ref.gabarits[nom_gab]
        Z = zones(gab)

        # C1 champ requis jamais rempli. Capteur: POSITIONS DE MOTS, pas l'encre. Le spike a
        # mesure qu'un champ texte VIDE lit encore +2,44% d'encre contre +4,5 pour un rempli.
        for role in (gab.requis if "champ_requis" in actifs else ()):
            for champ in gab.champ(role):
                z = Z.get(champ)
                if z is None:
                    continue
                r = par_controle["champ_requis"]
                if r.capteur_texte == "encre":
                    # Le capteur que le spike accusait: l'encre ajoutee dans la zone. Il ne
                    # sait pas ce qui est ecrit, seulement qu'il y a quelque chose de plus
                    # sombre qu'avant, et une bordure sale suffit a le faire mentir.
                    d = lec.encre_champs.get(champ, {}).get(str(r.seuil_encre))
                    if d is None:
                        continue
                    score, detail = -float(d), f"encre {d:+.2f}"
                else:
                    mots = lec.mots_zone(z, r.conf_min, capteur=r.capteur_texte)
                    score, detail = -float(_alnum(mots)), " ".join(m[0] for m in mots)[:40]
                out.append(Constat("champ_requis", piece_id, champ, score,
                                   score > seuils["champ_requis"], detail))

        # C2 case obligatoire non cochee. Encre differentielle dans un disque CENTRAL: le
        # trait de la case reste dehors, sinon on mesure le formulaire et pas la coche.
        for role in (gab.cases_requises if "case_obligatoire" in actifs else ()):
            champ = gab.cases[role]
            r = par_controle["case_obligatoire"]
            d = lec.cases.get(champ, {}).get(f"{r.part_disque}|{r.seuil_encre}")
            if d is None:
                continue
            out.append(Constat("case_obligatoire", piece_id, champ, -d,
                               -d > seuils["case_obligatoire"], f"delta {d:+.1f}"))

        # C3 signature absente. Deux capteurs concurrents, le duel est tranche par la grille.
        for role in (gab.signatures_requises if "signature" in actifs else ()):
            champ = gab.signatures[role]
            r = par_controle["signature"]
            v = lec.signatures.get(champ, {}).get(str(r.seuil_encre))
            if v is None:
                continue
            taux, n, aire, diag = v
            score = -diag if r.capteur_signature == "composantes" else -taux
            out.append(Constat("signature", piece_id, champ, score,
                               score > seuils["signature"],
                               f"taux {taux:+.1f} n {n} diag {diag:.0f}"))

        # C4 date perimee AU JOUR DU DEPOT. Deux horloges: la meme piece peut etre bonne pour
        # un dossier et perimee pour l'autre au meme instant, et c'est l'horloge qui tranche,
        # jamais la date du jour implicite.
        for role, genre in (gab.dates.items() if "validite" in actifs else ()):
            if genre != "expiration":
                continue
            for champ in gab.champ(role):
                date, brut = _lire_date(lec, gab, champ, par_controle["validite"])
                if date is None:
                    out.append(Constat("validite", piece_id, champ, None, False,
                                       f"illisible {brut[:24]!r}"))
                    continue
                jours = (date_ref - date).days
                out.append(Constat("validite", piece_id, champ, float(jours),
                                   jours > seuils["validite"],
                                   f"{date} vs {horloge} {date_ref}"))

        # C7 sous le plancher de resolution. Le dpi n'est pas lu dans une metadonnee (un vrai
        # scan n'en a pas): il est ESTIME par l'echelle qui recale la page sur le vierge.
        if "resolution" in actifs:
            out.append(Constat("resolution", piece_id, "", -lec.dpi_source,
                               -lec.dpi_source > seuils["resolution"],
                               f"{lec.dpi_source:.0f} dpi estimes"))
        # C8 page coupee.
        if "page_coupee" in actifs:
            out.append(Constat("page_coupee", piece_id, "", 1.0 - lec.couverture,
                               1.0 - lec.couverture > seuils["page_coupee"],
                               f"couverture {lec.couverture:.3f}"))
        # C9 page tournee. Score continu: de combien le quart retenu bat le quart d'origine.
        if "page_tournee" in actifs:
            out.append(Constat("page_tournee", piece_id, "", lec.marge_orientation,
                               lec.marge_orientation > seuils["page_tournee"],
                               f"quart {lec.quart}"))

        # C6 valeur interdite qui reapparait. Comparaison sur la forme NUE (sans separateurs):
        # un numero interdit reste interdit qu'il soit imprime 999-99-9999 ou 999999999.
        mots_ajoutes = (lec.tous_mots(par_controle["valeur_interdite"].conf_min)
                        if "valeur_interdite" in actifs else [])
        for val in (ref.valeurs_interdites if "valeur_interdite" in actifs else ()):
            s = _meilleur_ngram(mots_ajoutes, val)
            out.append(Constat("valeur_interdite", piece_id, val, s,
                               s > seuils["valeur_interdite"], f"ressemblance {s:.2f}"))

    # C5 meme donnee divergente entre deux pieces. Mesuree par RECOUVREMENT DE JETONS, sans
    # passer par le referentiel: deux pieces peuvent se contredire alors qu'aucune des deux
    # n'est celle qu'on attendait.
    for coh in (ref.coherences if "coherence" in actifs else ()):
        lus = []
        for l in coh["lectures"]:
            lec = lectures.get(l["piece"])
            if lec is None:
                continue
            gab = ref.gabarits[dict(ref.pieces)[l["piece"]]]
            for champ in gab.champ(l["champ"]):
                z = zones(gab).get(champ)
                if z is not None:
                    rc = par_controle["coherence"]
                    lus.append((l["piece"], _jetons(
                        m[0] for m in lec.mots_zone(z, rc.conf_min, capteur=rc.capteur_texte))))
        for i in range(len(lus)):
            for j in range(i + 1, len(lus)):
                (pa, a), (pb, b) = lus[i], lus[j]
                rec = _recouvrement(a, b)
                out.append(Constat("coherence", f"{pa}+{pb}", coh["donnee"], 1.0 - rec,
                                   1.0 - rec > seuils["coherence"],
                                   f"{sorted(a)} vs {sorted(b)}"[:70]))
    return out
