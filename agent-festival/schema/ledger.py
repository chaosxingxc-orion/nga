#!/usr/bin/env python3
"""Validate event-ledger fixtures (piece 4 oracle).

Ledger documents: JSON Schema + the cross-event rules JSON Schema cannot
express — eight families: arbitration_seq strictly increasing (+int64
domain, +float syntax beyond ±2^53 rejected by rule), one payload digest
per operation (15 B4), idempotency presence (bidirectional: every
non-conflict event carries it, and a conflict carrying it is rejected —
the loser's digest never enters the registry), the idem-identity key
coupling, status families never
crossing the event-type boundary, the grant pin riding the adopted event
only, effect events carrying the adopted pin's attribution triple, and the
single-writer event-sequence grammar (each operation opens with exactly
one adopted event and its effect events follow the machine's transition
DAG). Input discipline: documents come in as exact-decoded maps
(json.loads int/float) — a Go caller feeding a float64-decoded map loses
three rules silently (monotonicity at 2^53, the float-syntax-beyond rule,
integral-float normalization). Aggregation contract: the code-rule families
aggregate in the same order on both sides; both checkers short-circuit at
the schema, and the Go checker additionally short-circuits at the
float-syntax and typed-view-parse points where this oracle appends and
continues — so error-set composition may differ on documents violating
those two, and invalid fixtures are single-violation by discipline (the
one designed exception: effect-before-adoption is one bypass fact that
legitimately trips both the grammar and the transition table, identically
on both sides). The verdict never differs.
Fixtures follow the base's pin discipline: valid must be accepted, invalid
must be rejected for the reason its _expect_match names.

Exit 0 iff every examples/ledger/valid/* passes AND every invalid/* is
rejected — and, when an invalid example carries _expect_match, rejected for
that reason.

Usage: python3 schema/ledger.py
Dependencies: jsonschema (pinned in requirements.txt).
"""
import json
import sys
from pathlib import Path

import jsonschema

import _suite

HERE = Path(__file__).resolve().parent
LEDGER_SCHEMA = json.loads((HERE / "event-ledger.schema.json").read_text())
ADOPTION_SCHEMA = json.loads((HERE / "adoption.schema.json").read_text())

# status families — module level so the lockstep check can compare them with
# the schema enum (R3 m-2: the vocabulary exists as several copies; the
# lockstep check makes the schema enum the enforced single source)
ADOPT_STATUSES = {"adopted", "reused", "conflict"}
EFFECT_STATUSES = {"dispatched", "unresolved", "completed", "failed"}
INT64_MAX = 9223372036854775807




