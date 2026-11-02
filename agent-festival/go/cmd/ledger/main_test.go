package main

import (
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/suite"
)

// TestLedgerSuiteGreenAndCounted pins the driver's verdict AND the corpus
// size (D93 count-floor: shrinking the corpus must redden this test in the
// same commit that shrinks it — the discipline 4b04cea missed and 4e52a20
// had to repay).
func TestLedgerSuiteGreenAndCounted(t *testing.T) {
	buf := suite.Capture(func() { run() })
	if !strings.Contains(buf, "[ledger] 10 must-accept + 26 must-reject, 0 failures") {
		t.Fatalf("ledger summary line wrong (corpus count changed or suite red):\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("suite not green:\n%s", buf)
	}
}

// TestManifestCheckGate wires the machine-generated manifest block's --check
// gate into go test ./... (R3 M4: the gate existed but nothing ran it, so the
// M2 accident form — corpus change without a re-render — could silently
// recur; every other mechanical gate in this repo lives in go test by D93
// house convention). The generator resolves schema/examples relative to its
// cwd, so the subprocess runs from the repo root.
func TestManifestCheckGate(t *testing.T) {
	root, err := filepath.Abs(filepath.Join("..", "..", ".."))
	if err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command("python3", "tools/corpus_manifest.py", "--check")
	cmd.Dir = root
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("manifest --check gate red (err=%v):\n%s", err, out)
	}
}
