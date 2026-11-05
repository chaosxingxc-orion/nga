// Package adopt implements the adoption gate state machine (piece 2 of the
// NGA unified-architecture growth layer). It is the single writer of adoption
// and effect events into the ledger: the first request under a key adopts; a
// same-key same-digest retry reuses; a same-key different-digest request is
// rejected (15 §B4 / 14-A5 counterexample four). The dispatch path rechecks
// authority against the grant set pinned at decision time (14-A4: admission
// guarantees nothing about later permission). A dispatch whose outcome is
// unknown enters the first-class 'unresolved' state (14-A5 counterexample
// three) and is never auto-retried — a silent retry there is exactly the
// duplicate-effect bug the counterexample names.
//
// State DAG: adopted → dispatched | unresolved; dispatched → unresolved |
// completed | failed; unresolved → completed | failed (reconciliation).
// 'unresolved' is reachable from adopted because a crash at the dispatch
// boundary leaves the machine with an adopted operation whose external
// effect may or may not have gone out — exactly the 14-A5 counterexample
// three shape (the crash-unresolved-then-complete ledger fixture pins
// adoption → unresolved → completed). Every other transition is rejected.
// The machine is in-memory with an append-only JSON-lines file
// as its durable form: each event is one line, and the file is replaced
// atomically (write the full new content to a temp file, rename over — a
// crash leaves the old or the new file, never a half-written one). A torn
// tail from external damage is remembered, not healed: the machine refuses
// every mutation until the file is manually repaired and re-Opened (the
// torn-tail doctrine, unified with evidlog — P1-2, 2026-11-03). Because
// the event file is the machine's only durable state, the pinned grants
// and the winner's identity/versions/accountability ride the adoption
// event;
// otherwise the crash would silently void the revocation check or fork the
// post-recovery event stream. The durability contract is process-crash
// level: rename atomicity holds across a killed process, but power-loss
// grade durability (fsync of file and directory) is out of scope, as is
// file-level tamper-proofing (12 §6: append-only is not tamper-evidence) —
// load-time checking (Open runs the ledger checker and rejects bypass
// documents) is the integrity boundary that IS in scope.
package adopt

import (
	"bytes"
	"crypto/sha256"

	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sync"
	"unicode/utf8"

	"github.com/openjiuwen/agent-festival/go/internal/ledger"
	"github.com/openjiuwen/agent-festival/go/internal/rfc8785"
)

// State is one state of the per-operation state machine.
type State string

const (
	StateAdopted    State = "adopted"
	StateDispatched State = "dispatched"
	StateUnresolved State = "unresolved" // dispatch outcome unknown (timeout / crash) — first-class, never auto-retried
	StateCompleted  State = "completed"
	StateFailed     State = "failed"
)

// Request is an adoption request. The document form is validated against
// adoption.schema.json — externally by the fixture suites (CheckRequest /
// the Python oracle) and internally by Adopt itself: the single writer
// refuses to adopt a request whose document is non-conforming, so the
// durable form is conforming by construction even for in-process callers
// that skip every external validation.
type Request struct {
	AdoptionVersion  string                 `json:"adoption_version"`
	Identity         ledger.Identity        `json:"identity"`
	Versions         ledger.Versions        `json:"versions"`
	PayloadDigest    string                 `json:"payload_digest"`
	GrantsAtDecision []ledger.Grant         `json:"grants_at_decision"`
	Accountability   *ledger.Accountability `json:"accountability,omitempty"`
}

// Outcome is the machine's answer to a call. Status is one of
// adopted | reused | dispatched | unresolved | completed | failed | rejected.
// Event is the ledger event the call wrote, nil when nothing was written.
type Outcome struct {
	Status string
	Detail string
	Event  *ledger.Event
}

// A zero-value Machine is not usable (Adopt would panic on the nil ops
// map) — Open is the only constructor. The panic is loud, not silent: the
// zero value can never reach the durable form (R11 MINOR-b, evidlog-m3's
// adopt-side cousin — noisier but structurally the same statement).
//
// Machine is the adoption gate. Use Open to attach a durable JSONL file.
// The durable form supports at most ONE Machine instance per file: the
// rewrite is read-rebuild-rename under this instance's lock only — a second
// instance on the same path would interleave renames and silently lose
// events, and a STALE instance's write is a false success that poisons the
// file (detectable at the next Open) — since R11 the write-time
// ADOPT.STALE_WRITER gate rejects it in the guilty caller instead
// (contract-external use; a crashed process leaves at most one live
// instance, and restart goes through Open again).
type Machine struct {
	mu       sync.Mutex
	ops      map[string]*opState // keyed by operation_id
	seq      int64               // last arbitration sequence written (0-based)
	path     string              // append-only JSONL file ("" = in-memory only)
	tornTail bool                // the durable form ended in a torn tail at Open time (external damage)
}

