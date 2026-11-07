package compose

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
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

// TestBoundsKeyLockstep locks compose's bound-key tables to the schema
// (R5 F3 — the R4 M-1 drift family in another costume): summedBounds +
// timeBound vs schema bounds properties had no mechanical comparison, so a
// schema-side bound addition would be silently un-aggregated and unchecked.
func TestBoundsKeyLockstep(t *testing.T) {
	var raw []byte
	for _, root := range []string{"../..", "../../..", "../../../.."} {
		if b, err := os.ReadFile(filepath.Join(root, "schema", "capability-contract.schema.json")); err == nil {
			raw = b
			break
		}
	}
	if raw == nil {
		t.Fatal("capability-contract.schema.json not found from the package dir")
	}
	var doc struct {
		Properties struct {
			Bounds struct {
				Properties map[string]json.RawMessage `json:"properties"`
			} `json:"bounds"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	want := map[string]bool{}
	for k := range doc.Properties.Bounds.Properties {
		want[k] = true
	}
	got := map[string]bool{}
	for _, k := range summedBounds {
		got[k] = true
	}
	got[timeBound] = true
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("bounds key lockstep broken:\ncompose tables %v\nschema properties %v", sortedKeys(got), sortedKeys(want))
	}
}

func sortedKeys(m map[string]bool) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	return ks
}
