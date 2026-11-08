package e2e

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// P0-A (xingchao 198789782 §2 + 198789653 counterexamples 1/A): the
// overdue-ontology split — duration and recency are separate event
// attributes; the veto (rule 0) reads duration alone (>3 months at any
// time), the upper-band premise (rule 1) reads recency alone (any
// duration inside the six-month window). The P3 definitional absorption
// (the term "overdue" embedding ">3 months") is reverted in fixture
// v1.1.0.
//
// TRUTH SOURCE: the six-cell matrix below is FROZEN in
// impl-2026-11-01/50-p0a-scope-prior.md §三 BEFORE this file was
// written — expectations are translated from the original business rule
// (xingchao 198789782 §2, verbatim), never reverse-derived from the
// implementation (the W1 disease, institutionalized defense). Any
// expectation change MUST edit the frozen table first, with a one-line
// why.
//
// Dual implementation (互证 form): s1Judge reads the frozen t1Spec text
// ("no overdue in the last six months"), verify anchors the fixture's
// time_window — two independent implementations of the same predicates,
// asserted per-cell; divergence is red by construction.

// TestP0A_SixCellMatrix is the frozen judgment-truth matrix (50 号 §三):
// every cell asserts BOTH implementations. Mutation probes: delete the
// window branch in s1Judge → cells 1/7 fail the s1 assertion; delete
// the window check in verify → cells 1/7 fail the verify assertion.
func TestP0A_SixCellMatrix(t *testing.T) {
	spec := loadE3Fixture(t)
	if w := anchorWindowMonths(spec); w != 6 {
		t.Fatalf("P0-A: anchored window = %d, want 6 (fixture time_window 'six calendar months')", w)
	}
	if v := anchorVetoMonths(spec); v != 3 {
		t.Fatalf("P0-A: anchored veto = %d, want 3 (rule 0 'longer than three months')", v)
	}
	cells := []struct {
		name              string
		events            []overdueEvent
		wantS1            string // s1Judge's expected verdict kind
		wantVerifyGrantOK bool   // verify(grant-50000) expected outcome
	}{
		// cell 1 — xingchao's second counterexample FORMALIZED
		// (198789782 §2 / 198789653 probe 1): a one-month overdue one
		// month ago blocks the upper band WITHOUT the veto firing —
		// the remaining outcome is the uncovered case, NOT an auto-deny.
		{"cell1-recent-short", []overdueEvent{{durationMonths: 1, monthsAgo: 1}}, "on_undefined_rule", false},
		{"cell2-historic-short", []overdueEvent{{durationMonths: 1, monthsAgo: 24}}, "grant-50000", true},
		{"cell3-recent-long", []overdueEvent{{durationMonths: 4, monthsAgo: 2}}, "deny", false},
		// cell 4 — xingchao's original counterexample A: the veto is
		// unbounded by the window.
		{"cell4-historic-long", []overdueEvent{{durationMonths: 4, monthsAgo: 24}}, "deny", false},
		{"cell5-clean-positive-control", nil, "grant-50000", true},
		{"cell7-boundary-in-inclusive", []overdueEvent{{durationMonths: 1, monthsAgo: 6}}, "on_undefined_rule", false},
		{"cell8-boundary-out", []overdueEvent{{durationMonths: 1, monthsAgo: 7}}, "grant-50000", true},
	}
	for _, c := range cells {
		t.Run(c.name, func(t *testing.T) {
			e := creditEvidence{assetMillions: 35, assetReportOK: true, overdueOnRecord: c.events}
			v := s1Judge(e)
			if v.kind != c.wantS1 {
				t.Fatalf("s1Judge = %q (%s), want %q — implementation diverges from the frozen matrix", v.kind, v.details, c.wantS1)
			}
			raw := rawEvidence{assetMillionsDeclared: 35, assetReportPresent: true, overdueOnRecord: c.events}
			cr := verify(s1Verdict{kind: "grant-50000", details: "matrix probe"}, spec, raw)
			if cr.ok != c.wantVerifyGrantOK {
				t.Fatalf("verify(grant-50000) ok=%v (%s), want %v — the seat diverges from the frozen matrix", cr.ok, cr.reason, c.wantVerifyGrantOK)
			}
			// R72 B-1 (fourth-round collision): the COMPOSED face — the
			// system must accept the judge's OWN verdict. Asserting the two
			// components separately (above) let them deadlock unnoticed:
			// on cell1/7 the judge's correct "uncovered" answer was
			// rejected by the seat, and all five kinds were rejected.
			// Separate assertions are component evidence; only the
			// composition is system evidence (R3: Accept_component ≠
			// Accept_system, here inside a single file).
			if cv := verify(v, spec, raw); !cv.ok {
				t.Fatalf("COMPOSED face: judge says %q but the seat refuses it (%s) — the system cannot accept its own correct verdict (component guarantees do not add up)", v.kind, cv.reason)
			}
		})
	}
	// cell 6 (coverage-insufficient) lives on the E2 pre-judgment face:
	// a six-month-only ledger does not satisfy the declared historical
	// source — routed for evidence, never an auto-deny.
	t.Run("cell6-coverage-insufficient", func(t *testing.T) {
		gaps := coverageGap([]string{"the declared asset valuation report submitted with the application", "the payment-history ledger of record for the overdue window"})
		if len(gaps) == 0 {
			t.Fatal("cell6: the six-month-only source list satisfied the declared historical source — the coverage face went blind under the new ontology")
		}
	})
}

