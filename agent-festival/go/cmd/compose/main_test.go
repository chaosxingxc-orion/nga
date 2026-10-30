package main

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"festival-dev/go/internal/compose"
	"festival-dev/go/internal/validate"
)

// The runner's pin-comparison guards live here as testing.T tests (V21 F3:
// cmd/compose had zero test files, so shadowing/print-and-vanish degradations
// were invisible to `go test`; t.Fatalf has no bad++ aggregation to shadow).
// Each test drives the PRODUCTION entry (ComposeErrors / composedMismatches).

func loadSample(t *testing.T) map[string]any {
	t.Helper()
	compose.RegisterGraph() // production main() does this before any ComposeErrors call
	for _, root := range []string{"../../schema", "../../../schema"} {
		fx, err := validate.LoadFixture(filepath.Join(root, "examples", "compose", "valid", "parallel-split-inexact-share.json"))
		if err != nil {
			continue
		}
		if fx.ParseError != "" {
			t.Fatalf("sample fixture parse error: %s", fx.ParseError)
		}
		return fx.Doc
	}
	t.Fatal("sample fixture not found")
	return nil
}

// TestMalformedPinKeys covers the four key-level guards (V17/V18): a
// present-but-wrong-typed pin key must FAIL, not silently skip.
func TestMalformedPinKeys(t *testing.T) {
	pins := map[string]any{
		"requires": "not-a-list", "effects": []any{"x"},
		"bounds": 7, "shares": 5,
	}
	for _, key := range []string{"requires", "effects", "bounds", "shares"} {
		oneKey := map[string]any{}
		oneKey[key] = pins[key]
		mism := composedMismatches(nil, oneKey)
		if len(mism) == 0 || !anyContains(mism, "is malformed (want") {
			t.Fatalf("malformed pin key %s produced %v (want an 'is malformed (want' mismatch)", key, mism)
		}
	}
}

// TestMalformedPinEntry covers the entry-level guard (V8 F3): a 2-element
// requires pin entry must FAIL, not drop out of the comparison.
func TestMalformedPinEntry(t *testing.T) {
	entryPin := map[string]any{"requires": []any{[]any{"data", "x"}}}
	if mism := composedMismatches(nil, entryPin); len(mism) == 0 {
		t.Fatal("malformed pin entry silently passed")
	}
}

// TestValueLevelUnitPin pins the type-strict comparator (V19/V20/V21 F1):
// graph unit "5" (string) vs pin unit 5 (number) is same-text/different-type —
// a %v text comparator collapses it into a silent pass, DeepEqual must not.
func TestValueLevelUnitPin(t *testing.T) {
	doc := cloneOf(loadSample(t))
	rewriteUnitsToFive(doc)
	res := compose.ComposeErrors(doc)
	if len(res.Errors) > 0 {
		t.Fatalf("sample graph rejected: %v", res.Errors[:1])
	}
	gotBounds, ok := res.Composed["bounds"].(map[string]any)
	if !ok {
		t.Fatal("no composed bounds")
	}
	pinBounds := cloneOf(gotBounds)
	mc, ok := pinBounds["max_cost"].(map[string]any)
	if !ok {
		t.Fatal("no max_cost in composed bounds")
	}
	mc["unit"] = 5
	mism := composedMismatches(res.Composed, map[string]any{"bounds": pinBounds})
	if len(mism) == 0 {
		t.Fatal("numeric unit pin silently passed — the comparator lost type strictness")
	}
}

// TestFmtAmountOverflow pins the ≥2^63 guard (V20 M-3 / V21 F2): beyond int64
// the renderer must fall back to %v, never saturate to MaxInt64.
func TestFmtAmountOverflow(t *testing.T) {
	if got := fmtAmount(1e21); got == "9223372036854775807" {
		t.Fatalf("fmtAmount(1e21) saturated to MaxInt64: %q", got)
	}
	if got := fmtAmount(1e21); got != "1e+21" {
		t.Fatalf("fmtAmount(1e21) = %q, want the %v fallback", got, "1e+21")
	}
}

