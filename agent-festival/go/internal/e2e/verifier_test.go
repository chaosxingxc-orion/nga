package e2e

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// E1: the verification seat (33号 B1) — a TEST-FACE component (the types
// it verifies against live in the test files; the production adopt machine
// stays semantically blind by design — the seat sits at the HOST tier,
// exactly where E5's nodeEntry authorization lives). The seat is the
// correctness layer whose ABSENCE the E0 experiments proved: a
// DETERMINISTIC function of the fixture spec and the RAW evidence (never — in THIS wiring —
// of S1's extraction output (the raw/extracted separation is the caller's
// discipline, not a type-level force: rawEvidence can be legally built
// from extracted data — R32 m-5)) — the hermes-self-evolution layering
// (frame-bench, evolution/core/constraints.py — "Every candidate variant
// must pass ALL constraints … Failed constraints = immediate rejection")
// is the same shape: hard deterministic gates decide, the model seat only
// advises. The seat wires judge→verify→adopt: a verdict that contradicts
// the raw evidence under the fixture's rules is refused BEFORE the
// dispatch, and the refusal lives in the host tier's own audit surface.

// rawEvidence is the evidence AS IT EXISTS in the source dossier — the
// ground truth the extraction layer is supposed to carry into S1's input.
// The verification seat reads THIS, not the extracted form: an extraction
// error (the E0 extraction-miss disease) can then never inherit into the
// check.
type rawEvidence struct {
	assetMillionsDeclared float64
	assetReportPresent    bool
	overdueOnRecord       []overdueEvent // the full-history ledger of record
}

// anchorBandBounds derives the open-question band's closed bounds from the
// fixture's rule texts — the NUMBER IS PARSED from the matched text (R33
// M-1: the previous Contains+literal-copy form was blind to digit
// extension, "above 30"→"above 300" matched and kept the stale 30). An
// unparseable bound returns 0 (the fail-closed sentinel: the anchor test
// flags it), never a historic default. R33 m-3 honesty: with bounds (0,0)
// the band face's closed interval [0,0] fires only at assets==0 — the
// "never fires" phrasing was false; the sentinel's real protection is the
// TEST-layer value assertion, not gate inertness.
func anchorBandBounds(spec *fixtureSpec) (float64, float64) {
	var lo, hi float64
	aboveRe := regexp.MustCompile(`above (\d+(?:\.\d+)?)`)
	belowRe := regexp.MustCompile(`below (\d+(?:\.\d+)?)`)
	for _, r := range spec.Rules {
		if m := aboveRe.FindStringSubmatch(r.Coverage); m != nil {
			fmt.Sscanf(m[1], "%g", &hi)
		}
		if m := belowRe.FindStringSubmatch(r.Coverage); m != nil {
			fmt.Sscanf(m[1], "%g", &lo)
		}
	}
	return lo, hi
}

// anchorVetoMonths derives the veto threshold from the fixture's rule-0
// coverage text. R30 M-2: FAIL-CLOSED — an unparseable threshold returns
// 0 (the sentinel: no anchor), NOT the historic default. The old
// fail-open default turned the anchor from a drift detector into a drift
// cover ("six months" → silently kept verifying at 3). verify treats 0 as
// "no anchored threshold" and refuses to gate (refuses OPEN, i.e. fails
// closed for the flow); TestE1_VetoThresholdAnchored asserts both the
// parse and the value.
func anchorVetoMonths(spec *fixtureSpec) int {
	// R31 m-4: a FIXED order slice (map range order is random — a
	// coverage text mentioning two threshold words would 3/6-flip) with
	// FIRST-HIT-wins; "six-month" (hyphenated) does not match "six
	// months" — the fixture's window mention is safe today, and a double
	// hit among the THRESHOLD words stays deterministic (first in this
	// order wins; the anchor test pins the value).
	for _, r := range spec.Rules {
		if r.Precedence == 0 {
			for _, w := range []struct {
				word string
				n    int
			}{{"three", 3}, {"four", 4}, {"five", 5}, {"six", 6}} {
				if strings.Contains(r.Coverage, w.word+" months") {
					return w.n
				}
			}
		}
	}
	return 0 // unparseable — fail-closed sentinel (the anchor test flags it)
}

