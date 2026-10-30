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

	"festival-dev/go/internal/schemalib"
)

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
	ArbitrationSeq   int             `json:"arbitration_seq"`
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
// rules: arbitration_seq non-decreasing; one payload digest per operation —
// a changed payload under the same key is a rejection (15 §B4); an effect
// event needs an earlier adoption event for the same operation (the
// single-writer discipline: effects only exist downstream of an adoption).
func Errors(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	// cross-event rules on the typed view
	var d Document
	raw, err := json.Marshal(doc)
	if err != nil {
		return []string{"ledger: internal re-marshal failed: " + err.Error()}
	}
	if err := json.Unmarshal(raw, &d); err != nil {
		return []string{"ledger: internal re-parse failed: " + err.Error()}
	}
	var errs []string
	prevSeq := -1
	for i, e := range d.Events {
		if e.ArbitrationSeq < prevSeq {
			errs = append(errs, fmt.Sprintf("events/%d: arbitration_seq %d breaks the non-decreasing order", i, e.ArbitrationSeq))
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
	adopted := map[string]bool{}
	for i, e := range d.Events {
		if e.EventType == "adoption" {
			adopted[e.Identity.OperationID] = true
		} else if !adopted[e.Identity.OperationID] {
			errs = append(errs, fmt.Sprintf("events/%d: effect event for operation %q has no earlier adoption event — a bypass write into the ledger, not a machine transition", i, e.Identity.OperationID))
		}
	}
	return errs
}