// seqExhausted reports whether the arbitration counter's int64 domain has
// no write headroom left: a file loaded with seq == MaxInt64 is legal for
// every check rule, but the machine's next m.seq+1 would wrap negative and
// the durable form's schema (minimum 0) would reject the file forever after
// — the machine writing a file its own loader refuses. At exhaustion every
// write is refused cleanly (R10 MAJOR).
const seqExhaustedMsg = "arbitration counter exhausted — the durable form's sequence domain is full, refusing to write rather than wrap"

func (m *Machine) seqExhausted() bool {
	return m.seq == math.MaxInt64
}

// opState is the in-memory projection of one operation's events. Every field
// is reconstructed from the event file on load; nothing is kept only in RAM.
type opState struct {
	digest         string
	state          State
	grants         []ledger.Grant // pinned at adoption (14-A4 revocation-check baseline)
	identity       ledger.Identity
	versions       ledger.Versions
	accountability *ledger.Accountability // pinned at adoption; rides every effect event
	dispatchedSeq  int64                  // the arbitration seq of THIS operation's dispatch event; -1 before the first dispatch (R29 M-1: initialized at Adopt/replay, not left as Go zero value) — the checked version for the E6 conditional commit (C4)
}

// Open loads (or starts) the durable form at path. A torn tail — an
// unparseable remnant at EOF without a trailing newline — is skipped in
// the load projection but REMEMBERED, not healed: TornTail() reports it
// and every mutating call refuses until the file is manually repaired and
// re-Opened. Events end at the last complete line; anything non-parseable
// elsewhere fails the open.
// TORN-TAIL DOCTRINE, unified with evidlog (P1-2, 2026-11-03, retiring the
// R9 F2 "heals / lossy-but-safe" divergence): remember + refuse. Under the
// machine's own temp+rename protocol a crash leaves the old or the new
// file, never a partial line, so the tolerated shape can only come from
// OUTSIDE — and external damage is exactly the case where the machine must
// not guess what was lost. A lost dispatch line is an unrecorded,
// re-issuable execution permit: the retired doctrine's safety argument
// ("a re-dispatch is exactly the 14-A5 unresolved case the machine already
// models") was falsified by the external review probe — after healing,
// Open re-derives to adopted and Dispatch legally returns "dispatched"
// AGAIN, and the 14-A5 protection (caller-asserted MarkUnresolved) can
// never fire because the damage signal was swallowed. Healing would also
// erase the evidence: the rewrite-from-parsed-lines dropped the remnant
// bytes before any human looked. The append path re-checks the bytes at
// write time, so out-of-band damage between Open and write is caught too.
// Manual repair is the only recovery: fix or truncate the file outside,
// then re-Open. Do NOT reintroduce healing on either side of this pair.
// The loaded lines are checked BEFORE any state is absorbed: a file this
// machine did not write fails the open (see checkLoaded).
func Open(path string) (*Machine, error) {
	m := &Machine{ops: map[string]*opState{}, seq: -1, path: path}
	lines, torn, err := ledger.LoadDocument(path)
	if err != nil {
		return nil, err
	}
	m.tornTail = torn
	if err := m.checkLoaded(lines); err != nil {
		return nil, err
	}
	for i := range lines {
		m.replayEvent(&lines[i].Event)
	}
	return m, nil
}

// TornTail reports whether the durable form ended in an unparseable torn
// tail at Open time (external damage). While true the machine is
// read-only: every mutation is refused until the file is repaired and the
// machine is re-Opened (see the torn-tail doctrine on Open).
func (m *Machine) TornTail() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.tornTail
}