// TestGuardOutcomesAllGreen pins the guard suite against false positives —
// every programmatic guard must be OK on the current tree (a broken guard
// body shows up as a mutation-kill in the body-pin tests; a FALSE PASS here
// means a guard silently stopped testing anything).
func TestGuardOutcomesAllGreen(t *testing.T) {
	for _, o := range guardOutcomes(samplePath(t)) {
		if !o.ok {
			t.Fatalf("guard %s: %s", o.name, o.detail)
		}
	}
}

// captureStdout runs body with os.Stdout piped to a concurrent reader —
// read-after-close only deadlocks once the pipe buffer fills (V24 4-lens m2).
func captureStdout(t *testing.T, body func()) string {
	t.Helper()
	old := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stdout = w
	done := make(chan string, 1)
	go func() {
		buf, _ := io.ReadAll(r)
		done <- string(buf)
	}()
	defer r.Close() // the read end was never closed — fd leak per capture (V25 4-lens N1)
	body()
	w.Close()
	os.Stdout = old
	return <-done
}

// TestPrintGuardOutcomesCounts pins the AGGREGATOR itself (V22 singularity
// F1): the returned failure count must equal the number of printed FAIL
// lines — this is the counting point that once lived as shadowable bad++
// inside the guard blocks (print-and-vanish class, V20 M-1).
func TestPrintGuardOutcomesCounts(t *testing.T) {
	outcomes := []guardOutcome{
		{"a-pass", true, "ok"},
		{"b-fail", false, "reason b"},
		{"c-fail", false, "reason c"},
		{"d-pass", true, "ok"},
	}
	var fails int
	buf := captureStdout(t, func() { fails = printGuardOutcomes(outcomes) })
	if fails != 2 {
		t.Fatalf("printGuardOutcomes counted %d failures, want 2", fails)
	}
	if n := strings.Count(buf, "FAIL"); n != 2 {
		t.Fatalf("printed %d FAIL lines, want 2 (output: %s)", n, buf)
	}
}

func samplePath(t *testing.T) string {
	t.Helper()
	for _, root := range []string{"../../schema", "../../../schema"} {
		p := filepath.Join(root, "examples", "compose", "valid", "parallel-split-inexact-share.json")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	t.Fatal("sample fixture not found")
	return ""
}

// TestRunExitCodePropagatesFailures pins the FULL compose decision chain
// (V23 S1): a poisoned _expect_composed pin must reach run()'s return value.
func TestRunExitCodePropagatesFailures(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "valid", "parallel-split-inexact-share.json")
	doc := readJSONMap(t, poison)
	if pin, ok := doc["_expect_composed"].(map[string]any); ok {
		if bounds, ok := pin["bounds"].(map[string]any); ok {
			bounds["max_seconds"] = 999999 // wrong on purpose
		}
	}
	writeJSONMap(t, poison, doc)

	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	if rc := run(); rc == 0 {
		t.Fatal("run() returned 0 despite a poisoned composed pin")
	}
}

// TestRunCleanTreeZero pins the positive direction on the untouched corpus,
// AND that run() actually wires the guard battery in (mutC1: unwiring
// guardSuite from run() left rc unchanged — the wiring is pinned by the guard
// section's presence in the output, not just by the exit code).
func TestRunCleanTreeZero(t *testing.T) {
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc != 0 {
		t.Fatalf("run() = %d on the clean tree, want 0", rc)
	}
	if !strings.Contains(buf, "PASS programmatic") {
		t.Fatal("run() produced no programmatic guard lines — guardSuite is unwired from the decision chain")
	}
}

// TestGuardOutcomesCountFloor pins guard EVAPORATION (V23 S2, mutG class):
// the battery must hold its EXACT count — a margin of 1 let a single guard
// evaporate silently (V24 F3), the JCS differential's compared>=80 lesson
// applied at full strength.
func TestGuardOutcomesCountFloor(t *testing.T) {
	const want = 11
	if got := len(guardOutcomes(samplePath(t))); got != want {
		t.Fatalf("guard battery has %d outcomes (want exactly %d) — a guard evaporated or was added without updating the floor", got, want)
	}
}

