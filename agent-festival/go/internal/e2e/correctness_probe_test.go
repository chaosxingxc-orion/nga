package e2e

// E0/E3: correctness-layer experiments from the synthesized verification plan
// (29-reconciliation §3.2). These are the zero-LLM, immediately-runnable
// experiments that test whether xingchao's "consistent but wrong" critique
// (198232012) identifies a real structural hole in our architecture.
//
// E1 flipped the E0 polarity (this batch): the verification seat now sits
// judge→verify→adopt, and the former disease tests assert the
// INTERCEPTION (coupled to verify's ANSWER — a seat that returns ok turns
// them red; the conditional-flow face is TestE2's). The disease's
// existence is historical record: a "sick" S1 used to pass the adoption
// gate undetected (WGR 1/1), and E3 proved the spec self-contradiction
// that P3+L23 resolved.
//
// The experiments were framed as conclusion-changing probes (the user's
// instruction: "有可能会通过实验验证或者改变我们的结论"). Both concluded:
// the structural-blindness claim held (E0 era) and was then ANSWERED by
// the E1 verification seat; the E3 contradiction resolved once P3+L23
// landed. Nothing in this file asserts a pending state.
//
// (The R11-era POLARITY GUARD instruction is RETIRED: the flip this block
// demanded happened in this batch — the rewritten tests assert the
// blocking, mutation-coupled, no skip guards survive.)

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
)

// correctnessLayerLanded was retired in E1 (the R20 B-1 discipline): the
// E0-sick tests were REWRITTEN to assert the blocking state in the same
// commit the verification seat landed — no skip guards survive to turn
// the rewritten assertions into dead code. The rewritten tests are
// mutation-coupled: removing the verify gate from the harness turns the
// sick-chain test red (the grant flows through again).

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

// TestE1_PositiveControlHealthyS1 is the positive control: the healthy S1
// correctly denies the counterexample evidence (4-month overdue 2 years ago).
// This must pass, proving the test harness works. If this fails, E0's
// negative result is meaningless.
func TestE1_PositiveControlHealthyS1(t *testing.T) {
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
	// E1 positive control: the CORRECT deny also passes the verification
	// seat (the seat guards against wrong grants, not against denies —
	// a healthy flow must not be damaged by the new gate).
	cr := verify(v, loadE3Fixture(t), rawEvidence{
		assetMillionsDeclared: float64(e.assetMillions),
		assetReportPresent:    e.assetReportOK,
		overdueOnRecord:       e.overdueOnRecord,
	})
	if !cr.ok {
		t.Fatalf("E1 positive control: the seat REFUSED a correct deny (%s) — the gate damages healthy flows", cr.reason)
	}
	// the deny record is adopted (decision record) — the machine CAN dispatch
	// it (it doesn't know it's a "deny" — this IS the structural blindness
	// E0 proves), but the HOST chooses not to. We verify the healthy S1
	// verdict is correct, not that the machine blocks it.
	if o := h.machine.Adopt(requestFor("op-e0-healthy", "er-1", "ev-1", digestHex('1'))); o.Status != "adopted" {
		t.Fatalf("E0 positive control: adopt = %q: %s", o.Status, o.Detail)
	}
	// This test DELIBERATELY dispatches the deny record to prove the
	// machine's semantic blindness (it has no verdict field); a PRODUCTION
	// host withholds dispatch on a deny — the distinction matters and the
	// dispatch here is the demonstration, not a policy (R32 m-6: the old
	// comment claimed the host decides not to dispatch, contradicting the
	// dispatch two lines below).
	if o := h.machine.Dispatch("op-e0-healthy", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("E0 positive control: dispatch on deny record = %q — expected dispatched "+
			"(machine is semantically blind by design; the dispatch here is the demonstration, not a policy)", o.Status)
	}
}