// checkLoaded runs the RAW line documents — what is on disk, byte for byte —
// through the ledger checker: the single-writer discipline's load-time
// integrity boundary. A typed re-projection would launder the file (omitempty
// folds an empty grants array into absence, unknown fields vanish), so the
// schema sees exactly the bytes a bypass writer could have put there (R2
// BLOCKER). A file this machine did not write — an event sequence that
// violates the ledger grammar, a registered digest flipped, a non-conforming
// event — fails the open: the machine refuses to resume from a bypassed or
// tampered file rather than silently absorbing it as legal state.
func (m *Machine) checkLoaded(lines []ledger.ParsedLine) error {
	if len(lines) == 0 {
		return nil // fresh (or fully torn) file: nothing to check
	}
	events := make([]any, 0, len(lines))
	for _, l := range lines {
		events = append(events, l.Doc)
	}
	doc := map[string]any{"ledger_version": ledger.Version, "events": events}
	if errs := ledger.Errors(doc); len(errs) > 0 {
		return fmt.Errorf("durable form rejected at load: %s", errs[0])
	}
	return nil
}

func (m *Machine) replayEvent(e *ledger.Event) {
	if e.ArbitrationSeq > m.seq {
		m.seq = e.ArbitrationSeq
	}
	if e.Idempotency == nil {
		return
	}
	op := e.Idempotency.OperationID
	st, ok := m.ops[op]
	if !ok {
		st = &opState{dispatchedSeq: -1} // R29 M-1: replay-side sentinel consistency
		m.ops[op] = st
	}
	st.digest = e.Idempotency.PayloadDigest
	// The adoption event is the pin: only it stamps the operation's
	// identity/versions/grants/accountability. A reused event carries the
	// RETRYER's identity, a conflict event the competitor's — replaying them
	// over the winner's pin would fork the post-recovery event stream away
	// from the never-crashed machine's output (R1 BLOCKER: the idempotency
	// key does not cover evaluation_revision/versions, so same-key retries
	// legally differ there).
	if e.Outcome.Status == string(StateAdopted) {
		st.identity = e.Identity
		st.versions = e.Versions
		st.grants = e.GrantsAtDecision
		st.accountability = e.Accountability
	}
	if s := State(e.Outcome.Status); s == StateAdopted || s == StateDispatched ||
		s == StateUnresolved || s == StateCompleted || s == StateFailed {
		st.state = s
	}
	// E6 (C4): the dispatch event's arbitration seq is the operation's
	// checked version for the conditional commit — replayed from the
	// durable form exactly as a live Dispatch would record it.
	if e.Outcome.Status == string(StateDispatched) {
		st.dispatchedSeq = e.ArbitrationSeq
	}
}

// State returns the operation's current state ("" when unknown).
func (m *Machine) State(op string) State {
	m.mu.Lock()
	defer m.mu.Unlock()
	if st, ok := m.ops[op]; ok {
		return st.state
	}
	return ""
}

