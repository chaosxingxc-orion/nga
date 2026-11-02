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
	"strings"

	"github.com/openjiuwen/agent-festival/go/internal/schemalib"
)

// AdoptStatuses / EffectStatuses are the status families. Package-level so
// the lockstep test can compare them against the schema enum (the status
// vocabulary exists as several copies — schema enum, these sets, the Python
// sets, the machine's State constants — and the lockstep test is what makes
// the schema enum the enforced single source, R3 m-2).
var AdoptStatuses = map[string]bool{"adopted": true, "reused": true, "conflict": true}
var EffectStatuses = map[string]bool{"dispatched": true, "unresolved": true, "completed": true, "failed": true}

// User ruling 2026-11-02: this package does no float math — the seq domain
// is a machine counter, and integer LITERALS are the only writable form.
// floatSyntax enforces that: any arbitration_seq json.Number that is not
// Int64-parseable (0.0, 1e0, 1.5 — even inside ±2^53, even
// integer-valued) is rejected by rule. The old charter accepted
// integer-valued float syntax inside the domain (JCS analogy) — retired:
// JCS governs the SIGNATURE payload only, never the counter; the
// normalization layer and the ±2^53 sub-domain rule are gone with it.
func floatSyntax(doc map[string]any) []string {
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
		if _, err := n.Int64(); err != nil {
			// syntax guard: integer syntax beyond int64 is the typed
			// domain's rejection; float syntax is the literal gate's
			if strings.ContainsAny(n.String(), ".eE") {
				errs = append(errs, fmt.Sprintf("[LEDGER.SEQ_FLOAT_SYNTAX] events/%d: arbitration_seq %s is not an integer literal — the counter domain is machine-written int64; this package does no float math (user ruling 2026-11-02)", i, n.String()))
			} else {
				errs = append(errs, fmt.Sprintf("[LEDGER.SEQ_INT64_OVERFLOW] events/%d: arbitration_seq %s exceeds the int64 domain — the machine's counter domain; such a document is not machine-writable", i, n.String()))
			}
		}
	}
	return errs
}

// accountabilityEqual compares the optional triples by value.
func accountabilityEqual(a, b *Accountability) bool {
	if a == nil || b == nil {
		return a == b
	}
	return *a == *b
}

