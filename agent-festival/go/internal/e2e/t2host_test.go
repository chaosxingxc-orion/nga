package e2e

// T2 reference-host tier: the minimal node entry, result store, and failing
// adapter probes required to accept scenario R (persisted result reuse
// across restart) and scenario K (new-task knowledge consumption with zero
// model calls). This is a VERIFICATION fixture, not a production framework —
// it demonstrates that the control-semantics contracts (piece 2/4/7) accept
// a host that stores results outside the ledger and routes through
// knowledge methods, without the ledger schema changing.
//
// DESIGN (from 31-rk-scope-prior.md):
//   resultStore: independent JSON file (T2 host layer, NOT the ledger —
//   the ledger stays lean, recording decisions and effects; receipts/facts/
//   references live in the host's persistence file). Keyed by operation_id.
//   The R scenario proves the store survives restart (file-backed, not
//   in-memory).
//
//   knowledgeMethod: a registered method with declared applicability
//   (EDPA SPI-ownership form — the method declares which node kinds it
//   serves and its input contract). The K scenario proves a new task can
//   consume a published method with zero model calls and produce its OWN
//   result (not another task's receipt).
//
//   failingAdapter: replaces model seats and the business API with probes
//   that FAIL if called — proving zero-invocation by construction, not by
//   counter (the counter can be bypassed; the adapter cannot).

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// ---------------------------------------------------------------------------
// resultStore: T2 host-layer persistence for node results (receipts, facts,
// references). File-backed JSON, keyed by operation_id. Survives restart.

type storedResult struct {
	Receipt       string   `json:"receipt"`
	Facts         []string `json:"facts"`
	References    []string `json:"references"`
	BusinessReqID string   `json:"business_request_id"`
	EvaluationRev string   `json:"evaluation_revision"`
	KnowledgeUsed string   `json:"knowledge_used,omitempty"`
}

// resultStore is the T2 host's persistence for node results. It is NOT the
// ledger — the ledger records decisions and effects (piece 4's lean
// contract); this store holds the receipt/facts payload the host needs to
// answer "what was the node's result?" without re-running the node.
type resultStore struct {
	mu   sync.Mutex
	path string
	data map[string]storedResult // keyed by operation_id
}

func newResultStore(dir string) (*resultStore, error) {
	rs := &resultStore{
		path: filepath.Join(dir, "t2-results.json"),
		data: map[string]storedResult{},
	}
	raw, err := os.ReadFile(rs.path)
	if err != nil {
		if os.IsNotExist(err) {
			return rs, nil // fresh store
		}
		return nil, err
	}
	if err := json.Unmarshal(raw, &rs.data); err != nil {
		return nil, fmt.Errorf("[T2.RESULT_STORE] corrupt result store: %v", err)
	}
	return rs, nil
}

