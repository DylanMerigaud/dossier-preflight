"""Lancer les checks sur un VRAI dossier: des scans a soi, pas des fixtures.

    python -m preflight fixtures/reference.yaml \
        --clock filing \
        --piece tax=scans/w9.pdf --piece employment=scans/i9.pdf

TROIS VERDICTS ET PAS DEUX, et c'est le resultat de mesure le plus recent du depot. Un
check qui LIT s'abstient sur une piece sous le floor de resolution: son constat porte
un score None qui vaut INDECIDABLE, jamais "conforme". Les deux appellent des gestes opposes
au filing: un defaut dit REFAIS LE DOSSIER, une page illisible dit REFAIS LE SCAN. Ecraser
les deux dans un meme code de sortie dirait "ton dossier a un defaut" a quelqu'un dont le
dossier est peut-etre parfait et le scan mauvais.

    0   aucun constat
    1   au moins un DEFAUT DE DOSSIER, c'est-a-dire un check autre que resolution
    2   aucun defaut de dossier, mais l'outil ne sait pas read_piece: resolution se fires
        et/ou des checks se sont abstenus
    64  erreur d'usage (EX_USAGE), pour ne pas se confondre avec 2

Le check de resolution est du cote SCAN et pas du cote DOSSIER, et ce n'est pas un choix
de gout: LIMITES.md le dit deja pour lui seul, il repond "je ne sais pas read_piece cette page" et
pas "cette page est fautive". Ranger son declenchement parmi les defauts ferait sortir 1 sur
un dossier peut-etre parfait mal numerise. L'abstention a exactement la meme condition que
son declenchement (les deux lisent le meme floor), donc un code reserve au seul indecidable
ne se produirait jamais: les deux partagent le code 2, et le texte les distingue.

L'HORLOGE EST OBLIGATOIRE, et ce n'est pas de la ceremonie. La meme piece est bonne pour un
dossier et perimee pour l'autre au meme instant: le reference declare ses clocks par name
(filing, admissibility) et un outil qui prendrait la date du jour en silence jetterait la
seule propriete que ce depot outille et que les autres n'outillent pas.

LIMITE CONNUE DE --dpi. C'est le dpi de RASTERISATION du PDF, pas le dpi de capture du scan.
Sur un PDF qui contains deja une image, demander 300 ici ne recree pas l'information que le
scanner n'a pas prise: la page est rendue plus grande, et le check de resolution estime
alors la resolution du RENDU. Rasteriser haut ne fait donc pas passer le floor a un mauvais
scan, il deplace la question. Le defaut est CANON_DPI, la resolution du repere canonique, et
c'est la value sous laquelle tous les chiffres de LIMITES.md ont ete mesures.
"""
import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, replace

from . import CANON_DPI
from .checks import CHECKS, evaluate
from .degradation import Degradation
from .templates import ROOT
from .reading import read_piece, blank
from .reference import load_reference


@dataclass(frozen=True)
class ScannedPiece:
    """Le minimum que `read_piece()` demande. Volontairement pas la BuiltPiece de fixtures.py:
    le chemin de production ne doit pas dependre du generateur de dossiers synthetiques,
    sinon le point d'entree ne saurait tourner que sur des dossiers fabriques et aurait l'air
    de marcher sur un vrai."""
    id: str
    template: object
    pdf: str


# Aucune degradation: ni rotation, ni bruit, ni blur, ni recompression. `apply()` rend
# alors la page telle qu'elle a ete rasterisee. La grid degrade, la production non.
PRISTINE = Degradation(angle=0.0, jpeg=100, sigma=0.0, blur=0.0)

# Le seul check qui, en se declenchant, parle du SCAN et non du DOSSIER.
SCAN_SIDE = "resolution"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        """argparse sort 2 par defaut, or 2 veut dire "je ne sais pas read_piece" ici."""
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: erreur: {message}\n")
        sys.exit(64)


def _clock(ref, value):
    """Un name declare par le reference, ou une date ISO. Jamais la date du jour implicite."""
    if value in ref.clocks:
        return ref, value
    try:
        date = dt.date.fromisoformat(value)
    except ValueError:
        connues = ", ".join(sorted(ref.clocks)) or "aucune"
        raise SystemExit(f"clock inconnue {value!r}. Horloges declarees: {connues}. "
                         f"Sinon donner une date ISO (AAAA-MM-JJ).")
    return replace(ref, clocks={**ref.clocks, value: date}), value


def _pieces(ref, couples):
    """id=chemin, valide contre ce que le reference declare."""
    declarees = dict(ref.pieces)
    out = {}
    for c in couples:
        if "=" not in c:
            raise SystemExit(f"--piece attend id=chemin, recu {c!r}")
        pid, chemin = c.split("=", 1)
        if pid not in declarees:
            raise SystemExit(f"piece {pid!r} non declaree par le reference. "
                             f"Declarees: {', '.join(declarees)}")
        if not os.path.exists(chemin):
            raise SystemExit(f"piece {pid!r}: fichier introuvable {chemin!r}")
        out[pid] = ScannedPiece(pid, ref.templates[declarees[pid]], os.path.abspath(chemin))
    return out


def sort_findings(constats):
    """Trois tas: defaut de dossier, page illisible, et le reste."""
    defauts = [c for c in constats if c.fires and c.check != SCAN_SIDE]
    illisible = [c for c in constats
                 if (c.fires and c.check == SCAN_SIDE) or c.score is None]
    muets = [c for c in constats if not c.fires and c.score is not None]
    return defauts, illisible, muets


