package e2e

// E7a/E7b (xia round-4 §2 canary discipline, 41号 report §四): the canary
// experiments — zero LLM, test-form only (the 41号 prior verified the
// production injection API would self-brick on EVENT_BEFORE_ADOPTION, so
// this round lands the probe layer; the durable-layer grammar boundary is
// itself pinned as a fact below).
//
// E7a: injection-point grammar — three faces (unknown-op direct /
// synthesized [CANARY] control events / durable-layer boundary) +
// canarySilent (the canary's own death probe).
// E7b: the guardDied canary filter face — an alive canary FEEDS the death
// probe (masking real business-guard death); the filter parameter provides
// the opt-in closure (R47 M-2: per-call-site opt-in, NOT a default — the
// E4 call sites preserve the unfiltered semantics by passing ""). [CANARY]
// prefix is a reserved convention riding the schema's free-text Detail
// field ("not a machine-checked field") — a mid-detail [CANARY] must NOT
// be filtered (pinned below); field-form retires the prefix at 0.2.0.
// REACHABILITY BOUNDARY (R47 M-2, honest): today the machine/耐久 paths
// cannot place a canary event into guardDied's input stream (Machine.Events
// only yields machine-written events; a hand-appended no-adoption canary
// line bricks Open — E7a③ pins this) — the masked bad state is reachable
// only from synthesized fixtures; the 0.2.0 canary field is what changes
// that. The filter face is the fixture-composition + forward-looking face.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// canaryPrefix is the reserved Detail-prefix convention for probe-layer
// canary events (0.2.0 field-form retires it).
const canaryPrefix = "[CANARY]"

// canaryEvent builds a synthesized control event with the canary marker
// (Versions/Accountability present for schema validity — the durable
// form must pass the ledger schema).
func canaryEvent(seq int, op string) ledger.Event {
	return ledger.Event{
		EventType:      "control",
		ArbitrationSeq: int64(seq),
		Identity:       ledger.Identity{BusinessRequestID: "br-canary", OperationID: op},
		Versions:       ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		Outcome:        ledger.Outcome{Status: "rejected", Detail: canaryPrefix + " probe injection"},
		Accountability: &ledger.Accountability{Session: "sess-canary", Skill: "skill-canary", Role: "employee"},
	}
}

// canarySilent reports whether the canary stream itself went silent while
// effect traffic continues — the canary's own death probe (the meta layer
// of xia round-4 §2: who watches the watcher — the probe face watches the
// canary stream). Zero canary events → never injected → NOT silent.
func canarySilent(events []ledger.Event) bool {
	lastCanary := -1
	lastTraffic := -1
	for i, e := range events {
		if e.EventType == "control" && strings.HasPrefix(e.Outcome.Detail, canaryPrefix) {
			lastCanary = i
		}
		if e.EventType == "effect" {
			lastTraffic = i
		}
	}
	if lastCanary < 0 {
		return false // never injected — not silent
	}
	return lastTraffic > lastCanary
}

// TestE7a_UnknownOpDispatchUntraceable pins the GRAMMAR GAP (face ①): a
// dispatch attempt on an operation that was never adopted is rejected as a
// PURE RETURN VALUE — no control event is written (refuse() only serves
// adopted operations). This is the fact behind xia's canary discipline
// being unimplementable in this form today; it flips when the grammar
// grows a traceable unknown-op refusal (rewrite, not fix).
func TestE7a_UnknownOpDispatchUntraceable(t *testing.T) {
	m := mustOpenAdopt(t, newLedgerPath(t))
	o := m.Dispatch("op-never-adopted", nil)
	if o.Status != "rejected" {
		t.Fatalf("E7a①: unknown-op dispatch = %q, want rejected", o.Status)
	}
	if o.Event != nil {
		t.Fatalf("E7a①: unknown-op rejection left an event — the grammar gap is closed (rewrite this test: the refusal became traceable)")
	}
	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range events {
		if e.Identity.OperationID == "op-never-adopted" {
			t.Fatalf("E7a①: found an event for the unknown op — the gap is closed (rewrite)")
		}
	}
}

