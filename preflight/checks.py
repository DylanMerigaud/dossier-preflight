"""The checks: counter rejection, not extraction.

Each one returns a CONTINUOUS SCORE oriented the same way (higher = more reason to reject)
and compares it to a threshold. That single orientation is what makes it possible to plot a
precision/recall curve per check and READ the operating point off it, instead of picking a
number by hand.

THE LOSS IS ASYMMETRIC, AND IT IS DECLARED HERE:
  a FALSE NEGATIVE is the counter rejecting the dossier: months of delay, a summons to start
  again, sometimes a document to request again from a foreign administration.
  a FALSE POSITIVE is the gate crying on a clean dossier: people stop believing it, and a rule
  that cries wolf makes every rule next to it get skimmed.
The first costs more than the second, but the second destroys the tool. The retained operating
point therefore aims for the highest ATTAINABLE recall at a held false positive rate, and that
held rate is written in thresholds.json next to each value.
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
    """The nuisance parameters the grid sweeps, not decision thresholds."""
    min_conf: float = 40.0
    disc_ratio: float = 0.42
    ink_threshold: int = 160
    signature_sensor: str = "components"     # "components" or "ink", A/B duel
    text_sensor: str = "union"               # "page", "zone", "union" or "ink", A/B duel


@dataclass(frozen=True)
class Finding:
    check: str
    piece: str
    target: str
    score: float          # None when the check cannot conclude
    fires: bool
    detail: str = ""


def _alnum(words):
    """The number of ADDED alphanumeric characters read inside the zone.

    This is the measurement behind the "required field" check, and it replaced "confidence of
    the most confident word" after measurement: on the Cerfa, per zone OCR reads the field
    borders as three vertical bars at confidence 97. Confidence therefore said "this field is
    filled" about an EMPTY field, which is a false negative, the expensive side of the
    asymmetry. A vertical bar carries no alphanumeric character; a surname carries thirteen.
    """
    return sum(len(re.sub(r"[^0-9A-Za-z]", "", m[0])) for m in words)


def _key(t):
    return re.sub(r"[^0-9a-z]", "", normalize(t))


def _tokens(texts):
    return {j for t in texts for j in re.findall(r"[0-9a-z]+", normalize(t)) if len(j) >= 2}


def _overlap(a, b):
    """Is everything the smaller reading says also said by the larger one.

    Two choices, both paid for by measurement:
      - similarity and not equality. The Cerfa gets read as "LDES ACACIAS": the field's left
        border sticks to the word, and EXACT token overlap then drops to 0.50 on a CLEAN
        dossier. "ldes" against "des" is similar at 0.86.
      - the WORST token, not the mean. On the diverging address the mean is pulled up by the
        tokens that still coincide and the separation falls to 0.07 against 0.37. The worst
        token gives 0.14 against 0.73: what we are looking for is ONE piece of data diverging,
        not the overall similarity of two documents.
    """
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return min(max(_similarity(x, y) for y in large) for x in small)


def _similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _best_ngram(words, target, n_max=4):
    """The best similarity between a wanted value and a run of words read on the page.

    The length filter is not a free optimisation: two strings whose lengths differ by a factor
    of two cannot be more than 2/3 similar, so comparing them cannot change the maximum. It is
    what keeps the grid sweep down to minutes instead of hours.
    """
    goal = _key(target)
    if not goal or not words:
        return 0.0
    texts = [m[0] for m in sorted(words, key=lambda m: (m[2] // 20, m[1]))]
    keys = [_key(t) for t in texts]
    best = 0.0
    for n in range(1, min(n_max, len(keys)) + 1):
        for i in range(len(keys) - n + 1):
            run = "".join(keys[i:i + n])
            if not run or not (0.5 * len(goal) <= len(run) <= 2.0 * len(goal)):
                continue
            best = max(best, _similarity(run, goal))
    return best


_ZONE_MEMO = {}


def zones(tpl):
    key = (tpl.pdf, tpl.page)
    if key not in _ZONE_MEMO:
        _ZONE_MEMO[key] = declared_zones(tpl.pdf, tpl.page)
    return _ZONE_MEMO[key]


def _read_date(reading, tpl, name, settings):
    """The date as it is REALLY printed, not the one the PDF claims to carry."""
    z = zones(tpl).get(name)
    if z is None:
        return None, ""
    words = reading.zone_words(z, settings.min_conf, sensor=settings.text_sensor)
    raw = " ".join(m[0] for m in sorted(words, key=lambda m: m[1]))
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 8:
        return None, raw
    shape = "%m%d%Y" if tpl.date_format == "us" else "%d%m%Y"
    try:
        return dt.datetime.strptime(digits, shape).date(), raw
    except ValueError:
        return None, raw


# Each check only depends on a handful of settings. The analysis uses this to sweep only what
# matters: sweeping all 288 combinations for the nine checks would cost 288 full evaluations
# where 12 are enough for the required-field check.
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
    """The settings the grid retained, one per check. Fallback: the spike values."""
    from .thresholds import load_settings
    base = Settings()
    return {c: replace(base, **{k: v for k, v in (load_settings().get(c) or {}).items()
                                if hasattr(base, k)})
            for c in CHECKS}


def evaluate(readings, ref, clock="filing", settings=None, thresholds=None, checks=None,
             abstention=True):
    """Every finding of a dossier, at a given clock and a given set of thresholds.

    `checks` restricts the computation: the grid analysis calls this same code one check at a
    time, so that a check never has two implementations, the one that ships and the one that
    is measured.

    `abstention=False` DISABLES the refusal to judge a piece below the floor, and the grid
    uses that to choose the floor in the first place. Without the switch there is a loop:
    abstention reads the resolution threshold, the domain search measures checks that abstain
    and therefore miss nothing, the domain widens to the lowest dpi, and the resolution
    threshold follows it down. Measured 2026-08-21: the domain fell from 150 to 96 dpi from one
    publication to the next, and would have climbed back at the following one. A measurement
    cannot depend on the behaviour it is used to tune.
    """
    from .thresholds import load_thresholds
    thresholds = thresholds or load_thresholds()
    active = set(checks) if checks is not None else set(CHECKS)
    # settings=None means "take what the grid measured", and that is the normal mode. The grid
    # itself passes explicit settings, since sweeping them is precisely its job.
    per_check = {c: settings for c in CHECKS} if settings is not None else measured_settings()
    floor = -thresholds["resolution"]
    ref_date = ref.clock(clock)
    out = []
    for piece_id, template_name in ref.pieces:
        reading = readings.get(piece_id)
        if reading is None:
            continue
        tpl = ref.templates[template_name]
        Z = zones(tpl)
        # A PIECE BELOW THE FLOOR IS NOT JUDGED, IT IS FLAGGED. The checks that READ abstain,
        # with a score of None meaning "undecidable" and not "compliant". Measured 2026-08-21
        # without this rule: consistency fired on 52.8% of the dossiers carrying a piece at 72
        # dpi, comparing tokens it had not managed to read. That was not a threshold error, it
        # was an answer to a question that should not have been asked. The resolution check
        # does fire: that is its job.
        unreadable = abstention and reading.source_dpi < floor

        # C1 required field never filled. Sensor: WORD POSITIONS, not ink. The spike measured
        # that an EMPTY text field still reads +2.44% ink against +4.5% for a filled one.
        reads_text = per_check["required_field"].text_sensor != "ink"
        for role in (tpl.required if "required_field" in active else ()):
            for name in tpl.field_ids(role):
                z = Z.get(name)
                if z is None:
                    continue
                if unreadable and reads_text:
                    out.append(Finding("required_field", piece_id, name, None, False,
                                       "piece below the resolution floor"))
                    continue
                r = per_check["required_field"]
                if r.text_sensor == "ink":
                    # The sensor the spike accused: ink added inside the zone. It does not know
                    # what is written, only that something is darker than before, and a dirty
                    # border is enough to make it lie.
                    d = reading.field_ink.get(name, {}).get(str(r.ink_threshold))
                    if d is None:
                        continue
                    score, detail = -float(d), f"ink {d:+.2f}"
                else:
                    words = reading.zone_words(z, r.min_conf, sensor=r.text_sensor)
                    score, detail = -float(_alnum(words)), " ".join(m[0] for m in words)[:40]
                out.append(Finding("required_field", piece_id, name, score,
                                   score > thresholds["required_field"], detail))

        # C2 required checkbox left unticked. Differential ink inside a CENTRAL disc: the box
        # outline stays outside, otherwise we measure the form and not the tick.
        for role in (tpl.required_boxes if "required_checkbox" in active else ()):
            name = tpl.boxes[role]
            r = per_check["required_checkbox"]
            d = reading.boxes.get(name, {}).get(f"{r.disc_ratio}|{r.ink_threshold}")
            if d is None:
                continue
            out.append(Finding("required_checkbox", piece_id, name, -d,
                               -d > thresholds["required_checkbox"], f"delta {d:+.1f}"))

        # C3 missing signature. Two competing sensors, the duel is settled by the grid.
        for role in (tpl.required_signatures if "signature" in active else ()):
            name = tpl.signatures[role]
            r = per_check["signature"]
            v = reading.signatures.get(name, {}).get(str(r.ink_threshold))
            if v is None:
                continue
            rate, n, area, diag = v
            score = -diag if r.signature_sensor == "components" else -rate
            out.append(Finding("signature", piece_id, name, score,
                               score > thresholds["signature"],
                               f"rate {rate:+.1f} n {n} diag {diag:.0f}"))

        # C4 expired ON THE DAY OF FILING. Two clocks: the same piece can be good for one
        # dossier and expired for another at the very same instant, and it is the clock that
        # decides, never an implicit today.
        for role, kind in (tpl.dates.items() if "expiry" in active else ()):
            if kind != "expiration":
                continue
            for name in tpl.field_ids(role):
                if unreadable:
                    out.append(Finding("expiry", piece_id, name, None, False,
                                       "piece below the resolution floor"))
                    continue
                date, raw = _read_date(reading, tpl, name, per_check["expiry"])
                if date is None:
                    out.append(Finding("expiry", piece_id, name, None, False,
                                       f"unreadable {raw[:24]!r}"))
                    continue
                days = (ref_date - date).days
                out.append(Finding("expiry", piece_id, name, float(days),
                                   days > thresholds["expiry"],
                                   f"{date} vs {clock} {ref_date}"))

        # C7 below the resolution floor. The dpi is not read from metadata (a real scan has
        # none): it is ESTIMATED from the scale that registers the page onto the blank.
        if "resolution" in active:
            out.append(Finding("resolution", piece_id, "", -reading.source_dpi,
                               -reading.source_dpi > thresholds["resolution"],
                               f"{reading.source_dpi:.0f} estimated dpi"))
        # C8 cropped page.
        if "cropped_page" in active:
            out.append(Finding("cropped_page", piece_id, "", 1.0 - reading.coverage,
                               1.0 - reading.coverage > thresholds["cropped_page"],
                               f"coverage {reading.coverage:.3f}"))
        # C9 rotated page. Continuous score: by how much the chosen quarter turn beats the
        # original one.
        if "rotated_page" in active:
            out.append(Finding("rotated_page", piece_id, "", reading.orientation_margin,
                               reading.orientation_margin > thresholds["rotated_page"],
                               f"quarter turns {reading.quarter_turns}"))

        # C6 forbidden value reappearing. Compared on the BARE form (no separators): a
        # forbidden number stays forbidden whether printed 999-99-9999 or 999999999.
        page_words = (reading.all_words(per_check["forbidden_value"].min_conf)
                      if "forbidden_value" in active and not unreadable else [])
        for val in (ref.forbidden_values if "forbidden_value" in active else ()):
            if unreadable:
                out.append(Finding("forbidden_value", piece_id, val, None, False,
                                   "piece below the resolution floor"))
                continue
            s = _best_ngram(page_words, val)
            out.append(Finding("forbidden_value", piece_id, val, s,
                               s > thresholds["forbidden_value"], f"similarity {s:.2f}"))

    # C5 the same data diverging between two pieces. Measured by TOKEN OVERLAP, without going
    # through the reference: two pieces can contradict each other even when neither of them is
    # the one that was expected.
    for cons in (ref.consistencies if "consistency" in active else ()):
        read = []
        unreadable_pieces = []
        for side in cons["readings"]:
            reading = readings.get(side["piece"])
            if reading is None:
                continue
            if abstention and reading.source_dpi < floor:
                unreadable_pieces.append(side["piece"])
                continue
            tpl = ref.templates[dict(ref.pieces)[side["piece"]]]
            for name in tpl.field_ids(side["field"]):
                z = zones(tpl).get(name)
                if z is not None:
                    rc = per_check["consistency"]
                    read.append((side["piece"], _tokens(
                        m[0] for m in reading.zone_words(z, rc.min_conf, sensor=rc.text_sensor))))
        if unreadable_pieces:
            out.append(Finding("consistency", "+".join(unreadable_pieces), cons["data"], None,
                               False, "piece below the resolution floor"))
            continue
        for i in range(len(read)):
            for j in range(i + 1, len(read)):
                (pa, a), (pb, b) = read[i], read[j]
                overlap = _overlap(a, b)
                out.append(Finding("consistency", f"{pa}+{pb}", cons["data"], 1.0 - overlap,
                                   1.0 - overlap > thresholds["consistency"],
                                   f"{sorted(a)} vs {sorted(b)}"[:70]))
    return out
