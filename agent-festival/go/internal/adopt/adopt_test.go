package adopt

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
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
	// seam: Digest() is the producer, the schema pattern is the consumer —
	// close the seam through the real validator so a format regression (e.g.
	// a dropped "sha256:" prefix) cannot keep every test green while real
	// requests are refused (R1 m-10)
	d, err := Digest(map[string]any{"credit": 450})
	if err != nil {
		t.Fatal(err)
	}
	req := testRequest("op-digest-shape", d, pinGrants())
	rawReq, err := json.Marshal(req)
	if err != nil {
		t.Fatal(err)
	}
	var asMap map[string]any
	if err := json.Unmarshal(rawReq, &asMap); err != nil {
		t.Fatal(err)
	}
	if errs := CheckRequest(asMap); len(errs) > 0 {
		t.Fatalf("Digest() output does not satisfy the schema pattern: %v", errs)
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
	doc := ledger.Document{LedgerVersion: ledger.Version, Events: events}
	raw, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	var asMap map[string]any
	// UseNumber, per ledger.Errors' documented input contract (a float64
	// map is the blind spot the doc warns future callers about — this test
	// must model the discipline, not break it)
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&asMap); err != nil {
		t.Fatal(err)
	}
	if errs := ledger.Errors(asMap); len(errs) > 0 {
		t.Fatalf("machine output is not a conforming ledger document: %v", errs)
	}
}

// TestReplayKeepsWinnerIdentity is the R1 BLOCKER regression: the
// idempotency key (operation_id + digest) does not cover
// evaluation_revision/versions, so a same-key retry legally differs there.
// The retry's reused event must NOT overwrite the winner's pinned
// identity/versions on reload — post-recovery effect events must carry the
// winner's values, matching the never-crashed machine's output.
func TestReplayKeepsWinnerIdentity(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-win", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q, want adopted", o.Status)
	}
	retry := testRequest("op-win", digestA, pinGrants())
	retry.Identity.EvaluationRevision = "er-2"
	retry.Versions.Model = "m-2"
	if o := m.Adopt(retry); o.Status != "reused" {
		t.Fatalf("retry = %q, want reused", o.Status)
	}
	m2 := mustOpen(t, path)
	if o := m2.Dispatch("op-win", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch after reload = %q, want dispatched: %s", o.Status, o.Detail)
	}
	events, _ := m2.Events()
	if len(events) != 3 {
		t.Fatalf("events = %d, want 3", len(events))
	}
	// the reused event records the RETRYER's identity (a ledger fact)...
	if events[1].Identity.EvaluationRevision != "er-2" || events[1].Versions.Model != "m-2" {
		t.Fatalf("reused event does not record the retryer's identity/versions")
	}
	// ...but the machine's pin stays the WINNER's for everything it writes next
	for i, e := range []ledger.Event{events[2]} {
		if e.Identity.EvaluationRevision != "er-1" || e.Versions.Model != "m-1" {
			t.Fatalf("post-recovery effect %d carries the retryer's pin (rev=%q model=%q) — the replay forked the event stream", i, e.Identity.EvaluationRevision, e.Versions.Model)
		}
	}
}

