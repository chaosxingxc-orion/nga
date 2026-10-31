package main

import (
	"strings"
	"testing"

	"festival-dev/go/internal/suite"
)

// TestReplaySuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, the Python twin lives in replay.py's main).
func TestReplaySuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[replay] 8 must-accept + 6 must-reject, 0 failures") {
		t.Fatalf("replay summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}
