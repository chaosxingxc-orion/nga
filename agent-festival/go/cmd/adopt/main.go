// adopt runs the adoption-request fixture suite (piece 2, Go side of the
// oracle): every examples/adoption/valid/* must be accepted by
// adoption.schema.json, every invalid/* rejected for the reason its
// _expect_match names. The state-machine semantics (the 14-A5
// counterexamples, concurrency, crash recovery) are owned by
// internal/adopt's tests, not re-run here.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"festival-dev/go/internal/adopt"
)

func main() {
	if adopt.SchemaPath == "" {
		fmt.Println("[adoption] schema not found")
		os.Exit(1)
	}
	base := filepath.Join(filepath.Dir(adopt.SchemaPath), "examples", "adoption")
	valid := glob(filepath.Join(base, "valid", "*.json"))
	invalid := glob(filepath.Join(base, "invalid", "*.json"))
	sort.Strings(valid)
	sort.Strings(invalid)
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Println("[adoption] suite incomplete: need at least one valid and one invalid example")
		os.Exit(1)
	}
	bad := 0
	for _, f := range valid {
		fx, err := adopt.LoadFixture(f)
		if err != nil || fx.ParseError != "" {
			fmt.Printf("[adoption] FAIL must-accept %s  (load error)\n", filepath.Base(f))
			bad++
			continue
		}
		errs := adopt.CheckRequest(fx.Doc)
		if len(errs) == 0 {
			fmt.Printf("[adoption] PASS must-accept %s\n", filepath.Base(f))
		} else {
			fmt.Printf("[adoption] FAIL must-accept %s\n", filepath.Base(f))
			for _, e := range errs {
				fmt.Printf("      %s\n", e)
			}
			bad++
		}
	}
	for _, f := range invalid {
		fx, err := adopt.LoadFixture(f)
		if err != nil || fx.ParseError != "" {
			fmt.Printf("[adoption] FAIL must-reject %s  (load error)\n", filepath.Base(f))
			bad++
			continue
		}
		errs := adopt.CheckRequest(fx.Doc)
		name := filepath.Base(f)
		if len(errs) == 0 {
			fmt.Printf("[adoption] FAIL must-reject %s  (was accepted!)\n", name)
			bad++
		} else if fx.ExpectMatch != "" && !containsAny(errs, fx.ExpectMatch) {
			fmt.Printf("[adoption] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", name, errs[0], fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[adoption] PASS must-reject %s  (%s)\n", name, firstLine(errs[0]))
		}
	}
	fmt.Printf("[adoption] %d must-accept + %d must-reject, %d failures\n", len(valid), len(invalid), bad)
	if bad == 0 {
		fmt.Println("ALL GREEN")
	}
	os.Exit(boolExit(bad == 0))
}

func glob(pattern string) []string {
	files, _ := filepath.Glob(pattern)
	return files
}

func containsAny(errs []string, substr string) bool {
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
