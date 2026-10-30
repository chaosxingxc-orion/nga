// Request-document checking against adoption.schema.json (the fixture-suite
// entry point shared with schema/adoption.py, the Python oracle). The machine
// itself is a state-rule enforcer, not a schema engine — documents are
// validated before they reach it. Schema compilation and fixture loading are
// the growth layer's shared machinery (internal/schemalib, internal/suite).
package adopt

import (
	"festival-dev/go/internal/schemalib"
)

// SchemaPath is where adoption.schema.json was found ("" = not found).
var SchemaPath = schemalib.FindSchema("adoption.schema.json")

// schema is the fail-closed compile-once handle for the adoption schema.
var schema = schemalib.NewLazy(
	"https://agent-festival.local/schema/adoption/0.1.0", SchemaPath)

// CheckRequest validates a request document against adoption.schema.json.
// There are no cross-request rules: a request is a standalone document; the
// state rules that need machine memory (single winner, digest stability per
// key) live in the machine, not the schema.
func CheckRequest(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	return nil
}
