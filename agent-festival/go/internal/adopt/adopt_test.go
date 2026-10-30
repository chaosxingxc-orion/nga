package adopt

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"festival-dev/go/internal/ledger"
)

// digestA/digestB are two well-formed distinct JCS-shape digests (fixture
// family: a/b/e hex, same as the ledger fixtures).
const (
	digestA = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	digestB = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
)

func testRequest(op, digest string, grants []ledger.Grant) *Request {
	return &Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-t", EvaluationRevision: "er-1", OperationID: op},
		Versions:         ledger.Versions{Evidence: "ev-1", Rule: "rule-1", Model: "m-1", Readout: "r-1", Policy: "p-1"},
		PayloadDigest:    digest,
		GrantsAtDecision: grants,
		Accountability:   &ledger.Accountability{Session: "sess-t", Skill: "skill-t", Role: "employee"},
	}
}

func pinGrants() []ledger.Grant {
	return []ledger.Grant{
		{Kind: "data", Selector: "ledger://credit/t", Actions: []string{"read"}, Effect: "none"},
		{Kind: "tool", Selector: "tool://credit-transfer", Actions: []string{"execute"}, Effect: "irreversible"},
	}
}

func mustOpen(t *testing.T, path string) *Machine {
	t.Helper()
	m, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	return m
}

// TestConcurrentDoubleAdoption is 14-A5 counterexample one: N goroutines race
// an identical request under one key. Exactly one adopts; every other gets
// 'reused' and the retry is a recorded fact; the durable file holds one
// 'adopted' + N-1 'reused' adoption events with a strictly increasing
// arbitration order (the machine lock is the arbitrator). Run with -race:
// the goroutines hit the same Machine and the same file.
func TestConcurrentDoubleAdoption(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	const n = 8
	results := make([]Outcome, n)
	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < n; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start
			results[i] = m.Adopt(testRequest("op-race", digestA, pinGrants()))
		}(i)
	}
	close(start)
	wg.Wait()

	adopted, reused, other := 0, 0, 0
	for _, r := range results {
		switch r.Status {
		case "adopted":
			adopted++
		case "reused":
			reused++
		default:
			other++
		}
	}
	if adopted != 1 || reused != n-1 || other != 0 {
		t.Fatalf("race outcome wrong: adopted=%d reused=%d other=%d (want 1/%d/0)", adopted, reused, n-1, other)
	}
	if m.State("op-race") != StateAdopted {
		t.Fatalf("state after race = %q, want adopted", m.State("op-race"))
	}
	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != n {
		t.Fatalf("durable events = %d, want %d (the retries are facts)", len(events), n)
	}
	prev := -1
	for i, e := range events {
		if e.ArbitrationSeq <= prev {
			t.Fatalf("event %d: arbitration_seq %d not increasing", i, e.ArbitrationSeq)
		}
		prev = e.ArbitrationSeq
		want := "reused"
		if i == 0 {
			want = "adopted"
		}
		if e.Outcome.Status != want {
			t.Fatalf("event %d status = %q, want %q", i, e.Outcome.Status, want)
		}
	}
}

// TestRetryReuseAfterTerminal pins the deeper idempotence point: a retry
// arriving after the operation already completed must 'reuse', never
// re-adopt — re-execution is the duplicate-effect bug the gate exists to
// stop.
func TestRetryReuseAfterTerminal(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-t1", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("first adopt = %q, want adopted", o.Status)
	}
	if o := m.Dispatch("op-t1", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q, want dispatched", o.Status)
	}
	if o := m.MarkCompleted("op-t1"); o.Status != "completed" {
		t.Fatalf("complete = %q, want completed", o.Status)
	}
	o := m.Adopt(testRequest("op-t1", digestA, pinGrants()))
	if o.Status != "reused" {
		t.Fatalf("retry after completion = %q, want reused (never re-adopted)", o.Status)
	}
	if m.State("op-t1") != StateCompleted {
		t.Fatalf("state after retry = %q, want completed", m.State("op-t1"))
	}
	events, _ := m.Events()
	if len(events) != 4 { // adopted, dispatched, completed, reused
		t.Fatalf("events = %d, want 4: %+v", len(events), events)
	}
}

