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
// tail line from an earlier partial write is skipped when loading, so
// recovery resumes at the last complete event boundary. Because the event
// file is the machine's only durable state, the pinned grants ride the
// adoption event; otherwise the crash would silently void the revocation
// check. File-level tamper-proofing is out of scope (12 §6: append-only is
// not tamper-evidence).
package adopt

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"festival-dev/go/internal/ledger"
	"festival-dev/go/internal/rfc8785"
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
// adoption.schema.json (this package's CheckRequest, or the Python oracle);
// the machine itself trusts its caller and enforces only the state rules.
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

// Machine is the adoption gate. Use Open to attach a durable JSONL file.
type Machine struct {
	mu   sync.Mutex
	ops  map[string]*opState // keyed by operation_id
	seq  int                 // last arbitration sequence written (0-based)
	path string              // append-only JSONL file ("" = in-memory only)
}

// opState is the in-memory projection of one operation's events. Every field
// is reconstructed from the event file on load; nothing is kept only in RAM.
type opState struct {
	digest   string
	state    State
	grants   []ledger.Grant // pinned at adoption (14-A4 revocation-check baseline)
	identity ledger.Identity
	versions ledger.Versions
}

// Open loads (or starts) the durable form at path. A torn tail line — the
// residue of a crash between 'write full content' and 'rename' — is skipped:
// events end at the last complete line, and the machine resumes from there.
func Open(path string) (*Machine, error) {
	m := &Machine{ops: map[string]*opState{}, seq: -1, path: path}
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return m, nil
	}
	if err != nil {
		return nil, err
	}
	lineStart := 0
	for i := 0; i <= len(raw); i++ {
		if i != len(raw) && raw[i] != '\n' {
			continue
		}
		line := raw[lineStart:i]
		lineStart = i + 1
		if len(line) == 0 {
			continue
		}
		var e ledger.Event
		if json.Unmarshal(line, &e) != nil {
			continue // torn tail: resume from the last complete line
		}
		m.replayEvent(&e)
	}
	return m, nil
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
		st = &opState{}
		m.ops[op] = st
	}
	st.digest = e.Idempotency.PayloadDigest
	st.identity = e.Identity
	st.versions = e.Versions
	if len(e.GrantsAtDecision) > 0 {
		st.grants = e.GrantsAtDecision
	}
	if s := State(e.Outcome.Status); s == StateAdopted || s == StateDispatched ||
		s == StateUnresolved || s == StateCompleted || s == StateFailed {
		st.state = s
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
	m.mu.Lock()
	defer m.mu.Unlock()
	op := req.Identity.OperationID
	if st, ok := m.ops[op]; ok {
		if st.digest != req.PayloadDigest {
			detail := fmt.Sprintf("operation_id %q carries payload_digest %q but an earlier event recorded %q — changed payload under the same key", op, req.PayloadDigest, st.digest)
			ev := &ledger.Event{
				EventType:      "adoption",
				ArbitrationSeq: m.seq + 1,
				Identity:       req.Identity,
				Versions:       req.Versions,
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
			Outcome:        ledger.Outcome{Status: "reused", Detail: "retry under the same key and digest"},
		}
		if err := m.append(ev); err != nil {
			return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
		}
		m.seq = ev.ArbitrationSeq
		return Outcome{Status: "reused", Event: ev}
	}
	st := &opState{
		digest:   req.PayloadDigest,
		state:    StateAdopted,
		grants:   req.GrantsAtDecision,
		identity: req.Identity,
		versions: req.Versions,
	}
	ev := &ledger.Event{
		EventType:        "adoption",
		ArbitrationSeq:   m.seq + 1,
		Identity:         req.Identity,
		Versions:         req.Versions,
		Idempotency:      &ledger.Idempotency{OperationID: op, PayloadDigest: req.PayloadDigest},
		GrantsAtDecision: req.GrantsAtDecision,
		Outcome:          ledger.Outcome{Status: string(StateAdopted), Detail: "adopted by the gate"},
	}
	if req.Accountability != nil {
		ev.Accountability = req.Accountability
	}
	if err := m.append(ev); err != nil {
		return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
	}
	m.ops[op] = st
	m.seq = ev.ArbitrationSeq
	return Outcome{Status: "adopted", Event: ev}
}

// Dispatch transitions an adopted operation to dispatched, rechecking the
// caller's LIVE grant set against the snapshot pinned at decision time
// (14-A4: a revocation must stop the effect even though the adoption stands).
func (m *Machine) Dispatch(op string, liveGrants []ledger.Grant) Outcome {
	m.mu.Lock()
	defer m.mu.Unlock()
	st, ok := m.ops[op]
	if !ok || st.state != StateAdopted {
		return Outcome{Status: "rejected", Detail: fmt.Sprintf("operation %q is not in the adopted state", op)}
	}
	if !grantsCover(liveGrants, st.grants) {
		return Outcome{Status: "rejected",
			Detail: "live grant set no longer covers the grants pinned at decision time (revocation check, 14-A4)"}
	}
	return m.commit(st, StateDispatched, "dispatched after the 14-A4 revocation check")
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
		return Outcome{Status: "rejected",
			Detail: fmt.Sprintf("operation %q is in the %s state; only adopted or dispatched operations can become unresolved", op, st.state)}
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
		return Outcome{Status: "rejected", Detail: fmt.Sprintf("operation %q is in the %s state; only dispatched or unresolved operations can finish", op, st.state)}
	}
	return m.commit(st, to, detail)
}

func (m *Machine) commit(st *opState, to State, detail string) Outcome {
	ev := &ledger.Event{
		EventType:      "effect",
		ArbitrationSeq: m.seq + 1,
		Identity:       st.identity,
		Versions:       st.versions,
		Idempotency:    &ledger.Idempotency{OperationID: st.identity.OperationID, PayloadDigest: st.digest},
		Outcome:        ledger.Outcome{Status: string(to), Detail: detail},
	}
	if err := m.append(ev); err != nil {
		return Outcome{Status: "rejected", Detail: "ledger append failed: " + err.Error()}
	}
	st.state = to
	m.seq = ev.ArbitrationSeq
	return Outcome{Status: string(to), Event: ev}
}

// Events returns every complete event line currently in the durable form
// (and only those — a torn tail, if present, is excluded). In-memory mode
// has no durable form; the caller drives scenarios through the API instead.
func (m *Machine) Events() ([]ledger.Event, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	raw, err := os.ReadFile(m.path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var events []ledger.Event
	lineStart := 0
	for i := 0; i <= len(raw); i++ {
		if i != len(raw) && raw[i] != '\n' {
			continue
		}
		line := raw[lineStart:i]
		lineStart = i + 1
		if len(line) == 0 {
			continue
		}
		var e ledger.Event
		if json.Unmarshal(line, &e) != nil {
			continue
		}
		events = append(events, e)
	}
	return events, nil
}

// append writes one event as a JSON line. The write is atomic at file scope:
// the full new content (existing complete lines + this line) goes to a temp
// file in the same directory, which is then renamed over the target — a
// crash leaves either the old or the new file. A torn tail left by whatever
// crashed earlier is thereby healed away on the next successful append.
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
	// heal a torn tail: the durable unit is the complete line, so anything
	// after the last newline is crash residue and is dropped — concatenating
	// onto it would fuse two events into one unparseable line.
	if n := bytes.LastIndexByte(existing, '\n'); n >= 0 {
		existing = existing[:n+1]
	} else {
		existing = nil
	}
	next := make([]byte, 0, len(existing)+len(line)+1)
	next = append(next, existing...)
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
	return os.Rename(tmp.Name(), m.path)
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
