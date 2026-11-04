package e2e

// E0/E3: correctness-layer experiments from the synthesized verification plan
// (29-reconciliation §3.2). These are the zero-LLM, immediately-runnable
// experiments that test whether xingchao's "consistent but wrong" critique
// (198232012) identifies a real structural hole in our architecture.
//
// E0 proves the disease exists: a "sick" S1 that always returns grant passes
// the adoption gate undetected. E3 proves the spec is self-contradictory:
// the fixture's veto window contradicts both T0 and T1.
//
// Both experiments may CHANGE our conclusions (the user's instruction:
// "有可能会通过实验验证或者改变我们的结论"). If E0 shows the gate somehow
// blocks the wrong grant, the "structural blindness" claim is falsified. If
// E3 shows the fixture and stand-ins are actually consistent, the "spec
// correctness" gap is falsified.
//
// POLARITY GUARD (review-loop R11): the two E0-sick tests assert the DISEASED
// state (pass = disease exists). When the correctness layer lands, they MUST
// be flipped to assert the blocking (pass = fixed). Forgetting to flip would
// leave them green while silently proving an obsolete claim.

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
)

// correctnessLayerLanded is the polarity guard's flip switch — set to true
// in the same commit that adds the correctness layer. E0-sick tests skip
// when this is true (their claim is obsolete).
var correctnessLayerLanded = false // flip when preconditions[]/verifier lands

// p3FixtureCorrectionLanded flips when the P3 fixture correction (unbounded
// veto, business-owner seat) lands. E3-window skips when this is true.
var p3FixtureCorrectionLanded = false // flip when P3 fixture correction lands

// s1AlwaysGrant is the "sick" S1 stand-in for E0: it ALWAYS returns
// grant-50000 with high-confidence details, regardless of evidence. This
// simulates xingchao's counterexample A: "even if Jev is deterministic and
// consistent, it can be stably wrong." If the adoption gate has any semantic
// correctness layer, this should be blocked. If not, it will be dispatched.
func s1AlwaysGrant(e creditEvidence) s1Verdict {
	return s1Verdict{
		kind:    "grant-50000",
		details: "all checks passed, assets well above cutoff, clean record, high confidence",
	}
}

// TestE0DiseaseExists_HealthyS1 is the positive control: the healthy S1
// correctly denies the counterexample evidence (4-month overdue 2 years ago).
// This must pass, proving the test harness works. If this fails, E0's
// negative result is meaningless.
func TestE0DiseaseExists_HealthyS1(t *testing.T) {
	h := newTask(t)
	e := creditEvidence{
		assetMillions:   35,
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}},
	}
	v := h.judge(e)
	if v.kind != "deny" {
		t.Fatalf("E0 positive control: healthy S1 returned %q, want deny — harness broken", v.kind)
	}
	// the deny record is adopted (decision record) — the machine CAN dispatch
	// it (it doesn't know it's a "deny" — this IS the structural blindness
	// E0 proves), but the HOST chooses not to. We verify the healthy S1
	// verdict is correct, not that the machine blocks it.
	if o := h.machine.Adopt(requestFor("op-e0-healthy", "er-1", "ev-1", digestHex('1'))); o.Status != "adopted" {
		t.Fatalf("E0 positive control: adopt = %q: %s", o.Status, o.Detail)
	}
	// CRITICAL: the machine WOULD dispatch this deny record if asked —
	// it has no verdict field and no precondition check. The HOST decides
	// not to call Dispatch for a deny. This is by design (semantic blindness
	// is the architecture's contract, not a bug), but it means the machine
	// provides no guard against a sick S1 that returns grant instead of deny.
	if o := h.machine.Dispatch("op-e0-healthy", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("E0 positive control: dispatch on deny record = %q — expected dispatched "+
			"(machine is semantically blind by design, host decides not to dispatch)", o.Status)
	}
}