// TestChangedPayloadSameKey is 14-A5 counterexample four: the same
// operation_id with a different payload digest is rejected, and the
// competitor's loss is recorded as a 'conflict' adoption event without
// idempotency (its digest never enters the registry — the concurrent
// double-adoption ledger fixture's shape).
func TestChangedPayloadSameKey(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-t2", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("first adopt = %q, want adopted", o.Status)
	}
	o := m.Adopt(testRequest("op-t2", digestB, pinGrants()))
	if o.Status != "rejected" {
		t.Fatalf("changed payload = %q, want rejected", o.Status)
	}
	events, _ := m.Events()
	if len(events) != 2 {
		t.Fatalf("events = %d, want 2 (adopted + conflict)", len(events))
	}
	if events[1].Outcome.Status != "conflict" {
		t.Fatalf("second event status = %q, want conflict", events[1].Outcome.Status)
	}
	if events[1].Idempotency != nil {
		t.Fatalf("conflict event carries idempotency — the loser's digest must not enter the registry")
	}
	if m.State("op-t2") != StateAdopted {
		t.Fatalf("state = %q, want adopted (the winner stands)", m.State("op-t2"))
	}
}

// TestCrashRecoveryTornTail is 14-A5 counterexample two: a crash mid-write
// leaves a torn tail line; reopening resumes at the last complete event
// boundary, and the grants pinned at adoption survive the crash (they ride
// the event) so the 14-A4 revocation check is NOT vacuous after recovery.
func TestCrashRecoveryTornTail(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-t3", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q, want adopted", o.Status)
	}
	// simulate the crash: a half-written line from a lost append race
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	torn := append(raw, []byte(`{"event_type":"effect","arbitration_seq":1,"ide`)...)
	if err := os.WriteFile(path, torn, 0o644); err != nil {
		t.Fatal(err)
	}

	m2 := mustOpen(t, path)
	if m2.State("op-t3") != StateAdopted {
		t.Fatalf("recovered state = %q, want adopted (torn tail skipped)", m2.State("op-t3"))
	}
	events, err := m2.Events()
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 {
		t.Fatalf("recovered events = %d, want 1 (torn tail excluded)", len(events))
	}
	// the pinned grants survived: a revoked live set is still rejected after recovery
	if o := m2.Dispatch("op-t3", []ledger.Grant{pinGrants()[0]}); o.Status != "rejected" {
		t.Fatalf("dispatch after recovery with revoked grants = %q, want rejected (pin survived)", o.Status)
	}
	// and the covering live set passes; the next append heals the torn tail away
	if o := m2.Dispatch("op-t3", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch after recovery = %q, want dispatched: %s", o.Status, o.Detail)
	}
	raw2, _ := os.ReadFile(path)
	if len(raw2) == 0 || raw2[len(raw2)-1] != '\n' {
		t.Fatalf("file not healed to event boundaries: tail byte %q", raw2[len(raw2)-1])
	}
	// sequence numbering continues from the last complete event, not from 0
	if o := m2.MarkUnresolved("op-t3"); o.Status != "unresolved" {
		t.Fatalf("mark unresolved = %q, want unresolved: %s", o.Status, o.Detail)
	}
	events, _ = m2.Events()
	if len(events) != 3 {
		t.Fatalf("events after recovery writes = %d, want 3", len(events))
	}
	if events[1].ArbitrationSeq != 1 || events[2].ArbitrationSeq != 2 {
		t.Fatalf("recovered sequence numbering wrong: %d %d", events[1].ArbitrationSeq, events[2].ArbitrationSeq)
	}
}

