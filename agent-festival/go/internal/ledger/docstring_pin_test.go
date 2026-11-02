package ledger

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestDocstringFamilyEnumerationPinned guards the source-of-truth
// docstrings (ledger.go's Errors doc and ledger.py's module doc — two
// hand-synced prose copies) against silent drift (R14 m-1): the R12
// "docstring is the count's source of truth" ruling had no pin on the
// source itself, only on the consumer README.
func TestDocstringFamilyEnumerationPinned(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("event-ledger schema not found")
	}
	dir := filepath.Dir(SchemaPath)
	goSrc, err := os.ReadFile(filepath.Join(filepath.Dir(SchemaPath), "..", "go", "internal", "ledger", "ledger.go"))
	if err != nil {
		t.Fatal(err)
	}
	pySrc, err := os.ReadFile(filepath.Join(dir, "ledger.py"))
	if err != nil {
		t.Fatal(err)
	}
	// per-file phrase lists: the two docstrings are hand-synced prose, not
	// literal copies — each is pinned to its own actual wording, covering
	// all nine families (R15 m-1: the first version covered 3/8; R19 split transition DAG out as its own)
	goPhrases := []string{
		"strictly increasing",                 // seq family
		"one payload digest per operation",    // digest stability
		"never enters the registry",           // idempotency presence, bidirectional
		"idempotency.operation_id equals",     // key coupling
		"never cross the event-type boundary", // status families
		"rides the adopted event only",        // grant pin placement
		"attribution triple",                  // effect attribution
		"exactly one adopted adoption event",  // single-writer grammar
	}
	pyPhrases := []string{
		"strictly increasing",                // seq family
		"one payload digest",                 // digest stability
		"never enters the registry",          // idempotency presence, bidirectional
		"idem-identity key",                  // key coupling
		"crossing the event-type boundary",   // status families
		"grant pin riding the adopted event", // grant pin placement
		"attribution triple",                 // effect attribution
		"one adopted event",                  // grammar (the docstring wraps the line)
	}
	for _, phrase := range goPhrases {
		if !strings.Contains(string(goSrc), phrase) {
			t.Fatalf("ledger.go docstring lost the phrase %q", phrase)
		}
	}
	for _, phrase := range pyPhrases {
		if !strings.Contains(string(pySrc), phrase) {
			t.Fatalf("ledger.py docstring lost the phrase %q", phrase)
		}
	}
}
