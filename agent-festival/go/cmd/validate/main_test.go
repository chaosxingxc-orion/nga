package main

import (
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/validate"
)

// TestListEqualTypeStrict pins the kids-pin value-level comparison (V20 M-2):
// the old %v rendering collapsed "5" and 5 into the same text; verified kids
// are []string and a numeric kid pin must FAIL, not text-match.
func TestListEqualTypeStrict(t *testing.T) {
	cases := []struct {
		a, b any
		want bool
	}{
		{[]string{"k1", "k2"}, []any{"k1", "k2"}, true},
		{[]string{"k1"}, []any{5}, false},    // numeric pin must fail
		{[]string{"k1"}, []any{true}, false}, // bool pin must fail
		{[]string{"k1", "k2"}, []any{"k1"}, false},
		{[]string{"k1"}, "k1", false}, // non-list pin must fail
		{[]any{"k1"}, []any{"k1"}, true},
		// same-text/different-type (V21 F4): the ONLY shapes that distinguish a
		// type-strict comparison from a %v text comparison
		{[]string{"5"}, []any{5}, false},
		{[]string{"true"}, []any{true}, false},
		{[]string{"1e21"}, []any{1e21}, false},
	}
	for _, c := range cases {
		if got := listEqual(c.a, c.b); got != c.want {
			t.Fatalf("listEqual(%v, %v) = %v, want %v", c.a, c.b, got, c.want)
		}
	}
}

// TestRunExitCodePropagatesFailures pins the FULL decision chain (V23 S1):
// a poisoned must-accept fixture must reach the exit code through every
// aggregation point (suite loop → total → run()). This is the print-and-vanish
// class that survived four generations while main() was untestable.
func TestRunExitCodePropagatesFailures(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "envelopes", "valid", "doc-extractor.envelope.json")
	doc := readJSON(t, poison)
	doc["_expect_verified_kids"] = []any{"no-such-kid"}
	writeJSON(t, poison, doc)

	save := validate.ExamplesDir
	validate.ExamplesDir = dir
	defer func() { validate.ExamplesDir = save }()
	if rc := run(); rc == 0 {
		t.Fatal("run() returned 0 despite a poisoned envelope pin — failures do not reach the exit code")
	}
}

// captureStdout runs body with os.Stdout piped to a concurrent reader —
// read-after-close only deadlocks once the pipe buffer fills (V24 4-lens m2).
func captureStdout(t *testing.T, body func()) string {
	t.Helper()
	old := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	os.Stdout = w
	done := make(chan string, 1)
	go func() {
		buf, _ := io.ReadAll(r)
		done <- string(buf)
	}()
	defer r.Close() // the read end was never closed — fd leak per capture (V25 4-lens N1)
	body()
	w.Close()
	os.Stdout = old
	return <-done
}

// TestRunCleanTreeZero pins the positive direction: the untouched corpus
// aggregates to exit code 0, AND the guards section is actually wired into
// run() (its PASS lines must appear in the output — the exit code alone
// cannot see an unwired suite).
func TestRunCleanTreeZero(t *testing.T) {
	var rc int
	buf := captureStdout(t, func() { rc = run() })
	if rc != 0 {
		t.Fatalf("run() = %d on the clean tree, want 0", rc)
	}
	if !strings.Contains(buf, "[guards] PASS") {
		t.Fatal("run() produced no [guards] lines — guardSuite is unwired from the decision chain")
	}
}

func copyExamplesTree(t *testing.T) string {
	t.Helper()
	for _, root := range []string{"../../schema", "../../../schema"} {
		src := filepath.Join(root, "examples")
		if _, err := os.Stat(src); err != nil {
			continue
		}
		dst := t.TempDir()
		err := filepath.WalkDir(src, func(p string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			rel, _ := filepath.Rel(src, p)
			target := filepath.Join(dst, rel)
			if d.IsDir() {
				return os.MkdirAll(target, 0o755)
			}
			raw, err := os.ReadFile(p)
			if err != nil {
				return err
			}
			return os.WriteFile(target, raw, 0o644)
		})
		if err != nil {
			t.Fatal(err)
		}
		return dst
	}
	t.Fatal("examples tree not found")
	return ""
}

