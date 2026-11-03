package validate

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

// TestVerdictCheckedPinsThePillar locks the fail-closed disagreement alarm
// itself (V5 M-1): mutation showed the whole cross-check could be deleted with
// both suites still green, because the corpora currently contain zero
// disagreements — the alarm is a drift tripwire and only a constructed
// disagreement proves it fires. Both directions are pinned: library-rejects /
// engine-accepts, and library-accepts / engine-rejects.
func TestVerdictCheckedPinsThePillar(t *testing.T) {
	c := jsonschema.NewCompiler()
	const doc = `{"$id": "https://test.local/pillar", "type": "string"}`
	var schemaDoc any
	if err := json.Unmarshal([]byte(doc), &schemaDoc); err != nil {
		t.Fatal(err)
	}
	if err := c.AddResource("https://test.local/pillar", schemaDoc); err != nil {
		t.Fatal(err)
	}
	compiled, err := c.Compile("https://test.local/pillar")
	if err != nil {
		t.Fatal(err)
	}

	// library rejects (42 is not a string), message engine accepted
	out := verdictChecked(42, compiled, nil, "pillar")
	if len(out) != 1 || !strings.Contains(out[0], "schema engine disagreement") || !strings.Contains(out[0], "fail closed") {
		t.Fatalf("engine-accepts/library-rejects disagreement not raised: %v", out)
	}

	// library accepts, message engine rejected
	out = verdictChecked("s", compiled, []string{"phony"}, "pillar")
	if len(out) != 2 || !strings.Contains(out[1], "schema engine disagreement") {
		t.Fatalf("engine-rejects/library-accepts disagreement not raised: %v", out)
	}

	// agreement in both directions stays silent
	if out := verdictChecked("s", compiled, nil, "pillar"); len(out) != 0 {
		t.Fatalf("agreeing pair produced errors: %v", out)
	}
	if out := verdictChecked(42, compiled, []string{"phony"}, "pillar"); len(out) != 1 {
		t.Fatalf("agreeing reject pair altered errors: %v", out)
	}

	// unavailable library fails closed (compiled == nil)
	if out := verdictChecked("s", nil, nil, "pillar"); len(out) != 1 || !strings.Contains(out[0], "unavailable") {
		t.Fatalf("nil compiled did not fail closed: %v", out)
	}
}

// TestProductionWiringFailsClosed pins that the PUBLIC entries invoke the
// cross-check (V7 M-1): the pillar test above calls verdictChecked directly,
// so deleting the Check*Verdict call sites stayed green — the wiring, not the
// alarm, was the unpinned half of the claim "cross-checked on every
// validation". Breaking the library deliberately (nil compiled schema) must
// surface "schema library unavailable" THROUGH ContractErrors / EnvelopeErrors;
// remove the production call and these assertions go red.
func TestProductionWiringFailsClosed(t *testing.T) {
	doc := map[string]any{"contract_version": "0.1.0"}

	// compile FIRST so the saved values are the real compiled schemas, then
	// break them: nil-ing before the first compileLibraries() call would let the
	// once-guard recompile and overwrite the nils mid-test (V11 fix).
	compileLibraries()
	saveContract, saveEnvelope := libContract, libEnvelope
	libContract, libEnvelope = nil, nil
	defer func() { libContract, libEnvelope = saveContract, saveEnvelope }()

	errs := ContractErrors(doc)
	if !hasSubstr(errs, "schema library unavailable") {
		t.Fatalf("ContractErrors did not surface the fail-closed wiring: %v", errs)
	}
	errs, _ = EnvelopeErrors(map[string]any{
		"envelope_version": "0.1.0", "contract": doc, "contract_hash": "x",
		"signatures": []any{},
	}, &TrustStore{}, false)
	if !hasSubstr(errs, "schema library unavailable") {
		t.Fatalf("EnvelopeErrors did not surface the fail-closed wiring: %v", errs)
	}
}

func hasSubstr(errs []string, substr string) bool {
	for _, e := range errs {
		if strings.Contains(e, substr) {
			return true
		}
	}
	return false
}

