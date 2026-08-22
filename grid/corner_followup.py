#!/usr/bin/env python3
"""Mesure de SUIVI sur la seule cell du domaine nominal ou l'outil manque quelque chose.

HORS PROTOCOLE, et il faut le dire avant les chiffres. La grid publie ses thresholds selon une
regle stricte: deux graines calibrent, la troisieme n'est jamais regardee avant que le chiffre
soit ecrit. Ces graines-ci ont ete tirees APRES avoir vu ou l'outil manquait, sur une cell
choisie parce qu'elle manquait. Elles ne peuvent donc pas deplacer un seuil ni entrer dans un
chiffre publie: elles repondent a une seule question, celle de la taille d'echantillon.

    n=18 sur les graines d'origine donnait 0,833, avec un intervalle si large qu'on ne pouvait
    pas dire si le check manquait vraiment ou si trois tirages malheureux s'etaient suivis.

Deux jeux, douze graines neuves chacun, une seule chose qui change entre eux:
    coin    300 dpi, JPEG 95, bruit 12
    temoin  300 dpi, JPEG 30, bruit 12
Le temoin est ce qui fait la difference entre "mes graines sont dures" et "c'est la
compression". Sans lui, les douze graines neuves ne prouvent rien.

    python3 grid/corner_followup.py    # ecrit grid/resultats/suivi.json
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grid.analyze import load, damaged_targets, complete_dossiers, target_scores, wilson
from preflight.checks import measured_settings
from preflight.fixtures import VARIANTS
from preflight.reference import load_reference
from preflight.thresholds import load_thresholds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROLE = "forbidden_value"
CORNER = (300, 95, 12.0)          # dpi, qualite JPEG, bruit sigma
MARCHE_ANGLE = 0.5              # l'angle a partir duquel le rappel decroche


def recalls(dossiers, ref, reg, seuil, cibles, var):
    """Retour: (tp, n, par angle)."""
    par_angle = collections.defaultdict(lambda: [0, 0])
    tp = n = 0
    for key, dossier in dossiers.items():
        sc = target_scores(dossier[var.name], ref, CONTROLE, reg)
        pos = {k: v for k, v in sc.items() if k in cibles} or sc
        for x in pos.values():
            n += 1
            tp += x > seuil
            g = par_angle[key[0]]
            g[0] += x > seuil
            g[1] += 1
    return tp, n, {a: tuple(g) for a, g in sorted(par_angle.items())}


def main():
    ref = load_reference()
    seuil = load_thresholds()[CONTROLE]
    reg = measured_settings()[CONTROLE]
    var = next(v for v in VARIANTS if v.check == CONTROLE)
    cibles = damaged_targets(var, ref)
    base = os.path.join(ROOT, "grid", "mesures")

    jeux = {}
    principal = complete_dossiers(load(os.path.join(base, "mesures.jsonl")))
    jeux["origine"] = {k: v for k, v in principal.items() if (k[1], k[2], k[3]) == CORNER}
    for name, fichier in (("coin", "suivi/mesures-coin.jsonl"),
                         ("temoin", "suivi/mesures-temoin.jsonl")):
        jeux[name] = complete_dossiers(load(os.path.join(base, fichier)))

    out = {"check": CONTROLE, "seuil": seuil, "reglage": reg.text_sensor,
           "coin": {"dpi": CORNER[0], "jpeg": CORNER[1], "sigma": CORNER[2]},
           "hors_protocole": "graines tirees apres avoir vu ou l'outil manquait; "
                             "ne deplacent aucun seuil et n'entrent dans aucun chiffre publie",
           "jeux": {}}
    for name, d in jeux.items():
        tp, n, par_angle = recalls(d, ref, reg, seuil, cibles, var)
        bas = [g for a, g in par_angle.items() if a < MARCHE_ANGLE]
        haut = [g for a, g in par_angle.items() if a >= MARCHE_ANGLE]
        out["jeux"][name] = {
            "n_couples": len(d), "tp": tp, "n": n, "rappel": tp / max(1, n),
            "ic": list(wilson(tp, n)),
            "par_angle": {str(a): list(g) for a, g in par_angle.items()},
            "angle_sous_marche": [sum(g[0] for g in bas), sum(g[1] for g in bas)],
            "angle_sur_marche": [sum(g[0] for g in haut), sum(g[1] for g in haut)],
        }
    o, c = out["jeux"]["origine"], out["jeux"]["coin"]
    tp, n = o["tp"] + c["tp"], o["n"] + c["n"]
    bas = [o["angle_sous_marche"][i] + c["angle_sous_marche"][i] for i in (0, 1)]
    haut = [o["angle_sur_marche"][i] + c["angle_sur_marche"][i] for i in (0, 1)]
    out["cumule"] = {"tp": tp, "n": n, "rappel": tp / n, "ic": list(wilson(tp, n)),
                     "angle_sous_marche": bas + [bas[0] / bas[1]],
                     "angle_sur_marche": haut + [haut[0] / haut[1]],
                     "marche_angle": MARCHE_ANGLE}
    dest = os.path.join(ROOT, "grid", "resultats", "suivi.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"coin q95   {c['tp']}/{c['n']} = {c['rappel']:.4f} {[round(x,3) for x in c['ic']]}")
    print(f"temoin q30 {out['jeux']['temoin']['tp']}/{out['jeux']['temoin']['n']} = "
          f"{out['jeux']['temoin']['rappel']:.4f}")
    print(f"CUMULE     {tp}/{n} = {tp/n:.4f} {[round(x, 3) for x in out['cumule']['ic']]}")
    print(f"  angle < {MARCHE_ANGLE}: {bas[0]}/{bas[1]}   angle >= {MARCHE_ANGLE}: {haut[0]}/{haut[1]}")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
