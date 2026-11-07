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

// R43 m-2 declaration: rawEvidence's yearsAgo (inside overdueEvent) is
// DECORATIVE at the seat — the unbounded veto ignores age by design (the
// R37 M-1 window-face retirement removed the seat's only yearsAgo
// reader); the S1 stand-in consumes it. Anyone re-introducing window
// semantics must re-declare the consumption.

// anchorBandBounds derives the open-question band's closed bounds from the
// fixture's rule texts — the NUMBER IS PARSED from the matched text (R33
// M-1: the previous Contains+literal-copy form was blind to digit
// extension, "above 30"→"above 300" matched and kept the stale 30). An
// An unparseable, conflicting, or self-contradicting derivation returns
// (0, 0) (the fail-closed sentinel: the anchor test flags it; the
// verify-side refusal names all three sources — R46 m-1/m-5), never a
// historic default. Sentinel protection state: the
// VERIFY-side refusal (R40 M-2) rejects an unanchored spec outright
// (TestE1_BandAnchorFailClosed pins that carrier — deleting the refusal
// resurrects the drift cover). (R42 m-1: the older R33 m-3 note here
// described the since-deleted band face and predated the verify-side
// refusal.)
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
	// silently-resolved array order. R38 M-2: FindAllStringSubmatch —
	// INTRA-RULE matches too (an appended clause "recap: assets above 50
	// as before" was silently ignored by first-match); two different
	// values in one rule are a conflict, same as cross-rule. R44 m-4:
	// DECLARED blind spot — the COMMA/CONJUNCTION LISTING form ("above
	// 30, 50 as before" / "above 30 and 50") yields one match per
	// keyword occurrence; a second bare number without its keyword is
	// not a hit and is not conflicted (the anchor test pins the
	// fixture's canonical form; the listing form is out of the anchor's
	// grammar, like the veto arm's conjunction blind spot).
	// R40 m-2: seenAbove/seenBelow separate "a value was recorded" from
	// the recorded VALUE — the 0 sentinel used to collide with a
	// legitimately-parsed 0 ("above 0" then "above 50" last-wins'd
	// silently because hi != 0 was false).
	seenAbove, seenBelow := false, false
	for _, r := range spec.Rules {
		// R42 M-1: the band anchor also runs on the NORMALIZED text (the
		// single-space regex literals missed whitespace-variant conflict
		// declarations — "above␣␣50" never matched and drifted silently)
		normalizedBand := normalizeRuleText(r.Coverage)
		for _, m := range aboveRe.FindAllStringSubmatch(normalizedBand, -1) {
			if m[2] != "" {
				return 0, 0 // grouped/poisoned form — fail closed
			}
			var v float64
			if _, err := fmt.Sscanf(m[1], "%g", &v); err != nil {
				return 0, 0
			}
			if seenAbove && hi != v {
				return 0, 0 // two different "above" bounds (cross- or intra-rule) — ambiguous
			}
			hi, seenAbove = v, true
		}
		for _, m := range belowRe.FindAllStringSubmatch(normalizedBand, -1) {
			if m[2] != "" {
				return 0, 0
			}
			var v float64
			if _, err := fmt.Sscanf(m[1], "%g", &v); err != nil {
				return 0, 0
			}
			if seenBelow && lo != v {
				return 0, 0
			}
			lo, seenBelow = v, true
		}
	}

	// R35 m-2: an INVERTED interval (lo > hi — both parsed but the text
	// contradicts itself) is neither unparseable nor multi-hit — it is
	// the third fail-open form: inBand would be vacuously false and the
	// band face silently inert. Refuse it like the others.
	// R41 m-1: the seen flags (R40 m-2) decide "inverted" — the old
	// lo != 0 && hi != 0 form skipped a TRUE inversion when one bound was
	// a legitimately-parsed 0 ("above 0" + "below 5" → (5,0) slipped).
	if seenAbove && seenBelow && lo > hi {
		return 0, 0
	}
	return lo, hi
}

