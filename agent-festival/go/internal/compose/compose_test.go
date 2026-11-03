package compose

import (
	"testing"
)

// TestAnyToInt64Saturates pins the conversion discipline (V26 F-4 / V27 F-1):
// out-of-range floats saturate instead of the implementation-defined bare
// int64() conversion (arm64 saturates, amd64 wraps negative — the verdict
// would be architecture-dependent without this).
// NOTE: the kill power of the saturation tests below is amd64-only — arm64
// hardware saturates float->int64 natively, so removing the explicit guards
// stays green on arm64. GOARCH=amd64 is the mandatory run form for these
// pins (V33 4-lens m-2; the loop's green gate runs both architectures).
func TestAnyToInt64Saturates(t *testing.T) {
	if got := anyToInt64(1e19); got != 9223372036854775807 {
		t.Fatalf("anyToInt64(1e19) = %d, want MaxInt64", got)
	}
	if got := anyToInt64(-1e19); got != -9223372036854775808 {
		t.Fatalf("anyToInt64(-1e19) = %d, want MinInt64", got)
	}
	if got := anyToInt64(5.0); got != 5 {
		t.Fatalf("anyToInt64(5.0) = %d, want 5", got)
	}
	if got := anyToInt64(int64(7)); got != 7 {
		t.Fatalf("anyToInt64(int64(7)) = %d, want 7", got)
	}
}

// TestBoundAmountSaturates pins the same discipline at boundAmount's float
// branch (V27 F-1: the discipline landed in anyToInt64 but this sibling
// site kept a bare conversion 210 lines away).
func TestBoundAmountSaturates(t *testing.T) {
	got, ok := boundAmount(map[string]any{"max_seconds": 1e19}, "max_seconds")
	if !ok || got != 9223372036854775807 {
		t.Fatalf("boundAmount(1e19) = %d (ok=%v), want MaxInt64", got, ok)
	}
}

// The V29 M-2 panic pins (V30 F-2, evidenced now): a non-map max_cost must
// panic loudly at all three sites — schema-gated for JSON, this is the
// programmatic-caller defense.
func TestMaxCostNonMapPanics(t *testing.T) {
	mustPanic := func(name string, body func()) {
		t.Helper()
		defer func() {
			if recover() == nil {
				t.Fatalf("%s: non-map max_cost did not panic", name)
			}
		}()
		body()
	}
	mustPanic("normalizeBounds", func() { normalizeBounds(map[string]any{"max_cost": 7.0}) })
	mustPanic("foldBounds", func() {
		nodes := map[string]map[string]any{
			"a": {"bounds": map[string]any{"max_cost": 7.0}},
			"b": {"bounds": map[string]any{"max_cost": map[string]any{"amount": int64(1), "unit": "u"}}},
		}
		_, _ = foldBounds(map[string]any{"seq": []any{"a", "b"}}, nodes)
	})
	mustPanic("splitBounds", func() {
		splitBounds(map[string]any{"max_cost": 7.0}, 2)
	})
}