// checkResult is the verification seat's answer.
type checkResult struct {
	ok     bool
	reason string
}

// verify checks a verdict against the raw evidence under the fixture's
// rules (P3-corrected: the veto is unbounded, "at any time … on record").
// Deterministic: same inputs, same answer, zero model calls.
// R29 M-3: the spec parameter is LOAD-BEARING — the veto threshold is
// anchored to the fixture text via anchorVetoMonths (below), so a fixture
// edit that changes the threshold (e.g. "three" → "four") turns the E1
// anchor test red instead of silently diverging the third leg of the
// three-way agreement.
func verify(v s1Verdict, spec *fixtureSpec, raw rawEvidence) checkResult {
	if spec == nil {
		return checkResult{ok: false, reason: "no specification loaded — refusing to verify against nothing"}
	}
	vetoMonths := anchorVetoMonths(spec)
	if vetoMonths == 0 {
		return checkResult{ok: false, reason: "the fixture's rule-0 threshold is unparseable — the seat refuses to gate on an unanchored spec (fail-closed, R30 M-2)"}
	}
	// R31 M-1: the VOCABULARY gate with NORMALIZATION comes first — a
	// case variant that folds onto a fixture name takes the fixture's
	// canonical form (every semantic face below compares canonical case;
	// EqualFold alone would admit "DENY" into the vocabulary while the
	// faces still compared exact case — the variant was admitted by the
	// gate and exempted by every face). Unknown kinds and the resolution
	// verdicts keep their literal form. R31 m-5: the resolution words are
	// HARDCODED here — uneven vs the levels arm's fixture derivation (the
	// fixture's resolution section is not parsed into fixtureSpec; a
	// rename there drifts silently — the known 0.2.0 face, same family as
	// requiredSources).
	kind := strings.TrimSpace(v.kind)
	inVocabulary := false
	for _, lvl := range spec.Levels {
		if strings.EqualFold(strings.TrimSpace(lvl.Name), kind) {
			kind = strings.TrimSpace(lvl.Name) // the fixture's canonical form
			inVocabulary = true
			break
		}
	}
	for _, res := range []string{"on_undefined_rule", "on_missing_evidence"} {
		if kind == res {
			inVocabulary = true
			break
		}
	}
	if !inVocabulary {
		return checkResult{ok: false, reason: "the verdict kind " + v.kind + " is not in the fixture's verdict vocabulary — not a verdict under this spec"}
	}
	// Rule 0 (the veto, precedence 0): ANY overdue beyond the anchored
	// threshold at any time on record denies — regardless of assets,
	// regardless of what S1 said.
	vetoFires := false
	for _, o := range raw.overdueOnRecord {
		if o.months > vetoMonths {
			vetoFires = true
			break
		}
	}
	if vetoFires && kind != "deny" {
		return checkResult{ok: false, reason: fmt.Sprintf("rule 0 (unbounded veto): the raw evidence carries an overdue beyond %d months (the anchored threshold) — the only conforming verdict is deny, the seat received %q", vetoMonths, v.kind)}
	}
	// The mirror face (R30 M-3 form, R31 M-1 normalized): a deny with no
	// veto behind it is fabricated — rule 0 is the fixture's only deny
	// path, so any deny while the veto is silent contradicts the spec
	// regardless of wording or case.
	if !vetoFires && kind == "deny" {
		return checkResult{ok: false, reason: "the verdict is a deny but the raw record carries no overdue beyond the anchored threshold — rule 0 is the only deny path in this spec, so this deny is fabricated"}
	}
	// R32 M-2: the evidence-presence mirror faces — the fixture's FIRST
	// evidence source (the asset valuation report) must be present for a
	// grant to be honest, and a report that IS present must not be
	// denied-by-evasion. Both directions of the E0 evasive-S1 family.
	if !raw.assetReportPresent && (kind == "grant-50000" || kind == "grant-10000") {
		return checkResult{ok: false, reason: "the asset valuation report (the fixture's first evidence source) is absent — a grant verdict without it is the evasive-S1 form (E0 family)"}
	}
	if raw.assetReportPresent && kind == "on_missing_evidence" {
		return checkResult{ok: false, reason: "the asset valuation report is present but the verdict claims it missing — the spec's resolution scopes on_missing_evidence to the asset report alone (any other gap is the host's pre-judgment coverage route, E2), so this claim is the evasion mirror"}
	}
	// The between-bands face: the seat knows the open question and holds
	// S1 to the spec's own vocabulary — a grant from an unsettled zone is
	// a model-authored default (the spec forbids it). R29 M-4: the open
	// set is CLOSED at both ends (>= 1 && <= 30) — exactly-30 comes from
	// the upper rule's exceptions, exactly-1 from the fixture's examples
	// (R30 m-5: the two edges have DIFFERENT fixture homes).
	// R32 M-3: the band bounds are DERIVED from the fixture (anchorBandBounds)
	// like the veto threshold — a fixture edit that moves a bound turns the
	// anchor test red instead of silently over/under-blocking the seat.
	lo, hi := anchorBandBounds(spec)
	if lo == 0 || hi == 0 {
		return checkResult{ok: false, reason: "the fixture's band bounds are unparseable — the seat refuses to gate on an unanchored spec (fail-closed, R33 m-3: the two anchors now fail at the same depth)"}
	}
	inBand := raw.assetMillionsDeclared >= lo && raw.assetMillionsDeclared <= hi
	if inBand && (kind == "grant-50000" || kind == "grant-10000") {
		return checkResult{ok: false, reason: "assets in the closed between-bands zone (both cutoffs included) are an open specification question — a grant verdict is a model-authored default"}
	}
	return checkResult{ok: true, reason: "verdict conforms to the raw evidence under the corrected spec"}
}

