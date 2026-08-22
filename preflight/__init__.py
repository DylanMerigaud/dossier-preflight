"""dossier-preflight: is this dossier going to be rejected at the counter.

A "dossier" is a set of supporting documents filed together with an administration, and a
"piece" is one document in it. Both words are kept untranslated throughout: they are the
subject, and "file" and "document" lose the relation between the two.

Three properties carry the whole design, and all three came out of the spike:

  1. ANY coordinate-based check needs DESKEWING first. Raw ink measured inside a zone of a
     rotated scan reported 8 ticked boxes when nothing was ticked at all.
  2. Ink is the wrong sensor for TEXT. An empty field still reads +2.44% ink against +4.5%
     for a filled one: separable, but fragile. OCR word positions are clean (0 words
     against 3).
  3. The blank form is not just a fixture, it is the REFERENCE IMAGE. Every check is a
     differential against it, the pre-printed words read on the blank are subtracted, and
     the tool therefore only ever asserts something about what was ADDED.

The canonical frame is the blank rendered at CANON_DPI. A scan is brought into that frame by
registration (orientation, scale, translation) before a single coordinate is read. No
coordinate is measured by hand anywhere: AcroForm PDFs DECLARE their zones.
"""
CANON_DPI = 200
