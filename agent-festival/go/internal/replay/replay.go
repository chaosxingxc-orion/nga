// Package replay is piece 6: the four replay modes as four non-interchangeable
// structured entry points (current proposal §8). The package is a READ-ONLY
// consumer of the growth layer: it never writes a durable ledger.
//
// Two engine families, deliberately split (frame-bench collision ruling A):
// Inspect is a PROJECTION reducer — a second implementation that rebuilds a
// view from the record without recomputing decisions (codex rollout-trace
// precedent: projections stay outside the core); Replay and Reevaluate are
// RE-EXECUTION — they drive the production state machine (a fresh in-memory
// adopt.Machine) through the recorded steps and only the recorded-family
// boundary is supplied from the case (langgraph time-travel / dsh-llm-replay
// "booting the real agent" precedent). The machine grows no replay-only
// branch (the no-hidden-entrypoint rule).
//
// Invariant-1 split narration (the priors' three-layer rule): DECISIONS
// (gate/idempotence rulings) never pass through a model — they are
// recomputed deterministically here; OBSERVATIONS (S1 semantic judgments)
// may pass through a model in production but enter the recomputation as
// RECORDS, never as fresh inference.
//
// The two verdicts are separate contracts (legacy 12号 §3 tail semantics):
// fidelity — did recomputation reproduce the record? conformance — does the
// record itself pass the ledger's eight rule families? All four quadrants
// are legal outcomes; a replay of a recorded violation is fidelity-match +
// conformance-fail. No ecosystem precedent defines the double-verdict
// runner output contract — this package is that contract's first machine
// form, and the fixture corpus pins all four quadrants.
//
// Arbitration (collision ruling B, narrowed): re-execution consumes the
// RECORDED arbitration order — it never re-arbitrates (legacy semantics,
// drift register L5). This applies to true adjudication results only (the
// adopt race's first-wins outcome); purely-ordered events that a stable key
// could sort must not enter arbitration records.
//
// Known limitation (recorded, not pretended solved — dsh precedent): a
// case whose steps race the SAME operation concurrently binds
// non-deterministically in production; such cases must encode one recorded
// arbitration outcome per case (family e's two-outcome fixtures), not
// expect the re-execution to reproduce both.
package replay

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"

	"festival-dev/go/internal/adopt"
	"festival-dev/go/internal/ledger"
	"festival-dev/go/internal/schemalib"
)

// SchemaPath is where replay-case.schema.json was found ("" = not found).
var SchemaPath = schemalib.FindSchema("replay-case.schema.json")

var caseSchema = schemalib.NewLazy(
	"https://agent-festival.local/schema/replay-case/0.1.0", SchemaPath)

// Verdict is one half of the double verdict.
type Verdict string

const (
	Match      Verdict = "match"
	Divergence Verdict = "divergence"
	Pass       Verdict = "pass"
	Fail       Verdict = "fail"
)

// InspectReport is mode 1's projection: the reconstructed state view plus
// the record's gaps (the ledger checker's full report). No recomputation.
type InspectReport struct {
	Path        string
	Events      []ledger.Event
	States      map[string]string // operation id -> final state in the record
	Gaps        []string          // ledger.Errors over the record
	ByOperation map[string][]ledger.Event
}

// Inspect is mode 1: historical inspection — reconstruct retained history
// and expose missing evidence; no live effects, no recomputation. It is a
// projection reducer (second implementation by design).
func Inspect(path string) (*InspectReport, error) {
	lines, err := ledger.LoadDocument(path)
	if err != nil {
		return nil, err
	}
	r := &InspectReport{Path: path, States: map[string]string{}, ByOperation: map[string][]ledger.Event{}}
	if len(lines) == 0 {
		return r, nil // no record: nothing to project, no gaps to expose
	}
	doc := map[string]any{"ledger_version": ledger.Version}
	events := make([]any, 0, len(lines))
	for _, l := range lines {
		events = append(events, l.Doc)
	}
	doc["events"] = events
	r.Gaps = ledger.Errors(doc)
	for _, l := range lines {
		r.Events = append(r.Events, l.Event)
		op := l.Event.Identity.OperationID
		r.ByOperation[op] = append(r.ByOperation[op], l.Event)
		if s := l.Event.Outcome.Status; s == "adopted" || s == "dispatched" ||
			s == "unresolved" || s == "completed" || s == "failed" {
			r.States[op] = s
		}
	}
	return r, nil
}

// Step is one recorded input: the call that drove the machine.
type Step struct {
	Op      string          `json:"op"`
	Request json.RawMessage `json:"request,omitempty"`
	Grants  []ledger.Grant  `json:"grants,omitempty"`
	OpID    string          `json:"op_id,omitempty"`
}

