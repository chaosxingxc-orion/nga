// release runs the release-manifest fixture suite (piece 5, Go side of the
// oracle): every examples/release/valid/* must be accepted by
// release.schema.json, every invalid/* rejected for the reason its
// _expect_match names. The suite discipline lives in internal/suite.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"festival-dev/go/internal/release"
	"festival-dev/go/internal/suite"
)

func main() {
	os.Exit(run())
}

func run() int {
	if release.SchemaPath == "" {
		fmt.Println("[release] schema not found")
		return 1
	}
	base := filepath.Join(filepath.Dir(release.SchemaPath), "examples", "release")
	bad := suite.Run("release", filepath.Join(base, "valid"), filepath.Join(base, "invalid"), release.CheckManifest)
	if bad == 0 {
		return 0
	}
	return 1
}
