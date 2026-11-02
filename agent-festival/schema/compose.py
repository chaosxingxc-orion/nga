#!/usr/bin/env python3
"""Execution-graph composition and attenuation check for L3 contracts (ADR-0001 §2.4, D10/D22/D24).

Given a graph of node contracts, an execution plan (seq / par tree) and the grants the
caller holds, this module computes the composed contract of the whole graph and decides
whether the graph may run under the caller's authority:

    requires(G)  = union of every node's atomic grants, worst effect per atom. A grant marked
                   supplied_by=upstream is a checked declaration, not a subtraction: some supplier
                   (source of an incoming edge, transitively along edges) must hold the same
                   (kind, selector, action) at an effect at least as severe, else the graph is
                   rejected. Edge existence alone verifies nothing.
    effects(G)   = worst level; compensation = weakest among nodes with a side effect
    bounds(G)    = max_seconds: seq sum / par max; every other bound: sum everywhere;
                   mixed max_cost currencies are an error, never silently dropped
    admissible   = every atomic grant in requires(G) is covered by a held grant with an
                   effect at least as severe, and the graph's bounds fit the parent's

Graph shape is checked before composing (grammar by execution-graph.schema.json, the rest here):
every node must be scheduled in the plan exactly once, and every supply edge [u, v] must have u run
strictly before v in a `seq` group (an edge between parallel siblings, or backwards, is
impossible at run time and is rejected). A `kind: agent` + `delegate` grant whose target is
not a node of this graph is rejected: the closure is only computable over modeled nodes, and
resolving a delegate to its published contract is L4 work (ADR-0001 §2.4, round 16).

Selector coverage in 0.1.0 is exact match on the canonical (whitespace-trimmed) selector.
That is sound for concrete selectors (never admits more than the parent holds) and not
complete; RFC 6570 `{var}` template selectors compare as literal text, so two grants that
share a template string are treated as covering each other regardless of how the variable
is later bound — the L3 runtime must bind template variables for parent and child from the
same context (documented boundary, round 16 F-3). The 0.2.0 grammar (D32) widens coverage.

Parallel budgets are split at issue time (D22): each child gets an equal share (integer floor
for counts, exact decimal for cost; time is not split) and is rejected if it declares more
than its share; there is no shared counter to race on.

`_expect_composed` may pin `effects`, `bounds`, the atom list `requires`, and `shares` (the per-leaf issued
budgets, which is where ROUND_DOWN in the split is observable: the graph-level sum check already rejects any
over-parent total, so only pinned shares make the rounding mode load-bearing). Every pin is all-or-nothing:
the whole value is compared, a partial `requires` list or a subset of leaves is a mismatch.

Exit 0 iff every examples/compose/valid/* passes (including its `_expect_composed` values) AND
every examples/compose/invalid/* is rejected for the reason its `_expect_match` names.

Usage:  python3 schema/compose.py            # run the example suite
        python3 schema/compose.py FILE...    # compose specific graph files
"""
import decimal
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import REGISTRY, _schema_errors, bounds_errors, contract_errors, grant_errors  # noqa: E402
from validate import load as load_json  # noqa: E402

HERE = Path(__file__).resolve().parent
GRAPH_SCHEMA = json.loads((HERE / "execution-graph.schema.json").read_text())
REGISTRY = REGISTRY.with_resource(GRAPH_SCHEMA["$id"], __import__("referencing").Resource.from_contents(GRAPH_SCHEMA))
LEVEL = {"none": 0, "reversible": 1, "irreversible": 2}
COMPENSATION_RANK = {"none": 0, "manual": 1, "automatic": 2}
SUMMED_BOUNDS = ("max_cost", "max_downstream_calls", "max_bytes_out")
TIME_BOUND = "max_seconds"
# Integer budgets (D22 rev, round 28): every bound is an integer in the unit's smallest denomination
# (e.g. USD-cents), schema-capped at SAFE_INT_MAX = 2^53-1 so every language implementation (JS Number,
# Go int64, Python int) represents it exactly. Sums are exact by construction; splits use integer floor
# division, remainder dropped, so N shares never sum above the parent. The decimal era (0.05 USD amounts,
# prec=50 traps) was retired when the domain went integer — see build-log round 28.
SAFE_INT_MAX = 9007199254740991