// TestE0DiseaseExists_SickS1 is the disease existence proof: the "sick" S1
// (always grant) passes through the adoption gate completely undetected.
// This test asserts the CURRENT state — the fact that it PASSES is the
// proof that the architectural blindness is real. When we add the
// correctness layer (preconditions[] or verifier), this test should
// flip to red (the sick grant gets blocked), and then we update it to
// assert the blocking.
func TestE0DiseaseExists_SickS1(t *testing.T) {
	// POLARITY GUARD (review-loop R11): if the correctness layer has landed,
	// this test's claim ("disease exists") is obsolete — the sick grant would
	// be blocked and this test would fail its "adopted" assertion below,
	// which is the CORRECT red signal. The guard makes the polarity explicit:
	if correctnessLayerLanded {
		t.Skip("E0-sick: correctness layer landed — this test asserted the DISEASED state; " +
			"it must be rewritten to assert the BLOCKING (preconditions violation → control event)")
	}
	h := newTask(t)
	e := creditEvidence{
		assetMillions:   35,
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}, // veto should fire
	}

	// The sick S1 says grant, ignoring the 4-month overdue entirely
	v := s1AlwaysGrant(e)
	if v.kind != "grant-50000" {
		t.Fatalf("E0: sick S1 returned %q, want grant-50000 — sick stand-in broken", v.kind)
	}

	// THE EXPERIMENT: walk the sick grant through the full chain.
	// If the adoption gate has any semantic correctness layer, it should
	// reject or block this somewhere. If it doesn't, the wrong grant
	// will be adopted and dispatched.
	if o := h.machine.Adopt(requestFor("op-e0-sick", "er-1", "ev-1", digestHex('2'))); o.Status != "adopted" {
		t.Fatalf("E0: adopt = %q: %s — UNEXPECTED: gate blocked the sick grant! "+
			"This FALSIFIES the 'structural blindness' hypothesis", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-e0-sick", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("E0: dispatch = %q: %s — UNEXPECTED: gate blocked the sick dispatch! "+
			"This FALSIFIES the 'structural blindness' hypothesis", o.Status, o.Detail)
	}

	// If we reach here, the sick grant was adopted AND dispatched.
	// The disease exists. Record the evidence:
	receipt := h.submit("op-e0-sick")
	if o := h.machine.MarkCompleted("op-e0-sick"); o.Status != "completed" {
		t.Fatalf("E0: complete = %q: %s", o.Status, o.Detail)
	}

	// Assert the machine has no mechanism to detect the error:
	// 1. No precondition field in the request (verified by construction — Request struct has none)
	// 2. No verdict field (the gate never saw "grant-50000" vs the evidence)
	// 3. The machine completed normally — from its perspective, nothing went wrong
	if s := h.machine.State("op-e0-sick"); s != adopt.StateCompleted {
		t.Fatalf("E0: state = %q, want completed — machine saw nothing wrong", s)
	}
	events, _ := h.machine.Events()
	// 3 events: adoption, dispatched, completed — zero control events (nothing was rejected)
	if len(events) != 3 {
		t.Fatalf("E0: events = %d, want 3 (no rejections, no control events — gate was semantically blind)", len(events))
	}
	for _, ev := range events {
		if ev.EventType == "control" {
			t.Fatalf("E0: found control event — gate DID detect something! This falsifies the hypothesis")
		}
	}

	// CONCLUSION: the sick grant went through the entire chain —
	// adopt → dispatch → business API → completed — with zero resistance.
	// The adoption gate is semantically blind to the judgment's correctness.
	// xingchao's counterexample A is validated: "consistent but wrong" passes.
	//
	// t.Logf("E0 RESULT: disease CONFIRMED — sick S1 (always grant) with " +
	// 	"4-month overdue evidence passed through adopt→dispatch→API→completed. " +
	// 	"WGR = 1/1. The adoption gate has no semantic correctness layer. " +
	// 	"Receipt: %s", receipt)
	_ = receipt
}

// TestE0DiseaseExists_SickS1ExtractionMiss is the extraction-miss arm from
// 27-blank-collision: the S1 correctly reads the overdue record but the
// EVIDENCE DOSSIER itself is incomplete — the 4-month overdue is missing from
// the structured input the verifier would see. This tests whether ANY layer
// (not just the gate) catches "evidence was there but the input lost it."
//
// In our current architecture, the input (creditEvidence struct) is composed
// by the test harness — there IS no input assembly layer that could catch
// extraction errors. This test proves that.
func TestE0DiseaseExists_SickS1ExtractionMiss(t *testing.T) {
	h := newTask(t)

	// The REAL evidence has a 4-month overdue — but the EXTRACTION layer
	// (simulated: the input composer) drops it. The S1 sees a "clean" record.
	realEvidence := creditEvidence{
		assetMillions:   35,
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}, // REAL fact
	}
	// The extraction layer misses it:
	extractedEvidence := creditEvidence{
		assetMillions:   35,
		assetReportOK:   true,
		overdueOnRecord: nil, // extraction missed the overdue record
	}

	// S1 correctly judges based on what it was given (clean record → grant)
	v := h.judge(extractedEvidence)
	if v.kind != "grant-50000" {
		t.Fatalf("E0-extraction: S1 returned %q, want grant-50000 — the extraction stand-in is broken", v.kind)
	}
	// But the REAL evidence says this should be deny
	vReal := h.judge(realEvidence)
	if vReal.kind != "deny" {
		t.Fatalf("E0-extraction: real evidence S1 returned %q, want deny — harness broken", vReal.kind)
	}

	// The wrong grant (based on incomplete extraction) goes through the chain
	if o := h.machine.Adopt(requestFor("op-e0-extract", "er-1", "ev-1", digestHex('3'))); o.Status != "adopted" {
		t.Fatalf("E0-extraction: adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-e0-extract", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("E0-extraction: dispatch = %q: %s", o.Status, o.Detail)
	}
	_ = h.submit("op-e0-extract")
	if o := h.machine.MarkCompleted("op-e0-extract"); o.Status != "completed" {
		t.Fatalf("E0-extraction: complete = %q: %s", o.Status, o.Detail)
	}

	// CONCLUSION: the extraction error propagated through the entire chain
	// undetected. Even if we add a verifier that checks "months > 3 → deny"
	// on the EXTRACTED input, it would see a clean record and pass —
	// because the verifier consumes the same incomplete extraction.
	//
	// This is 27-blank-collision's "independence trap" proven in code:
	// the verifier's independence is capped by the extraction source's
	// independence. If the verifier reads the same (incomplete) input,
	// it inherits the extraction error.
	//
	// The fix requires: the verifier reads the ORIGINAL evidence source
	// (e.g., the evidlog / raw dossier), not S1's processed input.
}

