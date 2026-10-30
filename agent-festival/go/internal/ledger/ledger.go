// Package ledger provides the event-ledger types and checker (piece 4 of the
// NGA unified-architecture growth layer). The ledger is append-only and holds
// adoption/effect events carrying the three-layer business identity, the P5
// five-dimension version binding, and the correlation keys the replay matcher
// consumes. The adopt state machine (piece 2) is the single writer; replay
// (piece 6) is a reader; this package itself is types + document checking.
//
// The schema is compiled through internal/schemalib (the growth layer's
// shared engine entry: santhosh + regexp2, Python-parity '$' semantics), and
// the cross-event rules JSON Schema cannot express (arbitration_seq
// monotonicity, payload-digest stability per operation, adoption-before-effect)
// are checked in code — mirroring schema/ledger.py (the Python oracle) so
// both sides stay behaviorally aligned.
package ledger

import (
	"encoding/json"
	"fmt"
	"math"
	"strings"

	"festival-dev/go/internal/schemalib"
)

// AdoptStatuses / EffectStatuses are the status families. Package-level so
// the lockstep test can compare them against the schema enum (the status
// vocabulary exists as several copies — schema enum, these sets, the Python
// sets, the machine's State constants — and the lockstep test is what makes
// the schema enum the enforced single source, R3 m-2).
var AdoptStatuses = map[string]bool{"adopted": true, "reused": true, "conflict": true}
var EffectStatuses = map[string]bool{"dispatched": true, "unresolved": true, "completed": true, "failed": true}

// floatSyntaxBeyondExactDomain names events whose arbitration_seq is a
// float-syntax number beyond ±2^53, where float64 no longer represents
// every integer exactly.
func floatSyntaxBeyondExactDomain(doc map[string]any) []string {
	events, _ := doc["events"].([]any)
	var errs []string
	for i, e := range events {
		em, _ := e.(map[string]any)
		if em == nil {
			continue
		}
		n, ok := em["arbitration_seq"].(json.Number)
		if !ok {
			continue
		}
		if _, err := n.Int64(); err == nil {
			continue // integer syntax: exact in any domain
		}
		s := n.String()
		if !strings.ContainsAny(s, ".eE") {
			continue // integer syntax beyond int64: the typed view names it
		}
		f, err := n.Float64()
		if err != nil {
			continue
		}
		if f == math.Trunc(f) && (f > 1<<53 || f < -(1<<53)) {
			errs = append(errs, fmt.Sprintf("events/%d: arbitration_seq %s uses float syntax beyond the exact-representation domain (±2^53) — the value a parser recovers depends on its float rounding, not on the document", i, n.String()))
		}
	}
	return errs
}

