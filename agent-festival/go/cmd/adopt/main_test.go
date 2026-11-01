package main

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

// TestAdoptionSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, same rationale as cmd/ledger's).
func TestAdoptionSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[adoption] 2 must-accept + 5 must-reject, 0 failures") {
		t.Fatalf("adoption summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}
