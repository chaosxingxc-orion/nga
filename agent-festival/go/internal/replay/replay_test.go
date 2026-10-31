package replay

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"festival-dev/go/internal/adopt"
	"festival-dev/go/internal/ledger"
)

func loadCase(t *testing.T, name string) *Case {
	t.Helper()
	if SchemaPath == "" {
		t.Fatal("replay-case schema not found")
	}
	raw, err := os.ReadFile(filepath.Join(filepath.Dir(SchemaPath), "examples", "replay", "valid", name))
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber() // ledger.Errors input discipline: integers must survive the map domain
	if err := dec.Decode(&doc); err != nil {
		t.Fatal(err)
	}
	delete(doc, "_expect") // fixture pins pop before validation (suite.Load discipline)
	delete(doc, "_expect_match")
	c, err := LoadCase(doc)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

// TestRecomputeIsNotPlayback is the machine-checked form of pre-registered
// attack surface B: a real PLAYBACK engine — one that "verifies" by
// returning the record as its own recomputation — matches the
// tampered-conclusion fixture and catches nothing, while Replay recomputes
// by driving the production machine and diverges at the tampered event.
// The playback arm is executable (a literal engine function), not a narrated
// constant.
func TestRecomputeIsNotPlayback(t *testing.T) {
	c := loadCase(t, "tampered-conclusion.json")

	// the playback engine: recomputation == the record, by construction
	playback := func(c *Case) *ReplayReport {
		return &ReplayReport{CaseID: c.CaseID, Recomputed: c.RecordedEvents, Recorded: c.RecordedEvents, Fidelity: Match, DivergenceAt: -1}
	}
	pb := playback(c)
	if pb.Fidelity != Match {
		t.Fatal("playback engine misconstructed — it must match by construction")
	}

	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Divergence {
		t.Fatalf("replay fidelity = %q, want divergence — the recomputation degraded into playback", rep.Fidelity)
	}
	if rep.DivergenceAt != 2 {
		t.Fatalf("divergence located at %d, want 2 (the tampered conclusion event)", rep.DivergenceAt)
	}
	if rep.Conformance != Pass {
		t.Fatalf("conformance = %q, want pass (completed→failed is legal — only recomputation catches it)", rep.Conformance)
	}
}

// TestReevaluateSubstitutionIsolates pins mode 3: under FULL-field
// comparison a version substitution IS material — the recomputed stream's
// versions field changes (that is what mode 3 exists to surface), located
// at event 0; a substitution that breaks a step's operability diverges the
// streams; and the original case is untouched.
func TestReevaluateSubstitutionIsolates(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	orig, _ := json.Marshal(c)
	rep, err := Reevaluate(c, func(sub *Case) {
		for i := range sub.Steps {
			if sub.Steps[i].Op == "adopt" {
				var m map[string]any
				json.Unmarshal(sub.Steps[i].Request, &m)
				m["versions"].(map[string]any)["model"] = "m-2"
				sub.Steps[i].Request, _ = json.Marshal(m)
			}
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	// full-field comparison: a version substitution IS material — the
	// recomputed stream's versions field changes (that is what mode 3
	// exists to surface: intended differences), located at event 0.
	if !rep.Changed || rep.At != 0 {
		t.Fatalf("version substitution should change the recomputation at event 0, got changed=%v at=%d", rep.Changed, rep.At)
	}
	if rep.BaseFidelity != Match || rep.BaseConformance != Pass {
		t.Fatalf("baseline verdicts wrong: %+v", rep)
	}
	rep2, err := Reevaluate(c, func(sub *Case) {
		sub.Steps[1].OpID = "op-nonexistent"
	})
	if err != nil {
		t.Fatal(err)
	}
	if !rep2.Changed || rep2.At < 0 {
		t.Fatalf("material substitution (dispatch a different op) should change the recomputation at a located event, got changed=%v at=%d", rep2.Changed, rep2.At)
	}
	if string(orig) != string(mustMarshal(t, c)) {
		t.Fatal("Reevaluate mutated the original case — mode 3 must be isolated")
	}
}

// TestMutatedInputDivergenceLocated pins family (b)'s location in the unit
// test layer (the suite-level divergence_at check rides the cmd checker;
// this makes the pin load-bearing here too — deleting either catches it).
func TestMutatedInputDivergenceLocated(t *testing.T) {
	c := loadCase(t, "mutated-input-located.json")
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Divergence || rep.DivergenceAt != 1 {
		t.Fatalf("family (b): fidelity=%q at=%d, want divergence at 1", rep.Fidelity, rep.DivergenceAt)
	}
}

// TestIdentityOnlyDivergence pins the identity comparison dimension (the
// deletion-probe found no fixture exercised it — a record whose operation
// identity differs from the recomputation's must diverge at event 0).
func TestIdentityOnlyDivergence(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	for i := range c.RecordedEvents {
		c.RecordedEvents[i].Identity.OperationID = "op-swapped"
	}
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Divergence || rep.DivergenceAt != 0 {
		t.Fatalf("identity-only divergence: fidelity=%q at=%d, want divergence at 0", rep.Fidelity, rep.DivergenceAt)
	}
}

func mustMarshal(t *testing.T, c *Case) []byte {
	t.Helper()
	b, err := json.Marshal(c)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestInspectProjectsAndExposesGaps pins mode 1: the projection reducer
// rebuilds states from the record and exposes the ledger checker's gaps —
// no recomputation (a bypassed record's gap shows up here, not in Replay).
func TestInspectProjectsAndExposesGaps(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	rep, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(rep.Events) != 0 || len(rep.Gaps) != 0 {
		t.Fatalf("empty ledger should project empty, got %d events / %d gaps", len(rep.Events), len(rep.Gaps))
	}
	// build a real record then inspect it
	digest := "sha256:" + strings.Repeat("a", 64)
	if o := m.Adopt(&adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-i", OperationID: "op-i"},
		Versions:         ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:    digest,
		GrantsAtDecision: []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}},
	}); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	rep, err = Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-i"] != "adopted" {
		t.Fatalf("projection state = %q, want adopted", rep.States["op-i"])
	}
	if len(rep.Gaps) != 0 {
		t.Fatalf("machine-written record has gaps: %v", rep.Gaps)
	}
}

// TestRecoversToDispatchableNotBeyond pins mode 4: recovery restores machine
// state from the durable record and reports reconciliation exits — it never
// dispatches (0.1.0 boundary: dispatching is the gate's live-effect
// authority).
func TestRecoversToDispatchableNotBeyond(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	digest := "sha256:" + strings.Repeat("a", 64)
	grants := []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}}
	m.Adopt(&adopt.Request{
		AdoptionVersion: "0.1.0",
		Identity:        ledger.Identity{BusinessRequestID: "br-r", OperationID: "op-r"},
		Versions:        ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:   digest, GrantsAtDecision: grants,
	})
	m.Dispatch("op-r", grants)
	m.MarkUnresolved("op-r")

	rep, err := Recover(path)
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-r"] != "unresolved" {
		t.Fatalf("recovered state = %q, want unresolved", rep.States["op-r"])
	}
	if len(rep.Unresolved) != 1 || !strings.Contains(rep.Unresolved[0], "never re-dispatch") {
		t.Fatalf("reconciliation exit report wrong: %v", rep.Unresolved)
	}
	events, _ := m.Events()
	if len(events) != 3 {
		t.Fatalf("Recover wrote to the durable form: %d events", len(events))
	}
}

