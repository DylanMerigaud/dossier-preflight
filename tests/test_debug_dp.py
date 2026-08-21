from preflight.controles import evaluer
def test_debug(lectures, referentiel):
    from preflight.seuils import charger_seuils
    from preflight.controles import reglages_mesures
    r = reglages_mesures()["champ_requis"]
    print("\nreglage:", r.capteur_texte, r.seuil_encre, "seuil:", charger_seuils()["champ_requis"])
    cons = evaluer(lectures["sain"], referentiel, "guichet", controles=["champ_requis"])
    for c in sorted(cons, key=lambda c: -c.score)[:5]:
        print(f"  {'CRIE' if c.declenche else '    '} {c.piece:10s} {str(c.cible)[:24]:26s} {c.score:9.3f} {c.detail}")
