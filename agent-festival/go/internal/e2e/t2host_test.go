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
	// "最新已采纳修订=当前有效"). Revisions are lexically ordered (er-1 < er-2).
	var best storedResult
	bestOp := ""
	found := false
	for opID, r := range rs.data {
		if r.BusinessReqID != brID {
			continue
		}
		if !found || r.EvaluationRev > best.EvaluationRev {
			best = r
			bestOp = opID
			found = true
		}
	}
	return best, bestOp, found
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
// node's result. The method body is a pure function of its declared inputs —
// in production this would call a domain service or rule engine; in T2 it
// is a deterministic function for test reproducibility.
func (m knowledgeMethod) execute(inputs map[string]string) storedResult {
	// the T2 method: "history-overdue verification" — checks the input facts
	// for any overdue > 3 months (the unbounded veto from the corrected spec)
	facts := []string{}
	receipt := fmt.Sprintf("method:%s:result", m.ID)
	overdueMonths := 0
	if v, ok := inputs["overdue_months"]; ok {
		fmt.Sscanf(v, "%d", &overdueMonths)
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
	}
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
func (kr *knowledgeRegistry) findForNode(nodeKind string) (knowledgeMethod, bool) {
	for _, m := range kr.methods {
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