// isWordChar reports whether c is an ASCII letter (the compound-word
// boundary predicate's helper).
func isWordChar(c byte) bool {
	return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
}

// normalizeRuleText is the SINGLE whitespace-normalization helper (R43
// m-3: the Fields/Join expression lived inline in three consumption
// faces — the R42 M-1 lesson was exactly that a new text treatment must
// be sweepable, and a named function makes the sweep a one-line grep).
func normalizeRuleText(s string) string {
	return strings.Join(strings.Fields(s), " ")
}

// R37 m-3: the veto word table is defined ONCE (collect and decide share
// it — two inline copies could silently fork when one side gains a word).
type vetoWord struct {
	word string
	n    int
}

var vetoWords = []vetoWord{
	{"three", 3}, {"four", 4}, {"five", 5}, {"six", 6},
}

// compoundTokens are the number words that can precede a table word to
// form a space-separated compound (R35 M-1/R36 m-2 family).
var compoundTokens = []string{"three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million"}

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
	// them). R40 m-3: the CONJUNCTION sub-family ("a hundred AND three
	// months" — preceding token is a plain article, not a number word) is
	// a DECLARED blind spot: the token scan cannot distinguish it from
	// prose; the anchor test pins the fixture to the canonical form.
	// R31 m-4: fixed order slice (deterministic); collect-then-
	// decide since R35 m-1 (R39 m-3: the old "first-hit-wins" phrasing
	// described the pre-refactor inline-return form).
	// R35 m-1: COLLECT-then-DECIDE — all precedence-0 word hits are
	// gathered first; DIFFERENT values across hits are an ambiguous
	// derivation → sentinel (the band arm's R34 m-2 discipline, now on
	// this arm too; the previous inline-return form let the word ORDER
	// decide — "three" hit before "six" regardless of which rule the text
	// meant). Same value repeats are agreement.
	seen := map[int]struct{}{}
	for _, r := range spec.Rules {
		// R42 M-1: the collect phase reads the NORMALIZED text — same as
		// the decide phase (the two phases saw different texts before: a
		// whitespace-variant conflict declaration slipped the bare
		// Contains and the conflict was silently dropped)
		normalized := normalizeRuleText(r.Coverage)
		if r.Precedence == 0 {
			for _, w := range vetoWords {
				if !strings.Contains(normalized, w.word+" months") {
					continue
				}
				// R36 m-1: no per-key conflict check here — the n→word
				// table is a bijection, so a key can only ever map to one
				// word; the REAL ambiguity check is len(seen) > 1 below
				// (two different VALUES claimed).
				seen[w.n] = struct{}{} // R42 m-2: the word form was never consumed (dead value) — the SET membership is the semantics
			}
		}
	}
	if len(seen) > 1 {
		return 0 // multiple distinct thresholds claimed — ambiguous
	}
	// R37 M-2: decide scans EVERY precedence-0 rule's EVERY occurrence —
	// a compound anywhere in those rules poisons the anchor BEFORE (R39
	// m-3: the scan is precedence-0-scoped, matching the anchor's source;
	// any clean value returns (the previous per-rule early-return let a
	// clean rule's hit exempt a later compound rule).
	for _, r := range spec.Rules {
		// R39 m-1: the anchor is a PURE function now — the whitespace
		// normalization (R38 M-3) lives on a LOCAL copy instead of
		// mutating the caller's spec (the mutation also depended on the
		// early-return path, making it input-dependent).
		normalized := normalizeRuleText(r.Coverage)
		if r.Precedence == 0 {
			for _, w := range vetoWords {
				searchFrom := 0
				for {
					rel := strings.Index(normalized[searchFrom:], w.word+" months")
					if rel < 0 {
						break
					}
					idx := searchFrom + rel
					if idx > 0 {
						prev := normalized[idx-1]
						if isWordChar(prev) || prev == '-' {
							return 0 // letter/hyphen compound — unrepresentable value, poison
						}
						if prev == ' ' && idx >= 2 {
							compound := false
							for _, w2 := range compoundTokens {
								start := idx - 1 - len(w2)
								if start >= 0 && normalized[start:idx-1] == w2 && (start == 0 || !isWordChar(normalized[start-1])) {
									compound = true
									break
								}
							}
							if compound {
								return 0 // space-separated compound → poison
							}
						}
					}
					searchFrom = idx + 1
				}
			}
		}
	}
	// no compound anywhere — the clean value (from the collect phase) is
	// the anchor. R38 m-1: iterate SEEN, not a third hardcoded copy of the
	// word table (len(seen) <= 1 is guaranteed by the conflict check) —
	// a new word added to vetoWords flows through without touching here.
	for n := range seen {
		return n
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
		// R46 m-1: the 0 sentinel has THREE reachable sources (unparseable
		// text, multi-value conflicts, compound poisoning) — the message
		// names all three (the band arm's R45 m-2 exhaustiveness, now on
		// this twin arm too).
		return checkResult{ok: false, reason: "no usable veto threshold — the fixture's rule-0 threshold is unparseable, conflicting, or compound-poisoned; the seat refuses to gate (fail-closed, R30 M-2/R46 m-1)"}
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
	// R32 M-2 + R40 M-1: the evidence-presence faces, dispatched by switch
	// — each case IS a face for its kind; the final default refuses any
	// kind no case consumed (consumption completeness is structural: a new
	// fixture level forces a new case, the fail-open channel is not
	// expressible without adding BOTH the case AND its semantics — the old
	// consumed-literal enumeration was a second hand-maintained list whose
	// drift from the faces was pure convention).
	switch kind {
	case "grant-50000", "grant-10000":
		if !raw.assetReportPresent {
			return checkResult{ok: false, reason: "the asset valuation report (the fixture's first evidence source) is absent — a grant verdict without it is the evasive-S1 form (E0 family)"}
		}
	case "on_missing_evidence":
		if raw.assetReportPresent {
			return checkResult{ok: false, reason: "the asset valuation report is present but the verdict claims it missing — the spec's resolution scopes on_missing_evidence to the asset report alone (any other gap is the host's pre-judgment coverage route, E2), so this claim is the evasion mirror"}
		}
	case "deny", "on_undefined_rule":
		// their semantic faces live below (deny: the veto mirror above;
		// on_undefined_rule: the band mirrors after the band anchor)
	default:
		return checkResult{ok: false, reason: "the verdict kind " + v.kind + " is in the fixture's vocabulary but no semantic face consumes it — add a case (face) for the new level instead of passing it silently (fail-closed, R39 M-1/R40 M-1)"}
	}
	// R40 M-1: the consumption-completeness gate is now STRUCTURAL — the
	// old `consumed :=` literal enumeration was a SECOND hand-maintained
	// list (adding a level to consumed without adding a face reopened the
	// fail-open channel R39 M-1 closed; the two lists' sync was pure
	// convention). The switch below is the single dispatch point: each
	// case IS a face, the default refuses, and an unconsumed kind is not
	// expressible (the vocabulary gate above still admits fixture names,
	// but every admitted name must now land in a case).
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
		// R45 m-2: the (0,0) sentinel has THREE reachable sources — truly
		// unparseable text, multi-hit conflicts (bounds parsed fine), and
		// self-contradicting inversions (R41 m-1's own note says "neither
		// unparseable nor multi-hit") — the message names all three
		// instead of claiming unparseable (the host would otherwise go fix
		// a parser that is not broken).
		return checkResult{ok: false, reason: "no usable band bounds — the fixture's bounds are unparseable, conflicting, or self-contradicting; the seat refuses to gate (fail-closed, R33 m-3/R40 M-2)"}
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
	// R38 B-1: the LOWER-half mirror — actually landed this time (the R37
	// m-1 patch failed to match and the ledger claimed it anyway; this is
	// the "修复声明必须机械验证" discipline's own recurrence). rule 2
	// covers assets below lo the same way rule 1 covers above hi.
	if kind == "on_undefined_rule" && raw.assetMillionsDeclared < lo {
		return checkResult{ok: false, reason: "rule 2 covers this assets point (below the lower bound) — on_undefined_rule contradicts the rules instead of answering them"}
	}
	// R37 M-1: the WINDOW-PREMISE face is RETIRED — under the unbounded
	// veto (rule 0), any term-level overdue inside the window ALREADY
	// fails the veto face (kind != deny), so this face's predicate domain
	// was a strict SUBSET of rule 0's: a 1408-input brute scan found ZERO
	// inputs where this face's reason was reachable (R36 M-1's dead-guard
	// shape, re-introduced by R36 M-2's own addition). Rule 1's window
	// premise is enforced BY rule 0 in this fixture — the enforcement
	// exists, its carrier is the veto face, and the separate face was a
	// second carrier claiming the same refusals.
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
	events, err := h.machine.Events()
	if err != nil {
		t.Fatalf("E2/E5: Events() failed — a load error must fail, not silently empty the assertion set: %v", err)
	}
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

// TestE1_CaseVariantsRefused is the R31 M-1 direct probe (R41 M-1
// re-pinned, R43 m-1 header synced to the arm notes): case variants must
// be refused exactly like their canonical forms. Carrier map — the
// vocabulary gate NORMALIZES a variant to canonical form BEFORE the faces
// run, so arm ① is refused by the DENY MIRROR and arm ② by the
// LEVEL-BAND face; arm ③ is the normalization assignment's EXCLUSIVE
// face (a variant-case REAL deny must be ACCEPTED — removing the
// assignment turns arm ③ red).
func TestE1_CaseVariantsRefused(t *testing.T) {
	spec := loadE3Fixture(t)

	// ① "DENY" on a clean record — refused BY THE DENY MIRROR (the
	// vocabulary gate NORMALIZES "DENY"→canonical "deny" BEFORE the
	// faces run, so the mirror sees the canonical form; the switch
	// default is NOT the carrier — R41 M-1 first-draft error, the mirror
	// is and the reason is pinned)
	rawClean := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	cr1 := verify(s1Verdict{kind: "DENY", details: "fabricated in caps"}, spec, rawClean)
	if cr1.ok {
		t.Fatal("M-1 probe: DENY on a clean record was served — the variant escaped the mirror face")
	}
	if !strings.Contains(cr1.reason, "rule 0 is the only deny path") {
		t.Fatalf("M-1 probe: arm ① refusal reason = %q, want the deny-mirror marker (the pinned carrier)", cr1.reason)
	}
	// ② "GRANT-50000" in the open band — normalized to canonical by the
	// vocabulary gate, then refused BY THE LEVEL-BAND FACE (its carrier)
	rawBand := rawEvidence{assetMillionsDeclared: 12, assetReportPresent: true}
	cr2 := verify(s1Verdict{kind: "GRANT-50000", details: "variant grant"}, spec, rawBand)
	if cr2.ok {
		t.Fatal("M-1 probe: GRANT-50000 in the open band was served — the variant escaped the level-band face")
	}
	if !strings.Contains(cr2.reason, "level-band consistency") {
		t.Fatalf("M-1 probe: arm ② refusal reason = %q, want the level-band marker (the pinned carrier)", cr2.reason)
	}
	// ③ the normalization assignment's EXCLUSIVE face: the variant honored
	// as a REAL deny when the veto fires (the seat accepts the normalized
	// form's verdict — normalization is symmetric). Mutation probe:
	// remove the normalization assignment and THIS arm goes red.
	rawVeto := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}}
	if cr := verify(s1Verdict{kind: "DENY", details: "real veto in caps"}, spec, rawVeto); !cr.ok {
		t.Fatalf("M-1 probe: a variant-case REAL deny was refused (%s) — normalization broke the happy path (the assignment's exclusive face)", cr.reason)
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
	// R46 m-4: THREE independent keyword pins (the exhaustiveness is
	// load-bearing — a prefix-only anchor let the enumeration silently
	// drop)
	for _, kw := range []string{"unparseable", "conflicting", "compound"} {
		if !strings.Contains(cr.reason, kw) {
			t.Fatalf("M-1 probe: refusal reason = %q, want the %q source named (R46 m-1 exhaustive message)", cr.reason, kw)
		}
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
	var cr checkResult
	cr = verify(s1Verdict{kind: "grant-10000", details: "wrong level"}, spec, wrongLevel)
	if cr.ok {
		t.Fatal("M-2 probe: a grant-10000 verdict at assets=35 passed — the level-band consistency face is not load-bearing")
	}
	// ② window-premise enforcement: a term-level overdue INSIDE the
	// window still kills the grant — but the CARRIER is rule 0 (the R37
	// M-1 retirement: the separate window face's domain was a strict
	// subset of the veto's). The probe pins the veto reason so a future
	// carrier change must re-declare itself.
	window := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 0}}}
	cr = verify(s1Verdict{kind: "grant-50000", details: "in-window overdue ignored"}, spec, window)
	if cr.ok {
		t.Fatal("M-2 probe: a grant-50000 verdict with an in-window term-level overdue passed — rule 1's window premise is not enforced")
	}
	if !strings.Contains(cr.reason, "rule 0") {
		t.Fatalf("M-2 probe: the in-window refusal came from %q — the declared carrier is the veto face (rule 0); a new carrier must re-pin this probe", cr.reason)
	}
	// ③ R36 M-2 positive control: a SUB-TERM record (1 month, 5 years
	// ago — not an "overdue" under the fixture's term; the yearsAgo value
	// is decorative at the seat per the R43 m-2 declaration) must NOT be
	// blocked — the old record-global form refused this spec-conforming
	// verdict.
	legacy := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: []overdueEvent{{months: 1, yearsAgo: 5}}}
	if cr := verify(s1Verdict{kind: "grant-50000", details: "old sub-term record"}, spec, legacy); !cr.ok {
		t.Fatalf("M-2 probe: a spec-conforming verdict with an out-of-window sub-term record was refused (%s) — the window premise over-blocks", cr.reason)
	}
	// positive controls: the consistent forms still pass
	if cr := verify(s1Verdict{kind: "grant-50000", details: "clean record"}, spec, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}); !cr.ok {
		t.Fatalf("M-2 probe: the consistent grant-50000 was refused (%s) — the new faces over-block", cr.reason)
	}
	// R40 m-1: the grant-10000 下臂 positive control — a grant-10000 BELOW
	// lo must pass (the only two grant-10000 verify calls before this were
	// refusals; an over-block mutation on the lower-band face was green)
	if cr := verify(s1Verdict{kind: "grant-10000", details: "clean record"}, spec, rawEvidence{assetMillionsDeclared: 0.5, assetReportPresent: true}); !cr.ok {
		t.Fatalf("m-1 probe: the consistent grant-10000 was refused (%s) — the lower-band face over-blocks (over-block mutation invisible)", cr.reason)
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
// refused — the band face must not silently go inert. R41 m-2: the spec
// CARRIES a parseable precedence-0 rule (veto anchor resolves) so the
// verify-side arm's refusal genuinely lands on the BAND face (the old
// veto-broken form was refused by the veto anchor first, mis-attributing
// the carrier); the reason is now pinned. Mutation probe: remove the
// inversion check and both the anchor value and the verify-side reason
// go red.
func TestE1_BandBoundsInvertedRefused(t *testing.T) {
	inverted := &fixtureSpec{
		Levels: []fixtureLevel{{Name: "grant-50000"}, {Name: "deny"}},
		Rules: []fixtureVetoRule{
			{Precedence: 0, Coverage: "denies beyond three months for standard applicants"},
			{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line"},
			{Precedence: 2, Coverage: "exception: assets below 40 (USD-millions) may also qualify"},
		},
	}
	lo, hi := anchorBandBounds(inverted)
	if lo != 0 || hi != 0 {
		t.Fatalf("m-2 probe: inverted interval = (%v, %v), want (0, 0) — a self-contradicting band is a conflict", lo, hi)
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, inverted, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok {
		t.Fatal("m-2 probe: verify gated on an inverted-band spec — the fail-closed face is not load-bearing")
	}
	if !strings.Contains(cr.reason, "no usable band bounds") {
		t.Fatalf("m-2 probe: refusal reason = %q, want the no-usable-bounds marker (R45 m-2)", cr.reason)
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
	// R38 B-1 third arm: the LOWER-half covered point (assets=0.5, rule 2
	// "below 1") — the form the R37 m-1 ledger entry claimed was fixed but
	// never landed
	lower := rawEvidence{assetMillionsDeclared: 0.5, assetReportPresent: true}
	cr2 := verify(s1Verdict{kind: "on_undefined_rule", details: "evasive non-answer below"}, spec, lower)
	if cr2.ok {
		t.Fatal("B-1 probe: an on_undefined_rule verdict at a rule-2-covered point passed — the lower mirror is not load-bearing")
	}
	if !strings.Contains(cr2.reason, "rule 2") {
		t.Fatalf("B-1 probe: lower refusal reason = %q, want the rule-2 carrier", cr2.reason)
	}
	// positive control: the OPEN ZONE keeps its honest on_undefined_rule
	open := rawEvidence{assetMillionsDeclared: 12, assetReportPresent: true}
	if cr := verify(s1Verdict{kind: "on_undefined_rule", details: "genuinely open"}, spec, open); !cr.ok {
		t.Fatalf("m-4 probe: the honest open-zone verdict was refused (%s) — the mirror over-blocks", cr.reason)
	}
}

// TestE1_VetoAnchorMixedOrder is the R37 M-2 probe: a compound occurrence
// anywhere in the text poisons the anchor regardless of ORDER — the clean
// occurrence must not exempt a later compound (clean-first single rule),
// and a clean RULE must not exempt a compound RULE (array order).
// Mutation probe: revert decide to first-occurrence-only and both cases
// parse the clean value — this goes red.
func TestE1_VetoAnchorMixedOrder(t *testing.T) {
	// ① clean-first single rule
	cleanFirst := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "three months for apprentices; denies beyond thirty-three months for everyone else"}}}
	if got := anchorVetoMonths(cleanFirst); got != 0 {
		t.Fatalf("M-2 probe: clean-first mixed text anchored = %d, want 0 — the later compound poisons", got)
	}
	// ② clean rule first, compound rule second
	compoundLater := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 0, Coverage: "three months for apprentices"},
		{Precedence: 0, Coverage: "denies beyond thirty-three months"},
	}}
	if got := anchorVetoMonths(compoundLater); got != 0 {
		t.Fatalf("M-2 probe: clean-rule-first anchored = %d, want 0 — the compound rule poisons", got)
	}
}

