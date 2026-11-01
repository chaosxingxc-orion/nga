// ledger runs the event-ledger fixture suite (piece 4, Go side of the
// oracle). The suite discipline (must-accept / must-reject with wrong-reason
// pins, loud pin failures, two-path parse errors) is internal/suite — this
// driver only binds it to the ledger checker and directories.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/openjiuwen/agent-festival/go/internal/ledger"
	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

func main() {
	os.Exit(run())
}

func run() int {
	if ledger.SchemaPath == "" {
		fmt.Println("[ledger] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(ledger.SchemaPath), "examples", "ledger")
	bad := suite.Run("ledger", filepath.Join(base, "valid"), filepath.Join(base, "invalid"), ledger.Errors)
	if bad == 0 {
		return 0
	}
	return 1
}