// ---------------------------------------------------------------------------
// E2 (33号 B2): the evidence-coverage gap — the machine face of counterexample
// B ("only six months of material ≠ no long-term overdue in history"). The
// fixture DECLARES which sources the rules require (P3 correction added the
// historical ledger as REQUIRED for the unbounded veto); the input snapshot
// DECLARES which sources are actually present; the DIFFERENCE is a
// declarative missing-evidence routed BEFORE judgment — the same shape as
// evidlog's CheckCoverage (declared footprint vs actual footprint), with
// sources instead of tool calls. Zero new concepts; a same-family
// generalization of an in-repo precedent.

// requiredSources are the fixture's evidence_sources minus the
// demonstration-assumption bracket — the semantic key of each source line
// maps to a structured requirement. (The fixture prose is human-facing;
// this table is its machine projection — kept adjacent to the fixture
// reader so a fixture edit that adds a source surfaces here.)
// R29 m-4 honesty: this is a HOST-side projection table, NOT mechanically
// derived from the fixture prose (the map values were dead weight and are
// gone) — a fixture edit does NOT surface here automatically; the
// THRESHOLD face is anchored (TestE1_VetoThresholdAnchored), and the
// source-list face's anchor is a known gap for the 0.2.0 input-snapshot
// schema (33号 B2's 产物面), not this fixture.
var requiredSources = []string{
	"asset report",
	"historical ledger",
}

// coverageGap returns the required sources NOT present in the input
// snapshot (deterministic: sorted keys — langgraph _algo.py ordering
// discipline). Empty = the evidence base is sufficient (positive path).
func coverageGap(presentSources []string) []string {
	present := map[string]bool{}
	for _, s := range presentSources {
		present[s] = true
	}
	var missing []string
	keys := make([]string, len(requiredSources))
	copy(keys, requiredSources)
	sort.Strings(keys)
	for _, k := range keys {
		if !present[k] {
			missing = append(missing, k)
		}
	}
	return missing
}