def ledger_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(LEDGER_SCHEMA)
    errs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]
    if errs:
        return errs
    # sequence ORDER is checked, density is not: the machine writes gap-free
    # consecutive seqs, but a gap forges no order and crosses no state — no
    # falsifiable surface, so no rule (deliberate, not an omission).
    # cross-event rule: arbitration_seq must be strictly increasing, and within
    # the int64 domain (the machine's counter domain — Python's bignum would
    # otherwise accept a document the Go typed view rejects, forking the
    # dual validators' verdicts)
    seqs = [e["arbitration_seq"] for e in doc["events"]]
    if any(seqs[i] >= seqs[i + 1] for i in range(len(seqs) - 1)):
        errs.append(f"[LEDGER.SEQ_NOT_INCREASING] events: arbitration_seq must be strictly increasing, got {seqs} — "
                    f"the machine never repeats or rewinds an arbitration sequence")
    if any(s > INT64_MAX for s in seqs):
        errs.append("[LEDGER.SEQ_INT64_OVERFLOW] events: arbitration_seq exceeds the int64 domain — the machine's "
                    "counter domain; such a document is not machine-writable")
    # cross-event rule: a payload digest is a function of the operation — the same
    # operation_id across idempotency entries must carry the same digest (15 B4:
    # 'changed payload under the same key' is a rejection, not a second opinion)
    seen: dict[str, str] = {}
    for e in doc["events"]:
        idem = e.get("idempotency")
        if not idem:
            continue
        op, dig = idem["operation_id"], idem["payload_digest"]
        if op in seen and seen[op] != dig:
            errs.append(f"[LEDGER.DIGEST_CHANGED_UNDER_KEY] events: operation_id {op!r} carries payload_digest {dig!r} "
                        f"but an earlier event recorded {seen[op]!r} — changed payload under the same key")
        seen[op] = dig
    # cross-event rule: arbitration_seq in float syntax beyond ±2^53 — the
    # value a parser recovers depends on its float rounding (Python's
    # float() folds odd values past 2^53), so the document has no
    # parser-independent value; both validators reject by rule (mirrors Go)
    for i, e in enumerate(doc["events"]):
        seq = e["arbitration_seq"]
        if isinstance(seq, float) and seq == int(seq) and abs(seq) > 2 ** 53:
            errs.append(f"[LEDGER.SEQ_FLOAT_BEYOND_EXACT] events/{i}: arbitration_seq {seq!r} uses float syntax beyond the "
                        f"exact-representation domain (±2^53) — the value a parser recovers "
                        f"depends on its float rounding, not on the document")

    # cross-event rule: status families never cross the event-type boundary
    # (adoption events carry adopted/reused/conflict, effect events carry
    # dispatched/unresolved/completed/failed) — checked in code on both sides
    # because schema if/then validator messages do not name the offending
    # value, so wrong-reason pins could not match on both validators
    for i, e in enumerate(doc["events"]):
        status = e.get("outcome", {}).get("status", "")
        ok = status in (EFFECT_STATUSES if e["event_type"] == "effect" else ADOPT_STATUSES)
        if not ok:
            # the label names the status's OWN family — that is the
            # vocabulary crossing being reported. (Empty and unknown-status
            # branches are unreachable: the schema's required outcome +
            # status enum constrain the value first.)
            family = "adoption" if status in ADOPT_STATUSES else "effect"
            errs.append(f"[LEDGER.STATUS_FAMILY] events/{i}: {e['event_type']} event carries the {family}-family status "
                        f"{status!r} — the status vocabulary never crosses the "
                        f"event-type boundary")
        if (e["event_type"] == "effect" or status != "adopted") and e.get("grants_at_decision"):
            errs.append(f"[LEDGER.GRANTS_ON_NON_ADOPTED] events/{i}: {e['event_type']} event (status {status!r}) for operation "
                        f"{e['identity']['operation_id']!r} carries grants_at_decision — the grant "
                        f"pin rides the adopted event only (stamped once, at the decision point)")

    # cross-event rule: per-operation transition order — mirror the adopt
    # machine's own DAG (adopted -> dispatched | unresolved; dispatched ->
    # unresolved | completed | failed; unresolved -> completed | failed).
    # An effect event that is not a legal transition from the operation's
    # current state is a bypass write; without this the loader absorbs e.g.
    # completed-before-dispatched and the machine resumes from a state it
    # can never be in (R3 M-1, mirrors the Go checker).
    def not_a_transition(i: int, op: str, status: str, from_state: str) -> str:
        return (f"[LEDGER.ILLEGAL_TRANSITION] events/{i}: operation {op!r}: status {status!r} after "
                f"{from_state or 'nothing'!r} is not a legal state-machine transition — "
                f"a bypass write into the ledger, not a machine transition")

    state: dict[str, str] = {}
    for i, e in enumerate(doc["events"]):
        op = e["identity"]["operation_id"]
        if e["event_type"] != "adoption":
            status = e["outcome"]["status"]
            from_state = state.get(op, "")
            if status == "dispatched":
                if from_state != "adopted":
                    errs.append(not_a_transition(i, op, "dispatched", from_state))
                state[op] = "dispatched"
            elif status == "unresolved":
                if from_state not in ("adopted", "dispatched"):
                    errs.append(not_a_transition(i, op, "unresolved", from_state))
                state[op] = "unresolved"
            elif status in ("completed", "failed"):
                if from_state not in ("dispatched", "unresolved"):
                    errs.append(not_a_transition(i, op, status, from_state))
                state[op] = status
            continue
        if e["outcome"].get("status") == "adopted":
            state[op] = "adopted"
    # cross-event rule: idempotency presence — the machine writes
    # idempotency on every event except conflict (the loser's digest never
    # enters the registry); an adopted/reused/effect event without it is a
    # bypass write, and absorbing one forks the replay state away from the
    # durable form (R10 BLOCKER, mirrors the Go checker)
    for i, e in enumerate(doc["events"]):
        status = e.get("outcome", {}).get("status", "")
        if e["event_type"] == "adoption" and status == "conflict" and e.get("idempotency"):
            errs.append(f"[LEDGER.CONFLICT_IDEM_FORBIDDEN] events/{i}: conflict event carries idempotency — the loser's digest "
                        f"never enters the registry; carrying it is a bypass write, not a "
                        f"machine transition")
        needs_idem = e["event_type"] == "effect" or status in ("adopted", "reused")
        if needs_idem and not e.get("idempotency"):
            errs.append(f"[LEDGER.IDEM_REQUIRED] events/{i}: {e['event_type']} event (status {status!r}) must carry "
                        f"idempotency — the machine writes it on every non-conflict event; its "
                        f"absence is a bypass write, not a machine transition")

    # cross-event rule: the key coupling — the machine writes
    # idempotency.operation_id and identity.operation_id EQUAL on every event
    # carrying idempotency; a mismatch registers a phantom operation the
    # caller never created (R6 BLOCKER, mirrors the Go checker)
    for i, e in enumerate(doc["events"]):
        idem = e.get("idempotency")
        if idem and idem["operation_id"] != e["identity"]["operation_id"]:
            errs.append(f"[LEDGER.IDEM_IDENTITY_MISMATCH] events/{i}: idempotency.operation_id {idem['operation_id']!r} does not "
                        f"match identity.operation_id {e['identity']['operation_id']!r} — the "
                        f"machine writes them equal; a mismatch is a bypass write, not a "
                        f"machine transition")

    # cross-event rule: attribution consistency — the machine stamps the
    # winner's identity/versions/accountability pin on every effect event;
    # a divergence is a bypass write that forges the audit trail and
    # pollutes the piece-6 replay correlation keys (mirrors the Go checker;
    # checked only where an adopted pin exists — effect-before-adoption is
    # already the grammar's designed exception)
    pins: dict[str, tuple] = {}
    for i, e in enumerate(doc["events"]):
        op = e["identity"]["operation_id"]
        if e["event_type"] == "adoption" and e.get("outcome", {}).get("status") == "adopted":
            pins[op] = (e["identity"], e["versions"], e.get("accountability"))
        elif e["event_type"] == "effect" and op in pins:
            if (e["identity"], e["versions"], e.get("accountability")) != pins[op]:
                errs.append(f"[LEDGER.ATTRIBUTION_DIVERGENCE] events/{i}: effect event's attribution (identity/versions/"
                            f"accountability) differs from the adopted pin for operation "
                            f"{op!r} — the machine stamps the winner's pin on every effect "
                            f"event; a divergence is a bypass write, not a machine transition")

    # cross-event rule: the single-writer event-sequence grammar — each
    # operation opens with exactly one adopted adoption event, and every
    # later event for it (reused / conflict / effects) only exists downstream
    # of that adoption. A violation is a bypass write, not a machine
    # transition (mirrors the Go checker).
    adopted: set[str] = set()
    for i, e in enumerate(doc["events"]):
        op = e["identity"]["operation_id"]
        if e["event_type"] == "adoption":
            if e["outcome"]["status"] == "adopted":
                if op in adopted:
                    errs.append(f"[LEDGER.DOUBLE_ADOPTED] events/{i}: operation {op!r} already has an adopted event — "
                                f"a second adopted event would re-pin the machine's state mid-flight "
                                f"(a bypass write, not a machine transition)")
                adopted.add(op)
            elif op not in adopted:
                errs.append(f"[LEDGER.EVENT_BEFORE_ADOPTION] events/{i}: {e['event_type']} event for operation {op!r} "
                            f"precedes its adopted event — a bypass write into the ledger, "
                            f"not a machine transition")
        elif op not in adopted:
            errs.append(f"events/{i}: effect event for operation {op!r} precedes its adopted "
                        f"event — a bypass write into the ledger, not a machine transition")
    return errs


