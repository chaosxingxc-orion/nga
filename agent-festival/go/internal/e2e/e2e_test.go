package e2e

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/evidlog"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
	"github.com/openjiuwen/agent-festival/go/internal/replay"
)

// overdueEvent is one fact in the evidence snapshot: an obligation past
// due for months, recorded yearsAgo years back.
type overdueEvent struct {
	months   int
	yearsAgo int
}

// creditEvidence is the sealed-dossier stand-in: what the framework hands
// the S1 judge (and what the S2 stand-in fills in the supplement scenario).
type creditEvidence struct {
	assetMillions   int
	assetReportOK   bool
	overdueOnRecord []overdueEvent
}

// s1Verdict is the structured judgment the S1 stand-in emits — the schema
// vocabulary of judgment-spec-credit (deny / grant-50000 / grant-10000 /
// on_missing_evidence / on_undefined_rule), not the ledger vocabulary.
type s1Verdict struct {
	kind    string
	details string
}

// s1Judge is the S1 model stand-in: deterministic, embodying the CORRECTED
// credit rules — the historical veto is UNBOUNDED (08:181-183; 10-walkthrough
// :145 "may be an older record outside the recent six-month window ... R1 now
// requires rejection"), so a >3-month overdue ANYWHERE on record denies.
// The judgment-spec-credit fixture's window-scoped veto wording is the
// pending P3 correction (business-owner seat + pending-confirmation); this
// stand-in does not wait for it — the E2E data uses the reviewer's
// counterexample (assets 35M, clean recent window, 4-month overdue two
// years ago → deny).
func s1Judge(e creditEvidence) s1Verdict {
	if !e.assetReportOK {
		return s1Verdict{kind: "on_missing_evidence", details: "asset valuation not retrievable — request evidence, record the issue, no automatic denial"}
	}
	for _, o := range e.overdueOnRecord {
		if o.months > 3 {
			return s1Verdict{kind: "deny",
				details: fmt.Sprintf("historical veto: a %d-month overdue %d years ago is on record — the veto is unbounded by any window", o.months, o.yearsAgo)}
		}
	}
	if e.assetMillions > 30 {
		return s1Verdict{kind: "grant-50000", details: "assets above the upper cutoff with a clean record"}
	}
	if e.assetMillions < 1 {
		return s1Verdict{kind: "grant-10000", details: "assets below the lower cutoff"}
	}
	return s1Verdict{kind: "on_undefined_rule", details: "assets between the bands — an open specification question for the owner, no default grant"}
}

// s2Query is the S2 model stand-in's authorized investigation: one tool
// call, recorded in the evidence log (the query footprint the sealed
// dossier's completeness declaration is later diff-checked against).
func s2Query(evid *evidlog.Log, tool, selector string) error {
	return evid.Append(evidlog.Entry{
		Tool:     tool,
		Selector: selector,
		Caller:   "s2",
		At:       "2026-11-03T22:00:00Z",
	})
}

// bankAPISubmit is the business-API stub: the external effect boundary. It
// is deterministic (a receipt keyed by the operation) — T0 asserts control
// semantics, not bank behavior.
func bankAPISubmit(op string) string {
	return "receipt:" + op + ":accepted"
}

// taskHarness wires one credit task's durable forms: the adoption machine
// (the framework's control gate) and the evidence log (S2's query trail).
// standinCalls counts model-seat and external-boundary invocations driven
// through the harness — the F-02C zero-call probe's measurement surface:
// a full fast-path hit must return the recorded receipt without entering
// any seat.
type standinCalls struct {
	s1Judge int
	s2Query int
	bankAPI int
}

type taskHarness struct {
	t       *testing.T
	dir     string
	machine *adopt.Machine
	evid    *evidlog.Log
	calls   standinCalls
}