// TestE2_CoverageGapBlocksCounterexampleB is the E2 experiment: the
// counterexample-B input (only the six-month window ledger present — the
// historical ledger missing) is routed to missing-evidence BEFORE the
// judgment runs. Mutation probe: remove the coverage check from the host
// flow below and the wrong grant flows (red).
func TestE2_CoverageGapBlocksCounterexampleB(t *testing.T) {
	h := newTask(t)

	// The input snapshot DECLARES its sources: only the recent-window
	// ledger is present. The historical ledger — REQUIRED by the
	// unbounded veto — is absent. This is exactly counterexample B's
	// shape: "we checked the last six months and found nothing" is not
	// evidence about year-old records.
	presentSources := []string{"asset report", "recent-window ledger"}
	gap := coverageGap(presentSources)
	if len(gap) == 0 {
		t.Fatal("E2: no coverage gap detected — the historical ledger is REQUIRED by the unbounded veto and must be flagged missing")
	}
	foundHistorical := false
	for _, g := range gap {
		if g == "historical ledger" {
			foundHistorical = true
		}
	}
	if !foundHistorical {
		t.Fatalf("E2: gap = %v, want it to name the historical ledger", gap)
	}

	// R30 M-1: the interception is a REAL conditional flow — the host's
	// dispatch decision is gated ON the gap (empty gap → judge/adopt/
	// dispatch/submit; non-empty → withhold). With the gate in place the
	// counterexample-B flow never reaches the API; with the gate removed
	// (mutation) the flow runs to completion and the assertions below go
	// red — the interception has behavioral mass, not just a unit check.
	if len(coverageGap(presentSources)) == 0 {
		// the gate-free path: judge, adopt, dispatch, submit
		v := h.judge(creditEvidence{assetMillions: 35, assetReportOK: true})
		_ = v
		if o := h.machine.Adopt(requestFor("op-e2-gap", "er-1", "ev-1", digestHex('4'))); o.Status != "adopted" {
			t.Fatalf("E2: adopt = %q: %s", o.Status, o.Detail)
		}
		if o := h.machine.Dispatch("op-e2-gap", chainGrants()); o.Status != "dispatched" {
			t.Fatalf("E2: dispatch = %q: %s", o.Status, o.Detail)
		}
		h.submit("op-e2-gap")
		if o := h.machine.MarkCompleted("op-e2-gap"); o.Status != "completed" {
			t.Fatalf("E2: complete = %q: %s", o.Status, o.Detail)
		}
	} else {
		// the gated path: the record is adopted (the machine is blind by
		// design — R29 M-5), the DISPATCH is withheld (no false unresolved
		// fact), the gap detail rides the HOST-tier refusal
		if o := h.machine.Adopt(requestFor("op-e2-gap", "er-1", "ev-1", digestHex('4'))); o.Status != "adopted" {
			t.Fatalf("E2: adopt = %q: %s", o.Status, o.Detail)
		}
		if st := h.machine.State("op-e2-gap"); st != adopt.StateAdopted {
			t.Fatalf("E2: state after coverage refusal = %q, want adopted (never dispatched)", st)
		}
	}
	// behavioral assertions (both faces): the gated flow shows zero API
	// calls and zero dispatch/completed events; under the mutation the
	// gate-free branch runs and these go red.
	if h.calls.bankAPI != 0 {
		t.Fatalf("E2: the business API was called %d times — counterexample B's insufficient evidence reached execution", h.calls.bankAPI)
	}
	events, _ := h.machine.Events()
	for _, ev := range events {
		if ev.Outcome.Status == "dispatched" || ev.Outcome.Status == "completed" {
			t.Fatalf("E2: found a %q event — counterexample B's insufficient evidence reached execution", ev.Outcome.Status)
		}
	}

	// Positive control: a COMPLETE evidence base has an empty gap — the
	// gate does not damage healthy flows.
	full := coverageGap([]string{"asset report", "historical ledger"})
	if len(full) != 0 {
		t.Fatalf("E2 positive control: complete base flagged gaps %v — the gate over-blocks", full)
	}
}

// ---------------------------------------------------------------------------
// E5 (33号 B5): the read-authorization VARIANTS — the D-04 gap's acceptance
// face, built on the T2 nodeEntry the first batch landed (L39). The plain
// L39 form covers empty-vs-nonempty grants; the variants here cover the
// DOWNGRADED form (a caller whose grants were narrowed after the result
// was stored) and the pin the host-tier boundary: the machine's State()
// serves any caller (semantic blindness by design); the HOST's entry is
// where authorization lives.