// TestFmtNumOverflow pins the >=2^63 guard (V12/V21 F2): beyond int64 the
// renderer falls back to %v — deleting the guard saturates to MaxInt64 (or
// another implementation-defined value) that can silently masquerade.
func TestFmtNumOverflow(t *testing.T) {
	if got := fmtNum(1e21); got != "1e+21" {
		t.Fatalf("fmtNum(1e21) = %q, want the %%v fallback 1e+21", got)
	}
	if got := fmtNum(9223372036854775808.0); got == "9223372036854775807" {
		t.Fatalf("fmtNum(2^63) saturated to MaxInt64: %q", got)
	}
	if got := fmtNum(-9223372036854775808.0); got == "-9223372036854775808" {
		t.Fatalf("fmtNum(-2^63) printed as an in-range integer: %q", got)
	}
}

// TestErrorOrderDeterministic pins the sorted-key iteration (V23 4-lens M-1):
// a document with several unknown properties must report them in sorted key
// order on every trial — removing the sort makes map order random and this
// flakes within a few trials (30 trials × 3 keys ≈ certain detection).
func TestErrorOrderDeterministic(t *testing.T) {
	doc := map[string]any{
		"contract_version": "0.1.0",
		"zz-bad":           1,
		"aa-bad":           1,
		"mm-bad":           1,
	}
	for trial := 0; trial < 30; trial++ {
		errs := ContractErrors(doc)
		if len(errs) < 3 {
			t.Fatalf("trial %d: expected at least 3 errors, got %v", trial, errs)
		}
		tail := errs[len(errs)-3:]
		for i, want := range []string{"aa-bad", "mm-bad", "zz-bad"} {
			if !strings.Contains(tail[i], want) {
				t.Fatalf("trial %d: error %d is %q, want the %s violation (sorted order broken)", trial, i, tail[i], want)
			}
		}
	}
}

// TestBothPinsParseError is the body pin behind the both-pins guard (V24 F2):
// a fixture carrying both pins must surface the authoring error — the guard
// alone was constant-true when its sentinel contained the match phrase.
func TestBothPinsParseError(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "both.tmp.json")
	if err := os.WriteFile(p, []byte(`{"_expect_verified_kids": [], "_expect_composed": {}}`), 0o644); err != nil {
		t.Fatal(err)
	}
	fx, err := LoadFixture(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError == "" || !strings.Contains(fx.ParseError, "carries both") {
		t.Fatalf("both-pins fixture ParseError = %q, want the carries-both authoring error", fx.ParseError)
	}
}

// TestContractNaNRejected is the body pin behind cmd/validate's NaN guard
// cases (V24 F1/p1d): a programmatic NaN bound must fail the contract's
// integer type check — the guard's final-return aggregation is only reachable
// through this production behavior, so it gets its own pin.
func TestContractNaNRejected(t *testing.T) {
	doc := map[string]any{
		"contract_version": "0.1.0",
		"subject":          map[string]any{"id": "x", "kind": "agent", "version": "1"},
		"provides":         []any{},
		"requires":         []any{},
		"effects":          map[string]any{"level": "none"},
		"bounds":           map[string]any{"max_seconds": math.NaN()},
	}
	errs := ContractErrors(doc)
	if !hasSubstr(errs, "not of type 'integer'") {
		t.Fatalf("NaN bound not rejected: %v", errs)
	}
}

// The three sibling order pins (V24 4-lens M-2): propertyNames, subject_of
// and splitViolations each sort their map iteration — each pin drives the
// production entry with MULTIPLE violating members so removing the sort
// flips the order within a few trials.

