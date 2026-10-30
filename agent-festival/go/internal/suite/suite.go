// Package suite runs the fixture-suite discipline shared by the growth-layer
// drivers (cmd/ledger, cmd/adopt, and the pieces still to come): valid
// examples must be accepted, invalid examples must be rejected — and, when
// an invalid example pins a reason via _expect_match, rejected for that
// reason. Pin loading follows the frozen base's hardened semantics: a
// wrong-typed _expect_match fails LOUD (a silent downgrade to "no pin" would
// bypass the wrong-reason checks, V28 F-1), and a fixture whose JSON failed
// to parse counts as rejected-at-parse with its pin still matchable (V32
// M-1's two-path split: an unreadable pin must not mask the verdict).
//
// R1 M-5/m-6: the ledger and adoption drivers had each carried a naive
// 104-line copy of this logic with the base's hardening stripped out — the
// suite discipline itself had forked three ways. This package is the growth
// layer's single source for it; the frozen base (cmd/validate) keeps its own
// copy untouched.
package suite

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// Fixture is a loaded fixture document with its pins popped.
type Fixture struct {
	Doc         map[string]any
	ExpectMatch string
	ParseError  string
}

// Load reads a fixture and pops its _expect* pins. A document whose JSON
// does not parse yields Doc == nil with ParseError set (the
// rejected-at-parse path — the driver may still match its pin against the
// parse error). A document that parses but carries a wrong-typed
// _expect_match yields Doc != nil with ParseError set (the loud
// pin-authoring failure — the driver must FAIL, not silently run unpinned).
func Load(path string) (*Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	f := &Fixture{}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		f.ParseError = "document rejected at parse: " + err.Error()
		return f, nil
	}
	delete(doc, "_expect") // descriptive only
	if m, has := doc["_expect_match"]; has {
		if s, isStr := m.(string); isStr {
			f.ExpectMatch = s
		} else {
			f.ParseError = fmt.Sprintf("_expect_match must be a string, got %T", m)
		}
	}
	delete(doc, "_expect_match")
	f.Doc = doc
	return f, nil
}

// Checker validates one popped fixture document; nil/empty = accepted.
type Checker func(doc map[string]any) []string

// Run executes the two-phase suite over the example directories and returns
// the failure count (0 = green). It prints one line per fixture plus the
// summary; the caller maps failures to the exit code. An empty phase fails
// the suite: a corpus that lost its valid or its invalid half must not pass
// silently.
func Run(label, validDir, invalidDir string, check Checker) int {
	valid := glob(filepath.Join(validDir, "*.json"))
	invalid := glob(filepath.Join(invalidDir, "*.json"))
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Printf("[%s] suite incomplete: need at least one valid and one invalid example\n", label)
		return 1
	}
	bad := 0
	for _, f := range valid {
		fx, err := Load(f)
		name := filepath.Base(f)
		if err != nil || (fx.ParseError != "" && fx.Doc == nil) {
			fmt.Printf("[%s] FAIL must-accept %s  (load error: %v)\n", label, name, errOrParse(fx, err))
			bad++
			continue
		}
		if fx.ParseError != "" {
			// the document parsed but its pin is malformed — an authoring error
			fmt.Printf("[%s] FAIL must-accept %s  (%s)\n", label, name, firstLine(fx.ParseError))
			bad++
			continue
		}
		errs := check(fx.Doc)
		if len(errs) == 0 {
			fmt.Printf("[%s] PASS must-accept %s\n", label, name)
		} else {
			fmt.Printf("[%s] FAIL must-accept %s\n", label, name)
			for _, e := range errs {
				fmt.Printf("      %s\n", e)
			}
			bad++
		}
	}
	for _, f := range invalid {
		fx, err := Load(f)
		name := filepath.Base(f)
		if err != nil {
			fmt.Printf("[%s] FAIL must-reject %s  (unreadable: %v)\n", label, name, err)
			bad++
			continue
		}
		if fx.ParseError != "" && fx.Doc != nil {
			// the DOCUMENT parsed; the error is a malformed pin. An unreadable
			// pin cannot verify the rejection and must not MASK the
			// was-accepted verdict (V32 M-1).
			fmt.Printf("[%s] FAIL must-reject %s  (%s — an unreadable pin cannot verify the rejection)\n", label, name, firstLine(fx.ParseError))
			bad++
			continue
		}
		var errs []string
		if fx.ParseError != "" {
			errs = []string{fx.ParseError}
		} else {
			errs = check(fx.Doc)
		}
		if len(errs) == 0 {
			fmt.Printf("[%s] FAIL must-reject %s  (was accepted!)\n", label, name)
			bad++
		} else if fx.ExpectMatch != "" && !anyContains(errs, fx.ExpectMatch) {
			fmt.Printf("[%s] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", label, name, errs[0], fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[%s] PASS must-reject %s  (%s)\n", label, name, firstLine(errs[0]))
		}
	}
	fmt.Printf("[%s] %d must-accept + %d must-reject, %d failures\n", label, len(valid), len(invalid), bad)
	if bad == 0 {
		fmt.Println("ALL GREEN")
	}
	return bad
}

func glob(pattern string) []string {
	files, _ := filepath.Glob(pattern)
	sort.Strings(files)
	return files
}

func errOrParse(fx *Fixture, err error) string {
	if err != nil {
		return err.Error()
	}
	return fx.ParseError
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