// TestE1_AnchorWhitespaceAndMultiHit is the R38 M-2/M-3 probe pair:
// ① double-space compound poisons (whitespace normalization), ② an
// appended clause with a different bound inside ONE rule conflicts.
// Mutation probes: remove the whitespace normalization (① parses 3) or
// revert to first-match (② returns (1,30)) — either goes red.
func TestE1_AnchorWhitespaceAndMultiHit(t *testing.T) {
	// ① double-space compound
	doubleSpace := &fixtureSpec{Rules: []fixtureVetoRule{{Precedence: 0, Coverage: "any overdue longer than twenty  three months at any time denies credit"}}}
	if got := anchorVetoMonths(doubleSpace); got != 0 {
		t.Fatalf("M-3 probe: double-space compound anchored = %d, want 0 — whitespace normalization is not load-bearing", got)
	}
	// ② intra-rule second different bound
	intra := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line; recap: assets above 50 as before"},
		{Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"},
	}}
	lo, hi := anchorBandBounds(intra)
	if lo != 0 || hi != 0 {
		t.Fatalf("M-2 probe: intra-rule conflicting bounds = (%v, %v), want (0, 0) — the appended clause drifted silently", lo, hi)
	}
}

// TestE1_VocabularyConsumptionComplete is the R39 M-1 probe: EVERY name in
// spec.Levels (plus the resolution words) must be CONSUMED by a semantic
// face — a new level added to the fixture (a legal spec evolution) must
// turn this red instead of silently passing. Mutation probe: delete the
// consumption-completeness gate in verify() and a synthetic new level
// passes through (red).
func TestE1_VocabularyConsumptionComplete(t *testing.T) {
	spec := loadE3Fixture(t)
	// the real fixture's levels are all consumed (the gate does not fire):
	for _, lvl := range spec.Levels {
		raw := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
		cr := verify(s1Verdict{kind: lvl.Name, details: "probe"}, spec, raw)
		if strings.Contains(cr.reason, "no semantic face consumes") {
			t.Fatalf("M-1 probe: fixture level %q is admitted but unconsumed — the fail-open channel is live", lvl.Name)
		}
	}
	// the synthetic new level: admitted by the vocabulary gate, refused by
	// the completeness gate (no face consumes it)
	newLevel := &fixtureSpec{
		Levels: []fixtureLevel{{Name: "grant-20000"}, {Name: "deny"}},
		Rules:  spec.Rules,
	}
	raw := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true}
	cr := verify(s1Verdict{kind: "grant-20000", details: "a legal spec evolution"}, newLevel, raw)
	if cr.ok {
		t.Fatal("M-1 probe: a synthetic new level passed verify — the fail-open channel is live (add a face, not a pass)")
	}
	if !strings.Contains(cr.reason, "no semantic face consumes") {
		t.Fatalf("M-1 probe: refusal reason = %q, want the consumption marker", cr.reason)
	}
}

