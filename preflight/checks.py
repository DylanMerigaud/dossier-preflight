"""Les checks: du refus de filing, pas de l'extraction.

Chacun rend un SCORE CONTINU oriente dans le meme sens (plus haut = plus de raison de
refuser) et le compare a un seuil. Cette orientation unique est ce qui permet de plot une
curve precision/rappel par check et d'y LIRE le point de fonctionnement, au lieu de
choisir un nombre a la main.

LA PERTE EST ASYMETRIQUE, ET ELLE EST DECLAREE ICI:
  un FAUX NEGATIF, c'est le filing qui refuse le dossier: des mois de delai, une convocation
  a reprendre, parfois une piece a redemander a une administration etrangere.
  un FAUX POSITIF, c'est la gate qui crie sur un dossier clean: on cesse de la croire, et une
  regle qui crie au loup fait survoler toutes celles d'a cote.
Le premier coute plus cher que le second, mais le second detruit l'outil. Le point de
fonctionnement retenu vise donc le rappel le plus haut ATTEIGNABLE a taux de faux positifs
tenu, et ce taux tenu est ecrit dans thresholds.json a cote de chaque value.
"""
import datetime as dt
import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

from .sensors import normalize
from .geometry import declared_zones

CHECKS = ("required_field", "required_checkbox", "signature", "expiry", "consistency",
             "forbidden_value", "resolution", "cropped_page", "rotated_page")


@dataclass(frozen=True)
class Settings:
    """Les parametres de nuisance que la grid balaie, pas des thresholds de decision."""
    min_conf: float = 40.0
    disc_ratio: float = 0.42
    ink_threshold: int = 160
    signature_sensor: str = "components"     # "components" ou "ink", duel A/B
    text_sensor: str = "union"               # "page", "zone", "union" ou "ink", duel A/B


@dataclass(frozen=True)
class Finding:
    check: str
    piece: str
    target: str
    score: float          # None quand le check ne peut pas conclure
    fires: bool
    detail: str = ""


def _alnum(words):
    """Le nombre de caracteres alphanumeriques AJOUTES lus dans la zone.

    C'est la mesure du check "field required", et elle a remplace "confiance du mot le plus
    sur" apres mesure: sur le Cerfa, l'OCR de zone lit les bordures du field comme trois
    barres verticales avec une confiance de 97. La confiance disait donc "ce field est
    rempli" sur un field VIDE, ce qui est un faux negatif, le cote cher de l'asymetrie. Une
    barre verticale ne porte aucun caractere alphanumerique; un name en porte treize.
    """
    return sum(len(re.sub(r"[^0-9A-Za-z]", "", m[0])) for m in words)


def _key(t):
    return re.sub(r"[^0-9a-z]", "", normalize(t))


def _tokens(textes):
    return {j for t in textes for j in re.findall(r"[0-9a-z]+", normalize(t)) if len(j) >= 2}


def _overlap(a, b):
    """Est-ce que tout ce que dit la plus petite reading est aussi dit par la plus grande.

    Deux choix, tous deux payes par la mesure:
      - ressemblance et non egalite. Le Cerfa fait read_piece "LDES ACACIAS": la bordure gauche du
        field se colle au mot, et un recouvrement de jetons EXACT tombe alors a 0,50 sur un
        dossier SAIN. "ldes" contre "des" ressemble a 0,86.
      - le PIRE jeton et non la moyenne. Sur l'address divergente, la moyenne est tiree vers
        le haut par les jetons qui coincident encore et la separation tombe a 0,07 contre
        0,37. Le pire jeton donne 0,14 contre 0,73: c'est la divergence d'UNE data qu'on
        cherche, pas la ressemblance globale de deux pieces.
    """
    if not a or not b:
        return 0.0
    petit, grand = (a, b) if len(a) <= len(b) else (b, a)
    return min(max(_similarity(x, y) for y in grand) for x in petit)


