package e2e

import (
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
)

// X-S2 (R54 §三 red-team #4): the expectedRev PARAMETER form of conditional
// commit has a trust hole — a caller who reads the scope head and echoes it
// bypasses the check regardless of which revision their decision was made
// against. The MACHINE-INTERNAL form (read the op's OWN adopted revision
// from opState.identity — which already exists, adopt.go:129/232 — and
// compare with the head) has no parameter to lie about.
//
// This file demonstrates BOTH forms side by side using a minimal test-local
// scope head, in the style of xingchao's overlay experiments (198789653 §3):
// demonstrate the flaw without touching production code.

// minimal test-local scope head (what N1 will materialize in the Machine)
type xs2ScopeHead struct {
	current map[string]string // business_request_id -> effective revision
}

// PARAMETER form (51号 A2 / 52号 N1 design): the caller supplies expectedRev.
func xs2ParamCommit(h *xs2ScopeHead, brID, callerExpectedRev string) bool {
	return callerExpectedRev == h.current[brID]
}

// MACHINE-INTERNAL form (R54 §三 #4 refinement): no parameter — the check
// reads the op's OWN adopted revision from machine state.
func xs2InternalCommit(m *adopt.Machine, h *xs2ScopeHead, op string) bool {
	// the machine exposes the op's adopted identity via its event record;
	// State() alone doesn't expose identity, so this demonstration reads
	// Events() — in the real N1 this is an O(1) in-memory check on
	// opState.identity (which already exists, adopt.go:129).
	events, err := m.Events()
	if err != nil {
		return false
	}
	var opEr, opBr string
	for _, e := range events {
		if e.EventType == "adoption" && e.Identity.OperationID == op {
			opEr = e.Identity.EvaluationRevision
			opBr = e.Identity.BusinessRequestID
		}
	}
	return h.current[opBr] == opEr && opEr != ""
}

func TestXS2_ParameterFormTrustHole(t *testing.T) {
	// setup: two ops under one business request, er-2 is effective
	head := &xs2ScopeHead{current: map[string]string{"br-cas": "er-2"}}

	// the LIYING caller: their decision was made against er-1 (op-old),
	// but they read the head and echo "er-2"
	lyingCallerPasses := xs2ParamCommit(head, "br-cas", "er-2")
	if !lyingCallerPasses {
		t.Fatal("X-S2 arm 1 FAILED to demonstrate the hole: the parameter form refused the lying caller — the hole is NOT as described")
	}
	// the hole is demonstrated: the lying caller passed
	t.Logf("X-S2 arm 1: lying caller (decision=er-1, echoes head=er-2) PASSED the parameter form — trust hole confirmed")

	// honest caller for contrast: presents their actual (stale) revision
	honestCallerRefused := !xs2ParamCommit(head, "br-cas", "er-1")
	if !honestCallerRefused {
		t.Fatal("X-S2 arm 1 control: the honest caller was not refused — unexpected")
	}
	t.Logf("X-S2 arm 1 control: honest caller (presents actual er-1) refused — the parameter form only catches HONEST stale callers")
}

func TestXS2_MachineInternalFormImmune(t *testing.T) {
	// same setup, but with the real machine holding both ops
	m := mustOpenAdopt(t, newLedgerPath(t))
	if o := m.Adopt(adoptRequest(t, "old")); o.Status != "adopted" {
		t.Fatal(o)
	}
	if o := m.Adopt(adoptRequest(t, "new")); o.Status != "adopted" {
		t.Fatal(o)
	}
	// NOTE: adoptRequest assigns a fresh BusinessRequestID per call — we
	// need both ops under the SAME br. Rebuild with explicit shared identity.
	m2 := mustOpenAdopt(t, newLedgerPath(t))
	reqOld := adoptRequest(t, "old")
	reqOld.Identity.BusinessRequestID = "br-xs2"
	reqOld.Identity.EvaluationRevision = "er-1"
	if o := m2.Adopt(reqOld); o.Status != "adopted" {
		t.Fatal(o)
	}
	reqNew := adoptRequest(t, "new")
	reqNew.Identity.BusinessRequestID = "br-xs2"
	reqNew.Identity.EvaluationRevision = "er-2"
	if o := m2.Adopt(reqNew); o.Status != "adopted" {
		t.Fatal(o)
	}

	head := &xs2ScopeHead{current: map[string]string{"br-xs2": "er-2"}}

	// the machine-internal form checks op-old's OWN er against the head —
	// there is NO parameter, so "lying" is not even expressible
	if xs2InternalCommit(m2, head, "old") {
		t.Fatal("X-S2 arm 2 FAILED: the internal form permitted a stale op (er-1) under head er-2")
	}
	t.Logf("X-S2 arm 2: op-old (own er=er-1, head=er-2) REFUSED by the internal form — no parameter exists to lie about")

	// positive control: the current op (er-2) passes
	if !xs2InternalCommit(m2, head, "new") {
		t.Fatal("X-S2 arm 2 control: the current op (er-2) was refused — the internal form is too strict")
	}
	t.Logf("X-S2 arm 2 control: op-new (own er=er-2, head=er-2) permitted — positive control green")
}