def check_status_lockstep() -> list[str]:
    """The status vocabulary exists as several copies (schema enum, these
    family sets, the Go sets, the machine's State constants) — this check
    makes the schema enum the enforced single source (R3 m-2).
    """
    enum = set(LEDGER_SCHEMA["$defs"]["event"]["properties"]["outcome"]["properties"]["status"]["enum"])
    union = ADOPT_STATUSES | EFFECT_STATUSES
    if enum != union:
        return [f"status lockstep broken: schema enum {sorted(enum)} != checker families "
                f"{sorted(union)}"]
    return []


def check_lockstep() -> list[str]:
    """Five shared atoms exist as two self-contained schema copies each (frozen
    engine stake C5-a): grant, identity, versions, accountability, and the
    payload-digest shape. 'Stay in lockstep' is only real if something
    compares them — this check diffs
    each pair directly, recursively stripped of descriptions (R2 m-4; R6
    M-2 extended it from grant alone to the whole shared surface).
    """
    def strip_desc(node):
        if isinstance(node, dict):
            return {k: strip_desc(v) for k, v in node.items() if k != "description"}
        if isinstance(node, list):
            return [strip_desc(v) for v in node]
        return node

    pairs = [
        ("grant", LEDGER_SCHEMA["$defs"]["grant"],
         ADOPTION_SCHEMA["properties"]["grants_at_decision"]["items"]),
        ("identity", LEDGER_SCHEMA["$defs"]["identity"],
         ADOPTION_SCHEMA["properties"]["identity"]),
        ("versions", LEDGER_SCHEMA["$defs"]["versions"],
         ADOPTION_SCHEMA["properties"]["versions"]),
        ("accountability", LEDGER_SCHEMA["$defs"]["event"]["properties"]["accountability"],
         ADOPTION_SCHEMA["properties"]["accountability"]),
        # the fifth shared atom: the payload-digest shape. The machine's
        # "conforming by construction" depends on adoption ⊆ ledger —
        # without this pair, a loosened request-side pattern lets the
        # machine write files its own loader rejects (R9 M-1).
        ("payload_digest", LEDGER_SCHEMA["$defs"]["idempotency"]["properties"]["payload_digest"],
         ADOPTION_SCHEMA["properties"]["payload_digest"]),
    ]
    errs = []
    for name, a, b in pairs:
        if strip_desc(a) != strip_desc(b):
            errs.append(f"{name} shape lockstep broken: event-ledger copy != adoption copy "
                        f"({json.dumps(strip_desc(a), ensure_ascii=False)} vs "
                        f"{json.dumps(strip_desc(b), ensure_ascii=False)})")
    return errs