func readJSON(t *testing.T, p string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

func writeJSON(t *testing.T, p string, m map[string]any) {
	t.Helper()
	raw, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(p, raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

// The three suite-aggregation poisons (V24 F1): each suite's failure must
// reach run()'s return value — the envelopeSuite poison alone left the other
// three aggregation points swallowable with a single mutation.

func TestRunContractSuitePoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "valid", "doc-extractor.json")
	doc := readJSON(t, poison)
	delete(doc, "subject") // a must-accept that must now FAIL the contract suite
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite a poisoned valid contract — runSuite aggregation swallowed the failure")
		}
	})
}

func TestRunKeystoreSuitePoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "keys", "invalid", "duplicate-kid.jwks.json")
	doc := readJSON(t, poison)
	if keys, ok := doc["keys"].([]any); ok && len(keys) == 2 {
		doc["keys"] = []any{keys[0]} // de-duplicated: this must-reject store now LOADS
	}
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite a loadable must-reject keystore — keystoreSuite aggregation swallowed the failure")
		}
	})
}

// TestGuardSuitePropagatesFailures pins guardSuite's OWN aggregation: a
// missing base fixture must make guardSuite itself return non-zero. (A
// run()-level poison cannot isolate this suite — the guards' base fixture is
// shared with the contract suite, so any file-level poison trips both; the
// run()-level WIRING of guardSuite is pinned by TestRunCleanTreeZero's
// output assertion instead.)
func TestGuardSuitePropagatesFailures(t *testing.T) {
	dir := copyExamplesTree(t)
	if err := os.Remove(filepath.Join(dir, "valid", "doc-extractor.json")); err != nil {
		t.Fatal(err)
	}
	withExamplesDir(t, dir, func() {
		if rc := guardSuite(); rc == 0 {
			t.Fatal("guardSuite() = 0 despite being unable to load its base fixture — its aggregation swallowed the failure")
		}
	})
}

// TestValidateGuardsGreenAndFloored gives cmd/validate's guard battery the
// same governance compose has (V24 F4): zero failures AND a PASS-line floor.
func TestValidateGuardsGreenAndFloored(t *testing.T) {
	var rc int
	buf := captureStdout(t, func() { rc = guardSuite() })
	if rc != 0 {
		t.Fatalf("guardSuite() = %d on the clean tree, want 0", rc)
	}
	if n := strings.Count(buf, "[guards] PASS"); n < 4 {
		t.Fatalf("guards battery printed %d PASS lines (floor 4) — a guard evaporated", n)
	}
	if strings.Contains(buf, "[guards] FAIL") {
		t.Fatalf("guards battery has FAIL lines on the clean tree: %s", buf)
	}
}

func withExamplesDir(t *testing.T, dir string, body func()) {
	t.Helper()
	save := validate.ExamplesDir
	validate.ExamplesDir = dir
	defer func() { validate.ExamplesDir = save }()
	body()
}

// TestRunTrustStorePoison pins the trust-store load failure (V25 4-lens F1 /
// singularity F-2): a broken trusted.jwks.json must reach run()'s return
// value with the oracle's exit code 2 — the old os.Exit(1) killed the process
// inside run() instead.
func TestRunTrustStorePoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "keys", "trusted.jwks.json")
	doc := readJSON(t, poison)
	if keys, ok := doc["keys"].([]any); ok && len(keys) >= 2 {
		if k0, ok := keys[0].(map[string]any); ok {
			keys[1].(map[string]any)["kid"] = k0["kid"] // duplicate kid -> load failure
		}
	}
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		if rc := run(); rc != 2 {
			t.Fatalf("run() = %d on a broken trust store, want 2 (oracle exit-code parity)", rc)
		}
	})
}

// The three suite-incomplete pins (V25 4-lens F2 / singularity F-2): an empty
// corpus directory must fail its own suite's incomplete branch — the "silent
// empty batch" defense, previously pinned only on the compose side.

