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
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// expectMatchRe pulls a string _expect_match out of raw fixture bytes whose
// JSON does not parse (the base's discipline).
var expectMatchRe = regexp.MustCompile(`"_expect_match"\s*:\s*"([^"]*)"`)

// Fixture is a loaded fixture document with its pins popped. The shared
// discipline owns the common pins; piece-specific extras (compose's
// _expect_composed) travel through the loader closure instead (R20 B-3:
// the Extra field was born-dead — zero consumers, the Go compose checker
// pins via WithLoader's captured map).
type Fixture struct {
	Doc         map[string]any
	ExpectMatch string
	ParseError  string
}

// Load reads a fixture and pops its _expect* pins. A document whose JSON
// does not parse yields Doc == nil with ParseError set; its pin, if the raw
// bytes carry one, is still extracted so the wrong-reason check stays armed
// against the parse error (the rejected-at-parse path). A document that
// parses but carries a wrong-typed _expect_match yields Doc != nil with
// ParseError set (the loud pin-authoring failure — the driver must FAIL,
// not silently run unpinned).
func Load(path string) (*Fixture, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	f := &Fixture{}
	var doc map[string]any
	// UseNumber: integers survive the map domain exactly — float64 rounding
	// is monotonic, so DECREASING pairs are still caught after folding; what
	// a float64 map breaks is the other direction, silently rejecting LEGAL
	// consecutive seqs that cross 2^53 (pinned by the high-seq-across-2e53
	// fixture). santhosh accepts json.Number as a number, and the checkers'
	// typed re-parse is exact.
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&doc); err != nil {
		f.ParseError = "document rejected at parse: " + err.Error()
		// the pin, if any, is still extracted from the raw bytes — a
		// parse-failed fixture's wrong-reason check must stay armed (the
		// base's expectMatchRe discipline; R3 M-3 found this promised in
		// the comment but never implemented, silently disarming the pin)
		if m := expectMatchRe.FindSubmatch(raw); m != nil {
			f.ExpectMatch = string(m[1])
		}
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

// Option parameterizes Run for pieces whose fixtures need more than the
// shared discipline (compose: the base's rich loader + composed-output
// pins). The four default consumers are untouched.
type Option func(*config)

type config struct {
	loader func(path string) (*Fixture, error)
}

// WithLoader replaces the default Load (compose rides the frozen base's
// rich loader: bare-NaN scan, surrogate scoping, regex pin extraction).
func WithLoader(l func(path string) (*Fixture, error)) Option {
	return func(c *config) { c.loader = l }
}

// Run executes the two-phase suite over the example directories and returns
// the failure count (0 = green). It prints one line per fixture plus the
// summary; the caller maps failures to the exit code. An empty phase fails
// the suite: a corpus that lost its valid or its invalid half must not pass
// silently.
func Run(label, validDir, invalidDir string, check Checker, opts ...Option) int {
	cfg := &config{loader: Load}
	for _, opt := range opts {
		opt(cfg)
	}
	valid := glob(filepath.Join(validDir, "*.json"))
	invalid := glob(filepath.Join(invalidDir, "*.json"))
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Printf("[%s] suite incomplete: need at least one valid and one invalid example\n", label)
		return 1
	}
	bad := 0
	for _, f := range valid {
		fx, err := cfg.loader(f)
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
		fx, err := cfg.loader(f)
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

// Capture runs f with stdout captured and returns the captured text (one
// exported helper for the drivers' count-pin tests — R2 m-2: the local
// copies had reached three and growing). A reader goroutine drains the pipe
// while f runs — a synchronous read after f would deadlock once the output
// exceeds the pipe buffer — and the defer restores stdout even on panic.
func Capture(f func()) string {
	old := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		return ""
	}
	os.Stdout = w
	var buf []byte
	done := make(chan struct{})
	go func() {
		buf, _ = io.ReadAll(r)
		close(done)
	}()
	defer func() {
		os.Stdout = old
		w.Close()
	}()
	f()
	w.Close()
	<-done
	return string(buf)
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
