#!/usr/bin/env python3
"""Lire les thresholds SUR les courbes, pas les choisir a la main.

Entree: les mesures brutes de la grid. Sortie: une curve precision/rappel par check, le
point de fonctionnement retenu, le floor de panne, et les tableaux des duels A/B.

L'ASYMETRIE EST DECLAREE ICI, EN CHIFFRES, parce qu'un point de fonctionnement choisi sans
elle est choisi au hasard:

  un FAUX NEGATIF, c'est le filing qui refuse le dossier. Des mois de delai, une convocation
  a reprendre, parfois une piece a redemander a une administration etrangere.
  un FAUX POSITIF, c'est la gate qui crie sur un dossier clean. Il ne coute pas un delai, il
  coute la CREDIBILITE de la gate, et une regle qui crie au loup fait survoler toutes celles
  d'a cote. C'est le seul cout qui detruit l'outil au lieu de le degrader.

D'ou la regle: on prend le RAPPEL LE PLUS HAUT ATTEIGNABLE sous un budget de faux positifs
tenu, et le budget est ecrit noir sur blanc (FP_BUDGET), pas suppose. Il est par check et
par dossier: avec neuf checks, un dossier clean a environ 9 fois ce budget de chance de
declencher une alarme pour rien, et ce chiffre-la est celui que l'utilisateur ressent.

    python3 grid/analyze.py
"""
import argparse
import collections
import csv
import itertools
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preflight.sensors import DISC_RATIOS, INK_THRESHOLDS
from preflight.checks import CHECKS, NUISANCES, Settings, evaluate
from preflight.fixtures import BY_NAME, VARIANTS
from preflight.reading import Reading
from preflight.reference import load_reference

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "grid", "resultats")

# Budget de faux positifs PAR CIBLE (un field, une case, une value interdite), et non par
# dossier. Un dossier porte dix-sept fields required: le taux qu'un utilisateur RESSENT est
# celui du dossier entier, environ dix-sept fois celui-ci, et il est mesure puis publie a
# part sous le name de taux par dossier. Declarer l'un en croyant parler de l'autre est la
# facon la plus courante d'annoncer une gate plus sure qu'elle n'est.
FP_BUDGET = 0.002
VALIDATION_SEED = 37     # jamais regardee pour choisir un seuil, uniquement pour le rapporter
RECALL_FLOOR = 0.95     # sous ce rappel, la cell est declaree hors domaine
PREVALENCE = 0.10          # part supposee de dossiers reellement fautifs, pour la precision

# Balaye jusqu'a 0. Un field PEIGNE (une case par caractere, le formulaire le declare) se lit
# "4/1)2" avec une confiance de 38: les trois chiffres sont bien la, mais les separateurs
# cassent le modele de mot de tesseract et effondrent sa confiance. Un floor a 40 jetterait
# un field REMPLI, c'est-a-dire fabriquerait un faux positif sur un dossier clean, du cote qui
# detruit la credibilite de la gate. La confiance etant appliquee a l'ANALYSE et non a la
# grid, l'elargir ne coute pas une seule image.
CONF_MINS = (0.0, 10.0, 20.0, 40.0, 60.0, 80.0)
TEXT_SENSORS = ("page", "zone", "union")
SIGNATURE_SENSORS = ("components", "ink")

VALEURS = {"min_conf": CONF_MINS, "text_sensor": TEXT_SENSORS,
           "disc_ratio": DISC_RATIOS, "ink_threshold": INK_THRESHOLDS,
           "signature_sensor": SIGNATURE_SENSORS}

MINUS_INF = -1e18


def combinations(check):
    """Les reglages qui changent quelque chose POUR CE CONTROLE, et eux seuls.

    Le check des fields required est le seul a croiser deux familles de sensors qui n'ont
    pas les memes boutons: la confiance OCR ne veut rien dire pour un capteur d'ink, et le
    seuil d'ink ne veut rien dire pour un capteur de words. Les croiser quand meme
    multiplierait par six un balayage deja long sans produire un seul point de plus.
    """
    if check == "required_field":
        return ([Settings(text_sensor=t, min_conf=c)
                 for t in TEXT_SENSORS for c in CONF_MINS]
                + [Settings(text_sensor="ink", ink_threshold=e) for e in INK_THRESHOLDS])
    noms = NUISANCES[check]
    if not noms:
        return [Settings()]
    return [Settings(**dict(zip(noms, v)))
            for v in itertools.product(*[VALEURS[n] for n in noms])]


def load(chemin):
    """index[(angle, dpi, jpeg, sigma, seed)][variant][piece] = Reading"""
    index = collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            d = json.loads(ligne)
            key = (d["angle"], d["dpi"], d["jpeg"], d["sigma"], d["seed"])
            index[key][d["variant"]][d["piece"]] = Reading.from_dict(d["reading"])
    return index


def complete_dossiers(index):
    """Un dossier de variant = la piece modifiee, plus les deux pieces du dossier clean.

    Les cellules incompletes sont ecartees en silence: la grid reprend ou elle s'arrete, et
    une cell a moitie ecrite fabriquerait un faux negatif qui n'existe pas.
    """
    attendues = {v.name for v in VARIANTS}
    out = {}
    for key, par_var in index.items():
        if not attendues <= set(par_var):
            continue
        clean = par_var["clean"]
        if len(clean) < 3:
            continue
        d = {"clean": clean}
        for v in VARIANTS:
            if v.check:
                d[v.name] = dict(clean, **par_var[v.name])
        out[key] = d
    return out


def target_scores(readings, ref, check, reg, clock="filing", abstention=False):
    """Le score de CHAQUE target du check: un field, une case, une value interdite.

    C'est la bonne unite de mesure, et le choisir change le resultat. Roule au niveau du
    dossier, le check des fields required n'a que deux points de fonctionnement possibles
    (crier des qu'un field sur dix-sept est illisible, ou ne jamais crier) parce que son score
    est le PIRE de ses fields. Par target, la curve existe vraiment, les negatifs sont
    dix-sept fois plus nombreux donc le taux de faux positifs est mesurable, et surtout on
    peut dire QUEL field n'est pas certifiable au lieu de condamner le check entier.
    """
    return {(c.piece, str(c.target)): c.score
            for c in evaluate(readings, ref, clock, reg, checks=[check],
                             abstention=abstention)
            if c.score is not None}


def dossier_score(readings, ref, check, reg, clock="filing"):
    """Le pire constat du dossier. Un dossier est refuse des qu'UNE piece cloche."""
    return max(target_scores(readings, ref, check, reg, clock).values(), default=MINUS_INF)


def damaged_targets(var, ref):
    """Ce que la variant abime VRAIMENT, declare et pas devine.

    Sans cette liste, la classe positive serait "tout le dossier fautif" et les seize fields
    intacts qu'il porte compteraient comme des positifs manques.
    """
    if not var.check:
        return set()
    gab = ref.templates[dict(ref.pieces)[var.piece]] if var.piece else None
    if var.empty_fields:
        return {(var.piece, c) for role in var.empty_fields for c in gab.field(role)}
    if var.uncheck:
        return {(var.piece, gab.boxes[role]) for role in var.uncheck}
    if var.without_signature:
        return {(var.piece, c) for c in gab.signatures.values()}
    if var.expired_date:
        return {(var.piece, c) for role, genre in gab.dates.items() if genre == "expiration"
                for c in gab.field(role)}
    if var.check == "forbidden_value":
        injectees = {str(v) for v in var.replace.values()}
        return {(var.piece, v) for v in ref.forbidden_values if v in injectees}
    if var.check == "consistency":
        return {(f"{a['piece']}+{b['piece']}", coh["data"])
                for coh in ref.consistencies
                for a, b in itertools.combinations(coh["readings"], 2)}
    return {(var.piece, "")}          # resolution, page coupee, page tournee


def wilson(succes, n, z=1.96):
    """Intervalle de Wilson. A n=3 graines par cell, l'intervalle normal ment."""
    if n == 0:
        return (0.0, 1.0)
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def curve(pos, neg):
    """Tous les points de fonctionnement, du plus laxiste au plus strict.

    Les thresholds candidats sont les scores OBSERVES: entre deux scores voisins, aucun seuil ne
    change quoi que ce soit, et en inventer d'autres ne ferait qu'epaissir le fichier.
    """
    thresholds = sorted({s for s in list(pos) + list(neg) if s > MINUS_INF})
    if not thresholds:
        return []
    marges = [thresholds[0] - 1.0]
    marges += [(a + b) / 2 for a, b in zip(thresholds, thresholds[1:])]
    marges += [thresholds[-1] + 1.0]
    pts = []
    for t in marges:
        tp = sum(1 for s in pos if s > t)
        fp = sum(1 for s in neg if s > t)
        rappel = tp / len(pos) if pos else 0.0
        fpr = fp / len(neg) if neg else 0.0
        prec_grille = tp / (tp + fp) if (tp + fp) else 1.0
        num = PREVALENCE * rappel
        prec_reelle = num / (num + (1 - PREVALENCE) * fpr) if (num + (1 - PREVALENCE) * fpr) else 1.0
        pts.append({"seuil": t, "rappel": rappel, "fpr": fpr,
                    "precision_grille": prec_grille, "precision_prevalence": prec_reelle,
                    "tp": tp, "fp": fp, "n_pos": len(pos), "n_neg": len(neg)})
    return pts


