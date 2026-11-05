package e2e

// E0/E3: correctness-layer experiments from the synthesized verification plan
// (29-reconciliation §3.2). These are the zero-LLM, immediately-runnable
// experiments that test whether xingchao's "consistent but wrong" critique
// (198232012) identifies a real structural hole in our architecture.
//
// E0 proves the disease exists: a "sick" S1 that always returns grant passes
// the adoption gate undetected. E3 PROVED the spec was self-contradictory
// (the fixture's window-scoped veto contradicted both T0 and T1); that
// contradiction is now RESOLVED (P3 fixture correction + L23 priority
// alignment landed — see the two E3 tests' doc comments for the resolved
// state and their mutation probes).
//
// Both experiments were framed as conclusion-changing probes (the user's
// instruction: "有可能会通过实验验证或者改变我们的结论"). E0's result
// stands (the gate does not block the wrong grant — the structural
// blindness claim holds). E3 ran and resolved its contradiction once P3+L23
// landed; its former "the fixture and stand-ins are actually consistent"
// falsification branch is now the asserted state.
//
// POLARITY GUARD (review-loop R11): the two E0-sick tests assert the DISEASED
// state (pass = disease exists). When the correctness layer lands, they MUST
// be flipped to assert the blocking (pass = fixed). Forgetting to flip would
// leave them green while silently proving an obsolete claim.

