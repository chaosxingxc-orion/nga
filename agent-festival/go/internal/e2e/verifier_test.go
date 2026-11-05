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
	// R34 m-1: a digit run followed by a comma/digit means a GROUPED
	// number ("30,000") — the capture would be a prefix (30), so any such
	// match poisons the bound (sentinel 0) instead of silently parsing
	// the prefix. Sscanf errors are surfaced (a partial parse is a
	// sentinel, not a stale value).
	aboveRe := regexp.MustCompile(`above (\d+(?:\.\d+)?)([,.]\d)?`)
	belowRe := regexp.MustCompile(`below (\d+(?:\.\d+)?)([,.]\d)?`)
	// R34 m-2: MULTIPLE hits for the same face are a CONFLICT, not a
	// silently-resolved array order (the countPrecedenceZero discipline —
	// ambiguous derivation refuses). First hit wins only within ONE rule;
	// a second rule deriving the same face with a different value is
	// ambiguous → sentinel.
	for _, r := range spec.Rules {
		if m := aboveRe.FindStringSubmatch(r.Coverage); m != nil {
			if m[2] != "" {
				return 0, 0 // grouped/poisoned form — fail closed
			}
			var v float64
			if _, err := fmt.Sscanf(m[1], "%g", &v); err != nil {
				return 0, 0
			}
			if hi != 0 && hi != v {
				return 0, 0 // two rules derive different "above" bounds — ambiguous
			}
			hi = v
		}
		if m := belowRe.FindStringSubmatch(r.Coverage); m != nil {
			if m[2] != "" {
				return 0, 0
			}
			var v float64
			if _, err := fmt.Sscanf(m[1], "%g", &v); err != nil {
				return 0, 0
			}
			if lo != 0 && lo != v {
				return 0, 0
			}
			lo = v
		}
	}
	// R35 m-2: an INVERTED interval (lo > hi — both parsed but the text
	// contradicts itself) is neither unparseable nor multi-hit — it is
	// the third fail-open form: inBand would be vacuously false and the
	// band face silently inert. Refuse it like the others.
	if lo != 0 && hi != 0 && lo > hi {
		return 0, 0
	}
	return lo, hi
}

