package main

import (
	"strings"
	"testing"

	"festival-dev/go/internal/suite"
)

// TestLedgerSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor: shrinking the corpus must redden this test in the
// same commit that shrinks it — the discipline 4b04cea missed and 4e52a20
// had to repay).
func TestLedgerSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[ledger] 9 must-accept + 26 must-reject, 0 failures") {
		t.Fatalf("ledger summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}
