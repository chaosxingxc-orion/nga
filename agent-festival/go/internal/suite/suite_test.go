package suite

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

// The checker used by the poison tests: a document is accepted iff it has no
// "poison" key; the rejection names the poison — a stand-in for a real
// schema checker with a matchable reason.
func poisonCheck(doc map[string]any) []string {
	if v, ok := doc["poison"]; ok {
		return []string{"poison: " + toString(v)}
	}
	return nil
}

func toString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return "present"
}

func write(t *testing.T, dir, name, content string) string {
	t.Helper()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func corpus(t *testing.T) (valid, invalid string) {
	t.Helper()
	root := t.TempDir()
	valid = filepath.Join(root, "valid")
	invalid = filepath.Join(root, "invalid")
	for _, d := range []string{valid, invalid} {
		if err := os.Mkdir(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	write(t, valid, "ok.json", `{"_expect": "clean"}`)
	write(t, invalid, "bad.json", `{"poison": "yes", "_expect_match": "poison"}`)
	return valid, invalid
}

// TestRunCleanCorpusIsGreen pins the happy path and the summary line the
// count-floor tests of future pieces will match against.
func TestRunCleanCorpusIsGreen(t *testing.T) {
	valid, invalid := corpus(t)
	buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if bad := summaryFailures(t, buf); bad != 0 {
		t.Fatalf("clean corpus: failures = %d\n%s", bad, buf)
	}
	if !strings.Contains(buf, "[t] 1 must-accept + 1 must-reject, 0 failures") {
		t.Fatalf("summary line wrong:\n%s", buf)
	}
	if !strings.Contains(buf, "ALL GREEN") {
		t.Fatalf("ALL GREEN marker missing:\n%s", buf)
	}
}

// TestWrongReasonPoison pins the wrong-reason branch: an invalid fixture
// rejected for a reason its pin does not name must FAIL the suite.
func TestWrongReasonPoison(t *testing.T) {
	valid, invalid := corpus(t)
	write(t, invalid, "wrong-reason.json", `{"poison": "x", "_expect_match": "zzz-no-such-reason"}`)
	buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if summaryFailures(t, buf) == 0 {
		t.Fatalf("wrong-reason poison was green:\n%s", buf)
	}
	if !strings.Contains(buf, "rejected for the wrong reason") {
		t.Fatalf("wrong-reason message missing:\n%s", buf)
	}
}

// TestWasAcceptedPoison pins the was-accepted branch: an invalid fixture the
// checker accepts must FAIL the suite.
func TestWasAcceptedPoison(t *testing.T) {
	valid, invalid := corpus(t)
	write(t, invalid, "actually-valid.json", `{"_expect_match": "anything"}`)
	buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if summaryFailures(t, buf) == 0 {
		t.Fatalf("was-accepted poison was green:\n%s", buf)
	}
	if !strings.Contains(buf, "was accepted!") {
		t.Fatalf("was-accepted message missing:\n%s", buf)
	}
}

// TestWrongTypedPinPoison pins V28 F-1: a non-string _expect_match must FAIL
// LOUD in both phases — never silently downgrade to "no pin", which would
// bypass the wrong-reason checks.
func TestWrongTypedPinPoison(t *testing.T) {
	for _, phase := range []struct {
		dir   string
		label string
	}{
		{"valid", "must-accept"},
		{"invalid", "must-reject"},
	} {
		valid, invalid := corpus(t)
		d := valid
		if phase.dir == "invalid" {
			d = invalid
		}
		write(t, d, "bad-pin.json", `{"poison": "keep", "_expect_match": 5}`)
		buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
		if summaryFailures(t, buf) == 0 {
			t.Fatalf("wrong-typed pin in %s phase was green:\n%s", phase.dir, buf)
		}
		if !strings.Contains(buf, "_expect_match must be a string") {
			t.Fatalf("loud pin error missing in %s phase:\n%s", phase.dir, buf)
		}
	}
}

// TestParseFailedInvalidCountsAsRejected pins the two-path split (V32 M-1):
// an invalid fixture whose JSON does not parse is rejected-at-parse — only a
// READABLE document with a bad pin is a hard FAIL.
func TestParseFailedInvalidCountsAsRejected(t *testing.T) {
	valid, invalid := corpus(t)
	write(t, invalid, "not-json.json", `{"poison": "unterminated`)
	buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if !strings.Contains(buf, "PASS must-reject not-json.json") {
		t.Fatalf("parse-failed invalid not counted as rejected:\n%s", buf)
	}
	if summaryFailures(t, buf) != 0 {
		t.Fatalf("parse-failed invalid made the suite red:\n%s", buf)
	}
}

// TestSuiteIncompleteFails pins the empty-phase guard: a corpus that lost
// its valid or its invalid half fails, never passes silently.
func TestSuiteIncompleteFails(t *testing.T) {
	root := t.TempDir()
	valid := filepath.Join(root, "valid")
	invalid := filepath.Join(root, "invalid")
	for _, d := range []string{valid, invalid} {
		if err := os.Mkdir(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	write(t, valid, "ok.json", `{}`)
	if Run("t", valid, invalid, poisonCheck) == 0 {
		t.Fatal("empty invalid phase passed")
	}
	if Run("t", invalid, valid, poisonCheck) == 0 {
		t.Fatal("empty valid phase passed")
	}
}

// TestLoadPinSemantics pins Load's two failure shapes directly: doc-parse
// failure (Doc == nil, parse error set) vs pin-type failure (Doc != nil,
// parse error set).
func TestLoadPinSemantics(t *testing.T) {
	dir := t.TempDir()
	p := write(t, dir, "bad-pin.json", `{"a": 1, "_expect_match": 5}`)
	fx, err := Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.Doc == nil || fx.ParseError == "" {
		t.Fatalf("wrong-typed pin not loud: %+v", fx)
	}
	p = write(t, dir, "not-json.json", `{"a": `)
	fx, err = Load(p)
	if err != nil {
		t.Fatal(err)
	}
	if fx.Doc != nil || fx.ParseError == "" {
		t.Fatalf("parse failure not recorded: %+v", fx)
	}
}

// summaryFailures extracts the failure count from the summary line, failing
// the test when no summary line was printed.
func summaryFailures(t *testing.T, buf string) int {
	t.Helper()
	for _, line := range strings.Split(buf, "\n") {
		if !strings.HasPrefix(line, "[t] ") || !strings.Contains(line, "failures") {
			continue
		}
		// "[t] N must-accept + M must-reject, K failures"
		parts := strings.Fields(strings.TrimSuffix(strings.SplitN(line, ",", 2)[1], " failures"))
		n, err := strconv.Atoi(parts[len(parts)-1])
		if err != nil {
			t.Fatalf("summary line unparseable: %q", line)
		}
		return n
	}
	t.Fatalf("no summary line in:\n%s", buf)
	return -1
}

// TestParseFailedPinStaysArmed pins R3 M-3: a fixture whose JSON does not
// parse still has its wrong-reason check armed — the pin is extracted from
// the raw bytes and matched against the parse error. A non-matching pin
// must FAIL; a matching pin must PASS as rejected-for-that-reason.
func TestParseFailedPinStaysArmed(t *testing.T) {
	dir := t.TempDir()
	valid := filepath.Join(dir, "valid")
	invalid := filepath.Join(dir, "invalid")
	for _, d := range []string{valid, invalid} {
		if err := os.Mkdir(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	write(t, valid, "ok.json", `{"_expect": "clean"}`)

	// a pinless unparseable fixture: rejected at parse, no wrong-reason check
	write(t, invalid, "unparseable-matching.json", `{"poison": "unterminated`)
	fx, err := Load(filepath.Join(invalid, "unparseable-matching.json"))
	if err != nil {
		t.Fatal(err)
	}
	if fx.Doc != nil || fx.ParseError == "" {
		t.Fatalf("parse failure not recorded: %+v", fx)
	}
	if fx.ExpectMatch != "" {
		t.Fatalf("pin extracted from a pinless fixture: %q", fx.ExpectMatch)
	}
	buf := Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if summaryFailures(t, buf) != 0 {
		t.Fatalf("pinless parse-failed fixture made the suite red:\n%s", buf)
	}

	// an armed pin that does not match the parse error: the wrong-reason
	// check must FAIL the suite — a silently disarmed pin is exactly the
	// bypass V28 F-1 legislates against
	write(t, invalid, "unparseable-wrong-reason.json",
		`{"poison": "unterminated", "_expect_match": "zzz-no-such-reason"`)
	buf = Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if !strings.Contains(buf, "rejected for the wrong reason") {
		t.Fatalf("wrong-reason check disarmed on a parse-failed fixture:\n%s", buf)
	}

	// an armed pin that DOES match the parse error: rejected for that reason
	write(t, invalid, "unparseable-right-reason.json",
		`{"poison": "unterminated", "_expect_match": "parse"`)
	buf = Capture(func() { Run("t", valid, invalid, poisonCheck) })
	if !strings.Contains(buf, "PASS must-reject unparseable-right-reason.json") {
		t.Fatalf("matching pin on a parse-failed fixture not PASSed:\n%s", buf)
	}
	// the wrong-reason fixture from the previous case still fails by design
	// in this shared directory, so the suite is red here — only the
	// right-reason fixture's own verdict is under assertion
}
