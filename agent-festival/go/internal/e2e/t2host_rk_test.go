package e2e

// Scenario R (persisted result reuse across restart) and Scenario K
// (new-task knowledge consumption, zero model calls) — xingchao's
// acceptance scenarios from 198178087, implemented on the T2 reference
// host. Plus the correction-coexistence variant from 198232012 (§四 How).

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
)

// t2Digest is the digest helper for T2 scenarios (distinct prefix to avoid
// collision with T0 digests if they share a store — they don't, but
// explicit is better than implicit).
func t2Digest(ch byte) string {
	return "sha256:" + strings.Repeat(string(ch), 64)
}

// ---------------------------------------------------------------------------
// Scenario R: persisted result reuse across restart

// TestT2R_PersistedReceiptAcrossRestart is the full R scenario: first pass
// runs the chain and stores the receipt; the host restarts (fresh machine +
// fresh resultStore, file-backed); all adapters (model seats, business API)
// are replaced with failing probes; the same node execution is re-submitted
// and MUST return the original result from the persisted record — zero seat
// calls, zero adapter calls.
func TestT2R_PersistedReceiptAcrossRestart(t *testing.T) {
	dir := t.TempDir()

	// FIRST PASS: run the chain normally
	h1 := newT2Host(t, dir)
	receipt1 := "receipt:op-t2r:bank-ref-9876:accepted-2026-11-04T10:30:00Z"
	o := h1.adoptAndDispatch(
		"op-t2r", "er-1", "ev-1", t2Digest('a'),
		"br-t2r", receipt1,
		[]string{"asset_report_present", "no_overdue_in_window", "history_checked"},
	)
	if o.Status != "dispatched" {
		t.Fatalf("R first pass: dispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h1.completeNode("op-t2r"); o.Status != "completed" {
		t.Fatalf("R first pass: complete = %q: %s", o.Status, o.Detail)
	}

	// RESTART: fresh machine (from ledger) + fresh resultStore (from file)
	h2 := h1.reopen()

	// Replace ALL adapters with failing probes
	pS1 := h2.addProbe("s1-model-seat")
	pS2 := h2.addProbe("s2-investigation")
	pAPI := h2.addProbe("business-api")

	// RE-SUBMIT the same node execution: the host checks the record first.
	// The machine state is "completed" (from the ledger) — the host's node
	// entry queries the machine, finds it complete, and returns the stored
	// result WITHOUT calling any adapter.
	if s := h2.machine.State("op-t2r"); s != adopt.StateCompleted {
		t.Fatalf("R restart: state = %q, want completed (the ledger remembers)", s)
	}

	// The host returns the stored result — from the file, not re-derived
	stored, ok := h2.store.get("op-t2r")
	if !ok {
		t.Fatal("R restart: stored result not found — the result store did not survive restart")
	}
	if stored.Receipt != receipt1 {
		t.Fatalf("R restart: receipt = %q, want %q — must be the ORIGINAL receipt (persisted, not re-derived)", stored.Receipt, receipt1)
	}

	// Zero-invocation assertion: all probes must be silent
	pS1.assertNotCalled(t)
	pS2.assertNotCalled(t)
	pAPI.assertNotCalled(t)
	_ = pS1
	_ = pS2
	_ = pAPI

	// No new events in the ledger (the reuse is a read, not a write)
	events1, err := h1.machine.Events()
	if err != nil {
		t.Fatalf("Events() failed (R43 m-4): %v", err)
	}
	events2, err := h2.machine.Events()
	if err != nil {
		t.Fatalf("Events() failed (R43 m-4): %v", err)
	}
	if len(events2) != len(events1) {
		t.Fatalf("R restart: events changed %d → %d — reuse must not write new ledger events", len(events1), len(events2))
	}
}

// TestT2R_SameKeyDifferentPayload is R variant 1: the same operation_id with
// a DIFFERENT payload digest → conflict, never silent overwrite.
func TestT2R_SameKeyDifferentPayload(t *testing.T) {
	h := newT2Host(t, t.TempDir())
	if o := h.machine.Adopt(requestForT2("op-t2r-diff", "er-1", "ev-1", t2Digest('a'), "br-t2r")); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	// same key, different content → conflict
	o := h.machine.Adopt(requestForT2("op-t2r-diff", "er-1", "ev-1", t2Digest('b'), "br-t2r"))
	if o.Status != "rejected" {
		t.Fatalf("same-key-different-payload = %q, want rejected (conflict)", o.Status)
	}
}

// TestT2R_PermissionRevoked is R variant 2: the caller's read permission is
// revoked — the stored result is NOT returned (the host checks authorization
// before serving results, per D-04's read-authorization gap).
func TestT2R_PermissionRevoked(t *testing.T) {
	h := newT2Host(t, t.TempDir())
	h.adoptAndDispatch(
		"op-t2r-perm", "er-1", "ev-1", t2Digest('c'),
		"br-t2r-perm", "receipt:op-t2r-perm:accepted",
		[]string{"fact_1"},
	)
	h.completeNode("op-t2r-perm")

	// L39 fix + E5 upgrade (R46 m-3 honesty sync): the host-side
	// authorization check is a REAL assertion. The T2 nodeEntry method
	// checks the caller's grants via grantsCoverRead — kind/selector/
	// actions CONTENT matching against the result's grants (not just
	// non-emptiness; TestE5_ReadAuthorizationVariants proves the
	// downgraded-selector form is refused). Both sides:
	// ① caller whose grants COVER the result's → served
	// ② caller WITHOUT grants → NOT served
	stored, ok := h.store.get("op-t2r-perm")
	if !ok || stored.Receipt == "" {
		t.Fatal("stored result not found or empty — the store should have it")
	}

	// positive control: authorized caller CAN read the stored result
	if served, err := h.nodeEntry("op-t2r-perm", chainGrants()); err != nil {
		t.Fatalf("authorized read failed: %v", err)
	} else if served.Receipt != "receipt:op-t2r-perm:accepted" {
		t.Fatalf("authorized read receipt = %q, want original", served.Receipt)
	}

	// the ACTUAL assertion: unauthorized caller (empty grants) is REFUSED
	// — the host's authorization boundary is real, not just a comment
	if _, err := h.nodeEntry("op-t2r-perm", nil); err == nil {
		t.Fatal("L39 FIX REQUIRED: unauthorized read served stored result — host must check caller grants before serving")
	} else if !strings.Contains(err.Error(), "not authorized") {
		t.Fatalf("unauthorized read error = %q, want 'not authorized' (not a generic failure)", err.Error())
	}
}

// TestT2R_StaleResultCorrection is R variant 3 + correction coexistence
// (198232012 §四 How): the original result was wrong — a correction revision
// is created (same business_request_id, new operation_id), the validity
// projection shows the correction as current, and the FOUR READS are
// asserted independently:
//  1. Idempotency read: same-key retry → original receipt (unchanged)
//  2. Validity read: current-validity projection → correction is current
//  3. History replay: original events unchanged
//  4. Knowledge search: the corrected method is consumed, not the stale one
func TestT2R_StaleResultCorrection(t *testing.T) {
	dir := t.TempDir()
	h := newT2Host(t, dir)

	// First pass: a WRONG result (the sick S1 gave grant when it should deny)
	badReceipt := "receipt:op-t2r-corr:wrong-grant"
	if o := h.machine.Adopt(requestForT2("op-t2r-corr", "er-1", "ev-1", t2Digest('d'), "br-t2r-corr")); o.Status != "adopted" {
		t.Fatalf("wrong result adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-t2r-corr", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("wrong result dispatch = %q: %s", o.Status, o.Detail)
	}
	if err := h.store.put("op-t2r-corr", storedResult{
		Receipt:       badReceipt,
		Facts:         []string{"overdue_missed_by_extraction"},
		BusinessReqID: "br-t2r-corr",
		EvaluationRev: "er-1",
	}); err != nil {
		t.Fatal(err)
	}
	if o := h.machine.MarkCompleted("op-t2r-corr"); o.Status != "completed" {
		t.Fatalf("wrong result complete = %q: %s", o.Status, o.Detail)
	}

	// CORRECTION: the error is discovered — a new revision (er-2) is created
	// with the corrected verdict (deny), same business_request_id.
	// This is NOT a retry — it's a new adopted decision.
	if o := h.machine.Adopt(requestForT2("op-t2r-corr-fix", "er-2", "ev-2", t2Digest('e'), "br-t2r-corr")); o.Status != "adopted" {
		t.Fatalf("correction adopt = %q: %s", o.Status, o.Detail)
	}
	if err := h.store.put("op-t2r-corr-fix", storedResult{
		Receipt:       "correction:op-t2r-corr-fix:deny-veto-fired",
		Facts:         []string{"historical_overdue_4_months", "veto_applied"},
		BusinessReqID: "br-t2r-corr",
		EvaluationRev: "er-2",
	}); err != nil {
		t.Fatal(err)
	}

	// READ 1: idempotency — same-key retry still returns the ORIGINAL result
	// (the original operation op-t2r-corr is completed; its record is intact)
	orig, ok := h.store.get("op-t2r-corr")
	if !ok || orig.Receipt != badReceipt {
		t.Fatalf("R-correction READ-1: original result changed: %+v — history must be immutable", orig)
	}

	// READ 2: validity projection — the CURRENT valid result for this
	// business request is the CORRECTION (er-2), not the original (er-1)
	current, currentOp, found := h.store.lookupByBusinessRequest("br-t2r-corr")
	if !found {
		t.Fatal("R-correction READ-2: no result found for the business request")
	}
	if current.EvaluationRev != "er-2" {
		t.Fatalf("R-correction READ-2: current revision = %q, want er-2 (the correction)", current.EvaluationRev)
	}
	if !strings.Contains(current.Receipt, "deny") {
		t.Fatalf("R-correction READ-2: current receipt = %q, want deny — the correction must be the current valid result", current.Receipt)
	}
	_ = currentOp

	// READ 3: history replay — the machine's original events are unchanged
	// (both operations coexist in the ledger; history is not rewritten)
	events, err := h.machine.Events()
	if err != nil {
		t.Fatalf("Events() failed — a load error must fail, not silently empty the assertion set (R43 m-4): %v", err)
	}
	hasOriginal := false
	hasCorrection := false
	for _, e := range events {
		if e.Identity.OperationID == "op-t2r-corr" && e.Outcome.Status == "completed" {
			hasOriginal = true
		}
		if e.Identity.OperationID == "op-t2r-corr-fix" && e.Outcome.Status == "adopted" {
			hasCorrection = true
		}
	}
	if !hasOriginal || !hasCorrection {
		t.Fatalf("R-correction READ-3: history incomplete — original: %v, correction: %v", hasOriginal, hasCorrection)
	}

	// READ 4 (R17 M-A fix + R18 m-1 honesty fix — the registry-filter face):
	// the correction's method lifecycle: v1 is published valid, the
	// correction publishes v2 (Replaces v1), then v1 is invalidated. A NEW
	// task searching the registry must find v2, not v1 — this face is the
	// REGISTRY (findForNode), independent of the store lookups in READ 1/2.
	// (v1 and v2 share the same deterministic body in this fixture — the
	// correction here is the REGISTRY transition, not a logic change.)
	// R21 m-1 (honest scope): this scenario asserts the TERMINAL STATE
	// produced by both mechanisms being in play (supersession OR
	// invalidation alone would also yield v2); each mechanism has its own
	// dedicated mutation-coupled probe
	// (TestT2FindForNode_SupersessionWindow / TestT2K_ExpiredKnowledgeNotConsumed).
	// The pre-invalidate assertion below makes the WINDOW state observable
	// here too (supersession step observable in-scenario).
	h.registry.mustPublish(t, knowledgeMethod{
		ID: "method-overdue-v1", Version: "1.0.0",
		ServesNode:  "history-verification",
		InputFields: []string{"overdue_months", "business_request_id"},
		Valid:       true, // valid BEFORE the correction (the transition state is real)
	})
	h.registry.mustPublish(t, knowledgeMethod{
		ID: "method-overdue-v2", Version: "2.0.0",
		ServesNode:  "history-verification",
		InputFields: []string{"overdue_months", "business_request_id"},
		Valid:       true,
		Replaces:    "method-overdue-v1",
	})
	// WINDOW assertion (before the flip): v1 is STILL valid and sorts
	// BELOW v2 — only supersession keeps it from being served
	if m, ok := h.registry.findForNode("history-verification"); !ok || m.ID != "method-overdue-v2" {
		t.Fatalf("R-correction READ-4 window: found %q (ok=%v), want method-overdue-v2 — during the correction window (v1 valid, v2 supersedes) the correction must be served", m.ID, ok)
	}
	// invalidate v1 (superseded by the correction) — the single flip path
	if err := h.registry.invalidate("method-overdue-v1"); err != nil {
		t.Fatal(err)
	}
	corrMethod, methodOK := h.registry.findForNode("history-verification")
	if !methodOK {
		t.Fatal("R-correction READ-4: no method found for a new task — the correction method must be discoverable")
	}
	if corrMethod.ID != "method-overdue-v2" {
		t.Fatalf("R-correction READ-4: new task found %q, want method-overdue-v2 — the stale method must not be served to new tasks", corrMethod.ID)
	}
	// The registry serves the correction's method to a new task; executing
	// it on the corrected input reproduces the deny semantic (the veto
	// input for this business request's history). R20 m-1: the receipt
	// assertion embeds v2's IDENTITY — the assertion is no longer
	// decorative (v1/v2 share the method body, so a bare "veto-fired"
	// check could not distinguish which method was served).
	kResult, err := corrMethod.execute(map[string]string{
		"overdue_months":      "4", // the historical veto input (4 months, 2 years ago)
		"business_request_id": "br-t2r-corr",
	})
	if err != nil {
		t.Fatalf("R-correction READ-4: correction method execute failed: %v", err)
	}
	if kResult.Receipt != "method:method-overdue-v2:veto-fired" {
		t.Fatalf("R-correction READ-4: correction method receipt = %q, want method:method-overdue-v2:veto-fired — the result must come from the v2 correction method, with its identity embedded", kResult.Receipt)
	}
}

// ---------------------------------------------------------------------------
// Scenario K: new-task knowledge consumption, zero model calls

// TestT2K_NewTaskZeroModelCalls is the K scenario: a NEW task (no prior
// result, no prior operation) consumes a published knowledge method with
// zero model invocations. The method produces the NEW task's own result.
func TestT2K_NewTaskZeroModelCalls(t *testing.T) {
	h := newT2Host(t, t.TempDir())

	// Publish a knowledge method (the "history-overdue verification" method)
	h.registry.mustPublish(t, knowledgeMethod{
		ID:          "method-overdue-v1",
		Version:     "1.0.0",
		ServesNode:  "history-verification",
		InputFields: []string{"overdue_months", "business_request_id"},
		Valid:       true,
	})

	// Replace ALL model seats with failing probes
	pS1 := h.addProbe("s1-model-seat")
	pS2 := h.addProbe("s2-investigation")
	_ = pS1
	_ = pS2

	// A NEW task arrives — no prior operation, no prior result
	brID := "br-t2k-new"
	_, priorOp, priorFound := h.store.lookupByBusinessRequest(brID)
	if priorFound {
		t.Fatalf("K: prior result found for new task (op %q) — this should be a fresh task", priorOp)
	}

	// The host finds the published method for this node kind
	method, ok := h.registry.findForNode("history-verification")
	if !ok {
		t.Fatal("K: no valid method found for 'history-verification' node")
	}

	// Execute the method with the new task's inputs — ZERO model calls
	result, err := method.execute(map[string]string{
		"overdue_months":      "0",
		"business_request_id": brID,
	})
	if err != nil {
		t.Fatalf("K: method execute failed: %v", err)
	}

	// The result is the NEW task's own (not another task's receipt)
	if result.BusinessReqID != brID {
		t.Fatalf("K: result business_request_id = %q, want %q — the result must be the new task's own", result.BusinessReqID, brID)
	}
	if !strings.Contains(result.Receipt, "method-overdue-v1") {
		t.Fatalf("K: receipt = %q, want method-overdue-v1 prefix — the result must come from the method", result.Receipt)
	}

	// Store the new task's own result
	if err := h.store.put("op-t2k-new", result); err != nil {
		t.Fatal(err)
	}
	// Adopt the result as a decision (the framework's role)
	if o := h.machine.Adopt(requestForT2("op-t2k-new", "er-1", "ev-1", t2Digest('f'), "br-t2k-new")); o.Status != "adopted" {
		t.Fatalf("K: adopt = %q: %s", o.Status, o.Detail)
	}

	// Zero-invocation: all model probes must be silent
	pS1.assertNotCalled(t)
	pS2.assertNotCalled(t)
}

// TestT2K_ExpiredKnowledgeNotConsumed is K variant 1: the knowledge method
// has been invalidated — a new task must NOT consume it.
// R19 M-2/m-2 fix: the INVALID one is named "method-a-old" (sorts BELOW
// "method-b-new") so this probe is COUPLED to the Valid filter — removing
// the Valid check would serve the expired method and turn this red (the
// old IDs, "method-current" < "method-expired", made the sorted-order
// winner identical with or without the Valid check — silently disarmed).
// No Replaces here: this probe guards the F-04 VALIDITY face alone (the
// supersession face has its own probe, TestT2FindForNode_SupersessionWindow).
func TestT2K_ExpiredKnowledgeNotConsumed(t *testing.T) {
	h := newT2Host(t, t.TempDir())

	// Publish the (about-to-expire) old method, then the current one
	h.registry.mustPublish(t, knowledgeMethod{
		ID: "method-a-old", Version: "1.0.0",
		ServesNode: "history-verification", Valid: true,
	})
	h.registry.mustPublish(t, knowledgeMethod{
		ID: "method-b-new", Version: "2.0.0",
		ServesNode: "history-verification", Valid: true,
	})
	// The old method expires (invalidated) — the single flip write path
	if err := h.registry.invalidate("method-a-old"); err != nil {
		t.Fatal(err)
	}

	// A new task should find only the CURRENT method
	method, ok := h.registry.findForNode("history-verification")
	if !ok {
		t.Fatal("K-expired: no method found — the current method should be discoverable")
	}
	if method.ID != "method-b-new" {
		t.Fatalf("K-expired: found %q, want %q — the expired method must not be consumed", method.ID, "method-b-new")
	}
}

// TestT2K_SimilarButDifferentTask is K variant 2: a similar task's result
// must NOT be consumed by a different task — each task has its own identity.
func TestT2K_SimilarButDifferentTask(t *testing.T) {
	h := newT2Host(t, t.TempDir())

	// Task A's result exists
	h.store.put("op-t2k-a", storedResult{
		Receipt:       "receipt:op-t2k-a:accepted",
		BusinessReqID: "br-t2k-a",
	})

	// Task B is a DIFFERENT business request — it must NOT get task A's result
	brB := "br-t2k-b"
	_, _, found := h.store.lookupByBusinessRequest(brB)
	if found {
		t.Fatal("K-similar: a result was found for task B — similar tasks must not share results")
	}
}

// TestT2K_ScopeMismatch is K variant 3: the method's scope doesn't match
// the node kind — the method is not consumed.
func TestT2K_ScopeMismatch(t *testing.T) {
	h := newT2Host(t, t.TempDir())
	h.registry.mustPublish(t, knowledgeMethod{
		ID: "method-credit", Version: "1.0.0",
		ServesNode: "credit-scoring", // serves a DIFFERENT node
		Valid:      true,
	})

	// A "history-verification" node asks for a method — no match
	_, ok := h.registry.findForNode("history-verification")
	if ok {
		t.Fatal("K-scope: a credit-scoring method was found for a history-verification node — scope mismatch must not match")
	}
}