// TestE1_AnchorPurity is the R39 m-1 probe: anchorVetoMonths is a PURE
// function — its input spec must be byte-identical after the call (the
// whitespace normalization lives on a local copy). Mutation probe: revert
// to in-place spec mutation and this goes red.
func TestE1_AnchorPurity(t *testing.T) {
	spec := loadE3Fixture(t)
	before := fmt.Sprintf("%v", spec.Rules)
	_ = anchorVetoMonths(spec)
	after := fmt.Sprintf("%v", spec.Rules)
	if before != after {
		t.Fatal("m-1 probe: anchorVetoMonths mutated its input spec — the derive function carries a hidden write side effect")
	}
}

// (R39 m-1 mutation-verification record: reverting the decide phase to
// in-place spec mutation made THIS test red — verified before the revert
// was restored. The probe is coupled to the purity property.)

// TestE1_BandAnchorFailClosed is the R40 M-2 probe: the band-anchor's
// verify-side refusal (unparseable bounds → refuse to gate) had ZERO
// reachable probes — every test spec with a broken band anchor ALSO broke
// the veto anchor, whose face returned first. This spec breaks ONLY the
// band anchor (veto parses fine), so the band-side refusal is what fires.
// Mutation probe: delete the lo==0/hi==0 refusal in verify() and this
// goes red (grant-50000@35 falls to the level-band face with hi=0 —
// 35 <= 0 false — and passes, the drift-cover复活).
func TestE1_BandAnchorFailClosed(t *testing.T) {
	bandOnly := &fixtureSpec{
		Levels: []fixtureLevel{{Name: "grant-50000"}, {Name: "deny"}},
		Rules: []fixtureVetoRule{
			{Precedence: 0, Coverage: "denies beyond three months for standard applicants"},
			{Precedence: 1, Coverage: "assets above 30,000 (USD-millions) grant the line"},
			{Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"},
		},
	}
	cr := verify(s1Verdict{kind: "grant-50000", details: "healthy"}, bandOnly, rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true})
	if cr.ok {
		t.Fatal("M-2 probe: verify gated on a band-unparseable spec — the band-side fail-closed face is not load-bearing")
	}
	if !strings.Contains(cr.reason, "no usable band bounds") {
		t.Fatalf("M-2 probe: refusal reason = %q, want the no-usable-bounds marker (R45 m-2)", cr.reason)
	}
}