def check_odd_twin_bytes() -> list[str]:
    """Byte-level pin on the odd-twin fixture (R2 M3): the literal
    9007199254740993.0 must survive at the BYTE level. Both it and the even
    twin fold to the same float64, so every parsed assertion is identity-blind
    — this fixture silently regressed ..993.0→..992.0 once with the whole
    suite green. The Go twin lives in ledger_test.go (TestOddFloatTwinPinsFoldedDomain)."""
    p = HERE / "examples" / "ledger" / "valid" / "seq-odd-float-twin.json"
    raw = p.read_bytes()
    if b'"arbitration_seq": 9007199254740993.0' not in raw:
        return [f"odd-twin byte pin lost: the raw literal 9007199254740993.0 is gone "
                f"from {p.name} — the folding semantics are unpinned"]
    return []


def main() -> int:
    ex = HERE / "examples" / "ledger"
    bad = _suite.run_suite("ledger", ex / "valid", ex / "invalid", ledger_errors)
    # D93 count-floor (the Go twin lives in cmd/ledger/main_test.go): a
    # corpus that shrank without its pin rebased must fail here too
    n_valid = len(list((ex / "valid").glob("*.json")))
    n_invalid = len(list((ex / "invalid").glob("*.json")))
    if (n_valid, n_invalid) != (10, 26):
        print(f"[ledger] FAIL corpus count {n_valid}+{n_invalid} != pinned 10+26 (corpus count changed?)")
        bad += 1
    for e in check_status_lockstep() + check_lockstep() + check_odd_twin_bytes():
        print(f"[ledger] FAIL {e}")
        bad += 1
    if bad == 0:
        print("[ledger] lockstep: status enum == checker families; "
              "grant/identity/versions/accountability/payload_digest shapes == adoption copies")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