def _similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _best_ngram(words, target, n_max=4):
    """La meilleure ressemblance entre une value cherchee et une suite de words lus.

    Le filtre de longueur n'est pas une optimisation gratuite: deux chaines dont les
    longueurs different d'un facteur deux ne peuvent pas se ressembler a plus de 2/3, donc
    les comparer ne peut pas changer le maximum. Il fait tenir le balayage de la grid en
    minutes au lieu d'heures.
    """
    but = _key(target)
    if not but or not words:
        return 0.0
    textes = [m[0] for m in sorted(words, key=lambda m: (m[2] // 20, m[1]))]
    cles = [_key(t) for t in textes]
    best = 0.0
    for n in range(1, min(n_max, len(cles)) + 1):
        for i in range(len(cles) - n + 1):
            bout = "".join(cles[i:i + n])
            if not bout or not (0.5 * len(but) <= len(bout) <= 2.0 * len(but)):
                continue
            best = max(best, _similarity(bout, but))
    return best


_ZONE_MEMO = {}


def zones(gab):
    key = (gab.pdf, gab.page)
    if key not in _ZONE_MEMO:
        _ZONE_MEMO[key] = declared_zones(gab.pdf, gab.page)
    return _ZONE_MEMO[key]


def _read_date(lec, gab, field, reg):
    """La date telle qu'elle est VRAIMENT imprimee, pas celle que le PDF pretend porter."""
    z = zones(gab).get(field)
    if z is None:
        return None, ""
    words = lec.zone_words(z, reg.min_conf, capteur=reg.text_sensor)
    raw = " ".join(m[0] for m in sorted(words, key=lambda m: m[1]))
    chiffres = re.sub(r"\D", "", raw)
    if len(chiffres) != 8:
        return None, raw
    shape = "%m%d%Y" if gab.date_format == "us" else "%d%m%Y"
    try:
        return dt.datetime.strptime(chiffres, shape).date(), raw
    except ValueError:
        return None, raw


# Chaque check ne depend que d'une poignee de reglages. L'analyse s'en sert pour ne
# sweep que ce qui compte: sweep les 288 combinations pour les neuf checks couterait
# 288 evaluations completes la ou 12 suffisent au check des fields required.
NUISANCES = {
    "required_field": ("min_conf", "text_sensor", "ink_threshold"),
    "required_checkbox": ("disc_ratio", "ink_threshold"),
    "signature": ("ink_threshold", "signature_sensor"),
    "expiry": ("min_conf", "text_sensor"),
    "consistency": ("min_conf", "text_sensor"),
    "forbidden_value": ("min_conf", "text_sensor"),
    "resolution": (),
    "cropped_page": (),
    "rotated_page": (),
}


def measured_settings():
    """Les reglages que la grid a retenus, un par check. Fallback: les valeurs de spike."""
    from .thresholds import load_settings
    base = Settings()
    return {c: replace(base, **{k: v for k, v in (load_settings().get(c) or {}).items()
                                if hasattr(base, k)})
            for c in CHECKS}


def evaluate(readings, ref, clock="filing", reg=None, thresholds=None, checks=None,
            abstention=True):
    """Tous les constats d'un dossier, a une clock et un jeu de thresholds donnes.

    `checks` restreint le calcul: l'analyse de la grid appelle ce meme code un check
    a la fois, pour qu'il n'existe jamais deux implementations d'un check, celle qui
    tourne et celle qui est mesuree.

    `abstention=False` DEBRANCHE le refus de juger une piece sous le floor, et la grid
    s'en sert pour choisir ce floor justement. Sans ce debranchement il y a une boucle:
    l'abstention lit le seuil de resolution, la recherche de domaine mesure des checks qui
    s'abstiennent donc ne manquent plus rien, le domaine s'elargit jusqu'au dpi le plus bas,
    et le seuil de resolution le suit. Mesure au 2026-08-21: le domaine tombait de 150 a 96
    dpi d'une publication a l'autre, et serait remonte a la suivante. Une mesure ne peut pas
    dependre du comportement qu'elle sert a regler.
    """
    from .thresholds import load_thresholds
    thresholds = thresholds or load_thresholds()
    actifs = set(checks) if checks is not None else set(CHECKS)
    # reg=None veut dire "prends ce que la grid a mesure", et c'est le mode normal. La grid
    # elle-meme passe un reglage explicite, puisque c'est justement ce qu'elle balaie.
    par_controle = {c: reg for c in CHECKS} if reg is not None else measured_settings()
    floor = -thresholds["resolution"]
    date_ref = ref.clock(clock)
    out = []
    for piece_id, nom_gab in ref.pieces:
        lec = readings.get(piece_id)
        if lec is None:
            continue
        gab = ref.templates[nom_gab]
        Z = zones(gab)
        # UNE PIECE SOUS LE PLANCHER NE SE JUGE PAS, ELLE SE SIGNALE. Les checks qui
        # LISENT s'abstiennent, avec un score None qui vaut "indecidable" et non "conforme".
        # Mesure du 2026-08-21 sans cette regle: la consistency se declenchait sur 52,8% des
        # dossiers portant une piece a 72 dpi, en comparant des jetons qu'elle n'avait pas su
        # read_piece. Ce n'etait pas une erreur de seuil, c'etait une reponse a une question qu'il
        # ne fallait pas poser. Le check de resolution, lui, crie: c'est son task.
        illisible = abstention and lec.source_dpi < floor

        # C1 field required jamais rempli. Capteur: POSITIONS DE MOTS, pas l'ink. Le spike a
        # mesure qu'un field texte VIDE lit encore +2,44% d'ink contre +4,5 pour un rempli.
        lit_le_texte = par_controle["required_field"].text_sensor != "ink"
        for role in (gab.required if "required_field" in actifs else ()):
            for field in gab.field(role):
                z = Z.get(field)
                if z is None:
                    continue
                if illisible and lit_le_texte:
                    out.append(Finding("required_field", piece_id, field, None, False,
                                       "piece sous le floor de resolution"))
                    continue
                r = par_controle["required_field"]
                if r.text_sensor == "ink":
                    # Le capteur que le spike accusait: l'ink ajoutee dans la zone. Il ne
                    # sait pas ce qui est ecrit, seulement qu'il y a quelque chose de plus
                    # sombre qu'avant, et une bordure sale suffit a le faire mentir.
                    d = lec.field_ink.get(field, {}).get(str(r.ink_threshold))
                    if d is None:
                        continue
                    score, detail = -float(d), f"ink {d:+.2f}"
                else:
                    words = lec.zone_words(z, r.min_conf, capteur=r.text_sensor)
                    score, detail = -float(_alnum(words)), " ".join(m[0] for m in words)[:40]
                out.append(Finding("required_field", piece_id, field, score,
                                   score > thresholds["required_field"], detail))

        # C2 case obligatoire non cochee. Encre differentielle dans un disque CENTRAL: le
        # trait de la case reste dehors, sinon on mesure le formulaire et pas la coche.
        for role in (gab.required_boxes if "required_checkbox" in actifs else ()):
            field = gab.boxes[role]
            r = par_controle["required_checkbox"]
            d = lec.boxes.get(field, {}).get(f"{r.disc_ratio}|{r.ink_threshold}")
            if d is None:
                continue
            out.append(Finding("required_checkbox", piece_id, field, -d,
                               -d > thresholds["required_checkbox"], f"delta {d:+.1f}"))

        # C3 signature absente. Deux sensors concurrents, le duel est tranche par la grid.
        for role in (gab.required_signatures if "signature" in actifs else ()):
            field = gab.signatures[role]
            r = par_controle["signature"]
            v = lec.signatures.get(field, {}).get(str(r.ink_threshold))
            if v is None:
                continue
            taux, n, aire, diag = v
            score = -diag if r.signature_sensor == "components" else -taux
            out.append(Finding("signature", piece_id, field, score,
                               score > thresholds["signature"],
                               f"taux {taux:+.1f} n {n} diag {diag:.0f}"))

        # C4 date perimee AU JOUR DU DEPOT. Deux clocks: la meme piece peut etre bonne pour
        # un dossier et perimee pour l'autre au meme instant, et c'est l'clock qui tranche,
        # jamais la date du jour implicite.
        for role, genre in (gab.dates.items() if "expiry" in actifs else ()):
            if genre != "expiration":
                continue
            for field in gab.field(role):
                if illisible:
                    out.append(Finding("expiry", piece_id, field, None, False,
                                       "piece sous le floor de resolution"))
                    continue
                date, raw = _read_date(lec, gab, field, par_controle["expiry"])
                if date is None:
                    out.append(Finding("expiry", piece_id, field, None, False,
                                       f"illisible {raw[:24]!r}"))
                    continue
                jours = (date_ref - date).days
                out.append(Finding("expiry", piece_id, field, float(jours),
                                   jours > thresholds["expiry"],
                                   f"{date} vs {clock} {date_ref}"))

        # C7 sous le floor de resolution. Le dpi n'est pas lu dans une metadonnee (un vrai
        # scan n'en a pas): il est ESTIME par l'scale qui recale la page sur le blank.
        if "resolution" in actifs:
            out.append(Finding("resolution", piece_id, "", -lec.source_dpi,
                               -lec.source_dpi > thresholds["resolution"],
                               f"{lec.source_dpi:.0f} dpi estimes"))
        # C8 page coupee.
        if "cropped_page" in actifs:
            out.append(Finding("cropped_page", piece_id, "", 1.0 - lec.coverage,
                               1.0 - lec.coverage > thresholds["cropped_page"],
                               f"coverage {lec.coverage:.3f}"))
        # C9 page tournee. Score continu: de combien le quarter_turns retenu bat le quarter_turns d'origine.
        if "rotated_page" in actifs:
            out.append(Finding("rotated_page", piece_id, "", lec.orientation_margin,
                               lec.orientation_margin > thresholds["rotated_page"],
                               f"quarter_turns {lec.quarter_turns}"))

        # C6 value interdite qui reapparait. Comparaison sur la shape NUE (sans separateurs):
        # un number interdit reste interdit qu'il soit imprime 999-99-9999 ou 999999999.
        added_words = (lec.all_words(par_controle["forbidden_value"].min_conf)
                        if "forbidden_value" in actifs and not illisible else [])
        for val in (ref.forbidden_values if "forbidden_value" in actifs else ()):
            if illisible:
                out.append(Finding("forbidden_value", piece_id, val, None, False,
                                   "piece sous le floor de resolution"))
                continue
            s = _best_ngram(added_words, val)
            out.append(Finding("forbidden_value", piece_id, val, s,
                               s > thresholds["forbidden_value"], f"ressemblance {s:.2f}"))

    # C5 meme data divergente entre deux pieces. Mesuree par RECOUVREMENT DE JETONS, sans
    # passer par le reference: deux pieces peuvent se contredire alors qu'aucune des deux
    # n'est celle qu'on attendait.
    for coh in (ref.consistencies if "consistency" in actifs else ()):
        lus = []
        illisibles = []
        for l in coh["readings"]:
            lec = readings.get(l["piece"])
            if lec is None:
                continue
            if abstention and lec.source_dpi < floor:
                illisibles.append(l["piece"])
                continue
            gab = ref.templates[dict(ref.pieces)[l["piece"]]]
            for field in gab.field(l["field"]):
                z = zones(gab).get(field)
                if z is not None:
                    rc = par_controle["consistency"]
                    lus.append((l["piece"], _tokens(
                        m[0] for m in lec.zone_words(z, rc.min_conf, capteur=rc.text_sensor))))
        if illisibles:
            out.append(Finding("consistency", "+".join(illisibles), coh["data"], None, False,
                               "piece sous le floor de resolution"))
            continue
        for i in range(len(lus)):
            for j in range(i + 1, len(lus)):
                (pa, a), (pb, b) = lus[i], lus[j]
                rec = _overlap(a, b)
                out.append(Finding("consistency", f"{pa}+{pb}", coh["data"], 1.0 - rec,
                                   1.0 - rec > thresholds["consistency"],
                                   f"{sorted(a)} vs {sorted(b)}"[:70]))
    return out
