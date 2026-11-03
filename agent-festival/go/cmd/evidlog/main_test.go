package main

import (
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

func TestEvidlogSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[evidlog] 1 must-accept + 3 must-reject, 0 failures") {
		t.Fatalf("evidlog summary wrong:\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("not green:\n%s", buf)
	}
}