// isWordChar reports whether c is an ASCII letter (the compound-word
// boundary predicate's helper).
func isWordChar(c byte) bool {
	return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
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
	// R34 M-1: BOUNDARY-AWARE word matching — a bare word directly
	// preceded by a letter or hyphen ("thirty-three months", "twenty-three
	// months") is a DIFFERENT number and must NOT match ("three months"
	// was a prefix substring of it: the seat silently kept vetoing at >3
	// while the fixture said >33). The R33 M-1 regex-digits discipline
	// swept the band arm; this is the veto arm's word-form sweep. Compound
	// forms land on the 0 sentinel (fail-closed — the anchor test flags
	// them). R31 m-4: fixed order slice, first-hit-wins (deterministic).
	// R35 m-1: COLLECT-then-DECIDE — all precedence-0 word hits are
	// gathered first; DIFFERENT values across hits are an ambiguous
	// derivation → sentinel (the band arm's R34 m-2 discipline, now on
	// this arm too; the previous inline-return form let the word ORDER
	// decide — "three" hit before "six" regardless of which rule the text
	// meant). Same value repeats are agreement.
	seen := map[int]string{}
	for _, r := range spec.Rules {
		if r.Precedence == 0 {
			for _, w := range []struct {
				word string
				n    int
			}{{"three", 3}, {"four", 4}, {"five", 5}, {"six", 6}} {
				if !strings.Contains(r.Coverage, w.word+" months") {
					continue
				}
				// R36 m-1: no per-key conflict check here — the n→word
				// table is a bijection, so a key can only ever map to one
				// word; the REAL ambiguity check is len(seen) > 1 below
				// (two different VALUES claimed).
				seen[w.n] = w.word
			}
		}
	}
	if len(seen) > 1 {
		return 0 // multiple distinct thresholds claimed — ambiguous
	}
	for _, r := range spec.Rules {
		if r.Precedence == 0 {
			for _, w := range []struct {
				word string
				n    int
			}{{"three", 3}, {"four", 4}, {"five", 5}, {"six", 6}} {
				if strings.Contains(r.Coverage, w.word+" months") {
					// boundary check: the character before the word (if any)
					// must not be a letter, hyphen, or a space preceded by a
					// number word (R35 M-1: the SPACE-separated compound
					// family — "twenty three months", "sixty six months" —
					// slipped the letter/hyphen check because prev==' ';
					// a preceding number word makes this a compound too).
					idx := strings.Index(r.Coverage, w.word+" months")
					if idx == 0 {
						return w.n
					}
					prev := r.Coverage[idx-1]
					poisoned := false
					if isWordChar(prev) || prev == '-' {
						// R36 m-3: a compound hit's true value is not
						// representable in the word table — if the text
						// ALSO carries a clean hit (the collect phase saw
						// the bare word), the two "agree" falsely; poison.
						poisoned = true
					}
					if poisoned {
						return 0
					}
					if prev == ' ' && idx >= 2 {
						// R36 m-2: the magnitude words are in the family too
						// ("hundred three months" parsed as 3 before)
						for _, w2 := range []string{"three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million"} {
							start := idx - 1 - len(w2)
							if start >= 0 && r.Coverage[start:idx-1] == w2 && (start == 0 || !isWordChar(r.Coverage[start-1])) {
								return 0 // space-separated compound → sentinel
							}
						}
					}
					if !(prev >= 'A' && prev <= 'Z') && !(prev >= 'a' && prev <= 'z') && prev != '-' {
						return w.n
					}
					// letter/hyphen compound — keep scanning (fail through to 0)
				}
			}
		}
	}
	return 0 // unparseable/compound — fail-closed sentinel (the anchor test flags it)
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
	// R35 M-2: the LEVEL-BAND CONSISTENCY face — the fixture's rule 1
	// grants 50,000 only above the upper bound, rule 2 grants 10,000 only
	// below the lower bound; a verdict in the wrong band for the declared
	// assets contradicts the rules. R36 M-1: this face SUBSUMES the
	// former between-bands face (inBand ⟹ the matching level-band
	// condition for either grant kind — the old face was a dead guard
	// whose "delete → red" probe was unreachable), so the band face is
	// GONE and the between-bands semantics live entirely here: a grant
	// in [lo,hi] is refused as a model-authored default in the open zone.
	// (Plus the WINDOW-PREMISE face: rule 1's grant carries "with no
	// overdue in the window" — see R36 M-2 for its window-aware form.)
	if kind == "grant-10000" && raw.assetMillionsDeclared >= lo {
		return checkResult{ok: false, reason: "a grant-10000 verdict with assets at or above the lower bound contradicts rule 2 (the level-band consistency face)"}
	}
	if kind == "grant-50000" && raw.assetMillionsDeclared <= hi {
		return checkResult{ok: false, reason: "a grant-50000 verdict with assets in the closed between-bands zone or below it contradicts rule 1 (the level-band consistency face)"}
	}
	// R36 m-4: the on_undefined_rule MIRROR — a rule COVERS the assets
	// point (35 > 30 is unambiguously rule 1), so answering
	// on_undefined_rule there contradicts the rules just like a wrong
	// grant does (the open-zone positive control below stays green).
	if kind == "on_undefined_rule" && raw.assetMillionsDeclared > hi {
		return checkResult{ok: false, reason: "rule 1 covers this assets point (above the upper bound) — on_undefined_rule contradicts the rules instead of answering them"}
	}
	if kind == "grant-50000" {
		for _, o := range raw.overdueOnRecord {
			// R36 M-2: WINDOW-AWARE and TERM-CONSISTENT — the fixture's
			// window is the recent six months (yearsAgo == 0), and its
			// term "overdue" means longer than the anchored threshold
			// (the same definition rule 0 uses — the previous months>0
			// form invented a second definition and was record-global).
			// A term-level overdue INSIDE the window violates rule 1's
			// premise; anything else is spec-conforming.
			if o.yearsAgo == 0 && o.months > vetoMonths {
				return checkResult{ok: false, reason: "a grant-50000 verdict with a term-level overdue inside the recent window violates rule 1's window premise (with no overdue in the window)"}
			}
		}
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
	// edges. R36 M-1: the carrier is now the LEVEL-BAND face (it subsumes
	// the former band face); the probe pins its exclusive reason string —
	// deleting the level-band face turns these red.
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
		if !strings.Contains(cr.reason, "level-band consistency") {
			t.Fatalf("E1 band: refusal at assets=%v came from %q — want the level-band face (the between-bands semantics' only carrier)", assets, cr.reason)
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

// TestE1_VetoAnchorCompoundWords is the R34 M-1 direct probe: compound
// number words ("thirty-three months") must NOT parse as their bare-word
// prefix ("three months") — they land on the 0 sentinel (fail-closed) and
// verify refuses to gate. Mutation probe: remove the boundary check in
// anchorVetoMonths and "thirty-three months" parses as 3 — this goes red.
func TestE1_VetoAnchorCompoundWords(t *testing.T) {
	compound := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "any overdue longer than thirty-three months at any time denies credit"}}}
	if got := anchorVetoMonths(compound); got != 0 {
		t.Fatalf("M-1 probe: compound word anchored = %d, want 0 (a compound is a different number — fail-closed sentinel)", got)
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, compound, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok {
		t.Fatal("M-1 probe: verify gated on a compound-word spec — the unanchored refusal is not load-bearing")
	}
	// the honest fixture still parses (the boundary check does not break
	// the canonical form)
	if got := anchorVetoMonths(loadE3Fixture(t)); got != 3 {
		t.Fatalf("M-1 probe: the real fixture anchored = %d, want 3 — the boundary check broke the happy path", got)
	}

	// R35 M-1: the SPACE-separated compound family ("twenty three months",
	// "sixty six months") — prev==' ' passes the letter/hyphen check, so
	// these were value-preserving misparses (3 and 6). Mutation probe:
	// remove the space-token check and these go red.
	space1 := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "any overdue longer than twenty three months at any time denies credit"}}}
	if got := anchorVetoMonths(space1); got != 0 {
		t.Fatalf("M-1 probe: space compound (twenty three) anchored = %d, want 0 — a space-separated compound is a different number", got)
	}
	space2 := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "any overdue longer than sixty six months at any time denies credit"}}}
	if got := anchorVetoMonths(space2); got != 0 {
		t.Fatalf("M-1 probe: space compound (sixty six) anchored = %d, want 0", got)
	}

	// R34 m-1: the SEPARATOR form ("30,000") must fail closed — the digit
	// regex stops at the comma and would silently capture "30"; the
	// declared contract is sentinel-0 for any form the parser can't take
	// whole. Mutation probe: widen the digit class to include commas and
	// this red expectation changes shape (re-pin it).
	bandSpec := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 1, Coverage: "assets above 30,000 (USD-millions) grant the line"}, {Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"}}}
	blo, bhi := anchorBandBounds(bandSpec)
	if blo != 0 || bhi != 0 {
		t.Fatalf("m-1 probe: separator-form bounds = (%v, %v), want (0, 0) — the digit regex captured a prefix of a grouped number (fail-closed violated)", blo, bhi)
	}
}

