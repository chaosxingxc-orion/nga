package rfc8785

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"testing"
)

// TestDifferential proves the reference implementation (engine of record) and
// the in-repo ES6 serializer agree byte for byte — over every fixture in the
// frozen example suites and an adversarial corpus: IEEE extremes, ES6 notation
// thresholds (1e21 / 1e-6 / 1e-7), 2^53 neighborhood, subnormals, and UTF-16
// key ordering (BMP vs astral pairs). Two independent implementations agreeing
// is the standing defense against a silent divergence in either.
func TestDifferential(t *testing.T) {
	corpus := []any{
		float64(0), math.Copysign(0, -1), 1.0, -1.0, 600.0, 1e15, 1e16, 1e20, 1e21, 1e22,
		0.000001, 0.0000001, 5e-324, 2.2250738585072014e-308,
		9007199254740991.0, 9007199254740992.0, 9007199254740993.0, -9007199254740991.0,
		1.7976931348623157e308, -1.7976931348623157e308, 123456789.123456789,
		0.1, 0.2, 0.3, 3.0, 2.5, 1e-6, 9.999999999999999e20,
	}
	docs := []any{
		map[string]any{"a": corpus},
		corpus,
		map[string]any{"": "empty key", "\u0001": "control", "\u0080": "first BMP", "\uffff": "last BMP", "\U0001F600": "astral", "e": "z"},
		[]any{"<html>&\"'", "\u2028\u2029", "tab\there", "back\\slash", "\u0000"},
		// the literal six-character TEXT "\u2028" must survive the unescape
		// post-processing untouched (V4 F-1) while the real characters become raw
		// UTF-8 — one doc exercising both sides at once, through BOTH engines
		map[string]any{"lit": `text \u2028 and \u2029 verbatim`, "raw": "real \u2028 and \u2029 here"},
		map[string]any{"nested": map[string]any{"deep": []any{true, false, nil, ""}}},
	}
	for i, doc := range docs {
		assertEqualBytes(t, doc, fmt.Sprintf("corpus[%d]", i))
	}
	for _, v := range corpus {
		// values ride inside an object wrapper: only top-level SCALARS fall back
		// to the local serializer — the reference Transform accepts arrays too
		assertEqualBytes(t, map[string]any{"v": v}, fmt.Sprintf("wrapped value %v", v))
	}

	// every fixture document in the frozen suites, with a count floor: a
	// silently-empty walk must fail the test, not pass it (V4 F-4, the Go-side
	// counterpart of the XM2 静默空批防线 legislation)
	compared := 0
	roots := []string{"../../../schema/examples", "../../../../schema/examples"}
	for _, root := range roots {
		if _, err := os.Stat(root); err != nil {
			continue
		}
		_ = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() || filepath.Ext(path) != ".json" {
				return nil
			}
			raw, err := os.ReadFile(path)
			if err != nil {
				t.Fatalf("read %s: %v", path, err)
			}
			var doc any
			if err := json.Unmarshal(raw, &doc); err != nil {
				return nil // pins-only rejections and surrogate fixtures may not parse leniently here
			}
			assertEqualBytes(t, doc, path)
			compared++
			return nil
		})
		break // first existing root wins; both roots point at the same corpus in dev layouts
	}
	if compared < 80 {
		t.Fatalf("differential walk compared only %d fixture documents (want >= 80): corpus root missing?", compared)
	}
	// NaN / Inf are not JSON: both implementations must refuse. The reference
	// path only receives objects/arrays, so the value is wrapped — a bare
	// scalar would silently exercise only the local serializer.
	for _, v := range []float64{math.NaN(), math.Inf(1), math.Inf(-1)} {
		if _, err := canonicalizeLocal(v); err == nil {
			t.Errorf("local impl accepted non-finite %v", v)
		}
		if _, err := Canonicalize(map[string]any{"v": v}); err == nil {
			t.Errorf("reference path accepted non-finite %v", v)
		}
	}
}

func assertEqualBytes(t *testing.T, doc any, label string) {
	t.Helper()
	ref, err1 := Canonicalize(doc)
	loc, err2 := canonicalizeLocal(doc)
	if err1 != nil || err2 != nil {
		if err1 == nil || err2 == nil {
			t.Fatalf("%s: error divergence ref=%v local=%v", label, err1, err2)
		}
		return
	}
	if string(ref) != string(loc) {
		t.Fatalf("%s: byte divergence\n reference: %s\n local:      %s", label, ref, loc)
	}
}
