package compose

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/validate"
)

// TestGraphRegistrationRetryAfterFailure pins the retryable-registration
// semantics (V26 F-5 / V27 m-1). Sequenced INSIDE one test function with the
// failure-first wiring check: separate tests were shuffle-fragile (the
// wiring check false-REDs when it runs after the retry has made graphDone
// stick — V28 N-1a).
func TestGraphRegistrationRetryAfterFailure(t *testing.T) {
	// wiring first: with the library unavailable, ComposeErrors must fail closed
	if err := validate.RegisterGraphSchema(nil); err == nil {
		t.Fatal("nil schema registration should fail")
	}
	res := ComposeErrors(map[string]any{
		"nodes": map[string]any{},
		"plan":  "x",
	})
	found := false
	for _, e := range res.Errors {
		if strings.Contains(e, "schema library unavailable") {
			found = true
		}
	}
	if !found {
		t.Fatalf("fail-closed wiring did not fire while unregistered: %v", res.Errors)
	}
	// then the recovery: a later real registration must un-poison the process
	RegisterGraph()
	res = ComposeErrors(map[string]any{
		"nodes": map[string]any{},
		"plan":  "x",
	})
	for _, e := range res.Errors {
		if strings.Contains(e, "schema library unavailable") {
			t.Fatalf("graph library still poisoned after successful retry: %v", res.Errors)
		}
	}
}