// TestE1_BandBoundsMultiHitConflicts is the R34 m-2 probe: two rules
// deriving the same face with DIFFERENT values is an ambiguous derivation
// — the anchor refuses (sentinel), matching the
// ambiguous-precedence-is-a-conflict discipline. Mutation probe: make the
// second hit silently overwrite (last-wins) and this goes red.
func TestE1_BandBoundsMultiHitConflicts(t *testing.T) {
	ambiguous := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line"},
		{Precedence: 3, Coverage: "assets above 40 (USD-millions) also mentioned"},
	}}
	lo, hi := anchorBandBounds(ambiguous)
	if lo != 0 || hi != 0 {
		t.Fatalf("m-2 probe: conflicting derivations = (%v, %v), want (0, 0) — ambiguity is a conflict, not a last-wins order", lo, hi)
	}
	// agreement face: two rules deriving the SAME value are fine (plus
	// the below-1 rule so lo is populated — the fixture's real shape)
	agreeing := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line"},
		{Precedence: 3, Coverage: "recap: assets above 30 (USD-millions) as before"},
		{Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"},
	}}
	lo, hi = anchorBandBounds(agreeing)
	if lo != 1 || hi != 30 {
		t.Fatalf("m-2 probe: agreeing derivations = (%v, %v), want (1, 30) — agreement must not be treated as conflict", lo, hi)
	}
}

