// Package replay is piece 6: the four replay modes as four non-interchangeable
// structured entry points (current proposal §8). The package is a READ-ONLY
// consumer of the growth layer: it never writes a durable ledger.
//
// Two engine families, deliberately split (frame-bench collision ruling A):
// Inspect is a PROJECTION reducer — a second implementation that rebuilds a
// view from the record without recomputing decisions (codex rollout-trace
// precedent: projections stay outside the core); Replay and Reevaluate are
// RE-EXECUTION — they drive the production state machine (a fresh
// scratch-isolated adopt.Machine) through the recorded steps and only the recorded-family
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
// form, and the fixture corpus pins all four quadrants — match+fail is reachable through an unknown-field record (the fidelity comparison sees typed fields only; the raw conformance arm rejects the smuggled property).
//
// Arbitration (collision ruling B, narrowed): re-execution consumes the
// RECORDED arbitration order — it never re-arbitrates (legacy semantics,
// drift register L5). This applies to true adjudication results only (the
// adopt race's first-wins outcome); purely-ordered events that a stable key
// could sort must not enter arbitration records. Family (e) note: the
// priors' original wording ("the same steps sequence, two outcomes") is
// unrealizable under a sequential driver — the realized form is the pair
// race-outcome-{a,b} (SAME step order, different step INPUTS: the first
// adopt's digest differs across the pair, flipping the second adopt's
// outcome — reused vs conflict), which pins the
// same property: the recorded arbitration order is consumed, never
// re-derived.
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
	"slices"
	"strings"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
	"github.com/openjiuwen/agent-festival/go/internal/schemalib"
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
	States      map[string]string // operation id -> the STATUS-TAIL projection of its last event (includes the fact words reused/conflict — not the machine state; Recover reports that)
	Gaps        []string          // ledger.Errors over the record
	ByOperation map[string][]ledger.Event
}

