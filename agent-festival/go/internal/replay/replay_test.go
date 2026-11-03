package replay

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

func loadCase(t *testing.T, name string) *Case {
	t.Helper()
	if SchemaPath == "" {
		t.Fatal("replay-case schema not found")
	}
	full := filepath.Join(filepath.Dir(SchemaPath), "examples", "replay", "valid", name)
	c, fatalf := loadCasePath(t, full)
	if fatalf != "" {
		t.Fatal(fatalf)
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
	for _, name := range []string{"race-outcome-a-first.json", "race-outcome-b-first.json", "happy-chain.json", "unknown-field-in-record.json"} {
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
	if err == nil || !strings.Contains(err.Error(), "steps domain") {
		t.Fatalf("hostile closure: err = %v, want the domain refusal (the guard fires before any report)", err)
	}
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
	if _, err := drive(m, c.Steps[:1]); err != nil { // the package's driver — no hand-rolled adopt arm
		t.Fatal(err)
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

// TestRawCaseDocRewriteRefused pins the rawCaseDoc arm of the mode-3 guard
// (R7: the arm had zero pins — deleting it stayed green). A closure that
// rewrites ONLY the document view (record untouched) hits the frozen-view
// refusal.
func TestRawCaseDocRewriteRefused(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	_, err := Reevaluate(c, func(sub *Case) {
		delete(sub.rawCaseDoc, "expected") // document view only; record untouched
	})
	if err == nil || !strings.Contains(err.Error(), "raw document view") {
		t.Fatalf("document-view rewrite: err = %v, want the frozen-view refusal", err)
	}
}

// TestOperationSetLockstep pins the op vocabulary's two machine copies
// (schema enum ↔ drive's switch) against drift (R9: only one-sided edits
// stayed green). Every schema-enum member must be KNOWN to drive (no
// "unknown op" refusal); every non-member must be refused — the invented-op
// fixture pins that direction at the suite layer.
func TestOperationSetLockstep(t *testing.T) {
	raw, err := os.ReadFile(SchemaPath)
	if err != nil {
		t.Fatal(err)
	}
	var s struct {
		Properties struct {
			Steps struct {
				Items struct {
					Properties struct {
						Op struct {
							Enum []string `json:"enum"`
						} `json:"op"`
					} `json:"properties"`
				} `json:"items"`
			} `json:"steps"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(raw, &s); err != nil {
		t.Fatal(err)
	}
	if len(s.Properties.Steps.Items.Properties.Op.Enum) == 0 {
		t.Fatal("schema op enum not found — the lockstep test itself is broken")
	}
	m, err := adopt.Open(filepath.Join(t.TempDir(), "scratch.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	// the Go-side operation set, declared once — bidirectional: every enum
	// member is known to drive AND every known op is an enum member (a
	// schema-side deletion or drive-side addition both go red here)
	goOps := map[string]bool{"adopt": true, "dispatch": true, "mark_unresolved": true, "mark_completed": true, "mark_failed": true}
	enum := s.Properties.Steps.Items.Properties.Op.Enum
	if len(enum) != len(goOps) {
		t.Fatalf("op vocabulary drifted: schema enum has %d members, the Go-side set has %d", len(enum), len(goOps))
	}
	for _, op := range enum {
		if !goOps[op] {
			t.Fatalf("schema enum member %q is not in the Go-side op set — the copies drifted", op)
		}
	}
	for _, op := range s.Properties.Steps.Items.Properties.Op.Enum {
		_, derr := drive(m, []Step{{Op: op}}) // minimal step: param errors are fine, "unknown op" is not
		if derr != nil && strings.Contains(derr.Error(), "unknown op") {
			t.Fatalf("schema enum member %q refused by drive as unknown — the vocabulary copies drifted", op)
		}
	}
	_, derr := drive(m, []Step{{Op: "definitely-not-an-op"}})
	if derr == nil || !strings.Contains(derr.Error(), "unknown op") {
		t.Fatal("a non-member passed drive's switch — the refusal direction drifted")
	}
	// Coverage statement (honest form, R12): the checks above prove
	// enum↔goOps SET EQUALITY and the enum→drive direction (every enum
	// member is known to drive) plus the non-member refusal. The growth
	// direction (drive's switch growing an arm that NEITHER set has) is
	// structurally unprovable from outside the switch — deleting an arm is
	// caught (the enum loop hits it), growing one is not; the set-equality
	// check is the declared boundary of this lockstep.
}

// TestReplayPropagatesDriveErrors pins the propagation leg (R8: the drive
// guards had pins, but swallowing the error INSIDE Replay stayed green):
// hostile steps reaching Replay through LoadCase return the drive error —
// never a forged divergence report over a silent empty stream.
func TestReplayPropagatesDriveErrors(t *testing.T) {
	digest := "sha256:" + strings.Repeat("a", 64)
	// a fully VALID raw doc (passes the raw-view schema), with the hostility
	// injected into the TYPED steps after LoadCase — only the typed steps
	// carry the unknown op to drive
	doc := map[string]any{
		"case_version": "0.1.0", "case_id": "hostile",
		"steps": []any{map[string]any{"op": "adopt", "request": map[string]any{
			"adoption_version": "0.1.0",
			"identity":         map[string]any{"business_request_id": "b", "operation_id": "o"},
			"versions":         map[string]any{"evidence": "e", "rule": "r", "model": "m", "readout": "ro", "policy": "p"},
			"payload_digest":   digest,
			"grants_at_decision": []any{map[string]any{"kind": "data", "selector": "s",
				"actions": []any{"read"}, "effect": "none"}},
		}}},
		"recorded_events": []any{map[string]any{"event_type": "adoption", "arbitration_seq": 0,
			"identity":    map[string]any{"business_request_id": "b", "operation_id": "o"},
			"versions":    map[string]any{"evidence": "e", "rule": "r", "model": "m", "readout": "ro", "policy": "p"},
			"outcome":     map[string]any{"status": "adopted"},
			"idempotency": map[string]any{"operation_id": "o", "payload_digest": digest}}},
		"expected": map[string]any{"fidelity": "match", "conformance": "pass"},
	}
	c, err := LoadCase(doc)
	if err != nil {
		t.Fatal(err)
	}
	c.Steps = []Step{{Op: "re-execute-everything"}}
	_, err = Replay(c)
	if err == nil || !strings.Contains(err.Error(), "unknown op") {
		t.Fatalf("hostile steps through Replay: err = %v, want the propagated drive refusal — a forged divergence@0 report means the propagation leg regressed", err)
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
	if _, err := drive(m, c.Steps); err != nil { // the package's own driver — no second switch copy
		t.Fatal(err)
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
	// and the OTHER fact word: a record ending in reused projects reused
	// (R7: conflict was pinned, reused was not — a drifted vocabulary
	// missing it stayed green)
	c2 := loadCase(t, "race-outcome-a-first.json")
	path2 := filepath.Join(t.TempDir(), "adopt-a.jsonl")
	m2, err := adopt.Open(path2)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := drive(m2, c2.Steps); err != nil { // the package's own driver — no second copy
		t.Fatal(err)
	}
	rep2, err := Inspect(path2)
	if err != nil {
		t.Fatal(err)
	}
	if rep2.States["op-a"] != "reused" {
		t.Fatalf("reused tail projection = %q, want the reused fact word", rep2.States["op-a"])
	}
}

// TestScratchWriteFailureIsLoud pins the WRITE-path fail-loud guard (R11:
// the fix was real and triggerable but unpinned — reverting stayed green).
// A read-only scratch directory makes the machine's append fail; Replay
// must return that error, never a forged divergence verdict. This pin also
// carries the cross-package string lockstep: adopt's refusal detail must
// keep carrying "ledger append failed" for replay to see it.
func TestScratchWriteFailureIsLoud(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory write permissions — the read-only scratch setup cannot bite here")
	}
	roDir := filepath.Join(t.TempDir(), "ro")
	if err := os.Mkdir(roDir, 0o500); err != nil { // write-denied directory
		t.Fatal(err)
	}
	path := filepath.Join(roDir, "scratch.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Skipf("cannot set up read-only scratch: %v", err)
	}
	digest := "sha256:" + strings.Repeat("a", 64)
	_, derr := drive(m, []Step{{Op: "adopt", Request: mustAdoptRequest(t, "op-w", digest)}})
	if derr == nil || !strings.Contains(derr.Error(), "scratch write failed") {
		t.Fatalf("scratch write failure: err = %v, want the loud write-path refusal (a forged verdict means the guard regressed or adopt's detail wording drifted)", derr)
	}
}

// mustAdoptRequest marshals a minimal valid adoption request.
func mustAdoptRequest(t *testing.T, op, digest string) json.RawMessage {
	t.Helper()
	req := adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-w", OperationID: op},
		Versions:         ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:    digest,
		GrantsAtDecision: []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}},
	}
	b, err := json.Marshal(req)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestLoadCaseRefusesFoldedNumbers pins the structural UseNumber discipline
// (R11: it was comment-only — a float64-decoded doc must be refused).
func TestLoadCaseRefusesFoldedNumbers(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	// re-decode the raw recorded view the float64 way
	b, _ := json.Marshal(c.RecordedRawDoc)
	var folded []any
	json.Unmarshal(b, &folded)
	doc := map[string]any{"case_version": "0.1.0", "case_id": "folded",
		"steps": c.Steps, "recorded_events": folded, "expected": c.Expected}
	_, err := LoadCase(doc)
	if err == nil || !strings.Contains(err.Error(), "UseNumber") {
		t.Fatalf("float-folded recorded doc: err = %v, want the discipline refusal", err)
	}
}

// TestLoadCaseRefusesBadPinnedFixture pins loadCase's ParseError
// consumption arm (R12: R11's version called suite.Load directly — the
// arm stayed dead; deleting it stayed green). The poison fixture goes
// through loadCase itself.
func TestLoadCaseRefusesBadPinnedFixture(t *testing.T) {
	dir := t.TempDir()
	poison := filepath.Join(dir, "poison.json")
	if err := os.WriteFile(poison, []byte(`{"case_version":"0.1.0","case_id":"p","_expect_match":5}`), 0o644); err != nil {
		t.Fatal(err)
	}
	loaded, died := loadCasePath(t, poison)
	if loaded != nil {
		t.Fatal("a wrong-typed pin loaded silently — the hardened contract is bypassed")
	}
	if !strings.Contains(died, "fail loud") {
		t.Fatalf("refusal text = %q, want the hardened-contract refusal", died)
	}
}

// loadCasePath is loadCase for an arbitrary path — the shared loader plus
// the ParseError consumption arm, factored so the arm is testable.
func loadCasePath(t *testing.T, path string) (c *Case, fatalf string) {
	t.Helper()
	fx, err := suite.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError != "" {
		return nil, fmt.Sprintf("fixture %s: %s (the hardened loader's contract: fail loud, never run unpinned)", filepath.Base(path), fx.ParseError)
	}
	c, err = LoadCase(fx.Doc)
	if err != nil {
		t.Fatal(err)
	}
	return c, ""
}

// TestRecoverDoesNotDispatchAdoptedWork pins the never-dispatch boundary on
// the DISPATCHABLE shape (R12: the existing pin's record ended unresolved,
// where Dispatch is refused anyway — the boundary was untested where it
// actually bites).
func TestRecoverDoesNotDispatchAdoptedWork(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	digest := "sha256:" + strings.Repeat("a", 64)
	grants := []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}}
	m.Adopt(&adopt.Request{
		AdoptionVersion: "0.1.0",
		Identity:        ledger.Identity{BusinessRequestID: "br-d", OperationID: "op-d"},
		Versions:        ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:   digest, GrantsAtDecision: grants,
	})
	rep, err := Recover(path)
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-d"] != "adopted" {
		t.Fatalf("recovered state = %q, want adopted (dispatchable)", rep.States["op-d"])
	}
	events, _ := m.Events()
	if len(events) != 1 {
		t.Fatalf("Recover moved a dispatchable operation: %d events, want 1 — the never-dispatch boundary regressed", len(events))
	}
}

// TestGrantSubdimensions pins the grants dimension's three UNPINNED sub-legs
// (R15: only Selector had a tamper arm — Kind/Effect/Actions tampering
// stayed invisible to fidelity).
func TestGrantSubdimensions(t *testing.T) {
	tamper := func(name string, f func(ev []ledger.Event)) {
		t.Run(name, func(t *testing.T) {
			c := loadCase(t, "happy-chain.json")
			f(c.RecordedEvents)
			rep, err := Replay(c)
			if err != nil {
				t.Fatal(err)
			}
			if rep.Fidelity != Divergence {
				t.Fatalf("%s tamper not caught — fidelity=%q (the sub-leg is blind)", name, rep.Fidelity)
			}
		})
	}
	tamper("kind", func(ev []ledger.Event) { ev[0].GrantsAtDecision[0].Kind = "secret" })
	tamper("effect", func(ev []ledger.Event) { ev[0].GrantsAtDecision[0].Effect = "irreversible" })
	tamper("actions", func(ev []ledger.Event) { ev[0].GrantsAtDecision[0].Actions = []string{"write"} })
}

// TestReportSelfDescription pins the report fields that describe their own
// subject (R16: five lazy fields had no reader — Path/CaseID get their
// one-line assertions here; Recorded rides Recomputed's comparison and is
// covered by every fidelity test).
func TestReportSelfDescription(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	dir := t.TempDir()
	path := filepath.Join(dir, "desc.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := drive(m, c.Steps); err != nil {
		t.Fatal(err)
	}
	insp, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if insp.Path != path {
		t.Fatalf("InspectReport.Path = %q, want the inspected path (self-description broke)", insp.Path)
	}
	rec, err := Recover(path)
	if err != nil {
		t.Fatal(err)
	}
	if rec.Path != path {
		t.Fatalf("RecoverReport.Path = %q, want the recovered path", rec.Path)
	}
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.CaseID != "happy" {
		t.Fatalf("ReplayReport.CaseID = %q, want the case's own id", rep.CaseID)
	}
	if len(rep.Recorded) != len(c.RecordedEvents) {
		t.Fatalf("ReplayReport.Recorded = %d events, want the record carried for audit", len(rep.Recorded))
	}
}