// E3: Spec Self-Contradiction
//
// The judgment-spec-credit.json fixture says the veto is "in the window"
// (six-month window), but both T0's s1Judge and T1's t1Spec use an
// UNBOUNDED veto (any >3-month overdue at any time denies).
// Additionally, on C8 (missing asset report + historical overdue), T0
// returns on_missing_evidence (checks report first), but the spec's
// precedence 0 (veto) should fire first, and T1 correctly expects deny.
//
// This test PROVES the contradiction is real, not just asserted.

// fixtureVetoRule holds the parsed veto rule from the fixture JSON
type fixtureVetoRule struct {
	Precedence int    `json:"precedence"`
	Coverage   string `json:"coverage"`
}

type fixtureSpec struct {
	Conventions struct {
		TimeWindow string `json:"time_window"`
	} `json:"conventions"`
	Rules []fixtureVetoRule `json:"rules"`
}

// TestE3SpecSelfContradiction_WindowScope proves that the fixture's veto
// scope ("in the window") contradicts T0's stand-in ("unbounded") and T1's
// spec text ("at any time in the applicant's credit history on record").
//
// This test is expected to be RED (it proves a contradiction exists).
// When the P3 fixture correction lands (business-owner seat + unbounded veto),
// this test should flip to GREEN.
func TestE3SpecSelfContradiction_WindowScope(t *testing.T) {
	// POLARITY GUARD (review-loop R11): if the P3 fixture correction landed
	// (unbounded veto), this test's claim (fixture is window-scoped) is
	// obsolete — the fixture would no longer contain "in the window" and
	// the first assertion below would fail, which IS the correct red signal.
	// The guard makes the polarity explicit.
	if p3FixtureCorrectionLanded {
		t.Skip("E3-window: P3 fixture correction landed — this test asserted the OLD window-scoped veto; " +
			"rewrite to assert the unbounded scope in the corrected fixture")
	}
	// Read the fixture
	fixturePath := filepath.Join("..", "..", "..", "schema", "examples", "judgment", "valid", "judgment-spec-credit.json")
	raw, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Skipf("E3: fixture not found at %s (running from wrong directory?): %v", fixturePath, err)
	}
	var spec fixtureSpec
	if err := json.Unmarshal(raw, &spec); err != nil {
		t.Fatalf("E3: fixture JSON parse failed: %v", err)
	}

	// Find the veto rule (precedence 0)
	var vetoRule *fixtureVetoRule
	for i, r := range spec.Rules {
		if r.Precedence == 0 {
			vetoRule = &spec.Rules[i]
			break
		}
	}
	if vetoRule == nil {
		t.Fatal("E3: no precedence-0 rule found in fixture")
	}

	// ASSERTION 1: The fixture's veto is window-scoped
	// ("any overdue longer than three months in the window")
	if !strings.Contains(vetoRule.Coverage, "in the window") {
		t.Fatalf("E3: fixture veto coverage = %q — expected window-scoped (contains 'in the window'). "+
			"If this changed, the P3 fixture correction may have landed — update this test.", vetoRule.Coverage)
	}

	// ASSERTION 2: T0's s1Judge uses UNBOUNDED veto
	// (any >3-month overdue at any time → deny)
	e := creditEvidence{
		assetMillions:   35,
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}, // 2 years ago = OUTSIDE window
	}
	v := s1Judge(e)
	if v.kind != "deny" {
		t.Fatalf("E3: T0 s1Judge returned %q for 2-year-ago overdue, want deny (unbounded). "+
			"If this changed, the stand-in may have been window-scoped — contradiction resolved?", v.kind)
	}

	// THE CONTRADICTION: the fixture says "in the window" (six months),
	// but the stand-in denies a 2-year-ago overdue (which is OUTSIDE the
	// window). These two cannot both be correct.
	//
	// The fixture's own text limits the veto to the six-month window:
	if !strings.Contains(spec.Conventions.TimeWindow, "six calendar months") {
		t.Fatalf("E3: fixture time_window = %q — expected 'six calendar months'", spec.Conventions.TimeWindow)
	}

	// Proof complete: fixture says "in the window" (six months) but stand-in
	// denies a 2-year-old overdue. The spec is self-contradictory with its
	// own implementation. This is the E3 experiment result:
	//
	// t.Logf("E3 RESULT: spec self-contradiction CONFIRMED — fixture veto scope: "+
	// 	"'%s' (window-scoped, time_window='%s'), but T0 s1Judge denies a "+
	// 	"4-month overdue from %d years ago (unbounded). "+
	// 	"These cannot both be correct.", vetoRule.Coverage, spec.Conventions.TimeWindow, 2)
}