// Adopt processes an adoption request. New key → adopted (the single winner
// of any concurrent race, serialized under the machine lock). Same key and
// same digest → reused: the repeated request is a ledger fact, so a 'reused'
// adoption event is written (the retry-reuse fixture's shape). Same key and
// a different digest → rejected (15 §B4): the competitor's loss is recorded
// as a 'conflict' adoption event without idempotency — its digest never
// enters the registry, and the ledger's digest-stability rule reads the
// registry, not the battlefield (the concurrent-double-adoption fixture's
// shape, 12 §2: the loser's event is a fact, not an error).
func (m *Machine) Adopt(req *Request) Outcome {
	// The single writer must not write non-conforming ledger documents: the
	// request is schema-checked before anything is adopted, so the durable
	// form is conforming by construction (R2: the machine previously trusted
	// its caller, and an in-process caller could bypass every external
	// validation — an empty grant pin would then reach the file).
	if errs := m.checkRequest(req); len(errs) > 0 {
		return Outcome{Status: "rejected", Detail: "request rejected: " + errs[0]}
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.seqExhausted() {
		return Outcome{Status: "rejected", Detail: seqExhaustedMsg}
	}
	op := req.Identity.OperationID
	if st, ok := m.ops[op]; ok {
		if st.digest != req.PayloadDigest {
			detail := fmt.Sprintf("operation_id %q carries payload_digest %q but an earlier event recorded %q — changed payload under the same key", op, req.PayloadDigest, st.digest)
			ev := &ledger.Event{
				EventType:      "adoption",
				ArbitrationSeq: m.seq + 1,
				Identity:       req.Identity,
				Versions:       req.Versions,
				Accountability: copyAccountability(req.Accountability),
				Outcome:        ledger.Outcome{Status: "conflict", Detail: detail},
			}
			if err := m.append(ev); err != nil {
				return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
			}
			m.seq = ev.ArbitrationSeq
			return Outcome{Status: "rejected", Detail: detail, Event: ev}
		}
		ev := &ledger.Event{
			EventType:      "adoption",
			ArbitrationSeq: m.seq + 1,
			Identity:       req.Identity,
			Versions:       req.Versions,
			Idempotency:    &ledger.Idempotency{OperationID: op, PayloadDigest: req.PayloadDigest},
			Accountability: copyAccountability(req.Accountability),
			Outcome:        ledger.Outcome{Status: "reused", Detail: "retry under the same key and digest"},
		}
		if err := m.append(ev); err != nil {
			return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
		}
		m.seq = ev.ArbitrationSeq
		return Outcome{Status: "reused", Event: ev}
	}
	st := &opState{
		digest:         req.PayloadDigest,
		state:          StateAdopted,
		grants:         copyGrants(req.GrantsAtDecision),
		identity:       req.Identity,
		versions:       req.Versions,
		accountability: copyAccountability(req.Accountability),
		dispatchedSeq:  -1, // R29 M-1: the documented sentinel, actually assigned (pre-dispatch = no dispatch event)
	}
	ev := &ledger.Event{
		EventType:        "adoption",
		ArbitrationSeq:   m.seq + 1,
		Identity:         req.Identity,
		Versions:         req.Versions,
		Idempotency:      &ledger.Idempotency{OperationID: op, PayloadDigest: req.PayloadDigest},
		GrantsAtDecision: copyGrants(req.GrantsAtDecision),
		Accountability:   copyAccountability(req.Accountability),
		Outcome:          ledger.Outcome{Status: string(StateAdopted), Detail: "adopted by the gate"},
	}
	if err := m.append(ev); err != nil {
		return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
	}
	m.ops[op] = st
	m.seq = ev.ArbitrationSeq
	return Outcome{Status: "adopted", Event: ev}
}

// dispatchGated is the shared gate body of Dispatch and DispatchIfCurrent
// (R29 m-1: the two public methods were 30+ duplicated lines; the commit
// detail differs, everything else is identical). observedDispatchSeq < 0
// skips the version gate (the plain Dispatch form); commitDetail rides
// through to the ledger event. R31 M-2: a conditional commit with
// observed >= 0 can NEVER succeed on the current ledger grammar (an
// adopted operation has no dispatch version to match — the version gate
// below refuses every observed >= 0); its success-path detail is
// therefore unreachable by construction, and both callers pass static
// honest wording.
func (m *Machine) dispatchGated(op string, liveGrants []ledger.Grant, observedDispatchSeq int64, commitDetail string) Outcome {
	// The torn-tail gate comes FIRST (P1-2): a damaged durable form may
	// have lost the dispatch line of this very operation — re-issuing the
	// execution permit on a guess ("probably never dispatched") is the
	// falsified lossy-but-safe posture. No state change, no external
	// effect, until repair and re-Open.
	if m.tornTail {
		return Outcome{Status: "rejected",
			Detail: fmt.Sprintf("durable form %s ends in a torn tail (external damage): no state change and no execution permission until the file is repaired and the machine is re-Opened", m.path)}
	}
	st, ok := m.ops[op]
	if !ok || st.state != StateAdopted {
		if !ok {
			return Outcome{Status: "rejected", Detail: fmt.Sprintf("operation %q is not in the adopted state", op)}
		}
		return m.refuse(st, fmt.Sprintf("operation %q is in the %s state — not adoptable for dispatch", op, st.state))
	}
	if observedDispatchSeq >= 0 && observedDispatchSeq != st.dispatchedSeq {
		// R30 m-6: the reachable refusal face is forged/cross-wired
		// observations — at this gate st.dispatchedSeq is always -1 (an
		// adopted operation has no dispatch event), so the message says
		// exactly that instead of narrating a same-op CAS story the
		// architecture has ruled out, and the sentinel is explained.
		return m.refuse(st, fmt.Sprintf("conditional commit rejected (E6/C4): the caller observed dispatch seq %d but the operation has no dispatch event (version -1) — the observation was never this operation's version", observedDispatchSeq))
	}
	if !grantsCover(liveGrants, st.grants) {
		return m.refuse(st, "live grant set no longer covers the grants pinned at decision time (revocation check, 14-A4)")
	}
	// R31 M-2: the R30 detail split's two non-fresh arms were DEAD CODE —
	// an adopted operation has no dispatch event (no back-edge in the
	// ledger grammar), so at this gate st.dispatchedSeq is always -1 and
	// a conditional commit with observed >= 0 can NEVER land (it is
	// refused at the version gate above). The success detail is therefore
	// static per caller and both callers pass their own honest wording;
	// no runtime form-splitting exists to maintain.
	o := m.commit(st, StateDispatched, commitDetail)
	// E6 (C4): record the dispatch's own arbitration seq. R32 m-1 honesty:
	// with no ledger back-edge this pin has NO reachable reader on the
	// success path (an adopted operation — the only state that reaches the
	// version gate — always carries -1); the pin exists for replay
	// symmetry and a future grammar that allows re-commit, and its one
	// LIVE face is the adopted-state forged-observation refusal above.
	if o.Event != nil {
		st.dispatchedSeq = o.Event.ArbitrationSeq
	}
	return o
}

// Dispatch transitions an adopted operation to dispatched, rechecking the
// caller's LIVE grant set against the snapshot pinned at decision time
// (14-A4: a revocation must stop the effect even though the adoption stands).
func (m *Machine) Dispatch(op string, liveGrants []ledger.Grant) Outcome {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.dispatchGated(op, liveGrants, -1, "dispatched after the 14-A4 revocation check")
}

// DispatchIfCurrent is the E6 conditional commit (C4, xingchao 198232012
// §一.4): the caller pins the dispatch seq it OBSERVED, and the commit
// lands only if that version is still current at commit time. A stale
// caller (its observation invalidated by an intervening decision — the
// "D2 took effect between check and submit" race) is rejected with a
// control event, not silently reordered. The plain Dispatch stays
// version-blind (the machine dispatches whatever the caller submits —
// semantic blindness by design); this method is the OPT-IN versioned
// form for hosts whose sequencing requires the checked version to hold.
//
// WINDOW DECLARATION (the two windows of C4, pre-declared per 33号 B6;
// R29 M-2 narrowed to the mechanism's true reach):
//
//	Window 1 — "approved but not sent" (adopted, pre-dispatch): covered
//	for revocation-form interventions (14-A4 blocks before any external
//	call) and for FORGED/CROSS-WIRED observations (a seq the operation
//	never had is refused). The canonical same-operation CAS race — an
//	intervening decision on ANOTHER operation while the caller holds a
//	correct fresh observation of THIS one — is NOT detectable here: an
//	adopted operation has no dispatch event, so its version cannot go
//	stale (adopted has no back-edge in the ledger grammar). That form's
//	protection lives at the host tier (the host's own sequencing), not
//	in this gate.
//	Window 2 — "sent but unconfirmed" (post-dispatch, pre-receipt): NOT
//	covered by any pre-commit check — the effect may already be external.
//	The machine's answer is MarkUnresolved (T0 scenario 5); declaring a
//	residual window honestly is the contract — no method promises that a
//	late revocation retracts an in-flight external effect.
func (m *Machine) DispatchIfCurrent(op string, liveGrants []ledger.Grant, observedDispatchSeq int64) Outcome {
	m.mu.Lock()
	defer m.mu.Unlock()
	// observedDispatchSeq < 0 means "I never observed a dispatch" — for an
	// adopted operation that is the correct fresh-observation form (no
	// dispatch event exists yet), so the version gate is skipped (see
	// dispatchGated). R30 M-4: the ledger detail names the skipped check
	// honestly — the fresh form never ran a version comparison.
	return m.dispatchGated(op, liveGrants, observedDispatchSeq, "dispatched after the fresh-observation form (no dispatch version to check) and the 14-A4 revocation check")
}

// MarkUnresolved records 'dispatch outcome unknown' (timeout / lost receipt /
// crash at the dispatch boundary). It is legal from adopted and from
// dispatched — in both the caller asserts a dispatch attempt happened whose
// effect status is unknown. The caller reconciles; the machine never
// re-dispatches (a silent retry here is the duplicate-effect bug 14-A5
// counterexample three names).
func (m *Machine) MarkUnresolved(op string) Outcome {
	m.mu.Lock()
	defer m.mu.Unlock()
	st, ok := m.ops[op]
	if !ok {
		return Outcome{Status: "rejected", Detail: fmt.Sprintf("operation %q is unknown", op)}
	}
	if st.state != StateAdopted && st.state != StateDispatched {
		return m.refuse(st, fmt.Sprintf("operation %q is in the %s state; only adopted or dispatched operations can become unresolved", op, st.state))
	}
	return m.commit(st, StateUnresolved, "unresolved — outcome unknown, awaiting reconciliation")
}

// MarkCompleted records a successful external effect (also the reconciliation
// exit from unresolved).
func (m *Machine) MarkCompleted(op string) Outcome {
	return m.finish(op, StateCompleted, "completed")
}

// MarkFailed records a failed external effect (also the reconciliation exit
// from unresolved).
func (m *Machine) MarkFailed(op string) Outcome {
	return m.finish(op, StateFailed, "failed")
}

func (m *Machine) finish(op string, to State, detail string) Outcome {
	m.mu.Lock()
	defer m.mu.Unlock()
	st, ok := m.ops[op]
	if !ok {
		return Outcome{Status: "rejected", Detail: fmt.Sprintf("operation %q is unknown", op)}
	}
	if st.state != StateDispatched && st.state != StateUnresolved {
		return m.refuse(st, fmt.Sprintf("operation %q is in the %s state; only dispatched or unresolved operations can finish", op, st.state))
	}
	return m.commit(st, to, detail)
}

func (m *Machine) commit(st *opState, to State, detail string) Outcome {
	if m.seqExhausted() {
		return Outcome{Status: "rejected", Detail: seqExhaustedMsg}
	}
	ev := &ledger.Event{
		EventType:      "effect",
		ArbitrationSeq: m.seq + 1,
		Identity:       st.identity,
		Versions:       st.versions,
		Idempotency:    &ledger.Idempotency{OperationID: st.identity.OperationID, PayloadDigest: st.digest},
		// a COPY, not the pin: the event is returned to the caller, and a
		// caller mutating the returned event must not reach the machine's
		// pin — later durable events keep the adopted stamp (R8 M-2, the
		// output-direction twin of the R7 input-direction fix)
		Accountability: copyAccountability(st.accountability),
		Outcome:        ledger.Outcome{Status: string(to), Detail: detail},
	}
	if err := m.append(ev); err != nil {
		return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
	}
	st.state = to
	m.seq = ev.ArbitrationSeq
	return Outcome{Status: string(to), Event: ev}
}

// refuse records a control-plane refusal as a control event (E3,
// 2026-11-03): the rejected attempt is an audit fact — the 14-A4
// revocation rejection, an illegal-transition attempt — carrying the
// operation's full identity/versions/accountability pin. Control events
// never transition state (the checker's transition loop skips them) and
// never enter the idempotency registry (CONTROL_IDEM_FORBIDDEN), so the
// ledger gains the refusal record without touching replay or the
// machine's own state. The pre-E3 hole: the 14-A4 revocation check was
// the component's signature guard while every one of its firings was
// traceless (a return value only — a host had no API to audit how many
// revoked-permission attempts were blocked). Unknown-operation refusals
// stay return-value-only: there is no identity to pin (the grammar
// requires the full identity, and a control event precedes nothing).
func (m *Machine) refuse(st *opState, detail string) Outcome {
	if m.seqExhausted() {
		return Outcome{Status: "rejected", Detail: detail}
	}
	ev := &ledger.Event{
		EventType:      "control",
		ArbitrationSeq: m.seq + 1,
		Identity:       st.identity,
		Versions:       st.versions,
		Accountability: copyAccountability(st.accountability),
		Outcome:        ledger.Outcome{Status: "rejected", Detail: detail},
	}
	if err := m.append(ev); err != nil {
		return Outcome{Status: "rejected", Detail: detail + " (refusal not recorded: " + err.Error() + ")"}
	}
	m.seq = ev.ArbitrationSeq
	return Outcome{Status: "rejected", Detail: detail, Event: ev}
}

// Events returns every complete event line currently in the durable form
// (and only those — a torn tail, if present, is excluded). In-memory mode
// has no durable form; the caller drives scenarios through the API instead.
func (m *Machine) Events() ([]ledger.Event, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	lines, _, err := ledger.LoadDocument(m.path)
	if err != nil {
		return nil, err
	}
	events := make([]ledger.Event, 0, len(lines))
	for _, l := range lines {
		events = append(events, l.Event)
	}
	return events, nil
}

// append writes one event as a JSON line. The write is atomic at file scope:
// the full new content (the parsed complete lines + this line) goes to a
// temp file in the same directory, which is then renamed over the target —
// a crash leaves either the old or the new file. A torn tail, if present,
// never reaches the rewrite: the write-time re-check inside refuses the
// append first, so the damaged bytes survive for manual repair (P1-2).
func (m *Machine) append(ev *ledger.Event) error {
	if m.path == "" {
		return nil
	}
	line, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	existing, err := os.ReadFile(m.path)
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	// rebuild from the parser's boundary definition, byte for byte: the
	// durable unit is the parsed complete line, so a final complete line
	// without a trailing newline survives (the loader accepts it; the
	// rewrite must not delete what the loader accepted — R2 BLOCKER).
	// A torn tail never reaches this rebuild: the write-time re-check
	// below refuses first, so damaged bytes are never erased. Concatenating
	// onto raw bytes instead would fuse a torn tail and the new line into
	// one unparseable line.
	parsed, tornNow, err := ledger.ParseLines(existing)
	if err != nil {
		return err
	}
	// Write-time torn-tail re-check (P1-2, the adopt-side twin of
	// evidlog's R10 face-B byte re-check): the Open-time flag is a view,
	// the bytes are the truth — out-of-band damage between Open and this
	// write is caught here, and refusing here is what guarantees the
	// rebuild above never erases damaged evidence.
	if tornNow {
		return fmt.Errorf("[ADOPT.TORN_TAIL] %s: append refused — the durable form ends in an unparseable torn tail (externally damaged file); repair the file, then re-Open", m.path)
	}
	// Write-time seq-continuity gate (R11 MAJOR — the counterpart of
	// evidlog's R10 face-B re-check): the Open-time view may be stale after
	// an out-of-band or stale-instance write. Under the machine's
	// strictly-increasing seq the last parsed event must be exactly this
	// event's predecessor — every legal path (14-A5 crash-recovery
	// re-Open, a surviving no-newline complete line) passes by
	// construction; the ONLY thing this gate can reject is a write whose
	// view of the file is stale, and it fails HERE, in the guilty caller,
	// instead of emitting a false success that poisons the file for the
	// next Open (probes: sequential stale write, stale double dispatch —
	// both silently "succeeded" pre-gate).
	want := int64(0)
	if len(parsed) > 0 {
		want = parsed[len(parsed)-1].Event.ArbitrationSeq + 1
	}
	if ev.ArbitrationSeq != want {
		return fmt.Errorf("[ADOPT.STALE_WRITER] %s: append refused — the durable form's last seq is %d but this instance is about to write %d; the Open-time view is stale (foreign or stale-instance write). Re-Open to absorb the file, then decide", m.path, want-1, ev.ArbitrationSeq)
	}
	next := make([]byte, 0, len(existing)+len(line)+1)
	for _, l := range parsed {
		next = append(next, l.Raw...)
		next = append(next, '\n')
	}
	next = append(next, line...)
	next = append(next, '\n')
	dir, base := filepath.Split(m.path)
	tmp, err := os.CreateTemp(dir, "."+base+".*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := tmp.Write(next); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	// Whole-file replace keeps the durable file's permission bits and
	// never widens them (P1-1, 2026-11-03 external review, overturning the
	// L14 first-write-0644 ruling): an existing file keeps the operator's
	// exact mode, and a first durable write keeps os.CreateTemp's
	// owner-only 0600. os.Chmod bypasses umask by design, so a 0644
	// default silently widened visibility past what a umask 077 deployment
	// asked for — wider audit readability is a deployment decision
	// (explicit chmod or config), never a component default.
	mode, err := durableMode(m.path)
	if err != nil {
		return err
	}
	if err := os.Chmod(tmp.Name(), mode); err != nil {
		return err
	}
	return os.Rename(tmp.Name(), m.path)
}

// durableMode returns the permission mode a whole-file replace should
// carry: the existing file's exact bits, or owner-only 0600 for a file
// that does not exist yet. Any other Stat failure is an error, not a
// silent new-file default (P1-1).
func durableMode(path string) (os.FileMode, error) {
	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) {
			return 0o600, nil
		}
		return 0, err
	}
	return info.Mode().Perm(), nil
}