// TestE5_ReadAuthorizationVariants drives the three authorization shapes
// through nodeEntry: authorized read serves, empty-grants read refuses,
// and a DOWNGRADED (narrowed) grant set refuses too — the caller who could
// read at store time but cannot at read time is the D-04 form. Mutation
// probe: change nodeEntry's check from "any grants" to "any caller" and
// both refusal shapes serve (red).
func TestE5_ReadAuthorizationVariants(t *testing.T) {
	h := newT2Host(t, t.TempDir())

	// store a result the ordinary way
	if o := h.adoptAndDispatch("op-e5", "er-1", "ev-1", t2Digest('a'), "br-e5", "receipt:op-e5:accepted", nil); o.Status != "dispatched" {
		t.Fatalf("E5: adoptAndDispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h.completeNode("op-e5"); o.Status != "completed" {
		t.Fatalf("E5: complete = %q: %s", o.Status, o.Detail)
	}

	// ① authorized caller: served
	if served, err := h.nodeEntry("op-e5", chainGrants()); err != nil {
		t.Fatalf("E5: authorized read failed: %v", err)
	} else if served.Receipt != "receipt:op-e5:accepted" {
		t.Fatalf("E5: authorized receipt = %q", served.Receipt)
	}

	// ② empty grants: refused
	if _, err := h.nodeEntry("op-e5", nil); err == nil {
		t.Fatal("E5: empty-grants read was served — the host authorization boundary is gone")
	}

	// ③ DOWNGRADED grants (narrowed after store time): refused. The D-04
	// form — "the consumer's channel visibility was reduced; can it still
	// read the completed result?" — must be refused by the same gate.
	// The downgrade narrows the data-read's SELECTOR (the caller's channel
	// was cut back to a different subtree — the result's selector is no
	// longer in its visibility): same grant count, same kinds, different
	// reach.
	downgraded := []ledger.Grant{
		{Kind: "data", Selector: "ledger://credit/other-subtree", Actions: []string{"read"}, Effect: "none"},
		{Kind: "tool", Selector: "tool://credit-transfer", Actions: []string{"execute"}, Effect: "irreversible"},
	}
	if _, err := h.nodeEntry("op-e5", downgraded); err == nil {
		t.Fatal("E5: downgraded-grants read was served — the D-04 form (channel visibility narrowed away from the result's selector) is not covered by the host gate")
	}

	// the machine-side boundary statement: State() has no authorization
	// gate (D-04 acknowledged, F-C 分叉裁定) — pinned so the host-tier
	// placement of the gate stays honest
	if s := h.machine.State("op-e5"); s != adopt.StateCompleted {
		t.Fatalf("E5: machine State from an unauthorized context = %q — the machine stays blind (the gate is the host's, pinned by design)", s)
	}
}

// TestE1_VetoThresholdAnchored is the R29 M-3 anchor: verify's threshold
// must be DERIVED from the fixture, not hardcoded next to it. Mutation
// probe: edit the fixture's rule-0 coverage threshold ("three months" →
// "four months") and this test goes red — the three-way agreement's third
// leg (the seat) can no longer silently diverge from the other two.
func TestE1_VetoThresholdAnchored(t *testing.T) {
	spec := loadE3Fixture(t)
	if got := anchorVetoMonths(spec); got != 3 {
		t.Fatalf("E1 anchor: veto threshold = %d, want 3 (from the fixture's 'three months') — the fixture wording and the seat have drifted", got)
	}
	// behavioral face: a 4-month overdue sits exactly on the anchored
	// boundary — verify must refuse a grant verdict against it
	raw := rawEvidence{
		assetMillionsDeclared: 35,
		assetReportPresent:    true,
		overdueOnRecord:       []overdueEvent{{months: 4, yearsAgo: 2}},
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "sick"}, spec, raw)
	if cr.ok {
		t.Fatal("E1 anchor: a grant verdict passed against a 4-month overdue — the anchored veto is not load-bearing")
	}
}

