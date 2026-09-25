"""Which readings choose the thresholds, and which report them: a predicate on the cell key.

The published protocol calibrates on seeds 11 and 23 and reports on seed 37. The study around
this tool needs other splits (a held-out factor level, a held-out identity, another generator
as the report set, both generators pooled), and each one is a pair of predicates over the SAME
key grid/analyze.py already builds, never a new code path per protocol.

An expression is a small subset of Python syntax, PARSED here and never handed to eval():

    seed != 37
    source == "g1" and seed == 37
    source in ("g0", "g1") and seed in (11, 23)
    not (angle == 2.0 or dpi == 150)
    identity != "id03"

Names are the key fields of KEY_FIELDS, values are literals (numbers, strings, True, False,
None, or a tuple/list/set of them for `in`). Allowed: and, or, not, parentheses, ==, !=, <,
<=, >, >=, in, not in, chained comparisons. Anything else (a call, an attribute, a subscript,
arithmetic, an unknown name) is refused when the expression is parsed, before any row is read.
An ordering (<, <=, >, >=) against None is false rather than an error: capture and mark_step
are None on every generator reading, and "mark_step >= 1" must simply not select them.
"""
import ast
import operator

# The cell key grid/analyze.py load() builds, in its order. The first seven are the historical
# key (seed at 4, parasite at 5, identity at 6: see load()); the last four are appended so that
# readings of another source, of the jittered generator, or of a real capture never share a key
# with a G0 reading of the same factors.
KEY_FIELDS = ("angle", "dpi", "jpeg", "sigma", "seed", "parasite", "identity",
              "source", "jitter", "capture", "mark_step")
KEY_INDEX = {name: i for i, name in enumerate(KEY_FIELDS)}

def _ordered(op):
    """An ordering is false when either side is None (a field the row does not carry, such as
    mark_step on a generator reading), instead of raising halfway through a file."""
    return lambda a, b: a is not None and b is not None and op(a, b)


_COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: _ordered(operator.lt),
            ast.LtE: _ordered(operator.le), ast.Gt: _ordered(operator.gt),
            ast.GtE: _ordered(operator.ge),
            ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


class PredicateError(ValueError):
    pass


def _literal(node, text):
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool,
                                                                  type(None))):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return frozenset(_literal(e, text) for e in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) \
            and isinstance(node.operand, ast.Constant) \
            and isinstance(node.operand.value, (int, float)) \
            and not isinstance(node.operand.value, bool):
        return -node.operand.value
    raise PredicateError(f"{text!r}: only literals may stand here, got "
                         f"{type(node).__name__}")


def _operand(node, text):
    """A key field (returns its index) or a literal (returns ('lit', value))."""
    if isinstance(node, ast.Name):
        if node.id not in KEY_INDEX:
            raise PredicateError(f"{text!r}: unknown field {node.id!r}. Known: "
                                 + ", ".join(KEY_FIELDS))
        return ("field", KEY_INDEX[node.id])
    return ("lit", _literal(node, text))


def _compile(node, text, used):
    if isinstance(node, ast.Expression):
        return _compile(node.body, text, used)
    if isinstance(node, ast.BoolOp):
        parts = [_compile(v, text, used) for v in node.values]
        if isinstance(node.op, ast.And):
            return lambda k: all(p(k) for p in parts)
        return lambda k: any(p(k) for p in parts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _compile(node.operand, text, used)
        return lambda k: not inner(k)
    if isinstance(node, ast.Compare):
        operands = [_operand(node.left, text)] + [_operand(c, text) for c in node.comparators]
        ops = []
        for op in node.ops:
            if type(op) not in _COMPARE:
                raise PredicateError(f"{text!r}: operator {type(op).__name__} not allowed")
            ops.append(_COMPARE[type(op)])
        for kind, v in operands:
            if kind == "field":
                used.add(KEY_FIELDS[v])

        def value(o, k):
            return k[o[1]] if o[0] == "field" else o[1]

        def compare(k):
            for i, op in enumerate(ops):
                if not op(value(operands[i], k), value(operands[i + 1], k)):
                    return False
            return True
        return compare
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return lambda k, v=node.value: v
    raise PredicateError(f"{text!r}: {type(node).__name__} is not allowed in a predicate")


class Predicate:
    """A compiled expression: callable on a key tuple, with the fields it reads."""

    def __init__(self, text):
        self.text = text.strip()
        try:
            tree = ast.parse(self.text, mode="eval")
        except SyntaxError as e:
            raise PredicateError(f"{text!r}: {e.msg}") from None
        self.fields = set()
        self._fn = _compile(tree, self.text, self.fields)

    def __call__(self, key):
        return bool(self._fn(key))

    def __repr__(self):
        return f"Predicate({self.text!r})"


class Holdout:
    """(calibrate, report): the two sets a protocol chooses on and reports on.

    `on_parasite` says whether either side reads the parasite level. When one does, the
    analysis must NOT first cut the data down to level 0 (unparasited()): a fold whose report
    set is a non-zero level would otherwise be emptied before it is ever looked at.
    """

    def __init__(self, calibrate, report):
        self.calibrate = calibrate if isinstance(calibrate, Predicate) else Predicate(calibrate)
        self.report = report if isinstance(report, Predicate) else Predicate(report)
        self.on_parasite = "parasite" in (self.calibrate.fields | self.report.fields)

    def keeps(self, key):
        return self.calibrate(key) or self.report(key)

    def __repr__(self):
        return f"Holdout(calibrate={self.calibrate.text!r}, report={self.report.text!r})"