def precisions(rappel, fpr):
    """Precision a la composition de la grid (un fautif pour un clean) et a la prevalence
    supposee. La seconde est celle qui compte, et elle est plus severe."""
    num = PREVALENCE * rappel
    return {"precision_grille": rappel / (rappel + fpr) if (rappel + fpr) else 1.0,
            "precision_prevalence": num / (num + (1 - PREVALENCE) * fpr)
            if (num + (1 - PREVALENCE) * fpr) else 1.0}


def chosen_point(pts, budget=FP_BUDGET):
    """Le rappel le plus haut sous le budget de faux positifs. Rien de plus, rien de moins.

    Il existe TOUJOURS un point sous n'importe quel budget: celui qui ne fires jamais, a
    rappel nul. Ce n'est donc jamais l'absence de point qui signale un check inutilisable,
    c'est un rappel trop bas au point retenu, et c'est ce que LIMITES.md doit dire.
    """
    if not pts:
        return None
    tenables = [p for p in pts if p["fpr"] <= budget]
    if not tenables:
        return None
    meilleur = max(tenables, key=lambda p: (p["rappel"], -p["fpr"]))
    # A rappel egal, on prend le seuil le plus au milieu du palier: un seuil colle contre une
    # value observee bascule au premier pixel de bruit d'une mesure future.
    palier = [p for p in tenables
              if p["rappel"] == meilleur["rappel"] and p["fpr"] == meilleur["fpr"]]
    return palier[len(palier) // 2]


def sweep(dossiers, ref, check):
    """Pour chaque reglage, les scores par target, cell par cell.

    Retour: {reglage: {cle_cellule: {"pos": {target: score}, "neg": {target: score}}}}
    Les positifs sont les cibles que la variant abime; les negatifs sont TOUTES les cibles du
    dossier clean, ce qui donne au taux de faux positifs la puissance qui lui manquait.
    """
    var = next(v for v in VARIANTS if v.check == check)
    cibles = damaged_targets(var, ref)
    out = {}
    for reg in combinations(check):
        par_cellule = {}
        for key, d in dossiers.items():
            tous = target_scores(d[var.name], ref, check, reg)
            pos = {k: v for k, v in tous.items() if k in cibles} or tous
            par_cellule[key] = {"pos": pos,
                                "neg": target_scores(d["clean"], ref, check, reg)}
        out[reg] = par_cellule
    return out


def flatten(par_cellule):
    pos = [x for v in par_cellule.values() for x in v["pos"].values()]
    neg = [x for v in par_cellule.values() for x in v["neg"].values()]
    return pos, neg


def split(par_cellule):
    """Calibration contre validation.

    Choisir un seuil sur des donnees puis rapporter son rappel sur les MEMES donnees le
    surestime toujours: le seuil s'est loge dans le bruit de ces tirages-la. Deux graines
    calibrent, la troisieme n'est jamais regardee avant d'ecrire le chiffre.
    """
    cal = {k: v for k, v in par_cellule.items() if k[4] != VALIDATION_SEED}
    val = {k: v for k, v in par_cellule.items() if k[4] == VALIDATION_SEED}
    return cal, val


def measure(par_cellule, seuil):
    """Deux taux de faux positifs, et il faut les deux.

    Par target: la probabilite qu'UN field clean soit declare vide. C'est celui sur lequel le
    seuil se choisit, parce que c'est la decision elementaire.
    Par dossier: la probabilite qu'AU MOINS UNE alarme parte sur un dossier entierement clean.
    C'est celui que l'utilisateur ressent, et c'est lui qui decide s'il continue de croire la
    gate. Le second est environ le premier multiplie par le nombre de cibles.
    """
    pos, neg = flatten(par_cellule)
    tp = sum(1 for x in pos if x > seuil)
    fp = sum(1 for x in neg if x > seuil)
    touches = sum(1 for v in par_cellule.values() if any(x > seuil for x in v["neg"].values()))
    n_d = len(par_cellule)
    return {"seuil": seuil, "rappel": tp / len(pos) if pos else 0.0,
            "fpr": fp / len(neg) if neg else 0.0, "tp": tp, "fp": fp,
            "n_pos": len(pos), "n_neg": len(neg), "n_dossiers": n_d,
            "fpr_dossier": touches / n_d if n_d else 0.0,
            "ic_rappel": wilson(tp, len(pos)), "ic_fpr": wilson(fp, len(neg)),
            "ic_fpr_dossier": wilson(touches, n_d)}


def certifiability(par_cellule):
    """Quelles cibles l'outil peut certifier, et lesquelles il doit refuser de juger.

    CE CALCUL NE TOUCHE PAS AU POINT DE FONCTIONNEMENT, et il a fallu une erreur pour le
    comprendre. En excluant les cibles genantes AVANT de choisir le seuil, on cree une boucle:
    moins de negatifs, donc un seuil plus permissif tenable, donc un rappel de 100% affiche sur
    la seule target survivante. Sur le check des valeurs interdites, cette boucle sortait un
    seuil de 0,11 de ressemblance, value a laquelle n'importe quoi ressemble a n'importe quoi,
    avec cinq cibles sur six exclues et un score parfait. C'etait du maquillage.

    Le seuil se choisit donc sur TOUTES les cibles. Ce calcul-ci ne sert qu'a EXPLIQUER le
    chiffre obtenu: quand un check plafonne, c'est presque toujours deux ou trois fields qui
    le plafonnent, et les nommer vaut mieux que condamner le check entier. Ce qu'un tel
    field appelle, c'est que l'outil y reponde "je ne sais pas read_piece ce field" au lieu de "ce
    field est vide": meme capteur, consequences opposees au filing.
    """
    pos, _ = flatten(par_cellule)
    if not pos:
        return {}, {}
    ordonnes = sorted(pos)
    plein = ordonnes[min(len(ordonnes) - 1,
                         int(round((1 - RECALL_FLOOR) * len(ordonnes))))] - 1e-9
    compte, vus = collections.Counter(), collections.Counter()
    for v in par_cellule.values():
        for target, score in v["neg"].items():
            vus[target] += 1
            if score > plein:
                compte[target] += 1
    taux = {c: compte[c] / vus[c] for c in vus}
    return ({c: t for c, t in taux.items() if t <= FP_BUDGET},
            {c: t for c, t in sorted(taux.items(), key=lambda kv: -kv[1]) if t > FP_BUDGET})


def restricted_to_certifiable(par_cellule, gardees, check):
    """Chiffre SECONDAIRE et etiquete comme tel: ce que le check vaut si on ne lui demande
    que les cibles qu'il sait certifier. Jamais le chiffre de tete, jamais dans thresholds.json."""
    if not gardees or len(gardees) == len(next(iter(par_cellule.values()))["neg"]):
        return None
    sous = restrict(par_cellule, gardees)
    cal, val = split(sous)
    pos, neg = flatten(cal)
    pt = chosen_point(curve(pos, neg))
    if pt is None:
        return None
    m = measure(val, pt["seuil"])
    m["cibles_gardees"] = len(gardees)
    m["cibles_totales"] = len(next(iter(par_cellule.values()))["neg"])
    return m


def restrict(par_cellule, gardees):
    return {key: {"pos": v["pos"],
                  "neg": {k: x for k, x in v["neg"].items() if k in gardees}}
            for key, v in par_cellule.items()}


def noisy_targets(par_cellule, seuil, n=8):
    """Quelles cibles SAINES declenchent, et a quelle frequence. La liste actionnable.

    Un check globalement inutilisable est presque toujours un check que deux ou trois
    fields rendent inutilisable. Nommer ces fields vaut mieux que condamner le check.
    """
    compte = collections.Counter()
    vus = collections.Counter()
    for v in par_cellule.values():
        for target, score in v["neg"].items():
            vus[target] += 1
            if score > seuil:
                compte[target] += 1
    return [(c, compte[c], vus[c]) for c, _ in compte.most_common(n)]


def settings_summary(par_cellule):
    """La curve et le point sont calcules sur la CALIBRATION seule."""
    cal, _ = split(par_cellule)
    pos, neg = flatten(cal)
    pts = curve(pos, neg)
    return pts, chosen_point(pts)


def by_factor(par_cellule, seuil):
    """Rappel et faux positifs par value de chaque facteur, au seuil retenu."""
    axes = {"angle": 0, "dpi": 1, "jpeg": 2, "sigma": 3}
    out = {}
    for name, i in axes.items():
        groupes = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        for key, v in par_cellule.items():
            g = groupes[key[i]]
            g[0] += sum(1 for x in v["pos"].values() if x > seuil)
            g[1] += len(v["pos"])
            g[2] += sum(1 for x in v["neg"].values() if x > seuil)
            g[3] += len(v["neg"])
            g[4] += any(x > seuil for x in v["neg"].values())
            g[5] += 1
        out[name] = {val: {"rappel": g[0] / max(1, g[1]), "n": g[1],
                          "fpr": g[2] / max(1, g[3]),
                          "fpr_dossier": g[4] / max(1, g[5]),
                          "ic": wilson(g[0], g[1])}
                    for val, g in sorted(groupes.items())}
    return out


def floor(par_cellule, seuil, minimum=RECALL_FLOOR):
    """Les cellules ou le rappel passe sous le floor. Une cell = 3 graines.

    Un outil qui ne dit pas ou il cesse de marcher n'est pas mesure, il est raconte.
    """
    groupes = collections.defaultdict(lambda: [0, 0])
    for (a, d, q, s, _), v in par_cellule.items():
        g = groupes[(a, d, q, s)]
        g[0] += sum(1 for x in v["pos"].values() if x > seuil)
        g[1] += len(v["pos"])
    tombees = {c: (g[0] / max(1, g[1]), g[1]) for c, g in groupes.items()
               if g[0] / max(1, g[1]) < minimum}
    return tombees, len(groupes)


AXES = ("angle", "dpi", "jpeg", "sigma")


def worst_conjunctions(par_cellule, seuil, combien=3):
    """Les pires CROISEMENTS de deux facteurs, pas seulement les pires valeurs de chacun.

    Une reading marginale peut mentir par omission. Sur les valeurs interdites, le rappel dit
    0,979 a 300 dpi, 0,981 en JPEG 95 et 0,977 a sigma 12: aucune de ces trois valeurs ne
    franchit le floor, et on conclut que le check va bien partout. Croisees, elles font
    une cell sous le floor. Le signe est a l'envers de l'intuition, et c'est ce qui le
    rend interessant: le rappel baisse quand la qualite MONTE, parce qu'une compression forte
    efface le grain du capteur alors qu'une compression legere le garde, et qu'a haute
    resolution ce grain est assez fin pour se faire read_piece comme de la structure de caractere.
    Cette partie du mecanisme est mesuree par temoin, voir grid/corner_followup.py.

    CE BALAYAGE NE VOIT QUE L'OMBRE DE LA CELL, et il faut le savoir en le lisant. La shape
    reelle de ce defaut-la est une conjonction de QUATRE facteurs (300 dpi ET JPEG 95 ET bruit
    12 ET angle superieur ou egal a 0,5 deg: 30/30 en dessous de cet angle, 50/60 au-dessus).
    Une paire moyenne sur les deux facteurs restants, donc elle attenue toujours ce qu'elle
    montre. Aller a trois et quatre facteurs ferait exploser le nombre de boxes et tomber n a
    15 par case, ce qui rendrait les intervalles inutilisables. Le balayage a deux facteurs
    sert donc a TROUVER la cell; c'est la liste des pires cellules, deja a quatre facteurs,
    qui la NOMME.
    """
    out = {}
    for i, a in enumerate(AXES):
        for b in AXES[i + 1:]:
            ia, ib = AXES.index(a), AXES.index(b)
            groupes = collections.defaultdict(lambda: [0, 0])
            for key, v in par_cellule.items():
                g = groupes[(key[ia], key[ib])]
                g[0] += sum(1 for x in v["pos"].values() if x > seuil)
                g[1] += len(v["pos"])
            classe = sorted(((k, g[0] / max(1, g[1]), g[1], wilson(g[0], g[1]))
                             for k, g in groupes.items()), key=lambda t: t[1])
            out[f"{a} x {b}"] = [{"valeurs": list(k), "rappel": r, "n": n, "ic": list(ic)}
                                 for k, r, n, ic in classe[:combien]]
    return out


def frontier(tombees, toutes):
    """La frontier lisible: par facteur, la value a partir de laquelle ca tombe."""
    axes = ["angle", "dpi", "jpeg", "sigma"]
    out = {}
    for i, name in enumerate(axes):
        compte = collections.Counter(c[i] for c in tombees)
        total = collections.Counter(c[i] for c in toutes)
        out[name] = {v: (compte.get(v, 0), total[v]) for v in sorted(total)}
    return out


def plot(resultats, chemin):
    if not resultats:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(resultats)
    cols = 3
    lignes = (n + cols - 1) // cols
    fig, axes = plt.subplots(lignes, cols, figsize=(4.6 * cols, 3.8 * lignes))
    for ax, (check, r) in zip(axes.ravel(), sorted(resultats.items())):
        for etiquette, pts, gras in r["courbes"]:
            xs = [p["rappel"] for p in pts]
            ys = [p["precision_prevalence"] for p in pts]
            ax.plot(xs, ys, linewidth=2.0 if gras else 0.8,
                    alpha=1.0 if gras else 0.35, label=etiquette if gras else None)
        pt = r["point"]
        if pt:
            ax.plot([pt["rappel"]], [pt["precision_prevalence"]], "o", color="crimson", zorder=5)
            ax.annotate(f"seuil {pt['seuil']:.3g}\nrappel {pt['rappel']:.3f}\nfpr {pt['fpr']:.4f}",
                        (pt["rappel"], pt["precision_prevalence"]), fontsize=7,
                        xytext=(-4, -34), textcoords="offset points", color="crimson")
        ax.axvline(RECALL_FLOOR, color="gray", linestyle=":", linewidth=0.8)
        ax.set_title(check, fontsize=10)
        ax.set_xlabel("rappel")
        ax.set_ylabel(f"precision a prevalence {PREVALENCE:.0%}")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.2)
        if any(g for _, _, g in r["courbes"]):
            ax.legend(fontsize=7, loc="lower left")
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(f"Precision/rappel par check, {resultats[list(resultats)[0]]['n_cellules']} "
                 f"cellules x 3 graines, budget de faux positifs {FP_BUDGET:.1%}", fontsize=11)
    fig.tight_layout()
    fig.savefig(chemin, dpi=130)
    return chemin