// Inspect is mode 1: historical inspection — reconstruct retained history
// and expose missing evidence; no live effects, no recomputation. It is a
// projection reducer (second implementation by design).
//
// Known blind spot (inherited from the piece-4 boundary, declared here):
// a TORN TAIL — an unparseable remnant at EOF — is skipped by the loader,
// so neither the projection nor Gaps sees it; a record whose newest events
// live in the torn remnant projects to its prefix silently. Closing this
// belongs to the loader (piece 4), not to this projection.
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
		if s := l.Event.Outcome.Status; ledger.AdoptStatuses[s] || ledger.EffectStatuses[s] {
			r.States[op] = s // derived from the ledger's family sets — no fifth vocabulary copy
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

// Case is one replay-case document. RecordedRawDoc carries the recorded
// events as the RAW decoded documents (json:"-" — LoadCase fills it from
// the case file's own map). The conformance arm judges the record through
// this raw view: re-marshalling typed events would launder it (unknown
// fields dropped, empty arrays folded) — the R2 laundering lesson, applied
// here from day one.
type Case struct {
	CaseVersion    string         `json:"case_version"`
	CaseID         string         `json:"case_id"`
	Steps          []Step         `json:"steps"`
	RecordedEvents []ledger.Event `json:"recorded_events"`
	RecordedRawDoc []any          `json:"-"`
	rawCaseDoc     map[string]any `json:"-"` // the case document's own raw view (schema validation input)
	Expected       Expected       `json:"expected"`
}

// LoadCase decodes a case document from its RAW map form, preserving BOTH
// raw views. Boundary: the typed decode requires recorded_events to fit the
// Event types — a record whose integers leave the int64-typed form (e.g.
// float syntax like 5.0, rejected by the ledger checker's literal gate since
// the R16 数值域章程) fails HERE with a decode error; divergence_at
// float syntax is rejected BEFORE the typed decode with the
// REPLAY.SEQ_FLOAT_SYNTAX key so both oracles reject the same document
// (R16 A-M1 — the Py schema face alone would accept it by value).
// raw views: the recorded events' (for the conformance arm) and the case
// document's own map (for schema validation — validating a typed
// re-projection would launder unknown fields away, the same R2 lesson one
// layer up). Callers must decode with json.Decoder.UseNumber (the
// ledger.Errors input discipline).
func LoadCase(doc map[string]any) (*Case, error) {
	raw, err := json.Marshal(doc)
	if err != nil {
		return nil, err
	}
	// 数值域章程 v2 literal gate (R16 A-M1), BEFORE the typed decode: the
	// typed view rejects float syntax without a neutral key, while the
	// Python schema face accepts it by value — this gate makes both sides
	// reject the same documents WITH the key. json.Number is guaranteed by
	// the numbersSurvived discipline below.
	if exp, ok := doc["expected"].(map[string]any); ok {
		if n, ok := exp["divergence_at"].(json.Number); ok {
			if _, err := n.Int64(); err != nil {
				return nil, fmt.Errorf("[REPLAY.SEQ_FLOAT_SYNTAX] expected.divergence_at %s is not an integer literal — the divergence locator domain is integer; this package does no float math (user ruling 2026-11-02)", n.String())
			}
		}
	}
	var c Case
	if err := json.Unmarshal(raw, &c); err != nil {
		return nil, err
	}
	if rec, ok := doc["recorded_events"].([]any); ok {
		for i, e := range rec {
			if !numbersSurvived(e) {
				return nil, fmt.Errorf("recorded_events/%d: the map was decoded WITHOUT UseNumber — the conformance arm refuses float-folded integers (decode with json.Decoder.UseNumber)", i)
			}
		}
		c.RecordedRawDoc = rec
	}
	c.rawCaseDoc = doc
	return &c, nil
}

// numbersSurvived reports whether every numeric leaf in the node is a
// json.Number — the structural form of the UseNumber input discipline.
func numbersSurvived(node any) bool {
	switch v := node.(type) {
	case map[string]any:
		for _, child := range v {
			if !numbersSurvived(child) {
				return false
			}
		}
	case []any:
		for _, child := range v {
			if !numbersSurvived(child) {
				return false
			}
		}
	case float64:
		return false // folded — the discipline was broken upstream
	}
	return true
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
	DivergenceAt int // first diverging EVENT index (-1 = none) — the single coordinate system the schema pins
	Detail       string
}

// Replay is mode 2: executable control replay — recompute the controller's
// rulings by driving a FRESH scratch-isolated machine through the case's steps
// (recorded-family inputs come from the case; the machine is the production
// one, never a second implementation), then compare the recomputed event
// stream against the record. Live effects are structurally disabled: the
// machine is scratch-isolated and dispatch never leaves it.
func Replay(c *Case) (*ReplayReport, error) {
	if c.rawCaseDoc == nil {
		return nil, fmt.Errorf("case %q carries no raw case view — schema validation refuses a laundered projection (load via LoadCase)", c.CaseID)
	}
	if err := caseSchema.Validate(c.rawCaseDoc); err != nil {
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
	recomputed, err := drive(m, c.Steps)
	if err != nil {
		return nil, err
	}

	rep := &ReplayReport{CaseID: c.CaseID, Recomputed: recomputed, Recorded: c.RecordedEvents, DivergenceAt: -1}

	// fidelity: event-stream comparison, located at the first diverging
	// EVENT index (the single coordinate system; every machine step that is
	// not refused emits exactly one event, so the value coincides with the
	// step index today — the schema pins the event coordinate)
	rep.Fidelity = Match
	if !eventsEqual(recomputed, c.RecordedEvents) {
		rep.Fidelity = Divergence
		rep.DivergenceAt = locateDivergence(recomputed, c.RecordedEvents)
		rep.Detail = fmt.Sprintf("recomputation diverged at event %d — recomputed %d events, record has %d", rep.DivergenceAt, len(recomputed), len(c.RecordedEvents))
	}

	// conformance: does the RECORD itself pass the eight families? Judged
	// through the RAW recorded documents — never a typed re-projection.
	if c.RecordedRawDoc == nil {
		return nil, fmt.Errorf("case %q carries no raw recorded view — the conformance arm refuses to judge a laundered projection (load via LoadCase)", c.CaseID)
	}
	rep.Conformance = Pass
	if errs := ledger.Errors(map[string]any{"ledger_version": ledger.Version, "events": c.RecordedRawDoc}); len(errs) > 0 {
		rep.Conformance = Fail
		if rep.Detail == "" {
			rep.Detail = errs[0]
		}
	}
	return rep, nil
}

// SubstitutionReport is mode 3's own output contract (it deliberately does
// NOT reuse the ReplayReport field names — fidelity/conformance there mean
// "recomputation vs record"; here the question is what the substitution
// changed, against the BASELINE's two verdicts). The substitute's own
// conformance verdict is deliberately not carried: steps-substitutions
// cannot change the record, so it is structurally equal to the baseline's
// (the substitute's raw views still go through the same discipline — the
// deep copies are UseNumber-decoded as ledger.Errors inputs, currently
// consumed only inside Replay(sub)).
type SubstitutionReport struct {
	CaseID          string
	Changed         bool // did the substitution alter the recomputation?
	At              int  // first diverging event index (-1 = unchanged)
	BaseFidelity    Verdict
	BaseConformance Verdict
	Detail          string
}

// Reevaluate is mode 3: candidate reevaluation — substitute declared
// versions/basis in an isolated recomputation and report the intended
// differences. The original case is never touched (read-only input; the
// report is a diff between two recomputations).
func Reevaluate(c *Case, substitution func(*Case)) (*SubstitutionReport, error) {
	sub, err := deepCopyCase(c)
	if err != nil {
		return nil, err
	}
	substitution(sub)
	// mode 3's substitution domain is the STEPS (declared versions/basis).
	// A closure that rewrites the RECORD leaves the documented contract —
	// refused loudly rather than reported as an intended difference (the
	// report would silently carry a conformance it claims cannot change).
	// Two frozen surfaces, two different reasons (deliberately separate
	// arms — conflating them misreports violations):
	// - the RECORD (typed events + its raw view): the conformance arm
	//   judges this form, so a rewrite here is a record rewrite.
	// - the CASE DOCUMENT's raw view: frozen so the substitute's schema
	//   validation input cannot drift from its typed steps. Substituted
	//   steps are NOT revalidated against the case schema (Replay validates
	//   the pre-substitution view); the machine gate and drive's own guards
	//   carry the behavioral check for whatever the substitution produces.
	if !eventsEqual(sub.RecordedEvents, c.RecordedEvents) || !recordedRawEqual(sub, c) {
		return nil, fmt.Errorf("substitution left the steps domain: the case %q's record was rewritten (typed or raw view) — mode 3 substitutes declared inputs, never the record", c.CaseID)
	}
	if !rawCaseDocEqual(sub, c) {
		return nil, fmt.Errorf("substitution left the steps domain: the case %q's raw document view was rewritten — the document view is frozen; substitute the typed steps", c.CaseID)
	}
	base, err := Replay(c)
	if err != nil {
		return nil, err
	}
	alt, err := Replay(sub)
	if err != nil {
		return nil, err
	}
	rep := &SubstitutionReport{
		CaseID:          c.CaseID + "→" + sub.CaseID,
		BaseFidelity:    base.Fidelity,
		BaseConformance: base.Conformance,
		At:              -1,
	}
	if !eventsEqual(base.Recomputed, alt.Recomputed) {
		rep.Changed = true
		rep.At = locateDivergence(alt.Recomputed, base.Recomputed)
		rep.Detail = fmt.Sprintf("substitution changed the recomputation at event %d", rep.At)
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
// from the machine's scratch output. An I/O failure reading the scratch
// form is an ERROR, never a silent empty stream (a silent nil would forge a
// divergence@0 verdict — fail loud). (declared-only: the scratch path is
// package-private and machine-written, so no fixture can induce an Events()
// failure — pinning this would need an injectable failure face, which is
// out of scope; the write-path twin IS pinned, TestScratchWriteFailureIsLoud.) An unknown op is an error too: the
// machine's operation set never collapses into one generic call.
func drive(m *adopt.Machine, steps []Step) ([]ledger.Event, error) {
	for i, s := range steps {
		var o adopt.Outcome
		switch s.Op {
		case "adopt":
			var req adopt.Request
			if err := json.Unmarshal(s.Request, &req); err != nil {
				return nil, fmt.Errorf("step %d: adopt request undecodable: %v", i, err)
			}
			o = m.Adopt(&req)
		case "dispatch":
			o = m.Dispatch(s.OpID, s.Grants)
		case "mark_unresolved":
			o = m.MarkUnresolved(s.OpID)
		case "mark_completed":
			o = m.MarkCompleted(s.OpID)
		case "mark_failed":
			o = m.MarkFailed(s.OpID)
		default:
			return nil, fmt.Errorf("step %d: unknown op %q — the machine's operation set never collapses into one generic call", i, s.Op)
		}
		// the WRITE path goes fail-loud too: a scratch-write failure is an
		// I/O error, and treating it as a legal refusal would forge a
		// divergence verdict over an under-produced stream (the read path's
		// own doctrine, applied symmetrically)
		if o.Status == "rejected" && strings.Contains(o.Detail, "ledger append failed") {
			return nil, fmt.Errorf("step %d (%s): scratch write failed: %s", i, s.Op, o.Detail)
		}
	}
	return m.Events()
}

// recordedRawEqual compares the recorded events' raw views — the record's
// JUDGED form (the conformance arm reads it), so the mode-3 domain guard
// must cover this layer, not only the typed one.
func recordedRawEqual(a, b *Case) bool {
	ab, aerr := json.Marshal(a.RecordedRawDoc)
	bb, berr := json.Marshal(b.RecordedRawDoc)
	return aerr == nil && berr == nil && string(ab) == string(bb)
}

// rawCaseDocEqual compares the case document's raw views — frozen so the
// substitute's schema-validation input cannot drift from its typed steps.
func rawCaseDocEqual(a, b *Case) bool {
	ab, aerr := json.Marshal(a.rawCaseDoc)
	bb, berr := json.Marshal(b.rawCaseDoc)
	return aerr == nil && berr == nil && string(ab) == string(bb)
}

// eventsEqual compares two event streams on the FULL field set the record
// pins: seq, event_type, identity, versions (the replay matcher's matching
// inputs — event-ledger schema), idempotency, grants, outcome status, and
// the accountability triple. Detail is the one exception: the schema
// declares it free-text provenance, "not a machine-checked field".
func eventsEqual(a, b []ledger.Event) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		x, y := a[i], b[i]
		if x.ArbitrationSeq != y.ArbitrationSeq ||
			x.EventType != y.EventType ||
			x.Identity != y.Identity ||
			x.Versions != y.Versions ||
			!idemEqual(x.Idempotency, y.Idempotency) ||
			x.Outcome.Status != y.Outcome.Status ||
			!grantsEqual(x.GrantsAtDecision, y.GrantsAtDecision) ||
			!acctEqual(x.Accountability, y.Accountability) {
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

// grantsEqual deep-compares the optional grant slices.
func grantsEqual(a, b []ledger.Grant) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i].Kind != b[i].Kind || a[i].Selector != b[i].Selector ||
			a[i].Effect != b[i].Effect || !slices.Equal(a[i].Actions, b[i].Actions) {
			return false
		}
	}
	return true
}

// acctEqual nil-safely compares the optional triples.
func acctEqual(a, b *ledger.Accountability) bool {
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

func deepCopyCase(c *Case) (*Case, error) {
	raw, err := json.Marshal(c)
	if err != nil {
		return nil, err
	}
	var cp Case
	if err := json.Unmarshal(raw, &cp); err != nil {
		return nil, err
	}
	// deep copies of BOTH raw views — a shallow alias would let a
	// substitution closure reach into the original case's conformance
	// inputs (the isolation contract covers the raw layer too)
	if c.RecordedRawDoc != nil {
		b, err := json.Marshal(c.RecordedRawDoc)
		if err != nil {
			return nil, err
		}
		dec := json.NewDecoder(bytes.NewReader(b))
		dec.UseNumber() // RecordedRawDoc is a ledger.Errors input — the integer-domain discipline applies to copies too (declared-only: the corpus's small seqs cannot distinguish this from a plain decode; a ≥2^53 fixture through Reevaluate would pin it)
		if err := dec.Decode(&cp.RecordedRawDoc); err != nil {
			return nil, err
		}
	}
	if c.rawCaseDoc != nil {
		b, err := json.Marshal(c.rawCaseDoc)
		if err != nil {
			return nil, err
		}
		dec := json.NewDecoder(bytes.NewReader(b))
		dec.UseNumber() // declared-only twin of the RecordedRawDoc copy note above — same discipline, same untestable-on-corpus status
		if err := dec.Decode(&cp.rawCaseDoc); err != nil {
			return nil, err
		}
	}
	return &cp, nil
}
