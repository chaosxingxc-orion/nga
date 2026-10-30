package ledger

import (
	"encoding/json"
	"os"
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