// (Historical doc, E0 era: this test asserted the disease — the sick S1
// passing adopt→dispatch→API→completed with zero resistance, WGR 1/1.
// E1 flipped the polarity: the verification seat now sits judge→verify→
// adopt and the test asserts the INTERCEPTION — see the rewritten body.)
func TestE1_BlocksSickS1(t *testing.T) {
	// E1 flipped the polarity (33号 B1): the verification seat is in the
	// chain, so the sick grant is BLOCKED — this test now asserts the
	// interception, not the disease. The seat's mutation coupling is the
	// DIRECT assertion on verify's answer (a seat returning ok for the
	// sick verdict turns this red); the conditional-flow face with full
	// behavioral mass lives in TestE2 (R30 M-1). R31 m-2: the earlier
	// "remove the verify call and the grant flows" narrative was false —
	// this test's remaining assertions are unconditional and cannot
	// detect a deleted call.
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

	// THE EXPERIMENT (E1, polarity flipped): the verification seat sits
	// between the verdict and the adoption — judge → verify → adopt. The
	// raw evidence carries the 4-month overdue; the sick verdict says
	// grant; the seat must refuse BEFORE adoption.
	raw := rawEvidence{
		assetMillionsDeclared: 35,
		assetReportPresent:    true,
		overdueOnRecord:       e.overdueOnRecord,
	}
	spec := loadE3Fixture(t)
	cr := verify(v, spec, raw)
	if cr.ok {
		t.Fatal("E1: the verification seat PASSED the sick grant — the seat is not load-bearing (the disease is back); verify() is broken or bypassed")
	}
	if !strings.Contains(cr.reason, "rule 0") {
		t.Fatalf("E1: seat rejection reason = %q, want the rule-0 (unbounded veto) marker", cr.reason)
	}

	// The record IS adopted (the machine stays semantically blind by
	// design — R29 M-5 honesty fix: the previous comment claimed "nothing
	// was adopted", which contradicted the Adopt call below; the truth is
	// the DECISION RECORD enters the machine, the DISPATCH is what the
	// host withholds).
	if o := h.machine.Adopt(requestFor("op-e0-sick", "er-1", "ev-1", digestHex('2'))); o.Status != "adopted" {
		t.Fatalf("E1: adopt = %q: %s — unexpected: the machine refused on its own (it must stay blind; the HOST is the correctness seat)", o.Status, o.Detail)
	}
	// The host checks the seat result before dispatching. It does NOT
	// call MarkUnresolved for a seat refusal: unresolved asserts "a
	// dispatch attempt happened whose outcome is unknown" (the machine's
	// own contract) — no attempt happened here, so writing unresolved
	// would plant a FALSE reconciliation fact (a reconciler could legally
	// look for an external effect that never existed). The host's refusal
	// fact lives at the host tier; the operation simply stays adopted
	// with no dispatch (the ledger truth: adopted, never dispatched).
	// (cr.ok is already excluded above — the state check is unconditional.)
	if s := h.machine.State("op-e0-sick"); s != adopt.StateAdopted {
		t.Fatalf("E1: state after seat refusal = %q, want adopted (parked, never dispatched — no false unresolved fact)", s)
	}

	// Zero external effect: the API counter is zero BY CONSTRUCTION in
	// this flow (no submit path exists below the refusal — R30 m-3
	// honesty: the counter adds no independent evidence here; the
	// conditional-flow face with real counter evidence is TestE2).
	if h.calls.bankAPI != 0 {
		t.Fatalf("E1: the business API was called %d times — the sick verdict reached execution despite the seat refusal", h.calls.bankAPI)
	}
	events, _ := h.machine.Events()
	for _, ev := range events {
		if ev.Outcome.Status == "dispatched" || ev.Outcome.Status == "completed" {
			t.Fatalf("E1: found a %q event — the sick verdict reached execution despite the seat refusal", ev.Outcome.Status)
		}
	}
}

// loadE3Fixture parses the credit fixture for the verification seat (the
// same file the E3 tests read — one spec, all seats).
func loadE3Fixture(t *testing.T) *fixtureSpec {
	t.Helper()
	fixturePath := filepath.Join("..", "..", "..", "schema", "examples", "judgment", "valid", "judgment-spec-credit.json")
	raw, err := os.ReadFile(fixturePath)
	if err != nil {
		t.Fatalf("E1: fixture not found (an in-repo required resource): %v", err)
	}
	var spec fixtureSpec
	if err := json.Unmarshal(raw, &spec); err != nil {
		t.Fatalf("E1: fixture parse failed: %v", err)
	}
	return &spec
}

