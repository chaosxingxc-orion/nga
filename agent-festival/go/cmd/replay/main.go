// replay runs the replay-case fixture suite (piece 6, Go side of the oracle):
// every examples/replay/valid/* must recompute to its pinned double verdict
// (fidelity × conformance — all four quadrants are pinned), every invalid/*
// must be rejected for the reason its _expect_match names. The suite
// discipline lives in internal/suite.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"festival-dev/go/internal/replay"
	"festival-dev/go/internal/suite"
)

func main() { os.Exit(run()) }

func run() int {
	if replay.SchemaPath == "" {
		fmt.Println("[replay] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(replay.SchemaPath), "examples", "replay")
	bad := suite.Run("replay",
		filepath.Join(base, "valid"), filepath.Join(base, "invalid"),
		func(doc map[string]any) []string {
			var c replay.Case
			raw, _ := json.Marshal(doc)
			if err := json.Unmarshal(raw, &c); err != nil {
				return []string{"case decode failed: " + err.Error()}
			}
			return caseVerdictErrors(&c)
		})
	if bad == 0 {
		return 0
	}
	return 1
}

// caseVerdictErrors recomputes a case and compares against its pinned
// expected verdicts — a mismatch is a fixture failure (wrong-reason pins
// ride _expect_match on the schema layer for invalid cases).
func caseVerdictErrors(c *replay.Case) []string {
	rep, err := replay.Replay(c)
	if err != nil {
		return []string{err.Error()}
	}
	var errs []string
	if string(rep.Fidelity) != c.Expected.Fidelity {
		errs = append(errs, fmt.Sprintf("fidelity: recomputed %q, expected %q (%s)", rep.Fidelity, c.Expected.Fidelity, rep.Detail))
	}
	if string(rep.Conformance) != c.Expected.Conformance {
		errs = append(errs, fmt.Sprintf("conformance: recomputed %q, expected %q", rep.Conformance, c.Expected.Conformance))
	}
	if c.Expected.DivergenceAt != nil && rep.DivergenceAt != *c.Expected.DivergenceAt {
		errs = append(errs, fmt.Sprintf("divergence_at: located %d, expected %d", rep.DivergenceAt, *c.Expected.DivergenceAt))
	}
	return errs
}