// The five production assertions behind the guards, pinned directly (V23 S2,
// mutH class: a guard whose condition is gutted reports a false green; these
// tests hold the production behavior the guard condition depends on).

func TestNaNParentBoundsRejected(t *testing.T) {
	doc := loadSample(t)
	bounds, _ := doc["parent_bounds"].(map[string]any)
	if bounds == nil {
		bounds = map[string]any{}
		doc["parent_bounds"] = bounds
	}
	bounds["max_cost"] = map[string]any{"amount": math.NaN(), "unit": "USD"}
	errs := compose.ComposeErrors(doc).Errors
	if !anyContains(errs, "not of type") && !anyContains(errs, "not a finite") {
		t.Fatalf("NaN parent_bounds not rejected: %v", errs)
	}
}

func TestSeqSumSaturationRejects(t *testing.T) {
	src := loadSample(t)
	nodes, _ := src["nodes"].(map[string]any)
	var srcNode map[string]any
	for _, v := range nodes {
		srcNode, _ = v.(map[string]any)
		break
	}
	leaf := cloneOf(srcNode)
	leaf["requires"] = []any{}
	leaf["bounds"] = map[string]any{"max_seconds": int64(9007199254740991)}
	nodes2 := map[string]any{}
	ids := make([]any, 0, 1025)
	for i := 0; i < 1025; i++ {
		id := fmt.Sprintf("n%d", i)
		nodes2[id] = cloneOf(leaf)
		ids = append(ids, id)
	}
	doc := map[string]any{
		"nodes":         nodes2,
		"plan":          map[string]any{"seq": ids},
		"parent_bounds": map[string]any{"max_seconds": int64(9007199254740991)},
	}
	errs := compose.ComposeErrors(doc).Errors
	if !anyContains(errs, "exceeds parent budget") {
		t.Fatalf("1025-leaf saturated sum not rejected: %v", errs[:min(2, len(errs))])
	}
}

func TestIntTypedParentBudgetRejects(t *testing.T) {
	src := loadSample(t)
	nodes, _ := src["nodes"].(map[string]any)
	var srcNode map[string]any
	for _, v := range nodes {
		srcNode, _ = v.(map[string]any)
		break
	}
	nodes3 := map[string]any{}
	for _, nid := range []string{"n0", "n1"} {
		leaf := cloneOf(srcNode)
		leaf["requires"] = []any{}
		leaf["bounds"] = map[string]any{"max_seconds": int64(100)}
		nodes3[nid] = leaf
	}
	doc := map[string]any{
		"nodes":         nodes3,
		"plan":          map[string]any{"seq": []any{"n0", "n1"}},
		"parent_bounds": map[string]any{"max_seconds": 100},
	}
	errs := compose.ComposeErrors(doc).Errors
	if !anyContains(errs, "exceeds parent budget") {
		t.Fatalf("int-typed parent budget not rejected: %v", errs)
	}
}

func TestSharesAreInt64Values(t *testing.T) {
	res := compose.ComposeErrors(loadSample(t))
	if len(res.Errors) > 0 {
		t.Fatalf("sample graph rejected: %v", res.Errors[:1])
	}
	shares, ok := res.Composed["shares"].(map[string]any)
	if !ok || len(shares) == 0 {
		t.Fatal("no shares in composed output")
	}
	for leaf, allot := range shares {
		am, ok := allot.(map[string]any)
		if !ok {
			t.Fatalf("shares[%s] is not a map", leaf)
		}
		for k, v := range am {
			if k == "max_cost" {
				if amount, ok := v.(map[string]any)["amount"]; !ok || fmt.Sprintf("%T", amount) != "int64" {
					t.Fatalf("shares[%s].max_cost.amount is %T, want int64", leaf, amount)
				}
				continue
			}
			if _, isInt := v.(int64); !isInt {
				t.Fatalf("shares[%s][%s] is %T, want int64", leaf, k, v)
			}
		}
	}
}

