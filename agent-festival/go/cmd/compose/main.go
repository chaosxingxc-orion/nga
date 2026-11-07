// compose runs the execution-graph composition suite (Go successor of schema/compose.py).
package main

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"github.com/openjiuwen/agent-festival/go/internal/compose"
	"github.com/openjiuwen/agent-festival/go/internal/suite"
	"github.com/openjiuwen/agent-festival/go/internal/validate"
)

func main() { os.Exit(run()) }

// run is the full CLI decision chain as a testable function (V23 S1).
func run() int {
	compose.RegisterGraph()
	base := filepath.Join(compose.ExamplesDir, "compose")
	// the frozen base's rich loader (bare-NaN scan, surrogate scoping, regex
	// pin extraction) bridged into the shared suite discipline; the composed
	// pins ride the WithLoader closure (a captured pins map keyed by path;
	// R2-A4 moved the last inline phase harness here) and the composed-map
	// comparison runs as a post-loop over the collected fixtures (R20 B-3:
	// the old comment pointed at Extra/WithValidExtra — a born-dead data
	// path this checker never actually used).
	pins := map[string]any{}
	bad := suite.Run("compose",
		filepath.Join(base, "valid"), filepath.Join(base, "invalid"),
		func(doc map[string]any) []string {
			return compose.ComposeErrors(doc).Errors
		},
		suite.WithLoader(func(path string) (*suite.Fixture, error) {
			fx, err := validate.LoadFixture(path)
			if err != nil {
				return nil, err
			}
			pins[path] = fx.Pin
			return &suite.Fixture{Doc: fx.Doc, ExpectMatch: fx.ExpectMatch, ParseError: fx.ParseError}, nil
		}),
	)
	// composed-output pins: the base's _expect_composed comparison, kept here
	// because it consumes the checker's structured output
	files, _ := filepath.Glob(filepath.Join(base, "valid", "*.json"))
	sort.Strings(files)
	for _, f := range files {
		pin, has := pins[f]
		if !has || pin == nil {
			continue
		}
		fx, err := validate.LoadFixture(f)
		if err != nil || fx.ParseError != "" {
			continue // already reported by the phase loop
		}
		expected, ok := pin.(map[string]any)
		if !ok {
			fmt.Printf("[compose] FAIL must-accept %s (_expect_composed pin is not an object: %v)\n", filepath.Base(f), pin)
			bad++
			continue
		}
		res := compose.ComposeErrors(fx.Doc)
		if m := composedMismatches(res.Composed, expected); len(m) > 0 {
			fmt.Printf("[compose] FAIL must-accept %s\n", filepath.Base(f))
			for _, e := range m {
				fmt.Printf("      %s\n", e)
			}
			bad++
		}
	}
	if len(files) > 0 {
		bad += guardSuite(files[0])
	}
	return boolExit(bad == 0)
}

// guardOutcome is one programmatic guard's verdict, as pure data (V22
// singularity F1): verdicts are computed in guardOutcomes, printing AND
// counting live in exactly one place — printGuardOutcomes — so there is no
// inner bad++ to shadow and the aggregation itself is pinned by a test.
type guardOutcome struct {
	name   string
	ok     bool
	detail string
}