def dec(x):
    """Integer amount from a JSON number. An integer-valued float like 3.0 is the integer 3 (JSON has one
    number type; double charter). Finiteness is guaranteed upstream by validate.bounds_errors."""
    return int(x)


# ---------- grants ----------

def atomic_grants(grants: list[dict]) -> dict[tuple[str, str, str], str]:
    """Expand grants to {(kind, selector, action): effect}, keeping the worst effect per key."""
    out: dict[tuple[str, str, str], str] = {}
    for g in grants:
        kind = g["resource"]["kind"]
        selector = canonical_selector(g["resource"]["selector"])
        for action in g["actions"]:
            key = (kind, selector, action)
            if LEVEL[g["effect"]] > LEVEL.get(out.get(key, "none"), 0) or key not in out:
                out[key] = g["effect"]
    return out


def canonical_selector(selector: str) -> str:
    """0.1.0 canonical form is enforced at the gate (schema pattern + validate.selector_errors), so nothing is
    normalized here: two selectors cover each other iff they are the same string. 0.2.0 adds per-kind
    normalization (D32)."""
    return selector


def covers(held_key: tuple[str, str, str], wanted_key: tuple[str, str, str]) -> bool:
    """Whether a held grant covers a wanted grant. Exact match only in 0.1.0 (sound, not complete)."""
    return held_key == wanted_key


# ---------- composition ----------

class GraphShapeError(ValueError):
    """The graph document is malformed in a way that makes composition meaningless."""


def _merge_worst(into: dict[tuple[str, str, str], str], key: tuple[str, str, str], effect: str) -> None:
    if key not in into or LEVEL[effect] > LEVEL[into[key]]:
        into[key] = effect


def compose_requires(nodes: dict[str, dict], edges: list[list[str]], plan) -> tuple[dict, list[str]]:
    """requires(G) = union of every node's atomic grants, worst effect per atom; plus the errors from
    checking each `supplied_by: upstream` declaration.

    The flag does not subtract anything. Round 16 second pass showed that a *sound* subtraction (only
    when a supplier holds the same (kind, selector, action) at an effect >= the consumer's) is always a
    no-op on the union: whatever covers the consumer's grant is itself in requires(G) at that effect or
    worse. So the flag is a checked declaration: "an earlier node hands me this; I do not need the
    caller to grant it separately". It is verified along edges, transitively (A -> B -> C where only A
    holds X: B's and C's declarations both check out), and a false declaration is an error — a WRITE
    declared upstream of a supplier that only READs, a worse effect than the supplier's, or no supplier
    at all. Edge existence alone verifies nothing.
    """
    suppliers: dict[str, set[str]] = {}
    for src, dst in edges:
        suppliers.setdefault(dst, set()).add(src)
    effective: dict[str, dict[tuple[str, str, str], str]] = {}
    merged: dict[tuple[str, str, str], str] = {}
    errs: list[str] = []
    for node_id in plan_ids(plan):  # edges respect plan order, so every supplier was walked already
        held_upstream: dict[tuple[str, str, str], str] = {}
        for s in suppliers.get(node_id, ()):
            for key, effect in effective.get(s, {}).items():
                _merge_worst(held_upstream, key, effect)
        own: dict[tuple[str, str, str], str] = {}
        for g in nodes[node_id]["requires"]:
            for key, effect in atomic_grants([g]).items():
                _merge_worst(merged, key, effect)
                if g.get("supplied_by") != "upstream":
                    _merge_worst(own, key, effect)
                    continue
                kind, selector, action = key
                if key not in held_upstream:
                    errs.append(f"node {node_id} declares {kind}:{selector} action={action} as upstream-supplied, "
                                "but no supplier (source of an incoming edge) holds it with that action")
                elif LEVEL[held_upstream[key]] < LEVEL[effect]:
                    errs.append(f"node {node_id} declares {kind}:{selector} action={action} as upstream-supplied at "
                                f"effect {effect}, but its supplier holds it at {held_upstream[key]}")
                else:  # only a verified declaration counts as something this node can hand further downstream
                    _merge_worst(own, key, effect)
        effective[node_id] = own
    return merged, errs