// TestE1_BandBoundsZeroSentinelCollision is the R40 m-2 probe: "above 0"
// parses to the same value as the un-parsed sentinel — a second DIFFERENT
// hit ("above 50") used to last-wins silently. Mutation probe: remove the
// zero-collision re-scan and this returns (1, 50) (red).
func TestE1_BandBoundsZeroSentinelCollision(t *testing.T) {
	zeroThenFifty := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 0 (USD-millions) technically grants everything"},
		{Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"},
		{Precedence: 3, Coverage: "recap: assets above 50 as before"},
	}}
	lo, hi := anchorBandBounds(zeroThenFifty)
	if lo != 0 || hi != 0 {
		t.Fatalf("m-2 probe: zero-collision bounds = (%v, %v), want (0, 0) — the sentinel collision must conflict, not last-wins", lo, hi)
	}
}

// TestE1_BandBoundsInvertedWithZero is the R41 m-1 probe: a TRUE inversion
// where one bound is a legitimately-parsed 0 ("above 0" + "below 5" →
// lo=5 > hi=0) must be refused — the seen-flag form of the inversion
// check. Mutation probe: revert to the lo != 0 && hi != 0 form and this
// returns (5, 0) (red).
func TestE1_BandBoundsInvertedWithZero(t *testing.T) {
	invertedWithZero := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 0 (USD-millions) technically grants everything"},
		{Precedence: 2, Coverage: "assets below 5 (USD-millions) grants the small line"},
	}}
	lo, hi := anchorBandBounds(invertedWithZero)
	if lo != 0 || hi != 0 {
		t.Fatalf("m-1 probe: zero-involved inversion = (%v, %v), want (0, 0) — the seen-flag form must catch it", lo, hi)
	}
}