// TestE3SpecSelfContradiction_C8Precedence proves that on C8 (missing asset
// report + historical overdue), T0's s1Judge returns on_missing_evidence
// (because it checks the report first), but the spec's precedence-0 veto
// should fire FIRST (giving deny). T1's spec correctly puts the veto at
// precedence 0 — so T0 and T1 disagree on C8.
//
// This is registered as L23 in the minor ledger.
func TestE3SpecSelfContradiction_C8Precedence(t *testing.T) {
	// POLARITY GUARD (review-loop R12): C8 asserts T0's CURRENT precedence
	// order (report check before veto). When the P3 fixture correction
	// lands AND the T0 stand-in is fixed to match (veto fires first), this
	// test's claim (T0 = on_missing_evidence) is obsolete — rewrite to
	// assert deny (T0 ≡ T1, contradiction resolved).
	if p3FixtureCorrectionLanded {
		t.Skip("E3-C8: P3 fixture correction landed — T0 stand-in precedence must be fixed to match; " +
			"rewrite to assert T0 ≡ T1 (deny on C8, the L23 discrepancy is resolved)")
	}
	// C8 evidence: missing report AND a 4-month overdue 2 years ago
	e := creditEvidence{
		assetMillions:   35,
		assetReportOK:   false,                                    // report missing
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}, // AND veto should fire
	}

	// T0's s1Judge checks the report FIRST → on_missing_evidence
	v0 := s1Judge(e)
	if v0.kind != "on_missing_evidence" {
		t.Fatalf("E3-C8: T0 s1Judge returned %q for C8, want on_missing_evidence "+
			"(T0 checks report before veto — this is the L23 discrepancy)", v0.kind)
	}

	// T1's t1Spec puts the veto at precedence 0 (BEFORE the report check)
	// → the CORRECT answer per the spec is deny (veto fires regardless)
	//
	// We can't call t1Judge here (it's in the T1 test file which requires
	// real LLM), but we can verify the T1 spec text:
	//
	// From t1_llm_test.go's t1Spec:
	//   "- Precedence 0 (override): ANY overdue obligation longer than three
	//    months, AT ANY TIME in the applicant's credit history on record,
	//    denies credit — regardless of assets. This veto is NOT limited to
	//    any recent window"
	//
	// And C8 in t1Cases:
	//   expected: "deny", hardBar: true
	//
	// So T1 expects deny for the same input where T0 returns on_missing_evidence.
	//
	// PROOF: T0 returns on_missing_evidence, T1 expects deny. The spec's
	// own precedence rules say veto (precedence 0) fires before everything.
	// T0's implementation has the precedence order wrong.

	// We can verify this by reading the T1 test's spec text:
	t1SpecContainsVetoFirst := strings.Contains(t1Spec, "Precedence 0") &&
		strings.Contains(t1Spec, "ANY overdue") &&
		strings.Contains(t1Spec, "regardless of assets")

	if !t1SpecContainsVetoFirst {
		t.Fatal("E3-C8: T1 spec text does not contain unbounded precedence-0 veto — spec may have changed")
	}

	// t.Logf("E3-C8 RESULT: precedence contradiction CONFIRMED — T0 returns "+
	// 	"on_missing_evidence (report check first), T1 expects deny (veto at "+
	// 	"precedence 0 fires first). The spec's own precedence rules say the "+
	// 	"veto should fire before the report check. L23 is validated.")
}