import (
	"encoding/json"
	"fmt"
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

// p3FixtureCorrectionLanded was removed in R20 (B-1): its two skip guards
// survived the rewrite of the E3 test bodies, leaving the rewritten
// assertions as dead code — the P3 correction and the L23 fix had zero
// active coverage while the ledger claimed "极性翻绿". The E3 tests now
// assert the corrected state directly and are mutation-coupled (fixture
// text revert / s1Judge order revert both turn them red).

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
	// POLARITY GUARD (L47 fix): this test asserts the DISEASED state for
	// extraction-miss (the extraction error passes through undetected).
	// When the correctness layer lands, this test must be rewritten.
	if correctnessLayerLanded {
		t.Skip("extraction-miss: correctness layer landed — rewrite to assert the verification seat catches extraction gaps (or honestly declares it cannot)")
	}
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

// E3: Spec Self-Contradiction — RESOLVED STATE (P3 + L23 landed)
//
// The two contradictions this experiment proved are now fixed and this
// file asserts the resolved state (see each test's doc comment for its
// mutation probe):
//   - window scope: the fixture's veto is unbounded ("at any time"),
//     matching T0's stand-in and T1's t1Spec
//   - C8 precedence: T0's s1Judge fires the veto (precedence 0) BEFORE
//     the missing-evidence check, matching t1Spec's ordering

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

// TestE3SpecSelfContradiction_WindowScope asserts the RESOLVED state of
// the former window-scope contradiction: the fixture's veto is unbounded
// ("at any time in the applicant's credit history on record") and T0's
// stand-in agrees. R20 B-1: the polarity guard that skipped this test
// after the P3 correction landed was NEVER removed when the body was
// rewritten — the assertions below were dead code and the P3 correction
// had zero active coverage (reverting the fixture text kept all 21
// packages green). The guard is gone; the assertions must run.
//
// Mutation probes: revert the fixture's veto coverage to "in the window
// denies" → assertion 1 fails; window the stand-in → assertion 2 fails.
func TestE3SpecSelfContradiction_WindowScope(t *testing.T) {
	// Read the fixture. R21 M-3: a missing fixture is a RED, not a skip —
	// this test is the fixture's only SEMANTIC consumer (cmd/judgment's
	// must-accept loop also reads it, but only schema-validates the whole
	// examples/judgment/valid/ directory and does not pin this single
	// file); skipping on a missing/moved file would silently evaporate
	// the P3 correction's active coverage (the B-1 disease shape via an
	// environmental guard).
	fixturePath := filepath.Join("..", "..", "..", "schema", "examples", "judgment", "valid", "judgment-spec-credit.json")
	raw, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("E3: fixture not found at %s (an in-repo required resource — a missing fixture must fail, not skip): %v", fixturePath, err)
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

	// ASSERTION 1: The fixture's veto is NOW unbounded (P3 correction landed)
	// — it must NOT contain the old "in the window" window-scoping
	if strings.Contains(vetoRule.Coverage, "in the window denies") {
		t.Fatalf("E3: fixture veto still window-scoped (%q) — P3 correction NOT landed", vetoRule.Coverage)
	}
	if !strings.Contains(vetoRule.Coverage, "at any time") {
		t.Fatalf("E3: fixture veto coverage = %q — expected 'at any time' (unbounded, P3 corrected)", vetoRule.Coverage)
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
		t.Fatalf("E3: T0 s1Judge returned %q for 2-year-ago overdue, want deny (unbounded)", v.kind)
	}

	// The contradiction is RESOLVED: both the fixture and the stand-in now
	// use unbounded veto. The time_window convention still exists (for the
	// upper band rule) and correctly mentions "six calendar months":
	if !strings.Contains(spec.Conventions.TimeWindow, "six calendar months") {
		t.Fatalf("E3: fixture time_window = %q — expected 'six calendar months' (upper band only)", spec.Conventions.TimeWindow)
	}
	// The window must be scoped to the upper band, not the veto:
	if !strings.Contains(spec.Conventions.TimeWindow, "upper band") {
		t.Fatalf("E3: fixture time_window = %q — expected to mention 'upper band' scope", spec.Conventions.TimeWindow)
	}

	// R24 m-1: the T1 half of the resolved state is ASSERTED, not just
	// narrated — t1Spec's veto wording must stay unbounded (a re-windowed
	// veto clause would keep the three C8-side markers passing while
	// silently breaking the three-way agreement this file claims)
	if !strings.Contains(t1Spec, "AT ANY TIME") {
		t.Fatal("E3: t1Spec no longer contains 'AT ANY TIME' — the T1 veto clause is no longer unbounded")
	}
	if !strings.Contains(t1Spec, "limited to any recent window") {
		t.Fatal("E3: t1Spec no longer contains 'limited to any recent window' — the T1 veto clause's no-window declaration is gone")
	}

	// Proof complete: fixture and stand-in now AGREE on the unbounded veto
	// (the former contradiction is resolved by the P3 correction); the
	// time_window convention survives scoped to the upper band only.
}

// TestE3SpecSelfContradiction_C8Precedence asserts the RESOLVED state of
// the former C8 precedence discrepancy (minor ledger L23): on C8 (missing
// asset report + historical overdue), T0's s1Judge now returns deny —
// the veto (precedence 0) fires before the missing-evidence check,
// aligned with t1Spec. R20 B-1: the polarity guard that skipped this
// test after the correction landed was NEVER removed when the body was
// rewritten — the assertions below were dead code and the L23 fix had
// zero active coverage (reverting s1Judge's priority order kept the
// whole module green). The guard is gone; the assertions must run.
//
// Mutation probe: restore the report-check-first order in s1Judge →
// the deny assertion below fails.
func TestE3SpecSelfContradiction_C8Precedence(t *testing.T) {
	// C8 evidence: missing report AND a 4-month overdue 2 years ago
	e := creditEvidence{
		assetMillions:   35,
		assetReportOK:   false,                                    // report missing
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}, // AND veto should fire
	}

	// L23 FIXED: T0's s1Judge now checks the veto FIRST → deny
	// (priority order aligned with t1Spec: veto at precedence 0 fires
	// before the missing-evidence check)
	v0 := s1Judge(e)
	if v0.kind != "deny" {
		t.Fatalf("E3-C8: T0 s1Judge returned %q for C8, want deny "+
			"(L23 fix: veto at precedence 0 fires before missing-evidence check)", v0.kind)
	}

	// Historical record (the former diseased state, fixed by L23): T0's
	// s1Judge used to check the report FIRST and return
	// on_missing_evidence for C8, while t1Spec puts the veto at precedence
	// 0 (before the report check) and T1's C8 case expects deny — a
	// priority-order discrepancy between T0 and T1. The fix moved the veto
	// before the missing-evidence check in s1Judge (asserted above).
	// Mutation probe: revert s1Judge's order (report first) → the deny
	// assertion above fails.
	//
	// t1Spec (t1_llm_test.go) states: "Precedence 0 (override): ANY overdue
	// obligation longer than three months, AT ANY TIME in the applicant's
	// credit history on record, denies credit — regardless of assets. This
	// veto is NOT limited to any recent window" — and C8 in t1Cases
	// expects "deny", hardBar: true.
	t1SpecContainsVetoFirst := strings.Contains(t1Spec, "Precedence 0") &&
		strings.Contains(t1Spec, "ANY overdue") &&
		strings.Contains(t1Spec, "regardless of assets")

	if !t1SpecContainsVetoFirst {
		t.Fatal("E3-C8: T1 spec text does not contain unbounded precedence-0 veto — spec may have changed")
	}

	// R24 m-1 (ordering half): precedence 0 is THE VETO and nothing else —
	// the contiguous claim pins that the precedence-0 clause is the veto
	// clause, and the count pins that no other clause (e.g.
	// missing-evidence) has been relabeled precedence 0
	if !strings.Contains(t1Spec, "- Precedence 0 (override): ANY overdue") {
		t.Fatal("E3-C8: t1Spec's precedence-0 clause is no longer the unbounded veto — the contiguous claim 'Precedence 0 (override): ANY overdue' is gone")
	}
	if n := strings.Count(t1Spec, "Precedence 0"); n != 1 {
		t.Fatalf("E3-C8: t1Spec contains %d 'Precedence 0' clauses, want exactly 1 (the veto) — a relabeled clause would break the ordering half of the resolved state", n)
	}

	// R23 m-1: the T1-side half is ASSERTED, not just narrated — the C8
	// case-table entry itself must expect deny at the hard bar (if this
	// entry is edited to any other expectation, the resolved-state claim
	// loses its T1 half and this goes red).
	c8Found := false
	for _, c := range t1Cases {
		if c.id == "C8-veto-beats-missing-evidence" {
			c8Found = true
			if c.expected != "deny" || !c.hardBar {
				t.Fatalf("E3-C8: t1Cases C8 entry = (expected=%q, hardBar=%v), want (deny, true) — the T1 half of the resolved state", c.expected, c.hardBar)
			}
		}
	}
	if !c8Found {
		t.Fatal("E3-C8: t1Cases has no C8-veto-beats-missing-evidence entry — the case table changed")
	}
}