func TestRunContractIncomplete(t *testing.T) {
	dir := copyExamplesTree(t)
	// clear the INVALID side only: the guards' base fixture lives in valid/ and
	// must keep passing (a shared-file poison leaks into guardSuite and masks
	// the runSuite branch under test); an empty invalid corpus trips the same
	// incomplete branch
	removeGlob(t, filepath.Join(dir, "invalid", "*.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an empty contract corpus — runSuite's incomplete branch lost its failure")
		}
	})
}

func TestRunEnvelopeIncomplete(t *testing.T) {
	dir := copyExamplesTree(t)
	removeGlob(t, filepath.Join(dir, "envelopes", "valid", "*.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an empty envelope corpus — envelopeSuite's incomplete branch lost its failure")
		}
	})
}

func TestRunKeystoreIncomplete(t *testing.T) {
	dir := copyExamplesTree(t)
	removeGlob(t, filepath.Join(dir, "keys", "invalid", "*.jwks.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an empty keystore corpus — keystoreSuite's incomplete branch lost its failure")
		}
	})
}

func removeGlob(t *testing.T, pattern string) {
	t.Helper()
	files, err := filepath.Glob(pattern)
	if err != nil {
		t.Fatal(err)
	}
	for _, f := range files {
		if err := os.Remove(f); err != nil {
			t.Fatal(err)
		}
	}
}

// TestRunContractMustRejectPoison pins runSuite's "was accepted!" branch
// (V26 4-lens M-1 / singularity F-1): a must-reject contract fixed into
// validity must FAIL the suite and reach run()'s return value.
func TestRunContractMustRejectPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	fix := filepath.Join(dir, "invalid", "wildcard-selector.json")
	doc := readJSON(t, fix)
	delete(doc, "_expect")
	delete(doc, "_expect_match")
	if req, ok := doc["requires"].([]any); ok && len(req) > 0 {
		if g, ok := req[0].(map[string]any); ok {
			if res, ok := g["resource"].(map[string]any); ok {
				res["selector"] = "data:x" // the wildcard was the only rejection reason
			}
		}
	}
	writeJSON(t, fix, doc)
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite an accepted must-reject contract — the was-accepted branch lost its aggregation")
		}
	})
}

// TestRunEnvelopeMustRejectPoison pins envelopeSuite's "was accepted!" branch:
// a fully valid envelope placed among the invalid ones must FAIL.
func TestRunEnvelopeMustRejectPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	src := filepath.Join(dir, "envelopes", "valid", "doc-extractor.envelope.json")
	doc := readJSON(t, src)
	delete(doc, "_expect")
	delete(doc, "_expect_verified_kids")
	writeJSON(t, filepath.Join(dir, "envelopes", "invalid", "zz-poison-valid.json"), doc)
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite an accepted must-reject envelope — the was-accepted branch lost its aggregation")
		}
	})
}

// The wrong-reason enforcement edges (V26 singularity F-2): a must-reject
// fixture whose _expect_match names a reason that is NOT the rejection reason
// must FAIL — this edge is the only exit-code enforcement of the message pins.

func TestRunContractWrongReasonPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poisonMatch(t, filepath.Join(dir, "invalid", "wildcard-selector.json"), "zzz-no-such-reason")
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite a wrong-reason contract rejection — the wrong-reason branch lost its aggregation")
		}
	})
}

func TestRunEnvelopeWrongReasonPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poisonMatch(t, filepath.Join(dir, "envelopes", "invalid", "bad-typ.json"), "zzz-no-such-reason")
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite a wrong-reason envelope rejection — the wrong-reason branch lost its aggregation")
		}
	})
}

func TestRunKeystoreWrongReasonPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poisonMatch(t, filepath.Join(dir, "keys", "invalid", "missing-kid.jwks.json"), "zzz-no-such-reason")
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 despite a wrong-reason keystore rejection — the wrong-reason branch lost its aggregation")
		}
	})
}

