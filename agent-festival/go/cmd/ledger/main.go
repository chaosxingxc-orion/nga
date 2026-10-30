// ledger runs the event-ledger fixture suite (piece 4, Go side of the oracle).
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"festival-dev/go/internal/ledger"
)

func main() {
	dir := ledger.SchemaPath
	if dir == "" {
		fmt.Println("[ledger] schema not found")
		os.Exit(1)
	}
	base := filepath.Join(filepath.Dir(dir), "examples", "ledger")
	valid := glob(filepath.Join(base, "valid", "*.json"))
	invalid := glob(filepath.Join(base, "invalid", "*.json"))
	sort.Strings(valid)
	sort.Strings(invalid)
	if len(valid) == 0 || len(invalid) == 0 {
		fmt.Println("[ledger] suite incomplete: need at least one valid and one invalid example")
		os.Exit(1)
	}
	bad := 0
	for _, f := range valid {
		fx, err := ledger.LoadFixture(f)
		if err != nil || fx.ParseError != "" {
			fmt.Printf("[ledger] FAIL must-accept %s  (load error)\n", filepath.Base(f))
			bad++
			continue
		}
		errs := ledger.Errors(fx.Doc)
		if len(errs) == 0 {
			fmt.Printf("[ledger] PASS must-accept %s\n", filepath.Base(f))
		} else {
			fmt.Printf("[ledger] FAIL must-accept %s\n", filepath.Base(f))
			for _, e := range errs {
				fmt.Printf("      %s\n", e)
			}
			bad++
		}
	}
	for _, f := range invalid {
		fx, err := ledger.LoadFixture(f)
		if err != nil || fx.ParseError != "" {
			fmt.Printf("[ledger] FAIL must-reject %s  (load error)\n", filepath.Base(f))
			bad++
			continue
		}
		errs := ledger.Errors(fx.Doc)
		base := filepath.Base(f)
		if len(errs) == 0 {
			fmt.Printf("[ledger] FAIL must-reject %s  (was accepted!)\n", base)
			bad++
		} else if fx.ExpectMatch != "" && !containsAny(errs, fx.ExpectMatch) {
			fmt.Printf("[ledger] FAIL must-reject %s  (rejected for the wrong reason: %q lacks %q)\n", base, errs[0], fx.ExpectMatch)
			bad++
		} else {
			fmt.Printf("[ledger] PASS must-reject %s  (%s)\n", base, firstLine(errs[0]))
		}
	}
	fmt.Printf("[ledger] %d must-accept + %d must-reject, %d failures\n", len(valid), len(invalid), bad)
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