// TestE0DiseaseExists_PhantomJSONMidFile is R14' M-1's deterministic red
// probe (two assertions, one run): a "legal JSON object, not a machine
// event" line ({"note":"out-of-band"}) inserted mid-file between two real
// machine writes must be caught by the append-path write-time re-check —
// per the P1-2 doctrine ("out-of-band damage between Open and write is
// caught"). Current state: ParseLines' typed view accepts the phantom as
// a complete event line, tornNow=false, STALE_WRITER passes (last-line seq
// is the real event's), the rebuild preserves the phantom, and the write
// returns success — poisoning the file so the NEXT Open rejects it.
func TestE0DiseaseExists_PhantomJSONMidFile(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-phantom-1", "er-1", "ev-1", digestHex('8'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Adopt(requestFor("op-phantom-2", "er-1", "ev-1", digestHex('9'))); o.Status != "adopted" {
		t.Fatalf("adopt 2 = %q: %s", o.Status, o.Detail)
	}

	// external damage: insert a phantom JSON line mid-file (newline-terminated)
	path := h.dir + "/adopt.jsonl"
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.SplitN(string(raw), "\n", 2) // after first line
	if len(lines) < 2 {
		t.Fatal("expected at least 2 lines in the file")
	}
	phantom := `{"note":"out-of-band"}` + "\n"
	poisoned := lines[0] + "\n" + phantom + lines[1]
	if err := os.WriteFile(path, []byte(poisoned), 0o600); err != nil {
		t.Fatal(err)
	}

	// ASSERTION A: the next Adopt must be rejected (the write-time re-check
	// catches out-of-band damage per the P1-2 doctrine)
	if o := h.machine.Adopt(requestFor("op-phantom-3", "er-1", "ev-1", digestHex('a'))); o.Status == "adopted" {
		t.Fatalf("M-1 CONFIRMED: phantom JSON line accepted as a legal event — "+
			"adopt returned %q (detail: %s); the file is now poisoned "+
			"(the next Open will reject it)", o.Status, o.Detail)
	}

	// ASSERTION B (post-fix semantics): the phantom line is IN the file
	// (external damage was done before the write was refused — the machine
	// didn't write it, but the damaged bytes are there). The machine must
	// refuse ALL writes on it (no false success), and a fresh Open must
	// also detect the damage — this is the fail-closed doctrine: the file
	// needs manual repair, exactly like a torn tail. The POST-FIX assertion
	// is that Adopt was rejected (assertion A) and a fresh Open FAILS
	// (the damage is detectable, not silently absorbed) — the anti-pattern
	// was "write succeeds, next Open rejects"; the fixed pattern is
	// "write refused, next Open also refuses (detectable damage)".
	if _, err := adopt.Open(path); err == nil {
		t.Fatal("M-1 REGRESSION: the poisoned file was silently accepted by a fresh Open — " +
			"external damage must be detectable at load (fail-closed)")
	}
	// and the machine must not have made it worse: the file bytes are
	// exactly what the external damage left (no machine write on top)
	after, _ := os.ReadFile(path)
	if string(after) != poisoned {
		t.Fatal("M-1: the machine rewrote the poisoned file — damaged bytes must be preserved for manual repair")
	}
}