// TestRunTrustStoreMissing pins the missing-vs-corrupt divergence (V26 4-lens
// m-2): a MISSING trusted.jwks.json makes Go exit 2 (load error, fail-closed)
// where the oracle runs with an empty store and exits 1 through suite
// failures — FORCED DIVERGENCE, strict side wins; pinned on our side only.
func TestRunTrustStoreMissing(t *testing.T) {
	dir := copyExamplesTree(t)
	if err := os.Remove(filepath.Join(dir, "keys", "trusted.jwks.json")); err != nil {
		t.Fatal(err)
	}
	withExamplesDir(t, dir, func() {
		if rc := run(); rc != 2 {
			t.Fatalf("run() = %d on a missing trust store, want 2 (missing-file FORCED DIVERGENCE, strict side)", rc)
		}
	})
}

// TestValidateSuiteCountFloors pins corpus SIZES (V26 singularity F-3): a
// corpus that shrinks by one fixture must change a summary line — the
// incomplete pins only caught "all gone", not "one gone".
func TestValidateSuiteCountFloors(t *testing.T) {
	buf := captureStdout(t, func() {
		if rc := run(); rc != 0 {
			t.Fatalf("clean-tree run() = %d", rc)
		}
	})
	for _, want := range []string{
		"[contract] 7 must-accept + 23 must-reject, 0 failures", // 23 = 22 + encoded-wildcard-lowercase (V33 m-1; rebased in the same atom per the pin-repair anti-entropy rule, V34 F-1)
		"[envelope] 4 must-accept + 16 must-reject, 0 failures",
		"[keystore] 3 must-reject, 0 failures",
		"[guards] 4 programmatic must-reject, 0 failures",
	} {
		if !strings.Contains(buf, want) {
			t.Fatalf("suite summary %q missing from run() output (corpus shrank?):\n%s", want, buf)
		}
	}
}

func poisonMatch(t *testing.T, path, match string) {
	t.Helper()
	doc := readJSON(t, path)
	doc["_expect_match"] = match
	writeJSON(t, path, doc)
}