# Les checks qui dependent vraiment de ce que l'OCR arrive a read_piece. Ce sont eux qui
# definissent le floor de resolution utile, pas le check de resolution lui-meme.
OCR_DEPENDENT = ("required_field", "expiry", "consistency", "forbidden_value")


def crosstalk(dossiers, ref, resultats):
    """Le check c se fires-t-il quand le defaut appartient a un AUTRE check.

    Les tests posaient deja cette exigence, mais sur une seule cell. La grid la mesure
    partout, parce que c'est la moitie qui compte: un check qui crie sur le defaut du
    voisin fait douter du voisin, et une regle qui crie au loup fait survoler celles d'a cote.

    Le tableau n'est pas fait que de fautes. Une page ROGNEE emporte de vrais fields avec
    elle: le check des fields required a raison de crier. Ce que le tableau donne, c'est de
    quoi split ce qui est une consequence physique de ce qui est une contamination.
    """
    out = {}
    for check, r in resultats.items():
        reg, seuil = r["reglage"], r["seuil"]
        lignes = {}
        for v in VARIANTS:
            if not v.check or v.check == check:
                continue
            n = tire = 0
            for d in dossiers.values():
                # ICI l'abstention est BRANCHEE: la crosstalk mesure le comportement du
                # PRODUIT, pas la capacite brute des sensors.
                scores = target_scores(d[v.name], ref, check, reg, abstention=True)
                n += 1
                tire += any(x > seuil for x in scores.values())
            lignes[v.name] = {"taux": tire / max(1, n), "n": n, "ic": wilson(tire, n)}
        out[check] = lignes
    return out


def dpi_estimator_error(dossiers):
    """L'erreur relative maximale de l'estimateur de dpi, mesuree sur les dossiers sains."""
    pire = 0.0
    for (_, dpi, _, _, _), d in dossiers.items():
        for lec in d["clean"].values():
            pire = max(pire, abs(lec.source_dpi - dpi) / dpi)
    return pire