// Case is one replay-case document.
type Case struct {
	CaseVersion    string         `json:"case_version"`
	CaseID         string         `json:"case_id"`
	Steps          []Step         `json:"steps"`
	RecordedEvents []ledger.Event `json:"recorded_events"`
	Expected       Expected       `json:"expected"`
}

// Expected is the pinned double verdict.
type Expected struct {
	Fidelity     string `json:"fidelity"`
	Conformance  string `json:"conformance"`
	DivergenceAt *int   `json:"divergence_at,omitempty"`
}

// ReplayReport is mode 2's outcome: the double verdict plus the located
// divergence, if any.
type ReplayReport struct {
	CaseID       string
	Fidelity     Verdict
	Conformance  Verdict
	Recomputed   []ledger.Event
	Recorded     []ledger.Event
	DivergenceAt int // first step index where recomputation diverged (-1 = none)
	Detail       string
}

// Replay is mode 2: executable control replay — recompute the controller's
// rulings by driving a FRESH in-memory machine through the case's steps
// (recorded-family inputs come from the case; the machine is the production
// one, never a second implementation), then compare the recomputed event
// stream against the record. Live effects are structurally disabled: the
// machine is in-memory and dispatch never leaves it.
func Replay(c *Case) (*ReplayReport, error) {
	if err := caseSchema.Validate(caseAsDoc(c)); err != nil {
		return nil, fmt.Errorf("case rejected by replay-case schema: %v", err)
	}
	// the recomputation machine runs on a scratch durable form, not the
	// path=="" in-memory mode (whose Events() is deliberately empty — an
	// in-memory machine keeps no durable events). Driving the production
	// write path means the recomputed stream IS a durable form, produced by
	// the machine itself (fixtures machine-produced, collision ruling).
	tmp, err := os.CreateTemp("", "replay-*.jsonl")
	if err != nil {
		return nil, err
	}
	tmp.Close()
	defer os.Remove(tmp.Name())
	m, err := adopt.Open(tmp.Name())
	if err != nil {
		return nil, fmt.Errorf("scratch machine failed to open: %v", err)
	}
	recomputed, firstStep := drive(m, c.Steps)

	rep := &ReplayReport{CaseID: c.CaseID, Recomputed: recomputed, Recorded: c.RecordedEvents, DivergenceAt: -1}

	// fidelity: event-stream comparison, step-located
	rep.Fidelity = Match
	if !eventsEqual(recomputed, c.RecordedEvents) {
		rep.Fidelity = Divergence
		if firstStep >= 0 && eventsEqual(recomputed, c.RecordedEvents[:min(len(recomputed), len(c.RecordedEvents))]) {
			rep.DivergenceAt = firstStep
		} else {
			rep.DivergenceAt = locateDivergence(recomputed, c.RecordedEvents)
		}
		rep.Detail = fmt.Sprintf("recomputation diverged at step %d — recomputed %d events, record has %d", rep.DivergenceAt, len(recomputed), len(c.RecordedEvents))
	}

	// conformance: does the RECORD itself pass the eight families?
	rep.Conformance = Pass
	if errs := ledger.Errors(eventsAsDoc(c.RecordedEvents)); len(errs) > 0 {
		rep.Conformance = Fail
		if rep.Detail == "" {
			rep.Detail = errs[0]
		}
	}
	return rep, nil
}

// Reevaluate is mode 3: candidate reevaluation — substitute declared
// versions/basis in an isolated recomputation and report the intended
// differences. The original history is never touched (the case document is
// read-only input; the report is a diff between two recomputations).
func Reevaluate(c *Case, substitution func(*Case)) (*ReplayReport, error) {
	sub := deepCopyCase(c)
	substitution(sub)
	base, err := Replay(c)
	if err != nil {
		return nil, err
	}
	alt, err := Replay(sub)
	if err != nil {
		return nil, err
	}
	rep := &ReplayReport{
		CaseID:   c.CaseID + "→" + sub.CaseID,
		Fidelity: base.Fidelity, Conformance: alt.Conformance,
		Recomputed: alt.Recomputed, Recorded: alt.Recorded,
		DivergenceAt: -1,
	}
	if !eventsEqual(base.Recomputed, alt.Recomputed) {
		rep.Fidelity = Divergence
		rep.DivergenceAt = locateDivergence(alt.Recomputed, base.Recomputed)
		rep.Detail = fmt.Sprintf("substitution changed the recomputation at step %d (baseline fidelity: %s)", rep.DivergenceAt, base.Fidelity)
	}
	return rep, nil
}

