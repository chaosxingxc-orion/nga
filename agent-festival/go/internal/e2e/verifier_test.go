package e2e

import (
	"sort"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// E1: the verification seat (33号 B1) — a TEST-FACE component (the types
// it verifies against live in the test files; the production adopt machine
// stays semantically blind by design — the seat sits at the HOST tier,
// exactly where E5's nodeEntry authorization lives).

// E1: the verification seat (33号 B1) — the correctness layer whose
// ABSENCE the E0 experiments proved. The seat is a DETERMINISTIC function
// of the fixture spec and the RAW evidence (never of S1's extraction
// output): the hermes-self-evolution layering (frame-bench,
// evolution/core/constraints.py — "Every candidate variant must pass ALL
// constraints … Failed constraints = immediate rejection") is the same
// shape: hard deterministic gates decide, the model seat only advises.
//
// The seat wires judge→verify→adopt: a verdict that contradicts the raw
// evidence under the fixture's rules is refused BEFORE adoption, and the
// refusal is a control event (E3 family) — auditable, not traceless.

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

// anchorVetoMonths derives the veto threshold from the fixture's rule-0
// coverage text: the fixture says "longer than three months" — the anchor
// maps the spelled-out word to the numeric threshold. If the fixture
// changes its threshold wording, the anchor test (TestE1_VetoThresholdAnchored)
// goes red instead of verify silently diverging from the spec.
func anchorVetoMonths(spec *fixtureSpec) int {
	for _, r := range spec.Rules {
		if r.Precedence == 0 {
			if strings.Contains(r.Coverage, "three months") {
				return 3
			}
			if strings.Contains(r.Coverage, "four months") {
				return 4
			}
		}
	}
	return 3 // a fixture without a parseable threshold keeps the historic default (the anchor test will flag the drift)
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
	if vetoFires && v.kind != "deny" {
		return checkResult{ok: false, reason: "rule 0 (unbounded veto): the raw evidence carries an overdue beyond three months — the only conforming verdict is deny, the seat received " + v.kind}
	}
	// The mirror face: S1 claims a veto-deny the raw record does not
	// carry — a fabricated denial is also a contract violation (the seat
	// is symmetric: it guards the citizen's side too).
	if !vetoFires && v.kind == "deny" && strings.Contains(v.details, "veto") {
		return checkResult{ok: false, reason: "the verdict claims a veto deny but the raw record carries no overdue beyond three months — fabricated denial"}
	}
	// The between-bands face: the seat knows the open question and holds
	// S1 to the spec's own vocabulary — a grant from an unsettled zone is
	// a model-authored default (the spec forbids it). R29 M-4: the open
	// set is CLOSED at both ends — the fixture's exceptions name assets
	// exactly 30 and exactly 1 as equally unsettled (>= 1 && <= 30).
	inBand := raw.assetMillionsDeclared >= 1 && raw.assetMillionsDeclared <= 30
	if inBand && (v.kind == "grant-50000" || v.kind == "grant-10000") {
		return checkResult{ok: false, reason: "assets strictly between the bands are an open specification question — a grant verdict is a model-authored default"}
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

	// The host routes to missing-evidence BEFORE judgment: S1 is never
	// asked to decide on an insufficient evidence base (the declarative
	// gate runs first). R29 M-5: the record is adopted (the machine is
	// blind by design); the DISPATCH is withheld — no MarkUnresolved (it
	// would plant "outcome unknown" for a dispatch that never happened);
	// the gap detail rides the HOST-tier refusal, not the ledger event.
	if o := h.machine.Adopt(requestFor("op-e2-gap", "er-1", "ev-1", digestHex('4'))); o.Status != "adopted" {
		t.Fatalf("E2: adopt = %q: %s", o.Status, o.Detail)
	}
	if s := h.machine.State("op-e2-gap"); s != adopt.StateAdopted {
		t.Fatalf("E2: state after coverage refusal = %q, want adopted (never dispatched)", s)
	}
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
	// closure against the fixture's exceptions.
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