// checkRequest validates the request's document form against
// adoption.schema.json — and first that every string field is valid UTF-8:
// json.Marshal silently replaces invalid bytes with U+FFFD, so a request
// carrying them would pass the gate while the durable form registers a
// LAUNDERED key — the caller retries under the original key, the machine
// sees a new operation, and the file ends up with two adopted events under
// one laundered id: a ledger the machine's own loader permanently rejects
// (R5 BLOCKER). The gate rejects what it cannot byte-represent.
func (m *Machine) checkRequest(req *Request) []string {
	if errs := requestUTF8Errors(req); len(errs) > 0 {
		return errs
	}
	raw, err := json.Marshal(req)
	if err != nil {
		return []string{"request marshal failed: " + err.Error()}
	}
	var doc map[string]any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&doc); err != nil {
		return []string{"request decode failed: " + err.Error()}
	}
	return CheckRequest(doc)
}

// copyGrants deep-copies the grant slice: the pin must not alias the
// caller's memory — a caller that mutates its slice after Adopt would
// shrink or retarget the 14-A4 baseline the dispatch recheck compares
// against (R7 M-2).
func copyGrants(src []ledger.Grant) []ledger.Grant {
	if src == nil {
		return nil
	}
	out := make([]ledger.Grant, len(src))
	for i, g := range src {
		out[i] = g
		out[i].Actions = append([]string(nil), g.Actions...)
	}
	return out
}