// TestE0DiseaseExists_PhantomJSONEOF is M-1's sister probe (EOF form):
// a phantom line appended at EOF with a MATCHING seq passes both the
// torn check (it has a newline) and the STALE_WRITER check (seq == last+1
// coincidentally), gets persisted, and poisons the file.
func TestE0DiseaseExists_PhantomJSONEOF(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-phantom-eof", "er-1", "ev-1", digestHex('b'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}

	// external damage: append a phantom line with a MATCHING seq at EOF
	path := h.dir + "/adopt.jsonl"
	events, _ := h.machine.Events()
	nextSeq := len(events) // next arbitration_seq
	phantom := fmt.Sprintf(`{"arbitration_seq":%d}`+"\n", nextSeq)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := f.WriteString(phantom); err != nil {
		t.Fatal(err)
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}

	// ASSERTION A: the next Adopt must be rejected (the phantom has a
	// matching seq but is not a machine event)
	if o := h.machine.Adopt(requestFor("op-phantom-eof-2", "er-1", "ev-1", digestHex('c'))); o.Status == "adopted" {
		t.Fatalf("M-1 CONFIRMED (EOF form): phantom with matching seq accepted — "+
			"adopt returned %q; the file is poisoned", o.Status)
	}

	// ASSERTION B (post-fix semantics): a fresh Open must DETECT the damage
	// (fail-closed — the phantom line is a bypass write, not a machine
	// event), and the machine must not have rewritten the file
	if _, err := adopt.Open(path); err == nil {
		t.Fatal("M-1 REGRESSION (EOF form): the poisoned file was silently accepted by a fresh Open")
	}
	after, _ := os.ReadFile(path)
	if !strings.HasSuffix(string(after), phantom) {
		t.Fatal("M-1 (EOF form): the machine rewrote the poisoned file — damaged bytes must be preserved")
	}
}
