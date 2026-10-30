package ledger

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestSharedSubtreeLockstep is the Go twin of ledger.py's check_lockstep
// (R6 M-2): four subtrees exist as two self-contained schema copies each
// (frozen-engine stake C5-a) — grant, identity, versions, accountability —
// and 'stay in lockstep' is only real if BOTH validators' sides compare
// them. Descriptions are stripped recursively — the comparison is contract
// semantics, not prose.
func TestSharedSubtreeLockstep(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("event-ledger schema not found")
	}
	ledgerDoc, err := os.ReadFile(SchemaPath)
	if err != nil {
		t.Fatal(err)
	}
	adoptionPath := filepath.Join(filepath.Dir(SchemaPath), "adoption.schema.json")
	adoptionDoc, err := os.ReadFile(adoptionPath)
	if err != nil {
		t.Fatal(err)
	}
	var ledgerSchema, adoptionSchema map[string]any
	if err := json.Unmarshal(ledgerDoc, &ledgerSchema); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(adoptionDoc, &adoptionSchema); err != nil {
		t.Fatal(err)
	}
	defs, _ := ledgerSchema["$defs"].(map[string]any)
	eventDef, _ := defs["event"].(map[string]any)
	eventProps, _ := eventDef["properties"].(map[string]any)
	ledgerProps, _ := adoptionSchema["properties"].(map[string]any)
	grantsAt, _ := ledgerProps["grants_at_decision"].(map[string]any)
	pairs := []struct {
		name   string
		ledger map[string]any
		adopt  map[string]any
	}{
		{"grant", defs["grant"].(map[string]any), grantsAt["items"].(map[string]any)},
		{"identity", defs["identity"].(map[string]any), ledgerProps["identity"].(map[string]any)},
		{"versions", defs["versions"].(map[string]any), ledgerProps["versions"].(map[string]any)},
		{"accountability", eventProps["accountability"].(map[string]any), ledgerProps["accountability"].(map[string]any)},
	}
	for _, pair := range pairs {
		a, err := json.Marshal(stripDescription(pair.ledger))
		if err != nil {
			t.Fatal(err)
		}
		b, err := json.Marshal(stripDescription(pair.adopt))
		if err != nil {
			t.Fatal(err)
		}
		if string(a) != string(b) {
			t.Fatalf("%s shape lockstep broken: event-ledger copy != adoption copy\n%s\n%s", pair.name, a, b)
		}
	}
}

// stripDescription recursively drops description keys — prose is not contract.
func stripDescription(node any) any {
	switch v := node.(type) {
	case map[string]any:
		out := map[string]any{}
		for k, child := range v {
			if k == "description" {
				continue
			}
			out[k] = stripDescription(child)
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, child := range v {
			out[i] = stripDescription(child)
		}
		return out
	default:
		return v
	}
}
