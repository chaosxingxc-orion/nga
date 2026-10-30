// adopt runs the adoption-request fixture suite (piece 2, Go side of the
// oracle): every examples/adoption/valid/* must be accepted by
// adoption.schema.json, every invalid/* rejected for the reason its
// _expect_match names. The suite discipline lives in internal/suite; the
// state-machine semantics (the 14-A5 counterexamples, concurrency, crash
// recovery) are owned by internal/adopt's tests, not re-run here.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"festival-dev/go/internal/adopt"
	"festival-dev/go/internal/suite"
)

func main() {
	os.Exit(run())
}

func run() int {
	if adopt.SchemaPath == "" {
		fmt.Println("[adoption] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(adopt.SchemaPath), "examples", "adoption")
	bad := suite.Run("adoption", filepath.Join(base, "valid"), filepath.Join(base, "invalid"), adopt.CheckRequest)
	if bad == 0 {
		return 0
	}
	return 1
}