def remeasure(r, seuil):
    """Tout recalculer AU SEUIL QU'ON PUBLIE. Sinon on publie un rappel mesure ailleurs.

    Le seuil du check de resolution n'est pas celui de sa curve: il est porte au floor
    des autres. Sans ce recalcul, thresholds.json annoncait "faux positifs 0,0000" a cote d'une
    value a laquelle c'etait faux (33% des cibles saines a 150 dpi). Meme famille de faute
    que la phrase de reading survivant a son capteur: un nombre mesure sous une configuration,
    publie a cote d'une autre.
    """
    pc = r["_par_cellule"]
    cal, val = split(pc)
    tombees, n_cel = floor(pc, seuil)
    r.update({"seuil": seuil,
              "calibration": measure(cal, seuil), "validation": measure(val, seuil),
              "ensemble": measure(pc, seuil),
              "facteurs": by_factor(pc, seuil),
              "conjonctions": worst_conjunctions(pc, seuil),
              "tombees": tombees, "n_cellules": n_cel,
              "frontier": frontier(tombees, {c[:4] for c in pc}),
              "noisy_targets": noisy_targets(pc, seuil)})
    return r


def operational_floor(resultats, domaine, dossiers):
    """Le seuil du check de resolution ne se lit pas sur SA curve. Et c'est le sujet.

    Sa curve le placerait entre 72 dpi (la variant fautive) et 96 dpi (le plus bas dpi de la
    grid), c'est-a-dire a l'endroit qui separe le mieux ces deux populations. Mais la
    question que ce check doit poser n'est pas "cette page est-elle a 72 dpi", c'est "cette
    page est-elle assez nette pour que les AUTRES checks tiennent". Son seuil se lit donc
    sur le PLANCHER DE PANNE des checks qui dependent de l'OCR: le plus bas dpi ou tous
    gardent leur rappel au-dessus du floor.

    Consequence assumee, et il faut la dire: si ce floor est au-dessus du plus bas dpi de
    la grid, alors des dossiers SAINS numerises trop bas declenchent ce check. Ce n'est
    pas un faux positif, c'est le check qui fait son task: on refuse de se prononcer sur
    une page qu'on ne sait pas read_piece. La confondre avec un faux positif reviendrait a se taire
    exactement quand on ne sait pas.
    """
    # Le seuil se pose SOUS le floor, pas dessus. Un scan a exactement 150 dpi s'estime a
    # 149,98: seuil pose pile sur 150, il declenchait sur les 288 dossiers sains numerises au
    # floor meme. La marge vaut dix fois la pire erreur mesuree de l'estimateur, au minimum
    # 1%, ce qui reste quarante fois plus fin que l'ecart entre deux dpi de la grid.
    erreur = dpi_estimator_error(dossiers)
    marge = max(0.01, 10 * erreur)
    plancher_dpi = domaine
    seuil_dpi = domaine * (1 - marge)
    dpis = sorted(resultats["resolution"]["facteurs"]["dpi"])
    detail = {c: {d: round(resultats[c]["facteurs"]["dpi"][d]["rappel"], 3) for d in dpis}
              for c in OCR_DEPENDENT if c in resultats}
    pr = resultats["resolution"]["point"]
    return {"seuil": -float(seuil_dpi),
            "point": dict(pr or {}, seuil=-float(seuil_dpi)),
            "plancher_dpi": plancher_dpi,
            "marge_estimateur": marge,
            "erreur_max_estimateur": erreur,
            "seuil_courbe_propre": (pr or {}).get("seuil"),
            "rappel_par_dpi_des_dependants": detail}


DOMAINS = (96, 150, 200, 300)


def definition_thresholds():
    """Les thresholds qui ne se FITTENT pas, parce qu'ils ne sont pas des parametres.

    "Perime" veut dire que la date est passee: le seuil vaut zero jour, point. Laisser la
    grid le choisir a donne -207,5 jours, et c'est le test des deux clocks qui l'a
    attrape: la piece saine du reference expire en 2027, donc n'importe quel seuil entre
    -497 et -110 separe parfaitement les donnees, et l'optimiseur a pris le milieu du palier.
    L'outil aurait declare une piece perimee sept mois avant qu'elle le soit, avec un rappel
    de 1,000 a l'appui.

    C'est le piege central de "read_piece le seuil sur la curve": une curve ne connait que les
    donnees qu'on lui a donnees, et elle deplacera sans hesiter un seuil qui encode du SENS.
    La grid reste utile sur ces checks, mais pour repondre a une autre question: le seuil
    etant fixe par definition, quel rappel tient-il et a quel prix.
    """
    from preflight.thresholds import raw
    return {k for k, v in raw()["thresholds"].items() if v["origine"] == "definition"}


def subgrid(par_reglage, garde):
    return {reg: {key: v for key, v in pc.items() if garde(key)}
            for reg, pc in par_reglage.items()}