// TestP0A_TermOntologyAnchored pins the ontology SPLIT itself (E3's
// blind spot closed: the three-way consistency assertion anchored the
// veto wording but never the term definition — zero consumers then).
// Mutation probe: re-embed "three months" into the term definition →
// this reds (P3's definitional absorption cannot return silently).
func TestP0A_TermOntologyAnchored(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "schema", "examples", "judgment", "valid", "judgment-spec-credit.json"))
	if err != nil {
		t.Fatal(err)
	}
	s := string(raw)
	i := strings.Index(s, "\"name\": \"overdue\"")
	if i < 0 {
		t.Fatal("P0-A term anchor: the overdue term is not declared in the fixture")
	}
	def := s[i:]
	j := strings.Index(def, "\"unit\"")
	if j < 0 {
		t.Fatal("P0-A term anchor: the overdue term has no unit field")
	}
	def = strings.ToLower(def[:j])
	if strings.Contains(def, "three months") {
		t.Fatal("P0-A term anchor: the overdue term still embeds the veto duration — P3's definitional absorption is back; the duration threshold lives in rule 0's coverage ALONE")
	}
	if !strings.Contains(def, "duration and recency") {
		t.Fatal("P0-A term anchor: the term no longer declares the duration/recency split as event attributes")
	}
	// the window scope lives in the time_window convention alone
	spec := loadE3Fixture(t)
	if !strings.Contains(strings.ToLower(spec.Conventions.TimeWindow), "six calendar months") {
		t.Fatal("P0-A term anchor: the time_window convention lost the six-month declaration")
	}
}

// TestP0A_ScanRegenerated is the R37-scan regeneration under the split
// ontology, FULLY ARCHIVED (testdata/p0a_scan.tsv — generator params +
// every row + both predicates + the S1 outcome; the R37
// reproducibility gap closed). The decisive count: window-face-only
// rows (window dirty, veto silent) — R37's "zero reachable" is
// mechanically FALSE under the restored ontology (its scan ran inside
// the P3-narrowed domain where the window face was definitionally
// absorbed).
func TestP0A_ScanRegenerated(t *testing.T) {
	var b strings.Builder
	b.WriteString("# P0-A scan — frozen generator (50 号 §一.4): durationMonths 1..6 x monthsAgo 0..30 x asset {0,5,35}\n")
	b.WriteString("# veto = durationMonths > 3 (any time); windowDirty = monthsAgo <= 6 (any duration); s1Kind = s1Judge outcome\n")
	b.WriteString("# R72 M-1: windowDirty counts INPUTS (arithmetic identity); windowDecisive (rows whose verdict changes when the event leaves the window) is the IMPLEMENTATION-relevant measure\n")
	b.WriteString("durationMonths\tmonthsAgo\tasset\tvetoFires\twindowDirty\ts1Kind\n")
	windowOnly, vetoCount, total, windowDecisive := 0, 0, 0, 0
	for d := 1; d <= 6; d++ {
		for a := 0; a <= 30; a++ {
			for _, asset := range []int{0, 5, 35} {
				events := []overdueEvent{{durationMonths: d, monthsAgo: a}}
				veto := d > 3
				dirty := a <= 6
				kind := s1Judge(creditEvidence{assetMillions: asset, assetReportOK: true, overdueOnRecord: events}).kind
				b.WriteString(strconv.Itoa(d) + "\t" + strconv.Itoa(a) + "\t" + strconv.Itoa(asset) + "\t" + b2s(veto) + "\t" + b2s(dirty) + "\t" + kind + "\n")
				total++
				if veto {
					vetoCount++
				}
				if dirty && !veto {
					windowOnly++
				}
				// R72 M-1 (fourth-round collision): windowOnly is an
				// ARITHMETIC identity (3 durations x 7 recencies x 3
				// assets) — it counts inputs, not implementation behaviour
				// (asset=0 falls into the lower band, asset=5 into the
				// between-bands route; neither ever consults the window).
				// The implementation-relevant measure is DECISIVENESS:
				// push the event out of the window and see whether the
				// judge's verdict changes.
				moved := []overdueEvent{{durationMonths: d, monthsAgo: 999}}
				if s1Judge(creditEvidence{assetMillions: asset, assetReportOK: true, overdueOnRecord: moved}).kind != kind {
					windowDecisive++
				}
			}
		}
	}
	if windowOnly <= 0 {
		t.Fatalf("P0-A scan: window-face-only rows = %d — the window face is again unreachable (R37's condition has returned)", windowOnly)
	}
	// R72 M-1: the claim that must hold is the IMPLEMENTATION-relevant one.
	if windowDecisive <= 0 {
		t.Fatalf("P0-A scan: window-DECISIVE rows = %d — the window predicate changes no verdict; the face is arithmetically present but behaviourally inert", windowDecisive)
	}
	out := b.String()
	archived, err := os.ReadFile("testdata/p0a_scan.tsv")
	if err != nil {
		if err := os.MkdirAll("testdata", 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile("testdata/p0a_scan.tsv", []byte(out), 0o644); err != nil {
			t.Fatal(err)
		}
		t.Logf("archived on first run: %d rows, windowOnly=%d (inputs), windowDecisive=%d (implementation-relevant), veto=%d", total, windowOnly, windowDecisive, vetoCount)
		return
	}
	if string(archived) != out {
		t.Fatal("P0-A scan drift: the archived scan differs from the regenerated one — regenerate deliberately and review the diff (the archive is the record, not the mirror)")
	}
}

func b2s(b bool) string {
	if b {
		return "1"
	}
	return "0"
}