// copyAccountability deep-copies the accountability triple: the durable
// form stamps it on every effect event, and a caller mutating its pointer
// after Adopt would fork later events' audit attribution away from the
// adopted event's (R7 M-2).
func copyAccountability(src *ledger.Accountability) *ledger.Accountability {
	if src == nil {
		return nil
	}
	cp := *src
	return &cp
}

// requestUTF8Errors names every request string field that is not valid
// UTF-8.
func requestUTF8Errors(req *Request) []string {
	var errs []string
	add := func(field, v string) {
		if !utf8.ValidString(v) {
			errs = append(errs, fmt.Sprintf("request field %s is not valid UTF-8 — the durable form cannot byte-represent it (json.Marshal would launder it to U+FFFD, forking the caller's key from the ledger's)", field))
		}
	}
	add("adoption_version", req.AdoptionVersion)
	add("identity.business_request_id", req.Identity.BusinessRequestID)
	add("identity.evaluation_revision", req.Identity.EvaluationRevision)
	add("identity.operation_id", req.Identity.OperationID)
	add("payload_digest", req.PayloadDigest)
	add("versions.evidence", req.Versions.Evidence)
	add("versions.rule", req.Versions.Rule)
	add("versions.model", req.Versions.Model)
	add("versions.readout", req.Versions.Readout)
	add("versions.policy", req.Versions.Policy)
	for i, g := range req.GrantsAtDecision {
		add(fmt.Sprintf("grants_at_decision[%d].kind", i), g.Kind)
		add(fmt.Sprintf("grants_at_decision[%d].selector", i), g.Selector)
		add(fmt.Sprintf("grants_at_decision[%d].effect", i), g.Effect)
		for j, a := range g.Actions {
			add(fmt.Sprintf("grants_at_decision[%d].actions[%d]", i, j), a)
		}
	}
	if req.Accountability != nil {
		add("accountability.session", req.Accountability.Session)
		add("accountability.skill", req.Accountability.Skill)
		add("accountability.role", req.Accountability.Role)
	}
	return errs
}

