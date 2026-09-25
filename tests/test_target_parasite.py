"""shape_for: the fold-shape blind spot the archival run (T12) exists to close.

Plain `seed % 3` never looks at the cell, so with the 3 seeds this generator uses (11, 23, 37)
two of them collide on the same index into `sorted(SHAPES)` and the shape at index 0 never runs,
at any cell, for any variant. `--all-shapes` folds the cell index into the draw so every shape
appears across the 27 cells. This file tests the shape draw only, not the read pipeline: a real
reading is exercised by the archival run itself, not by a fast unit test.
"""
from grid.run import SEEDS
from grid.target_parasite import CELLS, shape_for
from preflight import parasite


def test_seed_only_skips_a_shape_over_the_real_seed_set():
    shapes = sorted(parasite.SHAPES)
    seen = {shape_for(s, ci, all_shapes=False) for s in SEEDS for ci in range(len(CELLS))}
    assert seen != set(shapes), "seed alone was expected to miss at least one shape"
    assert shapes[0] not in seen, "the first sorted shape (fold) is the one seed % 3 always misses"


def test_all_shapes_covers_every_shape_over_the_real_seed_and_cell_set():
    shapes = sorted(parasite.SHAPES)
    seen = {shape_for(s, ci, all_shapes=True) for s in SEEDS for ci in range(len(CELLS))}
    assert seen == set(shapes), "all_shapes must exercise every parasite shape"


def test_all_shapes_is_deterministic():
    for s in SEEDS:
        for ci in range(len(CELLS)):
            assert shape_for(s, ci, True) == shape_for(s, ci, True)


def test_plain_seed_rule_ignores_the_cell_index():
    # the byte-identical replay (T12) depends on this: with all_shapes=False the cell index must
    # never change the answer, so a --dump-only run reproduces the committed aggregate exactly.
    shapes = sorted(parasite.SHAPES)
    for s in SEEDS:
        want = shapes[s % len(shapes)]
        for ci in range(len(CELLS)):
            assert shape_for(s, ci, False) == want
