"""
The capability probes: every method runs on exactly these pairs.  Bases: the universe (2 to 4),
the synthetic dataset (every shape at 6, the sample at 9, the rule's shapes at 12 to 65, each
with its repeat versions), and real variants of each log (evaluation/probe_sets.py).

  paths      each edit grown from the start, the middle and the end of every sequence, and
             inside every block (evaluation.probes.paths_on; from 12 on at sizes 1, 2, 4, ... and the
             largest)
  one_step   every edit at its smallest size, at the first, the middle and the last place in
             reading order where it can go
  count      1, 2, 4, 8, ... separate edits of one type on separate activities, packed from
             the start, around the middle, or towards the end
  form       the same variant written differently: every block's children reversed
  renamed    a one-step pair with every activity renamed (to the next activity name in sorted
             order): the distance must not change
  combo      one edit, then a second of another kind (a swap, a missing activity, two
             activities made parallel) on other activities: the second must not bring the
             variant closer
  named      named cases of two edits interacting

Stacked edits are built as operations on labels (evaluation.probes.Edit.op, .touched): the base's
activities are tagged so each is unique, the candidate edits of the base are put in reading order,
and each is applied in turn to the current tree if it touches no activity used before.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation import probes
from evaluation.probes import _leaf_paths, _leaves, _node, _set_children, order, single_edits
from rotation_hrr.tree_utils import tree_to_sequence
from rotation_hrr.variant_enumeration import PAR, SEQ, canon, canonicalize, deep_copy, is_leaf, leaf, n_leaves, par, seq

TAG = "\x01"
COUNTS = (1, 2, 4, 8, 16, 32, 64)
POSITIONS = ("start", "middle", "end")
APPLICABLE = {"move": "swap", "missing": "remove", "relabel": "relabel", "repetition": "repeat",
              "seq_to_par": "par", "joins": "join", "nesting": "chain", "alongside": "alongside"}
COMBO_TYPES = ("move", "missing", "seq_to_par")
DELTA = {"remove": -1, "repeat": 1}


@dataclass
class Pair:
    kind: str           # paths | one_step | count | form | renamed | combo | named
    edit: str           # the edit (or case) name
    a: object
    b: object
    size: int = 1       # edit size, or count
    position: str = ""  # start | middle | end | whole
    path: int = -1      # which path or sequence of pairs this belongs to (paths, count, combo)
    expect: str = "apart"   # apart | same (should be 0) | not_closer (combo: compared with the
                            # pair before it in the same path)


# ---------------------------------------------------------------------------
# Tags and operations
# ---------------------------------------------------------------------------


def tag(t):
    """A copy whose activities are unique: label + TAG + reading position."""
    t = order(deep_copy(t))
    for k, x in enumerate(_leaves(t)):
        x.label = f"{x.label}{TAG}{k}"
    return t


def untag(t):
    t = deep_copy(t)
    for x in _leaves(t):
        x.label = x.label.split(TAG, 1)[0]
    return order(t)


def _find(t, lab):
    for p in _leaf_paths(t):
        if _node(t, p).label == lab:
            return p
    return None


def apply_op(t, op, fresh: str = "#new"):
    """The tree with *op* applied (evaluation.probes.Edit.op), or None if it no longer applies."""
    kind = op[0]
    t = deep_copy(t)
    if kind == "relabel":
        p = _find(t, op[1])
        if p is None:
            return None
        _node(t, p).label = fresh + TAG + op[1]
        return order(t)
    if kind == "relabel_to":                                     # named case 5
        p = _find(t, op[1])
        if p is None:
            return None
        _node(t, p).label = op[2] + TAG + "to" + op[1]
        return order(t)
    labs = [x for x in op[1:] if isinstance(x, str)]
    if kind == "alongside":
        labs = [op[1], *op[2]]
    paths = [_find(t, x) for x in labs]
    if any(p is None for p in paths):
        return None
    n0 = n_leaves(t)
    if kind == "remove":
        p = paths[0]
        if not p:
            return None
        kids = list(_node(t, p[:-1]).children)
        kids.pop(p[-1])
        _set_children(_node(t, p[:-1]), kids)
    elif kind == "repeat":
        p = paths[0]
        if not p:
            t = seq(t, leaf(op[1]))
        else:
            kids = list(_node(t, p[:-1]).children)
            kids.insert(p[-1] + 1, leaf(op[1]))
            _set_children(_node(t, p[:-1]), kids)
    else:
        parent = {p[:-1] for p in paths if p}
        if len(parent) != 1 or any(not p for p in paths):
            return None
        q = parent.pop()
        node = _node(t, q)
        idx = sorted(p[-1] for p in paths)
        kids = list(node.children)
        if kind == "swap":
            if node.op != SEQ or idx[1] - idx[0] != 1:
                return None
            kids[idx[0]], kids[idx[1]] = kids[idx[1]], kids[idx[0]]
        elif kind == "par":
            if node.op != SEQ or idx != list(range(idx[0], idx[0] + len(idx))):
                return None
            kids[idx[0]:idx[-1] + 1] = [par(*kids[idx[0]:idx[-1] + 1])]
        elif kind == "join":
            i, j = paths[0][-1], paths[0][-1] + op[2]
            if node.op != SEQ or not (0 <= j < len(kids)) or is_leaf(kids[j]) or kids[j].op != PAR:
                return None
            lo, hi = min(i, j), max(i, j)
            kids[lo:hi + 1] = [par(*kids[lo:hi + 1])]
        elif kind == "chain":
            if node.op != PAR or not all(is_leaf(c) for c in kids):
                return None
            chain = seq(*[kids[i] for i in [p[-1] for p in paths]])
            kids = [c for i, c in enumerate(kids) if i not in idx] + [chain]
        elif kind == "alongside":
            if node.op != SEQ or idx != list(range(idx[0], idx[0] + len(idx))):
                return None
            c = kids[paths[0][-1]]
            chain = [kids[p[-1]] for p in paths[1:]]
            kids[idx[0]:idx[-1] + 1] = [par(c, seq(*chain))]
        else:
            return None
        _set_children(node, kids)
    new = canonicalize(t)
    if new is None or n_leaves(new) != n0 + DELTA.get(kind, 0):
        return None
    return order(new)


# ---------------------------------------------------------------------------
# Candidate edits in reading order
# ---------------------------------------------------------------------------


def candidates(tb):
    """The base's smallest edits that can be stacked, by edit type, each with the reading
    positions of the activities it touches."""
    idx = {lab: k for k, lab in enumerate(tree_to_sequence(tb))}
    plain = canon(untag(tb))
    out: dict = {}
    for e in single_edits(tb, smallest=True):
        if not e.op or e.op[0] != APPLICABLE.get(e.edit):
            continue
        if canon(untag(e.edited)) == plain:      # e.g. two copies of one activity swapped: no edit
            continue
        ks = [idx[x] for x in e.touched if x in idx]
        if ks:
            out.setdefault(e.edit, []).append((min(ks), max(ks), e))
    return out, len(idx)


def in_order(cands, position: str, n: int):
    """start: from the first activity on; end: from the last back; middle: nearest the centre."""
    if position == "start":
        key = lambda c: (c[0], c[1])
    elif position == "end":
        key = lambda c: (-c[1], -c[0])
    else:
        key = lambda c: (abs((c[0] + c[1]) / 2 - (n - 1) / 2), c[0])
    return [c[2] for c in sorted(cands, key=key)]


def stack(tb, ordered, limit=None, used=None):
    """Apply the edits in turn, each only if it touches no activity used before and still
    applies; the trees after 1, 2, 3, ... edits."""
    used = set() if used is None else set(used)
    cur, out, k = tb, [], 0
    for e in ordered:
        if limit is not None and len(out) >= limit:
            break
        if e.touched & used:
            continue
        new = apply_op(cur, e.op, fresh=f"#new{k}")
        if new is None or canon(untag(new)) == canon(untag(cur)):   # no change once untagged
            continue
        k += 1
        cur, used = new, used | e.touched
        out.append((e, cur))
    return out


# ---------------------------------------------------------------------------
# The probe kinds
# ---------------------------------------------------------------------------


def one_steps(t, cands, n):
    """Every edit at its smallest size at the first, middle and last place in reading order."""
    out = []
    for edit, cs in cands.items():
        for pos in POSITIONS:
            e = in_order(cs, pos, n)[0]
            out.append(Pair("one_step", edit, t, untag(e.edited), e.size, pos))
    seen, uniq = set(), []                       # a short variant can give one place three times
    for p in out:
        key = (p.edit, repr(p.b))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def count_paths(t, tb, cands, n, path_id):
    out = []
    for edit, cs in cands.items():
        for pos in POSITIONS:
            steps = stack(tb, in_order(cs, pos, n))
            counts = [c for c in COUNTS if c <= len(steps)]
            if len(counts) < 2:
                continue
            path_id[0] += 1
            out += [Pair("count", edit, t, untag(steps[c - 1][1]), c, pos, path_id[0]) for c in counts]
    return out


def reversed_blocks(t):
    """The same variant written differently: every block's children in reverse order (not
    sorted again)."""
    t = deep_copy(t)
    stack_ = [t]
    while stack_:
        x = stack_.pop()
        if is_leaf(x):
            continue
        if x.op == PAR:
            _set_children(x, list(reversed(x.children)))
        stack_.extend(x.children)
    return t


def renamed(t, mapping):
    t = deep_copy(t)
    for x in _leaves(t):
        x.label = mapping.get(x.label, x.label)
    return order(t)


def combos(t, tb, cands, n, path_id):
    """One edit, then a second of another kind on other activities."""
    out = []
    for pos in POSITIONS:
        for t1 in COMBO_TYPES:
            for t2 in COMBO_TYPES:
                if t1 == t2 or t1 not in cands or t2 not in cands:
                    continue
                first = stack(tb, in_order(cands[t1], pos, n), limit=1)
                if not first:
                    continue
                e1, cur1 = first[0]
                second = stack(cur1, in_order(cands[t2], pos, n), limit=1, used=e1.touched)
                if not second:
                    continue
                path_id[0] += 1
                out += [Pair("combo", f"{t1}+{t2}", t, untag(cur1), 1, pos, path_id[0]),
                        Pair("combo", f"{t1}+{t2}", t, untag(second[0][1]), 2, pos, path_id[0],
                             "not_closer")]
    return out


def named(t, tb, cands, n):
    """The named cases, each at the start, the middle and the end where it applies."""
    out = []
    labs = [x.label for x in _leaves(tb)]
    for pos in POSITIONS:
        if "seq_to_par" in cands:                      # 1. a swap inside a block just made
            first = stack(tb, in_order(cands["seq_to_par"], pos, n), limit=1)
            if first:
                made = untag(first[0][1])
                out.append(Pair("named", "swap inside a new block", made, reversed_blocks(made),
                                position=pos, expect="same"))
        if "repetition" in cands and "missing" in cands:   # 2. repetition plus missing
            rep = stack(tb, in_order(cands["repetition"], pos, n), limit=1)
            if rep:
                gone = stack(rep[0][1], in_order(cands["missing"], pos, n), limit=1,
                             used=rep[0][0].touched)
                if gone:
                    out.append(Pair("named", "repetition plus missing", t, untag(gone[0][1]),
                                    position=pos))
        if "nesting" in cands:                         # 3. nesting plus a swap of the chain
            e = in_order(cands["nesting"], pos, n)[0]
            ab = apply_op(tb, e.op)
            ba = apply_op(tb, (e.op[0], e.op[2], e.op[1]) + tuple(e.op[3:]))
            if ab is not None and ba is not None:
                out.append(Pair("named", "nesting plus a swap", untag(ab), untag(ba), position=pos))
        if "missing" in cands and "move" in cands:     # 4. swap plus missing against missing alone
            gone = stack(tb, in_order(cands["missing"], pos, n), limit=1)
            if gone:
                sw = stack(gone[0][1], in_order(cands["move"], pos, n), limit=1,
                           used=gone[0][0].touched)
                if sw:
                    out.append(Pair("named", "swap plus missing against missing", untag(gone[0][1]),
                                    untag(sw[0][1]), position=pos))
        if "relabel" in cands and len(set(x.split(TAG)[0] for x in labs)) > 1:   # 5.
            e = in_order(cands["relabel"], pos, n)[0]
            src = e.op[1].split(TAG)[0]
            other = next((x.split(TAG)[0] for x in labs if x.split(TAG)[0] != src), None)
            new = apply_op(tb, ("relabel_to", e.op[1], other))
            if new is not None:
                out.append(Pair("named", "renamed to an activity already present", t, untag(new),
                                position=pos))
    return out


def probes_of(t, path_id, rename_map=None, thin=False):
    """Every probe on base *t* (paths thinned with *thin*, evaluation/probes.py)."""
    t = order(t)
    tb = tag(t)
    cands, n = candidates(tb)
    out: list[Pair] = []
    for (edit, _, _), steps in probes.paths_on(t, thin).items():
        if steps:
            path_id[0] += 1
            out += [Pair("paths", edit, e.base, e.edited, e.size, e.position, path_id[0]) for e in steps]
    singles = one_steps(t, cands, n)
    for p in singles:                                  # an id shared with its renamed twin
        path_id[0] += 1
        p.path = path_id[0]
    out += singles
    out += count_paths(t, tb, cands, n, path_id)
    if any(not is_leaf(x) and x.op == PAR for x in [_node(t, p) for p in probes._paths(t)]):
        out.append(Pair("form", "blocks reversed", t, reversed_blocks(t), expect="same"))
    if rename_map:
        out += [Pair("renamed", p.edit, renamed(p.a, rename_map), renamed(p.b, rename_map), p.size,
                     p.position, p.path, expect="as one_step") for p in singles]
    out += combos(t, tb, cands, n, path_id)
    out += [p for p in named(t, tb, cands, n)          # a case that should differ must differ (e.g.
            if p.expect != "apart" or canon(p.a) != canon(p.b)]   # A repeated, another A removed)
    return out


def rename_map(labels) -> dict:
    """Each activity to the next activity name in sorted order (the last to the first)."""
    s = sorted(set(labels))
    return {a: s[(i + 1) % len(s)] for i, a in enumerate(s)} if len(s) > 1 else {}


__all__ = ["COUNTS", "Pair", "apply_op", "candidates", "count_paths", "named", "probes_of",
           "rename_map", "reversed_blocks", "stack", "tag", "untag"]