// TestBypassWriteRejectedAtLoad pins the single-writer discipline's
// load-time boundary (R1 M-1): a hand-written file the machine did not
// produce — an effect with no adoption predecessor, or a registered digest
// flipped — is refused at Open, never silently absorbed as legal state.
func TestBypassWriteRejectedAtLoad(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	// form 1: effect event with no adoption predecessor
	effectOnly := &ledger.Event{
		EventType: "effect", ArbitrationSeq: 0,
		Identity:    ledger.Identity{BusinessRequestID: "br-t", OperationID: "op-bypass"},
		Versions:    ledger.Versions{Evidence: "ev", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		Idempotency: &ledger.Idempotency{OperationID: "op-bypass", PayloadDigest: digestA},
		Outcome:     ledger.Outcome{Status: "dispatched"},
	}
	// adoption events carry the grant pin (schema-required on adopted
	// events) so each bypass form below is rejected by the rule it means to
	// exercise, not incidentally by the grants rule
	adoptedGrants := pinGrants()
	line, err := json.Marshal(effectOnly)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, append(line, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("bypass write (effect without adoption) was accepted at load")
	}
	// form 2: adoption with digestA, then an effect carrying digestB — a
	// registered digest flipped
	adopted := *effectOnly
	adopted.EventType = "adoption"
	adopted.Outcome = ledger.Outcome{Status: "adopted"}
	adopted.GrantsAtDecision = adoptedGrants
	flipped := *effectOnly
	flipped.ArbitrationSeq = 1
	// fresh Idempotency value: *effectOnly shares the pointer, mutating it
	// would flip the adoption event's digest too
	flipped.Idempotency = &ledger.Idempotency{OperationID: "op-bypass", PayloadDigest: digestB}
	a, _ := json.Marshal(adopted)
	b, _ := json.Marshal(flipped)
	if err := os.WriteFile(path, append(append(a, '\n'), append(b, '\n')...), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("bypass write (flipped registered digest) was accepted at load")
	}
	// control: the same two events with a stable digest open cleanly
	stable := flipped // value copy — but the Idempotency pointer is shared, so give it its own
	stable.Idempotency = &ledger.Idempotency{OperationID: "op-bypass", PayloadDigest: digestA}
	s, _ := json.Marshal(stable)
	if err := os.WriteFile(path, append(append(a, '\n'), append(s, '\n')...), 0o644); err != nil {
		t.Fatal(err)
	}
	m, err := Open(path)
	if err != nil {
		t.Fatalf("clean machine-written shape rejected at load: %v", err)
	}
	if m.State("op-bypass") != StateDispatched {
		t.Fatalf("recovered state = %q, want dispatched", m.State("op-bypass"))
	}
}

// TestAccountabilityRidesEveryEvent pins D31 accountability on every event
// shape the machine writes (R1 M-2): adopted/reused/conflict carry the
// request's own triple (who adopted / who retried / who lost the race — the
// ledger fixtures distinguish the loser by session), effect events carry the
// pin stamped at adoption.
func TestAccountabilityRidesEveryEvent(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	win := testRequest("op-acc", digestA, pinGrants()) // sess-t
	if o := m.Adopt(win); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	retry := testRequest("op-acc", digestA, pinGrants())
	retry.Accountability = &ledger.Accountability{Session: "sess-retry", Skill: "skill-t", Role: "employee"}
	if o := m.Adopt(retry); o.Status != "reused" {
		t.Fatalf("retry = %q", o.Status)
	}
	comp := testRequest("op-acc", digestB, pinGrants())
	comp.Accountability = &ledger.Accountability{Session: "sess-comp", Skill: "skill-t", Role: "employee"}
	if o := m.Adopt(comp); o.Status != "rejected" {
		t.Fatalf("conflict = %q, want rejected", o.Status)
	}
	if o := m.Dispatch("op-acc", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q", o.Status)
	}
	if o := m.MarkUnresolved("op-acc"); o.Status != "unresolved" {
		t.Fatalf("unresolved = %q", o.Status)
	}
	if o := m.MarkCompleted("op-acc"); o.Status != "completed" {
		t.Fatalf("complete = %q", o.Status)
	}
	events, _ := m.Events()
	if len(events) != 6 {
		t.Fatalf("events = %d, want 6", len(events))
	}
	want := []string{"sess-t", "sess-retry", "sess-comp", "sess-t", "sess-t", "sess-t"}
	for i, e := range events {
		if e.Accountability == nil || e.Accountability.Session != want[i] {
			got := "<nil>"
			if e.Accountability != nil {
				got = e.Accountability.Session
			}
			t.Fatalf("event %d (%s) accountability = %q, want %q", i, e.Outcome.Status, got, want[i])
		}
	}
}

// TestLoadRejectsLaunderedShapes is the R2 BLOCKER regression: the load-time
// checker must see the RAW line documents — a typed re-projection would fold
// "grants_at_decision": [] into absence (making the 14-A4 pin vacuous) and
// silently drop unknown fields. Raw lines carrying those shapes must be
// refused at Open.
func TestLoadRejectsLaunderedShapes(t *testing.T) {
	dir := t.TempDir()
	// a well-formed adopted line, used as the template
	m := mustOpen(t, filepath.Join(dir, "seed.jsonl"))
	if o := m.Adopt(testRequest("op-seed", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("seed adopt = %q", o.Status)
	}
	seedEvents, _ := m.Events()
	if len(seedEvents) != 1 {
		t.Fatalf("seed events = %d", len(seedEvents))
	}
	seedLine, err := json.Marshal(seedEvents[0])
	if err != nil {
		t.Fatal(err)
	}

	// shape 1: an adopted event with an empty grants array — the typed
	// re-projection launders "grants": [] into absence, but the raw document
	// keeps the key present with zero items, which the schema's minItems
	// rejects. Empty pin = vacuous revocation check (the empty-grants
	// fixture's declared attack surface).
	emptyGrants := string(seedLine)
	emptyGrants = strings.Replace(emptyGrants,
		`"grants_at_decision":[{"kind":"data","selector":"ledger://credit/t","actions":["read"],"effect":"none"},{"kind":"tool","selector":"tool://credit-transfer","actions":["execute"],"effect":"irreversible"}]`,
		`"grants_at_decision":[]`, 1)
	if !strings.Contains(emptyGrants, `"grants_at_decision":[]`) {
		t.Fatalf("shape 1 construction failed — grants not emptied: %s", emptyGrants)
	}
	p := filepath.Join(dir, "empty-grants.jsonl")
	if err := os.WriteFile(p, []byte(emptyGrants+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(p); err == nil {
		t.Fatal("adopted event with empty grants array was accepted at load (laundered projection)")
	}

	// shape 2: an unknown side-channel field on the event line — the typed
	// projection drops unknown fields; the raw document keeps "decider",
	// which additionalProperties rejects.
	unknownField := strings.Replace(string(seedLine), `"event_type":"adoption"`,
		`"event_type":"adoption","decider":"hedge-v1"`, 1)
	if !strings.Contains(unknownField, `"decider"`) {
		t.Fatalf("shape 2 construction failed")
	}
	p = filepath.Join(dir, "unknown-field.jsonl")
	if err := os.WriteFile(p, []byte(unknownField+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(p); err == nil {
		t.Fatal("event line with an unknown side-channel field was accepted at load (laundered projection)")
	}

	// control: the unmodified machine line opens cleanly
	p = filepath.Join(dir, "clean.jsonl")
	if err := os.WriteFile(p, append(append([]byte{}, seedLine...), '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(p); err != nil {
		t.Fatalf("clean machine line rejected at load: %v", err)
	}
}

// TestHealKeepsNoTrailingNewlineEvent is the R2 BLOCKER regression: a final
// complete line without a trailing newline is a complete event (the loader
// accepts it) — the append-path rewrite must keep it, not drop the whole
// file for lack of a newline.
func TestHealKeepsNoTrailingNewlineEvent(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-nl", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	// strip the trailing newline: a complete line without it must still load
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if raw[len(raw)-1] != '\n' {
		t.Fatalf("machine did not newline-terminate its own line")
	}
	if err := os.WriteFile(path, raw[:len(raw)-1], 0o644); err != nil {
		t.Fatal(err)
	}
	m2, err := Open(path)
	if err != nil {
		t.Fatalf("no-trailing-newline complete line rejected at load: %v", err)
	}
	if m2.State("op-nl") != StateAdopted {
		t.Fatalf("state = %q, want adopted", m2.State("op-nl"))
	}
	// the next append must KEEP the adopted event and only add its own
	if o := m2.MarkUnresolved("op-nl"); o.Status != "unresolved" {
		t.Fatalf("mark unresolved = %q, want unresolved: %s", o.Status, o.Detail)
	}
	m3, err := Open(path)
	if err != nil {
		t.Fatalf("file rejected after append onto no-newline form: %v", err)
	}
	if m3.State("op-nl") != StateUnresolved {
		t.Fatalf("state after reopen = %q, want unresolved — the adopted event was dropped on heal", m3.State("op-nl"))
	}
	events, _ := m3.Events()
	if len(events) != 2 {
		t.Fatalf("events = %d, want 2 (adopted preserved + unresolved): %+v", len(events), events)
	}
}

// TestAdoptRejectsNonconformingRequests pins the single-writer's
// construction guarantee (R2): the machine schema-checks every request, so
// no in-process caller can drive a non-conforming document into the durable
// form — an empty grant pin or a malformed digest is rejected at the gate
// with nothing written.
func TestAdoptRejectsNonconformingRequests(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	noGrants := testRequest("op-bad", digestA, nil)
	if o := m.Adopt(noGrants); o.Status != "rejected" {
		t.Fatalf("empty-grant request = %q, want rejected", o.Status)
	}
	badDigest := testRequest("op-bad", "not-a-digest", pinGrants())
	if o := m.Adopt(badDigest); o.Status != "rejected" {
		t.Fatalf("malformed-digest request = %q, want rejected", o.Status)
	}
	events, _ := m.Events()
	if len(events) != 0 {
		t.Fatalf("nonconforming requests wrote %d events, want 0", len(events))
	}
	// the machine is still usable afterwards
	if o := m.Adopt(testRequest("op-good", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("good request after rejections = %q, want adopted: %s", o.Status, o.Detail)
	}
}

// TestOpenRejectsFoldedSeq is the machine-side 2^53 pin (R3 M-2, rebuilt in
// R4 M-1 after the first version's rejection was driven by a leftover
// grants-on-effect defect — a pin on the wrong rule): two typed-built lines
// whose ONLY defect is the folded sequence pair 9007199254740993 -> ...992;
// the effect line carries no grants. decodeLineDoc's UseNumber is what keeps
// the pair distinct in the map domain — without it both fold equal in
// float64 and the load-time monotonicity check goes blind.
func TestOpenRejectsFoldedSeq(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-f53", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	events, _ := m.Events()
	first, err := json.Marshal(events[0])
	if err != nil {
		t.Fatal(err)
	}
	adopted := events[0]
	adopted.ArbitrationSeq = 9007199254740993
	first, err = json.Marshal(adopted)
	if err != nil {
		t.Fatal(err)
	}
	effect := events[0]
	effect.EventType = "effect"
	effect.ArbitrationSeq = 9007199254740992
	effect.Outcome = ledger.Outcome{Status: string(StateDispatched)}
	effect.GrantsAtDecision = nil
	second, err := json.Marshal(effect)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(string(first)+"\n"+string(second)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("folded adjacent seqs past 2^53 were accepted at load — the map domain lost the integers")
	}
}

// TestOpenRejectsTransitionOrderBypass pins the machine path of the
// transition-order grammar (R3 M-1): a hand-written adopted→completed
// sequence must be refused at Open — absorbing it would let the machine
// resume from a state it can never be in and write events that violate its
// own DAG.
func TestOpenRejectsTransitionOrderBypass(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-tr", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	events, _ := m.Events()
	first, err := json.Marshal(events[0])
	if err != nil {
		t.Fatal(err)
	}
	// an effect event carrying completed straight after adopted — built from
	// the typed event so only the intended field differs (string surgery on
	// the marshaled line drifted into family-violation shapes twice)
	late := events[0]
	late.EventType = "effect"
	late.ArbitrationSeq = 1
	late.Outcome = ledger.Outcome{Status: string(StateCompleted)}
	late.GrantsAtDecision = nil
	second, err := json.Marshal(late)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(string(first)+"\n"+string(second)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("completed-without-dispatched bypass was accepted at load")
	}
	// control: the legal chain adopted→dispatched→completed loads cleanly
	disp := events[0]
	disp.EventType = "effect"
	disp.ArbitrationSeq = 1
	disp.Outcome = ledger.Outcome{Status: string(StateDispatched)}
	disp.GrantsAtDecision = nil
	dispLine, err := json.Marshal(disp)
	if err != nil {
		t.Fatal(err)
	}
	comp := disp
	comp.ArbitrationSeq = 2
	comp.Outcome = ledger.Outcome{Status: string(StateCompleted)}
	compLine, err := json.Marshal(comp)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(string(first)+"\n"+string(dispLine)+"\n"+string(compLine)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	m2, err := Open(path)
	if err != nil {
		t.Fatalf("legal chain rejected at load: %v", err)
	}
	if m2.State("op-tr") != StateCompleted {
		t.Fatalf("state = %q, want completed", m2.State("op-tr"))
	}
}

// TestOpenRejectsMidFileGarbage pins R4 M2: unparseable content is a torn
// tail ONLY at EOF without a trailing newline (crash residue); a garbage
// line anywhere else — mid-file, or newline-terminated at the end — is a
// bypass or corruption and fails the open. An append-only audit ledger must
// not silently drop audit data (or let the next append erase it).
func TestOpenRejectsMidFileGarbage(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-g1", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	if o := m.Adopt(testRequest("op-g2", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt 2 = %q", o.Status)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.SplitN(string(raw), "\n", 3) // two event lines + trailing empty
	if len(lines) < 2 {
		t.Fatalf("unexpected file shape: %q", raw)
	}
	// mid-file garbage
	mid := lines[0] + "\n" + `{"event_type":"adoption","arbitration` + "\n" + lines[1] + "\n"
	if err := os.WriteFile(path, []byte(mid), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("mid-file garbage line was silently dropped at load")
	}
	// newline-terminated garbage at the end — still not a torn tail
	trailing := lines[0] + "\n" + lines[1] + "\n" + "not json at all\n"
	if err := os.WriteFile(path, []byte(trailing), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("newline-terminated garbage at EOF was silently dropped at load")
	}
	// valid JSON but not an event (field type mismatch)
	typedBad := lines[0] + "\n" + strings.Replace(lines[1], `"arbitration_seq":1`, `"arbitration_seq":"1"`, 1) + "\n"
	if err := os.WriteFile(path, []byte(typedBad), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("type-mismatched event line was silently dropped at load")
	}
	// control: the untampered file loads
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err != nil {
		t.Fatalf("untampered file rejected: %v", err)
	}
}

// TestUnresolvedReconciliationToFailed pins the one DAG edge that had no
// exercise (R4 m-3): unresolved -> failed, the failure-exit reconciliation.
func TestUnresolvedReconciliationToFailed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-uf", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	if o := m.MarkUnresolved("op-uf"); o.Status != "unresolved" {
		t.Fatalf("unresolved = %q, want unresolved: %s", o.Status, o.Detail)
	}
	if o := m.MarkFailed("op-uf"); o.Status != "failed" {
		t.Fatalf("failed = %q, want failed: %s", o.Status, o.Detail)
	}
	if m.State("op-uf") != StateFailed {
		t.Fatalf("state = %q, want failed", m.State("op-uf"))
	}
}

// TestAdoptRejectsInvalidUTF8 is the R5 BLOCKER regression: json.Marshal
// launders invalid UTF-8 to U+FFFD, so a request carrying it would pass the
// schema check on the LAUNDERED document while the durable form registers a
// laundered key — after a crash-reload the caller's original key looks like
// a new operation, and the file ends with two adopted events under one
// laundered id, a ledger the loader permanently rejects. The gate rejects
// what it cannot byte-represent.
func TestAdoptRejectsInvalidUTF8(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	badOp := testRequest("op-\xff", digestA, pinGrants())
	if o := m.Adopt(badOp); o.Status != "rejected" {
		t.Fatalf("invalid-UTF-8 operation_id = %q, want rejected", o.Status)
	}
	badSelector := testRequest("op-ok1", digestA, []ledger.Grant{
		{Kind: "data", Selector: "ledger://credit/\xff", Actions: []string{"read"}, Effect: "none"},
	})
	if o := m.Adopt(badSelector); o.Status != "rejected" {
		t.Fatalf("invalid-UTF-8 grant selector = %q, want rejected", o.Status)
	}
	badSession := testRequest("op-ok2", digestA, pinGrants())
	badSession.Accountability = &ledger.Accountability{Session: "sess-\xff", Skill: "s", Role: "r"}
	if o := m.Adopt(badSession); o.Status != "rejected" {
		t.Fatalf("invalid-UTF-8 accountability session = %q, want rejected", o.Status)
	}
	events, _ := m.Events()
	if len(events) != 0 {
		t.Fatalf("invalid-UTF-8 requests wrote %d events, want 0", len(events))
	}
	// and the crash chain cannot start: a valid request under the same key
	// still adopts cleanly
	if o := m.Adopt(testRequest("op-\xff", digestA, pinGrants())); o.Status != "rejected" {
		t.Fatalf("second invalid-UTF-8 attempt = %q, want rejected", o.Status)
	}
	if o := m.Adopt(testRequest("op-clean", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("clean request = %q, want adopted", o.Status)
	}
}

// TestOpenAcceptsLegalHighSeqAcross2e53 is the pin UseNumber actually earns
// (R5 M1): float64 rounding is monotonic, so a DECREASING pair folds to
// equal-or-decreasing and the strict-increase check catches it with or
// without exact integers — the invalid-side fixture can never pin the
// decoder. The pinnable direction is the false positive: legal consecutive
// seqs across 2^53 fold EQUAL in float64 and a UseNumber-less loader would
// reject a machine-legal file.
func TestOpenAcceptsLegalHighSeqAcross2e53(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-hi", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	events, _ := m.Events()
	adopted := events[0]
	adopted.ArbitrationSeq = 9007199254740992 // 2^53
	first, err := json.Marshal(adopted)
	if err != nil {
		t.Fatal(err)
	}
	effect := events[0]
	effect.EventType = "effect"
	effect.ArbitrationSeq = 9007199254740993 // 2^53 + 1 — one past the fold point
	effect.Outcome = ledger.Outcome{Status: string(StateDispatched)}
	effect.GrantsAtDecision = nil
	second, err := json.Marshal(effect)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(string(first)+"\n"+string(second)+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	m2, err := Open(path)
	if err != nil {
		t.Fatalf("legal high-seq file rejected at load (folded equal in the map domain?): %v", err)
	}
	if m2.State("op-hi") != StateDispatched {
		t.Fatalf("state = %q, want dispatched", m2.State("op-hi"))
	}
}

// TestOpenRejectsInvalidUTF8Lines is the load-side twin of the request-gate
// UTF-8 BLOCKER (R6 B1, re-pinned R7 M-1 after the first version's tamper
// hit the key-coupling rule instead): Go's json decoder silently replaces
// invalid bytes with U+FFFD, so a tampered line would parse "successfully"
// with laundered keys and the machine would absorb a file it provably did
// not write (its own writes are always valid UTF-8 — the gate enforces it).
// The tamper targets a single-occurrence field and the assertion names the
// guard's own error, so deleting the UTF-8 check alone reddens THIS test.
func TestOpenRejectsInvalidUTF8Lines(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	if o := m.Adopt(testRequest("op-u8", digestA, pinGrants())); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	// tamper a field that occurs exactly once (business_request_id): no
	// other rule rejects this file, only the UTF-8 boundary can
	tampered := bytes.Replace(raw, []byte("br-t"), []byte("br-t\xff"), 1)
	if bytes.Equal(tampered, raw) {
		t.Fatal("tamper construction failed")
	}
	if err := os.WriteFile(path, tampered, 0o644); err != nil {
		t.Fatal(err)
	}
	_, err = Open(path)
	if err == nil {
		t.Fatal("invalid-UTF-8 line was absorbed at load (json decoder laundered it)")
	}
	if !strings.Contains(err.Error(), "not valid UTF-8") {
		t.Fatalf("rejection came from another rule (error: %v) — the UTF-8 pin is on the wrong guard", err)
	}
	// control: the untampered file still loads
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err != nil {
		t.Fatalf("untampered file rejected: %v", err)
	}
}

// TestPinIsNotCallerAliased is the R7 M-2 regression: the machine pins
// grants and accountability at adoption, and the caller mutating its own
// slice/pointer afterwards must not reach the pin — neither shrink the
// 14-A4 baseline (revoked authority passing the dispatch recheck) nor fork
// the audit attribution stamped onto later effect events.
func TestPinIsNotCallerAliased(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m := mustOpen(t, path)
	grants := pinGrants()
	req := testRequest("op-alias", digestA, grants)
	if o := m.Adopt(req); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	// caller shrinks its grant slice after adoption — the pin must hold
	grants[1].Effect = "reversible"
	if o := m.Dispatch("op-alias", grants); o.Status != "rejected" {
		t.Fatalf("dispatch with caller-shrunk pin = %q, want rejected (the 14-A4 baseline must not alias caller memory)", o.Status)
	}
	if o := m.Dispatch("op-alias", pinGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch with covering live set = %q, want dispatched: %s", o.Status, o.Detail)
	}
	// caller mutates its accountability pointer — later events keep the
	// pinned triple
	if req.Accountability != nil {
		req.Accountability.Role = "attacker"
	}
	if o := m.MarkUnresolved("op-alias"); o.Status != "unresolved" {
		t.Fatalf("unresolved = %q, want unresolved", o.Status)
	}
	if o := m.MarkCompleted("op-alias"); o.Status != "completed" {
		t.Fatalf("completed = %q, want completed", o.Status)
	}
	events, _ := m.Events()
	for i, e := range events {
		if e.Accountability == nil || e.Accountability.Role != "employee" {
			got := "<nil>"
			if e.Accountability != nil {
				got = e.Accountability.Role
			}
			t.Fatalf("event %d (%s) accountability role = %q, want the pinned 'employee' — the durable form forked with caller memory", i, e.Outcome.Status, got)
		}
	}
}