// TestE1_WhitespaceVariantConflictsCaught is the R42 M-1 probe: whitespace-
// variant conflict declarations must be CAUGHT like their single-space
// twins — the collect phase and the band regex both run on normalized
// text. Mutation probe: revert either consumer to bare-text and the
// matching case goes green (the conflict silently drops).
func TestE1_WhitespaceVariantConflictsCaught(t *testing.T) {
	// ① veto arm: a clean rule + a whitespace-variant conflicting
	// declaration → conflict (previously parsed 3, the conflict dropped)
	vetoConflict := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 0, Coverage: "denies beyond three months for standard applicants"},
		{Precedence: 0, Coverage: "recap: six  months as before"},
	}}
	if got := anchorVetoMonths(vetoConflict); got != 0 {
		t.Fatalf("M-1 probe: whitespace-variant veto conflict anchored = %d, want 0 — the conflict silently dropped", got)
	}
	// ② band arm: an appended clause with a whitespace-variant different
	// bound → conflict (previously (1, 30), the drift silently kept)
	bandConflict := &fixtureSpec{Rules: []fixtureVetoRule{
		{Precedence: 1, Coverage: "assets above 30 (USD-millions) grant the line; recap: assets above  50 as before"},
		{Precedence: 2, Coverage: "assets below 1 (USD-millions) grants the small line"},
	}}
	lo, hi := anchorBandBounds(bandConflict)
	if lo != 0 || hi != 0 {
		t.Fatalf("M-1 probe: whitespace-variant band conflict = (%v, %v), want (0, 0) — the appended-clause drift was silently kept", lo, hi)
	}
}