func guardOutcomes(sample string) []guardOutcome {
	compose.RegisterGraph() // self-contained: no sibling-test side effect needed (V22 4-lens m1)
	var out []guardOutcome
	add := func(name string, ok bool, detail string) {
		out = append(out, guardOutcome{name, ok, detail})
	}
	fx, err := validate.LoadFixture(sample)
	if err != nil {
		return []guardOutcome{{"guards load sample", false, err.Error()}}
	}
	clone := func() map[string]any { return validate.CloneDoc(fx.Doc) } // single source (V23 4-lens n3)

	// NaN parent_bounds must be rejected, not crash the comparison
	doc := clone()
	bounds, _ := doc["parent_bounds"].(map[string]any)
	if bounds == nil {
		bounds = map[string]any{}
		doc["parent_bounds"] = bounds
	}
	bounds["max_cost"] = map[string]any{"amount": math.NaN(), "unit": "USD"}
	errs := compose.ComposeErrors(doc).Errors
	if anyContains(errs, "not of type") || anyContains(errs, "not a finite") {
		add("must-reject parent_bounds NaN", true, firstLine(errs[0]))
	} else {
		add("must-reject parent_bounds NaN", false, fmt.Sprintf("errors: %v", errs))
	}

	// malformed-pin keys (V19 F1): the four key-level guards added in V17/V18
	// had ZERO execution coverage — a table of wrong-typed pins must FAIL with
	// the malformed message, which is exactly what the oracle does (it crashes
	// loudly instead).
	{
		pin := map[string]any{
			"requires": "not-a-list", "effects": []any{"x"},
			"bounds": 7, "shares": 5,
		}
		for _, key := range []string{"requires", "effects", "bounds", "shares"} {
			oneKey := map[string]any{}
			oneKey[key] = pin[key]
			mism := composedMismatches(nil, oneKey)
			if anyContains(mism, "is malformed (want") {
				add("must-reject malformed pin key "+key, true, "malformed (want) message")
			} else {
				add("must-reject malformed pin key "+key, false, fmt.Sprintf("mismatches: %v", mism))
			}
		}
		// value-level (V20 M-2, carrier fixed V21 F1): a numeric max_cost.unit
		// pin must FAIL. The pin is built from a REAL composed output (same-text
		// unit "5" vs numeric 5) so the comparator's type strictness decides.
		// Premise failures are loud too (V21 4-lens m-2).
		srcDoc := clone()
		rewriteUnitsToFive(srcDoc)
		valRes := compose.ComposeErrors(srcDoc)
		if len(valRes.Errors) > 0 {
			add("must-reject numeric unit pin", false, fmt.Sprintf("premise unmet, graph rejected: %v", valRes.Errors[:1]))
		} else if gotBounds, ok := valRes.Composed["bounds"].(map[string]any); !ok {
			add("must-reject numeric unit pin", false, "premise unmet: no composed bounds")
		} else if _, hasCost := gotBounds["max_cost"]; !hasCost {
			add("must-reject numeric unit pin", false, "premise unmet: no max_cost in composed bounds")
		} else {
			pinBounds := cloneOf(gotBounds)
			if mc, ok := pinBounds["max_cost"].(map[string]any); ok {
				mc["unit"] = 5 // numeric twin of the string "5"
			}
			mism := composedMismatches(valRes.Composed, map[string]any{"bounds": pinBounds})
			if len(mism) > 0 {
				// the %v rendering of the maps collapses "5" and 5 — say the
				// actual reason instead of the unreadable twin maps (V23 4-lens n6)
				add("must-reject numeric unit pin", true, "type-strict comparator caught the numeric unit twin")
			} else {
				add("must-reject numeric unit pin", false, "silent pass")
			}
		}
		// entry-level (V8 F3, pinned in V20): a 2-element requires pin entry
		// must FAIL, not drop out of the comparison
		entryPin := map[string]any{"requires": []any{[]any{"data", "x"}}}
		if mism := composedMismatches(nil, entryPin); len(mism) > 0 {
			add("must-reject malformed pin entry", true, firstLine(mism[0]))
		} else {
			add("must-reject malformed pin entry", false, "silent pass")
		}
	}

	// int64 saturation (V2 M5 institutionalized): 1025 leaves at the 2^53-1
	// cap sum past int64 — Go must saturate to the oracle's verdict, not wrap.
	doc = map[string]any{}
	node := clone()
	if nodes, ok := node["nodes"].(map[string]any); ok {
		src, ok := nodes[firstMapKey(nodes)].(map[string]any)
		if !ok {
			panic("guard premise broken: sample node is not an object (sample fixture shape changed?)")
		}
		src = cloneOf(src)
		src["requires"] = []any{} // drop delegate/grant noise; bounds only
		src["bounds"] = map[string]any{"max_seconds": int64(9007199254740991)}
		nodes2 := map[string]any{}
		ids := make([]any, 0, 1025)
		for i := 0; i < 1025; i++ {
			id := fmt.Sprintf("n%d", i)
			nodes2[id] = cloneOf(src)
			ids = append(ids, id)
		}
		doc["nodes"] = nodes2
		doc["plan"] = map[string]any{"seq": ids}
	}
	doc["parent_bounds"] = map[string]any{"max_seconds": int64(9007199254740991)}
	errs = compose.ComposeErrors(doc).Errors
	if anyContains(errs, "exceeds parent budget") {
		add("must-reject seq sum saturates past int64", true, "exceeds parent budget")
	} else {
		add("must-reject seq sum saturates past int64", false, fmt.Sprintf("errors: %v", errs[:min(2, len(errs))]))
	}

	// V11 4-lens M-1: each leaf fits its share, so ONLY the graph-level
	// sum-vs-parent comparison can reject — and the parent is a plain int.
	leafOK := map[string]any{}
	src := clone()
	srcNodes, _ := src["nodes"].(map[string]any)
	nodes3 := map[string]any{}
	for _, nid := range []string{"n0", "n1"} {
		srcNode, ok := srcNodes[firstMapKey(srcNodes)].(map[string]any)
		if !ok {
			panic("guard premise broken: sample node is not an object (sample fixture shape changed?)")
		}
		leaf := cloneOf(srcNode)
		leaf["requires"] = []any{}
		leaf["bounds"] = map[string]any{"max_seconds": int64(100)}
		nodes3[nid] = leaf
	}
	leafOK["nodes"] = nodes3
	leafOK["plan"] = map[string]any{"seq": []any{"n0", "n1"}}
	leafOK["parent_bounds"] = map[string]any{"max_seconds": 100}
	if errs := compose.ComposeErrors(leafOK).Errors; anyContains(errs, "exceeds parent budget") {
		add("must-reject int-typed parent budget", true, "exceeds parent budget")
	} else {
		add("must-reject int-typed parent budget", false, fmt.Sprintf("errors: %v", errs))
	}

	// V11 4-lens M-2: shares are product-facing output; their int64 shape is a
	// type contract (normalization is a forced divergence, pinned here).
	{
		r := compose.ComposeErrors(clone())
		switch {
		case len(r.Errors) > 0:
			add("shares int64 shape", false, fmt.Sprintf("graph rejected: %v", r.Errors[:1]))
		default:
			shares, ok := r.Composed["shares"].(map[string]any)
			if !ok || len(shares) == 0 {
				add("shares int64 shape", false, "no shares")
				break
			}
			bad := ""
			for leaf, allot := range shares {
				am, ok := allot.(map[string]any)
				if !ok {
					bad = fmt.Sprintf("shares[%s] not a map", leaf)
					break
				}
				for k, v := range am {
					if k == "max_cost" {
						if amount, ok := v.(map[string]any)["amount"]; !ok || fmt.Sprintf("%T", amount) != "int64" {
							bad = fmt.Sprintf("shares[%s].max_cost.amount is %T", leaf, amount)
							break
						}
						continue
					}
					if _, isInt := v.(int64); !isInt {
						bad = fmt.Sprintf("shares[%s][%s] is %T", leaf, k, v)
						break
					}
				}
				if bad != "" {
					break
				}
			}
			if bad != "" {
				add("shares int64 shape", false, bad)
			} else {
				add("shares int64 shape", true, "every share value is int64")
			}
		}
	}

	// shares pin without parent_bounds must get a message, not a silent pass
	doc = clone()
	delete(doc, "parent_bounds")
	res := compose.ComposeErrors(doc)
	var mism []string
	if res.Composed == nil || len(res.Errors) > 0 {
		mism = []string{"graph itself failed"}
	} else {
		mism = composedMismatches(res.Composed, map[string]any{"shares": map[string]any{}})
	}
	if anyContains(mism, "no parent_bounds") {
		add("shares pin without parent_bounds", true, firstLine(mism[0]))
	} else {
		add("shares pin without parent_bounds", false, fmt.Sprintf("mismatches: %v", mism))
	}
	return out
}

