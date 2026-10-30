package main

import (
	"io"
	"os"
	"strings"
	"testing"
)

// TestAdoptionSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor, same rationale as cmd/ledger's).
func TestAdoptionSuiteGreenAndCounted(t *testing.T) {
	buf := capture(t, run)
	if !strings.Contains(buf, "[adoption] 2 must-accept + 5 must-reject, 0 failures") {
		t.Fatalf("adoption summary line wrong (corpus shrank or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}

// capture runs f with stdout captured and returns the text.
func capture(t *testing.T, f func() int) string {
	t.Helper()
	old := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stdout = w
	f()
	w.Close()
	os.Stdout = old
	all, err := io.ReadAll(r)
	if err != nil {
		t.Fatal(err)
	}
	return string(all)
}