func TestPropertyNamesErrorOrderDeterministic(t *testing.T) {
	schema := Schema{"propertyNames": map[string]any{"pattern": "^[a-z]+$"}}
	doc := map[string]any{"zz-bad": 1, "aa-bad": 1, "mm-bad": 1}
	for trial := 0; trial < 30; trial++ {
		var errs []string
		SchemaErrors(doc, schema, "<root>", &errs)
		if len(errs) != 3 {
			t.Fatalf("trial %d: got %d errors, want 3: %v", trial, len(errs), errs)
		}
		for i, want := range []string{"aa-bad", "mm-bad", "zz-bad"} {
			if !strings.Contains(errs[i], want) {
				t.Fatalf("trial %d: error %d is %q, want %s (sorted order broken)", trial, i, errs[i], want)
			}
		}
	}
}

func TestSubjectOfErrorOrderDeterministic(t *testing.T) {
	dir := t.TempDir()
	store := map[string]any{
		"keys": []any{map[string]any{
			"kty": "EC", "crv": "P-256",
			"x":   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
			"y":   "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
			"kid": "real-kid", "use": "sig", "alg": "ES256",
		}},
		"subject_of": map[string]any{
			"zz-kid": []any{"s"},
			"aa-kid": []any{"s"},
		},
	}
	raw, _ := json.Marshal(store)
	p := filepath.Join(dir, "so.jwks.json")
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	for trial := 0; trial < 30; trial++ {
		_, err := LoadTrustStore(p)
		if err == nil || !strings.Contains(err.Error(), "aa-kid") {
			t.Fatalf("trial %d: first unknown kid is not the sorted-first one: %v", trial, err)
		}
	}
}

// TestExpectMatchTypeStrict pins the fifth face (V28 F-1): a wrong-typed
// _expect_match pin is an authoring error that must fail LOUD — the silent
// downgrade to "no pin" bypassed the wrong-reason checks; the oracle crashes.
func TestExpectMatchTypeStrict(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "badmatch.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "_expect_match": 5}`), 0o644); err != nil {
		t.Fatal(err)
	}
	fx, err := LoadFixture(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError == "" || !strings.Contains(fx.ParseError, "must be a string") {
		t.Fatalf("wrong-typed _expect_match ParseError = %q, want the type error", fx.ParseError)
	}
}

// TestEmptyEnumRejectsEverything pins the empty-enum code fix (V28 m-1 /
// V29 F-2): the hand engine rejects on an empty enum itself — the fix had
// landed with zero kill evidence (the disagreement alarm never fires: no
// schema uses an empty enum).
func TestEmptyEnumRejectsEverything(t *testing.T) {
	var errs []string
	SchemaErrors("x", Schema{"enum": []any{}}, "<root>", &errs)
	if len(errs) == 0 {
		t.Fatal("empty enum accepted by the hand engine — the V28 fix regressed")
	}
}