// printGuardOutcomes is the ONLY place guard verdicts are printed and counted
// (V22 singularity F1): one loop, one counter, pinned by test.
func printGuardOutcomes(outcomes []guardOutcome) int {
	fails := 0
	for _, o := range outcomes {
		if o.ok {
			fmt.Printf("[compose] PASS programmatic %s  (%s)\n", o.name, o.detail)
		} else {
			fmt.Printf("[compose] FAIL programmatic %s  (%s)\n", o.name, o.detail)
			fails++
		}
	}
	return fails
}

func guardSuite(sample string) int {
	return printGuardOutcomes(guardOutcomes(sample))
}

func cloneOf(m map[string]any) map[string]any { return validate.CloneDoc(m) } // single source (V23 4-lens n3)

// rewriteUnitsToFive makes every max_cost unit the STRING "5" so a numeric-5
// pin twin is same-text/different-type — the only shape that distinguishes a
// type-strict comparator from a %v text comparator (V21 F1).
func rewriteUnitsToFive(doc map[string]any) {
	if nodes, ok := doc["nodes"].(map[string]any); ok {
		for _, n := range nodes {
			if nm, ok := n.(map[string]any); ok {
				if b, ok := nm["bounds"].(map[string]any); ok {
					if mc, ok := b["max_cost"].(map[string]any); ok {
						mc["unit"] = "5"
					}
				}
			}
		}
	}
	if pb, ok := doc["parent_bounds"].(map[string]any); ok {
		if mc, ok := pb["max_cost"].(map[string]any); ok {
			mc["unit"] = "5"
		}
	}
}