func TestSharesPinWithoutParentBounds(t *testing.T) {
	doc := loadSample(t)
	delete(doc, "parent_bounds")
	res := compose.ComposeErrors(doc)
	if res.Composed == nil || len(res.Errors) > 0 {
		t.Fatalf("graph failed: %v", res.Errors[:1])
	}
	mism := composedMismatches(res.Composed, map[string]any{"shares": map[string]any{}})
	if !anyContains(mism, "no parent_bounds") {
		t.Fatalf("shares pin without parent_bounds produced %v", mism)
	}
}

func copyComposeTree(t *testing.T) string {
	t.Helper()
	for _, root := range []string{"../../schema", "../../../schema"} {
		src := filepath.Join(root, "examples")
		if _, err := os.Stat(src); err != nil {
			continue
		}
		dst := t.TempDir()
		err := filepath.WalkDir(src, func(p string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			rel, _ := filepath.Rel(src, p)
			target := filepath.Join(dst, rel)
			if d.IsDir() {
				return os.MkdirAll(target, 0o755)
			}
			raw, err := os.ReadFile(p)
			if err != nil {
				return err
			}
			return os.WriteFile(target, raw, 0o644)
		})
		if err != nil {
			t.Fatal(err)
		}
		return dst
	}
	t.Fatal("examples tree not found")
	return ""
}