// TestE7a_CanaryControlEventProbeFace is face ②'s REAL experiment (R47
// B-1 rewrite: the previous form was constructor-tautological — three
// assertions on fields the helper itself hardcodes). The grammar-LATERAL
// form: an ADOPTED operation whose pin-matching control event carries the
// canary marker — this file CAN be written (Open succeeds — the
// EVENT_BEFORE_ADOPTION boundary pins the no-adoption form, not this
// one), and the experiment proves the two remaining criteria on the
// replay side: zero state transfer (the op stays adopted — the control
// event does not project state) and zero idempotency-registry effect
// (re-dispatching is still a first dispatch, not a reused).
func TestE7a_CanaryControlEventProbeFace(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "adopt.jsonl")
	m := mustOpenAdopt(t, path)
	if o := m.Adopt(adoptRequest(t, "op-canary-2")); o.Status != "adopted" {
		t.Fatalf("E7a②: canary-form adopt = %q: %s", o.Status, o.Detail)
	}
	// append a pin-matching canary control event AFTER the adoption — the
	// grammar-lateral form (control events for adopted ops are legal;
	// identity/versions match the adopted pin)
	// pin-matching form: the canary control event carries EXACTLY the
	// adopted operation's pin (identity/versions/accountability) — the
	// ATTRIBUTION_DIVERGENCE checker requires control events to match the
	// adopted pin, and a canary from the machine's own discipline would
	// stamp the same pin
	canary := canaryEvent(1, "op-canary-2")
	canary.Identity = ledger.Identity{BusinessRequestID: "br-e4", EvaluationRevision: "er-1", OperationID: "op-canary-2"}
	canary.Versions = ledger.Versions{Evidence: "ev-1", Rule: "rule-1", Model: "m-1", Readout: "r-1", Policy: "p-1"}
	canary.Accountability = &ledger.Accountability{Session: "sess-e4", Skill: "skill-e4", Role: "employee"}
	line, err := json.Marshal(canary)
	if err != nil {
		t.Fatal(err)
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := f.Write(append(line, '\n')); err != nil {
		f.Close()
		t.Fatal(err)
	}
	f.Close()
	// Open the file with the canary event present
	m2, err := adopt.Open(path)
	if err != nil {
		t.Fatalf("E7a②: Open rejected the pin-matching canary form — grammar-lateral canaries are not loadable (check the rejection rule): %v", err)
	}
	// criterion: ZERO state transfer — the op is still adopted (the canary
	// control event did not project state)
	if st := m2.State("op-canary-2"); st != adopt.StateAdopted {
		t.Fatalf("E7a②: state after canary event replay = %q, want adopted — zero state transfer violated", st)
	}
	// criterion: ZERO idempotency-registry effect — a dispatch on this op
	// is a FIRST dispatch (not a reused outcome, proving no registry entry
	// was created by the canary event)
	if o := m2.Dispatch("op-canary-2", fullGrants()); o.Status != "dispatched" {
		t.Fatalf("E7a②: dispatch after canary replay = %q (%s), want dispatched — the canary event created a registry entry (zero-registry violated)", o.Status, o.Detail)
	}
}

