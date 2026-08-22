#!/usr/bin/env python3
"""Mesure de SUIVI sur la seule cell du domain nominal ou l'outil manque quelque chose.

HORS PROTOCOLE, et il faut le dire avant les chiffres. La grid publie ses thresholds selon une
regle stricte: deux graines calibrent, la troisieme n'est jamais regardee avant que le chiffre
soit ecrit. Ces graines-ci ont ete tirees APRES avoir vu ou l'outil manquait, sur une cell
choisie parce qu'elle manquait. Elles ne peuvent donc pas deplacer un threshold ni entrer dans un
chiffre publie: elles repondent a une seule question, celle de la taille d'echantillon.

    n=18 sur les graines d'origin donnait 0,833, avec un intervalle si large qu'on ne pouvait
    pas dire si le check manquait vraiment ou si trois tirages malheureux s'etaient suivis.

Deux sets, douze graines neuves chacun, une seule chose qui change entre eux:
    corner    300 dpi, JPEG 95, bruit 12
    control  300 dpi, JPEG 30, bruit 12
Le control est ce qui fait la difference entre "mes graines sont dures" et "c'est la
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
MARCHE_ANGLE = 0.5              # l'angle a partir duquel le recall decroche


def recalls(dossiers, ref, reg, threshold, cibles, var):
    """Retour: (tp, n, par angle)."""
    by_angle = collections.defaultdict(lambda: [0, 0])
    tp = n = 0
    for key, dossier in dossiers.items():
        sc = target_scores(dossier[var.name], ref, CONTROLE, reg)
        pos = {k: v for k, v in sc.items() if k in cibles} or sc
        for x in pos.values():
            n += 1
            tp += x > threshold
            g = by_angle[key[0]]
            g[0] += x > threshold
            g[1] += 1
    return tp, n, {a: tuple(g) for a, g in sorted(by_angle.items())}


def main():
    ref = load_reference()
    threshold = load_thresholds()[CONTROLE]
    reg = measured_settings()[CONTROLE]
    var = next(v for v in VARIANTS if v.check == CONTROLE)
    cibles = damaged_targets(var, ref)
    base = os.path.join(ROOT, "grid", "mesures")

    sets = {}
    principal = complete_dossiers(load(os.path.join(base, "mesures.jsonl")))
    sets["origin"] = {k: v for k, v in principal.items() if (k[1], k[2], k[3]) == CORNER}
    for name, fichier in (("corner", "suivi/mesures-corner.jsonl"),
                         ("control", "suivi/mesures-control.jsonl")):
        sets[name] = complete_dossiers(load(os.path.join(base, fichier)))

    out = {"check": CONTROLE, "threshold": threshold, "settings": reg.text_sensor,
           "corner": {"dpi": CORNER[0], "jpeg": CORNER[1], "sigma": CORNER[2]},
           "outside_protocol": "graines tirees apres avoir vu ou l'outil manquait; "
                             "ne deplacent aucun threshold et n'entrent dans aucun chiffre publie",
           "sets": {}}
    for name, d in sets.items():
        tp, n, by_angle = recalls(d, ref, reg, threshold, cibles, var)
        bas = [g for a, g in by_angle.items() if a < MARCHE_ANGLE]
        haut = [g for a, g in by_angle.items() if a >= MARCHE_ANGLE]
        out["sets"][name] = {
            "n_pairs": len(d), "tp": tp, "n": n, "recall": tp / max(1, n),
            "ci": list(wilson(tp, n)),
            "by_angle": {str(a): list(g) for a, g in by_angle.items()},
            "angle_below_step": [sum(g[0] for g in bas), sum(g[1] for g in bas)],
            "angle_above_step": [sum(g[0] for g in haut), sum(g[1] for g in haut)],
        }
    o, c = out["sets"]["origin"], out["sets"]["corner"]
    tp, n = o["tp"] + c["tp"], o["n"] + c["n"]
    bas = [o["angle_below_step"][i] + c["angle_below_step"][i] for i in (0, 1)]
    haut = [o["angle_above_step"][i] + c["angle_above_step"][i] for i in (0, 1)]
    out["combined"] = {"tp": tp, "n": n, "recall": tp / n, "ci": list(wilson(tp, n)),
                     "angle_below_step": bas + [bas[0] / bas[1]],
                     "angle_above_step": haut + [haut[0] / haut[1]],
                     "angle_step": MARCHE_ANGLE}
    dest = os.path.join(ROOT, "grid", "resultats", "suivi.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"corner q95   {c['tp']}/{c['n']} = {c['recall']:.4f} {[round(x,3) for x in c['ci']]}")
    print(f"control q30 {out['sets']['control']['tp']}/{out['sets']['control']['n']} = "
          f"{out['sets']['control']['recall']:.4f}")
    print(f"CUMULE     {tp}/{n} = {tp/n:.4f} {[round(x, 3) for x in out['combined']['ci']]}")
    print(f"  angle < {MARCHE_ANGLE}: {bas[0]}/{bas[1]}   angle >= {MARCHE_ANGLE}: {haut[0]}/{haut[1]}")
    print(f"-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