// grantsCover reports whether the live set still covers every pinned grant:
// same kind and selector, every pinned action present, and an effect at
// least as severe. An empty pinned set is vacuously covered — requests are
// required to carry at least one grant by the adoption schema, so live
// machines see a non-empty pin.
func grantsCover(live, pinned []ledger.Grant) bool {
	for _, p := range pinned {
		covered := false
		for _, l := range live {
			if l.Kind != p.Kind || l.Selector != p.Selector {
				continue
			}
			if !containsAll(l.Actions, p.Actions) {
				continue
			}
			if effectRank(l.Effect) < effectRank(p.Effect) {
				continue
			}
			covered = true
			break
		}
		if !covered {
			return false
		}
	}
	return true
}

func containsAll(have, want []string) bool {
	for _, w := range want {
		found := false
		for _, h := range have {
			if h == w {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	return true
}

func effectRank(e string) int {
	switch e {
	case "none":
		return 0
	case "reversible":
		return 1
	case "irreversible":
		return 2
	default:
		return -1
	}
}

// Digest computes the idempotency payload digest: sha256 of JCS(payload) —
// the same shape and stack as the base's ContractHash.
func Digest(payload any) (string, error) {
	b, err := rfc8785.Canonicalize(payload)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(b)
	return fmt.Sprintf("sha256:%x", sum), nil
}