// TestUnresolvedFirstClass is 14-A5 counterexample three: an operation whose
// dispatch outcome is unknown becomes 'unresolved' (reachable straight from
// adopted — a crash at the dispatch boundary), is never auto-re-dispatched,
// and is reconciled to completed with the same operation_id. The status
// chain adopted → unresolved → completed reproduces the
// crash-unresolved-then-complete ledger fixture.
func TestUnresolvedFirstClass(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-t4", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q, want adopted", o.Status)
	}
	if o := m.MarkUnresolved("op-t4"); o.Status != "unresolved" {
		t.Fatalf("unresolved from adopted = %q, want unresolved: %s", o.Status, o.Detail)
	}
	// no auto-retry: dispatch from unresolved is refused — a silent retry here
	// is the duplicate-effect bug
	if o := m.Dispatch("op-t4", pinGrants()); o.Status != "rejected" {
		t.Fatalf("dispatch from unresolved = %q, want rejected (no auto-retry)", o.Status)
	}
	if o := m.MarkUnresolved("op-t4"); o.Status != "rejected" {
		t.Fatalf("re-unresolved = %q, want rejected", o.Status)
	}
	if o := m.MarkCompleted("op-t4"); o.Status != "completed" {
		t.Fatalf("reconciliation = %q, want completed: %s", o.Status, o.Detail)
	}
	events, _ := m.Events()
	got := []string{}
	for _, e := range events {
		got = append(got, e.Outcome.Status)
	}
	want := []string{"adopted", "unresolved", "completed"}
	if fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("status chain = %v, want %v (the crash-unresolved-then-complete fixture shape)", got, want)
	}
}

// TestDispatchRevocationCheck pins 14-A4: admission guarantees nothing about
// later permission — dispatch rechecks the live grant set against the pin.
func TestDispatchRevocationCheck(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-t5", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q, want adopted", o.Status)
	}
	// grant entirely revoked
	if o := m.Dispatch("op-t5", []ledger.Grant{pinGrants()[0]}); o.Status != "rejected" {
		t.Fatalf("dispatch with revoked grant = %q, want rejected", o.Status)
	}
	// grant present but effect severity downgraded
	downgraded := pinGrants()
	downgraded[1].Effect = "reversible"
	if o := m.Dispatch("op-t5", downgraded); o.Status != "rejected" {
		t.Fatalf("dispatch with downgraded effect = %q, want rejected", o.Status)
	}
	// grant present but action dropped
	dropped := pinGrants()
	dropped[1].Actions = []string{"read"}
	if o := m.Dispatch("op-t5", dropped); o.Status != "rejected" {
		t.Fatalf("dispatch with dropped action = %q, want rejected", o.Status)
	}
	// covering live set passes; upgrade in severity is fine (covering, not equal)
	upgraded := pinGrants()
	upgraded[0].Actions = []string{"read", "write"}
	if o := m.Dispatch("op-t5", upgraded); o.Status != "dispatched" {
		t.Fatalf("dispatch with covering grants = %q, want dispatched: %s", o.Status, o.Detail)
	}
}