// TestExpectMatchFalsyLoud pins the falsy sub-face (V28 m-2 / V29 F-3): the
// oracle's truthiness check silently SKIPS falsy pins (null/0/[]/false);
// our loud rejection is the strict-side-wins reading — a parity "cleanup"
// that mirrors Python here must turn this red.
func TestExpectMatchFalsyLoud(t *testing.T) {
	dir := t.TempDir()
	for _, falsy := range []string{"null", "0", "[]", "false"} {
		p := filepath.Join(dir, "falsy.json")
		if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "_expect_match": `+falsy+`}`), 0o644); err != nil {
			t.Fatal(err)
		}
		fx, err := LoadFixture(p)
		if err != nil {
			t.Fatal(err)
		}
		if fx.ParseError == "" {
			t.Fatalf("falsy _expect_match (%s) silently skipped — the strict-side reading regressed", falsy)
		}
	}
}

// TestMinItemsFullPhrasing pins both minItems phrasings (V29 M-1, evidenced
// now — V30 F-2): full path AND the actual instance, "should be non-empty"
// only for the empty case, "is too short" for minItems>=2.
func TestMinItemsFullPhrasing(t *testing.T) {
	var errs []string
	SchemaErrors([]any{"a"}, Schema{"minItems": 2.0}, "edges/0", &errs)
	if len(errs) != 1 || !strings.Contains(errs[0], "edges/0: [a] is too short") {
		t.Fatalf("short-edge phrasing wrong: %v", errs)
	}
	errs = nil
	SchemaErrors([]any{}, Schema{"minItems": 1.0}, "requires/0/actions", &errs)
	if len(errs) != 1 || !strings.Contains(errs[0], "requires/0/actions: [] should be non-empty") {
		t.Fatalf("empty phrasing wrong: %v", errs)
	}
}

// TestTypeNameBoundary pins the architecture-stable name (V29 F-4, the one
// sibling the V30 sweep missed): beyond int64 the bare conversion is
// implementation-defined, and 1e19 kills the removed-clause mutation even on
// arm64 (int64(1e19) saturates to MaxInt64, whose float64 != 1e19).
func TestTypeNameBoundary(t *testing.T) {
	for _, v := range []float64{1e19, 9223372036854775808.0, -9223372036854775808.0} {
		if got := typeName(v); got != "integer" {
			t.Fatalf("typeName(%v) = %q, want integer", v, got)
		}
	}
	if got := typeName(2.5); got != "number" {
		t.Fatalf("typeName(2.5) = %q, want number", got)
	}
	if got := typeName(3.0); got != "integer" {
		t.Fatalf("typeName(3.0) = %q, want integer", got)
	}
}

// TestMatchAtWordBoundary pins the token-boundary guard (V34 N1, evidenced
// V35 F-1): a longer token like InfinityX is a syntax error, not a non-finite
// literal — the ParseError must not name Infinity as the reason.
func TestMatchAtWordBoundary(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "infX.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "notes": "x", "zz": InfinityX}`), 0o644); err != nil {
		t.Fatal(err)
	}
	fx, err := LoadFixture(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError == "" {
		t.Fatal("a bare InfinityX token was not rejected at parse")
	}
	if strings.Contains(fx.ParseError, "Infinity is not a JSON number") {
		t.Fatalf("syntax error misattributed to a non-finite literal: %q", fx.ParseError)
	}
	if !matchAt([]byte("InfinityX"), 0, "Infinity") == false {
		t.Fatal("matchAt accepted InfinityX as the Infinity token")
	}
}

// TestMatchAtPredecessorBoundary pins the second half (V35 4-lens m-1):
// tokens embedded in a syntax error ("1.NaN", "- Infinity") must be
// attributed to the parser, not named as bare non-finite literals.
func TestMatchAtPredecessorBoundary(t *testing.T) {
	if matchAt([]byte("1.NaN"), 2, "NaN") {
		t.Fatal("matchAt accepted NaN embedded in 1.NaN")
	}
	if matchAt([]byte("- Infinity"), 2, "Infinity") {
		t.Fatal("matchAt accepted Infinity embedded in '- Infinity'")
	}
	if !matchAt([]byte(":NaN,"), 1, "NaN") {
		t.Fatal("matchAt rejected a genuine bare NaN token")
	}
	dir := t.TempDir()
	p := filepath.Join(dir, "embedded.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "zz": 1.NaN}`), 0o644); err != nil {
		t.Fatal(err)
	}
	fx, err := LoadFixture(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError == "" {
		t.Fatal("1.NaN was not rejected at parse")
	}
	if strings.Contains(fx.ParseError, "NaN is not a JSON number") {
		t.Fatalf("syntax error misattributed to a non-finite literal: %q", fx.ParseError)
	}
}

// TestMatchAtSignSeparatedBehavior pins the sign-separated sub-branch's
// behavior face (V36 NIT-1): "- Infinity" must be attributed to the parser,
// not to a bare non-finite literal — the unit assertion alone left the
// message face unpinned.
func TestMatchAtSignSeparatedBehavior(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "signsep.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0", "zz": - Infinity}`), 0o644); err != nil {
		t.Fatal(err)
	}
	fx, err := LoadFixture(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.ParseError == "" {
		t.Fatal("- Infinity was not rejected at parse")
	}
	if strings.Contains(fx.ParseError, "Infinity is not a JSON number") {
		t.Fatalf("syntax error misattributed to a bare non-finite literal: %q", fx.ParseError)
	}
}