def compose_effects(nodes: dict[str, dict]) -> dict:
    """Worst level wins; compensation is the weakest among nodes with a side effect.

    'none' ranks weakest, so "any node without compensation makes the graph uncompensable"
    (ADR-0001 §2.4) is already implied by taking the minimum; a separate branch for it was
    an equivalent mutant (round 15, M5) and was removed.
    """
    level = max((LEVEL[c["effects"]["level"]] for c in nodes.values()), default=0)
    level_name = next(k for k, v in LEVEL.items() if v == level)
    if level_name == "none":
        return {"level": "none"}
    comps = [c["effects"]["compensation"] for c in nodes.values() if c["effects"]["level"] != "none"]
    return {"level": level_name, "compensation": min(comps, key=lambda c: COMPENSATION_RANK[c])}


def compose_bounds(plan, nodes: dict[str, dict]) -> dict:
    """Fold bounds over the plan tree with exact integers. A bound absent on any leaf is absent on the result."""
    return _fold_bounds(plan, nodes)


def _fold_bounds(plan, nodes: dict[str, dict]) -> dict:
    if isinstance(plan, str):
        return normalize_bounds(nodes[plan]["bounds"])
    (mode, children), = plan.items()
    parts = [_fold_bounds(child, nodes) for child in children]

    def fold(name: str, op):
        values = [p.get(name) for p in parts]
        if any(v is None for v in values):
            return None
        return op(values)

    out: dict = {}
    for name in SUMMED_BOUNDS:
        if name == "max_cost":
            costs = [p.get("max_cost") for p in parts]
            if all(c is not None for c in costs):
                units = {c["unit"] for c in costs}
                if len(units) != 1:
                    raise GraphShapeError(f"max_cost units differ across branches: {sorted(units)}; "
                                          "convert to one unit before composing")
                out["max_cost"] = {"amount": sum(c["amount"] for c in costs), "unit": units.pop()}
        else:
            v = fold(name, sum)
            if v is not None:
                out[name] = v
    v = fold(TIME_BOUND, sum if mode == "seq" else max)
    if v is not None:
        out[TIME_BOUND] = v
    return out


INTEGER_BOUNDS = ("max_downstream_calls", "max_bytes_out")


def normalize_bounds(bounds: dict) -> dict:
    """Copy of a bounds object with every numeric amount as int; an integer-valued float like 3.0 becomes 3
    so that printing and pinning see one value per number (round 16 P4-3, integer domain)."""
    out: dict = {}
    for name, v in bounds.items():
        if name == "max_cost":
            out[name] = {"amount": dec(v["amount"]), "unit": v["unit"]}
        else:
            out[name] = dec(v)
    return out


def jsonable_bounds(bounds: dict) -> dict:
    """int -> str for printing; the printed value is the compared value."""
    return {k: ({"amount": str(v["amount"]), "unit": v["unit"]} if k == "max_cost" else str(v))
            for k, v in bounds.items()}


# ---------- admissibility ----------

def subset_violations(wanted: dict[tuple[str, str, str], str], held: list[dict]) -> list[str]:
    held_atoms = atomic_grants(held)
    errs = []
    for key, effect in sorted(wanted.items()):
        matches = [hk for hk in held_atoms if covers(hk, key)]
        if not matches:
            errs.append(f"not held by caller: {key[0]}:{key[1]} action={key[2]}")
            continue
        held_effect = max((held_atoms[hk] for hk in matches), key=lambda e: LEVEL[e])
        if LEVEL[effect] > LEVEL[held_effect]:
            errs.append(f"effect escalation: {key[0]}:{key[1]} action={key[2]} "
                        f"wants {effect}, caller holds {held_effect}")
    return errs


def bound_amount(b: dict, name: str):
    v = b.get(name)
    if v is None:
        return None
    return dec(v["amount"]) if isinstance(v, dict) else dec(v)


