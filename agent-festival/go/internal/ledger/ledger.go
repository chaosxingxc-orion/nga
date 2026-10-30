// Package ledger provides the event-ledger types and checker (piece 4 of the
// NGA unified-architecture growth layer). The ledger is append-only and holds
// adoption/effect events carrying the three-layer business identity, the P5
// five-dimension version binding, and the correlation keys the replay matcher
// consumes. The adopt state machine (piece 2) is the single writer; replay
// (piece 6) is a reader; this package itself is types + document checking.
//
// The schema is validated with the same industry stack as the base
// (santhosh-tekuri/jsonschema, fail-closed), and the cross-event rules JSON
// Schema cannot express (arbitration_seq monotonicity, payload-digest
// stability per operation) are checked in code — mirroring schema/ledger.py
// (the Python oracle) so both sides stay behaviorally aligned.
package ledger

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

// SchemaDir is where event-ledger.schema.json lives (set by init from the
// same CWD probe the base packages use).
var SchemaPath string

func init() {
	for _, root := range []string{"../../schema", "../../../schema", "../schema", "."} {
		p := filepath.Join(root, "event-ledger.schema.json")
		if _, err := os.Stat(p); err == nil {
			SchemaPath = p
			return
		}
	}
}

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

// Event is one adoption or effect entry.
type Event struct {
	EventType     string        `json:"event_type"`
	ArbitrationSeq int         `json:"arbitration_seq"`
	Identity      Identity     `json:"identity"`
	Versions      Versions     `json:"versions"`
	Idempotency   *Idempotency `json:"idempotency,omitempty"`
	Outcome       Outcome      `json:"outcome,omitempty"`
	Accountability *Accountability `json:"accountability,omitempty"`
}

// Document is a parsed ledger file.
type Document struct {
	LedgerVersion string  `json:"ledger_version"`
	Events        []Event `json:"events"`
}

// Fixture pins (popped before validation, same discipline as the base).
type Fixture struct {
	Doc        map[string]any
	ExpectMatch string
	ParseError string
}

// LoadFixture reads a ledger fixture and pops its _expect* pins.
func LoadFixture(path string) (*Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	f := &Fixture{}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		f.ParseError = "document rejected at parse: " + err.Error()
		return f, nil
	}
	if m, ok := doc["_expect_match"].(string); ok {
		f.ExpectMatch = m
	}
	delete(doc, "_expect")
	delete(doc, "_expect_match")
	f.Doc = doc
	return f, nil
}

// compiled holds the fail-closed schema (nil until first use; ledger has no
// cross-schema $refs so a local compile is enough — the base's frozen engine
// only resolves cross-document refs into the contract schema).
var compiled *jsonschema.Schema
var compileErr error

func ensureCompiled() error {
	if compiled != nil || compileErr != nil {
		return compileErr
	}
	if SchemaPath == "" {
		compileErr = fmt.Errorf("event-ledger schema not found")
		return compileErr
	}
	raw, err := os.ReadFile(SchemaPath)
	if err != nil {
		compileErr = err
		return err
	}
	var doc any
	if err := json.Unmarshal(raw, &doc); err != nil {
		compileErr = err
		return err
	}
	c := jsonschema.NewCompiler()
	c.UseRegexpEngine(nil) // ledger schema has no patterns; keep the base's engine choice irrelevant here
	if err := c.AddResource("https://agent-festival.local/schema/event-ledger/0.1.0", doc); err != nil {
		compileErr = err
		return err
	}
	compiled, compileErr = c.Compile("https://agent-festival.local/schema/event-ledger/0.1.0")
	return compileErr
}

// Errors validates a ledger document against the schema plus the cross-event
// rules (monotonic arbitration_seq; one payload digest per operation — a
// changed payload under the same key is a rejection, 15 §B4).
func Errors(doc map[string]any) []string {
	if err := ensureCompiled(); err != nil {
		return []string{"ledger: schema unavailable: " + err.Error() + " (fail closed)"}
	}
	var errs []string
	if err := compiled.Validate(doc); err != nil {
		errs = append(errs, "schema: "+err.Error())
		return errs
	}
	// cross-event rules on the typed view
	var d Document
	raw, _ := json.Marshal(doc)
	if err := json.Unmarshal(raw, &d); err != nil {
		return append(errs, "ledger: internal re-parse failed: "+err.Error())
	}
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
	return errs
}