// (Historical doc, E0 era: this test asserted the extraction error
// propagating undetected — the 27-blank-collision "independence trap":
// a verifier consuming the SAME extracted input would inherit the error.
// E1's answer: the seat reads the RAW dossier, so the trap is dead —
// asserted below.)
func TestE1_SeatKillsExtractionInheritance(t *testing.T) {
	// E1's extraction arm (33号 B1 step 6): the extraction layer drops the
	// overdue, S1 sees a clean record and grants — but the seat reads the
	// RAW evidence, so the extraction error does NOT inherit into the
	// check. The interception is the answer to "can any layer catch
	// evidence was there but the input lost it": yes — the seat, because
	// it never reads the extracted form.
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

	// The seat verifies the sick verdict against the RAW record (not the
	// extracted one): the overdue the extraction dropped is still in the
	// raw ledger, so the grant is refused — the inheritance is killed.
	raw := rawEvidence{
		assetMillionsDeclared: float64(realEvidence.assetMillions),
		assetReportPresent:    realEvidence.assetReportOK,
		overdueOnRecord:       realEvidence.overdueOnRecord, // the RAW fact the extraction missed
	}
	spec := loadE3Fixture(t)
	cr := verify(v, spec, raw)
	if cr.ok {
		t.Fatal("E1: the seat PASSED a verdict built on dropped evidence — the extraction error inherited into the check (the seat must read RAW, never the extracted form)")
	}
	if !strings.Contains(cr.reason, "rule 0") {
		t.Fatalf("E1: seat rejection reason = %q, want the rule-0 marker", cr.reason)
	}
	// Same host-tier discipline as the sick arm (R29 M-5): the record is
	// adopted, the DISPATCH is withheld (no false unresolved fact); the
	// counter is zero by construction (R30 m-3).
	if o := h.machine.Adopt(requestFor("op-e0-extract", "er-1", "ev-1", digestHex('3'))); o.Status != "adopted" {
		t.Fatalf("E1: adopt = %q: %s", o.Status, o.Detail)
	}
	if s := h.machine.State("op-e0-extract"); s != adopt.StateAdopted {
		t.Fatalf("E1: state after seat refusal = %q, want adopted (never dispatched)", s)
	}
	if h.calls.bankAPI != 0 {
		t.Fatalf("E1: the business API was called %d times — the extraction-miss grant reached execution", h.calls.bankAPI)
	}
	events, _ := h.machine.Events()
	for _, ev := range events {
		if ev.Outcome.Status == "dispatched" || ev.Outcome.Status == "completed" {
			t.Fatalf("E1: found a %q event — the extraction-miss grant reached execution", ev.Outcome.Status)
		}
	}
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

type fixtureLevel struct {
	Name string `json:"name"`
}

type fixtureSpec struct {
	Conventions struct {
		TimeWindow string `json:"time_window"`
	} `json:"conventions"`
	Rules  []fixtureVetoRule `json:"rules"`
	Levels []fixtureLevel    `json:"levels"` // R30 M-3: the verdict vocabulary (the word-list gate's source)
}

// countPrecedenceZero counts rules at precedence 0 — the veto layer must
// be unique (R25 m-3: ambiguous precedence-0 is a conflict, not a
// silently resolved array order).
func countPrecedenceZero(rules []fixtureVetoRule) int {
	n := 0
	for _, r := range rules {
		if r.Precedence == 0 {
			n++
		}
	}
	return n
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
	// R33 m-7: the fixture load goes through loadE3Fixture (one spec, all
	// seats — the previously duplicated inline parse is gone; the
	// R21 M-3 fail-not-skip discipline lives in the helper).
	spec := loadE3Fixture(t)

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
	// R25 m-3: precedence 0 is unique in the FIXTURE half too — a second
	// rule relabeled precedence 0 (ambiguous precedence conflict) must
	// not pass silently while the first-in-array rule keeps all other
	// assertions green (the t1Spec half has had this count since R24 m-1)
	if n := countPrecedenceZero(spec.Rules); n != 1 {
		t.Fatalf("E3: fixture contains %d precedence-0 rules, want exactly 1 (the veto) — ambiguous precedence is a conflict, not a silently resolved order", n)
	}

	// ASSERTION 1: The fixture's veto is NOW unbounded (P3 correction landed)
	// — it must NOT contain the old "in the window" window-scoping
	if strings.Contains(vetoRule.Coverage, "in the window denies") {
		t.Fatalf("E3: fixture veto still window-scoped (%q) — P3 correction NOT landed", vetoRule.Coverage)
	}
	if !strings.Contains(vetoRule.Coverage, "at any time") {
		t.Fatalf("E3: fixture veto coverage = %q — expected 'at any time' (unbounded, P3 corrected)", vetoRule.Coverage)
	}
	// R26 m-3: the fixture half is POLARITY-PINNED too — the coverage's
	// parenthetical negation must be present verbatim (flipping its "NOT"
	// would re-window the veto in the prose while "at any time" stays,
	// silently breaking the three-way agreement this file asserts)
	collapsedCoverage := strings.Join(strings.Fields(vetoRule.Coverage), " ")
	if !strings.Contains(collapsedCoverage, "NOT limited to the six-month window") {
		t.Fatalf("E3: fixture veto coverage negation is gone or polarity-flipped — 'NOT limited to the six-month window' must be present verbatim: %q", vetoRule.Coverage)
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
	// R25 m-2: the marker is POLARITY-PINNED — the negation itself must
	// be present (deleting the "NOT" re-windows the veto while the bare
	// "limited to any recent window" substring stays green)
	collapsedSpec := strings.Join(strings.Fields(t1Spec), " ")
	if !strings.Contains(collapsedSpec, "NOT limited to any recent window") {
		t.Fatal("E3: t1Spec's veto negation is gone or polarity-flipped — the no-window declaration 'NOT limited to any recent window' is no longer present verbatim")
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

	// R27 m-1 + R28 m-2: the veto's priority over EVERY asset branch is
	// behaviorally pinned — four branch-order faces, four drive shapes:
	//   veto > missing-evidence (C8 shape, above)
	//   veto > upper band      (35M+overdue, the T0 drive points)
	//   veto > lower band      (C12 shape below)
	//   veto > between-bands   (12M+overdue below — a middle-band
	//                           applicant with a historical overdue is
	//                           deny, NOT on_undefined_rule)
	// Mutation probes: move ANY asset branch (or insert an explicit
	// between-bands early return) before the veto loop and the matching
	// shape below goes red.
	c12e := creditEvidence{
		assetMillions:   0, // below the lower cutoff
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 5, yearsAgo: 2}},
	}
	if v := s1Judge(c12e); v.kind != "deny" {
		t.Fatalf("E3-C8: T0 s1Judge returned %q for the C12 shape (lower band + historical overdue), want deny — the veto must fire before the lower-band branch", v.kind)
	}
	betweenBands := creditEvidence{
		assetMillions:   12, // strictly between the bands (1 < x < 30)
		assetReportOK:   true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}},
	}
	if v := s1Judge(betweenBands); v.kind != "deny" {
		t.Fatalf("E3-C8: T0 s1Judge returned %q for the between-bands shape (12M + historical overdue), want deny — the veto must fire before the between-bands default branch (rule 0: 'denies credit regardless of assets')", v.kind)
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
	// R27 m-3: the veto-first markers "Precedence 0" and "ANY overdue" are
	// pinned by the contiguous and count assertions below (which imply
	// them); the only independent marker left here is the
	// regardless-of-assets clause
	t1SpecContainsVetoFirst := strings.Contains(t1Spec, "regardless of assets")

	if !t1SpecContainsVetoFirst {
		t.Fatal("E3-C8: T1 spec text no longer contains 'regardless of assets' — spec may have changed")
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
	c12Found := false
	for _, c := range t1Cases {
		if c.id == "C8-veto-beats-missing-evidence" {
			c8Found = true
			if c.expected != "deny" || !c.hardBar {
				t.Fatalf("E3-C8: t1Cases C8 entry = (expected=%q, hardBar=%v), want (deny, true) — the T1 half of the resolved state", c.expected, c.hardBar)
			}
		}
		// R26 m-6: the C12 sister claim (s1Judge's L23 comment cites BOTH
		// C8 and C12 as hardBar deny) is asserted too — not just narrated
		if c.id == "C12-veto-beats-lower-band" {
			c12Found = true
			if c.expected != "deny" || !c.hardBar {
				t.Fatalf("E3-C8: t1Cases C12 entry = (expected=%q, hardBar=%v), want (deny, true) — the T1 half of the resolved state (cited by the L23 comment)", c.expected, c.hardBar)
			}
		}
	}
	if !c8Found {
		t.Fatal("E3-C8: t1Cases has no C8-veto-beats-missing-evidence entry — the case table changed")
	}
	if !c12Found {
		t.Fatal("E3-C8: t1Cases has no C12-veto-beats-lower-band entry — the case table changed")
	}
}

// TestE0_PhantomJSONMidFileCaught is R14' M-1's deterministic probe (two
// assertions, one run): a "legal JSON object, not a machine event" line
// ({"note":"out-of-band"}) inserted mid-file between two real machine
// writes must be caught by the append-path write-time re-check. State
// since the R14' fix: ParseLines' strict shape judgment REJECTS the
// phantom (valid JSON but not an event), the append refuses ("ledger
// append failed"), and the operation stays adopted — the file is not
// poisoned. The test name says the catch; the assertions verify it.
// (R35 m-3: formerly named TestE0DiseaseExists_* with a "Current state:
// accepts the phantom" narrative that predated the R14' fix.)
func TestE0_PhantomJSONMidFileCaught(t *testing.T) {
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

// TestE0_PhantomJSONEOFCaught is M-1's sister probe (EOF form):
// a phantom line appended at EOF with a MATCHING seq passes both the
// torn check (it has a newline) and the STALE_WRITER check (seq == last+1
// coincidentally), gets persisted, and poisons the file.
func TestE0_PhantomJSONEOFCaught(t *testing.T) {
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