func (rs *resultStore) put(opID string, r storedResult) error {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	rs.data[opID] = r
	raw, err := json.MarshalIndent(rs.data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(rs.path, raw, 0o600)
}

func (rs *resultStore) get(opID string) (storedResult, bool) {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	r, ok := rs.data[opID]
	return r, ok
}

// lookupByBusinessRequest finds the LATEST result for a business request
// (the "current validity projection" — per 29-reconciliation §3.2, the
// projection is a T2-layer function over results, not a machine state).
func (rs *resultStore) lookupByBusinessRequest(brID string) (storedResult, string, bool) {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	// The validity projection: the LATEST evaluation revision for this
	// business request is the current valid result (per 29-reconciliation:
	// "最新已采纳修订=当前有效").
	// L42 fix: revision comparison is now numeric, not lexical (er-10 > er-2
	// under lexical ordering — the old code would pick er-2 as "later").
	// Iteration order is made deterministic by sorting keys (L43 fix).
	var best storedResult
	bestOp := ""
	bestRev := -1
	found := false
	for _, opID := range sortedKeys(rs.data) {
		r := rs.data[opID]
		if r.BusinessReqID != brID {
			continue
		}
		rev := revisionNumber(r.EvaluationRev)
		if !found || rev > bestRev {
			best = r
			bestOp = opID
			bestRev = rev
			found = true
		}
	}
	return best, bestOp, found
}

// revisionNumber extracts the numeric suffix from "er-N" (returns -1 if
// unparseable — the caller treats it as the lowest revision).
// R18 M-3 family: strconv.Atoi (strict full-string parse) — fmt.Sscanf
// prefix-parses, so "er-2x" would have sorted as revision 2.
func revisionNumber(rev string) int {
	rev = strings.TrimPrefix(rev, "er-")
	n, err := strconv.Atoi(rev)
	if err != nil {
		return -1
	}
	return n
}

// sortedKeys returns map keys in sorted order (deterministic iteration —
// L43 fix: map iteration order is random in Go, making findForNode and
// lookupByBusinessRequest nondeterministic across runs).
func sortedKeys[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// ---------------------------------------------------------------------------
// failingAdapter: replaces a model seat or the business API with a probe
// that FAILS the test if invoked. Zero-invocation is proven by construction
// (the probe panics the test), not by counter.

type failingProbe struct {
	t      *testing.T
	name   string
	called bool
}

func newFailingProbe(t *testing.T, name string) *failingProbe {
	return &failingProbe{t: t, name: name}
}

func (p *failingProbe) invoke(args ...string) string {
	p.called = true
	p.t.Fatalf("T2 probe %q was invoked — zero-invocation contract violated (args: %v)", p.name, args)
	return "" // unreachable in tests (Fatalf exits)
}

func (p *failingProbe) assertNotCalled(t *testing.T) {
	t.Helper()
	if p.called {
		t.Fatalf("T2 probe %q was called during the test — zero-invocation contract violated", p.name)
	}
}

// ---------------------------------------------------------------------------
// knowledgeMethod: a registered, versioned method with declared
// applicability. The K scenario's "published knowledge" — consumed by node
// entry, not by LLM.

type knowledgeMethod struct {
	ID          string   `json:"id"`
	Version     string   `json:"version"`
	ServesNode  string   `json:"serves_node"`        // the node kind this method owns (EDPA SPI form)
	InputFields []string `json:"input_fields"`       // required input contract
	Valid       bool     `json:"valid"`              // validity flag (F-04 freshness governance)
	Replaces    string   `json:"replaces,omitempty"` // the method ID this one supersedes
}

// execute runs the method deterministically (zero LLM) and returns the
// node's result, or an error when the declared input contract is violated.
// The method body is a pure function of its declared inputs —
// in production this would call a domain service or rule engine; in T2 it
// is a deterministic function for test reproducibility.
func (m knowledgeMethod) execute(inputs map[string]string) (storedResult, error) {
	// the T2 method: "history-overdue verification" — checks the input facts
	// for any overdue > 3 months (the unbounded veto from the corrected spec)
	facts := []string{}
	receipt := fmt.Sprintf("method:%s:result", m.ID)
	overdueMonths := 0
	// R18 M-2: the DECLARED required inputs must be PRESENT — a missing
	// key fails closed. The extraction-miss disease (E0) is exactly the
	// missing-key form: the upstream never extracted the field, so the
	// veto input arrives absent and must not default to 0.
	for _, f := range m.InputFields {
		if _, ok := inputs[f]; !ok {
			return storedResult{}, fmt.Errorf("[T2.METHOD %s] required input %q is missing — refusing to produce a result without a declared contract input (fail-closed, R18 M-2)", m.ID, f)
		}
	}
	if v, ok := inputs["overdue_months"]; ok {
		// L44 fix (R17 M-C) + R18 M-3: the veto input is SAFETY-CRITICAL —
		// an unparseable overdue_months FAILS CLOSED (error), never treated
		// as 0. Treating it as 0 would mean a corrupted input silently
		// disarms the veto (the E0 extraction-miss disease, method-shaped).
		// R18 M-3: strconv.Atoi is a STRICT full-string parse — fmt.Sscanf
		// prefix-parses ("0abc"→0, "2xyz"→2, "0.5"→0 with no error), which
		// let corrupted inputs through the fail-closed gate.
		n, err := strconv.Atoi(v)
		if err != nil {
			return storedResult{}, fmt.Errorf("[T2.METHOD %s] overdue_months input %q is not a number — refusing to produce a result on a corrupted veto input (fail-closed, L44)", m.ID, v)
		}
		overdueMonths = n
	}
	if overdueMonths > 3 {
		facts = append(facts, fmt.Sprintf("overdue_%d_months_found", overdueMonths))
		receipt = fmt.Sprintf("method:%s:veto-fired", m.ID)
	} else {
		facts = append(facts, "no_overdue_beyond_threshold")
	}
	return storedResult{
		Receipt:       receipt,
		Facts:         facts,
		BusinessReqID: inputs["business_request_id"],
	}, nil
}

// knowledgeRegistry is the T2 host's method registry (published methods).
type knowledgeRegistry struct {
	methods map[string]knowledgeMethod
}

func newKnowledgeRegistry() *knowledgeRegistry {
	return &knowledgeRegistry{methods: map[string]knowledgeMethod{}}
}

func (kr *knowledgeRegistry) publish(m knowledgeMethod) {
	kr.methods[m.ID] = m
}

// findForNode returns the valid method serving the given node kind, or
// false. Validity is checked (F-04: expired/superseded methods are not
// consumed for new tasks).
// R18 M-1: iteration is DETERMINISTIC via sortedKeys — on multiple valid
// methods serving the same node kind (e.g. the correction window where
// v2 is published before v1 is flipped invalid), the
// lexicographically-lowest method ID wins. Raw map ranging made this
// choice random (~88/12 per probe), silently nondeterministic.
func (kr *knowledgeRegistry) findForNode(nodeKind string) (knowledgeMethod, bool) {
	for _, id := range sortedKeys(kr.methods) {
		m := kr.methods[id]
		if m.ServesNode == nodeKind && m.Valid {
			return m, true
		}
	}
	return knowledgeMethod{}, false
}

// ---------------------------------------------------------------------------
// t2Host: the reference host that wires everything together.

// t2Host is the reference host for scenarios R and K. It wraps the adopt
// machine with a result store and a knowledge registry — the minimum host
// surface needed to demonstrate the control contracts accepting a real
// host's result persistence and knowledge consumption.
type t2Host struct {
	t        *testing.T
	dir      string
	machine  *adopt.Machine
	store    *resultStore
	registry *knowledgeRegistry
	probes   map[string]*failingProbe
}

func newT2Host(t *testing.T, dir string) *t2Host {
	t.Helper()
	m, err := adopt.Open(filepath.Join(dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	rs, err := newResultStore(dir)
	if err != nil {
		t.Fatal(err)
	}
	return &t2Host{
		t:        t,
		dir:      dir,
		machine:  m,
		store:    rs,
		registry: newKnowledgeRegistry(),
		probes:   map[string]*failingProbe{},
	}
}

// reopen simulates a host restart: a fresh machine instance (the ledger is
// the durable state) + a fresh resultStore (file-backed — it survives).
func (h *t2Host) reopen() *t2Host {
	h.t.Helper()
	m, err := adopt.Open(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		h.t.Fatal(err)
	}
	rs, err := newResultStore(h.dir)
	if err != nil {
		h.t.Fatal(err)
	}
	return &t2Host{
		t:        h.t,
		dir:      h.dir,
		machine:  m,
		store:    rs,
		registry: h.registry, // registry is in-memory (published methods survive via re-publication in the test)
		probes:   h.probes,
	}
}

// addProbe registers a failing probe under a name — the test replaces a
// model seat or the business API with this probe to prove zero invocation.
func (h *t2Host) addProbe(name string) *failingProbe {
	p := newFailingProbe(h.t, name)
	h.probes[name] = p
	return p
}

// requestForT2 builds the adoption request with the T2 scenario's OWN
// business_request_id (the T0 requestFor hardcodes "br-e2e-credit" — using
// it here would put a wrong brID in the ledger Identity while the T2 store
// records the real one. R12' review found this MAJOR; this is the fix).
func requestForT2(op, revision, evidence, digest, brID string) *adopt.Request {
	return &adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: brID, EvaluationRevision: revision, OperationID: op},
		Versions:         ledger.Versions{Evidence: evidence, Rule: "rule-credit-v1", Model: "s1-standin", Readout: "r-1", Policy: "p-1"},
		PayloadDigest:    digest,
		GrantsAtDecision: chainGrants(),
		Accountability:   &ledger.Accountability{Session: "sess-t2", Skill: "skill-credit", Role: "employee"},
	}
}

// nodeEntry is the T2 reference host's unified node entry point (L41 fix:
// the "re-submit the same node execution" logic was previously inlined in
// test bodies; now it's a named component the tests call). It checks the
// caller's authorization (L39 fix: host-side read authorization), checks
// the machine state, and serves the stored result if the operation is
// complete — or errors if the caller is not authorized.
func (h *t2Host) nodeEntry(opID string, callerGrants []ledger.Grant) (storedResult, error) {
	// L39: host-side authorization check — the host checks its own access
	// rules before serving stored results (per MR#1 consensus: the framework
	// enforces the contract; the host checks its own permissions).
	if len(callerGrants) == 0 {
		return storedResult{}, fmt.Errorf("[T2.NODE_ENTRY] %s: caller not authorized to read stored results (empty grants)", opID)
	}
	// check the machine state — if completed, serve the stored result
	if s := h.machine.State(opID); s != adopt.StateCompleted {
		return storedResult{}, fmt.Errorf("[T2.NODE_ENTRY] %s: operation not completed (state=%v)", opID, s)
	}
	// serve from the store
	r, ok := h.store.get(opID)
	if !ok {
		return storedResult{}, fmt.Errorf("[T2.NODE_ENTRY] %s: no stored result found", opID)
	}
	return r, nil
}

// adoptAndDispatch is the standard first-pass flow: adopt + dispatch +
// store the receipt. Returns the outcome for assertions.
func (h *t2Host) adoptAndDispatch(op, revision, evidence, digest, brID string, receipt string, facts []string) adopt.Outcome {
	o := h.machine.Adopt(requestForT2(op, revision, evidence, digest, brID))
	if o.Status != "adopted" {
		return o
	}
	o2 := h.machine.Dispatch(op, chainGrants())
	if o2.Status != "dispatched" {
		return o2
	}
	// store the result in the T2 host layer (the ledger records the
	// dispatch decision; the store holds the receipt/facts payload)
	if err := h.store.put(op, storedResult{
		Receipt:       receipt,
		Facts:         facts,
		BusinessReqID: brID,
		EvaluationRev: revision,
	}); err != nil {
		h.t.Fatalf("T2 result store put failed: %v", err)
	}
	return o2
}

// completeNode marks the operation complete (the host observes the external
// terminal state and calls the machine).
func (h *t2Host) completeNode(op string) adopt.Outcome {
	return h.machine.MarkCompleted(op)
}

// ---------------------------------------------------------------------------
// R17 M-B probes: component-level red probes for the T2 bearing fixes
// (L42 numeric revision ordering, L43 deterministic iteration, nodeEntry
// branches) and the M-C fail-closed probe (L44). Each probe is coupled to
// a mutation: reverting its fix must turn the probe RED.

// TestT2Lookup_RevisionOrdering probes L42: the validity projection picks
// the LATEST revision NUMERICALLY (er-10 > er-2), not lexically (where
// "er-2" > "er-10"). Mutation probe: revert revisionNumber to a
// lexical-family comparison and this test fails.
func TestT2Lookup_RevisionOrdering(t *testing.T) {
	rs, err := newResultStore(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := rs.put("op-ord-a", storedResult{Receipt: "r-er-2", BusinessReqID: "br-ord", EvaluationRev: "er-2"}); err != nil {
		t.Fatal(err)
	}
	if err := rs.put("op-ord-b", storedResult{Receipt: "r-er-10", BusinessReqID: "br-ord", EvaluationRev: "er-10"}); err != nil {
		t.Fatal(err)
	}
	r, _, found := rs.lookupByBusinessRequest("br-ord")
	if !found {
		t.Fatal("L42 probe: no result found for br-ord")
	}
	if r.EvaluationRev != "er-10" {
		t.Fatalf("L42 probe: current revision = %q, want er-10 — numeric ordering (er-10 > er-2); a lexical comparison would pick er-2", r.EvaluationRev)
	}

	// unparseable revision sorts lowest (revisionNumber = -1): er-x loses
	// to er-1
	rs2, err := newResultStore(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := rs2.put("op-un-a", storedResult{Receipt: "r-er-x", BusinessReqID: "br-un", EvaluationRev: "er-x"}); err != nil {
		t.Fatal(err)
	}
	if err := rs2.put("op-un-b", storedResult{Receipt: "r-er-1", BusinessReqID: "br-un", EvaluationRev: "er-1"}); err != nil {
		t.Fatal(err)
	}
	r2, _, found2 := rs2.lookupByBusinessRequest("br-un")
	if !found2 || r2.EvaluationRev != "er-1" {
		t.Fatalf("L42 probe: unparseable-revision case = %q (found=%v), want er-1 — an unparseable revision must sort LOWEST", r2.EvaluationRev, found2)
	}
}

// TestT2Lookup_TieBreakDeterminism probes L43: when two results share the
// SAME revision, the winner is the lexicographically-lowest operation_id
// (sortedKeys + strict >), and the winner is STABLE across iterations —
// Go randomizes map iteration order per range, so only the sorted
// iteration makes this deterministic. Mutation probe: disable the sort in
// sortedKeys and this test fails within a few iterations.
func TestT2Lookup_TieBreakDeterminism(t *testing.T) {
	rs, err := newResultStore(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := rs.put("op-tie-z", storedResult{Receipt: "r-tie-z", BusinessReqID: "br-tie", EvaluationRev: "er-5"}); err != nil {
		t.Fatal(err)
	}
	if err := rs.put("op-tie-a", storedResult{Receipt: "r-tie-a", BusinessReqID: "br-tie", EvaluationRev: "er-5"}); err != nil {
		t.Fatal(err)
	}
	// 50 iterations: each lookup ranges the map once; without sorted
	// iteration the winner flips (random start offset per range)
	for i := 0; i < 50; i++ {
		r, opID, found := rs.lookupByBusinessRequest("br-tie")
		if !found {
			t.Fatal("L43 probe: no result found for br-tie")
		}
		if opID != "op-tie-a" {
			t.Fatalf("L43 probe: iteration %d winner = %q, want op-tie-a (lexicographically-lowest op_id on equal revision) — iteration order is nondeterministic", i, opID)
		}
		if r.Receipt != "r-tie-a" {
			t.Fatalf("L43 probe: iteration %d receipt = %q, want r-tie-a", i, r.Receipt)
		}
	}
}

// TestT2NodeEntry_Branches probes the nodeEntry component's error branches
// (L41 extraction): not-completed operation and completed-but-unstored
// operation both refuse. The unauthorized branch and the happy path are
// asserted in TestT2R_PermissionRevoked (L39).
func TestT2NodeEntry_Branches(t *testing.T) {
	h := newT2Host(t, t.TempDir())

	// adopt + dispatch but NOT completed → nodeEntry refuses
	if o := h.adoptAndDispatch("op-branch-1", "er-1", "ev-1", t2Digest('a'), "br-branch", "receipt:op-branch-1", nil); o.Status != "dispatched" {
		t.Fatalf("branch probe: adoptAndDispatch = %q: %s", o.Status, o.Detail)
	}
	if _, err := h.nodeEntry("op-branch-1", chainGrants()); err == nil {
		t.Fatal("branch probe: nodeEntry served an operation that is dispatched but NOT completed — must refuse")
	} else if !strings.Contains(err.Error(), "not completed") {
		t.Fatalf("branch probe: error = %q, want 'not completed'", err.Error())
	}

	// completed but no stored result → nodeEntry refuses. R18 m-2 fix:
	// drive the machine directly (Adopt/Dispatch/MarkCompleted, NO
	// adoptAndDispatch) so the result is NEVER persisted — the honest
	// "completed without persisting" scenario (previously the probe
	// persisted then deleted from the in-memory map, leaving the file
	// entry alive)
	if o := h.machine.Adopt(requestForT2("op-branch-2", "er-1", "ev-1", t2Digest('b'), "br-branch")); o.Status != "adopted" {
		t.Fatalf("branch probe: adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-branch-2", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("branch probe: dispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-branch-2"); o.Status != "completed" {
		t.Fatalf("branch probe: MarkCompleted = %q: %s", o.Status, o.Detail)
	}
	if _, ok := h.store.get("op-branch-2"); ok {
		t.Fatal("branch probe: fixture error — op-branch-2 should never have been stored")
	}
	if _, err := h.nodeEntry("op-branch-2", chainGrants()); err == nil {
		t.Fatal("branch probe: nodeEntry served a completed operation with NO stored result — must refuse")
	} else if !strings.Contains(err.Error(), "no stored result") {
		t.Fatalf("branch probe: error = %q, want 'no stored result'", err.Error())
	}
}

// TestT2Method_ParseErrorFailsClosed probes the L44 fix (R17 M-C) and its
// R18 M-2/M-3 extensions: the veto input fails closed on ALL corrupted
// forms — unparseable ("not-a-number"), prefix-parseable garbage that
// Sscanf would have accepted ("0abc", "2xyz", "0.5"), and MISSING (the
// extraction-miss form — the declared required input absent). Mutation
// probes: revert Atoi to Sscanf and the "0abc" case fails; remove the
// InputFields presence loop and the missing-key case fails.
func TestT2Method_ParseErrorFailsClosed(t *testing.T) {
	m := knowledgeMethod{
		ID:          "method-parse-probe",
		Version:     "1.0.0",
		ServesNode:  "history-verification",
		InputFields: []string{"overdue_months", "business_request_id"},
		Valid:       true,
	}
	badInputs := []string{"not-a-number", "0abc", "2xyz", "0.5", ""}
	for _, bad := range badInputs {
		_, err := m.execute(map[string]string{
			"overdue_months":      bad,
			"business_request_id": "br-parse",
		})
		if err == nil {
			t.Fatalf("L44/M-3 probe: overdue_months=%q produced a result (fail-open) — the veto input must fail CLOSED on every corrupted form", bad)
		}
		if !strings.Contains(err.Error(), "fail-closed") {
			t.Fatalf("L44/M-3 probe: error for %q = %q, want the fail-closed marker", bad, err.Error())
		}
	}

	// R18 M-2 probe: a DECLARED required input MISSING fails closed (the
	// extraction-miss form — the field never arrived, so it must not
	// default to 0 and silently disarm the veto)
	_, err := m.execute(map[string]string{
		"business_request_id": "br-parse",
	})
	if err == nil {
		t.Fatal("M-2 probe: a missing overdue_months (declared required) produced a result — missing inputs must fail CLOSED")
	}
	if !strings.Contains(err.Error(), "missing") {
		t.Fatalf("M-2 probe: error = %q, want the missing-input marker", err.Error())
	}

	// valid input still works (the fail-closed gates do not break the
	// happy path)
	r, err := m.execute(map[string]string{
		"overdue_months":      "4",
		"business_request_id": "br-parse",
	})
	if err != nil {
		t.Fatalf("L44 probe: valid input errored: %v", err)
	}
	if !strings.Contains(r.Receipt, "veto-fired") {
		t.Fatalf("L44 probe: receipt = %q, want veto-fired for 4-month overdue", r.Receipt)
	}
}

// TestT2FindForNode_Deterministic probes R18 M-1: with MULTIPLE valid
// methods serving the same node kind (the correction-window state — v2
// published before v1 is flipped invalid), findForNode must return a
// DETERMINISTIC winner: the lexicographically-lowest method ID. Mutation
// probe: revert findForNode to raw map ranging and the winner flips
// across iterations (raw ranging biased ~88/12 in measurement; escape
// probability across 200 iterations < 1e-10).
func TestT2FindForNode_Deterministic(t *testing.T) {
	kr := newKnowledgeRegistry()
	kr.publish(knowledgeMethod{ID: "method-c", Version: "1.0.0", ServesNode: "history-verification", Valid: true})
	kr.publish(knowledgeMethod{ID: "method-a", Version: "1.0.0", ServesNode: "history-verification", Valid: true})
	kr.publish(knowledgeMethod{ID: "method-b", Version: "1.0.0", ServesNode: "history-verification", Valid: true})
	for i := 0; i < 200; i++ {
		m, ok := kr.findForNode("history-verification")
		if !ok {
			t.Fatal("M-1 probe: no method found for history-verification")
		}
		if m.ID != "method-a" {
			t.Fatalf("M-1 probe: iteration %d winner = %q, want method-a (lexicographically-lowest ID among multiple valid methods) — selection is nondeterministic", i, m.ID)
		}
	}
	// invalid methods are filtered regardless of ID order (F-04 face)
	kr2 := newKnowledgeRegistry()
	kr2.publish(knowledgeMethod{ID: "method-a", ServesNode: "history-verification", Valid: false})
	kr2.publish(knowledgeMethod{ID: "method-b", ServesNode: "history-verification", Valid: true})
	m, ok := kr2.findForNode("history-verification")
	if !ok || m.ID != "method-b" {
		t.Fatalf("M-1 probe: expected method-b (the only valid one), got %q (ok=%v)", m.ID, ok)
	}
}
