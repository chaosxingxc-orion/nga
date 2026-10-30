// Request-document checking against adoption.schema.json (the fixture-suite
// entry point shared by cmd/adopt and mirroring schema/adoption.py, the
// Python oracle). The machine itself is a state-rule enforcer, not a schema
// engine — documents are validated before they reach it.
package adopt

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

// SchemaPath is where adoption.schema.json lives (set by init from the same
// CWD probe the ledger package uses).
var SchemaPath string

func init() {
	for _, root := range []string{"../../schema", "../../../schema", "../schema", "."} {
		p := filepath.Join(root, "adoption.schema.json")
		if _, err := os.Stat(p); err == nil {
			SchemaPath = p
			return
		}
	}
}

// Fixture is a request fixture with its _expect* pins popped (same
// discipline as the base and the ledger package).
type Fixture struct {
	Doc         map[string]any
	ExpectMatch string
	ParseError  string
}

// LoadFixture reads a request fixture and pops its pins.
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

// compiled holds the fail-closed schema (nil until first use; the adoption
// schema has no cross-schema $refs so a local compile is enough).
var compiled *jsonschema.Schema
var compileErr error

func ensureCompiled() error {
	if compiled != nil || compileErr != nil {
		return compileErr
	}
	if SchemaPath == "" {
		compileErr = fmt.Errorf("adoption schema not found")
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
	c.UseRegexpEngine(nil)
	if err := c.AddResource("https://agent-festival.local/schema/adoption/0.1.0", doc); err != nil {
		compileErr = err
		return err
	}
	compiled, compileErr = c.Compile("https://agent-festival.local/schema/adoption/0.1.0")
	return compileErr
}

// CheckRequest validates a request document against adoption.schema.json.
// There are no cross-request rules: a request is a standalone document; the
// state rules that need machine memory (single winner, digest stability per
// key) live in the machine, not the schema.
func CheckRequest(doc map[string]any) []string {
	if err := ensureCompiled(); err != nil {
		return []string{"adoption: schema unavailable: " + err.Error() + " (fail closed)"}
	}
	if err := compiled.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	return nil
}