// TestE7a_CanaryDurableGrammarBoundary pins the durable-layer grammar
// fact (face ③): a ledger file containing a control event for an
// operation with NO prior adoption is REFUSED at Open
// (EVENT_BEFORE_ADOPTION applies to control events too) — which is why a
// production canary-injection API cannot write this event form today
// without schema+checker+oracle lockstep (0.2.0 track). It flips when the
// grammar grows the canary field.
func TestE7a_CanaryDurableGrammarBoundary(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "adopt.jsonl")
	line := `{"event_type":"control","arbitration_seq":0,"identity":{"business_request_id":"br-canary","operation_id":"op-canary-d"},"versions":{"evidence":"e","rule":"r","model":"m","readout":"ro","policy":"p"},"outcome":{"status":"rejected","detail":"[CANARY] durable probe"}}`
	if err := os.WriteFile(path, []byte(line+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := adopt.Open(path); err == nil {
		t.Fatal("E7a③: Open accepted a canary control event with no prior adoption — the durable grammar grew a canary field (rewrite this boundary test)")
	} else if !strings.Contains(err.Error(), "EVENT_BEFORE_ADOPTION") {
		t.Fatalf("E7a③: rejection rule = %q, want EVENT_BEFORE_ADOPTION (R47 m-4: the pin must bind the rule, not just any rejection)", err.Error())
	}
}

// TestE7a_CanarySilentProbe probes the canary's own death: after
// injections stop while effect traffic continues, canarySilent reports
// true; a stream with no canary events never reports silent.
// Mutation probe: drop the traffic precondition and the ALIVE face goes
// red (R47 m-1: the never-injected face survives that mutation — the
// lastCanary guard still returns false on empty streams).
func TestE7a_CanarySilentProbe(t *testing.T) {
	// never-injected face: zero canary → NOT silent
	if canarySilent([]ledger.Event{}) {
		t.Fatal("E7a: canarySilent reported silent on a stream with no canary events — the probe is tautological")
	}
	// silent face: 3 injections then silence + effect traffic after
	stream := []ledger.Event{
		canaryEvent(0, "op-c"),
		canaryEvent(1, "op-c"),
		canaryEvent(2, "op-c"),
		{EventType: "effect", ArbitrationSeq: 3, Outcome: ledger.Outcome{Status: "dispatched"}},
	}
	if !canarySilent(stream) {
		t.Fatal("E7a: canarySilent missed the canary's own death (injections stopped, traffic continued)")
	}
	// alive face: the latest canary is after the latest traffic
	alive := []ledger.Event{
		{EventType: "effect", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(1, "op-c"),
	}
	if canarySilent(alive) {
		t.Fatal("E7a: canarySilent reported silent while the canary is alive (latest canary after latest traffic)")
	}
}

// ---------------------------------------------------------------------------
// E7b: the guardDied canary filter face.

// TestE7b_CanaryFeedsDeathProbe pins the DISEASE: an alive canary stream
// (periodic injected rejections) keeps refreshing guardDied's
// lastIntercept — the business guard's REAL death is masked (the probe
// reports alive). This test asserts the CURRENT unfiltered behavior; it
// flips when guardDied defaults to filtering (rewrite, not fix — the
// disease documentation form).
func TestE7b_HalfRealStreamFace(t *testing.T) {
	// R47 m-2: the filter face on a HALF-REAL stream — a real machine's
	// business rejection (refuse() output via Dispatch with revoked
	// grants) spliced with synthesized canary events, so the filter is
	// exercised on at least one machine-form detail (not only hand
	// literals).
	m := mustOpenAdopt(t, newLedgerPath(t))
	if o := m.Adopt(adoptRequest(t, "op-e7b-real")); o.Status != "adopted" {
		t.Fatalf("half-real: adopt = %q: %s", o.Status, o.Detail)
	}
	if o := m.Dispatch("op-e7b-real", nil); o.Status != "rejected" {
		t.Fatalf("half-real: revoked dispatch = %q, want rejected (the real business guard)", o.Status)
	}
	if o := m.Dispatch("op-e7b-real", fullGrants()); o.Status != "dispatched" {
		t.Fatalf("half-real: authorized dispatch = %q: %s", o.Status, o.Detail)
	}
	machineEvents, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	stream := append([]ledger.Event{}, machineEvents...)
	stream = append(stream, canaryEvent(len(stream), "op-c"))
	stream = append(stream, ledger.Event{EventType: "effect", ArbitrationSeq: int64(len(stream)), Outcome: ledger.Outcome{Status: "dispatched"}})
	stream = append(stream, canaryEvent(len(stream), "op-c"))
	// fixture precondition: the canary is alive
	if canarySilent(stream) {
		t.Fatal("half-real fixture error — the canary died")
	}
	// the filter closes the masking on the half-real stream too
	if died := guardDied(stream, "rejected", canaryPrefix); !died {
		t.Fatal("E7b half-real: filtered guardDied missed the business guard's death — the canary masks even on machine-form streams")
	}
	if died := guardDied(stream, "rejected", ""); died {
		t.Fatal("E7b half-real: unfiltered guardDied reported death — the canary failed to mask on machine-form streams (disease narrower than pinned)")
	}
}

func TestE7b_CanaryFeedsDeathProbe(t *testing.T) {
	// business guard alive (real rejection), then dies (traffic
	// continues, no more business rejections), then canary injections
	// keep coming — the unfiltered probe sees the canary rejections as
	// interceptions and reports ALIVE
	stream := []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business guard rejection"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(2, "op-c"),
		{EventType: "effect", ArbitrationSeq: 3, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(4, "op-c"),
	}
	// R47 M-1: BOTH payload preconditions are guarded (a fixture drift
	// that kills the canary or drops the business death must fail as a
	// FIXTURE error, not as a "disease is gone" misdiagnosis)
	if canarySilent(stream) {
		t.Fatal("E7b fixture error — the canary died in the fixture; the disease pin requires an ALIVE canary")
	}
	hasReal := false
	for _, e := range stream {
		if e.EventType == "control" && e.Outcome.Status == "rejected" && !strings.HasPrefix(e.Outcome.Detail, canaryPrefix) {
			hasReal = true
		}
	}
	if !hasReal {
		t.Fatal("E7b fixture error — no business rejection in the fixture; the disease pin requires a real death to mask")
	}
	if died := guardDied(stream, "rejected", ""); died {
		t.Fatal("E7b disease: unfiltered guardDied reported DEATH — the canary failed to mask it (the disease is gone; rewrite this test)")
	}
}

// TestE7b_FilterClosesMasking is the green face: the same stream with the
// filter applied reports DEATH correctly. Preconditions pinned (anti-
// tautology): a real business rejection exists BEFORE the traffic, and
// the canary events continue after it. Mutation probe: remove the filter
// guard (prefix != "") or the filter branch → this goes red or the E4
// suite breaks.
func TestE7b_FilterClosesMasking(t *testing.T) {
	stream := []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business guard rejection"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(2, "op-c"),
		{EventType: "effect", ArbitrationSeq: 3, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(4, "op-c"),
	}
	// precondition ① (R47 m-3: a fixture-EDIT tripwire, not an assertion
	// on the tested function — the property is visible in the literals
	// above): real business interception exists
	hasRealRejection := false
	for _, e := range stream {
		if e.EventType == "control" && e.Outcome.Status == "rejected" && !strings.HasPrefix(e.Outcome.Detail, canaryPrefix) {
			hasRealRejection = true
		}
	}
	if !hasRealRejection {
		t.Fatal("E7b: fixture error — no real business rejection in the stream")
	}
	// the filter face: with the canary prefix, the death is correctly
	// reported (canary rejections no longer count as interceptions)
	if died := guardDied(stream, "rejected", canaryPrefix); !died {
		t.Fatal("E7b filter: guardDied with canary filter missed the business guard's death — the canary still masks it")
	}
	// precondition ② (never-challenge face): remove the business
	// rejection → even filtered, no death is reported (the filter must
	// not invent interceptions)
	noBusiness := []ledger.Event{
		{EventType: "effect", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(1, "op-c"),
		{EventType: "effect", ArbitrationSeq: 2, Outcome: ledger.Outcome{Status: "dispatched"}},
	}
	if died := guardDied(noBusiness, "rejected", canaryPrefix); died {
		t.Fatal("E7b: filtered guardDied reported death with NO business rejection — the filter invented an interception (over-filtering)")
	}
}

// TestE7b_EmptyPrefixNoFilter pins the empty-string trap: a "" prefix
// must mean NO filtering (strings.HasPrefix(s, "") is always true — an
// unguarded predicate would filter every control event and break the E4
// semantics). The E4 suite passing unchanged is the regression proof.
func TestE7b_EmptyPrefixNoFilter(t *testing.T) {
	stream := []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "plain business rejection"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
	}
	// "" must behave exactly like the unfiltered probe (E4 semantics: a
	// business rejection followed by traffic reports DEATH)
	if died := guardDied(stream, "rejected", ""); !died {
		t.Fatal("E7b: empty prefix changed the unfiltered semantics — a business rejection followed by traffic must report death (E4)")
	}
}

// TestE7b_MidDetailCanaryNotFiltered pins the prefix convention's
// boundary: a [CANARY] appearing in the MIDDLE of a business detail is a
// coincidental string, not a canary event — it must NOT be filtered.
func TestE7b_MidDetailCanaryNotFiltered(t *testing.T) {
	stream := []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business detail mentioning [CANARY] incidentally"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
	}
	// the mid-detail event counts as a real interception (not filtered)
	if died := guardDied(stream, "rejected", canaryPrefix); !died {
		t.Fatal("E7b: a mid-detail [CANARY] was filtered — only the PREFIX form is the reserved convention")
	}
}
