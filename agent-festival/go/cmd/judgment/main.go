// judgment runs the judgment-specification fixture suite (piece 3, Go side
// of the oracle): every examples/judgment/valid/* must be accepted by
// judgment.schema.json, every invalid/* rejected for the reason its
// _expect_match names. The suite discipline lives in internal/suite.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"festival-dev/go/internal/judgment"
	"festival-dev/go/internal/suite"
)

func main() {
	os.Exit(run())
}

func run() int {
	if judgment.SchemaPath == "" {
		fmt.Println("[judgment] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(judgment.SchemaPath), "examples", "judgment")
	bad := suite.Run("judgment", filepath.Join(base, "valid"), filepath.Join(base, "invalid"), judgment.CheckSpec)
	if bad == 0 {
		return 0
	}
	return 1
}