func readJSONMap(t *testing.T, p string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

func writeJSONMap(t *testing.T, p string, m map[string]any) {
	t.Helper()
	raw, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

// TestRunEmptyCorpusRejected pins the suite-incomplete branch (V24 4-lens
// M-1): an empty corpus must return non-zero WITHOUT killing the process —
// the branch once held os.Exit(1), making run()'s "testable decision chain"
// claim false on this path.
func TestRunEmptyCorpusRejected(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "compose", "valid"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(dir, "compose", "invalid"), 0o755); err != nil {
		t.Fatal(err)
	}
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	if rc := run(); rc == 0 {
		t.Fatal("run() = 0 on an empty corpus — the suite-incomplete branch lost its failure")
	}
}

// TestSplitViolationsErrorOrderDeterministic pins splitViolations' sorted
// leaf iteration (V24 4-lens M-2): both leaves violate their shares; the
// sorted-first leaf (aa-leaf) must be reported first, every trial.
func TestSplitViolationsErrorOrderDeterministic(t *testing.T) {
	sample := loadSample(t)
	srcNodes, _ := sample["nodes"].(map[string]any)
	var srcNode map[string]any
	for _, v := range srcNodes {
		srcNode, _ = v.(map[string]any)
		break
	}
	leaf := func() map[string]any {
		n := cloneOf(srcNode) // a real, schema-valid node
		n["requires"] = []any{}
		n["bounds"] = map[string]any{"max_seconds": int64(100)}
		return n
	}
	doc := map[string]any{
		"nodes": map[string]any{"zz-leaf": leaf(), "aa-leaf": leaf()},
		"plan":  map[string]any{"par": []any{"zz-leaf", "aa-leaf"}},
		"parent_bounds": map[string]any{
			"max_seconds":          int64(50),
			"max_downstream_calls": int64(4),
			"max_cost":             map[string]any{"amount": int64(100), "unit": "USD-cents"},
		},
	}
	for trial := 0; trial < 30; trial++ {
		errs := compose.ComposeErrors(cloneOf(doc)).Errors
		var splitErrs []string
		for _, e := range errs {
			if strings.Contains(e, "leaf") {
				splitErrs = append(splitErrs, e)
			}
		}
		if len(splitErrs) < 2 {
			t.Fatalf("trial %d: expected >= 2 split violations, got %v", trial, errs)
		}
		if !strings.Contains(splitErrs[0], "aa-leaf") {
			t.Fatalf("trial %d: first split violation is %q, want the sorted-first leaf aa-leaf", trial, splitErrs[0])
		}
	}
}

// TestComposeMustRejectPoison pins the must-REJECT direction of the compose
// runner (V25 singularity F-3): a must-reject fixture that is actually valid
// must FAIL the suite and reach run()'s return value — only the must-accept
// direction had a poison before.
func TestComposeMustRejectPoison(t *testing.T) {
	dir := copyComposeTree(t)
	// caller-holds-absent fails only because caller_holds is missing — put it
	// back and the graph becomes valid ("was accepted!")
	fix := filepath.Join(dir, "compose", "invalid", "caller-holds-absent.json")
	doc := readJSONMap(t, fix)
	sample := loadSample(t)
	if ch, ok := sample["caller_holds"]; ok {
		doc["caller_holds"] = ch
	} else {
		doc["caller_holds"] = []any{}
	}
	delete(doc, "_expect_match")
	delete(doc, "_expect")
	writeJSONMap(t, fix, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	if rc := run(); rc == 0 {
		t.Fatal("run() = 0 despite a must-reject fixture being accepted — the reject direction lost its aggregation")
	}
}

// TestComposeWrongReasonPoison pins compose's wrong-reason branch (V26
// singularity F-2, the fourth suite): a must-reject graph rejected for a
// reason its pin does not name must FAIL.
func TestComposeWrongReasonPoison(t *testing.T) {
	dir := copyComposeTree(t)
	fix := filepath.Join(dir, "compose", "invalid", "orphan-in-edge.json")
	doc := readJSONMap(t, fix)
	delete(doc, "_expect")
	doc["_expect_match"] = "zzz-no-such-reason"
	writeJSONMap(t, fix, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	if rc := run(); rc == 0 {
		t.Fatal("run() = 0 despite a wrong-reason compose rejection — the wrong-reason branch lost its aggregation")
	}
}

// TestComposeSuiteCountFloors pins the compose corpus size (V26 singularity
// F-3): shrinking by one fixture must change the summary line.
func TestComposeSuiteCountFloors(t *testing.T) {
	buf := captureStdout(t, func() {
		if rc := run(); rc != 0 {
			t.Fatalf("clean-tree run() = %d", rc)
		}
	})
	if !strings.Contains(buf, "[compose] 9 must-accept + 32 must-reject, 0 failures") {
		t.Fatalf("compose summary line missing (corpus shrank?):\n%s", buf)
	}
}

// TestLeafAllotmentsNormalizesFloatParent pins the FORCED DIVERGENCE (V26
// 4-lens m-4): the oracle passes seq-leaf shares through RAW and fails its
// own must-accept on a float parent ("60.0" vs "60"); Go normalizes — the
// Go-lenient shape is pinned here because no shared fixture can express it.
func TestLeafAllotmentsNormalizesFloatParent(t *testing.T) {
	sample := loadSample(t)
	srcNodes, _ := sample["nodes"].(map[string]any)
	var srcNode map[string]any
	for _, v := range srcNodes {
		srcNode, _ = v.(map[string]any)
		break
	}
	nodes := map[string]any{}
	for _, nid := range []string{"n0", "n1"} {
		leaf := cloneOf(srcNode)
		leaf["requires"] = []any{}
		leaf["bounds"] = map[string]any{"max_seconds": int64(30)}
		nodes[nid] = leaf
	}
	doc := map[string]any{
		"nodes":         nodes,
		"plan":          map[string]any{"seq": []any{"n0", "n1"}},    // seq: shares pass the parent through
		"parent_bounds": map[string]any{"max_seconds": float64(100)}, // FLOAT parent: the oracle self-rejects this shape
	}
	res := compose.ComposeErrors(doc)
	if len(res.Errors) > 0 {
		t.Fatalf("sample graph rejected under float parent: %v", res.Errors[:1])
	}
	shares, ok := res.Composed["shares"].(map[string]any)
	if !ok || len(shares) == 0 {
		t.Fatal("no shares in composed output")
	}
	for leaf, allot := range shares {
		am, ok := allot.(map[string]any)
		if !ok {
			t.Fatalf("shares[%s] is not a map", leaf)
		}
		for k, v := range am {
			if k == "max_cost" {
				continue
			}
			if _, isInt := v.(int64); !isInt {
				t.Fatalf("shares[%s][%s] is %T under a float parent — normalization regressed (oracle self-rejects this shape, Go must not)", leaf, k, v)
			}
		}
	}
}

// TestRequiresNumericTwinPin pins the requires face's type strictness (V27
// 4-lens M-1): a pin whose selector is the NUMBER 5 where the composed atom
// holds the STRING "5" is same-text/different-type — %v rendering collapsed
// it into a silent pass where the oracle FAILs.
func TestRequiresNumericTwinPin(t *testing.T) {
	sample := loadSample(t)
	srcNodes, _ := sample["nodes"].(map[string]any)
	var srcNode map[string]any
	for _, v := range srcNodes {
		srcNode, _ = v.(map[string]any)
		break
	}
	// a node whose requires selector is the STRING "5" — its numeric twin 5.0
	// renders identically under %v, which is exactly the collapse class
	node := cloneOf(srcNode)
	node["requires"] = []any{map[string]any{
		"resource": map[string]any{"kind": "data", "selector": "5"},
		"actions":  []any{"read"},
		"effect":   "none",
	}}
	doc := map[string]any{
		"nodes": map[string]any{"n0": node},
		"plan":  map[string]any{"seq": []any{"n0"}},
	}
	// the caller must hold the grant, or admissibility rejects the graph
	if ch, ok := sample["caller_holds"].([]any); ok {
		holder := make([]any, 0, len(ch)+1)
		holder = append(holder, ch...)
		holder = append(holder, map[string]any{
			"resource": map[string]any{"kind": "data", "selector": "5"},
			"actions":  []any{"read"},
			"effect":   "none",
		})
		doc["caller_holds"] = holder
	} else {
		doc["caller_holds"] = []any{map[string]any{
			"resource": map[string]any{"kind": "data", "selector": "5"},
			"actions":  []any{"read"},
			"effect":   "none",
		}}
	}
	res := compose.ComposeErrors(doc)
	if len(res.Errors) > 0 {
		t.Fatalf("graph rejected: %v", res.Errors[:1])
	}
	reqs, _ := res.Composed["requires"].(map[string]any)
	if len(reqs) == 0 {
		t.Fatal("no composed requires")
	}
	pin := map[string]any{"requires": []any{[]any{"data", 5.0, "read", "none"}}}
	if mism := composedMismatches(res.Composed, pin); len(mism) == 0 {
		t.Fatal("numeric twin selector pin silently passed — the requires comparison lost type strictness")
	}
}

// TestComposeParseErrorPoison pins compose's ParseError propagation (V30
// F-1a, the third sibling).
func TestComposeParseErrorPoison(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "invalid", "orphan-in-edge.json")
	doc := readJSONMap(t, poison)
	doc["_expect_match"] = 5
	writeJSONMap(t, poison, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc == 0 {
		t.Fatal("run() = 0 — an unreadable pin on a must-reject fixture must FAIL (V32 M-1 flip)")
	}
	if !strings.Contains(buf, "must be a string") {
		t.Fatal("compose fixture's parse error was dropped from the output")
	}
}

// TestComposeKidsPinLoud pins the kids-pin-on-compose face (V30 F-4): the
// oracle silently skips a list-shaped pin; our loud FAIL is the strict-side
// FORCED DIVERGENCE reading.
func TestComposeKidsPinLoud(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "valid", "parallel-split-inexact-share.json")
	doc := readJSONMap(t, poison)
	delete(doc, "_expect_composed")
	doc["_expect_verified_kids"] = []any{"k"}
	writeJSONMap(t, poison, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc == 0 {
		t.Fatal("run() = 0 despite a kids-shaped pin on a compose fixture — the strict side must FAIL loudly")
	}
	if !strings.Contains(buf, "is not an object") {
		t.Fatalf("the malformed-pin message is missing (the fourth face, V32 F-2): %s", tailN(buf, 300))
	}
}

// TestComposeValidParseError pins the valid half (V31 F-2).
func TestComposeValidParseError(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "valid", "parallel-split-inexact-share.json")
	doc := readJSONMap(t, poison)
	doc["_expect_match"] = 5
	writeJSONMap(t, poison, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc == 0 {
		t.Fatal("run() = 0 despite a wrong-typed pin on a must-accept compose fixture — the valid half lost its propagation")
	}
	if !strings.Contains(buf, "must be a string") {
		t.Fatal("the rejection reason is missing from the output (message face unpinned — V32 F-1)")
	}
}

func tailN(s string, n int) string {
	if len(s) > n {
		return "..." + s[len(s)-n:]
	}
	return s
}

// TestMaxCostScalarPinMalformed pins the shape-level guard (V32 4-lens m-1 /
// V33 F-1): a bounds pin whose max_cost is a SCALAR was silently dropped by
// the renderer and the pin spun empty on a graph with no bounds — the oracle
// crashes loudly; deleting the guard made every suite green (zero kill).
func TestMaxCostScalarPinMalformed(t *testing.T) {
	doc := loadSample(t)
	delete(doc, "parent_bounds") // keep the graph simple; bounds may be absent
	res := compose.ComposeErrors(doc)
	if len(res.Errors) > 0 {
		t.Fatalf("sample graph rejected: %v", res.Errors[:1])
	}
	pin := map[string]any{"bounds": map[string]any{"max_cost": 7}}
	mism := composedMismatches(res.Composed, pin)
	if len(mism) == 0 {
		t.Fatal("scalar max_cost pin silently passed — the shape-level guard regressed")
	}
	if !anyContains(mism, "max_cost is malformed") {
		t.Fatalf("the malformed-pin message is missing (message face unpinned): %v", mism)
	}
}

// TestFlipScaffoldingMessage pins one flip site's scaffolding text (V33 F-2):
// the "unreadable pin cannot verify the rejection" wording is part of the
// authoring-error family face — a downgrade would go unnoticed otherwise.
func TestFlipScaffoldingMessage(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "invalid", "orphan-in-edge.json")
	doc := readJSONMap(t, poison)
	doc["_expect_match"] = 5
	writeJSONMap(t, poison, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc == 0 {
		t.Fatal("run() = 0 — the flip itself regressed")
	}
	if !strings.Contains(buf, "unreadable pin cannot verify the rejection") {
		t.Fatal("the flip scaffolding message is missing (downgraded?) — V33 F-2")
	}
}

// TestRunMaxCostScalarPinLoud pins the shape guard at the run() level (V34
// F-4): the direct composedMismatches pin covers the body, this drives the
// full decision chain — a scalar max_cost pin on a valid fixture must FAIL.
func TestRunMaxCostScalarPinLoud(t *testing.T) {
	dir := copyComposeTree(t)
	poison := filepath.Join(dir, "compose", "valid", "parallel-split-inexact-share.json")
	doc := readJSONMap(t, poison)
	if pin, ok := doc["_expect_composed"].(map[string]any); ok {
		if bounds, ok := pin["bounds"].(map[string]any); ok {
			bounds["max_cost"] = 7 // scalar twin of the object shape
		}
	}
	writeJSONMap(t, poison, doc)
	save := compose.ExamplesDir
	compose.ExamplesDir = dir
	defer func() { compose.ExamplesDir = save }()
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc == 0 {
		t.Fatal("run() = 0 despite a scalar max_cost pin — the shape guard is unwired from the decision chain")
	}
	if !strings.Contains(buf, "max_cost is malformed") {
		t.Fatalf("the malformed-pin message is missing at the run() level: %s", tailN(buf, 400))
	}
}
