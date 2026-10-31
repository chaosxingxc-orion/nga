package main

import (
	"strings"
	"testing"

	"festival-dev/go/internal/replay"

	"festival-dev/go/internal/suite"
)

// TestReplaySuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, the Python twin lives in replay.py's main).
func TestReplaySuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[replay] 8 must-accept + 6 must-reject, 0 failures") {
		t.Fatalf("replay summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}

// TestDivergenceAtLegCatchesWrongPin pins the cmd layer's divergence_at
// comparison leg (R14: the engine-side location had pins, but the
// fixture-expected→engine comparison itself was bare wiring — a hand-edited
// fixture pin passed green).
func TestDivergenceAtLegCatchesWrongPin(t *testing.T) {
	// a divergence case with a deliberate WRONG location pin: the steps end
	// in completed while the record ends in failed, the engine locates 2,
	// the pin claims 0 — the cmd comparison leg must go red naming the pin
	digest := "sha256:" + strings.Repeat("a", 64)
	ident := map[string]any{"business_request_id": "b", "operation_id": "o"}
	vers := map[string]any{"evidence": "e", "rule": "r", "model": "m", "readout": "ro", "policy": "p"}
	grants := []any{map[string]any{"kind": "data", "selector": "s", "actions": []any{"read"}, "effect": "none"}}
	ev := func(etype string, seq int, status string) map[string]any {
		e := map[string]any{"event_type": etype, "arbitration_seq": seq,
			"identity": ident, "versions": vers,
			"outcome":     map[string]any{"status": status},
			"idempotency": map[string]any{"operation_id": "o", "payload_digest": digest}}
		if status == "adopted" {
			e["grants_at_decision"] = grants // the adopted event carries the pin (schema-required)
		}
		return e
	}
	doc := map[string]any{
		"case_version": "0.1.0", "case_id": "wrong-pin",
		"steps": []any{
			map[string]any{"op": "adopt", "request": map[string]any{
				"adoption_version": "0.1.0", "identity": ident, "versions": vers,
				"payload_digest": digest,
				"grants_at_decision": []any{map[string]any{"kind": "data", "selector": "s",
					"actions": []any{"read"}, "effect": "none"}}}},
			map[string]any{"op": "dispatch", "op_id": "o",
				"grants": []any{map[string]any{"kind": "data", "selector": "s",
					"actions": []any{"read"}, "effect": "none"}}},
			map[string]any{"op": "mark_completed", "op_id": "o"},
		},
		"recorded_events": []any{ev("adoption", 0, "adopted"), ev("effect", 1, "dispatched"), ev("effect", 2, "failed")},
		"expected":        map[string]any{"fidelity": "divergence", "conformance": "pass", "divergence_at": 0},
	}
	c, err := replay.LoadCase(doc)
	if err != nil {
		t.Fatal(err)
	}
	errs := caseVerdictErrors(c)
	if len(errs) == 0 {
		t.Fatal("a wrong divergence_at pin passed the cmd comparison leg green — the wiring is bare")
	}
	if !strings.Contains(errs[0], "divergence_at") {
		t.Fatalf("first error does not name the pin: %v", errs[0])
	}
}