// copyDoc deep-copies a decoded JSON document, preserving json.Number.
func copyDoc(node any) any {
	switch v := node.(type) {
	case map[string]any:
		out := make(map[string]any, len(v))
		for k, child := range v {
			out[k] = copyDoc(child)
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, child := range v {
			out[i] = copyDoc(child)
		}
		return out
	default:
		return v
	}
}

// normalizeIntegralNumbers converts json.Number values with integral values
// that fit int64 into int64, in place. Without this, a seq written "5.0"
// would pass the schema (spec: integer-valued) but fail the typed re-parse —
// forking the dual validators' verdicts on the same document (R5 M-3).
func normalizeIntegralNumbers(node any) {
	switch v := node.(type) {
	case map[string]any:
		for k, child := range v {
			if n, ok := child.(json.Number); ok {
				if i, err := n.Int64(); err == nil {
					v[k] = i
					continue
				}
				if f, err := n.Float64(); err == nil && f == math.Trunc(f) &&
					f >= -(1<<53) && f <= 1<<53 {
					v[k] = int64(f)
					continue
				}
			}
			normalizeIntegralNumbers(child)
		}
	case []any:
		for i, child := range v {
			if n, ok := child.(json.Number); ok {
				if j, err := n.Int64(); err == nil {
					v[i] = j
					continue
				}
				if f, err := n.Float64(); err == nil && f == math.Trunc(f) &&
					f >= -(1<<53) && f <= 1<<53 {
					v[i] = int64(f)
					continue
				}
			}
			normalizeIntegralNumbers(child)
		}
	}
}

// notATransition formats the illegal-transition error.
func notATransition(i int, op, status, from string) string {
	if from == "" {
		from = "nothing"
	}
	return fmt.Sprintf("events/%d: operation %q: status %q after %q is not a legal state-machine transition — a bypass write into the ledger, not a machine transition", i, op, status, from)
}

// Version is the ledger document version — the Go-side twin of the schema's
// ledger_version const (kept in lockstep by the fixture suites: every
// fixture and every machine-written document carry it).
const Version = "0.1.0"

// SchemaPath is where event-ledger.schema.json was found ("" = not found;
// exported so drivers can resolve the fixture directory from it).
var SchemaPath = schemalib.FindSchema("event-ledger.schema.json")

// schema is the fail-closed compile-once handle for the event ledger schema.
var schema = schemalib.NewLazy(
	"https://agent-festival.local/schema/event-ledger/0.1.0", SchemaPath)

// Identity is the three-layer business identity (NGA §7.2).
type Identity struct {
	BusinessRequestID  string `json:"business_request_id"`
	EvaluationRevision string `json:"evaluation_revision,omitempty"`
	OperationID        string `json:"operation_id"`
}

// Versions is the P5 five-dimension version binding.
type Versions struct {
	Evidence string `json:"evidence"`
	Rule     string `json:"rule"`
	Model    string `json:"model"`
	Readout  string `json:"readout"`
	Policy   string `json:"policy"`
}

// Idempotency is the replay matcher's key (operation + payload digest).
type Idempotency struct {
	OperationID   string `json:"operation_id"`
	PayloadDigest string `json:"payload_digest"`
}

// Outcome is the event's verdict.
type Outcome struct {
	Status string `json:"status"`
	Detail string `json:"detail,omitempty"`
}

// Accountability is the festival D31 triple, orthogonal to the business identity.
type Accountability struct {
	Session string `json:"session"`
	Skill   string `json:"skill"`
	Role    string `json:"role"`
}

// Grant is one entry of a grant set pinned at a decision point. It rides the
// adoption event so the dispatch-time revocation check (14-A4) can compare
// the live grant set against the pin even after a crash — the event file is
// the adopt machine's only durable state.
type Grant struct {
	Kind     string   `json:"kind"`
	Selector string   `json:"selector"`
	Actions  []string `json:"actions"`
	Effect   string   `json:"effect"`
}

// Event is one adoption or effect entry.
type Event struct {
	EventType        string          `json:"event_type"`
	ArbitrationSeq   int64           `json:"arbitration_seq"`
	Identity         Identity        `json:"identity"`
	Versions         Versions        `json:"versions"`
	Idempotency      *Idempotency    `json:"idempotency,omitempty"`
	GrantsAtDecision []Grant         `json:"grants_at_decision,omitempty"`
	Outcome          Outcome         `json:"outcome"`
	Accountability   *Accountability `json:"accountability,omitempty"`
}

// Document is a parsed ledger document.
type Document struct {
	LedgerVersion string  `json:"ledger_version"`
	Events        []Event `json:"events"`
}

// Errors validates a ledger document against the schema plus the cross-event
// rules: arbitration_seq strictly increasing; one payload digest per operation —
// a changed payload under the same key is a rejection (15 §B4); and the
// event-sequence grammar of the single writer — each operation opens with
// exactly one adopted adoption event, and every later event for it (reused /
// conflict / effects) only exists downstream of that adoption. A violation
// of the grammar is a bypass write into the ledger, not a machine
// transition. Status families never cross the event-type boundary; effect
// events carry no grants_at_decision (the pin rides the adopted event
// only); idempotency.operation_id equals identity.operation_id on every
// event carrying idempotency; and each operation's effect events follow the
// machine's own transition DAG in file order. Aggregation contract: this
// checker returns at the first failing family while the Python oracle
// appends and continues — error-set composition may differ on
// multi-violation documents (the verdict never does), and invalid fixtures
// are disciplined to carry exactly one violation. The monotonicity
// check assumes the map input was decoded with json.Decoder.UseNumber:
// float64 rounding is monotonic, so DECREASING pairs are caught with or
// without exact integers — what a float64-decoded map breaks is the other
// direction, silently rejecting LEGAL consecutive seqs that cross 2^53 (the
// suite loader and the adopt machine's line decoder both keep this
// discipline; future callers — the replay reader — must too).
func Errors(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	// work on a copy: the normalization below rewrites number nodes, and a
	// validator must not mutate its caller's document (the replay reader
	// will reuse the same map)
	if copied, ok := copyDoc(doc).(map[string]any); ok {
		doc = copied
	}
	// normalize integral float-syntax numbers (json.Number like "5.0") into
	// the int domain: the reference implementation's Number.isInteger
	// accepts 5.0, so parity accepts it — and the comparisons below stay in
	// the native integer domain (the double charter). Non-integral or
	// beyond-int64 values stay as json.Number and fail the typed re-parse,
	// which is the int64-domain rejection.
	// float syntax beyond the exact-representation domain: the value a
	// parser recovers for such literals depends on its float rounding
	// (Python's float() folds odd values past 2^53), so the document has no
	// parser-independent value — both validators reject it by rule rather
	// than disagreeing about what it says.
	if errs := floatSyntaxBeyondExactDomain(doc); len(errs) > 0 {
		return errs
	}
	normalizeIntegralNumbers(doc)
	// cross-event rules on the typed view
	var d Document
	raw, err := json.Marshal(doc)
	if err != nil {
		return []string{"ledger: internal re-marshal failed: " + err.Error()}
	}
	if err := json.Unmarshal(raw, &d); err != nil {
		return []string{"ledger: document does not fit the typed ledger view (an integer field beyond the int64 domain, or a type mismatch — the machine never writes such values): " + err.Error()}
	}
	var errs []string
	prevSeq := int64(-1)
	for i, e := range d.Events {
		if e.ArbitrationSeq <= prevSeq {
			errs = append(errs, fmt.Sprintf("events/%d: arbitration_seq %d breaks the strictly-increasing order — the machine never repeats or rewinds an arbitration sequence", i, e.ArbitrationSeq))
		}
		prevSeq = e.ArbitrationSeq
	}
	seen := map[string]string{}
	for i, e := range d.Events {
		if e.Idempotency == nil {
			continue
		}
		op, dig := e.Idempotency.OperationID, e.Idempotency.PayloadDigest
		if prev, has := seen[op]; has && prev != dig {
			errs = append(errs, fmt.Sprintf("events/%d: operation_id %q carries payload_digest %q but an earlier event recorded %q — changed payload under the same key", i, op, dig, prev))
		}
		seen[op] = dig
	}
	// status families, transitions, and the grants-on-effect rule
	for i, e := range d.Events {
		ok := AdoptStatuses[e.Outcome.Status]
		if e.EventType == "effect" {
			ok = EffectStatuses[e.Outcome.Status]
		}
		if !ok {
			// the label names the status's OWN family — that is the
			// vocabulary crossing being reported. (The empty-status and
			// unknown-status branches are unreachable — the schema's
			// required outcome + status enum constrain the value before the
			// typed view sees it.)
			family := "effect"
			if AdoptStatuses[e.Outcome.Status] {
				family = "adoption"
			}
			errs = append(errs, fmt.Sprintf("events/%d: %s event carries the %s-family status %q — the status vocabulary never crosses the event-type boundary", i, e.EventType, family, e.Outcome.Status))
		}
		if e.EventType == "effect" || e.Outcome.Status != "adopted" {
			if len(e.GrantsAtDecision) > 0 {
				errs = append(errs, fmt.Sprintf("events/%d: %s event (status %q) for operation %q carries grants_at_decision — the grant pin rides the adopted event only (stamped once, at the decision point)", i, e.EventType, e.Outcome.Status, e.Identity.OperationID))
			}
		}
	}
	// per-operation transition order: mirror the adopt machine's own DAG —
	// adopted -> dispatched | unresolved; dispatched -> unresolved |
	// completed | failed; unresolved -> completed | failed. An effect event
	// that is not a legal transition from the operation's current state is a
	// bypass write; without this the loader absorbs e.g. completed-before-
	// dispatched and the machine resumes from a state it can never be in,
	// then writes events that violate its own DAG (R3 M-1).
	state := map[string]string{}
	for i, e := range d.Events {
		op := e.Identity.OperationID
		if e.EventType != "effect" {
			if e.Outcome.Status == "adopted" {
				state[op] = "adopted"
			}
			continue // reused / conflict record facts, they do not transition
		}
		from := state[op]
		switch e.Outcome.Status {
		case "dispatched":
			if from != "adopted" {
				errs = append(errs, notATransition(i, op, "dispatched", from))
			}
			state[op] = "dispatched"
		case "unresolved":
			if from != "adopted" && from != "dispatched" {
				errs = append(errs, notATransition(i, op, "unresolved", from))
			}
			state[op] = "unresolved"
		case "completed", "failed":
			if from != "dispatched" && from != "unresolved" {
				errs = append(errs, notATransition(i, op, e.Outcome.Status, from))
			}
			state[op] = e.Outcome.Status
		}
	}
	// the key coupling: the machine writes idempotency.operation_id and
	// identity.operation_id EQUAL on every event that carries idempotency —
	// a mismatch registers a phantom operation the caller never created and
	// lets the machine write zero-identity events under it, bricking its own
	// ledger (R6 BLOCKER).
	for i, e := range d.Events {
		if e.Idempotency != nil && e.Idempotency.OperationID != e.Identity.OperationID {
			errs = append(errs, fmt.Sprintf("events/%d: idempotency.operation_id %q does not match identity.operation_id %q — the machine writes them equal; a mismatch is a bypass write, not a machine transition", i, e.Idempotency.OperationID, e.Identity.OperationID))
		}
	}
	adopted := map[string]bool{}
	for i, e := range d.Events {
		op := e.Identity.OperationID
		if e.EventType == "adoption" {
			if e.Outcome.Status == "adopted" {
				if adopted[op] {
					errs = append(errs, fmt.Sprintf("events/%d: operation %q already has an adopted event — a second adopted event would re-pin the machine's state mid-flight (a bypass write, not a machine transition)", i, op))
				}
				adopted[op] = true
			} else if !adopted[op] {
				// reused/conflict before any adopted event for the operation
				errs = append(errs, fmt.Sprintf("events/%d: %s event for operation %q precedes its adopted event — a bypass write into the ledger, not a machine transition", i, e.EventType, op))
			}
		} else if !adopted[op] {
			errs = append(errs, fmt.Sprintf("events/%d: effect event for operation %q precedes its adopted event — a bypass write into the ledger, not a machine transition", i, op))
		}
	}
	return errs
}
