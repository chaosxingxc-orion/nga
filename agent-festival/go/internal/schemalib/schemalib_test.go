package schemalib

import (
	"strings"
	"testing"
)

// TestRegexpEngineMatchesPythonTrailingNewline pins the engine choice (R1
// M-6, the base's V3 MAJOR-1 legislation): '$' must match before a single
// trailing newline, like Python's re — Go's default RE2 rejects that shape,
// which forked the dual validators on the digest pattern.
func TestRegexpEngineMatchesPythonTrailingNewline(t *testing.T) {
	s, err := Compile("https://t/pattern", map[string]any{
		"$schema":  "https://json-schema.org/draft/2020-12/schema",
		"type":     "object",
		"required": []any{"digest"},
		"properties": map[string]any{
			"digest": map[string]any{"type": "string", "pattern": "^sha256:[0-9a-f]+$"},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Validate(map[string]any{"digest": "sha256:abc"}); err != nil {
		t.Fatalf("plain digest rejected: %v", err)
	}
	if err := s.Validate(map[string]any{"digest": "sha256:abc\n"}); err != nil {
		t.Fatalf("trailing-newline digest rejected — engine is not Python-parity: %v", err)
	}
	if err := s.Validate(map[string]any{"digest": "sha256:abc\n\n"}); err == nil {
		t.Fatal("two trailing newlines accepted — $ must not be a free wildcard")
	}
}

// TestLazyCompileOnceFailClosed pins the lazy handle: same result across
// calls, and a missing file fails closed forever (never a pass).
func TestLazyCompileOnceFailClosed(t *testing.T) {
	l := NewLazy("https://t/missing", "/no/such/schema.json")
	if _, err := l.Get(); err == nil {
		t.Fatal("missing schema compiled?")
	}
	if _, err := l.Get(); err == nil {
		t.Fatal("missing schema compiled on second call?")
	}
	if err := l.Validate(map[string]any{}); err == nil {
		t.Fatal("validation passed without a schema — not fail-closed")
	}
}

// TestFindSchemaLocatesGrowthLayerSchemas pins the CWD probe against the
// real schema directory.
func TestFindSchemaLocatesGrowthLayerSchemas(t *testing.T) {
	p := FindSchema("adoption.schema.json")
	if p == "" || !strings.HasSuffix(p, "schema/adoption.schema.json") {
		t.Fatalf("adoption schema not found from test CWD: %q", p)
	}
	if FindSchema("no-such-schema.json") != "" {
		t.Fatal("probe invented a path for a missing schema")
	}
}