// TestE1_MirrorAndBandFaces is the R29 M-4 probe: the two faces that were
// defined but never asserted get their red probes — deleting either face's
// code now turns this test red instead of silently decorating.
func TestE1_MirrorAndBandFaces(t *testing.T) {
	spec := loadE3Fixture(t)

	// face ① mirror (fabricated deny): the raw record is CLEAN but the
	// verdict claims a veto deny — refused. Mutation probe: delete the
	// mirror-face block in verify() and this case passes silently (red).
	rawClean := rawEvidence{
		assetMillionsDeclared: 35,
		assetReportPresent:    true,
		overdueOnRecord:       nil,
	}
	fabricated := verify(s1Verdict{kind: "deny", details: "historical veto: fabricated record"}, spec, rawClean)
	if fabricated.ok {
		t.Fatal("E1 mirror: a fabricated veto-deny passed — the citizen-side face is not load-bearing")
	}

	// face ② between-bands (open question → grant): refused at BOTH open
	// edges. Mutation probe: delete the band-face block and these pass
	// (red); the closed edges (exactly 1, exactly 30) pin the R29 M-4
	// closure (exactly-30 = rule-1 exception; exactly-1 = fixture example).
	for _, assets := range []float64{12, 1, 30} {
		rawBand := rawEvidence{
			assetMillionsDeclared: assets,
			assetReportPresent:    true,
			overdueOnRecord:       nil,
		}
		cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, spec, rawBand)
		if cr.ok {
			t.Fatalf("E1 band: a grant verdict passed at assets=%v — an open-question zone produced a grant (model-authored default)", assets)
		}
	}

	// positive control: the band face does not block a verdict the spec
	// leaves open (on_undefined_rule from the open zone is conforming)
	rawOpen := rawEvidence{assetMillionsDeclared: 12, assetReportPresent: true}
	open := verify(s1Verdict{kind: "on_undefined_rule", details: "between bands — owner question"}, spec, rawOpen)
	if !open.ok {
		t.Fatalf("E1 band: an on_undefined_rule verdict was refused (%s) — the seat over-blocks the spec's own vocabulary", open.reason)
	}
}

// TestE1_CaseVariantsRefused is the R31 M-1 direct probe — the probe the
// R30 M-3 ledger entry CLAIMED existed ("直检探针：变体必拒") but didn't.
// Case variants must be refused exactly like their canonical forms: the
// vocabulary gate normalizes them, so every semantic face sees the
// canonical kind. Mutation probe: remove the normalization assignment
// (kind = lvl.Name) and "DENY" on a clean record passes (red).
func TestE1_CaseVariantsRefused(t *testing.T) {
	spec := loadE3Fixture(t)

	// "DENY" on a clean record = fabricated deny in variant case — refused
	rawClean := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "DENY", details: "fabricated in caps"}, spec, rawClean); cr.ok {
		t.Fatal("M-1 probe: DENY on a clean record was served — the variant escaped the mirror face (normalization not load-bearing)")
	}
	// "GRANT-50000" in the open band — refused
	rawBand := rawEvidence{assetMillionsDeclared: 12, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "GRANT-50000", details: "variant grant"}, spec, rawBand); cr.ok {
		t.Fatal("M-1 probe: GRANT-50000 in the open band was served — the variant escaped the band face")
	}
	// the variant honored as a REAL deny when the veto fires (the seat
	// accepts the normalized form's verdict — normalization is symmetric)
	rawVeto := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}}
	if cr := verify(s1Verdict{kind: "DENY", details: "real veto in caps"}, spec, rawVeto); !cr.ok {
		t.Fatalf("M-1 probe: a variant-case REAL deny was refused (%s) — normalization broke the happy path", cr.reason)
	}
}

