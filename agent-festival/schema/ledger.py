#!/usr/bin/env python3
"""Validate event-ledger fixtures (piece 4 oracle).

Ledger documents: JSON Schema + the cross-event rules JSON Schema cannot
express (arbitration_seq monotonicity). Fixtures follow the base's pin
discipline: valid must be accepted, invalid must be rejected for the reason
its _expect_match names.

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




def ledger_errors(doc: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(LEDGER_SCHEMA)
    errs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(doc)]
    if errs:
        return errs
    # cross-event rule: arbitration_seq must be non-decreasing
    seqs = [e["arbitration_seq"] for e in doc["events"]]
    if any(seqs[i] > seqs[i + 1] for i in range(len(seqs) - 1)):
        errs.append(f"events: arbitration_seq must be non-decreasing, got {seqs}")
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
            errs.append(f"events: operation_id {op!r} carries payload_digest {dig!r} "
                        f"but an earlier event recorded {seen[op]!r} — changed payload under the same key")
        seen[op] = dig
    # cross-event rule: status families never cross the event-type boundary
    # (adoption events carry adopted/reused/conflict, effect events carry
    # dispatched/unresolved/completed/failed) — checked in code on both sides
    # because schema if/then validator messages do not name the offending
    # value, so wrong-reason pins could not match on both validators
    adopt_statuses = {"adopted", "reused", "conflict"}
    effect_statuses = {"dispatched", "unresolved", "completed", "failed"}
    for i, e in enumerate(doc["events"]):
        ok = e["outcome"]["status"] in (effect_statuses if e["event_type"] == "effect" else adopt_statuses)
        if not ok:
            family = "adoption" if e["outcome"]["status"] in effect_statuses else "effect"
            errs.append(f"events/{i}: {e['event_type']} event carries the {family}-family status "
                        f"{e['outcome']['status']!r} — the status vocabulary never crosses the "
                        f"event-type boundary")
        if e["event_type"] == "effect" and e.get("grants_at_decision"):
            errs.append(f"events/{i}: effect event for operation {e['identity']['operation_id']!r} "
                        f"carries grants_at_decision — the grant pin rides the adopted event only "
                        f"(stamped once, at the decision point)")
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
                    errs.append(f"events/{i}: operation {op!r} already has an adopted event — "
                                f"a second adopted event would re-pin the machine's state mid-flight "
                                f"(a bypass write, not a machine transition)")
                adopted.add(op)
            elif op not in adopted:
                errs.append(f"events/{i}: {e['event_type']} event for operation {op!r} "
                            f"precedes its adopted event — a bypass write into the ledger, "
                            f"not a machine transition")
        elif op not in adopted:
            errs.append(f"events/{i}: effect event for operation {op!r} precedes its adopted "
                        f"event — a bypass write into the ledger, not a machine transition")
    return errs


def check_grant_lockstep() -> list[str]:
    """The grant shape exists as two self-contained schema copies (frozen
    engine stake C5-a). 'Stay in lockstep' is only real if something
    compares them: this check diffs the two grant subtrees directly (R2 m-4
    — the previous 'checked by the shared fixture suites' claim only covered
    the values fixtures happened to use).
    """
    def strip_desc(node):
        if isinstance(node, dict):
            return {k: strip_desc(v) for k, v in node.items() if k != "description"}
        if isinstance(node, list):
            return [strip_desc(v) for v in node]
        return node

    errs = []
    ledger_grant = strip_desc(LEDGER_SCHEMA["$defs"]["grant"])
    adoption_grant = strip_desc(ADOPTION_SCHEMA["properties"]["grants_at_decision"]["items"])
    if ledger_grant != adoption_grant:
        errs.append(f"grant shape lockstep broken: event-ledger $defs.grant != adoption "
                    f"grants_at_decision items ({json.dumps(ledger_grant, ensure_ascii=False)} vs "
                    f"{json.dumps(adoption_grant, ensure_ascii=False)})")
    return errs


def main() -> int:
    ex = HERE / "examples" / "ledger"
    bad = _suite.run_suite("ledger", ex / "valid", ex / "invalid", ledger_errors)
    for e in check_grant_lockstep():
        print(f"[ledger] FAIL {e}")
        bad += 1
    if bad == 0:
        print("[ledger] grant lockstep: event-ledger $defs.grant == adoption grants_at_decision items")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