func newTask(t *testing.T) *taskHarness {
	t.Helper()
	dir := t.TempDir()
	m, err := adopt.Open(filepath.Join(dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	evid, err := evidlog.Open(filepath.Join(dir, "evid.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	return &taskHarness{t: t, dir: dir, machine: m, evid: evid}
}

// judge drives the S1 seat through the harness, counting the invocation.
func (h *taskHarness) judge(e creditEvidence) s1Verdict {
	h.calls.s1Judge++
	return s1Judge(e)
}

// query drives the S2 seat (the authorized investigation), counting it.
func (h *taskHarness) query(tool, selector string) error {
	h.calls.s2Query++
	return s2Query(h.evid, tool, selector)
}

// submit drives the business-API boundary, counting the external call.
func (h *taskHarness) submit(op string) string {
	h.calls.bankAPI++
	return bankAPISubmit(op)
}

func (h *taskHarness) reopen() *adopt.Machine {
	h.t.Helper()
	m, err := adopt.Open(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		h.t.Fatal(err)
	}
	return m
}

// chainGrants is the task's pinned authorization: read the credit ledger,
// execute the transfer tool.
func chainGrants() []ledger.Grant {
	return []ledger.Grant{
		{Kind: "data", Selector: "ledger://credit/e2e", Actions: []string{"read"}, Effect: "none"},
		{Kind: "tool", Selector: "tool://credit-transfer", Actions: []string{"execute"}, Effect: "irreversible"},
	}
}

// requestFor builds the adoption request of one judgment revision: the
// business identity is fixed per task, the revision and evidence version
// move together (new evidence → new evaluation revision, same business
// request), and the digest keys the material content.
func requestFor(op, revision, evidence, digest string) *adopt.Request {
	return &adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-e2e-credit", EvaluationRevision: revision, OperationID: op},
		Versions:         ledger.Versions{Evidence: evidence, Rule: "rule-credit-v1", Model: "s1-standin", Readout: "r-1", Policy: "p-1"},
		PayloadDigest:    digest,
		GrantsAtDecision: chainGrants(),
		Accountability:   &ledger.Accountability{Session: "sess-e2e", Skill: "skill-credit", Role: "employee"},
	}
}

func digestHex(ch byte) string {
	return "sha256:" + strings.Repeat(string(ch), 64)
}

// controlEvents returns the indices of control (refusal-record) events in
// the machine's durable form.
func controlEvents(t *testing.T, m *adopt.Machine) []ledger.Event {
	t.Helper()
	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	var out []ledger.Event
	for _, e := range events {
		if e.EventType == "control" {
			out = append(out, e)
		}
	}
	return out
}

// TestT0FullChainHappyPath is the §11.B skeleton end to end, stand-ins in
// every model seat: read rules → S1 finds a gap → S2 investigates within
// authorization (footprint recorded, declaration coverage-checked) → S1
// re-judges on the supplemented dossier → the framework adopts the
// decision and dispatches the bound business request → the stubbed API
// returns its receipt → the effect completes → the isolated projection
// (Inspect) reconstructs the whole task. Improvement-candidate formation
// (step 8) is out of T0 scope: first-version evolution is human-led (C3).
func TestT0FullChainHappyPath(t *testing.T) {
	h := newTask(t)

	// step 2: S1 judges on the initial dossier — the asset report is absent
	v := s1Judge(creditEvidence{assetMillions: 35})
	if v.kind != "on_missing_evidence" {
		t.Fatalf("initial judgment = %q, want on_missing_evidence", v.kind)
	}
	// step 3: S2 supplements within its authorization — one query, recorded
	if err := s2Query(h.evid, "bank.history", "customer=e2e-1"); err != nil {
		t.Fatal(err)
	}
	// the sealed dossier's completeness declaration is machine-checked
	// against the footprint (夏 round-1: 差集告警 — "check honesty")
	decl := evidlog.Declaration{QueriedTool: "bank.history", Selector: "customer=e2e-1"}
	if rep := evidlog.CheckCoverage(h.evid, decl); !rep.OK {
		t.Fatalf("coverage refused the honest declaration: %+v", rep)
	}
	// step 3-4: S1 re-judges on the supplemented dossier → grant
	v = s1Judge(creditEvidence{assetMillions: 35, assetReportOK: true})
	if v.kind != "grant-50000" {
		t.Fatalf("supplemented judgment = %q, want grant-50000", v.kind)
	}
	// step 4: the framework checks current authority and adopts the decision,
	// binding the business request
	if o := h.machine.Adopt(requestFor("op-grant-1", "er-2", "ev-2", digestHex('1'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	// step 5: dispatch after the 14-A4 re-check; the stubbed API answers
	if o := h.machine.Dispatch("op-grant-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	if got := bankAPISubmit("op-grant-1"); got != "receipt:op-grant-1:accepted" {
		t.Fatalf("stub receipt = %q", got)
	}
	// step 6: acceptance vs completion distinguished — the effect completes
	if o := h.machine.MarkCompleted("op-grant-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
	// step 7: isolated replay reconstructs the task
	rep, err := replay.Inspect(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if rep.TornTail {
		t.Fatal("healthy chain must not report a torn tail")
	}
	if rep.States["op-grant-1"] != "completed" {
		t.Fatalf("projection state = %q, want completed", rep.States["op-grant-1"])
	}
	if len(rep.Gaps) != 0 {
		t.Fatalf("healthy chain has gaps: %v", rep.Gaps)
	}
	events, _ := h.machine.Events()
	if len(events) != 3 { // adoption, dispatched, completed
		t.Fatalf("events = %d, want 3", len(events))
	}
}

// TestT0HistoricalOverdueVeto is §11.B scenario 1 with the reviewer's
// counterexample: assets 35M, clean recent window, a 4-month overdue two
// years ago. The corrected rule (unbounded veto) denies — and the deny
// decision is ADOPTED as a decision record with no external effect: an
// adopted-but-never-dispatched operation is the machine's shape for "the
// gate committed a decision that produces no effect".
func TestT0HistoricalOverdueVeto(t *testing.T) {
	h := newTask(t)
	v := s1Judge(creditEvidence{assetMillions: 35, assetReportOK: true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}})
	if v.kind != "deny" {
		t.Fatalf("judgment = %q, want deny (the historical veto is unbounded)", v.kind)
	}
	if o := h.machine.Adopt(requestFor("op-deny-1", "er-1", "ev-1", digestHex('2'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	// the HOST never dispatches a deny record (no external effect to issue).
	// The machine does not interpret business semantics — the verdict lives
	// in the payload, opaque to the gate — so what the gate pins is the
	// control fact: an adopted decision record with ZERO effect events.
	events, _ := h.machine.Events()
	if len(events) != 1 { // the adoption alone — nothing dispatched, nothing completed
		t.Fatalf("events = %d, want 1 (a decision record, no effect)", len(events))
	}
	if s := h.machine.State("op-deny-1"); s != adopt.StateAdopted {
		t.Fatalf("deny record state = %q, want adopted (a decision record, never an effect)", s)
	}
}

// TestT0MissingEvidenceThenSupplement is §11.B scenario 2: S1's structured
// gap (not an automatic denial) → S2's authorized query → the footprint is
// recorded and the coverage check PASSES the honest declaration → the
// re-judgment's revision is a new evaluation under the same business
// request. The dishonest-declaration face is asserted too: claiming a
// query the log lacks refuses green (Missing), and an unlisted log entry
// refuses it too (Unaccounted).
func TestT0MissingEvidenceThenSupplement(t *testing.T) {
	h := newTask(t)
	// the gap: no automatic negative business answer
	if v := s1Judge(creditEvidence{assetMillions: 35}); v.kind != "on_missing_evidence" {
		t.Fatalf("judgment = %q, want on_missing_evidence", v.kind)
	}
	// S2 investigates: footprint first — the supplement query the declaration
	// will cover
	if err := s2Query(h.evid, "asset.valuation", "customer=e2e-2"); err != nil {
		t.Fatal(err)
	}
	// honest (one sealed artifact's declaration covers its own query):
	// the claimed query exists, and nothing else is on the log
	honest := evidlog.Declaration{QueriedTool: "asset.valuation", Selector: "customer=e2e-2"}
	if rep := evidlog.CheckCoverage(h.evid, honest); !rep.OK {
		t.Fatalf("honest declaration refused: %+v", rep)
	}
	// liar: claiming a query the log lacks (差集告警 — Missing)
	liar := evidlog.Declaration{QueriedTool: "credit.bureau", Selector: "customer=e2e-2"}
	if rep := evidlog.CheckCoverage(h.evid, liar); rep.OK || len(rep.Missing) == 0 {
		t.Fatalf("claiming an unmade query passed: %+v", rep)
	}
	// a second query lands (another sealed artifact's footprint); the FIRST
	// artifact's declaration alone no longer accounts for the whole log —
	// the other-tool entry is Unaccounted (queried something undeclared:
	// the reverse of Missing)
	if err := s2Query(h.evid, "bank.history", "customer=e2e-2"); err != nil {
		t.Fatal(err)
	}
	underclaim := evidlog.Declaration{QueriedTool: "asset.valuation", Selector: "customer=e2e-2"}
	if rep := evidlog.CheckCoverage(h.evid, underclaim); rep.OK || len(rep.Unaccounted) == 0 {
		t.Fatalf("an unaccounted log entry passed: %+v", rep)
	}
	// the supplemented revision: new evaluation revision, same business request
	if v := s1Judge(creditEvidence{assetMillions: 35, assetReportOK: true}); v.kind != "grant-50000" {
		t.Fatalf("supplemented judgment = %q, want grant-50000", v.kind)
	}
	if o := h.machine.Adopt(requestFor("op-grant-2", "er-2", "ev-2", digestHex('3'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-grant-2", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-grant-2"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
}

// TestT0NewEvidenceForcesRevision is §11.B scenario 3: after the first
// revision completed, newly discovered history (an old severe overdue)
// forces a new judgment — a NEW evaluation revision under the same
// business request. The completed effect of the first revision is history:
// it is not rewritten (the correction process, not silent amendment), and
// the machine keeps both revisions independently attributable.
func TestT0NewEvidenceForcesRevision(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-rev-1", "er-1", "ev-1", digestHex('4'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-rev-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-rev-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
	// new evidence discovered: the record now shows an old severe overdue
	v := s1Judge(creditEvidence{assetMillions: 35, assetReportOK: true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 2}}})
	if v.kind != "deny" {
		t.Fatalf("revised judgment = %q, want deny", v.kind)
	}
	if o := h.machine.Adopt(requestFor("op-rev-2-deny", "er-2", "ev-2", digestHex('5'))); o.Status != "adopted" {
		t.Fatalf("revision adopt = %q: %s", o.Status, o.Detail)
	}
	// history is not rewritten: revision 1's effect stands completed
	if s := h.machine.State("op-rev-1"); s != adopt.StateCompleted {
		t.Fatalf("first revision = %q, want completed — history is not silently amended", s)
	}
	rep, err := replay.Inspect(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-rev-1"] != "completed" || rep.States["op-rev-2-deny"] != "adopted" {
		t.Fatalf("projection = %v", rep.States)
	}
}

// TestT0LateStaleProposal is §11.B scenario 4 at the component tier. Two
// protections are in frame: (a) the single-writer seq gate — a stale
// instance's write (the late proposal racing an already-committed newer
// one through a second instance) is refused as STALE_WRITER, failing in
// the guilty caller; (b) revision independence — an older revision is a
// distinct operation whose adoption does not overwrite the newer one.
// What is NOT yet in the machine is cross-revision supersession (an
// adopted D2 should hold a stale D1's dispatch): that is the C4 ordering
// contract (impl-2026-11-01/13) — host-side monotonic revision check,
// deliberately out of 0.1.0.
func TestT0LateStaleProposal(t *testing.T) {
	h := newTask(t)
	// a second instance opens the same durable form
	stale, err := adopt.Open(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	// the NEWER revision commits through the live instance
	if o := h.machine.Adopt(requestFor("op-d2", "er-2", "ev-2", digestHex('6'))); o.Status != "adopted" {
		t.Fatalf("newer adopt = %q: %s", o.Status, o.Detail)
	}
	// the stale instance's late write is refused in the guilty caller
	o := stale.Adopt(requestFor("op-d1-stale", "er-1", "ev-1", digestHex('7')))
	if o.Status != "rejected" || !strings.Contains(o.Detail, "STALE_WRITER") {
		t.Fatalf("stale write = %q (%s), want STALE_WRITER rejection", o.Status, o.Detail)
	}
	// re-Open absorbs the newer revision; the late proposal lands as its own
	// operation (a distinct revision never overwrites the winner)
	fresh := h.reopen()
	if s := fresh.State("op-d2"); s != adopt.StateAdopted {
		t.Fatalf("newer revision = %q, want adopted (the winner stands)", s)
	}
	if o := fresh.Adopt(requestFor("op-d1-stale", "er-1", "ev-1", digestHex('7'))); o.Status != "adopted" {
		t.Fatalf("late proposal adopt after re-Open = %q: %s", o.Status, o.Detail)
	}
	// C4 gap, pinned honestly: the machine keeps revisions independent —
	// dispatching the stale revision is legal AT THE MACHINE TIER; holding
	// it is the host-side ordering contract's job (13-c4 note)
	if o := fresh.Dispatch("op-d1-stale", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("stale-revision dispatch = %q: %s (C4: host-side check pending)", o.Status, o.Detail)
	}
}

// TestT0NewEvidenceAfterRequestSent is §11.B scenario 5: once the request
// is out, new evidence does not re-adjudicate the in-flight operation —
// the effect is awaited and reconciled; the new judgment lands as a new
// revision. Modifying the local conclusion never claims the old request
// away (the request fact is durable history).
func TestT0NewEvidenceAfterRequestSent(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-out-1", "er-1", "ev-1", digestHex('8'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-out-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	// new evidence arrives while the request is in flight
	v := s1Judge(creditEvidence{assetMillions: 35, assetReportOK: true,
		overdueOnRecord: []overdueEvent{{months: 4, yearsAgo: 3}}})
	if v.kind != "deny" {
		t.Fatalf("new judgment = %q, want deny", v.kind)
	}
	// the in-flight operation is untouched by the new judgment
	if s := h.machine.State("op-out-1"); s != adopt.StateDispatched {
		t.Fatalf("in-flight state = %q, want dispatched — new evidence does not re-adjudicate it", s)
	}
	// the new revision is its own operation
	if o := h.machine.Adopt(requestFor("op-out-1-rev", "er-2", "ev-2", digestHex('9'))); o.Status != "adopted" {
		t.Fatalf("revision adopt = %q: %s", o.Status, o.Detail)
	}
	// the in-flight request reconciles to completion — its fact stands
	if o := h.machine.MarkUnresolved("op-out-1"); o.Status != "unresolved" {
		t.Fatalf("unresolved = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-out-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
}

// TestT0RestartWhileWaiting is §11.B scenario 6 (14-A5): a crash at the
// dispatch boundary loses nothing — re-Open restores the dispatched
// state, a re-dispatch attempt is REFUSED (recorded as a control event —
// the never-auto-retry invariant is now visible in the ledger), and the
// operation reconciles through unresolved to its terminal state. The
// damaged-durable-form variant runs the torn-tail doctrine: the machine
// refuses every mutation on the damaged file, the bytes survive for
// repair, and recovery resumes after an external repair.
func TestT0RestartWhileWaiting(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-wait-1", "er-1", "ev-1", digestHex('a'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-wait-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	// crash: a new process re-Opens the durable form
	m2 := h.reopen()
	if s := m2.State("op-wait-1"); s != adopt.StateDispatched {
		t.Fatalf("recovered state = %q, want dispatched", s)
	}
	// the duplicate-effect reflex (re-dispatch after restart) is refused —
	// and the refusal is a recorded control fact (E3)
	if o := m2.Dispatch("op-wait-1", chainGrants()); o.Status != "rejected" {
		t.Fatalf("re-dispatch = %q, want rejected (never auto-retried): %s", o.Status, o.Detail)
	}
	cs := controlEvents(t, m2)
	if len(cs) != 1 || cs[0].Outcome.Status != "rejected" {
		t.Fatalf("control events = %+v, want one recorded refusal", cs)
	}
	// reconcile: unresolved → completed
	if o := m2.MarkUnresolved("op-wait-1"); o.Status != "unresolved" {
		t.Fatalf("unresolved = %q: %s", o.Status, o.Detail)
	}
	if o := m2.MarkCompleted("op-wait-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
	// the recovery tool reports the pre-reconciliation exits
	rrep, err := replay.Recover(filepath.Join(h.dir, "adopt.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if rrep.TornTail {
		t.Fatal("healthy form must not report a torn tail")
	}

	// damaged-form variant: external damage while waiting
	path := filepath.Join(h.dir, "adopt.jsonl")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := f.WriteString(`{"event_type":"eff`); err != nil {
		t.Fatal(err)
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}
	m3 := h.reopen()
	if !m3.TornTail() {
		t.Fatal("damaged form must report TornTail")
	}
	if o := m3.Dispatch("op-wait-1", chainGrants()); o.Status != "rejected" {
		t.Fatalf("dispatch on damaged form = %q, want rejected: %s", o.Status, o.Detail)
	}
	after, _ := os.ReadFile(path)
	fragment := `{"event_type":"eff`
	if len(after) != len(raw)+len(fragment) {
		t.Fatalf("damaged bytes were rewritten: %d vs %d+%d — the machine must not erase damaged evidence", len(after), len(raw), len(fragment))
	}
	// external repair: drop the torn remnant, re-Open, reconcile
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		t.Fatal(err)
	}
	m4 := h.reopen()
	if m4.TornTail() {
		t.Fatal("repaired form must not report TornTail")
	}
	if s := m4.State("op-wait-1"); s != adopt.StateCompleted {
		t.Fatalf("state after repair = %q, want completed (history survived the episode)", s)
	}
	irep, err := replay.Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if irep.TornTail || len(irep.Gaps) != 0 {
		t.Fatalf("repaired form reports problems: torn=%v gaps=%v", irep.TornTail, irep.Gaps)
	}
}

// TestT0DuplicateResponse is §11.B scenario 7, both faces of idempotency:
// at the ADOPTION tier a same-key same-digest retry resolves to the
// original receipt (reused — the caller's retry, not a new decision); at
// the COMPLETION tier a duplicate terminal report is refused as an
// illegal transition — and the refusal is a recorded control fact.
func TestT0DuplicateResponse(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-dup-1", "er-1", "ev-1", digestHex('b'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	// same command identity, same material content → the original receipt
	if o := h.machine.Adopt(requestFor("op-dup-1", "er-1", "ev-1", digestHex('b'))); o.Status != "reused" {
		t.Fatalf("same-key retry = %q, want reused", o.Status)
	}
	// same identity, CHANGED material content → conflict, never silent replace
	if o := h.machine.Adopt(requestFor("op-dup-1", "er-1", "ev-1", digestHex('c'))); o.Status != "rejected" {
		t.Fatalf("changed-content retry = %q, want rejected (conflict)", o.Status)
	}
	if o := h.machine.Dispatch("op-dup-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-dup-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
	// the duplicate terminal report (the API answered twice)
	if o := h.machine.MarkCompleted("op-dup-1"); o.Status != "rejected" {
		t.Fatalf("duplicate completion = %q, want rejected: %s", o.Status, o.Detail)
	}
	cs := controlEvents(t, h.machine)
	if len(cs) != 1 {
		t.Fatalf("control events = %d, want 1 (the duplicate report is recorded)", len(cs))
	}
}

// TestT0MidFlightRevocation is §11.B scenario 8 (14-A4): admission
// guarantees nothing about later permission — dispatch re-checks the live
// grant set against the pin. The revoked-set refusal is a recorded
// control fact (E3: the signature guard's every firing is auditable);
// re-granting admits the dispatch.
func TestT0MidFlightRevocation(t *testing.T) {
	h := newTask(t)
	if o := h.machine.Adopt(requestFor("op-rev-3", "er-1", "ev-1", digestHex('d'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	// the grant was revoked mid-flight: live no longer covers the pin
	if o := h.machine.Dispatch("op-rev-3", []ledger.Grant{chainGrants()[0]}); o.Status != "rejected" {
		t.Fatalf("dispatch with revoked grants = %q, want rejected", o.Status)
	}
	cs := controlEvents(t, h.machine)
	if len(cs) != 1 || !strings.Contains(cs[0].Outcome.Detail, "14-A4") {
		t.Fatalf("control events = %+v, want one recorded 14-A4 refusal", cs)
	}
	// re-granted: the covering live set passes
	if o := h.machine.Dispatch("op-rev-3", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch after re-grant = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.MarkCompleted("op-rev-3"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
}

// TestT0FastPathFullHitZeroModelCalls is F-02C's load-bearing counterexample
// (the one row of xingchao's acceptance list we had not pinned): 同一次执行
// 已提交的结果/回执 → 直接返回，不调用模型. After a task completes, the same
// business request arriving again resolves through the RECORD, not through
// re-computation — both fast-path faces are asserted: the read face (the host
// queries the machine's state and events and returns the recorded receipt)
// and the command-retry face (re-Adopt resolves to reused). The zero-call
// claim is mechanical: the harness's seat counters must be exactly at their
// end-of-first-pass baseline, asserted by exact value in both phases — if
// the counters silently failed to count, the baseline assertion itself
// reddens, so the measurement surface is load-bearing too.
func TestT0FastPathFullHitZeroModelCalls(t *testing.T) {
	h := newTask(t)

	// first pass: gap → supplement → judge → adopt → dispatch → complete
	if v := h.judge(creditEvidence{assetMillions: 35}); v.kind != "on_missing_evidence" {
		t.Fatalf("initial judgment = %q, want on_missing_evidence", v.kind)
	}
	if err := h.query("asset.valuation", "customer=e2e-fp"); err != nil {
		t.Fatal(err)
	}
	if v := h.judge(creditEvidence{assetMillions: 35, assetReportOK: true}); v.kind != "grant-50000" {
		t.Fatalf("supplemented judgment = %q, want grant-50000", v.kind)
	}
	if o := h.machine.Adopt(requestFor("op-fp-1", "er-2", "ev-2", digestHex('e'))); o.Status != "adopted" {
		t.Fatalf("adopt = %q: %s", o.Status, o.Detail)
	}
	if o := h.machine.Dispatch("op-fp-1", chainGrants()); o.Status != "dispatched" {
		t.Fatalf("dispatch = %q: %s", o.Status, o.Detail)
	}
	receipt := h.submit("op-fp-1")
	if receipt != "receipt:op-fp-1:accepted" {
		t.Fatalf("receipt = %q", receipt)
	}
	if o := h.machine.MarkCompleted("op-fp-1"); o.Status != "completed" {
		t.Fatalf("complete = %q: %s", o.Status, o.Detail)
	}
	// the measurement surface is asserted by exact value: 2 judgments
	// (gap + grant), 1 query, 1 external call
	baseline := h.calls
	if baseline != (standinCalls{s1Judge: 2, s2Query: 1, bankAPI: 1}) {
		t.Fatalf("baseline seat calls = %+v, want {s1:2 s2:1 api:1} — the counters themselves are broken", baseline)
	}
	eventsBefore, _ := h.machine.Events()

	// FAST-PATH FACE 1 (the read face, F-02B step 3 "先查执行记录"): the host
	// answers the same request from the record — state and events — without
	// entering any seat. Zero new events, zero seat invocations.
	if s := h.machine.State("op-fp-1"); s != adopt.StateCompleted {
		t.Fatalf("recorded state = %q, want completed (the record answers the retry)", s)
	}
	eventsNow, _ := h.machine.Events()
	if len(eventsNow) != len(eventsBefore) {
		t.Fatalf("read face wrote events: %d → %d", len(eventsBefore), len(eventsNow))
	}
	// the recorded receipt is returned as-is (deterministic stand-in — the
	// real system keeps the receipt with the record-family inputs)
	if got := bankAPISubmit("op-fp-1"); got != receipt {
		t.Fatalf("recorded receipt mismatch: %q vs %q", got, receipt)
	}

	// FAST-PATH FACE 2 (the command-retry face): the same command identity
	// with unchanged material content re-submits — the machine resolves it
	// to the ORIGINAL receipt (reused), never re-driving the node
	if o := h.machine.Adopt(requestFor("op-fp-1", "er-2", "ev-2", digestHex('e'))); o.Status != "reused" {
		t.Fatalf("retry adopt = %q, want reused — the original receipt resolves it", o.Status)
	}

	// THE assertion: the full fast-path hit invoked ZERO model seats and
	// ZERO external calls (F-02C row 1: 直接返回，不调用模型)
	if h.calls != baseline {
		t.Fatalf("fast-path retry entered seats: s1 %d→%d, s2 %d→%d, api %d→%d — a full hit must return the recorded receipt without calling the model",
			baseline.s1Judge, h.calls.s1Judge, baseline.s2Query, h.calls.s2Query, baseline.bankAPI, h.calls.bankAPI)
	}
}
