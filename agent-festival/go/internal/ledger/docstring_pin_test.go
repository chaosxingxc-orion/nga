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
	phrases := []string{
		"never enters the registry", // conflict-禁带 bidirectional clause
		"attribution triple",        // effect attribution family
		"strictly increasing",       // seq family
	}
	for _, phrase := range phrases {
		if !strings.Contains(string(goSrc), phrase) {
			t.Fatalf("ledger.go docstring lost the phrase %q", phrase)
		}
		if !strings.Contains(string(pySrc), phrase) {
			t.Fatalf("ledger.py docstring lost the phrase %q", phrase)
		}
	}
}
