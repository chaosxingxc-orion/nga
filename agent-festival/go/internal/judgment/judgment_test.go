package judgment

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// TestSchemaVersionLockstep pins the version copies against drift (R1 m-4):
// three direct assertions — the schema file's $id, its judgment_version
// const, and the Go compile id (read from this package's source) — with the
// fixtures' version carried only by transmission through the const. A bump
// that misses one of the three goes unnoticed by the fixtures alone.
func TestSchemaVersionLockstep(t *testing.T) {
	if SchemaPath == "" {
		t.Fatal("judgment schema not found")
	}
	raw, err := os.ReadFile(SchemaPath)
	if err != nil {
		t.Fatal(err)
	}
	var doc struct {
		ID         string `json:"$id"`
		Properties struct {
			Version struct {
				Const string `json:"const"`
			} `json:"judgment_version"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	const wantVersion = "0.1.0"
	const wantID = "https://agent-festival.local/schema/judgment/" + wantVersion
	if doc.ID != wantID {
		t.Fatalf("schema $id = %q, want %q", doc.ID, wantID)
	}
	if doc.Properties.Version.Const != wantVersion {
		t.Fatalf("judgment_version const = %q, want %q", doc.Properties.Version.Const, wantVersion)
	}
	// the compile id lives in this package's source — pin it by phrase
	src, err := os.ReadFile("check.go")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(src), `"`+wantID+`"`) {
		t.Fatalf("check.go compile id does not carry %q — the version forked", wantID)
	}
}
