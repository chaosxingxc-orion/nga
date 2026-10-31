package ledger

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestReadmeFamilyEnumerationPinned guards the README's rule-family text
// against silent drift (R13 m-2): the R11 README fix once failed to land
// while the commit claimed it had. The count pin guards the corpus size;
// this guards the prose — the enumeration keywords that must survive any
// rewrite of the README rows.
func TestReadmeFamilyEnumerationPinned(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("event-ledger schema not found")
	}
	readmePath := filepath.Join(filepath.Dir(SchemaPath), "README.md")
	raw, err := os.ReadFile(readmePath)
	if err != nil {
		t.Fatal(err)
	}
	text := string(raw)
	for _, phrase := range []string{
		"跨事件规则八族",
		"conflict 禁带",
		"effect 归因=adopted 钉照",
		"查序不查密度",
		"idem↔identity 键耦合",
		"payload_digest 五共享原子",
	} {
		if !strings.Contains(text, phrase) {
			t.Fatalf("README lost the family-enumeration phrase %q — the prose drifted from the checker", phrase)
		}
	}
}