// notATransition formats the illegal-transition error.
func notATransition(i int, op, status, from string) string {
	if from == "" {
		from = "nothing"
	}
	return fmt.Sprintf("[LEDGER.ILLEGAL_TRANSITION] events/%d: operation %q: status %q after %q is not a legal state-machine transition — a bypass write into the ledger, not a machine transition", i, op, status, from)
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
// machine's own transition DAG in file order; idempotency rides every
// event except conflict (and a conflict carrying it is rejected — the
// loser's digest never enters the registry); and every effect event
// carries the adopted pin's attribution triple. Aggregation contract: the
// code-rule families aggregate in the same order on both sides; both
// checkers short-circuit at the schema, and this checker additionally
// short-circuits at the float-syntax and typed-view-parse points where the
// Python oracle appends and continues — so error-set composition may
// differ on documents violating those two, and invalid fixtures are
// single-violation by discipline (the one designed exception:
// effect-before-adoption is one bypass fact that legitimately trips both
// the grammar and the transition table, identically on both sides). The
// verdict never differs. The map input must be decoded with
// json.Decoder.UseNumber (R16 数值域章程): the integer-literal gate keys
// off json.Number — on a plain float64 map every number arrives as
// float64 and the literal check is undecidable (0.0 is indistinguishable
// from 0). One input discipline (the suite loader and the adopt machine's
// line decoder both keep it; future callers — the replay reader — must
// too).
func Errors(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	// integer-literal domain (R16, user ruling): float-syntax seqs are
	// rejected by rule BEFORE anything else — no normalization layer, no
	// copy mutation contract (CheckDoc no longer rewrites the caller's
	// document; the copyDoc above is retired with the normalization).
	if errs := floatSyntax(doc); len(errs) > 0 {
		return errs
	}
	// cross-event rules on the typed view
	var d Document
	raw, err := json.Marshal(doc)
	if err != nil {
		return []string{"ledger: internal re-marshal failed: " + err.Error()}
	}
	if err := json.Unmarshal(raw, &d); err != nil {
		return []string{"[LEDGER.SEQ_INT64_OVERFLOW] ledger: document does not fit the typed ledger view (an integer field beyond the int64 domain, or a type mismatch — the machine never writes such values): " + err.Error()}
	}
	var errs []string
	// sequence ORDER is checked, density is not: the machine writes
	// gap-free consecutive seqs, but a gap forges no order (the arbitration
	// order is the ordering relation, not the density) and crosses no state
	// — no falsifiable surface, so no rule (deliberate, not an omission).
	prevSeq := int64(-1)
	for i, e := range d.Events {
		if e.ArbitrationSeq <= prevSeq {
			errs = append(errs, fmt.Sprintf("[LEDGER.SEQ_NOT_INCREASING] events/%d: arbitration_seq %d breaks the strictly-increasing order — the machine never repeats or rewinds an arbitration sequence", i, e.ArbitrationSeq))
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
			errs = append(errs, fmt.Sprintf("[LEDGER.DIGEST_CHANGED_UNDER_KEY] events/%d: operation_id %q carries payload_digest %q but an earlier event recorded %q — changed payload under the same key", i, op, dig, prev))
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
			errs = append(errs, fmt.Sprintf("[LEDGER.STATUS_FAMILY] events/%d: %s event carries the %s-family status %q — the status vocabulary never crosses the event-type boundary", i, e.EventType, family, e.Outcome.Status))
		}
		if e.EventType == "effect" || e.Outcome.Status != "adopted" {
			if len(e.GrantsAtDecision) > 0 {
				errs = append(errs, fmt.Sprintf("[LEDGER.GRANTS_ON_NON_ADOPTED] events/%d: %s event (status %q) for operation %q carries grants_at_decision — the grant pin rides the adopted event only (stamped once, at the decision point)", i, e.EventType, e.Outcome.Status, e.Identity.OperationID))
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
	// idempotency presence, bidirectional: the machine writes idempotency on
	// EVERY event except conflict (the loser's digest never enters the
	// registry) — an adopted/reused/effect event without it is a bypass
	// write, and absorbing one forks the replay state away from the durable
	// form: the loader skips nil-idempotency events entirely, so the machine
	// resumes from a state the file contradicts and its next write bricks
	// the ledger (R10 BLOCKER). The reverse holds too: a conflict event
	// CARRYING idempotency launders the loser's digest into the registry the
	// replay matcher reads — a bypass write (R12 M-1).
	for i, e := range d.Events {
		if e.EventType == "adoption" && e.Outcome.Status == "conflict" && e.Idempotency != nil {
			errs = append(errs, fmt.Sprintf("[LEDGER.CONFLICT_IDEM_FORBIDDEN] events/%d: conflict event carries idempotency — the loser's digest never enters the registry; carrying it is a bypass write, not a machine transition", i))
		}
		needsIdem := e.EventType == "effect" || e.Outcome.Status == "adopted" || e.Outcome.Status == "reused"
		if needsIdem && e.Idempotency == nil {
			errs = append(errs, fmt.Sprintf("[LEDGER.IDEM_REQUIRED] events/%d: %s event (status %q) must carry idempotency — the machine writes it on every non-conflict event; its absence is a bypass write, not a machine transition", i, e.EventType, e.Outcome.Status))
		}
	}
	// the key coupling: the machine writes idempotency.operation_id and
	// identity.operation_id EQUAL on every event that carries idempotency —
	// a mismatch registers a phantom operation the caller never created and
	// lets the machine write zero-identity events under it, bricking its own
	// ledger (R6 BLOCKER).
	for i, e := range d.Events {
		if e.Idempotency != nil && e.Idempotency.OperationID != e.Identity.OperationID {
			errs = append(errs, fmt.Sprintf("[LEDGER.IDEM_IDENTITY_MISMATCH] events/%d: idempotency.operation_id %q does not match identity.operation_id %q — the machine writes them equal; a mismatch is a bypass write, not a machine transition", i, e.Idempotency.OperationID, e.Identity.OperationID))
		}
	}
	// attribution consistency: the machine stamps the winner's
	// identity/versions/accountability pin on every effect event — an effect
	// event whose attribution diverges from the op's adopted event is a
	// bypass write; absorbing one forges the audit trail and pollutes the
	// piece-6 replay correlation keys (versions are its matching inputs).
	// Checked only where an adopted pin exists: an effect BEFORE its
	// adoption is already rejected by the grammar (the designed bypass
	// exception stays two-family).
	type pin struct {
		identity       Identity
		versions       Versions
		accountability *Accountability
	}
	pins := map[string]pin{}
	for i, e := range d.Events {
		op := e.Identity.OperationID
		if e.EventType == "adoption" && e.Outcome.Status == "adopted" {
			pins[op] = pin{identity: e.Identity, versions: e.Versions, accountability: e.Accountability}
		} else if e.EventType == "effect" {
			if p, has := pins[op]; has {
				if e.Identity != p.identity || e.Versions != p.versions ||
					!accountabilityEqual(e.Accountability, p.accountability) {
					errs = append(errs, fmt.Sprintf("[LEDGER.ATTRIBUTION_DIVERGENCE] events/%d: effect event's attribution (identity/versions/accountability) differs from the adopted pin for operation %q — the machine stamps the winner's pin on every effect event; a divergence is a bypass write, not a machine transition", i, op))
				}
			}
		}
	}
	adopted := map[string]bool{}
	for i, e := range d.Events {
		op := e.Identity.OperationID
		if e.EventType == "adoption" {
			if e.Outcome.Status == "adopted" {
				if adopted[op] {
					errs = append(errs, fmt.Sprintf("[LEDGER.DOUBLE_ADOPTED] events/%d: operation %q already has an adopted event — a second adopted event would re-pin the machine's state mid-flight (a bypass write, not a machine transition)", i, op))
				}
				adopted[op] = true
			} else if !adopted[op] {
				// reused/conflict before any adopted event for the operation
				errs = append(errs, fmt.Sprintf("[LEDGER.EVENT_BEFORE_ADOPTION] events/%d: %s event for operation %q precedes its adopted event — a bypass write into the ledger, not a machine transition", i, e.EventType, op))
			}
		} else if !adopted[op] {
			errs = append(errs, fmt.Sprintf("[LEDGER.EVENT_BEFORE_ADOPTION] events/%d: effect event for operation %q precedes its adopted event — a bypass write into the ledger, not a machine transition", i, op))
		}
	}
	return errs
}
