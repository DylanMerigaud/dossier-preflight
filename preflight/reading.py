"""What gets MEASURED on a piece, once and for all, without deciding anything.

A Reading is serialisable and is enough to replay every check at any threshold. That is what
makes the degradation grid affordable: 16,000 image passes once, then thousands of operating
points swept over the recorded measurements. A sensor that already returned a boolean would
have locked its threshold inside its own code, and a locked threshold cannot be read off a
curve.
"""
import hashlib
import json
import logging
import os
from dataclasses import dataclass, asdict, field

from .sensors import (DISC_RATIOS, INK_THRESHOLDS, Word, components, disc_ink,
                      added_words, ocr_words, ocr_zone_words, ink_ratio)
from .degradation import apply
from .geometry import declared_zones
from .deskew import prepare
from .render import CACHE, render

logging.getLogger("pypdf").setLevel(logging.ERROR)

ZONE_MARGIN = 8       # zones are expanded before reading, in canonical-frame pixels
PREPRINTED_RADIUS = 22


@dataclass
class Reading:
    piece: str
    template: str
    angle: float
    quarter_turns: int
    source_dpi: float
    peak: float
    coverage: float
    orientation_margin: float
    words: list = field(default_factory=list)               # full page OCR: (text, cx, cy, conf, added)
    zone_words_by_field: dict = field(default_factory=dict)  # per zone OCR: field -> same 5-tuples
    boxes: dict = field(default_factory=dict)                # field -> {"ratio|threshold": delta}
    field_ink: dict = field(default_factory=dict)            # text field -> {"threshold": ink delta}
    signatures: dict = field(default_factory=dict)           # field -> {"threshold": [rate, n, area, diag]}

    def dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return Reading(**d)

    def zone_words(self, zone, min_conf=0.0, added_only=True, sensor="union"):
        """The words read inside a zone, by one of the three competing text sensors.

        "union" is not a soft compromise: the two sensors fail on DIFFERENT fields (full page
        OCR sees nothing inside the Cerfa's NoCarteID, per zone OCR misses one box of the W-9's
        split tax number), so their union misses less than either alone.
        """
        z = zone.expanded(ZONE_MARGIN)
        page = [m for m in self.words if z.contains(m[1], m[2])]
        zonal = self.zone_words_by_field.get(zone.name, [])
        source = {"page": page, "zone": zonal, "union": page + zonal}[sensor]
        # Deduplication on a 16 px grid: in union mode both sensors read the same word two or
        # three pixels apart, and counting it twice would inflate the character count, which
        # would make an empty field look filled.
        seen, out = set(), []
        for t, cx, cy, c, added in source:
            key = (t.lower(), int(cx) // 16, int(cy) // 16)
            if c < min_conf or (added_only and not added) or key in seen:
                continue
            seen.add(key)
            out.append((t, cx, cy, c))
        return out

    def all_words(self, min_conf=0.0, added_only=True):
        seen, out = set(), []
        for t, cx, cy, c, added in (list(self.words)
                                    + [m for v in self.zone_words_by_field.values() for m in v]):
            if c < min_conf or (added_only and not added) or (t, round(cx), round(cy)) in seen:
                continue
            seen.add((t, round(cx), round(cy)))
            out.append((t, cx, cy, c))
        return out


_BLANK_MEMO = {}


def blank(template):
    """The blank rendered in the canonical frame, with its pre-printed words.

    The blank's words go to disk: without that cache every grid worker pays 2.8 s of OCR per
    template at startup, and there are as many workers as cores.
    """
    key = (template.pdf, template.page, template.language)
    if key in _BLANK_MEMO:
        return _BLANK_MEMO[key]
    img = render(template.pdf, page=template.page)
    zones = declared_zones(template.pdf, template.page)
    os.makedirs(CACHE, exist_ok=True)
    fingerprint = hashlib.sha1(f"v2|{key}|{img.shape}".encode()).hexdigest()[:16]
    path = os.path.join(CACHE, f"words-{fingerprint}.json")
    if os.path.exists(path):
        d = json.load(open(path))
        words = [Word(*m) for m in d["page"]]
        by_zone = {k: [Word(*m) for m in v] for k, v in d["zones"].items()}
    else:
        words = ocr_words(img, template.language)
        by_zone = {c: ocr_zone_words(img, zones[c], template.language)
                   for c in template.all_fields if c in zones}
        tmp = path + f".{os.getpid()}"
        json.dump({"page": [[m.text, m.cx, m.cy, m.conf] for m in words],
                   "zones": {k: [[m.text, m.cx, m.cy, m.conf] for m in v]
                             for k, v in by_zone.items()}}, open(tmp, "w"))
        os.replace(tmp, path)
    _BLANK_MEMO[key] = (img, words, zones, by_zone)
    return _BLANK_MEMO[key]


def read_piece(piece, deg):
    """Render, degrade, deskew, register, measure. Returns a Reading.

    Nothing here compares against a reference and nothing crosses a threshold: deliberately.
    """
    blank_img, blank_words, zones, _ = blank(piece.template)
    raw = render(piece.pdf, dpi=deg.dpi, page=piece.template.page)
    prep = prepare(apply(raw, deg), blank_img)
    frame, scan, framed_blank = prep.frame, prep.frame.scan, prep.frame.blank
    scale = frame.scale

    # Words are READ at native resolution, then their centres are brought back into the
    # canonical frame: that frame is the one carrying the declared zones and the Reading format.
    def canon(words):
        return [Word(m.text, *frame.to_canonical(m.cx, m.cy), m.conf) for m in words]

    all_read = canon(ocr_words(scan, piece.template.language))
    added = {id(m) for m in added_words(all_read, blank_words, PREPRINTED_RADIUS)}
    # Only words falling inside a DECLARED, expanded zone are kept. Without that filter the
    # grid writes 500 MB of JSONL for 36 KB of useful words per page, and the price is written
    # in plain sight in LIMITES.md: a forbidden value reappearing OUTSIDE any declared field
    # will not be seen.
    boxes = [z.expanded(ZONE_MARGIN) for z in zones.values()]
    out = Reading(piece.id, piece.template.name, round(prep.angle, 3), prep.quarter_turns,
                  round(prep.source_dpi, 2), round(prep.peak, 4), round(prep.coverage, 4),
                  round(prep.orientation_margin, 4),
                  words=[(m.text, round(m.cx), round(m.cy), round(m.conf), id(m) in added)
                         for m in all_read if any(b.contains(m.cx, m.cy) for b in boxes)])

    for name in piece.template.all_fields:
        z = zones.get(name)
        if z is None:
            continue
        read = canon(ocr_zone_words(scan, frame.zone(z), piece.template.language))
        zone_added = {id(m) for m in added_words(read, blank_words, PREPRINTED_RADIUS)}
        out.zone_words_by_field[name] = [
            (m.text, round(m.cx), round(m.cy), round(m.conf), id(m) in zone_added) for m in read]
        # INK on a TEXT field, the third contender in the text sensor duel. The spike already
        # put it in doubt at n=1 (an empty field read +2.44% against +4.5 to +5.1 for a filled
        # one, separable but fragile); the grid replays the duel at scale.
        zs = frame.zone(z)
        out.field_ink[name] = {
            str(s): round(ink_ratio(scan, zs, s) - ink_ratio(framed_blank, zs, s), 3)
            for s in INK_THRESHOLDS}

    for name in piece.template.boxes.values():
        z = zones.get(name)
        if z is None:
            continue
        zs = frame.zone(z)
        out.boxes[name] = {
            f"{r}|{s}": round(disc_ink(scan, zs, r, s) - disc_ink(framed_blank, zs, r, s), 3)
            for r in DISC_RATIOS for s in INK_THRESHOLDS}
    for name in piece.template.signatures.values():
        z = zones.get(name)
        if z is None:
            continue
        zs = frame.zone(z)
        out.signatures[name] = {}
        for s in INK_THRESHOLDS:
            # Area and diagonal are converted to CANONICAL pixels: otherwise a signature read
            # at 96 dpi would have a diagonal half as long as the same one at 200 dpi, and the
            # threshold would stop meaning anything from one cell to the next.
            n, area, diag = components(scan, framed_blank, zs, s)
            out.signatures[name][str(s)] = [
                round(ink_ratio(scan, zs, s) - ink_ratio(framed_blank, zs, s), 3), n,
                round(area * scale * scale), round(diag * scale, 1)]
    return out
