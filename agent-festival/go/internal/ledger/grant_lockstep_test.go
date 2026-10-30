package ledger

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestGrantShapeLockstep is the Go twin of ledger.py's check_grant_lockstep
// (R5 m-4): the grant shape exists as two self-contained schema copies
// (frozen-engine stake C5-a), and 'stay in lockstep' is only real if BOTH
// validators' sides compare them. Descriptions are stripped — the comparison
// is contract semantics, not prose.
func TestGrantShapeLockstep(t *testing.T) {
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
	grant, _ := defs["grant"].(map[string]any)
	props, _ := adoptionSchema["properties"].(map[string]any)
	grantsAt, _ := props["grants_at_decision"].(map[string]any)
	items, _ := grantsAt["items"].(map[string]any)
	if grant == nil || items == nil {
		t.Fatalf("grant subtrees not found: ledger=%v adoption=%v", grant != nil, items != nil)
	}
	if !equalSansDescription(stripDescription(grant), stripDescription(items)) {
		t.Fatal("grant shape lockstep broken: event-ledger $defs.grant != adoption grants_at_decision items")
	}
}

func stripDescription(node map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range node {
		if k == "description" {
			continue
		}
		out[k] = v
	}
	return out
}

func equalSansDescription(a, b map[string]any) bool {
	ab, err := json.Marshal(a)
	if err != nil {
		return false
	}
	bb, err := json.Marshal(b)
	if err != nil {
		return false
	}
	return string(ab) == string(bb)
}
