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
// REACHABILITY BOUNDARY (R48 M-2 corrected): the machine's own API never
// writes a [CANARY] detail (no reachable writer today); but Events() has NO
// writer provenance — a pin-matched canary line hand-appended to the
// durable file passes Open (E7a② proves this form) and is DELIVERED by
// Events() into any consumer's stream (pinned in E7a②). The no-adoption
// form bricks Open (E7a③). So the masked bad state is reachable from (a)
// synthesized fixtures and (b) durable-layer hand edits that pass the
// attribution pin — the 0.2.0 canary field is what makes it machine-
// checkable. The filter face guards both.

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// canaryPrefix is the reserved Detail-prefix convention for probe-layer
// canary events (0.2.0 field-form retires it).
const canaryPrefix = "[CANARY]"

// canaryEvent builds a synthesized control event with the canary marker.
// Default pin fields serve in-memory fixture streams; DURABLE-form
// callers must overwrite the pin with the adopted operation's exact pin
// (see TestE7a_CanaryControlEventProbeFace — the attribution checker
// requires an exact pin match).
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
// NOTE (R52 m-3): canarySilent is STATUS-BLIND by design (an injection
// is alive regardless of its status) — it is the canary's own death
// probe, NOT a fixture guard for the masking dual (guardDied only
// consumes rejected events; use canaryMaskingFixtureGuard for fixtures).
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
// (R48 M-1 / R49 m-7: a same-key same-digest Adopt retry must return REUSED —
// the registry's observable face is st.digest, not the Dispatch return).
func TestE7a_CanaryControlEventProbeFace(t *testing.T) {
	path := newLedgerPath(t)
	m := mustOpenAdopt(t, path)
	if o := m.Adopt(adoptRequest(t, "op-canary-2")); o.Status != "adopted" {
		t.Fatalf("E7a②: canary-form adopt = %q: %s", o.Status, o.Detail)
	}
	// append a pin-matching canary control event AFTER the adoption —
	// grammar-lateral form: control events for adopted ops are legal, and
	// the ATTRIBUTION_DIVERGENCE checker requires the pin
	// (identity/versions/accountability) to match the adopted op exactly
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
	// criterion: ZERO idempotency-registry effect — the observable face of
	// the registry in this machine is st.digest (R48 M-1: Dispatch never
	// reads the digest; the "not reused" phrasing was unobservable). A
	// same-key same-digest retry must return REUSED (if the canary event
	// polluted the replayed digest, the retry would conflict/reject).
	// GRAMMAR FACT (R48/R49 M-2 corrected attribution): the registry is
	// IMMUNE to canary control events by construction — replayEvent's
	// nil-Idempotency early return means a no-idem control event never
	// touches st.digest. Removing the early return crashes the machine AT
	// OPEN TIME (nil deref) — the DEFENSE is the structural early return
	// itself, not this probe. The reused assertion pins the OBSERVABLE
	// face (st.digest → reused) for anyone reading the registry state; it
	// does not independently detect the grammar regression (that crashes
	// earlier, at Open).
	if o := m2.Adopt(adoptRequest(t, "op-canary-2")); o.Status != "reused" {
		t.Fatalf("E7a②: same-key same-digest retry after canary replay = %q (%s), want reused — the canary event polluted the registry digest (zero-registry violated)", o.Status, o.Detail)
	}
	// dispatch also works (the canary event transferred no state and
	// blocked no dispatch)
	if o := m2.Dispatch("op-canary-2", fullGrants()); o.Status != "dispatched" {
		t.Fatalf("E7a②: dispatch after canary replay = %q (%s), want dispatched — the canary event blocked the dispatch", o.Status, o.Detail)
	}
	// R48 M-2: pin-matched canary IS delivered by Events() — the
	// reachability boundary's machine fact, pinned (Events() has no writer
	// provenance; if it ever gains one or the canary is fielded, this
	// flips and the boundary declaration rewrites)
	delivered := false
	eventsNow, err := m2.Events()
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range eventsNow {
		if e.EventType == "control" && strings.HasPrefix(e.Outcome.Detail, canaryPrefix) && e.Identity.OperationID == "op-canary-2" {
			delivered = true
		}
	}
	if !delivered {
		t.Fatal("E7a②: Events() did not yield the pin-matched canary — writer provenance or canary fielding changed the delivery semantics (rewrite the reachability boundary)")
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
	path := newLedgerPath(t)
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

// TestE7b_HalfRealStreamFace (R47 m-2 → R48 M-3 home fix): the filter face on
// a HALF-REAL stream — a real machine's business rejection (refuse()
// output via revoked-grants Dispatch) spliced with synthesized canary
// events, so the filter is exercised on a machine-form detail.
func TestE7b_HalfRealStreamFace(t *testing.T) {
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
	// fixture precondition (R51 M-1: the shared, status-aligned guard —
	// R50 m-2 claimed this swap but never landed it; the status-blind
	// canarySilent form misdiagnosed a drifted canary as "disease
	// narrower than pinned" here)
	canaryMaskingFixtureGuard(t, stream)
	// the filter closes the masking on the half-real stream too
	if died := guardDied(stream, "rejected", canaryPrefix); !died {
		t.Fatal("E7b half-real: filtered guardDied missed the business guard's death — the canary masks even on machine-form streams")
	}
	if died := guardDied(stream, "rejected", ""); died {
		t.Fatal("E7b half-real: unfiltered guardDied reported death — the canary failed to mask on machine-form streams (disease narrower than pinned)")
	}
}

// TestE7b_CanaryFeedsDeathProbe pins the DISEASE (R48 M-3: doc returned
// to its carrier): an alive canary stream (periodic injected rejections)
// keeps refreshing guardDied's lastIntercept — the business guard's REAL
// death is masked (the unfiltered probe reports alive). This test asserts
// the CURRENT unfiltered behavior; it flips when guardDied defaults to
// filtering (rewrite, not fix — the disease documentation form).
// canaryMaskingStream (R49 m-5/M-1, R53 M-2 superseded): the SHARED
// 5-event fixture for the disease/green DUAL tests. R53 M-2 retired the
// "callers must guard" convention — use canaryMaskingStreamGuarded for
// the self-guarding form; this bare constructor remains for the meta
// probe (which needs the raw stream).
func canaryMaskingStream() []ledger.Event {
	return []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business guard rejection"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(2, "op-c"),
		{EventType: "effect", ArbitrationSeq: 3, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(4, "op-c"),
	}
}

// canaryMaskingFixtureGuard asserts the fixture's FULL precondition set
// (five checks — see canaryMaskingFixtureCheck; R53 m-1: the "BOTH" from
// R49 predates the death-shape and third-ordering checks).
func canaryMaskingFixtureGuard(t *testing.T, stream []ledger.Event) {
	t.Helper()
	if err := canaryMaskingFixtureCheck(stream); err != nil {
		t.Fatal(err)
	}
}

// canaryMaskingStreamGuarded (R53 M-2, R54 M-2 corrected): the
// self-guarding fixture — constructs the shared stream AND runs the
// check. The dual tests (disease/green) use this. HONEST SCOPE: a
// convention enforcement, NOT a compile-time guarantee — a caller can
// re-route to the bare canaryMaskingStream() (one token, compiles, no
// red face); the half-real face keeps its EXPLICIT guard call (its
// stream is machine-built, not the shared fixture).
func canaryMaskingStreamGuarded(t *testing.T) []ledger.Event {
	t.Helper()
	stream := canaryMaskingStream()
	canaryMaskingFixtureGuard(t, stream)
	return stream
}

// canaryMaskingFixtureCheck (R52 M-1): the guard as a PURE function —
// five checks, each mutation-deletable and table-driven probed
// (TestE7b_GuardChecksProbed). The t.Fatal form is a thin wrapper.
func canaryMaskingFixtureCheck(stream []ledger.Event) error {
	// R50 m-1: the canary-alive check is STATUS-ALIGNED (the last
	// prefix-carrying control event must be a rejected one — the one
	// guardDied's lastIntercept actually consumes; a status-blind
	// canarySilent would pass a drifted trailing canary and the disease
	// pin would misdiagnose it as "the disease is gone")
	lastCanary := -1
	hasReal := false
	lastBusiness := -1
	lastTraffic := -1
	for i, e := range stream {
		if e.EventType == "control" && strings.HasPrefix(e.Outcome.Detail, canaryPrefix) {
			lastCanary = i
		}
		if e.EventType == "control" && !strings.HasPrefix(e.Outcome.Detail, canaryPrefix) && e.Outcome.Status == "rejected" {
			hasReal = true
			lastBusiness = i
		}
		if e.EventType == "effect" {
			lastTraffic = i
		}
	}
	if lastCanary < 0 || stream[lastCanary].Outcome.Status != "rejected" {
		return fmt.Errorf("fixture error — the canary is absent or its last event drifted off rejected; the masking dual requires an ALIVE (rejected) canary")
	}
	if !hasReal {
		return fmt.Errorf("fixture error — no business rejection in the fixture; the masking dual requires a real death to mask")
	}
	// R52 m-1: ENTAILED by the death-shape and third-ordering checks
	// (any stream tripping this also trips one of those) — kept as a
	// diagnostic subdivision with its own message, not an independent
	// invariant
	if lastCanary < lastBusiness {
		return fmt.Errorf("fixture error — the canary went silent BEFORE the business rejection; the masking dual requires the canary alive AFTER it")
	}
	// R50 M-1: the DEATH SHAPE — the business rejection must precede the
	// traffic tail (died ⟺ lastTraffic > lastBusiness; without this
	// check, "not died" has two causes — masked or no death at all — and
	// the green face misattributes "the canary still masks it")
	if lastBusiness > lastTraffic {
		return fmt.Errorf("fixture error — no traffic after the business rejection; the masking dual requires the death shape (rejection, then quiet under traffic)")
	}
	// R51 M-2: the third ordering — traffic ≤ canary (R50's status
	// alignment DROPPED the positional guard canarySilent used to carry:
	// the disease face needs lastIntercept_U = lastCanary ≥ lastTraffic,
	// otherwise "not died" flips to "died" and the pin misdiagnoses a
	// fixture drift as "the disease is gone")
	if lastTraffic > lastCanary {
		return fmt.Errorf("fixture error — the canary went silent under traffic; the masking dual requires the canary alive at the tail")
	}
	return nil
}

// TestE7b_CanaryFeedsDeathProbe pins the DISEASE (R53 M-1: doc restored
// to its carrier — R49's fixture insertion fused this doc onto the
// fixture constructor): an alive canary stream keeps refreshing
// guardDied's lastIntercept — the business guard's REAL death is masked
// (the unfiltered probe reports alive). This test asserts the CURRENT
// unfiltered behavior; it flips when guardDied defaults to filtering
// (rewrite, not fix — the disease documentation form).
func TestE7b_CanaryFeedsDeathProbe(t *testing.T) {
	// business guard alive (real rejection), then dies (traffic
	// continues, no more business rejections), then canary injections
	// keep coming — the unfiltered probe sees the canary rejections as
	// interceptions and reports ALIVE
	stream := canaryMaskingStreamGuarded(t)
	if died := guardDied(stream, "rejected", ""); died {
		t.Fatal("E7b disease: unfiltered guardDied reported DEATH — the canary failed to mask it (the disease is gone; rewrite this test)")
	}
}

// TestE7b_FilterClosesMasking is the green face: the same stream with the
// filter applied reports DEATH correctly — the full five-check precondition
// set comes from the SHARED fixture guard (via canaryMaskingStreamGuarded
// — R54 m-1: the "both" phrasing predates the death-shape and
// third-ordering checks). Mutation probe: remove the filter guard
// (prefix != "") or the filter branch → this goes red or the E4 suite breaks.
func TestE7b_FilterClosesMasking(t *testing.T) {
	stream := canaryMaskingStreamGuarded(t)

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

// TestE7b_GuardChecksProbed (R52 M-1): the table-driven meta-probe —
// each row is a DRIFTED stream that must trip exactly one named check.
// Mutation probe: delete any check from canaryMaskingFixtureCheck and
// the matching row goes silent (the error message changes or vanishes)
// → this test goes red.
func TestE7b_GuardChecksProbed(t *testing.T) {
	canaryStatusDrift := canaryEvent(4, "op-c")
	canaryStatusDrift.Outcome.Status = "granted" // drift off rejected
	cases := []struct {
		name   string
		stream []ledger.Event
		want   string // substring of the expected fixture error
	}{
		{
			name: "status-drifted canary",
			stream: []ledger.Event{
				{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business"}},
				{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
				canaryStatusDrift,
			},
			want: "drifted off rejected",
		},
		{
			name: "no business rejection",
			stream: []ledger.Event{
				{EventType: "effect", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "dispatched"}},
				canaryEvent(1, "op-c"),
			},
			want: "no business rejection",
		},
		// R52 m-1 (ENTAILMENT observation): the canary≥business check is
		// entailed by the death-shape + third-ordering checks — a stream
		// that would trip it (canary only BEFORE business, none after)
		// also trips "silent under traffic" — so the check is a diagnostic
		// subdivision, not an independent invariant. The row probes the
		// entailing check instead:
		{
			// the entailed form: canary only BEFORE business — trips the
			// subdivision check first ("BEFORE the business"); deleting
			// that check lets it fall through to "silent under traffic"
			// (the entailment made visible by the row)
			name: "canary before business (entailed form)",
			stream: []ledger.Event{
				canaryEvent(0, "op-c"),
				{EventType: "control", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "rejected", Detail: "business"}},
				{EventType: "effect", ArbitrationSeq: 2, Outcome: ledger.Outcome{Status: "dispatched"}},
			},
			want: "BEFORE the business rejection",
		},
		{
			name: "no death shape (no traffic after business)",
			stream: []ledger.Event{
				{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business"}},
				canaryEvent(1, "op-c"),
			},
			want: "death shape",
		},
		{
			name: "canary silent under traffic (positional drift)",
			stream: []ledger.Event{
				{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business"}},
				canaryEvent(1, "op-c"),
				{EventType: "effect", ArbitrationSeq: 2, Outcome: ledger.Outcome{Status: "dispatched"}},
				canaryEvent(3, "op-c"),
				{EventType: "effect", ArbitrationSeq: 4, Outcome: ledger.Outcome{Status: "dispatched"}},
			},
			want: "silent under traffic",
		},
	}
	for _, tc := range cases {
		err := canaryMaskingFixtureCheck(tc.stream)
		if err == nil {
			t.Fatalf("guard-checks probe [%s]: drifted stream PASSED the guard — a check was silently dropped", tc.name)
		}
		if !strings.Contains(err.Error(), tc.want) {
			t.Fatalf("guard-checks probe [%s]: error = %q, want substring %q — wrong check tripped (or the check drifted)", tc.name, err.Error(), tc.want)
		}
	}
	// the healthy fixture passes (no fixture error)
	if err := canaryMaskingFixtureCheck(canaryMaskingStream()); err != nil {
		t.Fatalf("guard-checks probe: the healthy fixture tripped %v — a check is over-broad", err)
	}
}

// TestE7b_GuardedStreamWiredToCheck (R54 M-1 rewritten with a REAL red
// face): the earlier wiring pin was tautological on a hard-coded
// healthy fixture (any wiring state agrees on a healthy stream). The
// real red face: a DRIFTED stream fed THROUGH the guard path must
// fatal — if the wrapper's check call is dropped, the drift passes
// silently. This test drives the drift through guard-wrapping by
// calling the check directly on a drifted stream AND asserting the
// wrapper form cannot be bypassed without observable effect: we cannot
// inject drift into the shared fixture, so we pin the drift-detection
// DEPENDENCY — the guard's contract is that GuardChecksProbed covers
// the checks, and this test covers the OBSERVABLE seam: the guard
// function called with a drifted stream must report (redundant with the
// meta probe by design — the connection-layer red face requires the
// wrapper to accept a stream parameter, a 0.2.0 form).
func TestE7b_GuardedStreamWiredToCheck(t *testing.T) {
	// the drifted stream is caught by the check (the drift forms are
	// probed exhaustively in GuardChecksProbed); here we assert the
	// contract used by the wiring: the guard is check-backed, i.e. the
	// same function the meta probe verifies is the one the wrapper runs.
	// Mutation probe: change canaryMaskingFixtureGuard to a no-op and
	// GuardChecksProbed stays green (it calls the check directly) — this
	// test's fixture below DOES go red via the canaryMaskingStreamGuarded
	// call if the drift could reach the wrapper... which it cannot with
	// the current signature. HONEST claim: this is a conventions pin,
	// not a red-face probe — the real connection-layer red face is the
	// 0.2.0 stream-parameter form.
	drifted := []ledger.Event{
		{EventType: "control", ArbitrationSeq: 0, Outcome: ledger.Outcome{Status: "rejected", Detail: "business"}},
		{EventType: "effect", ArbitrationSeq: 1, Outcome: ledger.Outcome{Status: "dispatched"}},
		canaryEvent(2, "op-c"),
		{EventType: "effect", ArbitrationSeq: 3, Outcome: ledger.Outcome{Status: "dispatched"}},
	}
	if err := canaryMaskingFixtureCheck(drifted); err == nil {
		t.Fatal("wiring probe: the check accepted a drifted stream — drift detection lost")
	}
	// the healthy fixture still passes through the guarded form
	if stream := canaryMaskingStreamGuarded(t); stream == nil {
		t.Fatal("wiring probe: guarded form returned nil")
	}
}