// TestInspectExposesGapsInViolatingRecord pins the projection's gap arm
// (R1: both test ledgers were clean — the exposing path had zero coverage).
func TestInspectExposesGapsInViolatingRecord(t *testing.T) {
	path := filepath.Join(t.TempDir(), "violating.jsonl")
	// a hand-written violating record: an effect event with no adoption
	// predecessor (the bypass shape the eight families reject)
	line := `{"event_type":"effect","arbitration_seq":0,"identity":{"business_request_id":"br-x","operation_id":"op-x"},"versions":{"evidence":"e","rule":"r","model":"m","readout":"ro","policy":"p"},"outcome":{"status":"dispatched"},"idempotency":{"operation_id":"op-x","payload_digest":"sha256:` + strings.Repeat("a", 64) + `"}}`
	if err := os.WriteFile(path, []byte(line+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	rep, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(rep.Gaps) == 0 {
		t.Fatal("a violating record projected to zero gaps — Inspect's gap arm is blind")
	}
	if !strings.Contains(rep.Gaps[0], "bypass write") {
		t.Fatalf("gap reported for the wrong reason: %v", rep.Gaps[0])
	}
}

// TestMachineProducedFixtures pins the anti-rot mechanism (collision
// ruling): the race fixtures' records are reproducible by driving the
// production machine through the same steps — hand-written records that
// drift from machine behavior fail here.
func TestMachineProducedFixtures(t *testing.T) {
	for _, name := range []string{"race-outcome-a-first.json", "race-outcome-b-first.json", "happy-chain.json"} {
		c := loadCase(t, name)
		rep, err := Replay(c)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if rep.Fidelity != Match {
			t.Fatalf("%s: machine could not reproduce the fixture record (%s) — fixture drifted from machine behavior", name, rep.Detail)
		}
	}
}

// TestSingleDimensionTampering pins the four comparison dimensions whose
// deletion stayed green at R2 (grants / accountability / event_type / seq):
// each test tampers ONE dimension of the record and requires divergence at
// a located event — the R1-B2 attack surface stays pinnable.
func TestSingleDimensionTampering(t *testing.T) {
	tamper := func(name string, f func(events []ledger.Event)) {
		t.Run(name, func(t *testing.T) {
			c := loadCase(t, "happy-chain.json")
			f(c.RecordedEvents)
			rep, err := Replay(c)
			if err != nil {
				t.Fatal(err)
			}
			if rep.Fidelity != Divergence {
				t.Fatalf("%s tamper not caught — fidelity=%q (the comparison dimension is blind)", name, rep.Fidelity)
			}
		})
	}
	tamper("grants", func(ev []ledger.Event) { ev[0].GrantsAtDecision[0].Selector = "ledger://evil" })
	tamper("accountability", func(ev []ledger.Event) { ev[0].Accountability.Session = "s-evil" })
	tamper("event_type", func(ev []ledger.Event) { ev[1].EventType = "adoption" })
	tamper("arbitration_seq", func(ev []ledger.Event) { ev[1].ArbitrationSeq = 9 })
}

// TestUnknownFieldRecordIsMatchPlusFail pins the match+fail quadrant through
// the unknown-field channel (R2's finding: the "unreachable" claim was
// false) — and doubles as the regression pin for the RAW conformance arm
// (a typed/laundered judgment would pass the record).
func TestUnknownFieldRecordIsMatchPlusFail(t *testing.T) {
	c := loadCase(t, "unknown-field-in-record.json")
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Match || rep.Conformance != Fail {
		t.Fatalf("quadrant = %s/%s, want match/fail (typed fields equal + smuggled property rejected by the raw arm)", rep.Fidelity, rep.Conformance)
	}
}

// TestIsolationCoversRawViews pins the M5 fix (R3): a substitution closure
// that mutates the substitute's raw views must not reach the original
// case's raw conformance inputs — the isolation contract covers the raw
// layer, and the assertion compares the raw views DIRECTLY (a json.Marshal
// of the Case is blind to the json:"-" fields).
func TestIsolationCoversRawViews(t *testing.T) {
	c := loadCase(t, "unknown-field-in-record.json")
	rawRecBefore, _ := json.Marshal(c.RecordedRawDoc)
	rawCaseBefore, _ := json.Marshal(c.rawCaseDoc)
	_, err := Reevaluate(c, func(sub *Case) {
		// hostile closure: rewrite the substitute's raw views in place
		if len(sub.RecordedRawDoc) > 0 {
			if last, ok := sub.RecordedRawDoc[len(sub.RecordedRawDoc)-1].(map[string]any); ok {
				delete(last, "smuggled")
			}
		}
		sub.RecordedRawDoc = sub.RecordedRawDoc[:0]
		delete(sub.rawCaseDoc, "expected") // IN-PLACE mutation — a rebound map would never reach the original
	})
	_ = err // the hostile closure breaking the substitute is expected; the assertion is about the ORIGINAL
	rawRecAfter, _ := json.Marshal(c.RecordedRawDoc)
	rawCaseAfter, _ := json.Marshal(c.rawCaseDoc)
	if string(rawRecBefore) != string(rawRecAfter) {
		t.Fatal("a substitution closure reached the original case's RecordedRawDoc — isolation does not cover the raw layer")
	}
	if string(rawCaseBefore) != string(rawCaseAfter) {
		t.Fatal("a substitution closure reached the original case's raw case view — isolation does not cover the raw layer")
	}
}

// TestMissingRawViewsRefuseJudgment pins the two fail-loud guards (R3:
// deleting either stayed green): a hand-built Case without the raw views is
// REFUSED — schema validation and the conformance arm never judge a
// laundered projection silently.
func TestMissingRawViewsRefuseJudgment(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	// strip both raw views (hand-built Case shape)
	stripped := &Case{
		CaseVersion: c.CaseVersion, CaseID: c.CaseID,
		Steps: c.Steps, RecordedEvents: c.RecordedEvents, Expected: c.Expected,
	}
	_, err := Replay(stripped)
	if err == nil || !strings.Contains(err.Error(), "raw case view") {
		t.Fatalf("missing rawCaseDoc (checked first): err = %v, want the laundering refusal", err)
	}
	withCase := *stripped
	withCase.rawCaseDoc = c.rawCaseDoc // raw case view present, raw recorded still missing
	_, err = Replay(&withCase)
	if err == nil || !strings.Contains(err.Error(), "raw recorded view") {
		t.Fatalf("missing RecordedRawDoc: err = %v, want the laundering refusal", err)
	}
}

// TestDriveGuardsRefuseLoudly pins the two fail-loud drive guards (R4:
// deleting either stayed green): an unknown op and an undecodable adopt
// request propagate as errors — never silently skipped steps.
func TestDriveGuardsRefuseLoudly(t *testing.T) {
	m, err := adopt.Open(filepath.Join(t.TempDir(), "scratch.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := drive(m, []Step{{Op: "re-execute-everything"}}); err == nil ||
		!strings.Contains(err.Error(), "unknown op") {
		t.Fatalf("unknown op: err = %v, want the loud refusal", err)
	}
	if _, err := drive(m, []Step{{Op: "adopt", Request: json.RawMessage(`{"identity": 5}`)}}); err == nil ||
		!strings.Contains(err.Error(), "undecodable") {
		t.Fatalf("undecodable request: err = %v, want the loud refusal", err)
	}
}

// TestInspectByOperationProjection pins the by-operation projection (R3:
// zero consumers made it dead weight — it is the audit view, assert it).
func TestInspectByOperationProjection(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	var req adopt.Request
	if err := json.Unmarshal(c.Steps[0].Request, &req); err != nil {
		t.Fatal(err)
	}
	if o := m.Adopt(&req); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	rep, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(rep.ByOperation["op-h"]) != 1 {
		t.Fatalf("by-operation projection = %v, want one event for op-h", rep.ByOperation["op-h"])
	}
}

// TestIdempotencySingleDimension pins the one comparison dimension whose
// only guard lived at the cmd-suite layer (R5): tampering the record's
// payload digest alone must diverge.
func TestIdempotencySingleDimension(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	for i := range c.RecordedEvents {
		if c.RecordedEvents[i].Idempotency != nil {
			c.RecordedEvents[i].Idempotency.PayloadDigest =
				"sha256:" + strings.Repeat("e", 64)
		}
	}
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Divergence {
		t.Fatalf("idempotency tamper not caught — fidelity=%q (the dimension is blind)", rep.Fidelity)
	}
}

// TestReevaluateRefusesRecordRewrites pins the mode-3 boundary guard (R5:
// "steps-substitutions cannot change the record" was convention, not
// structure — the closure signature reaches the record).
func TestReevaluateRefusesRecordRewrites(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	_, err := Reevaluate(c, func(sub *Case) {
		sub.RecordedEvents = sub.RecordedEvents[:0]
	})
	if err == nil || !strings.Contains(err.Error(), "steps domain") {
		t.Fatalf("record-rewriting substitution: err = %v, want the loud domain refusal", err)
	}
}

// TestRawChannelRewriteRefused pins the R6 finding: a substitution closure
// rewriting the substitute's RAW views (leaving the typed events intact)
// must hit the domain refusal — the guard covers the record's judged form,
// not only its typed projection.
func TestRawChannelRewriteRefused(t *testing.T) {
	c := loadCase(t, "unknown-field-in-record.json")
	_, err := Reevaluate(c, func(sub *Case) {
		if len(sub.RecordedRawDoc) > 0 {
			if last, ok := sub.RecordedRawDoc[len(sub.RecordedRawDoc)-1].(map[string]any); ok {
				delete(last, "smuggled") // raw rewrite, typed events untouched
			}
		}
	})
	if err == nil || !strings.Contains(err.Error(), "steps domain") {
		t.Fatalf("raw-channel rewrite: err = %v, want the loud domain refusal", err)
	}
}

// TestInspectStatesTailProjection pins the States semantics AND the ledger
// vocabulary derivation (R6: both had zero pins — a drifted inline table
// stayed green). A record ending in conflict projects the fact word, and
// the vocabulary is the ledger's, not a fifth copy.
func TestInspectStatesTailProjection(t *testing.T) {
	c := loadCase(t, "race-outcome-b-first.json") // ends in a conflict event
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	// drive the same steps to produce the durable record
	for _, s := range c.Steps {
		switch s.Op {
		case "adopt":
			var req adopt.Request
			if err := json.Unmarshal(s.Request, &req); err != nil {
				t.Fatal(err)
			}
			m.Adopt(&req)
		}
	}
	rep, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	// the record's last event for op-a is the conflict FACT — the tail
	// projection names it; the machine state (Recover's view) stays adopted
	if rep.States["op-a"] != "conflict" {
		t.Fatalf("tail projection = %q, want the conflict fact word", rep.States["op-a"])
	}
	rec, err := Recover(path)
	if err != nil {
		t.Fatal(err)
	}
	if rec.States["op-a"] != "adopted" {
		t.Fatalf("machine state = %q, want adopted — States semantics fork between Inspect (tail fact) and Recover (machine state) must be visible", rec.States["op-a"])
	}
}