// RecoverReport is mode 4's outcome: the machine state restored from the
// durable record plus the reconciliation exits. 0.1.0 recovers TO A
// DISPATCHABLE STATE and never dispatches — dispatching is the adopt gate's
// authority and a live effect.
type RecoverReport struct {
	Path       string
	States     map[string]string
	Unresolved []string // operations awaiting reconciliation, with their exits
}

// Recover is mode 4: live recovery — restore the machine from the durable
// record (the gate's own loader — no second reconstruction) and report the
// reconciliation exits for unresolved operations.
func Recover(path string) (*RecoverReport, error) {
	m, err := adopt.Open(path)
	if err != nil {
		return nil, fmt.Errorf("cannot recover from durable form: %v", err)
	}
	lines, err := ledger.LoadDocument(path)
	if err != nil {
		return nil, err
	}
	rep := &RecoverReport{Path: path, States: map[string]string{}, Unresolved: []string{}}
	seen := map[string]bool{}
	for _, l := range lines {
		op := l.Event.Identity.OperationID
		if seen[op] {
			continue
		}
		seen[op] = true
		st := string(m.State(op))
		rep.States[op] = st
		if st == "unresolved" {
			rep.Unresolved = append(rep.Unresolved,
				fmt.Sprintf("%s: reconciliation exits are mark_completed or mark_failed (never re-dispatch — a retry is the duplicate-effect bug 14-A5 counterexample three names)", op))
		}
	}
	return rep, nil
}

// drive runs the steps against a fresh machine, collecting emitted events
// from the machine's own in-memory output. It returns the events and the
// index of the first step the machine refused outright (rejected with no
// event written), or -1.
func drive(m *adopt.Machine, steps []Step) ([]ledger.Event, int) {
	for i, s := range steps {
		switch s.Op {
		case "adopt":
			var req adopt.Request
			if err := json.Unmarshal(s.Request, &req); err != nil {
				return machineEvents(m), i
			}
			if o := m.Adopt(&req); o.Status == "rejected" && o.Event == nil {
				return machineEvents(m), i
			}
		case "dispatch":
			if o := m.Dispatch(s.OpID, s.Grants); o.Status == "rejected" && o.Event == nil {
				return machineEvents(m), i
			}
		case "mark_unresolved":
			if o := m.MarkUnresolved(s.OpID); o.Status == "rejected" && o.Event == nil {
				return machineEvents(m), i
			}
		case "mark_completed":
			if o := m.MarkCompleted(s.OpID); o.Status == "rejected" && o.Event == nil {
				return machineEvents(m), i
			}
		case "mark_failed":
			if o := m.MarkFailed(s.OpID); o.Status == "rejected" && o.Event == nil {
				return machineEvents(m), i
			}
		}
	}
	return machineEvents(m), -1
}

// machineEvents reads the in-memory machine's collected events.
func machineEvents(m *adopt.Machine) []ledger.Event {
	events, err := m.Events()
	if err != nil {
		return nil
	}
	return events
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// eventsEqual compares two event streams on the fields the record pins:
// seq, event_type, identity, digest, outcome status. (Accountability and
// grants ride the adopted pin and are covered by conformance.)
func eventsEqual(a, b []ledger.Event) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i].ArbitrationSeq != b[i].ArbitrationSeq ||
			a[i].EventType != b[i].EventType ||
			a[i].Identity != b[i].Identity ||
			!idemEqual(a[i].Idempotency, b[i].Idempotency) ||
			a[i].Outcome.Status != b[i].Outcome.Status {
			return false
		}
	}
	return true
}

// idemEqual nil-safely compares the optional idempotency pairs (a conflict
// event carries none).
func idemEqual(a, b *ledger.Idempotency) bool {
	if a == nil || b == nil {
		return a == b
	}
	return *a == *b
}

// locateDivergence finds the first event index whose recomputed event
// differs from the record.
func locateDivergence(recomputed, recorded []ledger.Event) int {
	n := len(recomputed)
	if len(recorded) < n {
		n = len(recorded)
	}
	for i := 0; i < n; i++ {
		if !eventsEqual(recomputed[i:i+1], recorded[i:i+1]) {
			return i
		}
	}
	if len(recomputed) != len(recorded) {
		return n // stream length fork after the common prefix
	}
	return -1
}

func eventsAsDoc(events []ledger.Event) map[string]any {
	raw, _ := json.Marshal(events)
	var arr []any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	dec.Decode(&arr)
	return map[string]any{"ledger_version": ledger.Version, "events": arr}
}

func caseAsDoc(c *Case) map[string]any {
	raw, _ := json.Marshal(c)
	var doc map[string]any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	dec.Decode(&doc)
	return doc
}

func deepCopyCase(c *Case) *Case {
	raw, _ := json.Marshal(c)
	var cp Case
	json.Unmarshal(raw, &cp)
	return &cp
}