// TestE1_FailClosedAnchored is the R32 M-1 probe: the fail-closed faces
// R30 M-2 introduced had ZERO probes (deleting them or reverting the
// sentinel kept all 13 tests green — decorative guards by this repo's own
// R29 M-4 standard). Pinned now: an unparseable spec yields sentinel 0
// from the anchor, verify refuses to gate on it, and a nil spec refuses
// outright. Mutation probe: revert anchorVetoMonths's fallback to `return
// 3` (the R30 M-2 disease) or delete the vetoMonths==0 face — this goes red.
func TestE1_FailClosedAnchored(t *testing.T) {
	// ① unparseable threshold → sentinel 0 → verify refuses
	broken := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "denies credit for overdue records"}}}
	if got := anchorVetoMonths(broken); got != 0 {
		t.Fatalf("M-1 probe: unparseable threshold anchored = %d, want 0 (fail-closed sentinel)", got)
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, broken, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok {
		t.Fatal("M-1 probe: verify gated on an unanchored spec — the fail-closed face is not load-bearing")
	}
	if !strings.Contains(cr.reason, "unparseable") {
		t.Fatalf("M-1 probe: refusal reason = %q, want the unparseable marker", cr.reason)
	}

	// ② nil spec → outright refusal
	cr = verify(s1Verdict{kind: "grant-50000", details: "healthy"}, nil, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok || !strings.Contains(cr.reason, "no specification") {
		t.Fatalf("M-1 probe: nil spec = %+v, want refusal with the no-specification marker", cr)
	}
}

// TestE1_EvidencePresenceMirror is the R32 M-2 probe: both directions of
// the evidence-presence face. Mutation probes: delete either new face in
// verify() and the matching case passes silently (red).
func TestE1_EvidencePresenceMirror(t *testing.T) {
	spec := loadE3Fixture(t)

	// ① no report + a grant → refused (the evasive-S1 grant form)
	rawNoReport := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: false}
	if cr := verify(s1Verdict{kind: "grant-50000", details: "grant without a report"}, spec, rawNoReport); cr.ok {
		t.Fatal("M-2 probe: a grant verdict passed with the asset report absent — the evasive-S1 grant form is not intercepted")
	}
	// ② report present + on_missing_evidence → refused (the evasion mirror)
	rawPresent := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "on_missing_evidence", details: "claiming a gap that does not exist"}, spec, rawPresent); cr.ok {
		t.Fatal("M-2 probe: on_missing_evidence passed with the report present — the evasion mirror is not intercepted")
	}
	// positive control: an on_missing_evidence verdict with the report
	// genuinely ABSENT passes (the honest gap form)
	rawHonestGap := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: false}
	if cr := verify(s1Verdict{kind: "on_missing_evidence", details: "the report could not be retrieved"}, spec, rawHonestGap); !cr.ok {
		t.Fatalf("M-2 probe: an HONEST missing-evidence verdict was refused (%s) — the new faces over-block", cr.reason)
	}
}

// TestE1_BandBoundsAnchored is the R32 M-3 anchor: the between-bands face's
// bounds must be DERIVED from the fixture's rule texts. Mutation probe:
// change the fixture's rule-1 "above 30" to "above 50" and this goes red —
// the seat can no longer silently over-block grants the spec allows.
func TestE1_BandBoundsAnchored(t *testing.T) {
	spec := loadE3Fixture(t)
	lo, hi := anchorBandBounds(spec)
	if lo != 1 || hi != 30 {
		t.Fatalf("M-3 anchor: band bounds = (%v, %v), want (1, 30) from the fixture's rule texts — the fixture and the seat have drifted", lo, hi)
	}
	// behavioral face: the anchor actually drives the band face — a grant
	// verdict at assets=31 passes because inBand uses the DERIVED hi (31 >
	// 30), not a second hardcoded copy; this catches a verify-side
	// constant that forks from the anchor (R33 m-1: the earlier "the
	// hardcoded 30 would have blocked 31" history claim was false — every
	// prior form passed 31; the probe's real catch is the fork)
	raw := rawEvidence{assetMillionsDeclared: 31, assetReportPresent: true}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy upper-band grant"}, spec, raw)
	if !cr.ok {
		t.Fatalf("M-3 anchor: a grant at assets=31 was refused (%s) — the band face is not anchored to the fixture's 30", cr.reason)
	}
}
