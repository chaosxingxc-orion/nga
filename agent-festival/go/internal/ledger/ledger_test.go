package ledger

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// TestStatusVocabularyLockstep pins R3 m-2: the status vocabulary exists as
// several copies (schema enum, these family sets, the Python sets, the
// machine's State constants); this check makes the schema enum the enforced
// single source on the Go side — the Python twin lives in ledger.py's
// check_status_lockstep.
func TestStatusVocabularyLockstep(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("event-ledger schema not found")
	}
	raw, err := os.ReadFile(SchemaPath)
	if err != nil {
		t.Fatal(err)
	}
	var schema struct {
		Defs struct {
			Event struct {
				Properties struct {
					Outcome struct {
						Properties struct {
							Status struct {
								Enum []string `json:"enum"`
							} `json:"status"`
						} `json:"properties"`
					} `json:"outcome"`
				} `json:"properties"`
			} `json:"event"`
		} `json:"$defs"`
	}
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	got := map[string]bool{}
	for _, v := range schema.Defs.Event.Properties.Outcome.Properties.Status.Enum {
		got[v] = true
	}
	want := map[string]bool{}
	for v := range AdoptStatuses {
		want[v] = true
	}
	for v := range EffectStatuses {
		want[v] = true
	}
	if len(got) != len(want) {
		t.Fatalf("status lockstep broken: schema enum %v != checker families %v", got, want)
	}
	for v := range want {
		if !got[v] {
			t.Fatalf("status lockstep broken: %q missing from the schema enum", v)
		}
	}
}

// TestErrorsDoesNotMutateInput pins the R6 m-8 deep copy: a validator must
// not rewrite its caller's document — the normalization would otherwise
// turn the caller's json.Number nodes into int64s under it (R7: the fix
// existed but no test could see it being removed).
func TestErrorsDoesNotMutateInput(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("event-ledger schema not found")
	}
	doc := map[string]any{
		"ledger_version": "0.1.0",
		"events": []any{
			map[string]any{
				"event_type": "adoption", "arbitration_seq": json.Number("0"),
				"identity":           map[string]any{"business_request_id": "br-m", "operation_id": "op-m"},
				"versions":           map[string]any{"evidence": "e", "rule": "r", "model": "m", "readout": "ro", "policy": "p"},
				"grants_at_decision": []any{map[string]any{"kind": "data", "selector": "s", "actions": []any{"read"}, "effect": "none"}},
				"outcome":            map[string]any{"status": "adopted"},
				"idempotency":        map[string]any{"operation_id": "op-m", "payload_digest": "sha256:" + strings.Repeat("a", 64)},
			},
			map[string]any{
				"event_type": "effect", "arbitration_seq": json.Number("1"),
				"identity":    map[string]any{"business_request_id": "br-m", "operation_id": "op-m"},
				"versions":    map[string]any{"evidence": "e", "rule": "r", "model": "m", "readout": "ro", "policy": "p"},
				"outcome":     map[string]any{"status": "dispatched"},
				"idempotency": map[string]any{"operation_id": "op-m", "payload_digest": "sha256:" + strings.Repeat("a", 64)},
			},
		},
	}
	before, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	if errs := Errors(doc); len(errs) > 0 {
		t.Fatalf("clean doc rejected: %v", errs)
	}
	after, err := json.Marshal(doc)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatalf("Errors mutated its input:\nbefore %s\nafter  %s", before, after)
	}
}