def analyze_check(par_reglage, check, sortie=None):
    """Retient le meilleur reglage sous budget, mesure, cherche le floor.

    Prend le balayage DEJA calcule: la recherche du domaine nominal essaie quatre sous-grilles
    et il n'y a aucune raison de repasser quatre fois sur les memes images, ni meme sur les
    memes scores.
    """
    classement = []
    for reg, par_cellule in par_reglage.items():
        if not par_cellule:
            continue
        pts, pt = settings_summary(par_cellule)
        classement.append((reg, par_cellule, pts, pt))
    if not classement:
        return None
    tenables = [c for c in classement if c[3] is not None]
    gagnant = max(tenables or classement,
                  key=lambda c: (c[3]["rappel"] if c[3] else -1, -(c[3]["fpr"] if c[3] else 1)))
    reg, par_cellule, pts, pt = gagnant
    if not pts:
        return None
    fige = check in definition_thresholds()
    if fige:
        from preflight.thresholds import load_thresholds
        impose = float(load_thresholds()[check])
        # A seuil impose, le balayage ne sert plus qu'a choisir le CAPTEUR: on garde celui qui
        # rappelle le mieux A CE SEUIL-LA, pas celui qui rappellerait le mieux ailleurs.
        def note(c):
            m = measure(split(c[1])[0], impose)
            return (m["rappel"], -m["fpr"])
        reg, par_cellule, pts, pt = max(classement, key=note)
        m = measure(split(par_cellule)[0], impose)
        pt = dict(m, seuil=impose, **precisions(m["rappel"], m["fpr"]))
    gardees, exclues = certifiability(par_cellule)
    seuil = pt["seuil"] if pt else max(p["seuil"] for p in pts)
    cal, val = split(par_cellule)
    tombees, n_cel = floor(par_cellule, seuil)
    if sortie:
        with open(os.path.join(sortie, f"pr_{check}.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pts[0].keys()))
            w.writeheader()
            w.writerows(pts)
    return {
        "reglage": reg, "reglage_texte": settings_name(reg, check), "point": pt,
        "seuil": seuil, "n_cellules": n_cel,
        "calibration": measure(cal, seuil), "validation": measure(val, seuil),
        "ensemble": measure(par_cellule, seuil),
        "courbes": [(settings_name(r, check), p, r == reg) for r, _, p, _ in classement],
        "facteurs": by_factor(par_cellule, seuil),
        "tombees": tombees, "frontier": frontier(tombees, {c[:4] for c in par_cellule}),
        "noisy_targets": noisy_targets(par_cellule, seuil),
        "seuil_fige_par_definition": fige,
        "cibles_non_certifiables": [(f"{a} / {b}", round(t, 4)) for (a, b), t in exclues.items()],
        "restreint": restricted_to_certifiable(par_cellule, gardees, check),
        "classement": [{"reglage": settings_name(r, check),
                        "rappel": (q or {}).get("rappel"), "fpr": (q or {}).get("fpr"),
                        "seuil": (q or {}).get("seuil")}
                       for r, pc, _, q in sorted(
                           classement, key=lambda c: -((c[3] or {}).get("rappel", -1)))],
        "_classement": classement,
        "_par_cellule": par_cellule,
        "conjonctions": worst_conjunctions(par_cellule, seuil),
    }


def choose_domain(balayages, checks):
    """Le domaine nominal: le plus bas dpi ou les checks qui LISENT tiennent leur floor.

    Sans cette etape, le point de fonctionnement de tout check de texte est decide par les
    cellules ou la page est illisible, et il recule jusqu'a ne plus rien declencher. La raison
    est mecanique: un dossier est refuse des qu'UN field required est vide, donc le score du
    dossier est celui de son pire field; a 96 dpi le Cerfa a des fields que l'OCR ne lit pas,
    le dossier SAIN atteint alors le meme score que le fautif, et sous un budget de faux
    positifs serre aucun seuil ne les separe plus.

    Assouplir le budget effacerait le probleme sans le resoudre. Le bon geste est de dire ou
    l'outil se declare competent, et de REFUSER DE CONCLURE en dessous: c'est le role du
    check de resolution, dont le seuil sort precisement d'ici.
    """
    besoins = [c for c in OCR_DEPENDENT if c in checks]
    essais = []
    for dpi_min in DOMAINS:
        premier = next(iter(balayages.values()), {})
        vide = all(not any(k[1] >= dpi_min for k in pc) for pc in premier.values()) if premier \
            else True
        if vide:
            essais.append((dpi_min, None))
            continue
        if not besoins:
            essais.append((dpi_min, 1.0))
            continue
        pire = 1.0
        for c in besoins:
            r = analyze_check(subgrid(balayages[c], lambda k: k[1] >= dpi_min), c)
            pire = min(pire, 0.0 if r is None else r["validation"]["rappel"])
        essais.append((dpi_min, pire))
        if pire >= RECALL_FLOOR:
            return dpi_min, essais
    # Aucun domaine ne tient le floor. On garde alors le MOINS MAUVAIS, jamais le plus
    # etroit: se replier sur le domaine le plus etroit reviendrait a repondre "300 dpi" a une
    # question a laquelle la mesure a dit non partout, et a le faire sur le moins de donnees.
    valides = [(d, r) for d, r in essais if r is not None]
    if not valides:
        return DOMAINS[0], essais
    return max(valides, key=lambda x: x[1])[0], essais


PHRASES = {
    "required_field": lambda r, v: (
        f"se fires si la zone porte moins de {-v:.3f}% d'ink AJOUTEE par rapport au "
        f"blank (seuil d'ink {r.ink_threshold})" if r.text_sensor == "ink" else
        f"se fires si moins de {-v:.0f} caractere(s) alphanumerique(s) ajoute(s) sont lus "
        f"dans la zone par le capteur {r.text_sensor} au-dessus de {r.min_conf:.0f} de "
        f"confiance"),
    "required_checkbox": lambda r, v: (
        f"se fires si le delta d'ink du disque central (rayon {r.disc_ratio} du cote, "
        f"seuil d'ink {r.ink_threshold}) est sous {-v:+.2f}"),
    "signature": lambda r, v: (
        f"se fires si la plus grande composante ajoutee fait moins de {-v:.0f} px de "
        f"diagonale canonique" if r.signature_sensor == "components" else
        f"se fires si la zone porte moins de {-v:.2f}% d'ink ajoutee"),
    "expiry": lambda r, v: "se fires des que la date lue est depassee a l'clock choisie",
    "consistency": lambda r, v: (
        f"se fires si le pire jeton de la plus petite reading ressemble a moins de "
        f"{1 - v:.3f} au meilleur jeton de l'autre piece"),
    "forbidden_value": lambda r, v: (
        f"se fires si une suite de words ajoutes ressemble a plus de {v:.3f} a une value "
        f"interdite"),
    "cropped_page": lambda r, v: (
        f"se fires si plus de {v:.2%} de l'ink du blank sort du frame du scan"),
    "rotated_page": lambda r, v: (
        f"se fires si un quarter_turns de tour bat le quarter_turns d'origine de plus de {v:.3f} de "
        f"correlation"),
}


def reading_sentence(check, reg, value, defaut=""):
    """La phrase se REGENERE a chaque publication, from_dict le capteur reellement retenu.

    Une phrase reconduite telle quelle survit au capteur qu'elle decrit. C'est arrive ici:
    apres que la grid eut retenu l'ink pour les fields required, thresholds.json continuait de
    dire "moins de 1 caractere alphanumerique", et un lecteur pouvait croire que -0,345 etait
    un nombre de caracteres alors que c'est un pourcentage d'ink. Une unite fausse dans une
    phrase juste est plus dangereuse qu'une phrase absente.
    """
    f = PHRASES.get(check)
    return f(reg, value) if f else defaut


def _reglage_utile(reg, check):
    """Seulement les boutons qui agissent VRAIMENT sur le reglage retenu.

    Le capteur d'ink ignore la confiance OCR: la consigner a cote de lui ferait croire
    qu'elle a ete choisie alors qu'elle n'a rien decide.
    """
    noms = NUISANCES[check]
    if check == "required_field":
        noms = ("text_sensor", "ink_threshold") if reg.text_sensor == "ink" \
            else ("text_sensor", "min_conf")
    return {n: getattr(reg, n) for n in noms}


def _jsonable(v):
    """Les cellules sont des tuples (angle, dpi, jpeg, sigma): JSON ne veut pas de tels cles."""
    if isinstance(v, dict):
        return {(str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k):
                _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def settings_name(reg, check):
    if check == "required_field":
        return (f"text_sensor=ink, ink_threshold={reg.ink_threshold}"
                if reg.text_sensor == "ink"
                else f"text_sensor={reg.text_sensor}, min_conf={reg.min_conf}")
    noms = NUISANCES[check]
    return ", ".join(f"{n}={getattr(reg, n)}" for n in noms) or "aucun reglage"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesures", default=os.path.join(ROOT, "grid", "mesures", "mesures.jsonl"))
    ap.add_argument("--sortie", default=RESULTS)
    ap.add_argument("--checks", nargs="*", default=list(CHECKS))
    ap.add_argument("--publier", action="store_true",
                    help="ecrire LIMITES.md et thresholds.json a la racine du depot")
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)

    ref = load_reference()
    index = load(a.mesures)
    dossiers = complete_dossiers(index)
    cellules = {c[:4] for c in dossiers}
    print(f"{len(dossiers)} couples cell/seed complets, {len(cellules)} cellules distinctes")

    balayages = {}
    for check in a.checks:
        t = time.perf_counter()
        balayages[check] = sweep(dossiers, ref, check)
        print(f"  balayage {check:17s} {len(balayages[check]):3d} reglages, "
              f"{time.perf_counter() - t:5.1f}s", flush=True)

    domaine, essais = choose_domain(balayages, a.checks)
    retenus = {k: v for k, v in dossiers.items() if k[1] >= domaine}
    print(f"domaine nominal retenu: dpi >= {domaine} ({len(retenus)} couples). Essais: "
          + ", ".join(f"{d} dpi -> " + ("pas de donnees" if r is None else
                                        f"pire rappel {r:.3f}") for d, r in essais))
    if all((r or 0) < RECALL_FLOOR for _, r in essais):
        print(f"  AUCUN domaine ne tient le floor de {RECALL_FLOOR:.0%}: "
              "le domaine retenu est le moins mauvais, pas un domaine sur.")

    resultats = {}
    for check in a.checks:
        r = analyze_check(subgrid(balayages[check], lambda k: k[1] >= domaine),
                              check, a.sortie)
        if r is None:
            print(f"  {check:17s} AUCUNE mesure exploitable")
            continue
        r["domaine"] = domaine
        hors = subgrid(balayages[check], lambda k: k[1] < domaine)[r["reglage"]]
        r["hors_domaine"] = measure(hors, r["seuil"]) if hors else None
        resultats[check] = r
        v, c = r["validation"], r["calibration"]
        print(f"  {check:17s} {r['reglage_texte']:42s} seuil={r['seuil']:9.4g} "
              f"calib rappel={c['rappel']:.3f} fpr={c['fpr']:.4f} | "
              f"VALID rappel={v['rappel']:.3f} fpr={v['fpr']:.4f} | "
              f"hors domaine {len(r['tombees'])}/{r['n_cellules']}")

    if "resolution" in resultats:
        resultats["resolution"].update(operational_floor(resultats, domaine, retenus))
        r = remeasure(resultats["resolution"], resultats["resolution"]["seuil"])
        r["point"] = dict(r["validation"], seuil=r["seuil"],
                          **precisions(r["validation"]["rappel"], r["validation"]["fpr"]))
        print(f"  {'resolution':17s} seuil porte a {r['seuil']:.4g} = floor "
              f"{r['plancher_dpi']} dpi moins {r['marge_estimateur']:.1%} de marge "
              f"(erreur max mesuree de l'estimateur {r['erreur_max_estimateur']:.4%})")
    t = time.perf_counter()
    croise = crosstalk(retenus, ref, resultats)
    print(f"  crosstalk mesuree sur toute la grid en {time.perf_counter() - t:.0f}s")
    if not resultats:
        print("aucun check exploitable, rien a plot")
        return 1
    plot(resultats, os.path.join(a.sortie, "courbes.png"))
    json.dump({c: {k: _jsonable(v) for k, v in r.items()
                   if k not in ("courbes", "reglage", "_classement", "_par_cellule")}
               for c, r in resultats.items()},
              open(os.path.join(a.sortie, "resume.json"), "w"), indent=2, default=str)
    write_duels(resultats, os.path.join(a.sortie, "duels.md"))
    json.dump(_jsonable(croise), open(os.path.join(a.sortie, "crosstalk.json"), "w"), indent=2)
    racine = ROOT if a.publier else a.sortie
    write_limits(resultats, os.path.join(racine, "LIMITES.md"), len(dossiers),
                   domaine, len(retenus), essais, croise)
    if a.publier:
        write_thresholds(resultats, os.path.join(ROOT, "thresholds.json"))
    print(f"-> {a.sortie}/courbes.png, {racine}/LIMITES.md, {a.sortie}/duels.md"
          + (", thresholds.json publie" if a.publier else ", thresholds.json NON publie (--publier)"))
    return 0


def duel_by_dpi(classement, check):
    """Le gagnant change-t-il selon le dpi. C'est la seule facon honnete de trancher un duel.

    Chaque concurrent est juge a SON propre point de fonctionnement (celui qui tient le budget
    de faux positifs), pas au seuil du voisin: comparer deux sensors a un seuil commun
    compare une scale, pas un capteur.
    """
    dpis = sorted({c[1] for _, pc, _, _ in classement for c in pc})
    lignes = []
    for reg, par_cellule, _, pt in classement:
        if pt is None:
            continue
        ligne = {"reglage": settings_name(reg, check), "seuil": pt["seuil"],
                 "global": (pt["rappel"], pt["fpr"])}
        for dpi in dpis:
            sous = {k: v for k, v in par_cellule.items() if k[1] == dpi}
            m = measure(sous, pt["seuil"])
            ligne[dpi] = (m["rappel"], m["fpr"], m["ic_rappel"])
        lignes.append(ligne)
    return dpis, sorted(lignes, key=lambda l: -l["global"][0])


def write_duels(resultats, chemin):
    lignes = ["# Duels entre sensors concurrents", "",
              "Chaque concurrent est juge a SON propre point de fonctionnement, celui qui tient",
              f"le budget de faux positifs de {FP_BUDGET:.1%}. Comparer deux sensors a un seuil",
              "commun comparerait une scale et pas un capteur. Les intervalles sont des",
              "intervalles de Wilson a 95%: a trois graines par cell, l'intervalle normal ment.",
              ""]
    for check in sorted(resultats):
        r = resultats[check]
        if not NUISANCES[check]:
            continue
        dpis, tab = duel_by_dpi(r["_classement"], check)
        if not tab:
            continue
        lignes += [f"## {check}", "",
                   "| reglage | seuil | rappel global | fpr global | "
                   + " | ".join(f"rappel {d} dpi" for d in dpis) + " |",
                   "|---|---|---|---|" + "---|" * len(dpis)]
        for l in tab:
            boxes = " | ".join(f"{l[d][0]:.3f} [{l[d][2][0]:.2f}, {l[d][2][1]:.2f}]" for d in dpis)
            marque = " **(retenu)**" if l["reglage"] == r["reglage_texte"] else ""
            lignes.append(f"| {l['reglage']}{marque} | {l['seuil']:.4g} | {l['global'][0]:.3f} "
                          f"| {l['global'][1]:.4f} | {boxes} |")
        # Depart a rappel egal par le taux de faux positifs, sinon le "gagnant" est
        # simplement le premier de la liste, ce qui ne veut rien dire.
        gagnants = {d: max(tab, key=lambda l: (l[d][0], -l[d][1]))["reglage"] for d in dpis}
        # Une egalite est un resultat, pas un vainqueur. Annoncer "capteur X gagne" quand
        # deux sensors rendent exactement les memes chiffres partout, c'est raconter une
        # mesure qui n'a pas eu lieu.
        tete = max(l["global"] for l in tab)
        exaequo = [l["reglage"] for l in tab if l["global"] == tete]
        if len(exaequo) > 1:
            lignes += ["", f"EGALITE, non departage: {len(exaequo)} reglages rendent exactement "
                       f"le meme rappel ({tete[0]:.3f}) et le meme taux de faux positifs "
                       f"({tete[1]:.4f}) sur l'ensemble du domaine. Ce corpus et cette grid ne "
                       "les distinguent pas. Le reglage retenu est le premier de la liste, et ce "
                       "choix n'est appuye par aucune mesure: "
                       + ", ".join(exaequo[:4]) + "."]
        elif len(set(gagnants.values())) > 1:
            lignes += ["", "Le gagnant CHANGE selon le dpi: "
                       + ", ".join(f"{d} dpi -> {g}" for d, g in gagnants.items())
                       + ". Le reglage retenu est celui qui tient le mieux sur l'ensemble du "
                         "domaine, pas celui qui gagne une colonne."]
        else:
            lignes += ["", f"Meme gagnant a tous les dpi: {next(iter(gagnants.values()))}."]
        lignes.append("")
    open(chemin, "w", encoding="utf-8").write("\n".join(lignes) + "\n")


def write_limits(resultats, chemin, n_couples, domaine, n_retenus, essais, croise=None):
    l = ["# Limites: ou cet outil cesse de marcher", "",
         "Un outil qui ne dit pas ou il cesse de marcher n'est pas mesure, il est raconte.",
         "",
         f"## Domaine nominal: numerisation a {domaine} dpi ou plus", "",
         f"Les points de fonctionnement sont choisis sur les {n_retenus} couples de ce domaine,",
         f"pas sur les {n_couples} de la grid entiere. Ce n'est pas une facon de se donner de",
         "beaux chiffres, c'est une consequence mecanique: un dossier est refuse des qu'UN field",
         "required est vide, donc le score du dossier est celui de son PIRE field. Sous le",
         "floor, le Cerfa a des fields que l'OCR ne lit pas, le dossier SAIN atteint alors le",
         "meme score que le dossier fautif, et aucun seuil ne les separe plus. Le point de",
         "fonctionnement reculerait jusqu'a ne plus rien declencher du tout.",
         "",
         "Sous ce floor l'outil ne devine pas: le check de resolution se fires et dit",
         "qu'il ne sait pas read_piece la page. Chaque section ci-dessous donne aussi ce que le",
         "check fait HORS domaine, parce que le cacher serait le mentir.",
         "",
         "Domaines essayes, du plus large au plus etroit, avec le pire rappel des checks",
         "qui dependent de l'OCR: "
         + ", ".join(f"dpi >= {d} -> "
                     + ("pas de donnees" if r is None else f"{r:.3f}") for d, r in essais)
         + ".",
         "",
         f"Mesure sur {n_couples} couples cell/seed: angle (0, 0.25, 0.5, 1, 2, 4 deg) x",
         "dpi (96, 150, 200, 300) x qualite JPEG (30, 55, 75, 95) x bruit sigma (0, 3, 6, 12),",
         "trois graines par cell. Chaque check est evalue a son point de fonctionnement,",
         f"choisi comme le rappel le plus haut tenant un taux de faux positifs sous "
         f"{FP_BUDGET:.1%}.",
         "",
         "Le seuil est choisi sur les graines 11 et 23, et le chiffre publie est celui de la",
         f"seed {VALIDATION_SEED}, jamais regardee avant. Choisir un seuil et rapporter son",
         "rappel sur les memes tirages le surestime toujours.",
         "",
         "Une cell est declaree HORS DOMAINE quand le rappel y passe sous "
         f"{RECALL_FLOOR:.0%}.", "",
         "## Ce que la mesure ne couvre pas", "",
         "- Un seul jeu de trois formulaires (W-9, I-9, Cerfa 14011). Les chiffres ne se",
         "  transportent pas tels quels sur un formulaire dont la typographie ou l'encadrement",
         "  des fields differe. Le Cerfa, dont les fields sont encadres case par case, est deja",
         "  nettement plus dur que les deux formulaires americains.",
         "- Les words ne sont enregistres que dans les zones DECLAREES par l'AcroForm, dilatees",
         "  de 8 px. Une value interdite qui reapparaitrait hors de tout field declare, dans une",
         "  mention manuscrite en marge par exemple, ne serait pas vue.",
         "- Un formulaire sans AcroForm est hors de portee: toute la geometry vient de la",
         "  declaration du PDF, rien n'est mesure a la main.",
         "- Les degradations sont SYNTHETIQUES. Un vrai scanner ajoute des artefacts que cette",
         "  grid n'imite pas: courbure de page, ombre de reliure, poussiere sur la vitre,",
         "  moire de retramage. La grid borne le domaine, elle ne le prouve pas.",
         "- CONSEQUENCE DIRECTE SUR LE CAPTEUR D'ENCRE, et elle n'est plus une hypothese:",
         "  aucune degradation de cette grid n'AJOUTE d'ink etrangere dans une zone, et le",
         "  capteur retenu pour les fields required gagne donc son duel sur un terrain qui lui",
         "  est favorable. Une sonde de 528 readings a mis des le 2026-08-21 un chiffre sur ce",
         "  que ce terrain cachait (sonde-ink-parasite/CONSTAT-ENCRE-PARASITE.md): des qu'au",
         "  moins 0,5% d'ink etrangere entre dans la zone, ce capteur declare REMPLI un field",
         "  VIDE dans 1,000 des cas [0,975, 1,000] sur n=151, contre 0,272 pour l'union des",
         "  sensors de words, 0,185 pleine page et 0,106 en zone. Ce sont des faux negatifs, le",
         "  cote cher de l'asymetrie. La bascule est une falaise posee sur le seuil publie de",
         "  0,345%, et les deux populations ne se chevauchent pas d'une seule reading: le",
         "  capteur se fires 97 fois sur 97 jusqu'a 0,323% d'ink ajoutee et 0 fois sur",
         "  167 a partir de 0,380%. Pas de zone grise, une marche. Pour ce field, 0,35% vaut",
         "  une tache de 9 x 8 px a 200 dpi, une poussiere sur la vitre; un trait de stylo qui",
         "  deborde a peine du field voisin ajoute deja 0,61%.",
         "  LE CAPTEUR ET LE SEUIL N'ONT PAS ETE CHANGES, et c'est la bonne decision tant que",
         "  la mesure est une sonde: un field, deux cellules, trois formes de parasite. Elle",
         "  montre qu'un choix a ete tranche sur un terrain biaise, elle ne suffit pas a fixer",
         "  un seuil. Le changer demande de rejouer cette grid avec l'ink parasite en",
         "  CINQUIEME FACTEUR, et c'est le premier chantier de mesure qui reste ouvert.",
         "- La precision depend de la prevalence. Les courbes la donnent a "
         f"{PREVALENCE:.0%} de dossiers fautifs, value SUPPOSEE et non mesuree.",
         ""]
    suivi = os.path.join(ROOT, "grid", "resultats", "suivi.json")
    if os.path.exists(suivi):
        d = json.load(open(suivi))
        c, t, cu = d["jeux"]["coin"], d["jeux"]["temoin"], d["cumule"]
        co = d["coin"]
        l += ["## Suivi hors protocole: la seule cell ou l'outil manque quelque chose", "",
              "HORS PROTOCOLE, et il faut le dire avant les chiffres. Les thresholds publies sortent",
              "d'une regle stricte: deux graines calibrent, la troisieme n'est jamais regardee",
              "avant que le chiffre soit ecrit. Les graines de ce suivi ont ete tirees APRES",
              "avoir vu ou l'outil manquait, sur une cell choisie parce qu'elle manquait.",
              "Elles ne deplacent aucun seuil et n'entrent dans aucun chiffre publie ailleurs.",
              "Elles repondent a une seule question: n=18 suffisait-il pour conclure.", "",
              f"Cellule: {co['dpi']} dpi, JPEG {co['jpeg']}, bruit sigma {co['sigma']}, check "
              f"{d['check']}, seuil publie {d['seuil']}.", "",
              "| jeu | rappel | IC 95% | positifs |",
              "|---|---|---|---|",
              f"| graines d'origine (11, 23, 37) | {d['jeux']['origine']['rappel']:.4f} | "
              f"[{d['jeux']['origine']['ic'][0]:.3f}, {d['jeux']['origine']['ic'][1]:.3f}] | "
              f"{d['jeux']['origine']['n']} |",
              f"| 12 graines neuves | {c['rappel']:.4f} | [{c['ic'][0]:.3f}, "
              f"{c['ic'][1]:.3f}] | {c['n']} |",
              f"| CUMULE | {cu['rappel']:.4f} | [{cu['ic'][0]:.3f}, {cu['ic'][1]:.3f}] | "
              f"{cu['n']} |", "",
              f"Le point estime remonte de {d['jeux']['origine']['rappel']:.3f} a "
              f"{cu['rappel']:.3f}, retour a la moyenne attendu d'un n=18, mais la borne HAUTE",
              f"reste a {cu['ic'][1]:.3f}, sous le floor de {RECALL_FLOOR:.0%}. Ce n'est",
              "pas du bruit d'echantillon: le check manque vraiment quelque chose ici.", "",
              "TEMOIN, et c'est lui qui rend les douze graines interpretables. Meme cell,",
              "memes douze graines, seule la compression change:", "",
              f"- JPEG {co['jpeg']}: {c['tp']}/{c['n']} = {c['rappel']:.4f}",
              f"- JPEG 30: {t['tp']}/{t['n']} = {t['rappel']:.4f}", "",
              "Les graines neuves ne sont donc pas plus dures, c'est la compression. Une",
              "compression FORTE efface le grain du capteur; une compression legere le garde, et",
              "a haute resolution ce grain est assez fin pour se faire read_piece comme de la",
              "structure de caractere. Cette partie du mecanisme est MESUREE.", "",
              "LA FORME REELLE EST UNE CONJONCTION DE QUATRE FACTEURS, pas de deux:", "",
              f"- angle sous {cu['marche_angle']} deg: {cu['angle_sous_marche'][0]}/"
              f"{cu['angle_sous_marche'][1]} = {cu['angle_sous_marche'][2]:.4f}",
              f"- angle a {cu['marche_angle']} deg ou plus: {cu['angle_sur_marche'][0]}/"
              f"{cu['angle_sur_marche'][1]} = {cu['angle_sur_marche'][2]:.4f}", "",
              "Une marche, pas une pente. La cell fautive est donc "
              f"{co['dpi']} dpi ET JPEG {co['jpeg']} ET",
              f"bruit {co['sigma']} ET angle >= {cu['marche_angle']} deg. Le balayage a deux",
              "facteurs ci-dessous ne peut pas la voir telle quelle: chaque paire moyenne sur",
              "les deux facteurs restants, donc elle n'en montre que l'ombre. Il sert a la",
              "TROUVER; c'est la liste des pires cellules, qui est deja a quatre facteurs, qui",
              "la NOMME.", "",
              "Reserve sur le mecanisme: la partie compression est mesuree par le temoin, la",
              "partie angle est SUPPOSEE. L'hypothese est que c'est l'ampleur du",
              "reechantillonnage qui compte et non sa presence, un deskew au-dela d'un",
              "demi-degre etalant le grain fin dans l'epaisseur des traits. Elle n'est pas",
              "testee. Le deskew applique bien une rotation bicubique des 0,25 deg aussi,",
              "donc l'explication paresseuse (pas de reechantillonnage sous 0,5 deg) est fausse.",
              "", "Reproduire: `python3 grid/corner_followup.py`.", ""]

    if croise:
        noms = [v.name for v in VARIANTS if v.check]
        l += ["## Diaphonie: qui crie sur le defaut du voisin", "",
              "Chaque case donne la part des dossiers ou le check de la LIGNE se fires",
              "alors que le defaut injecte appartient a la COLONNE. La diagonale est vide par",
              "construction. Toutes les boxes ne sont pas des fautes: une page rognee emporte de",
              "vrais fields, donc le check des fields required a raison d'y crier. Ce tableau",
              "sert a split la consequence physique de la contamination.", "",
              "Une LIGNE UNIFORME n'est pas de la crosstalk: c'est le taux de fond du check",
              "qui reapparait. Les variantes partagent les pieces qu'elles n'abiment pas, donc",
              "un check qui se fires a x% sur un dossier clean se fires a x% sur",
              "toutes les colonnes. Ce qui se lit ici, ce sont les boxes qui DEPASSENT la ligne.",
              "",
              "| check \\ defaut | " + " | ".join(n[:14] for n in noms) + " |",
              "|---|" + "---|" * len(noms)]
        for check in sorted(croise):
            boxes = []
            for n in noms:
                d = croise[check].get(n)
                boxes.append("." if d is None else
                             ("." if d["taux"] == 0 else f"{d['taux']:.3f}"))
            l.append(f"| {check} | " + " | ".join(boxes) + " |")
        l += ["", "Un point vaut zero declenchement sur "
              f"{next(iter(next(iter(croise.values())).values()))['n']} dossiers.", ""]

    for check in sorted(resultats):
        r = resultats[check]
        pt = r["point"]
        l += [f"## {check}", ""]
        if pt is None:
            l += ["Aucune mesure exploitable pour ce check.", ""]
            continue
        if r["validation"]["rappel"] < RECALL_FLOOR:
            l += [f"ATTENTION: sous le budget de faux positifs de {FP_BUDGET:.1%}, le meilleur",
                  f"rappel atteignable est {r['validation']['rappel']:.3f}, sous le floor de",
                  f"{RECALL_FLOOR:.0%}. Ce check laisse passer des dossiers fautifs plus",
                  "souvent qu'il ne devrait: il ne doit pas etre presente comme une garantie.", ""]
        c, v, e = r["calibration"], r["validation"], r["ensemble"]
        l += [f"Reglage retenu: {r['reglage_texte']}. Seuil {r['seuil']:.4g}.", "",
              "| jeu | rappel | IC 95% | faux positifs par target | IC 95% | "
              "par dossier clean | positifs |",
              "|---|---|---|---|---|---|---|"]
        for etiquette, m in (("calibration (graines 11 et 23)", c),
                             ("VALIDATION (seed 37, jamais vue)", v), ("ensemble", e)):
            l.append(f"| {etiquette} | {m['rappel']:.3f} | [{m['ic_rappel'][0]:.3f}, "
                     f"{m['ic_rappel'][1]:.3f}] | {m['fpr']:.4f} | [{m['ic_fpr'][0]:.4f}, "
                     f"{m['ic_fpr'][1]:.4f}] | {m['fpr_dossier']:.4f} | {m['n_pos']} |")
        l += ["",
              "Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au",
              "moins une alarme parte sur un dossier entierement clean. C'est lui qui decide si",
              "la gate reste credible.", "",
              f"Cellules sous le floor: {len(r['tombees'])} sur {r['n_cellules']}.", ""]
        nc = r.get("cibles_non_certifiables") or []
        if nc:
            l += ["Cibles qui plafonnent ce check, avec la part des dossiers SAINS ou elles",
                  "se declenchent au seuil qu'il faudrait pour ne rien manquer:", ""]
            for name, taux in nc:
                l.append(f"- {name}: {taux:.1%}")
            l += ["", "Sur ces cibles, la bonne reponse de l'outil n'est pas \"ce field est",
                  "vide\" mais \"je ne sais pas read_piece ce field\": meme capteur, consequences",
                  "opposees au filing. Elles restent dans le chiffre de tete ci-dessus, elles",
                  "ne sont pas retirees pour l'embellir.", ""]
        rr = r.get("restreint")
        if rr:
            l += [f"Chiffre SECONDAIRE, a ne pas confondre avec celui de tete: si on ne demande",
                  f"a ce check que les {rr['cibles_gardees']} cibles sur "
                  f"{rr['cibles_totales']} qu'il sait certifier, il tient un rappel de "
                  f"{rr['rappel']:.3f} a {rr['fpr']:.4f} de faux positifs par target.", ""]
        conj = r.get("conjonctions") or {}
        pires = sorted(((k, c[0]) for k, c in conj.items() if c), key=lambda t: t[1]["rappel"])
        if pires and pires[0][1]["rappel"] < 1.0:
            l += ["Pires CROISEMENTS de deux facteurs. Une reading axe par axe peut mentir par",
                  "omission: trois valeurs marginales toutes au-dessus du floor peuvent se",
                  "croiser en une cell qui passe dessous.", ""]
            for name, c in pires[:4]:
                if c["rappel"] >= 1.0:
                    continue
                l.append(f"- {name} = {c['valeurs']}: rappel {c['rappel']:.3f} "
                         f"[{c['ic'][0]:.3f}, {c['ic'][1]:.3f}] sur {c['n']} positifs"
                         + ("  <- borne haute sous le floor"
                            if c["ic"][1] < RECALL_FLOOR else ""))
            l.append("")
        cf = r.get("noisy_targets") or []
        if cf:
            l += ["Cibles saines qui se declenchent AU SEUIL RETENU, celles qui coutent la "
                  "credibilite:", ""]
            for target, combien, total in cf[:6]:
                l.append(f"- {target[0]} / {target[1]}: {combien} fois sur {total}")
            l.append("")
        h = r.get("hors_domaine")
        if h and h["n_pos"]:
            l += [f"Hors domaine (dpi < {r['domaine']}), CAPTEURS BRUTS, c'est-a-dire ce que "
                  "l'outil ferait",
                  "s'il n'avait pas la regle d'abstention: rappel "
                  f"{h['rappel']:.3f} [{h['ic_rappel'][0]:.3f}, {h['ic_rappel'][1]:.3f}], "
                  f"declenchements sur dossier clean {h['fpr']:.4f} sur {h['n_neg']} cibles.",
                  "Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: "
                  "en",
                  "production, un check qui LIT s'abstient sous le floor au lieu de "
                  "produire",
                  "ce qu'on lit ici. Ils sont mesures sensors bruts a dessein, parce qu'une "
                  "mesure",
                  "ne peut pas dependre du comportement qu'elle sert a regler.", ""]
            if check == "resolution":
                l += ["Pour CE check, ces declenchements hors domaine ne sont pas des faux",
                      "positifs: c'est exactement son task. Il est la pour dire qu'une page",
                      "numerisee sous le floor ne doit pas etre jugee par les autres.", ""]
        if r["tombees"]:
            l += ["Frontiere par facteur, nombre de cellules tombees sur le total:", ""]
            for name, vals in r["frontier"].items():
                l.append("- " + name + ": " + ", ".join(f"{v} -> {a}/{b}" for v, (a, b) in vals.items()))
            l.append("")
            pires = sorted(r["tombees"].items(), key=lambda kv: kv[1][0])[:6]
            l += ["Les pires cellules (angle, dpi, jpeg, sigma) et leur rappel:", ""]
            for c, (rap, n) in pires:
                l.append(f"- angle {c[0]}, {c[1]} dpi, JPEG {c[2]}, sigma {c[3]}: "
                         f"rappel {rap:.2f} sur {n} graines")
            l.append("")
        else:
            l += ["Aucune cell du domaine explore ne passe sous le floor.", ""]
        l += ["Rappel par facteur, au seuil retenu:", ""]
        for name, vals in r["facteurs"].items():
            l.append("- " + name + ": " + ", ".join(
                f"{v} -> {d['rappel']:.3f} [{d['ic'][0]:.2f}, {d['ic'][1]:.2f}]"
                for v, d in vals.items()))
        l.append("")
    open(chemin, "w", encoding="utf-8").write("\n".join(l) + "\n")


def write_thresholds(resultats, chemin):
    d = json.load(open(chemin, encoding="utf-8"))
    for check, r in resultats.items():
        pt = r["point"]
        if pt is None:
            continue
        mesures = {
            "rappel": round(r["validation"]["rappel"], 4),
            "faux_positifs": round(r["validation"]["fpr"], 5),
            "mesure_sur": "seed 37, jamais utilisee pour choisir le seuil",
            "reglage": r["reglage_texte"],
            "reglage_mesure": _reglage_utile(r["reglage"], check),
            "curve": f"grid/resultats/pr_{check}.csv",
            "cellules_hors_domaine": f"{len(r['tombees'])}/{r['n_cellules']}",
            "domaine_nominal_dpi": r.get("domaine"),
        }
        if r.get("seuil_fige_par_definition"):
            d["thresholds"][check].update(mesures)
            d["thresholds"][check]["reading"] = reading_sentence(
                check, r["reglage"], float(r["seuil"]),
                d["thresholds"][check].get("reading", ""))
            continue
        d["thresholds"][check] = {
            "value": round(float(r["seuil"]), 4),
            "origine": "grid",
            "reading": reading_sentence(check, r["reglage"], float(r["seuil"]),
                                      d["thresholds"].get(check, {}).get("reading", "")),
            "reglage": r["reglage_texte"],
            "reglage_mesure": _reglage_utile(r["reglage"], check),
            "rappel": round(r["validation"]["rappel"], 4),
            "faux_positifs": round(r["validation"]["fpr"], 5),
            "mesure_sur": "seed 37, jamais utilisee pour choisir le seuil",
            "curve": f"grid/resultats/pr_{check}.csv",
            "cellules_hors_domaine": f"{len(r['tombees'])}/{r['n_cellules']}",
            "domaine_nominal_dpi": r.get("domaine"),
        }
        if "plancher_dpi" in r:
            d["thresholds"][check].update({
                "value": round(float(r["seuil"]), 4),
                "reading": f"se fires sous {-r['seuil']:.1f} dpi estimes, soit le floor "
                           f"de {r['plancher_dpi']} dpi moins une marge de "
                           f"{r['marge_estimateur']:.1%}; le floor est lu sur le rappel des "
                           "checks qui dependent de l'OCR et non sur la curve de ce "
                           "check, et la marge couvre dix fois l'erreur maximale mesuree de "
                           f"l'estimateur ({r['erreur_max_estimateur']:.4%})",
                "seuil_de_sa_propre_courbe": r["seuil_courbe_propre"],
                "rappel_par_dpi_des_dependants": r["rappel_par_dpi_des_dependants"]})
    d["mesure_le"] = "2026-08-21"
    d["budget_faux_positifs"] = FP_BUDGET
    json.dump(d, open(chemin, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
