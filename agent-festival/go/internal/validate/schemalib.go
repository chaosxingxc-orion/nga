package validate

import (
	"fmt"
	"sync"

	"github.com/dlclark/regexp2"
	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

// EQUALITY-SEMANTICS LEDGER (V19 m2, same family as FORMAT LEDGER — blind
// spots where BOTH Go engines agree and the disagreement alarm cannot see):
// python-jsonschema equates bool and int (True == 1) in uniqueItems / enum /
// const; the hand engine compares marshaled text ("true" vs "1" differ) and
// santhosh follows — so [true, 1] is non-unique for the oracle and unique
// here. Unreachable today (all enum/uniqueItems faces are string enums); a
// schema change that adds a numeric/boolean enum must pin both sides first.
// Family member three (V26 4-lens n2): jsonEqual marshals NaN with the error
// swallowed (nil==nil => "equal") where Python's == is False — same
// unreachability (no numeric enum), same rule.

// FORMAT LEDGER (V8 F-2, replaces the false "format never enforced" claim):
// the live oracle's FormatChecker DOES enforce the nine stdlib formats
// (date email idn-email idn-hostname ipv4 ipv6 regex time uuid); the one
// format our schemas use — "uri" — is unenforced ONLY because its checker
// (jsonschema 4.26 loads a uri checker from EITHER rfc3987 OR the fallback
// rfc3986_validator — BOTH must stay out of the pinned dependency set) is
// absent from the pinned dependency set. A 0.2.0 schema that
// uses ANY stdlib format flips the oracle to enforcing while both Go engines
// never enforce format — a divergence the two-engine alarm is structurally
// blind to (both engines agree). Rule: no new "format" keyword may enter a
// schema without first pinning its expected behavior in fixtures on both
// sides, or explicitly negotiating formats=() with the oracle (frozen —
// needs a user ruling).

// ---------- library cross-check: the judgment authority ----------
//
// 不重复造轮子立法（2026-10-28）: JSON Schema semantics are decided by the
// industry library (santhosh-tekuri/jsonschema, full draft 2020-12, with the
// dlclark/regexp2 engine so the selector pattern's lookaheads — legal in
// Python's re, illegal in Go's RE2 — behave as authored). The in-repo
// SchemaErrors keeps only the MESSAGE layer: fixtures pin the frozen oracle's
// exact Python-jsonschema phrasings, which no Go library reproduces. Verdicts
// are cross-checked on every validation — a disagreement is appended as an
// error, so the pair fails closed and can never silently drift apart again
// (V2's M1/maxProperties gap was exactly this class).

type dlclarkRegexp regexp2.Regexp

func (re *dlclarkRegexp) MatchString(s string) bool {
	matched, err := (*regexp2.Regexp)(re).MatchString(s)
	return err == nil && matched
}

func (re *dlclarkRegexp) String() string { return (*regexp2.Regexp)(re).String() }

func dlclarkCompile(s string) (jsonschema.Regexp, error) {
	// .NET default mode, not ECMAScript: its '$' matches before a single trailing
	// newline exactly like Python's re (V3 MAJOR-1) — the frozen oracle's
	// semantics are the parity target, and ECMA's strict '$' would silently
	// reject documents Python accepts.
	re, err := regexp2.Compile(s, regexp2.None)
	if err != nil {
		return nil, err
	}
	return (*dlclarkRegexp)(re), nil
}

var (
	libOnce     sync.Once
	graphMu     sync.Mutex
	graphDone   bool
	libContract *jsonschema.Schema
	libEnvelope *jsonschema.Schema
	libGraph    *jsonschema.Schema
	libGraphErr error
	libSetupErr error
	graphReady  bool
)

func compileLibraries() {
	libOnce.Do(func() {
		c := jsonschema.NewCompiler()
		c.UseRegexpEngine(dlclarkCompile)
		var err error
		if libContract, err = addAndCompile(c, ContractSchema); err != nil {
			libSetupErr = err
			return
		}
		libEnvelope, err = addAndCompile(c, EnvelopeSchema)
		if err != nil {
			libSetupErr = err
		}
	})
}

func addAndCompile(c *jsonschema.Compiler, s Schema) (*jsonschema.Schema, error) {
	if s == nil {
		return nil, fmt.Errorf("schema document not loaded from disk")
	}
	id, _ := s["$id"].(string)
	if id == "" {
		return nil, fmt.Errorf("schema document has no $id")
	}
	// the library type-switches on the unnamed map type; Schema is a named
	// map type and would be rejected as "invalid jsonType validate.Schema"
	if err := c.AddResource(id, map[string]any(s)); err != nil {
		return nil, err
	}
	return c.Compile(id)
}

// RegisterGraphSchema hands the execution-graph schema (loaded by the compose
// package) to the library and compiles it. Cross-schema refs into the contract
// schema resolve because that resource is registered first.
func RegisterGraphSchema(s Schema) error {
	compileLibraries()
	if libSetupErr != nil {
		return libSetupErr
	}
	graphMu.Lock()
	defer graphMu.Unlock()
	if graphDone {
		return libGraphErr
	}
	// a FAILED registration stays retryable — a sync.Once here let the wiring
	// test's nil registration poison the process for every later test (V26
	// singularity F-5); success is what makes it stick
	libGraphErr = registerGraphLocked(s)
	if libGraphErr == nil {
		graphDone = true
	}
	return libGraphErr
}

func registerGraphLocked(s Schema) error {
	c := jsonschema.NewCompiler()
	c.UseRegexpEngine(dlclarkCompile)
	var err error
	if libContract, err = addAndCompile(c, ContractSchema); err != nil {
		return err // the caller assigns libGraphErr once (single source, V31 n2)
	}
	libGraph, err = addAndCompile(c, s)
	if err != nil {
		return err
	}
	graphReady = true
	return nil
}

// verdictChecked appends a fail-closed alarm when the library's accept/reject
// verdict disagrees with the message engine's. handErrs are the rendered
// (pinned) messages and carry the verdict of the message engine.
func verdictChecked(doc any, compiled *jsonschema.Schema, handErrs []string, what string) []string {
	if compiled == nil {
		detail := "not compiled"
		if libSetupErr != nil {
			detail = libSetupErr.Error()
		} else if libGraphErr != nil {
			detail = libGraphErr.Error()
		}
		return append(handErrs, fmt.Sprintf("%s: schema library unavailable: %s (fail closed)", what, detail))
	}
	libRejected := compiled.Validate(doc) != nil
	handRejected := len(handErrs) > 0
	if libRejected != handRejected {
		return append(handErrs, fmt.Sprintf("%s: schema engine disagreement — library says %s, message engine says %s (fail closed)",
			what, verdictWord(libRejected), verdictWord(handRejected)))
	}
	return handErrs
}

func verdictWord(rejected bool) string {
	if rejected {
		return "reject"
	}
	return "accept"
}

// CheckContractVerdict cross-checks a contract document against the library.
func CheckContractVerdict(doc any, handErrs []string) []string {
	compileLibraries()
	return verdictChecked(doc, libContract, handErrs, "contract")
}

// CheckEnvelopeVerdict cross-checks an envelope document against the library.
func CheckEnvelopeVerdict(doc any, handErrs []string) []string {
	compileLibraries()
	return verdictChecked(doc, libEnvelope, handErrs, "envelope")
}

// CheckGraphVerdict cross-checks an execution-graph document against the library.
func CheckGraphVerdict(doc any, handErrs []string) []string {
	compileLibraries()
	if !graphReady {
		return append(handErrs, "graph: schema library unavailable (fail closed)")
	}
	return verdictChecked(doc, libGraph, handErrs, "graph")
}
