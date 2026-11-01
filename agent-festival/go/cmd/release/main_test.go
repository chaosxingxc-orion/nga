package main

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

// TestReleaseSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, the Python twin lives in release.py's main).
func TestReleaseSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[release] 3 must-accept + 14 must-reject, 0 failures") {
		t.Fatalf("release summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}
