// Document checking against release.schema.json (piece 5, the Go side of
// the oracle). Piece 5 is a standalone schema: no cross-document rules —
// the linking chain's other links (task recording, promotion, replay)
// belong to their consumers; piece 6 reads manifests, never writes. Schema
// compilation rides the growth layer's shared machinery.
package release

import (
	"festival-dev/go/internal/schemalib"
)

// SchemaPath is where release.schema.json was found ("" = not found).
var SchemaPath = schemalib.FindSchema("release.schema.json")

// schema is the fail-closed compile-once handle for the release schema.
var schema = schemalib.NewLazy(
	"https://agent-festival.local/schema/release/0.1.0", SchemaPath)

// CheckManifest validates a release manifest document against
// release.schema.json. Every field traces to NGA v0.2 §5 — the checker
// adds nothing the schema does not say.
func CheckManifest(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	return nil
}
