package main

import (
	"strings"
	"testing"

	"festival-dev/go/internal/suite"
)

// TestJudgmentSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, the Python twin lives in judgment.py's main).
func TestJudgmentSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[judgment] 2 must-accept + 19 must-reject, 0 failures") {
		t.Fatalf("judgment summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}