// TestE1_LevelBandConsistency is the R35 M-2 probe: the two semantic faces
// the header promised but the seat lacked. Mutation probes: delete either
// new face and the matching case passes silently (red).
func TestE1_LevelBandConsistency(t *testing.T) {
	spec := loadE3Fixture(t)

	// ① wrong-level grant: grant-10000 at assets=35 (rule 2 grants only
	// below 1) — refused
	wrongLevel := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "grant-10000", details: "wrong level"}, spec, wrongLevel); cr.ok {
		t.Fatal("M-2 probe: a grant-10000 verdict at assets=35 passed — the level-band consistency face is not load-bearing")
	}
	// ② window-premise violation: grant-50000 with a TERM-level overdue
	// INSIDE the window (4 months, yearsAgo=0) — the spec's answer is NOT
	// a clean grant. (R36 M-2: the probe is now window-aware AND
	// term-consistent — the old months=2 form invented a second definition
	// of "overdue".)
	window := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 0}}}
	if cr := verify(s1Verdict{kind: "grant-50000", details: "in-window overdue ignored"}, spec, window); cr.ok {
		t.Fatal("M-2 probe: a grant-50000 verdict with an in-window term-level overdue passed — rule 1's window premise is not enforced")
	}
	// ③ R36 M-2 positive control: a SUB-TERM record outside the window
	// (1 month, 5 years ago — not an "overdue" under the fixture's term,
	// not in the window) must NOT be blocked — the old record-global form
	// refused this spec-conforming verdict.
	legacy := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 1, yearsAgo: 5}}}
	if cr := verify(s1Verdict{kind: "grant-50000", details: "old sub-term record"}, spec, legacy); !cr.ok {
		t.Fatalf("M-2 probe: a spec-conforming verdict with an out-of-window sub-term record was refused (%s) — the window premise over-blocks", cr.reason)
	}
	// positive controls: the consistent forms still pass
	if cr := verify(s1Verdict{kind: "grant-50000", details: "clean record"}, spec, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}); !cr.ok {
		t.Fatalf("M-2 probe: the consistent grant-50000 was refused (%s) — the new faces over-block", cr.reason)
	}
}

// TestE1_VetoAnchorMultiHitConflicts is the R35 m-1 probe: the veto arm's
// multi-hit discipline (band arm's twin). Two precedence-0 rules claiming
// different thresholds → sentinel; the same threshold twice → agreement.
func TestE1_VetoAnchorMultiHitConflicts(t *testing.T) {
	conflicting := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 0, Coverage: "denies beyond six months for standard applicants"},
		{Precedence: 0, Coverage: "three months for apprentices"},
	}}
	if got := anchorVetoMonths(conflicting); got != 0 {
		t.Fatalf("m-1 probe: conflicting veto claims anchored = %d, want 0 — ambiguity is a conflict", got)
	}
	agreeing := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 0, Coverage: "denies beyond three months for standard applicants"},
		{Precedence: 0, Coverage: "recap: three months as before"},
	}}
	if got := anchorVetoMonths(agreeing); got != 3 {
		t.Fatalf("m-1 probe: agreeing claims anchored = %d, want 3 — agreement is not a conflict", got)
	}
}

// TestE1_BandBoundsInvertedRefused is the R35 m-2 probe: a parseable but
// SELF-CONTRADICTING interval ("above 30 … below 40" → lo=40 > hi=30) is
// refused — the band face must not silently go inert. Mutation probe:
// remove the inversion check and this goes red.
func TestE1_BandBoundsInvertedRefused(t *testing.T) {
	inverted := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line"},
		{Precedence: 2, Coverage: "exception: assets below 40 (USD-millions) may also qualify"},
	}}
	lo, hi := anchorBandBounds(inverted)
	if lo != 0 || hi != 0 {
		t.Fatalf("m-2 probe: inverted interval = (%v, %v), want (0, 0) — a self-contradicting band is a conflict", lo, hi)
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, inverted, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok {
		t.Fatal("m-2 probe: verify gated on an inverted-band spec — the fail-closed face is not load-bearing")
	}
}

// TestE1_UndefinedRuleMirror is the R36 m-4 probe: a rule-covered point
// answered on_undefined_rule is a contradiction (the mirror twin of the
// deny mirror). Mutation probe: delete the mirror face and this goes red.
func TestE1_UndefinedRuleMirror(t *testing.T) {
	spec := loadE3Fixture(t)
	covered := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "on_undefined_rule", details: "evasive non-answer"}, spec, covered); cr.ok {
		t.Fatal("m-4 probe: an on_undefined_rule verdict at a rule-covered point passed — the under-execution form is not intercepted")
	}
	// positive control: the OPEN ZONE keeps its honest on_undefined_rule
	open := rawEvidence{assetMillionsDeclared: 12, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "on_undefined_rule", details: "genuinely open"}, spec, open); !cr.ok {
		t.Fatalf("m-4 probe: the honest open-zone verdict was refused (%s) — the mirror over-blocks", cr.reason)
	}
}
