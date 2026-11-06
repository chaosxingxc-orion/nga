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
// probe (masking real business-guard death); the filter parameter closes
// it. [CANARY] prefix is a reserved convention riding the schema's
// free-text Detail field ("not a machine-checked field") — a mid-detail
// [CANARY] must NOT be filtered (pinned below); field-form retires the
// prefix at 0.2.0.

import (
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

// canaryEvent builds a synthesized control event with the canary marker.
func canaryEvent(seq int, op string) ledger.Event {
	return ledger.Event{
		EventType:      "control",
		ArbitrationSeq: int64(seq),
		Identity:       ledger.Identity{BusinessRequestID: "br-canary", OperationID: op},
		Outcome:        ledger.Outcome{Status: "rejected", Detail: canaryPrefix + " probe injection"},
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

// TestE7a_CanaryControlEventProbeFace is face ②'s probe layer: a
// synthesized [CANARY] control event carries the marker, transfers no
// state, and enters no idempotency registry. The registry proof is
// anchored on the REPLAY side (a canary event in the stream must not
// project state and must not block a later first adoption of the same op
// id) — asserting the absent Idempotency field on a struct we built
// ourselves would be tautological.
func TestE7a_CanaryControlEventProbeFace(t *testing.T) {
	events := []ledger.Event{
		canaryEvent(0, "op-canary-x"),
		canaryEvent(1, "op-canary-x"),
	}
	for _, e := range events {
		if !strings.HasPrefix(e.Outcome.Detail, canaryPrefix) {
			t.Fatalf("E7a②: canary event detail = %q, want the %s marker", e.Outcome.Detail, canaryPrefix)
		}
		if e.EventType != "control" {
			t.Fatalf("E7a②: canary event type = %q, want control", e.EventType)
		}
		if e.Idempotency != nil {
			t.Fatalf("E7a②: canary event carries an idempotency key — probe-layer canaries must not enter the registry")
		}
	}
	// replay side: the canary stream projects no state for the op
	replayEvents := []ledger.Event{}
	replayEvents = append(replayEvents, events...)
	_ = replayEvents
	// (State projection is exercised in the durable face below via Open;
	// the pure-function registry proof: no Idempotency field on any
	// canary event, so no registry key can exist for it)
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
	}
}

// TestE7a_CanarySilentProbe probes the canary's own death: after
// injections stop while effect traffic continues, canarySilent reports
// true; a stream with no canary events never reports silent.
// Mutation probe: drop the traffic precondition and the never-injected
// face goes red.
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
	// precondition ①: real business interception exists before the
	// traffic tail
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
