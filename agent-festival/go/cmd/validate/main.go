// validate is the Go successor of schema/validate.py (frozen oracle).
// Runs the four example suites: contract, envelope, keystore, guards.
package main

import (
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"festival-dev/go/internal/validate"
)

func runSuite(name string, check func(*validate.Fixture) []string) int {
	validDir := filepath.Join(validate.ExamplesDir, "valid")
	invalidDir := filepath.Join(validate.ExamplesDir, "invalid")
	valid, _ := filepath.Glob(filepath.Join(validDir, "*.json"))
	invalid, _ := filepath.Glob(filepath.Join(invalidDir, "*.json"))
	sort.Strings(valid)
	sort.Strings(invalid)
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Printf("[%s] suite incomplete: need at least one valid and one invalid example\n", name)
		return 1
	}
	bad := 0
	for _, f := range valid {
		fx, err := validate.LoadFixture(f)
		if err != nil {
			fmt.Printf("[%s] FAIL must-accept %s (%v)\n", name, filepath.Base(f), err)
			bad++
			continue
		}
		var errs []string
		if fx.ParseError != "" {
			errs = []string{fx.ParseError}
		} else {
			errs = check(fx)
		}
		// a pin on a contract-suite fixture is an authoring error — the oracle
		// crashes on it (verified=None called); we FAIL loudly instead (V25
		// claim, landed V30 after the sweep found it missing — V30 F-3)
		if len(errs) == 0 && fx.Pin != nil {
			errs = append(errs, fmt.Sprintf("contract fixture carries a pin %v — pins belong to envelope/compose suites", fx.Pin))
		}
		status := "PASS"
		if len(errs) > 0 {
			status = "FAIL"
			bad++
		}
		fmt.Printf("[%s] %s must-accept %s\n", name, status, filepath.Base(f))
		for _, e := range errs {
			fmt.Printf("      %s\n", e)
		}
	}
	for _, f := range invalid {
		fx, err := validate.LoadFixture(f)
		if err != nil {
			fmt.Printf("[%s] FAIL must-reject %s  (unreadable: %v)\n", name, filepath.Base(f), err)
			bad++
			continue
		}
		if fx.ParseError != "" && fx.Doc != nil {
			// the DOCUMENT parsed; the error is a malformed pin. An unreadable
			// pin cannot verify the rejection and must not MASK the
			// was-accepted verdict (V32 M-1: a regressed-to-valid fixture with
			// a wrong-typed pin used to PASS here while the oracle FAILs).
			fmt.Printf("[%s] FAIL must-reject %s  (%s — an unreadable pin cannot verify the rejection)\n", name, filepath.Base(f), firstLine(fx.ParseError))
			bad++
			continue
		}
		var errs []string
		if fx.ParseError != "" {
			errs = []string{fx.ParseError}
		} else {
			errs = check(fx)
		}
		base := filepath.Base(f)
		if len(errs) == 0 {
			fmt.Printf("[%s] FAIL must-reject %s  (was accepted!)\n", name, base)
			bad++
		} else if fx.ExpectMatch != "" && !anyContains(errs, fx.ExpectMatch) {
			fmt.Printf("[%s] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", name, base, errs[0], fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[%s] PASS must-reject %s  (%s)\n", name, base, firstLine(errs[0]))
		}
	}
	fmt.Printf("[%s] %d must-accept + %d must-reject, %d failures\n\n", name, len(valid), len(invalid), bad)
	return bad
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

func listEqual(a, b any) bool {
	// verified kids arrive as []string, pins as []any; a non-list on either
	// side is a type mismatch exactly like Python's list != — value-text
	// rendering collapsed "5" and 5 (V19 4-lens M-1 family)
	var as []any
	switch x := a.(type) {
	case []string:
		as = make([]any, len(x))
		for i, s := range x {
			as[i] = s
		}
	case []any:
		as = x
	default:
		return false
	}
	bs, bok := b.([]any)
	if !bok || len(as) != len(bs) {
		return false
	}
	for i := range as {
		// kids pins are strings; a numeric kid pin must FAIL, not text-match
		s, isStr := as[i].(string)
		if !isStr || bs[i] != any(s) {
			return false
		}
	}
	return true
}

func main() { os.Exit(run()) }

// run is the full CLI decision chain as a testable function (V23 S1): the
// aggregation points — suite loops, guards, the total, the exit code — are
// production decision paths; pinning only their projections left the
// print-and-vanish class alive in this file.
func run() int {
	// contract suite — trust-store failure is a load error: exit code 2,
	// matching the oracle's main() (V25 4-lens F1; the old os.Exit(1) inside
	// run() killed the process, making the "testable decision chain" claim
	// false on this branch)
	ts, tsErr := mustTrustStore()
	if tsErr != nil {
		fmt.Println("trust store:", tsErr)
		return 2
	}
	total := 0
	total += runSuite("contract", func(fx *validate.Fixture) []string {
		return validate.ContractErrors(fx.Doc)
	})

	// envelope suite (valid + invalid subdirs under examples/envelopes)
	total += envelopeSuite(ts)

	// keystore suite: examples/keys/invalid/*.jwks.json must fail at load
	total += keystoreSuite()

	// guards suite: programmatic must-rejects JSON fixtures cannot express
	total += guardSuite()

	fmt.Println(allGreen(total))
	return boolExit(total == 0)
}

func allGreen(n int) string {
	if n == 0 {
		return "ALL GREEN"
	}
	return fmt.Sprintf("%d FAILURES", n)
}

func boolExit(b bool) int {
	if b {
		return 0
	}
	return 1
}

func mustTrustStore() (*validate.TrustStore, error) {
	return validate.LoadTrustStore(filepath.Join(validate.ExamplesDir, "keys", "trusted.jwks.json"))
}

// guard is one programmatic guard case (hoisted to package level so
// bothPinsCase can construct one — V27 m-2 seam).
type guard struct {
	label string
	errs  []string
	match string
}

// bothPinsCase builds the both-pins guard case from a fixture path —
// extracted so the premise-failure path (fixture without both pins) is
// testable: a nil error slice can never match, so the guard fails
// structurally (V26 4-lens m-3 / V27 m-2).
func bothPinsCase(path string) guard {
	fx, err := validate.LoadFixture(path)
	var bothErrs []string
	if err == nil && fx.ParseError != "" { // fx is non-nil whenever err is nil
		bothErrs = []string{fx.ParseError}
	}
	return guard{"fixture with both _expect_verified_kids and _expect_composed", bothErrs, "carries both"}
}

func envelopeSuite(ts *validate.TrustStore) int {
	validDir := filepath.Join(validate.ExamplesDir, "envelopes", "valid")
	invalidDir := filepath.Join(validate.ExamplesDir, "envelopes", "invalid")
	valid, _ := filepath.Glob(filepath.Join(validDir, "*.json"))
	invalid, _ := filepath.Glob(filepath.Join(invalidDir, "*.json"))
	sort.Strings(valid)
	sort.Strings(invalid)
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Println("[envelope] suite incomplete: need at least one valid and one invalid example")
		return 1
	}
	bad := 0
	for _, f := range valid {
		fx, err := validate.LoadFixture(f)
		if err != nil {
			fmt.Printf("[envelope] FAIL must-accept %s (%v)\n", filepath.Base(f), err)
			bad++
			continue
		}
		var errs, verified []string
		if fx.ParseError != "" {
			errs = []string{fx.ParseError}
		} else {
			errs, verified = validate.EnvelopeErrors(fx.Doc, ts, fx.LoneSurrogate)
		}
		if len(errs) == 0 && fx.Pin != nil {
			if _, isList := fx.Pin.([]any); !isList {
				// a non-kids-shaped pin on an envelope fixture is an authoring
				// error — same message family as the contract suite (V30 m-2)
				errs = append(errs, fmt.Sprintf("envelope fixture carries a non-kids pin %v — kids pins are a list", fx.Pin))
			} else if !listEqual(verified, fx.Pin) {
				errs = append(errs, fmt.Sprintf("verified kids %v != expected %v", verified, fx.Pin))
			}
		}
		status := "PASS"
		if len(errs) > 0 {
			status = "FAIL"
			bad++
		}
		fmt.Printf("[envelope] %s must-accept %s\n", status, filepath.Base(f))
		for _, e := range errs {
			fmt.Printf("      %s\n", e)
		}
	}
	for _, f := range invalid {
		fx, err := validate.LoadFixture(f)
		if err != nil {
			fmt.Printf("[envelope] FAIL must-reject %s  (unreadable: %v)\n", filepath.Base(f), err)
			bad++
			continue
		}
		if fx.ParseError != "" && fx.Doc != nil {
			// malformed pin: must not mask the was-accepted verdict (V32 M-1)
			fmt.Printf("[envelope] FAIL must-reject %s  (%s — an unreadable pin cannot verify the rejection)\n", filepath.Base(f), firstLine(fx.ParseError))
			bad++
			continue
		}
		var errs []string
		if fx.ParseError != "" {
			errs = []string{fx.ParseError}
		} else {
			errs, _ = validate.EnvelopeErrors(fx.Doc, ts, fx.LoneSurrogate)
		}
		base := filepath.Base(f)
		if len(errs) == 0 {
			fmt.Printf("[envelope] FAIL must-reject %s  (was accepted!)\n", base)
			bad++
		} else if fx.ExpectMatch != "" && !anyContains(errs, fx.ExpectMatch) {
			fmt.Printf("[envelope] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", base, errs[0], fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[envelope] PASS must-reject %s  (%s)\n", base, firstLine(errs[0]))
		}
	}
	fmt.Printf("[envelope] %d must-accept + %d must-reject, %d failures\n\n", len(valid), len(invalid), bad)
	return bad
}

func keystoreSuite() int {
	invalid, _ := filepath.Glob(filepath.Join(validate.ExamplesDir, "keys", "invalid", "*.jwks.json"))
	sort.Strings(invalid)
	if len(invalid) == 0 {
		fmt.Println("[keystore] suite incomplete: need at least one must-reject key store")
		return 1
	}
	bad := 0
	for _, f := range invalid {
		fx, ferr := validate.LoadFixture(f)
		if ferr != nil {
			fmt.Printf("[keystore] FAIL must-reject %s  (unreadable: %v)\n", filepath.Base(f), ferr)
			bad++
			continue
		}
		if fx.ParseError != "" {
			// the store file PARSED (jwks are JSON); a ParseError here is a
			// malformed pin, which must FAIL — the old PASS branch skipped the
			// LoadTrustStore body entirely, masking a regressed-to-loadable
			// store behind the pin error (V29 F-1 landed the propagation, V32
			// M-1 flips its direction: the oracle FAILs "was accepted" here)
			fmt.Printf("[keystore] FAIL must-reject %s  (%s — an unreadable pin cannot verify the rejection)\n", filepath.Base(f), firstLine(fx.ParseError))
			bad++
			continue
		}
		// a pin on a keystore fixture is an authoring error — same rule as the
		// contract suite, the sibling the V30 pin-loud sweep missed (V30 m-2)
		if fx.Pin != nil {
			fmt.Printf("[keystore] FAIL must-reject %s  (keystore fixture carries a pin %v — pins belong to envelope/compose suites)\n", filepath.Base(f), fx.Pin)
			bad++
			continue
		}
		_, err := validate.LoadTrustStore(f)
		base := filepath.Base(f)
		if err == nil {
			fmt.Printf("[keystore] FAIL must-reject %s  (was accepted!)\n", base)
			bad++
		} else if fx.ExpectMatch != "" && !strings.Contains(err.Error(), fx.ExpectMatch) { // fx non-nil here
			fmt.Printf("[keystore] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", base, err.Error(), fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[keystore] PASS must-reject %s  (%s)\n", base, firstLine(err.Error()))
		}
	}
	fmt.Printf("[keystore] %d must-reject, %d failures\n\n", len(invalid), bad)
	return bad
}

// guardSuite ports Python run_guard_suite: rejections only a programmatic caller
// can reach. A dict built in code can carry float NaN / Inf, which JSON fixtures
// cannot express (the parser refuses them first); without these the value-layer
// guards would be GREEN under mutation (round 16 fourth pass, V2 m1).
func guardSuite() int {
	base, err := validate.LoadFixture(filepath.Join(validate.ExamplesDir, "valid", "doc-extractor.json"))
	if err != nil {
		fmt.Println("[guards] FAIL cannot load base fixture:", err)
		return 1
	}
	if _, ok := base.Doc["bounds"].(map[string]any); !ok {
		fmt.Println("[guards] FAIL base fixture has no bounds map")
		return 1
	}
	// deep copy so each case starts from the pristine document
	clone := func() map[string]any { return validate.CloneDoc(base.Doc) } // single source (V23 4-lens n3)
	var cases []guard
	for _, c := range []struct {
		name  string
		value any
	}{
		{"max_cost", map[string]any{"amount": math.NaN(), "unit": "USD"}},
		{"max_seconds", math.Inf(1)},
		{"max_seconds", math.NaN()},
	} {
		doc := clone()
		bounds, _ := doc["bounds"].(map[string]any)
		bounds[c.name] = c.value
		cases = append(cases, guard{fmt.Sprintf("contract bounds.%s=%v", c.name, c.value), validate.ContractErrors(doc), "not of type 'integer'"})
	}
	// a fixture carrying both pins is an authoring error that must surface (fifth pass)
	both := filepath.Join(os.TempDir(), fmt.Sprintf("both-pins-%d.tmp.json", os.Getpid())) // unique: concurrent runs cannot clobber each other
	_ = os.WriteFile(both, []byte(`{"_expect_verified_kids": [], "_expect_composed": {}}`), 0o644)
	cases = append(cases, bothPinsCase(both))
	_ = os.Remove(both)

	bad := 0
	for _, c := range cases {
		ok := len(c.errs) > 0 && anyContains(c.errs, c.match)
		status := "PASS"
		if !ok {
			status = "FAIL"
			bad++
		}
		fmt.Printf("[guards] %s must-reject %s", status, c.label)
		if !ok {
			fmt.Printf("  (errors: %v)", c.errs)
		}
		fmt.Println()
	}
	fmt.Printf("[guards] %d programmatic must-reject, %d failures\n\n", len(cases), bad)
	return bad
}
