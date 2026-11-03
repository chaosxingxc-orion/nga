// evidlog runs the evidence-log fixture suite (piece 7 spike, Go side).
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/openjiuwen/agent-festival/go/internal/evidlog"
	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

func main() { os.Exit(run()) }

func run() int {
	if evidlog.SchemaPath == "" {
		fmt.Println("[evidlog] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(evidlog.SchemaPath), "examples", "evidlog")
	bad := suite.Run("evidlog", filepath.Join(base, "valid"), filepath.Join(base, "invalid"), evidlog.CheckDoc)
	if bad == 0 {
		return 0
	}
	return 1
}