def _lines(constats):
    return [f"  {c.check:17s} {c.piece:12s} {str(c.target)[:26]:28s} {c.detail}"
            for c in sorted(constats, key=lambda c: (c.piece, c.check))]


def _text(constats, ref, nom_horloge, dpi, fournies, manquantes, tout):
    defauts, illisible, muets = sort_findings(constats)
    l = [f"dossier {ref.dossier}, clock {nom_horloge} ({ref.clock(nom_horloge)}), "
         f"{len(fournies)} piece(s) rendue(s) a {dpi} dpi"]
    if manquantes:
        l += ["", "PIECES NON FOURNIES, donc NON JUGEES (aucun constat ne les concerne): "
              + ", ".join(sorted(manquantes))]
    if defauts:
        l += ["", f"DEFAUTS DE DOSSIER ({len(defauts)}). Le filing refuserait, "
              "refaire le DOSSIER:"] + _lines(defauts)
        if {c.check for c in defauts} & {"cropped_page", "rotated_page"}:
            l += ["", "Une page coupee ou tournee peut venir du SCAN et pas du dossier. Ces "
                  "deux checks sont ranges du cote dossier parce que la grid les mesure "
                  "sur des pages vraiment abimees, pas parce qu'on sait d'ou vient l'abimage."]
    if illisible:
        abstenus = [c for c in illisible if c.score is None]
        l += ["", f"L'OUTIL NE SAIT PAS LIRE ({len(illisible)}). Ce n'est PAS \"conforme\", "
              "refaire le SCAN:"] + _lines(illisible)
        if abstenus:
            l += ["", f"{len(abstenus)} de ces constats sont des ABSTENTIONS: le check a "
                  "refuse de se prononcer sur une piece sous le floor de resolution. "
                  "Indecidable ne veut pas dire conforme."]
        if defauts:
            l += ["", "ATTENTION: des checks se sont tus faute de pouvoir read_piece. La liste "
                  "des defauts ci-dessus n'est donc pas complete."]
    if tout:
        l += ["", f"NE SE DECLENCHENT PAS ({len(muets)}):"] + _lines(muets)
    l.append("")
    if not defauts and not illisible:
        l += ["Aucun check ne se fires.",
              "CE N'EST PAS UNE GARANTIE. Le rappel et les faux positifs de chaque check,",
              "le domaine ou ils tiennent et ce que la mesure ne couvre pas sont dans",
              "LIMITES.md. En particulier: la mesure porte sur UN dossier fictif de trois",
              "formulaires degrades SYNTHETIQUEMENT, aucun scan reel n'y est entre."]
    return "\n".join(l)


def main(argv=None):
    ap = Parser(prog="python -m preflight",
                   description="Les checks de refus de filing, sur des scans a soi.",
                   epilog="Codes de sortie: 0 aucun constat, 1 defaut de dossier, "
                          "2 page illisible ou check abstenu, 64 erreur d'usage.")
    ap.add_argument("reference", help="YAML decrivant le dossier attendu et ses pieces")
    ap.add_argument("--piece", action="append", default=[], metavar="ID=CHEMIN",
                    help="le scan d'une piece declaree par le reference, repetable")
    ap.add_argument("--clock", required=True, metavar="NOM|AAAA-MM-JJ",
                    help="OBLIGATOIRE: un name d'clock du reference, ou une date ISO. "
                         "Une piece bonne a une date est perimee a l'autre.")
    ap.add_argument("--dpi", type=int, default=CANON_DPI,
                    help=f"dpi de rasterisation du PDF, pas de capture du scan "
                         f"(defaut {CANON_DPI})")
    ap.add_argument("--racine", default=ROOT,
                    help="dossier contenant templates/ et corpus/ (defaut: la racine du depot)")
    ap.add_argument("--tout", action="store_true",
                    help="lister aussi les checks qui ne se declenchent pas")
    ap.add_argument("--json", action="store_true", help="sortie machine")
    a = ap.parse_args(argv)

    if not a.piece:
        raise SystemExit("aucune piece fournie. Donner au moins un --piece ID=CHEMIN. "
                         "Ce point d'entree lit des scans reels, il ne genere pas de fixture.")
    ref = load_reference(a.reference, racine=a.racine)
    ref, nom_horloge = _clock(ref, a.clock)
    pieces = _pieces(ref, a.piece)
    manquantes = {p for p, _ in ref.pieces} - set(pieces)

    for _, nom_gab in ref.pieces:
        blank(ref.templates[nom_gab])
    readings = {pid: read_piece(p, replace(PRISTINE, dpi=a.dpi)) for pid, p in pieces.items()}
    constats = evaluate(readings, ref, nom_horloge)
    defauts, illisible, _ = sort_findings(constats)

    if a.json:
        print(json.dumps({
            "dossier": ref.dossier, "clock": nom_horloge,
            "date_horloge": str(ref.clock(nom_horloge)), "dpi_rendu": a.dpi,
            "pieces_jugees": sorted(pieces), "pieces_non_fournies": sorted(manquantes),
            "checks": list(CHECKS),
            "verdict": "defaut" if defauts else ("illisible" if illisible else "aucun_constat"),
            "constats": [{"check": c.check, "piece": c.piece, "target": str(c.target),
                          "score": c.score, "fires": c.fires,
                          "indecidable": c.score is None, "detail": c.detail}
                         for c in constats]}, ensure_ascii=False, indent=2))
    else:
        print(_text(constats, ref, nom_horloge, a.dpi, pieces, manquantes, a.tout))
    return 1 if defauts else (2 if illisible else 0)


if __name__ == "__main__":
    sys.exit(main())
