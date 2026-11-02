package main

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

// TestEvidlogSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor; the Python twin lives in schema/evidlog.py — R13
// A-m4: this was the one family pair missing the cross-reference).
func TestEvidlogSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[evidlog] 2 must-accept + 5 must-reject, 0 failures") {
		t.Fatalf("evidlog summary wrong:\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("not green:\n%s", buf)
	}
}
