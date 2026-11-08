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
		"跨事件规则九族",
		"seq 严格递增",             // family 1
		"同 op 单 digest",        // family 2
		"idempotency 在场性双向",    // family 3
		"conflict 禁带",          // family 3, reverse arm
		"idem↔identity 键耦合",    // family 4
		"status 家族不越界",         // family 5
		"钉照只骑 adopted",         // family 6
		"effect 归因=adopted 钉照", // family 7
		"转移序镜像机器 DAG",          // family 8 (R19: transition DAG — its own family/key/block)
		"恰一 adopted 开头",        // family 9
		"查序不查密度",               // explicit ruling
		"payload_digest 五共享原子", // lockstep surface
	} {
		if !strings.Contains(text, phrase) {
			t.Fatalf("README lost the family-enumeration phrase %q — the prose drifted from the checker", phrase)
		}
	}
}