// TestBothPinsCasePremiseFailure pins the sentinel-nil property (V26 m-3 /
// V27 m-2): a fixture WITHOUT both pins yields NO errors, and no error text
// can ever contain the match phrase — a re-tautologized string sentinel
// would make this guard constant-true.
func TestBothPinsCasePremiseFailure(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "no-pins.json")
	if err := os.WriteFile(p, []byte(`{"contract_version": "0.1.0"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	g := bothPinsCase(p)
	if len(g.errs) != 0 {
		t.Fatalf("premise failure produced errors %v — the sentinel is not nil", g.errs)
	}
}

// The unreadable-fixture aggregation edges (V27 singularity F-3): a fixture
// the runner cannot READ must FAIL its suite, in each of the three suites.

func TestRunContractUnreadable(t *testing.T) {
	dir := copyExamplesTree(t)
	chmod000(t, filepath.Join(dir, "invalid", "wildcard-selector.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an unreadable contract fixture — the unreadable branch lost its aggregation")
		}
	})
}

func TestRunEnvelopeUnreadable(t *testing.T) {
	dir := copyExamplesTree(t)
	chmod000(t, filepath.Join(dir, "envelopes", "invalid", "bad-typ.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an unreadable envelope fixture — the unreadable branch lost its aggregation")
		}
	})
}

func TestRunKeystoreUnreadable(t *testing.T) {
	dir := copyExamplesTree(t)
	chmod000(t, filepath.Join(dir, "keys", "invalid", "missing-kid.jwks.json"))
	withExamplesDir(t, dir, func() {
		if rc := run(); rc == 0 {
			t.Fatal("run() = 0 with an unreadable keystore fixture — the unreadable branch lost its aggregation")
		}
	})
}

// TestGuardSuiteBoundsMissing pins guardSuite's bounds-map-missing branch
// (V27 singularity F-3): a base fixture without bounds must fail the guards.
func TestGuardSuiteBoundsMissing(t *testing.T) {
	dir := copyExamplesTree(t)
	p := filepath.Join(dir, "valid", "doc-extractor.json")
	doc := readJSON(t, p)
	delete(doc, "bounds")
	writeJSON(t, p, doc)
	withExamplesDir(t, dir, func() {
		if rc := guardSuite(); rc == 0 {
			t.Fatal("guardSuite() = 0 despite a base fixture without bounds — the bounds-missing branch lost its failure")
		}
	})
}

func chmod000(t *testing.T, path string) {
	t.Helper()
	if err := os.Chmod(path, 0o000); err != nil {
		t.Fatal(err)
	}
}

// TestKeystoreParseErrorPropagates pins the fifth face's PROPAGATION (V29
// F-1): a keystore fixture with a wrong-typed pin must surface the parse
// reason in the output — keystoreSuite was the one consumer of four that
// dropped it, silently bypassing the wrong-reason layer.
func TestKeystoreParseErrorPropagates(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "keys", "invalid", "missing-kid.jwks.json")
	doc := readJSON(t, poison)
	doc["_expect_match"] = 5 // wrong-typed pin: parse error at load
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		buf := captureStdout(t, func() {
			rc := run()
			if rc == 0 {
				t.Fatal("run() = 0 — an unreadable pin must FAIL, not mask the store verdict (V32 M-1 flip; the old comment claiming the rejection still happened was wrong — LoadTrustStore never ran)")
			}
		})
		if !strings.Contains(buf, "must be a string") {
			t.Fatalf("keystore fixture's parse error was dropped from the output:\n%s", buf)
		}
	})
}

// The ParseError propagation pins for the three other suites (V30 F-1a —
// keystore had one, the siblings did not; the consumption code exists in all
// four, only the evidence did not). A wrong-typed pin on a must-reject
// fixture must surface the parse reason in the suite's output.

func TestRunContractParseErrorPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "invalid", "wildcard-selector.json")
	doc := readJSON(t, poison)
	doc["_expect_match"] = 5
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		buf := captureStdout(t, func() {
			rc := run()
			if rc == 0 {
				t.Fatal("run() = 0 — an unreadable pin on a must-reject fixture must FAIL (V32 M-1 flip)")
			}
		})
		if !strings.Contains(buf, "must be a string") {
			t.Fatalf("contract fixture's parse error was dropped:\n%s", tailN(buf, 400))
		}
	})
}

func TestRunEnvelopeParseErrorPoison(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "envelopes", "invalid", "bad-typ.json")
	doc := readJSON(t, poison)
	doc["_expect_match"] = 5
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		buf := captureStdout(t, func() {
			rc := run()
			if rc == 0 {
				t.Fatal("run() = 0 — an unreadable pin on a must-reject fixture must FAIL (V32 M-1 flip)")
			}
		})
		if !strings.Contains(buf, "must be a string") {
			t.Fatalf("envelope fixture's parse error was dropped:\n%s", tailN(buf, 400))
		}
	})
}

// TestRunContractPinLoud pins the suite/pin legality (V30 F-3): a kids pin
// on a VALID contract fixture is an authoring error — the oracle crashes
// (calling verified=None); we FAIL loudly.
func TestRunContractPinLoud(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "valid", "doc-extractor.json")
	doc := readJSON(t, poison)
	doc["_expect_verified_kids"] = []any{"no-such-kid"}
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		var rc int
		buf := captureStdout(t, func() { rc = run() })
		if rc == 0 {
			t.Fatal("run() = 0 despite a kids pin on a contract fixture — the oracle crashes on this shape; we must fail loudly")
		}
		if !strings.Contains(buf, "carries a pin") {
			t.Fatalf("the authoring-error message is missing (rolled back?): %s", tailN(buf, 400))
		}
	})
}

func tailN(s string, n int) string {
	if len(s) > n {
		return "..." + s[len(s)-n:]
	}
	return s
}

// TestKeystorePinLoud pins the keystore sibling (V30 m-2): a pin on a
// keystore fixture must FAIL the suite — the V30 pin-loud sweep landed
// contract only.
func TestKeystorePinLoud(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "keys", "invalid", "missing-kid.jwks.json")
	doc := readJSON(t, poison)
	delete(doc, "_expect")
	delete(doc, "_expect_match")
	doc["_expect_verified_kids"] = []any{"k"}
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		var rc int
		buf := captureStdout(t, func() { rc = run() })
		if rc == 0 {
			t.Fatal("run() = 0 despite a pin on a keystore fixture — the pin-loud rule must cover all suites")
		}
		if !strings.Contains(buf, "carries a pin") {
			t.Fatalf("the authoring-error message is missing (rolled back?): %s", tailN(buf, 400))
		}
	})
}

// TestEnvelopeNonKidsPinLoud pins the envelope sibling (V30 m-2): a
// map-shaped (composed-style) pin on an envelope fixture must FAIL with the
// authoring-error family message, not a misleading kids comparison — the
// MESSAGE is asserted too: the verdict face alone could not detect a rollback
// of the message swap (V31 F-1, mut4 survived).
func TestEnvelopeNonKidsPinLoud(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "envelopes", "valid", "doc-extractor.envelope.json")
	doc := readJSON(t, poison)
	delete(doc, "_expect_verified_kids")
	doc["_expect_composed"] = map[string]any{}
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		var rc int
		buf := captureStdout(t, func() { rc = run() })
		if rc == 0 {
			t.Fatal("run() = 0 despite a composed-shaped pin on an envelope fixture")
		}
		if !strings.Contains(buf, "non-kids pin") {
			t.Fatalf("the authoring-error message is missing (rolled back?): %s", tailN(buf, 400))
		}
	})
}

// The valid-half ParseError pins (V31 F-2): a must-ACCEPT fixture carrying a
// wrong-typed pin must FAIL — the propagation pins covered the invalid half
// only. FORCED DIVERGENCE: the oracle silently PASSES this face (its loader
// never type-checks pins), our loud rejection is strict-side-wins.
func TestRunContractValidParseError(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "valid", "doc-extractor.json")
	doc := readJSON(t, poison)
	doc["_expect_match"] = 5
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		var rc int
		buf := captureStdout(t, func() { rc = run() })
		if rc == 0 {
			t.Fatal("run() = 0 despite a wrong-typed pin on a must-accept contract — the valid half lost its propagation")
		}
		if !strings.Contains(buf, "must be a string") {
			t.Fatalf("the rejection reason is missing from the output (message face unpinned — V32 F-1): %s", tailN(buf, 400))
		}
	})
}

func TestRunEnvelopeValidParseError(t *testing.T) {
	dir := copyExamplesTree(t)
	poison := filepath.Join(dir, "envelopes", "valid", "doc-extractor.envelope.json")
	doc := readJSON(t, poison)
	doc["_expect_match"] = 5
	writeJSON(t, poison, doc)
	withExamplesDir(t, dir, func() {
		var rc int
		buf := captureStdout(t, func() { rc = run() })
		if rc == 0 {
			t.Fatal("run() = 0 despite a wrong-typed pin on a must-accept envelope — the valid half lost its propagation")
		}
		if !strings.Contains(buf, "must be a string") {
			t.Fatalf("the rejection reason is missing from the output (message face unpinned — V32 F-1): %s", tailN(buf, 400))
		}
	})
}

// The three flip-sites' scaffolding text (V34 F-3): the ParseError poison
// pins asserted the parse reason but not the family wording — a downgrade of
// any of the three sibling messages went unnoticed.
func TestFlipScaffoldingAllSuites(t *testing.T) {
	dir := copyExamplesTree(t)
	poisons := []string{
		filepath.Join(dir, "invalid", "wildcard-selector.json"),
		filepath.Join(dir, "envelopes", "invalid", "bad-typ.json"),
		filepath.Join(dir, "keys", "invalid", "missing-kid.jwks.json"),
	}
	for _, p := range poisons {
		doc := readJSON(t, p)
		doc["_expect_match"] = 5
		writeJSON(t, p, doc)
	}
	withExamplesDir(t, dir, func() {
		buf := captureStdout(t, func() {
			if rc := run(); rc == 0 {
				t.Fatal("run() = 0 — the flip itself regressed")
			}
		})
		if n := strings.Count(buf, "unreadable pin cannot verify the rejection"); n != 3 {
			t.Fatalf("flip scaffolding message appears %d times (want 3 — one per suite); a sibling was downgraded:\n%s", n, tailN(buf, 600))
		}
	})
}