def bounds_violations(graph_bounds: dict, parent_bounds: dict, where: str) -> list[str]:
    errs = []
    gc, pc = graph_bounds.get("max_cost"), parent_bounds.get("max_cost")
    if gc is not None and gc["amount"] > SAFE_INT_MAX:
        errs.append(f"{where}: max_cost {gc['amount']} exceeds the safe-integer ceiling {SAFE_INT_MAX}")
    if gc is not None and pc is not None and gc["unit"] != pc["unit"]:
        errs.append(f"{where}: max_cost unit {gc['unit']!r} differs from parent's {pc['unit']!r}; "
                    "amounts in different units are not comparable")
    for name in SUMMED_BOUNDS + (TIME_BOUND,):
        parent = bound_amount(parent_bounds, name)
        if parent is None or (name == "max_cost" and errs):
            continue
        child = bound_amount(graph_bounds, name)
        if child is None:
            errs.append(f"{where}: {name} unbounded but parent limits it to {parent}")
        elif child > parent:
            errs.append(f"{where}: {name} {child} exceeds parent budget {parent}")
    return errs


def split_bounds(parent_bounds: dict, n: int) -> dict:
    """Equal split of the parent's summed bounds across n parallel children (D22). Time is not split.

    Integer floor division with the remainder dropped (200 / 3 -> 66 x3, sum 198 <= 200), so n shares can
    never sum above the parent. Cost amounts are integers in the unit's smallest denomination.
    """
    share: dict = {}
    for name in SUMMED_BOUNDS:
        v = parent_bounds.get(name)
        if v is None:
            continue
        if name == "max_cost":
            share[name] = {"amount": dec(v["amount"]) // n, "unit": v["unit"]}
        else:
            share[name] = dec(v) // n
    if TIME_BOUND in parent_bounds:
        share[TIME_BOUND] = dec(parent_bounds[TIME_BOUND])
    return share


def leaf_allotments(plan, parent_bounds: dict) -> dict[str, dict]:
    """The budget each leaf's token would be issued with: par groups split equally, seq passes through (D22)."""
    out: dict[str, dict] = {}

    def walk(node, allotment: dict):
        if isinstance(node, str):
            out[node] = allotment
            return
        (mode, children), = node.items()
        child_allotment = split_bounds(allotment, len(children)) if mode == "par" else allotment
        for child in children:
            walk(child, child_allotment)

    walk(plan, parent_bounds)
    return out


def split_violations(plan, nodes: dict[str, dict], parent_bounds: dict) -> list[str]:
    """Every par group splits its allotment equally; a leaf declaring more than its share is rejected."""
    errs: list[str] = []
    for leaf, allotment in leaf_allotments(plan, parent_bounds).items():
        errs.extend(bounds_violations(nodes[leaf]["bounds"], allotment, f"node {leaf}"))
    return errs


def plan_ids(plan) -> list[str]:
    if isinstance(plan, str):
        return [plan]
    (_, children), = plan.items()
    return [i for c in children for i in plan_ids(c)]


def plan_paths(plan, prefix: tuple = ()) -> dict[str, tuple]:
    """node id -> path of (mode, index) steps from the root; used to order nodes and detect parallel siblings."""
    if isinstance(plan, str):
        return {plan: prefix}
    (mode, children), = plan.items()
    out: dict[str, tuple] = {}
    for i, child in enumerate(children):
        out.update(plan_paths(child, prefix + ((mode, i),)))
    return out


def shape_errors(nodes: dict[str, dict], edges: list[list[str]], plan) -> list[str]:
    """Reject graph documents whose shape makes the composition rules meaningless (round 16 K5)."""
    errs: list[str] = []
    # plan grammar (exactly one of seq/par, non-empty) is enforced by execution-graph.schema.json
    scheduled = plan_ids(plan)
    referenced = set(scheduled) | {i for e in edges for i in e}
    unknown = sorted(referenced - set(nodes))
    if unknown:
        errs.append(f"plan/edges reference unknown nodes: {unknown}")
    orphans = sorted(set(nodes) - set(scheduled))
    if orphans:
        errs.append(f"nodes defined but not scheduled in plan: {orphans}")
    twice = sorted({i for i in scheduled if scheduled.count(i) > 1})
    if twice:
        errs.append(f"nodes scheduled more than once in plan: {twice}; a node runs once per graph")
    if errs:
        return errs

    paths = plan_paths(plan)
    for src, dst in edges:
        if src == dst:
            errs.append(f"self edge {src} -> {dst}")
            continue
        ps, pd = paths[src], paths[dst]
        common = 0
        while common < min(len(ps), len(pd)) and ps[common] == pd[common]:
            common += 1
        if common == len(ps) or common == len(pd):
            errs.append(f"supply edge {src} -> {dst} between a group and its own member")
            continue
        (mode_s, idx_s), (mode_d, idx_d) = ps[common], pd[common]
        if mode_s == "par":
            errs.append(f"supply edge {src} -> {dst} between parallel siblings cannot be honored at run time")
        elif idx_s >= idx_d:
            errs.append(f"supply edge {src} -> {dst} runs backwards: {src} is scheduled after {dst}")

    for node_id, contract in nodes.items():
        for g in contract["requires"]:
            if g["resource"]["kind"] == "agent" and "delegate" in g["actions"]:
                target = canonical_selector(g["resource"]["selector"])
                if target not in nodes:
                    errs.append(f"node {node_id} delegates to {target!r}, which is not a node of this graph; "
                                "closure needs the delegate's contract modeled (ADR-0001 §2.4)")
    return errs


def compose_errors(doc: dict) -> tuple[list[str], dict | None]:
    errs = _schema_errors(doc, GRAPH_SCHEMA, REGISTRY)
    if errs:
        return errs, None
    nodes, edges, plan = doc["nodes"], doc.get("edges", []), doc["plan"]
    for node_id, contract in nodes.items():
        errs += [f"node {node_id}: {e}" for e in contract_errors(contract)]
    if errs:
        return errs, None
    errs = shape_errors(nodes, edges, plan) + grant_errors(doc.get("caller_holds", []), "caller_holds")
    if "parent_bounds" in doc:
        errs += bounds_errors(doc["parent_bounds"], "parent_bounds")
    if errs:
        return errs, None

    try:
        bounds = compose_bounds(plan, nodes)
        requires, errs = compose_requires(nodes, edges, plan)
        composed = {"requires": requires, "effects": compose_effects(nodes), "bounds": bounds}
        errs += subset_violations(composed["requires"], doc.get("caller_holds", []))
        if "parent_bounds" in doc:
            errs += bounds_violations(composed["bounds"], doc["parent_bounds"], "graph")
            errs += split_violations(plan, nodes, doc["parent_bounds"])
            composed["shares"] = leaf_allotments(plan, doc["parent_bounds"])
    except GraphShapeError as e:
        return [str(e)], None
    except OverflowError:
        return ["bounds arithmetic exceeds the safe-integer ceiling; amounts this large are not budgets"], None
    return errs, composed


# ---------- driver ----------

def load(path: Path):
    """(doc, _expect_match, _expect_composed, parse_error). Integer domain: json parses integers natively;
    NaN / Infinity are a parse-level rejection (validate.reject_constant); a non-integral float reaches dec()
    and raises for a schema-level story. The 50-digit lossless-parse era ended with the decimal domain."""
    return load_json(path)


def composed_mismatches(composed: dict, expected: dict) -> list[str]:
    """Compare the composed contract with a must-accept example's `_expect_composed` block.

    Accept/reject alone cannot see whether effects or bounds were composed correctly; this is
    what turns a valid example into a load-bearing assertion (mutation M5 survived without it).
    """
    errs = []
    if "effects" in expected and composed["effects"] != expected["effects"]:
        errs.append(f"composed effects {composed['effects']} != expected {expected['effects']}")
    if "bounds" in expected:
        got = jsonable_bounds(composed["bounds"])
        want = jsonable_bounds(normalize_bounds(expected["bounds"]))
        if got != want:
            errs.append(f"composed bounds {got} != expected {want}")
    if "requires" in expected:
        got = [list(k) + [v] for k, v in sorted(composed["requires"].items())]
        want = sorted(expected["requires"])
        if got != want:
            errs.append(f"composed requires {got} != expected {want}")
    if "shares" in expected:  # issued per-leaf budgets; the only place the split rounding mode is observable
        if "shares" not in composed:
            errs.append("fixture pins shares but the graph has no parent_bounds, so nothing was issued")
        else:
            got = {leaf: jsonable_bounds(a) for leaf, a in composed["shares"].items()}
            want = {leaf: jsonable_bounds(normalize_bounds(b)) for leaf, b in expected["shares"].items()}
            if got != want:
                errs.append(f"issued shares {got} != expected {want}")
    return errs


def run_suite(valid_dir: Path, invalid_dir: Path) -> int:
    valid, invalid = sorted(valid_dir.glob("*.json")), sorted(invalid_dir.glob("*.json"))
    if not valid or not invalid:
        print("[compose] suite incomplete: need at least one valid and one invalid example")
        return 1
    bad = 0
    for f in valid:
        doc, _, expected, parse_error = load(f)
        errs, composed = ([parse_error], None) if parse_error else compose_errors(doc)
        if composed and not errs and expected:
            errs = composed_mismatches(composed, expected)
        print(f"[compose] {'PASS' if not errs else 'FAIL'} must-accept {f.name}")
        for e in errs:
            print(f"      {e}")
        if composed and not errs:
            print(f"      requires(G)={len(composed['requires'])} atoms effects={composed['effects']} "
                  f"bounds={jsonable_bounds(composed['bounds'])}")
        bad += bool(errs)
    for f in invalid:
        doc, match, _, parse_error = load(f)
        errs = [parse_error] if parse_error else compose_errors(doc)[0]
        if not errs:
            print(f"[compose] FAIL must-reject {f.name}  (was accepted!)")
            bad += 1
        elif match and not any(match in e for e in errs):
            print(f"[compose] FAIL must-reject {f.name}  (rejected for the wrong reason: {errs[0]!r} lacks {match!r})")
            bad += 1
        else:
            print(f"[compose] PASS must-reject {f.name}  ({errs[0]})")
    print(f"[compose] {len(valid)} must-accept + {len(invalid)} must-reject, {bad} failures")
    return bad + run_guard_suite(valid[0])


def run_guard_suite(sample: Path) -> int:
    """Checks JSON fixtures cannot express (round 16 P4-2 / P4-4 / fifth pass):
    - a dict with float('nan') in parent_bounds must be rejected, not crash a comparison;
    - a fixture that pins `shares` without `parent_bounds` must get a message, not KeyError (that is a
      fixture-authoring error, so it can only be exercised here, never as a must-accept file)."""
    bad = 0
    doc, _, _, _ = load(sample)
    doc["parent_bounds"] = {"max_cost": {"amount": float("nan"), "unit": "USD"}}
    try:
        errs, _ = compose_errors(doc)
        ok, detail = any("not of type" in e or "not a finite" in e for e in errs), errs[:1]
    except Exception as e:  # noqa: BLE001 — the whole point is that no exception may escape here
        ok, detail = False, f"CRASH {type(e).__name__}: {e}"
    print(f"[compose] {'PASS' if ok else 'FAIL'} programmatic must-reject parent_bounds NaN  ({detail})")
    bad += not ok

    doc, _, expected, _ = load(sample)
    doc.pop("parent_bounds", None)
    errs, composed = compose_errors(doc)
    try:
        mism = composed_mismatches(composed, {"shares": {}}) if composed and not errs else ["graph itself failed"]
        ok, detail = any("no parent_bounds" in m for m in mism), mism[:1]
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"CRASH {type(e).__name__}: {e}"
    print(f"[compose] {'PASS' if ok else 'FAIL'} programmatic shares pin without parent_bounds  ({detail})")
    bad += not ok
    return bad


def main(argv: list[str]) -> int:
    if argv:
        rc = 0
        for f in argv:
            doc, _, _, parse_error = load(Path(f))
            errs, composed = ([parse_error], None) if parse_error else compose_errors(doc)
            print(f"{'OK  ' if not errs else 'FAIL'} {f}")
            for e in errs:
                print(f"      {e}")
            if composed:
                print(json.dumps({"requires": [list(k) + [v] for k, v in sorted(composed["requires"].items())],
                                  "effects": composed["effects"],
                                  "bounds": jsonable_bounds(composed["bounds"])},
                                 ensure_ascii=False, indent=2))
            rc |= bool(errs)
        return rc
    ex = HERE / "examples" / "compose"
    bad = run_suite(ex / "valid", ex / "invalid")
    # D93 count-floor (the Go twin lives in cmd/compose/main_test.go): a
    # corpus that shrank without its pin rebased must fail here too — this
    # oracle was the one family missing the third count pin (R9 F5).
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (10, 36):
        print(f"[compose] FAIL corpus count {n_valid}+{n_invalid} != pinned 10+36 (corpus count changed?)")
        bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
