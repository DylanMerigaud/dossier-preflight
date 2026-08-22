#!/usr/bin/env python3
"""Lire les seuils SUR les courbes, pas les choisir a la main.

Entree: les mesures brutes de la grille. Sortie: une courbe precision/rappel par controle, le
point de fonctionnement retenu, le plancher de panne, et les tableaux des duels A/B.

L'ASYMETRIE EST DECLAREE ICI, EN CHIFFRES, parce qu'un point de fonctionnement choisi sans
elle est choisi au hasard:

  un FAUX NEGATIF, c'est le guichet qui refuse le dossier. Des mois de delai, une convocation
  a reprendre, parfois une piece a redemander a une administration etrangere.
  un FAUX POSITIF, c'est la gate qui crie sur un dossier sain. Il ne coute pas un delai, il
  coute la CREDIBILITE de la gate, et une regle qui crie au loup fait survoler toutes celles
  d'a cote. C'est le seul cout qui detruit l'outil au lieu de le degrader.

D'ou la regle: on prend le RAPPEL LE PLUS HAUT ATTEIGNABLE sous un budget de faux positifs
tenu, et le budget est ecrit noir sur blanc (BUDGET_FP), pas suppose. Il est par controle et
par dossier: avec neuf controles, un dossier sain a environ 9 fois ce budget de chance de
declencher une alarme pour rien, et ce chiffre-la est celui que l'utilisateur ressent.

    python3 grille/analyser.py
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

from preflight.capteurs import PARTS_DISQUE, SEUILS_ENCRE
from preflight.controles import CONTROLES, NUISANCES, Reglages, evaluer
from preflight.fixtures import PAR_NOM, VARIANTES
from preflight.lecture import Lecture
from preflight.referentiel import charger_referentiel

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTATS = os.path.join(RACINE, "grille", "resultats")

# Budget de faux positifs PAR CIBLE (un champ, une case, une valeur interdite), et non par
# dossier. Un dossier porte dix-sept champs requis: le taux qu'un utilisateur RESSENT est
# celui du dossier entier, environ dix-sept fois celui-ci, et il est mesure puis publie a
# part sous le nom de taux par dossier. Declarer l'un en croyant parler de l'autre est la
# facon la plus courante d'annoncer une gate plus sure qu'elle n'est.
BUDGET_FP = 0.002
GRAINE_VALIDATION = 37     # jamais regardee pour choisir un seuil, uniquement pour le rapporter
RAPPEL_PLANCHER = 0.95     # sous ce rappel, la cellule est declaree hors domaine
PREVALENCE = 0.10          # part supposee de dossiers reellement fautifs, pour la precision

# Balaye jusqu'a 0. Un champ PEIGNE (une case par caractere, le formulaire le declare) se lit
# "4/1)2" avec une confiance de 38: les trois chiffres sont bien la, mais les separateurs
# cassent le modele de mot de tesseract et effondrent sa confiance. Un plancher a 40 jetterait
# un champ REMPLI, c'est-a-dire fabriquerait un faux positif sur un dossier sain, du cote qui
# detruit la credibilite de la gate. La confiance etant appliquee a l'ANALYSE et non a la
# grille, l'elargir ne coute pas une seule image.
CONF_MINS = (0.0, 10.0, 20.0, 40.0, 60.0, 80.0)
CAPTEURS_TEXTE = ("page", "zone", "union")
CAPTEURS_SIGNATURE = ("composantes", "encre")

VALEURS = {"conf_min": CONF_MINS, "capteur_texte": CAPTEURS_TEXTE,
           "part_disque": PARTS_DISQUE, "seuil_encre": SEUILS_ENCRE,
           "capteur_signature": CAPTEURS_SIGNATURE}

MOINS_INF = -1e18


def combinaisons(controle):
    """Les reglages qui changent quelque chose POUR CE CONTROLE, et eux seuls.

    Le controle des champs requis est le seul a croiser deux familles de capteurs qui n'ont
    pas les memes boutons: la confiance OCR ne veut rien dire pour un capteur d'encre, et le
    seuil d'encre ne veut rien dire pour un capteur de mots. Les croiser quand meme
    multiplierait par six un balayage deja long sans produire un seul point de plus.
    """
    if controle == "champ_requis":
        return ([Reglages(capteur_texte=t, conf_min=c)
                 for t in CAPTEURS_TEXTE for c in CONF_MINS]
                + [Reglages(capteur_texte="encre", seuil_encre=e) for e in SEUILS_ENCRE])
    noms = NUISANCES[controle]
    if not noms:
        return [Reglages()]
    return [Reglages(**dict(zip(noms, v)))
            for v in itertools.product(*[VALEURS[n] for n in noms])]


def charger(chemin):
    """index[(angle, dpi, jpeg, sigma, graine)][variante][piece] = Lecture"""
    index = collections.defaultdict(lambda: collections.defaultdict(dict))
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            d = json.loads(ligne)
            cle = (d["angle"], d["dpi"], d["jpeg"], d["sigma"], d["graine"])
            index[cle][d["variante"]][d["piece"]] = Lecture.depuis(d["lecture"])
    return index


def dossiers_complets(index):
    """Un dossier de variante = la piece modifiee, plus les deux pieces du dossier sain.

    Les cellules incompletes sont ecartees en silence: la grille reprend ou elle s'arrete, et
    une cellule a moitie ecrite fabriquerait un faux negatif qui n'existe pas.
    """
    attendues = {v.nom for v in VARIANTES}
    out = {}
    for cle, par_var in index.items():
        if not attendues <= set(par_var):
            continue
        sain = par_var["sain"]
        if len(sain) < 3:
            continue
        d = {"sain": sain}
        for v in VARIANTES:
            if v.controle:
                d[v.nom] = dict(sain, **par_var[v.nom])
        out[cle] = d
    return out


def scores_cibles(lectures, ref, controle, reg, horloge="guichet", abstention=False):
    """Le score de CHAQUE cible du controle: un champ, une case, une valeur interdite.

    C'est la bonne unite de mesure, et le choisir change le resultat. Roule au niveau du
    dossier, le controle des champs requis n'a que deux points de fonctionnement possibles
    (crier des qu'un champ sur dix-sept est illisible, ou ne jamais crier) parce que son score
    est le PIRE de ses champs. Par cible, la courbe existe vraiment, les negatifs sont
    dix-sept fois plus nombreux donc le taux de faux positifs est mesurable, et surtout on
    peut dire QUEL champ n'est pas certifiable au lieu de condamner le controle entier.
    """
    return {(c.piece, str(c.cible)): c.score
            for c in evaluer(lectures, ref, horloge, reg, controles=[controle],
                             abstention=abstention)
            if c.score is not None}


def score_dossier(lectures, ref, controle, reg, horloge="guichet"):
    """Le pire constat du dossier. Un dossier est refuse des qu'UNE piece cloche."""
    return max(scores_cibles(lectures, ref, controle, reg, horloge).values(), default=MOINS_INF)


def cibles_atteintes(var, ref):
    """Ce que la variante abime VRAIMENT, declare et pas devine.

    Sans cette liste, la classe positive serait "tout le dossier fautif" et les seize champs
    intacts qu'il porte compteraient comme des positifs manques.
    """
    if not var.controle:
        return set()
    gab = ref.gabarits[dict(ref.pieces)[var.piece]] if var.piece else None
    if var.vider:
        return {(var.piece, c) for role in var.vider for c in gab.champ(role)}
    if var.decocher:
        return {(var.piece, gab.cases[role]) for role in var.decocher}
    if var.sans_signature:
        return {(var.piece, c) for c in gab.signatures.values()}
    if var.date_perimee:
        return {(var.piece, c) for role, genre in gab.dates.items() if genre == "expiration"
                for c in gab.champ(role)}
    if var.controle == "valeur_interdite":
        injectees = {str(v) for v in var.remplacer.values()}
        return {(var.piece, v) for v in ref.valeurs_interdites if v in injectees}
    if var.controle == "coherence":
        return {(f"{a['piece']}+{b['piece']}", coh["donnee"])
                for coh in ref.coherences
                for a, b in itertools.combinations(coh["lectures"], 2)}
    return {(var.piece, "")}          # resolution, page coupee, page tournee


def wilson(succes, n, z=1.96):
    """Intervalle de Wilson. A n=3 graines par cellule, l'intervalle normal ment."""
    if n == 0:
        return (0.0, 1.0)
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def courbe(pos, neg):
    """Tous les points de fonctionnement, du plus laxiste au plus strict.

    Les seuils candidats sont les scores OBSERVES: entre deux scores voisins, aucun seuil ne
    change quoi que ce soit, et en inventer d'autres ne ferait qu'epaissir le fichier.
    """
    seuils = sorted({s for s in list(pos) + list(neg) if s > MOINS_INF})
    if not seuils:
        return []
    marges = [seuils[0] - 1.0]
    marges += [(a + b) / 2 for a, b in zip(seuils, seuils[1:])]
    marges += [seuils[-1] + 1.0]
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
    """Precision a la composition de la grille (un fautif pour un sain) et a la prevalence
    supposee. La seconde est celle qui compte, et elle est plus severe."""
    num = PREVALENCE * rappel
    return {"precision_grille": rappel / (rappel + fpr) if (rappel + fpr) else 1.0,
            "precision_prevalence": num / (num + (1 - PREVALENCE) * fpr)
            if (num + (1 - PREVALENCE) * fpr) else 1.0}


def point_retenu(pts, budget=BUDGET_FP):
    """Le rappel le plus haut sous le budget de faux positifs. Rien de plus, rien de moins.

    Il existe TOUJOURS un point sous n'importe quel budget: celui qui ne declenche jamais, a
    rappel nul. Ce n'est donc jamais l'absence de point qui signale un controle inutilisable,
    c'est un rappel trop bas au point retenu, et c'est ce que LIMITES.md doit dire.
    """
    if not pts:
        return None
    tenables = [p for p in pts if p["fpr"] <= budget]
    if not tenables:
        return None
    meilleur = max(tenables, key=lambda p: (p["rappel"], -p["fpr"]))
    # A rappel egal, on prend le seuil le plus au milieu du palier: un seuil colle contre une
    # valeur observee bascule au premier pixel de bruit d'une mesure future.
    palier = [p for p in tenables
              if p["rappel"] == meilleur["rappel"] and p["fpr"] == meilleur["fpr"]]
    return palier[len(palier) // 2]


def balayer(dossiers, ref, controle):
    """Pour chaque reglage, les scores par cible, cellule par cellule.

    Retour: {reglage: {cle_cellule: {"pos": {cible: score}, "neg": {cible: score}}}}
    Les positifs sont les cibles que la variante abime; les negatifs sont TOUTES les cibles du
    dossier sain, ce qui donne au taux de faux positifs la puissance qui lui manquait.
    """
    var = next(v for v in VARIANTES if v.controle == controle)
    cibles = cibles_atteintes(var, ref)
    out = {}
    for reg in combinaisons(controle):
        par_cellule = {}
        for cle, d in dossiers.items():
            tous = scores_cibles(d[var.nom], ref, controle, reg)
            pos = {k: v for k, v in tous.items() if k in cibles} or tous
            par_cellule[cle] = {"pos": pos,
                                "neg": scores_cibles(d["sain"], ref, controle, reg)}
        out[reg] = par_cellule
    return out


def aplatir(par_cellule):
    pos = [x for v in par_cellule.values() for x in v["pos"].values()]
    neg = [x for v in par_cellule.values() for x in v["neg"].values()]
    return pos, neg


def separer(par_cellule):
    """Calibration contre validation.

    Choisir un seuil sur des donnees puis rapporter son rappel sur les MEMES donnees le
    surestime toujours: le seuil s'est loge dans le bruit de ces tirages-la. Deux graines
    calibrent, la troisieme n'est jamais regardee avant d'ecrire le chiffre.
    """
    cal = {k: v for k, v in par_cellule.items() if k[4] != GRAINE_VALIDATION}
    val = {k: v for k, v in par_cellule.items() if k[4] == GRAINE_VALIDATION}
    return cal, val


def mesurer(par_cellule, seuil):
    """Deux taux de faux positifs, et il faut les deux.

    Par cible: la probabilite qu'UN champ sain soit declare vide. C'est celui sur lequel le
    seuil se choisit, parce que c'est la decision elementaire.
    Par dossier: la probabilite qu'AU MOINS UNE alarme parte sur un dossier entierement sain.
    C'est celui que l'utilisateur ressent, et c'est lui qui decide s'il continue de croire la
    gate. Le second est environ le premier multiplie par le nombre de cibles.
    """
    pos, neg = aplatir(par_cellule)
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


def certifiabilite(par_cellule):
    """Quelles cibles l'outil peut certifier, et lesquelles il doit refuser de juger.

    CE CALCUL NE TOUCHE PAS AU POINT DE FONCTIONNEMENT, et il a fallu une erreur pour le
    comprendre. En excluant les cibles genantes AVANT de choisir le seuil, on cree une boucle:
    moins de negatifs, donc un seuil plus permissif tenable, donc un rappel de 100% affiche sur
    la seule cible survivante. Sur le controle des valeurs interdites, cette boucle sortait un
    seuil de 0,11 de ressemblance, valeur a laquelle n'importe quoi ressemble a n'importe quoi,
    avec cinq cibles sur six exclues et un score parfait. C'etait du maquillage.

    Le seuil se choisit donc sur TOUTES les cibles. Ce calcul-ci ne sert qu'a EXPLIQUER le
    chiffre obtenu: quand un controle plafonne, c'est presque toujours deux ou trois champs qui
    le plafonnent, et les nommer vaut mieux que condamner le controle entier. Ce qu'un tel
    champ appelle, c'est que l'outil y reponde "je ne sais pas lire ce champ" au lieu de "ce
    champ est vide": meme capteur, consequences opposees au guichet.
    """
    pos, _ = aplatir(par_cellule)
    if not pos:
        return {}, {}
    ordonnes = sorted(pos)
    plein = ordonnes[min(len(ordonnes) - 1,
                         int(round((1 - RAPPEL_PLANCHER) * len(ordonnes))))] - 1e-9
    compte, vus = collections.Counter(), collections.Counter()
    for v in par_cellule.values():
        for cible, score in v["neg"].items():
            vus[cible] += 1
            if score > plein:
                compte[cible] += 1
    taux = {c: compte[c] / vus[c] for c in vus}
    return ({c: t for c, t in taux.items() if t <= BUDGET_FP},
            {c: t for c, t in sorted(taux.items(), key=lambda kv: -kv[1]) if t > BUDGET_FP})


def restreint_aux_certifiables(par_cellule, gardees, controle):
    """Chiffre SECONDAIRE et etiquete comme tel: ce que le controle vaut si on ne lui demande
    que les cibles qu'il sait certifier. Jamais le chiffre de tete, jamais dans seuils.json."""
    if not gardees or len(gardees) == len(next(iter(par_cellule.values()))["neg"]):
        return None
    sous = restreindre(par_cellule, gardees)
    cal, val = separer(sous)
    pos, neg = aplatir(cal)
    pt = point_retenu(courbe(pos, neg))
    if pt is None:
        return None
    m = mesurer(val, pt["seuil"])
    m["cibles_gardees"] = len(gardees)
    m["cibles_totales"] = len(next(iter(par_cellule.values()))["neg"])
    return m


def restreindre(par_cellule, gardees):
    return {cle: {"pos": v["pos"],
                  "neg": {k: x for k, x in v["neg"].items() if k in gardees}}
            for cle, v in par_cellule.items()}


def cibles_fautives(par_cellule, seuil, n=8):
    """Quelles cibles SAINES declenchent, et a quelle frequence. La liste actionnable.

    Un controle globalement inutilisable est presque toujours un controle que deux ou trois
    champs rendent inutilisable. Nommer ces champs vaut mieux que condamner le controle.
    """
    compte = collections.Counter()
    vus = collections.Counter()
    for v in par_cellule.values():
        for cible, score in v["neg"].items():
            vus[cible] += 1
            if score > seuil:
                compte[cible] += 1
    return [(c, compte[c], vus[c]) for c, _ in compte.most_common(n)]


def resume_reglage(par_cellule):
    """La courbe et le point sont calcules sur la CALIBRATION seule."""
    cal, _ = separer(par_cellule)
    pos, neg = aplatir(cal)
    pts = courbe(pos, neg)
    return pts, point_retenu(pts)


def par_facteur(par_cellule, seuil):
    """Rappel et faux positifs par valeur de chaque facteur, au seuil retenu."""
    axes = {"angle": 0, "dpi": 1, "jpeg": 2, "sigma": 3}
    out = {}
    for nom, i in axes.items():
        groupes = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        for cle, v in par_cellule.items():
            g = groupes[cle[i]]
            g[0] += sum(1 for x in v["pos"].values() if x > seuil)
            g[1] += len(v["pos"])
            g[2] += sum(1 for x in v["neg"].values() if x > seuil)
            g[3] += len(v["neg"])
            g[4] += any(x > seuil for x in v["neg"].values())
            g[5] += 1
        out[nom] = {val: {"rappel": g[0] / max(1, g[1]), "n": g[1],
                          "fpr": g[2] / max(1, g[3]),
                          "fpr_dossier": g[4] / max(1, g[5]),
                          "ic": wilson(g[0], g[1])}
                    for val, g in sorted(groupes.items())}
    return out


def plancher(par_cellule, seuil, minimum=RAPPEL_PLANCHER):
    """Les cellules ou le rappel passe sous le plancher. Une cellule = 3 graines.

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


def pires_conjonctions(par_cellule, seuil, combien=3):
    """Les pires CROISEMENTS de deux facteurs, pas seulement les pires valeurs de chacun.

    Une lecture marginale peut mentir par omission. Sur les valeurs interdites, le rappel dit
    0,979 a 300 dpi, 0,981 en JPEG 95 et 0,977 a sigma 12: aucune de ces trois valeurs ne
    franchit le plancher, et on conclut que le controle va bien partout. Croisees, elles font
    une cellule sous le plancher. Le signe est a l'envers de l'intuition, et c'est ce qui le
    rend interessant: le rappel baisse quand la qualite MONTE, parce qu'une compression forte
    efface le grain du capteur alors qu'une compression legere le garde, et qu'a haute
    resolution ce grain est assez fin pour se faire lire comme de la structure de caractere.
    Cette partie du mecanisme est mesuree par temoin, voir grille/suivi_coin.py.

    CE BALAYAGE NE VOIT QUE L'OMBRE DE LA CELLULE, et il faut le savoir en le lisant. La forme
    reelle de ce defaut-la est une conjonction de QUATRE facteurs (300 dpi ET JPEG 95 ET bruit
    12 ET angle superieur ou egal a 0,5 deg: 30/30 en dessous de cet angle, 50/60 au-dessus).
    Une paire moyenne sur les deux facteurs restants, donc elle attenue toujours ce qu'elle
    montre. Aller a trois et quatre facteurs ferait exploser le nombre de cases et tomber n a
    15 par case, ce qui rendrait les intervalles inutilisables. Le balayage a deux facteurs
    sert donc a TROUVER la cellule; c'est la liste des pires cellules, deja a quatre facteurs,
    qui la NOMME.
    """
    out = {}
    for i, a in enumerate(AXES):
        for b in AXES[i + 1:]:
            ia, ib = AXES.index(a), AXES.index(b)
            groupes = collections.defaultdict(lambda: [0, 0])
            for cle, v in par_cellule.items():
                g = groupes[(cle[ia], cle[ib])]
                g[0] += sum(1 for x in v["pos"].values() if x > seuil)
                g[1] += len(v["pos"])
            classe = sorted(((k, g[0] / max(1, g[1]), g[1], wilson(g[0], g[1]))
                             for k, g in groupes.items()), key=lambda t: t[1])
            out[f"{a} x {b}"] = [{"valeurs": list(k), "rappel": r, "n": n, "ic": list(ic)}
                                 for k, r, n, ic in classe[:combien]]
    return out


def frontiere(tombees, toutes):
    """La frontiere lisible: par facteur, la valeur a partir de laquelle ca tombe."""
    axes = ["angle", "dpi", "jpeg", "sigma"]
    out = {}
    for i, nom in enumerate(axes):
        compte = collections.Counter(c[i] for c in tombees)
        total = collections.Counter(c[i] for c in toutes)
        out[nom] = {v: (compte.get(v, 0), total[v]) for v in sorted(total)}
    return out


def tracer(resultats, chemin):
    if not resultats:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(resultats)
    cols = 3
    lignes = (n + cols - 1) // cols
    fig, axes = plt.subplots(lignes, cols, figsize=(4.6 * cols, 3.8 * lignes))
    for ax, (controle, r) in zip(axes.ravel(), sorted(resultats.items())):
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
        ax.axvline(RAPPEL_PLANCHER, color="gray", linestyle=":", linewidth=0.8)
        ax.set_title(controle, fontsize=10)
        ax.set_xlabel("rappel")
        ax.set_ylabel(f"precision a prevalence {PREVALENCE:.0%}")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.2)
        if any(g for _, _, g in r["courbes"]):
            ax.legend(fontsize=7, loc="lower left")
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle(f"Precision/rappel par controle, {resultats[list(resultats)[0]]['n_cellules']} "
                 f"cellules x 3 graines, budget de faux positifs {BUDGET_FP:.1%}", fontsize=11)
    fig.tight_layout()
    fig.savefig(chemin, dpi=130)
    return chemin


# Les controles qui dependent vraiment de ce que l'OCR arrive a lire. Ce sont eux qui
# definissent le plancher de resolution utile, pas le controle de resolution lui-meme.
DEPENDANTS_OCR = ("champ_requis", "validite", "coherence", "valeur_interdite")


def diaphonie(dossiers, ref, resultats):
    """Le controle c se declenche-t-il quand le defaut appartient a un AUTRE controle.

    Les tests posaient deja cette exigence, mais sur une seule cellule. La grille la mesure
    partout, parce que c'est la moitie qui compte: un controle qui crie sur le defaut du
    voisin fait douter du voisin, et une regle qui crie au loup fait survoler celles d'a cote.

    Le tableau n'est pas fait que de fautes. Une page ROGNEE emporte de vrais champs avec
    elle: le controle des champs requis a raison de crier. Ce que le tableau donne, c'est de
    quoi separer ce qui est une consequence physique de ce qui est une contamination.
    """
    out = {}
    for controle, r in resultats.items():
        reg, seuil = r["reglage"], r["seuil"]
        lignes = {}
        for v in VARIANTES:
            if not v.controle or v.controle == controle:
                continue
            n = tire = 0
            for d in dossiers.values():
                # ICI l'abstention est BRANCHEE: la diaphonie mesure le comportement du
                # PRODUIT, pas la capacite brute des capteurs.
                scores = scores_cibles(d[v.nom], ref, controle, reg, abstention=True)
                n += 1
                tire += any(x > seuil for x in scores.values())
            lignes[v.nom] = {"taux": tire / max(1, n), "n": n, "ic": wilson(tire, n)}
        out[controle] = lignes
    return out


def erreur_estimateur_dpi(dossiers):
    """L'erreur relative maximale de l'estimateur de dpi, mesuree sur les dossiers sains."""
    pire = 0.0
    for (_, dpi, _, _, _), d in dossiers.items():
        for lec in d["sain"].values():
            pire = max(pire, abs(lec.dpi_source - dpi) / dpi)
    return pire


def remesurer(r, seuil):
    """Tout recalculer AU SEUIL QU'ON PUBLIE. Sinon on publie un rappel mesure ailleurs.

    Le seuil du controle de resolution n'est pas celui de sa courbe: il est porte au plancher
    des autres. Sans ce recalcul, seuils.json annoncait "faux positifs 0,0000" a cote d'une
    valeur a laquelle c'etait faux (33% des cibles saines a 150 dpi). Meme famille de faute
    que la phrase de lecture survivant a son capteur: un nombre mesure sous une configuration,
    publie a cote d'une autre.
    """
    pc = r["_par_cellule"]
    cal, val = separer(pc)
    tombees, n_cel = plancher(pc, seuil)
    r.update({"seuil": seuil,
              "calibration": mesurer(cal, seuil), "validation": mesurer(val, seuil),
              "ensemble": mesurer(pc, seuil),
              "facteurs": par_facteur(pc, seuil),
              "conjonctions": pires_conjonctions(pc, seuil),
              "tombees": tombees, "n_cellules": n_cel,
              "frontiere": frontiere(tombees, {c[:4] for c in pc}),
              "cibles_fautives": cibles_fautives(pc, seuil)})
    return r


def plancher_operationnel(resultats, domaine, dossiers):
    """Le seuil du controle de resolution ne se lit pas sur SA courbe. Et c'est le sujet.

    Sa courbe le placerait entre 72 dpi (la variante fautive) et 96 dpi (le plus bas dpi de la
    grille), c'est-a-dire a l'endroit qui separe le mieux ces deux populations. Mais la
    question que ce controle doit poser n'est pas "cette page est-elle a 72 dpi", c'est "cette
    page est-elle assez nette pour que les AUTRES controles tiennent". Son seuil se lit donc
    sur le PLANCHER DE PANNE des controles qui dependent de l'OCR: le plus bas dpi ou tous
    gardent leur rappel au-dessus du plancher.

    Consequence assumee, et il faut la dire: si ce plancher est au-dessus du plus bas dpi de
    la grille, alors des dossiers SAINS numerises trop bas declenchent ce controle. Ce n'est
    pas un faux positif, c'est le controle qui fait son travail: on refuse de se prononcer sur
    une page qu'on ne sait pas lire. La confondre avec un faux positif reviendrait a se taire
    exactement quand on ne sait pas.
    """
    # Le seuil se pose SOUS le plancher, pas dessus. Un scan a exactement 150 dpi s'estime a
    # 149,98: seuil pose pile sur 150, il declenchait sur les 288 dossiers sains numerises au
    # plancher meme. La marge vaut dix fois la pire erreur mesuree de l'estimateur, au minimum
    # 1%, ce qui reste quarante fois plus fin que l'ecart entre deux dpi de la grille.
    erreur = erreur_estimateur_dpi(dossiers)
    marge = max(0.01, 10 * erreur)
    plancher_dpi = domaine
    seuil_dpi = domaine * (1 - marge)
    dpis = sorted(resultats["resolution"]["facteurs"]["dpi"])
    detail = {c: {d: round(resultats[c]["facteurs"]["dpi"][d]["rappel"], 3) for d in dpis}
              for c in DEPENDANTS_OCR if c in resultats}
    pr = resultats["resolution"]["point"]
    return {"seuil": -float(seuil_dpi),
            "point": dict(pr or {}, seuil=-float(seuil_dpi)),
            "plancher_dpi": plancher_dpi,
            "marge_estimateur": marge,
            "erreur_max_estimateur": erreur,
            "seuil_courbe_propre": (pr or {}).get("seuil"),
            "rappel_par_dpi_des_dependants": detail}


DOMAINES = (96, 150, 200, 300)


def seuils_de_definition():
    """Les seuils qui ne se FITTENT pas, parce qu'ils ne sont pas des parametres.

    "Perime" veut dire que la date est passee: le seuil vaut zero jour, point. Laisser la
    grille le choisir a donne -207,5 jours, et c'est le test des deux horloges qui l'a
    attrape: la piece saine du referentiel expire en 2027, donc n'importe quel seuil entre
    -497 et -110 separe parfaitement les donnees, et l'optimiseur a pris le milieu du palier.
    L'outil aurait declare une piece perimee sept mois avant qu'elle le soit, avec un rappel
    de 1,000 a l'appui.

    C'est le piege central de "lire le seuil sur la courbe": une courbe ne connait que les
    donnees qu'on lui a donnees, et elle deplacera sans hesiter un seuil qui encode du SENS.
    La grille reste utile sur ces controles, mais pour repondre a une autre question: le seuil
    etant fixe par definition, quel rappel tient-il et a quel prix.
    """
    from preflight.seuils import brut
    return {k for k, v in brut()["seuils"].items() if v["origine"] == "definition"}


def sous_grille(par_reglage, garde):
    return {reg: {cle: v for cle, v in pc.items() if garde(cle)}
            for reg, pc in par_reglage.items()}


def analyser_controle(par_reglage, controle, sortie=None):
    """Retient le meilleur reglage sous budget, mesure, cherche le plancher.

    Prend le balayage DEJA calcule: la recherche du domaine nominal essaie quatre sous-grilles
    et il n'y a aucune raison de repasser quatre fois sur les memes images, ni meme sur les
    memes scores.
    """
    classement = []
    for reg, par_cellule in par_reglage.items():
        if not par_cellule:
            continue
        pts, pt = resume_reglage(par_cellule)
        classement.append((reg, par_cellule, pts, pt))
    if not classement:
        return None
    tenables = [c for c in classement if c[3] is not None]
    gagnant = max(tenables or classement,
                  key=lambda c: (c[3]["rappel"] if c[3] else -1, -(c[3]["fpr"] if c[3] else 1)))
    reg, par_cellule, pts, pt = gagnant
    if not pts:
        return None
    fige = controle in seuils_de_definition()
    if fige:
        from preflight.seuils import charger_seuils
        impose = float(charger_seuils()[controle])
        # A seuil impose, le balayage ne sert plus qu'a choisir le CAPTEUR: on garde celui qui
        # rappelle le mieux A CE SEUIL-LA, pas celui qui rappellerait le mieux ailleurs.
        def note(c):
            m = mesurer(separer(c[1])[0], impose)
            return (m["rappel"], -m["fpr"])
        reg, par_cellule, pts, pt = max(classement, key=note)
        m = mesurer(separer(par_cellule)[0], impose)
        pt = dict(m, seuil=impose, **precisions(m["rappel"], m["fpr"]))
    gardees, exclues = certifiabilite(par_cellule)
    seuil = pt["seuil"] if pt else max(p["seuil"] for p in pts)
    cal, val = separer(par_cellule)
    tombees, n_cel = plancher(par_cellule, seuil)
    if sortie:
        with open(os.path.join(sortie, f"pr_{controle}.csv"), "w", newline="",
                  encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pts[0].keys()))
            w.writeheader()
            w.writerows(pts)
    return {
        "reglage": reg, "reglage_texte": nom_reglage(reg, controle), "point": pt,
        "seuil": seuil, "n_cellules": n_cel,
        "calibration": mesurer(cal, seuil), "validation": mesurer(val, seuil),
        "ensemble": mesurer(par_cellule, seuil),
        "courbes": [(nom_reglage(r, controle), p, r == reg) for r, _, p, _ in classement],
        "facteurs": par_facteur(par_cellule, seuil),
        "tombees": tombees, "frontiere": frontiere(tombees, {c[:4] for c in par_cellule}),
        "cibles_fautives": cibles_fautives(par_cellule, seuil),
        "seuil_fige_par_definition": fige,
        "cibles_non_certifiables": [(f"{a} / {b}", round(t, 4)) for (a, b), t in exclues.items()],
        "restreint": restreint_aux_certifiables(par_cellule, gardees, controle),
        "classement": [{"reglage": nom_reglage(r, controle),
                        "rappel": (q or {}).get("rappel"), "fpr": (q or {}).get("fpr"),
                        "seuil": (q or {}).get("seuil")}
                       for r, pc, _, q in sorted(
                           classement, key=lambda c: -((c[3] or {}).get("rappel", -1)))],
        "_classement": classement,
        "_par_cellule": par_cellule,
        "conjonctions": pires_conjonctions(par_cellule, seuil),
    }


def choisir_domaine(balayages, controles):
    """Le domaine nominal: le plus bas dpi ou les controles qui LISENT tiennent leur plancher.

    Sans cette etape, le point de fonctionnement de tout controle de texte est decide par les
    cellules ou la page est illisible, et il recule jusqu'a ne plus rien declencher. La raison
    est mecanique: un dossier est refuse des qu'UN champ requis est vide, donc le score du
    dossier est celui de son pire champ; a 96 dpi le Cerfa a des champs que l'OCR ne lit pas,
    le dossier SAIN atteint alors le meme score que le fautif, et sous un budget de faux
    positifs serre aucun seuil ne les separe plus.

    Assouplir le budget effacerait le probleme sans le resoudre. Le bon geste est de dire ou
    l'outil se declare competent, et de REFUSER DE CONCLURE en dessous: c'est le role du
    controle de resolution, dont le seuil sort precisement d'ici.
    """
    besoins = [c for c in DEPENDANTS_OCR if c in controles]
    essais = []
    for dpi_min in DOMAINES:
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
            r = analyser_controle(sous_grille(balayages[c], lambda k: k[1] >= dpi_min), c)
            pire = min(pire, 0.0 if r is None else r["validation"]["rappel"])
        essais.append((dpi_min, pire))
        if pire >= RAPPEL_PLANCHER:
            return dpi_min, essais
    # Aucun domaine ne tient le plancher. On garde alors le MOINS MAUVAIS, jamais le plus
    # etroit: se replier sur le domaine le plus etroit reviendrait a repondre "300 dpi" a une
    # question a laquelle la mesure a dit non partout, et a le faire sur le moins de donnees.
    valides = [(d, r) for d, r in essais if r is not None]
    if not valides:
        return DOMAINES[0], essais
    return max(valides, key=lambda x: x[1])[0], essais


PHRASES = {
    "champ_requis": lambda r, v: (
        f"se declenche si la zone porte moins de {-v:.3f}% d'encre AJOUTEE par rapport au "
        f"vierge (seuil d'encre {r.seuil_encre})" if r.capteur_texte == "encre" else
        f"se declenche si moins de {-v:.0f} caractere(s) alphanumerique(s) ajoute(s) sont lus "
        f"dans la zone par le capteur {r.capteur_texte} au-dessus de {r.conf_min:.0f} de "
        f"confiance"),
    "case_obligatoire": lambda r, v: (
        f"se declenche si le delta d'encre du disque central (rayon {r.part_disque} du cote, "
        f"seuil d'encre {r.seuil_encre}) est sous {-v:+.2f}"),
    "signature": lambda r, v: (
        f"se declenche si la plus grande composante ajoutee fait moins de {-v:.0f} px de "
        f"diagonale canonique" if r.capteur_signature == "composantes" else
        f"se declenche si la zone porte moins de {-v:.2f}% d'encre ajoutee"),
    "validite": lambda r, v: "se declenche des que la date lue est depassee a l'horloge choisie",
    "coherence": lambda r, v: (
        f"se declenche si le pire jeton de la plus petite lecture ressemble a moins de "
        f"{1 - v:.3f} au meilleur jeton de l'autre piece"),
    "valeur_interdite": lambda r, v: (
        f"se declenche si une suite de mots ajoutes ressemble a plus de {v:.3f} a une valeur "
        f"interdite"),
    "page_coupee": lambda r, v: (
        f"se declenche si plus de {v:.2%} de l'encre du vierge sort du cadre du scan"),
    "page_tournee": lambda r, v: (
        f"se declenche si un quart de tour bat le quart d'origine de plus de {v:.3f} de "
        f"correlation"),
}


def phrase_lecture(controle, reg, valeur, defaut=""):
    """La phrase se REGENERE a chaque publication, depuis le capteur reellement retenu.

    Une phrase reconduite telle quelle survit au capteur qu'elle decrit. C'est arrive ici:
    apres que la grille eut retenu l'encre pour les champs requis, seuils.json continuait de
    dire "moins de 1 caractere alphanumerique", et un lecteur pouvait croire que -0,345 etait
    un nombre de caracteres alors que c'est un pourcentage d'encre. Une unite fausse dans une
    phrase juste est plus dangereuse qu'une phrase absente.
    """
    f = PHRASES.get(controle)
    return f(reg, valeur) if f else defaut


def _reglage_utile(reg, controle):
    """Seulement les boutons qui agissent VRAIMENT sur le reglage retenu.

    Le capteur d'encre ignore la confiance OCR: la consigner a cote de lui ferait croire
    qu'elle a ete choisie alors qu'elle n'a rien decide.
    """
    noms = NUISANCES[controle]
    if controle == "champ_requis":
        noms = ("capteur_texte", "seuil_encre") if reg.capteur_texte == "encre" \
            else ("capteur_texte", "conf_min")
    return {n: getattr(reg, n) for n in noms}


def _jsonable(v):
    """Les cellules sont des tuples (angle, dpi, jpeg, sigma): JSON ne veut pas de tels cles."""
    if isinstance(v, dict):
        return {(str(k) if not isinstance(k, (str, int, float, bool, type(None))) else k):
                _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def nom_reglage(reg, controle):
    if controle == "champ_requis":
        return (f"capteur_texte=encre, seuil_encre={reg.seuil_encre}"
                if reg.capteur_texte == "encre"
                else f"capteur_texte={reg.capteur_texte}, conf_min={reg.conf_min}")
    noms = NUISANCES[controle]
    return ", ".join(f"{n}={getattr(reg, n)}" for n in noms) or "aucun reglage"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesures", default=os.path.join(RACINE, "grille", "mesures", "mesures.jsonl"))
    ap.add_argument("--sortie", default=RESULTATS)
    ap.add_argument("--controles", nargs="*", default=list(CONTROLES))
    ap.add_argument("--publier", action="store_true",
                    help="ecrire LIMITES.md et seuils.json a la racine du depot")
    a = ap.parse_args()
    os.makedirs(a.sortie, exist_ok=True)

    ref = charger_referentiel()
    index = charger(a.mesures)
    dossiers = dossiers_complets(index)
    cellules = {c[:4] for c in dossiers}
    print(f"{len(dossiers)} couples cellule/graine complets, {len(cellules)} cellules distinctes")

    balayages = {}
    for controle in a.controles:
        t = time.perf_counter()
        balayages[controle] = balayer(dossiers, ref, controle)
        print(f"  balayage {controle:17s} {len(balayages[controle]):3d} reglages, "
              f"{time.perf_counter() - t:5.1f}s", flush=True)

    domaine, essais = choisir_domaine(balayages, a.controles)
    retenus = {k: v for k, v in dossiers.items() if k[1] >= domaine}
    print(f"domaine nominal retenu: dpi >= {domaine} ({len(retenus)} couples). Essais: "
          + ", ".join(f"{d} dpi -> " + ("pas de donnees" if r is None else
                                        f"pire rappel {r:.3f}") for d, r in essais))
    if all((r or 0) < RAPPEL_PLANCHER for _, r in essais):
        print(f"  AUCUN domaine ne tient le plancher de {RAPPEL_PLANCHER:.0%}: "
              "le domaine retenu est le moins mauvais, pas un domaine sur.")

    resultats = {}
    for controle in a.controles:
        r = analyser_controle(sous_grille(balayages[controle], lambda k: k[1] >= domaine),
                              controle, a.sortie)
        if r is None:
            print(f"  {controle:17s} AUCUNE mesure exploitable")
            continue
        r["domaine"] = domaine
        hors = sous_grille(balayages[controle], lambda k: k[1] < domaine)[r["reglage"]]
        r["hors_domaine"] = mesurer(hors, r["seuil"]) if hors else None
        resultats[controle] = r
        v, c = r["validation"], r["calibration"]
        print(f"  {controle:17s} {r['reglage_texte']:42s} seuil={r['seuil']:9.4g} "
              f"calib rappel={c['rappel']:.3f} fpr={c['fpr']:.4f} | "
              f"VALID rappel={v['rappel']:.3f} fpr={v['fpr']:.4f} | "
              f"hors domaine {len(r['tombees'])}/{r['n_cellules']}")

    if "resolution" in resultats:
        resultats["resolution"].update(plancher_operationnel(resultats, domaine, retenus))
        r = remesurer(resultats["resolution"], resultats["resolution"]["seuil"])
        r["point"] = dict(r["validation"], seuil=r["seuil"],
                          **precisions(r["validation"]["rappel"], r["validation"]["fpr"]))
        print(f"  {'resolution':17s} seuil porte a {r['seuil']:.4g} = plancher "
              f"{r['plancher_dpi']} dpi moins {r['marge_estimateur']:.1%} de marge "
              f"(erreur max mesuree de l'estimateur {r['erreur_max_estimateur']:.4%})")
    t = time.perf_counter()
    croise = diaphonie(retenus, ref, resultats)
    print(f"  diaphonie mesuree sur toute la grille en {time.perf_counter() - t:.0f}s")
    if not resultats:
        print("aucun controle exploitable, rien a tracer")
        return 1
    tracer(resultats, os.path.join(a.sortie, "courbes.png"))
    json.dump({c: {k: _jsonable(v) for k, v in r.items()
                   if k not in ("courbes", "reglage", "_classement", "_par_cellule")}
               for c, r in resultats.items()},
              open(os.path.join(a.sortie, "resume.json"), "w"), indent=2, default=str)
    ecrire_duels(resultats, os.path.join(a.sortie, "duels.md"))
    json.dump(_jsonable(croise), open(os.path.join(a.sortie, "diaphonie.json"), "w"), indent=2)
    racine = RACINE if a.publier else a.sortie
    ecrire_limites(resultats, os.path.join(racine, "LIMITES.md"), len(dossiers),
                   domaine, len(retenus), essais, croise)
    if a.publier:
        ecrire_seuils(resultats, os.path.join(RACINE, "seuils.json"))
    print(f"-> {a.sortie}/courbes.png, {racine}/LIMITES.md, {a.sortie}/duels.md"
          + (", seuils.json publie" if a.publier else ", seuils.json NON publie (--publier)"))
    return 0


def duel_par_dpi(classement, controle):
    """Le gagnant change-t-il selon le dpi. C'est la seule facon honnete de trancher un duel.

    Chaque concurrent est juge a SON propre point de fonctionnement (celui qui tient le budget
    de faux positifs), pas au seuil du voisin: comparer deux capteurs a un seuil commun
    compare une echelle, pas un capteur.
    """
    dpis = sorted({c[1] for _, pc, _, _ in classement for c in pc})
    lignes = []
    for reg, par_cellule, _, pt in classement:
        if pt is None:
            continue
        ligne = {"reglage": nom_reglage(reg, controle), "seuil": pt["seuil"],
                 "global": (pt["rappel"], pt["fpr"])}
        for dpi in dpis:
            sous = {k: v for k, v in par_cellule.items() if k[1] == dpi}
            m = mesurer(sous, pt["seuil"])
            ligne[dpi] = (m["rappel"], m["fpr"], m["ic_rappel"])
        lignes.append(ligne)
    return dpis, sorted(lignes, key=lambda l: -l["global"][0])


def ecrire_duels(resultats, chemin):
    lignes = ["# Duels entre capteurs concurrents", "",
              "Chaque concurrent est juge a SON propre point de fonctionnement, celui qui tient",
              f"le budget de faux positifs de {BUDGET_FP:.1%}. Comparer deux capteurs a un seuil",
              "commun comparerait une echelle et pas un capteur. Les intervalles sont des",
              "intervalles de Wilson a 95%: a trois graines par cellule, l'intervalle normal ment.",
              ""]
    for controle in sorted(resultats):
        r = resultats[controle]
        if not NUISANCES[controle]:
            continue
        dpis, tab = duel_par_dpi(r["_classement"], controle)
        if not tab:
            continue
        lignes += [f"## {controle}", "",
                   "| reglage | seuil | rappel global | fpr global | "
                   + " | ".join(f"rappel {d} dpi" for d in dpis) + " |",
                   "|---|---|---|---|" + "---|" * len(dpis)]
        for l in tab:
            cases = " | ".join(f"{l[d][0]:.3f} [{l[d][2][0]:.2f}, {l[d][2][1]:.2f}]" for d in dpis)
            marque = " **(retenu)**" if l["reglage"] == r["reglage_texte"] else ""
            lignes.append(f"| {l['reglage']}{marque} | {l['seuil']:.4g} | {l['global'][0]:.3f} "
                          f"| {l['global'][1]:.4f} | {cases} |")
        # Depart a rappel egal par le taux de faux positifs, sinon le "gagnant" est
        # simplement le premier de la liste, ce qui ne veut rien dire.
        gagnants = {d: max(tab, key=lambda l: (l[d][0], -l[d][1]))["reglage"] for d in dpis}
        # Une egalite est un resultat, pas un vainqueur. Annoncer "capteur X gagne" quand
        # deux capteurs rendent exactement les memes chiffres partout, c'est raconter une
        # mesure qui n'a pas eu lieu.
        tete = max(l["global"] for l in tab)
        exaequo = [l["reglage"] for l in tab if l["global"] == tete]
        if len(exaequo) > 1:
            lignes += ["", f"EGALITE, non departage: {len(exaequo)} reglages rendent exactement "
                       f"le meme rappel ({tete[0]:.3f}) et le meme taux de faux positifs "
                       f"({tete[1]:.4f}) sur l'ensemble du domaine. Ce corpus et cette grille ne "
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


def ecrire_limites(resultats, chemin, n_couples, domaine, n_retenus, essais, croise=None):
    l = ["# Limites: ou cet outil cesse de marcher", "",
         "Un outil qui ne dit pas ou il cesse de marcher n'est pas mesure, il est raconte.",
         "",
         f"## Domaine nominal: numerisation a {domaine} dpi ou plus", "",
         f"Les points de fonctionnement sont choisis sur les {n_retenus} couples de ce domaine,",
         f"pas sur les {n_couples} de la grille entiere. Ce n'est pas une facon de se donner de",
         "beaux chiffres, c'est une consequence mecanique: un dossier est refuse des qu'UN champ",
         "requis est vide, donc le score du dossier est celui de son PIRE champ. Sous le",
         "plancher, le Cerfa a des champs que l'OCR ne lit pas, le dossier SAIN atteint alors le",
         "meme score que le dossier fautif, et aucun seuil ne les separe plus. Le point de",
         "fonctionnement reculerait jusqu'a ne plus rien declencher du tout.",
         "",
         "Sous ce plancher l'outil ne devine pas: le controle de resolution se declenche et dit",
         "qu'il ne sait pas lire la page. Chaque section ci-dessous donne aussi ce que le",
         "controle fait HORS domaine, parce que le cacher serait le mentir.",
         "",
         "Domaines essayes, du plus large au plus etroit, avec le pire rappel des controles",
         "qui dependent de l'OCR: "
         + ", ".join(f"dpi >= {d} -> "
                     + ("pas de donnees" if r is None else f"{r:.3f}") for d, r in essais)
         + ".",
         "",
         f"Mesure sur {n_couples} couples cellule/graine: angle (0, 0.25, 0.5, 1, 2, 4 deg) x",
         "dpi (96, 150, 200, 300) x qualite JPEG (30, 55, 75, 95) x bruit sigma (0, 3, 6, 12),",
         "trois graines par cellule. Chaque controle est evalue a son point de fonctionnement,",
         f"choisi comme le rappel le plus haut tenant un taux de faux positifs sous "
         f"{BUDGET_FP:.1%}.",
         "",
         "Le seuil est choisi sur les graines 11 et 23, et le chiffre publie est celui de la",
         f"graine {GRAINE_VALIDATION}, jamais regardee avant. Choisir un seuil et rapporter son",
         "rappel sur les memes tirages le surestime toujours.",
         "",
         "Une cellule est declaree HORS DOMAINE quand le rappel y passe sous "
         f"{RAPPEL_PLANCHER:.0%}.", "",
         "## Ce que la mesure ne couvre pas", "",
         "- Un seul jeu de trois formulaires (W-9, I-9, Cerfa 14011). Les chiffres ne se",
         "  transportent pas tels quels sur un formulaire dont la typographie ou l'encadrement",
         "  des champs differe. Le Cerfa, dont les champs sont encadres case par case, est deja",
         "  nettement plus dur que les deux formulaires americains.",
         "- Les mots ne sont enregistres que dans les zones DECLAREES par l'AcroForm, dilatees",
         "  de 8 px. Une valeur interdite qui reapparaitrait hors de tout champ declare, dans une",
         "  mention manuscrite en marge par exemple, ne serait pas vue.",
         "- Un formulaire sans AcroForm est hors de portee: toute la geometrie vient de la",
         "  declaration du PDF, rien n'est mesure a la main.",
         "- Les degradations sont SYNTHETIQUES. Un vrai scanner ajoute des artefacts que cette",
         "  grille n'imite pas: courbure de page, ombre de reliure, poussiere sur la vitre,",
         "  moire de retramage. La grille borne le domaine, elle ne le prouve pas.",
         "- CONSEQUENCE DIRECTE SUR LE CAPTEUR D'ENCRE, et elle est genante parce que ce capteur",
         "  gagne son duel: aucune degradation de cette grille n'AJOUTE d'encre etrangere dans",
         "  une zone. Un tampon, une ombre de pliure, un trait de stylo qui deborde du champ",
         "  voisin feraient dire a ce capteur qu'un champ vide est rempli, c'est-a-dire un faux",
         "  negatif, le cote cher de l'asymetrie. Il gagne ici sur un terrain qui lui est",
         "  favorable, et le dire fait partie du resultat. Le capteur de mots, lui, ne confond",
         "  pas une tache avec une valeur, et son point de fonctionnement mesure est juste a",
         "  cote (voir le duel).",
         "- La precision depend de la prevalence. Les courbes la donnent a "
         f"{PREVALENCE:.0%} de dossiers fautifs, valeur SUPPOSEE et non mesuree.",
         ""]
    suivi = os.path.join(RACINE, "grille", "resultats", "suivi.json")
    if os.path.exists(suivi):
        d = json.load(open(suivi))
        c, t, cu = d["jeux"]["coin"], d["jeux"]["temoin"], d["cumule"]
        co = d["coin"]
        l += ["## Suivi hors protocole: la seule cellule ou l'outil manque quelque chose", "",
              "HORS PROTOCOLE, et il faut le dire avant les chiffres. Les seuils publies sortent",
              "d'une regle stricte: deux graines calibrent, la troisieme n'est jamais regardee",
              "avant que le chiffre soit ecrit. Les graines de ce suivi ont ete tirees APRES",
              "avoir vu ou l'outil manquait, sur une cellule choisie parce qu'elle manquait.",
              "Elles ne deplacent aucun seuil et n'entrent dans aucun chiffre publie ailleurs.",
              "Elles repondent a une seule question: n=18 suffisait-il pour conclure.", "",
              f"Cellule: {co['dpi']} dpi, JPEG {co['jpeg']}, bruit sigma {co['sigma']}, controle "
              f"{d['controle']}, seuil publie {d['seuil']}.", "",
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
              f"reste a {cu['ic'][1]:.3f}, sous le plancher de {RAPPEL_PLANCHER:.0%}. Ce n'est",
              "pas du bruit d'echantillon: le controle manque vraiment quelque chose ici.", "",
              "TEMOIN, et c'est lui qui rend les douze graines interpretables. Meme cellule,",
              "memes douze graines, seule la compression change:", "",
              f"- JPEG {co['jpeg']}: {c['tp']}/{c['n']} = {c['rappel']:.4f}",
              f"- JPEG 30: {t['tp']}/{t['n']} = {t['rappel']:.4f}", "",
              "Les graines neuves ne sont donc pas plus dures, c'est la compression. Une",
              "compression FORTE efface le grain du capteur; une compression legere le garde, et",
              "a haute resolution ce grain est assez fin pour se faire lire comme de la",
              "structure de caractere. Cette partie du mecanisme est MESUREE.", "",
              "LA FORME REELLE EST UNE CONJONCTION DE QUATRE FACTEURS, pas de deux:", "",
              f"- angle sous {cu['marche_angle']} deg: {cu['angle_sous_marche'][0]}/"
              f"{cu['angle_sous_marche'][1]} = {cu['angle_sous_marche'][2]:.4f}",
              f"- angle a {cu['marche_angle']} deg ou plus: {cu['angle_sur_marche'][0]}/"
              f"{cu['angle_sur_marche'][1]} = {cu['angle_sur_marche'][2]:.4f}", "",
              "Une marche, pas une pente. La cellule fautive est donc "
              f"{co['dpi']} dpi ET JPEG {co['jpeg']} ET",
              f"bruit {co['sigma']} ET angle >= {cu['marche_angle']} deg. Le balayage a deux",
              "facteurs ci-dessous ne peut pas la voir telle quelle: chaque paire moyenne sur",
              "les deux facteurs restants, donc elle n'en montre que l'ombre. Il sert a la",
              "TROUVER; c'est la liste des pires cellules, qui est deja a quatre facteurs, qui",
              "la NOMME.", "",
              "Reserve sur le mecanisme: la partie compression est mesuree par le temoin, la",
              "partie angle est SUPPOSEE. L'hypothese est que c'est l'ampleur du",
              "reechantillonnage qui compte et non sa presence, un redressement au-dela d'un",
              "demi-degre etalant le grain fin dans l'epaisseur des traits. Elle n'est pas",
              "testee. Le redressement applique bien une rotation bicubique des 0,25 deg aussi,",
              "donc l'explication paresseuse (pas de reechantillonnage sous 0,5 deg) est fausse.",
              "", "Reproduire: `python3 grille/suivi_coin.py`.", ""]

    if croise:
        noms = [v.nom for v in VARIANTES if v.controle]
        l += ["## Diaphonie: qui crie sur le defaut du voisin", "",
              "Chaque case donne la part des dossiers ou le controle de la LIGNE se declenche",
              "alors que le defaut injecte appartient a la COLONNE. La diagonale est vide par",
              "construction. Toutes les cases ne sont pas des fautes: une page rognee emporte de",
              "vrais champs, donc le controle des champs requis a raison d'y crier. Ce tableau",
              "sert a separer la consequence physique de la contamination.", "",
              "Une LIGNE UNIFORME n'est pas de la diaphonie: c'est le taux de fond du controle",
              "qui reapparait. Les variantes partagent les pieces qu'elles n'abiment pas, donc",
              "un controle qui se declenche a x% sur un dossier sain se declenche a x% sur",
              "toutes les colonnes. Ce qui se lit ici, ce sont les cases qui DEPASSENT la ligne.",
              "",
              "| controle \\ defaut | " + " | ".join(n[:14] for n in noms) + " |",
              "|---|" + "---|" * len(noms)]
        for controle in sorted(croise):
            cases = []
            for n in noms:
                d = croise[controle].get(n)
                cases.append("." if d is None else
                             ("." if d["taux"] == 0 else f"{d['taux']:.3f}"))
            l.append(f"| {controle} | " + " | ".join(cases) + " |")
        l += ["", "Un point vaut zero declenchement sur "
              f"{next(iter(next(iter(croise.values())).values()))['n']} dossiers.", ""]

    for controle in sorted(resultats):
        r = resultats[controle]
        pt = r["point"]
        l += [f"## {controle}", ""]
        if pt is None:
            l += ["Aucune mesure exploitable pour ce controle.", ""]
            continue
        if r["validation"]["rappel"] < RAPPEL_PLANCHER:
            l += [f"ATTENTION: sous le budget de faux positifs de {BUDGET_FP:.1%}, le meilleur",
                  f"rappel atteignable est {r['validation']['rappel']:.3f}, sous le plancher de",
                  f"{RAPPEL_PLANCHER:.0%}. Ce controle laisse passer des dossiers fautifs plus",
                  "souvent qu'il ne devrait: il ne doit pas etre presente comme une garantie.", ""]
        c, v, e = r["calibration"], r["validation"], r["ensemble"]
        l += [f"Reglage retenu: {r['reglage_texte']}. Seuil {r['seuil']:.4g}.", "",
              "| jeu | rappel | IC 95% | faux positifs par cible | IC 95% | "
              "par dossier sain | positifs |",
              "|---|---|---|---|---|---|---|"]
        for etiquette, m in (("calibration (graines 11 et 23)", c),
                             ("VALIDATION (graine 37, jamais vue)", v), ("ensemble", e)):
            l.append(f"| {etiquette} | {m['rappel']:.3f} | [{m['ic_rappel'][0]:.3f}, "
                     f"{m['ic_rappel'][1]:.3f}] | {m['fpr']:.4f} | [{m['ic_fpr'][0]:.4f}, "
                     f"{m['ic_fpr'][1]:.4f}] | {m['fpr_dossier']:.4f} | {m['n_pos']} |")
        l += ["",
              "Le taux par dossier est celui que l'utilisateur ressent: la probabilite qu'au",
              "moins une alarme parte sur un dossier entierement sain. C'est lui qui decide si",
              "la gate reste credible.", "",
              f"Cellules sous le plancher: {len(r['tombees'])} sur {r['n_cellules']}.", ""]
        nc = r.get("cibles_non_certifiables") or []
        if nc:
            l += ["Cibles qui plafonnent ce controle, avec la part des dossiers SAINS ou elles",
                  "se declenchent au seuil qu'il faudrait pour ne rien manquer:", ""]
            for nom, taux in nc:
                l.append(f"- {nom}: {taux:.1%}")
            l += ["", "Sur ces cibles, la bonne reponse de l'outil n'est pas \"ce champ est",
                  "vide\" mais \"je ne sais pas lire ce champ\": meme capteur, consequences",
                  "opposees au guichet. Elles restent dans le chiffre de tete ci-dessus, elles",
                  "ne sont pas retirees pour l'embellir.", ""]
        rr = r.get("restreint")
        if rr:
            l += [f"Chiffre SECONDAIRE, a ne pas confondre avec celui de tete: si on ne demande",
                  f"a ce controle que les {rr['cibles_gardees']} cibles sur "
                  f"{rr['cibles_totales']} qu'il sait certifier, il tient un rappel de "
                  f"{rr['rappel']:.3f} a {rr['fpr']:.4f} de faux positifs par cible.", ""]
        conj = r.get("conjonctions") or {}
        pires = sorted(((k, c[0]) for k, c in conj.items() if c), key=lambda t: t[1]["rappel"])
        if pires and pires[0][1]["rappel"] < 1.0:
            l += ["Pires CROISEMENTS de deux facteurs. Une lecture axe par axe peut mentir par",
                  "omission: trois valeurs marginales toutes au-dessus du plancher peuvent se",
                  "croiser en une cellule qui passe dessous.", ""]
            for nom, c in pires[:4]:
                if c["rappel"] >= 1.0:
                    continue
                l.append(f"- {nom} = {c['valeurs']}: rappel {c['rappel']:.3f} "
                         f"[{c['ic'][0]:.3f}, {c['ic'][1]:.3f}] sur {c['n']} positifs"
                         + ("  <- borne haute sous le plancher"
                            if c["ic"][1] < RAPPEL_PLANCHER else ""))
            l.append("")
        cf = r.get("cibles_fautives") or []
        if cf:
            l += ["Cibles saines qui se declenchent AU SEUIL RETENU, celles qui coutent la "
                  "credibilite:", ""]
            for cible, combien, total in cf[:6]:
                l.append(f"- {cible[0]} / {cible[1]}: {combien} fois sur {total}")
            l.append("")
        h = r.get("hors_domaine")
        if h and h["n_pos"]:
            l += [f"Hors domaine (dpi < {r['domaine']}), CAPTEURS BRUTS, c'est-a-dire ce que "
                  "l'outil ferait",
                  "s'il n'avait pas la regle d'abstention: rappel "
                  f"{h['rappel']:.3f} [{h['ic_rappel'][0]:.3f}, {h['ic_rappel'][1]:.3f}], "
                  f"declenchements sur dossier sain {h['fpr']:.4f} sur {h['n_neg']} cibles.",
                  "Ces chiffres-la ne decrivent donc pas le produit, ils justifient la regle: "
                  "en",
                  "production, un controle qui LIT s'abstient sous le plancher au lieu de "
                  "produire",
                  "ce qu'on lit ici. Ils sont mesures capteurs bruts a dessein, parce qu'une "
                  "mesure",
                  "ne peut pas dependre du comportement qu'elle sert a regler.", ""]
            if controle == "resolution":
                l += ["Pour CE controle, ces declenchements hors domaine ne sont pas des faux",
                      "positifs: c'est exactement son travail. Il est la pour dire qu'une page",
                      "numerisee sous le plancher ne doit pas etre jugee par les autres.", ""]
        if r["tombees"]:
            l += ["Frontiere par facteur, nombre de cellules tombees sur le total:", ""]
            for nom, vals in r["frontiere"].items():
                l.append("- " + nom + ": " + ", ".join(f"{v} -> {a}/{b}" for v, (a, b) in vals.items()))
            l.append("")
            pires = sorted(r["tombees"].items(), key=lambda kv: kv[1][0])[:6]
            l += ["Les pires cellules (angle, dpi, jpeg, sigma) et leur rappel:", ""]
            for c, (rap, n) in pires:
                l.append(f"- angle {c[0]}, {c[1]} dpi, JPEG {c[2]}, sigma {c[3]}: "
                         f"rappel {rap:.2f} sur {n} graines")
            l.append("")
        else:
            l += ["Aucune cellule du domaine explore ne passe sous le plancher.", ""]
        l += ["Rappel par facteur, au seuil retenu:", ""]
        for nom, vals in r["facteurs"].items():
            l.append("- " + nom + ": " + ", ".join(
                f"{v} -> {d['rappel']:.3f} [{d['ic'][0]:.2f}, {d['ic'][1]:.2f}]"
                for v, d in vals.items()))
        l.append("")
    open(chemin, "w", encoding="utf-8").write("\n".join(l) + "\n")


def ecrire_seuils(resultats, chemin):
    d = json.load(open(chemin, encoding="utf-8"))
    for controle, r in resultats.items():
        pt = r["point"]
        if pt is None:
            continue
        mesures = {
            "rappel": round(r["validation"]["rappel"], 4),
            "faux_positifs": round(r["validation"]["fpr"], 5),
            "mesure_sur": "graine 37, jamais utilisee pour choisir le seuil",
            "reglage": r["reglage_texte"],
            "reglage_mesure": _reglage_utile(r["reglage"], controle),
            "courbe": f"grille/resultats/pr_{controle}.csv",
            "cellules_hors_domaine": f"{len(r['tombees'])}/{r['n_cellules']}",
            "domaine_nominal_dpi": r.get("domaine"),
        }
        if r.get("seuil_fige_par_definition"):
            d["seuils"][controle].update(mesures)
            d["seuils"][controle]["lecture"] = phrase_lecture(
                controle, r["reglage"], float(r["seuil"]),
                d["seuils"][controle].get("lecture", ""))
            continue
        d["seuils"][controle] = {
            "valeur": round(float(r["seuil"]), 4),
            "origine": "grille",
            "lecture": phrase_lecture(controle, r["reglage"], float(r["seuil"]),
                                      d["seuils"].get(controle, {}).get("lecture", "")),
            "reglage": r["reglage_texte"],
            "reglage_mesure": _reglage_utile(r["reglage"], controle),
            "rappel": round(r["validation"]["rappel"], 4),
            "faux_positifs": round(r["validation"]["fpr"], 5),
            "mesure_sur": "graine 37, jamais utilisee pour choisir le seuil",
            "courbe": f"grille/resultats/pr_{controle}.csv",
            "cellules_hors_domaine": f"{len(r['tombees'])}/{r['n_cellules']}",
            "domaine_nominal_dpi": r.get("domaine"),
        }
        if "plancher_dpi" in r:
            d["seuils"][controle].update({
                "valeur": round(float(r["seuil"]), 4),
                "lecture": f"se declenche sous {-r['seuil']:.1f} dpi estimes, soit le plancher "
                           f"de {r['plancher_dpi']} dpi moins une marge de "
                           f"{r['marge_estimateur']:.1%}; le plancher est lu sur le rappel des "
                           "controles qui dependent de l'OCR et non sur la courbe de ce "
                           "controle, et la marge couvre dix fois l'erreur maximale mesuree de "
                           f"l'estimateur ({r['erreur_max_estimateur']:.4%})",
                "seuil_de_sa_propre_courbe": r["seuil_courbe_propre"],
                "rappel_par_dpi_des_dependants": r["rappel_par_dpi_des_dependants"]})
    d["mesure_le"] = "2026-08-21"
    d["budget_faux_positifs"] = BUDGET_FP
    json.dump(d, open(chemin, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