func firstMapKey(m map[string]any) string {
	for k := range m {
		return k
	}
	return ""
}

func anyContains(errs []string, substr string) bool {
	for _, e := range errs {
		if strings.Contains(e, substr) {
			return true
		}
	}
	return false
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

func boolExit(b bool) int {
	if b {
		return 0
	}
	return 1
}

// composedMismatches mirrors Python composed_mismatches: every comparison is a
// full two-way equality — a leaf missing from either side is a mismatch (V2 F1:
// iterating only the expected side let a dropped leaf pass silently).
func composedMismatches(composed map[string]any, expected map[string]any) []string {
	var errs []string
	// A present-but-malformed pin key FAILS (mirror of V8 F3's entry-level rule,
	// applied at key level): silently skipping it made Go PASS fixtures the
	// oracle FAILs — a runner strictly weaker than the oracle on pin typos.
	// requires
	if expReq, ok := expected["requires"].([]any); ok {
		gotReq, _ := composed["requires"].(map[string]any)
		got := reqToSortedStrings(gotReq)
		want := reqAnyToSortedStrings(expReq)
		if !stringSlicesEqual(got, want) {
			errs = append(errs, fmt.Sprintf("composed requires mismatch: got %v want %v", got, expReq))
		}
	} else if _, has := expected["requires"]; has {
		errs = append(errs, fmt.Sprintf("_expect_composed.requires is malformed (want array): %v", expected["requires"]))
	}
	// effects
	if expEff, ok := expected["effects"].(map[string]any); ok {
		gotEff, _ := composed["effects"].(map[string]any)
		// type-strict like the rest of the pin comparisons (V22 F2: %v rendered
		// a numeric twin of an enum string identically; composed effects are
		// always strings so no normalization is needed — a numeric pin value
		// simply mismatches)
		if !reflect.DeepEqual(gotEff, expEff) {
			errs = append(errs, fmt.Sprintf("composed effects %v != expected %v", gotEff, expEff))
		}
	} else if _, has := expected["effects"]; has {
		errs = append(errs, fmt.Sprintf("_expect_composed.effects is malformed (want object): %v", expected["effects"]))
	}
	// bounds
	if expBounds, ok := expected["bounds"].(map[string]any); ok {
		// a scalar max_cost pin is a malformed pin (V32 4-lens m-1: it was
		// silently DROPPED by the renderer and the pin spun empty on a graph
		// with no bounds — the oracle crashes loudly on this shape)
		if _, hasCost := expBounds["max_cost"]; hasCost {
			if _, isObj := expBounds["max_cost"].(map[string]any); !isObj {
				errs = append(errs, fmt.Sprintf("_expect_composed.bounds.max_cost is malformed (want object): %v", expBounds["max_cost"]))
			}
		}
		gotBounds, _ := composed["bounds"].(map[string]any)
		gotJSON := compose.JSONableBounds(gotBounds)
		wantJSON := jsonableFromExpected(expBounds)
		if !mapsEqualStr(gotJSON, wantJSON) {
			errs = append(errs, fmt.Sprintf("composed bounds %v != expected %v", gotJSON, wantJSON))
		}
	} else if _, has := expected["bounds"]; has {
		errs = append(errs, fmt.Sprintf("_expect_composed.bounds is malformed (want object): %v", expected["bounds"]))
	}
	// shares: issued per-leaf budgets; the only place the split rounding mode is observable
	if expShares, ok := expected["shares"].(map[string]any); ok {
		gotShares, _ := composed["shares"].(map[string]any)
		if gotShares == nil {
			errs = append(errs, "fixture pins shares but the graph has no parent_bounds, so nothing was issued")
		} else {
			for leaf, expAllot := range expShares {
				expM, _ := expAllot.(map[string]any)
				gotAllot, has := gotShares[leaf]
				if !has {
					errs = append(errs, fmt.Sprintf("issued shares %v != expected %v: leaf %s missing", gotShares, expShares, leaf))
					continue
				}
				gotM, _ := gotAllot.(map[string]any)
				if !mapsEqualStr(compose.JSONableBounds(gotM), jsonableFromExpected(expM)) {
					errs = append(errs, fmt.Sprintf("shares[%s]: got %v want %v", leaf, compose.JSONableBounds(gotM), jsonableFromExpected(expM)))
				}
			}
			for leaf := range gotShares {
				if _, inExpected := expShares[leaf]; !inExpected {
					errs = append(errs, fmt.Sprintf("issued shares %v != expected %v: unexpected leaf %s", gotShares, expShares, leaf))
				}
			}
		}
	} else if _, has := expected["shares"]; has {
		// fourth key-level guard (V18 4-lens M-1): a non-object shares pin must
		// FAIL, not silently skip — shares is the ONLY observable face of the
		// split rounding mode; the oracle crashes loudly on this shape
		errs = append(errs, fmt.Sprintf("_expect_composed.shares is malformed (want object): %v", expected["shares"]))
	}
	return errs
}

// mapsEqualStr compares two normalized pin maps with type-strict equality —
// %v rendering collapsed "5" and 5 into the same text and let a wrong-typed
// unit pin pass where the oracle FAILs (V19 4-lens M-1, the value-level layer
// under the entry- and key-level guards).
func mapsEqualStr(a, b map[string]any) bool {
	return reflect.DeepEqual(a, b)
}

func reqToSortedStrings(m map[string]any) []string {
	var out []string
	for k, v := range m {
		parts := strings.SplitN(k, "\x00", 3)
		if len(parts) == 3 {
			out = append(out, fmt.Sprintf("[%s %s %s %v]", parts[0], parts[1], parts[2], v))
		}
	}
	sort.Strings(out)
	return out
}

func reqAnyToSortedStrings(a []any) []string {
	var out []string
	for _, e := range a {
		// malformed pin entries render as-is so they ALWAYS mismatch, mirroring
		// the oracle's full-list comparison — silently skipping them would make
		// the Go runner laxer than the oracle on hand-edited pins (V8 F3)
		m, ok := e.([]any)
		if !ok || len(m) != 4 {
			out = append(out, fmt.Sprintf("[malformed pin entry: %v]", e))
			continue
		}
		// every element must be a STRING: %v rendering collapsed 5 and "5"
		// into the same text and let numeric/bool twin pins pass silently
		// (V27 4-lens M-1 — the fourth face of the type-strictness family)
		k0, ok0 := m[0].(string)
		k1, ok1 := m[1].(string)
		k2, ok2 := m[2].(string)
		k3, ok3 := m[3].(string)
		if !ok0 || !ok1 || !ok2 || !ok3 {
			out = append(out, fmt.Sprintf("[malformed pin element: %v]", e))
			continue
		}
		out = append(out, fmt.Sprintf("[%s %s %s %s]", k0, k1, k2, k3))
	}
	sort.Strings(out)
	return out
}

func stringSlicesEqual(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// jsonableFromExpected normalizes pin values the way Python normalize_bounds +
// jsonable_bounds do: integral floats become ints, then print as decimal digits.
// fmt's %v on a float64 switches to exponent notation at 1e6+, which made every
// large-budget pin a false mismatch (V2 M6).
func jsonableFromExpected(b map[string]any) map[string]any {
	out := map[string]any{}
	for k, v := range b {
		if k == "max_cost" {
			if cm, ok := v.(map[string]any); ok {
				out[k] = map[string]any{"amount": fmtAmount(cm["amount"]), "unit": cm["unit"]}
			}
		} else {
			out[k] = fmtAmount(v)
		}
	}
	return out
}

// fmtAmount mirrors Python dec()=int() for numeric pins. Beyond int64 the
// oracle prints the exact integer while int64() would saturate or wrap —
// fall back to %v like fmtNum does (V20 M-3). A BOOL pin is an opposite-verdict
// forced divergence: int(False)=0 lets the oracle match a zero amount; the Go
// runner renders "false" and fails — strict side wins, ledgered with the
// pin-runner equality-semantics family.
func fmtAmount(v any) string {
	switch t := v.(type) {
	case float64:
		if t >= 9223372036854775808.0 || t <= -9223372036854775808.0 {
			return fmt.Sprintf("%v", t)
		}
		return fmt.Sprintf("%d", int64(t))
	case int64:
		return fmt.Sprintf("%d", t)
	case int:
		return fmt.Sprintf("%d", t)
	}
	return fmt.Sprintf("%v", v)
}