// TestStateGuards pins the rest of the DAG: no transition outside
// adopted → dispatched | unresolved; dispatched → unresolved | completed |
// failed; unresolved → completed | failed.
func TestStateGuards(t *testing.T) {
	m := mustOpen(t, filepath.Join(t.TempDir(), "adopt.jsonl"))
	if o := m.MarkCompleted("op-unknown"); o.Status != "rejected" {
		t.Fatalf("finish unknown op = %q, want rejected", o.Status)
	}
	if o := m.Dispatch("op-unknown", pinGrants()); o.Status != "rejected" {
		t.Fatalf("dispatch unknown op = %q, want rejected", o.Status)
	}
	if o := m.Adopt(testRequest("op-t6", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q, want adopted", o.Status)
	}
	if o := m.MarkCompleted("op-t6"); o.Status != "rejected" {
		t.Fatalf("complete from adopted = %q, want rejected", o.Status)
	}
	if o := m.MarkFailed("op-t6"); o.Status != "rejected" {
		t.Fatalf("fail from adopted = %q, want rejected", o.Status)
	}
	if o := m.Dispatch("op-t6", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q, want dispatched", o.Status)
	}
	if o := m.MarkFailed("op-t6"); o.Status != "failed" {
		t.Fatalf("fail from dispatched = %q, want failed", o.Status)
	}
	// terminal: nothing further moves
	if o := m.Dispatch("op-t6", pinGrants()); o.Status != "rejected" {
		t.Fatalf("dispatch from failed = %q, want rejected", o.Status)
	}
	if o := m.MarkCompleted("op-t6"); o.Status != "rejected" {
		t.Fatalf("complete from failed = %q, want rejected", o.Status)
	}
	if o := m.MarkUnresolved("op-t6"); o.Status != "rejected" {
		t.Fatalf("unresolved from failed = %q, want rejected", o.Status)
	}
}

// TestDigestJcsBasis pins the digest's JCS basis: key order cannot change
// it, content can.
func TestDigestJcsBasis(t *testing.T) {
	ab, err := Digest(map[string]any{"credit": 450, "ops": 4})
	if err != nil {
		t.Fatal(err)
	}
	ba, err := Digest(map[string]any{"ops": 4, "credit": 450})
	if err != nil {
		t.Fatal(err)
	}
	other, err := Digest(map[string]any{"credit": 451, "ops": 4})
	if err != nil {
		t.Fatal(err)
	}
	if ab != ba {
		t.Fatalf("digest is key-order sensitive (not JCS): %q vs %q", ab, ba)
	}
	if ab == other {
		t.Fatalf("digest collision across different payloads")
	}
}

// TestMachineOutputConformsToLedger closes the loop with piece 4: the
// machine's durable output, assembled as a ledger document, passes the
// ledger checker (schema + cross-event rules). The machine is a legal
// single writer of the ledger.
func TestMachineOutputConformsToLedger(t *testing.T) {
	if SchemaPath == "" && ledger.SchemaPath == "" {
		t.Fatal("schema directories not found")
	}
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	// op-1: full chain incl. conflict (a competitor with a different digest)
	if o := m.Adopt(testRequest("op-1", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("op-1 adopt = %q", o.Status)
	}
	if o := m.Dispatch("op-1", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("op-1 dispatch = %q", o.Status)
	}
	if o := m.MarkUnresolved("op-1"); o.Status != "unresolved" {
		t.Fatalf("op-1 unresolved = %q", o.Status)
	}
	if o := m.MarkCompleted("op-1"); o.Status != "completed" {
		t.Fatalf("op-1 complete = %q", o.Status)
	}
	if o := m.Adopt(testRequest("op-1", digestB, pinGrants())); o.Status != "rejected" {
		t.Fatalf("op-1 conflict = %q", o.Status)
	}
	// op-2: retry reuse
	if o := m.Adopt(testRequest("op-2", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("op-2 adopt = %q", o.Status)
	}
	if o := m.Adopt(testRequest("op-2", digestA, pinGrants())); o.Status != "reused" {
		t.Fatalf("op-2 reuse = %q", o.Status)
	}
	// op-3: crash-at-dispatch shape
	if o := m.Adopt(testRequest("op-3", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("op-3 adopt = %q", o.Status)
	}
	if o := m.MarkUnresolved("op-3"); o.Status != "unresolved" {
		t.Fatalf("op-3 unresolved = %q", o.Status)
	}

	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 9 {
		t.Fatalf("events = %d, want 9", len(events))
	}
	doc := ledger.Document{LedgerVersion: "0.1.0", Events: events}
	raw, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	var asMap map[string]any
	if err := json.Unmarshal(raw, &asMap); err != nil {
		t.Fatal(err)
	}
	if errs := ledger.Errors(asMap); len(errs) > 0 {
		t.Fatalf("machine output is not a conforming ledger document: %v", errs)
	}
}
