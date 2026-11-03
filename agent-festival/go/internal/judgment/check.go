// Request-document checking against judgment.schema.json (piece 3, the Go
// side of the oracle). Piece 3 is a standalone schema: no cross-document
// rules, no machine — semantic ownership belongs to the knowledge workflow
// that consumes it (the priors' boundary). Schema compilation rides the
// growth layer's shared machinery (internal/schemalib, internal/suite).
package judgment

import (
	"github.com/openjiuwen/agent-festival/go/internal/schemalib"
)

// SchemaPath is where judgment.schema.json was found ("" = not found).
var SchemaPath = schemalib.FindSchema("judgment.schema.json")

// schema is the fail-closed compile-once handle for the judgment schema.
var schema = schemalib.NewLazy(
	"https://agent-festival.local/schema/judgment/0.1.0", SchemaPath)

// CheckSpec validates a judgment specification document against
// judgment.schema.json. Every field traces to the schema's provenance
// anchors (current documents + the legacy overall-design §6/§6.1,
// superseded by the 2026-10-31 consolidation — see the schema description
// for the dual-anchor form). The checker adds nothing the schema does not
// say.
func CheckSpec(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	return nil
}
