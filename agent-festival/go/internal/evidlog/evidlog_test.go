package evidlog

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func open(t *testing.T) *Log {
	t.Helper()
	return &Log{seq: -1, path: filepath.Join(t.TempDir(), "evid.jsonl")}
}

// TestDenseAppend covers Open→Append→reopen with the durable form and the
// writer-allocated seq: the log must survive close/reopen with seqs dense.
func TestDenseAppend(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	// first-write byte shape: a fresh log must not begin with a newline (the
	// TrimRight-of-empty quirk used to write a leading "\n" — harmless only
	// while empty lines were silently skipped)
	if b := mustRead(t, path); len(b) == 0 || b[0] != '{' {
		t.Fatalf("first write did not start with an entry object: %q", b)
	}
	if err := l.Append(Entry{Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"}); err != nil {
		t.Fatal(err)
	}
	l2, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	es := l2.Entries()
	if len(es) != 2 || es[0].Seq != 0 || es[1].Seq != 1 {
		t.Fatalf("reopen lost entries or seqs: %+v", es)
	}
	// doc-level: the reopened log is schema-valid and dense
	// torn tail tolerance: append garbage, reopen still sees the 2 events
	line, _ := json.Marshal(Entry{Seq: 2, Tool: "t"})
	garbage := line[:len(line)-5]
	if err := os.WriteFile(path, append(mustRead(t, path), garbage...), 0o644); err != nil {
		t.Fatal(err)
	}
	l3, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(l3.Entries()) != 2 {
		t.Fatalf("torn tail not tolerated: %d entries", len(l3.Entries()))
	}
}

// TestMidfileUnparseableRejected pins the OTHER half of the boundary: an
// unparseable line BEFORE the EOF position (i.e. followed by more lines) is
// rejected outright — silently skipping it would shrink the coverage
// CheckCoverage accounts for and let a completeness verdict go green on an
// incomplete record. The torn-tail face (same garbage, no trailing newline,
// at EOF) stays tolerated and is pinned by TestDenseAppend.
func TestMidfileUnparseableRejected(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"}); err != nil {
		t.Fatal(err)
	}
	good, err := json.Marshal(Entry{Seq: 2, Tool: "t", Caller: "s2", At: "2026-11-01T10:02:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	midfile := append(mustRead(t, path), '\n', '{', '"', 's', 'e', 'q', ':', '\n')
	midfile = append(midfile, good...)
	if err := os.WriteFile(path, midfile, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("mid-file unparseable line was silently skipped — coverage boundary missing")
	} else if !strings.Contains(err.Error(), "EVIDLOG.MIDFILE_UNPARSEABLE") {
		t.Fatalf("mid-file rejection lacks the neutral key: %v", err)
	}
}

// TestDurableSeqGapRejected pins the durable face of the density contract
// (R3 M1): a byte-clean file with a dropped line — both lines perfectly
// parseable, the gap invisible to any per-line parser — must fail Open with
// EVIDLOG.SEQ_GAP, exactly as the envelope face (CheckDoc, seq-gap.json
// fixture) rejects the same shape. A dropped line is the cheapest way to
// shrink what CheckCoverage accounts for.
func TestDurableSeqGapRejected(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l1, _ := json.Marshal(Entry{Seq: 0, Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	l2, _ := json.Marshal(Entry{Seq: 2, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	body := append(append(append([]byte{}, l1...), '\n'), l2...)
	body = append(body, '\n')
	if err := os.WriteFile(path, body, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("dropped line silently absorbed — durable face never ran the density contract")
	} else if !strings.Contains(err.Error(), "EVIDLOG.SEQ_GAP") {
		t.Fatalf("seq-gap rejection lacks the neutral key: %v", err)
	}
}

// TestNullLineRejected pins the phantom-entry face (R3 M1): a bare `null`
// line unmarshals into a zero-value Entry without error, and a
// `{"seq":1}`-style fragment parses cleanly while still being a phantom —
// both must be rejected mid-file with EVIDLOG.NON_OBJECT_LINE; at the
// torn-tail position (EOF, no newline) the loader tolerates them as tail
// garbage.
func TestNullLineRejected(t *testing.T) {
	l1, _ := json.Marshal(Entry{Seq: 0, Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	l2, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	cases := map[string][]byte{
		"bare null":         append(append(append([]byte{}, l1...), '\n', 'n', 'u', 'l', 'l', '\n'), l2...),
		"fragment with seq": append(append(append(append([]byte{}, l1...), '\n', '{', '"', 's', 'e', 'q', '"', ':', '9', '}', '\n'), l2...), '\n'),
		"missing caller":    append(append(append([]byte{}, l1...), '\n', '{', '"', 's', 'e', 'q', '"', ':', '1', ',', '"', 't', 'o', 'o', 'l', '"', ':', '"', 'x', '"', ',', '"', 'a', 't', '"', ':', '"', 'y', '"', '}', '\n')),
	}
	for name, body := range cases {
		path := filepath.Join(t.TempDir(), "evid.jsonl")
		if err := os.WriteFile(path, append(body, '\n'), 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := Open(path); err == nil {
			t.Fatalf("%s: phantom line absorbed into the audit record", name)
		} else if !strings.Contains(err.Error(), "EVIDLOG.NON_OBJECT_LINE") {
			t.Fatalf("%s: rejection lacks the neutral key: %v", name, err)
		}
	}
}

// TestAppendRefusesTornTail pins the writer's recovery duty (R3 M2): Open
// tolerates a torn tail by skipping it, but Append on that same log must
// REFUSE — appending would splice the tail into mid-file and brick every
// future Open against this loader. After a human repair (tail removed, the
// log ends cleanly), appending works and the reopened log is dense.
func TestAppendRefusesTornTail(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	clean := mustRead(t, path) // the valid prefix, ends with '\n'
	line, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q"})
	if err := os.WriteFile(path, append(append([]byte{}, clean...), line[:len(line)-5]...), 0o644); err != nil {
		t.Fatal(err)
	}
	l2, err := Open(path) // tolerance at load: 1 entry, torn tail remembered
	if err != nil {
		t.Fatal(err)
	}
	if err := l2.Append(Entry{Tool: "t", Caller: "s2", At: "2026-11-01T10:02:00Z"}); err == nil {
		t.Fatal("Append wrote over a tolerated torn tail — the log is now bricked for every future Open")
	} else if !strings.Contains(err.Error(), "EVIDLOG.TORN_TAIL_BLOCKED") {
		t.Fatalf("torn-tail refusal lacks the neutral key: %v", err)
	}
	// repair: drop the torn tail bytes (a human decision on an audit record)
	// and rewrite the second entry cleanly — the log ends with '\n' again,
	// then the writer resumes and stays loadable and dense
	good, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	if err := os.WriteFile(path, append(append(append([]byte{}, clean...), good...), '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
	l3, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l3.Append(Entry{Tool: "t", Caller: "s2", At: "2026-11-01T10:02:00Z"}); err != nil {
		t.Fatalf("Append still refuses after repair: %v", err)
	}
	l4, err := Open(path)
	if err != nil {
		t.Fatalf("reopened log rejected after repair+append: %v", err)
	}
	if es := l4.Entries(); len(es) != 3 || es[2].Seq != 2 {
		t.Fatalf("repair+append lost density: %+v", es)
	}
}

func mustRead(t *testing.T, p string) []byte {
	t.Helper()
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestCoverageMissingAndHiddenExclusion pins both directions of the diff
// check: a declaration claiming a query the log lacks → Missing; a
// declaration whose exclusion record hides queried selectors → flagged in
// Unaccounted (the "沉默的零 vs 声明的零" face).
func TestCoverageMissingAndHiddenExclusion(t *testing.T) {
	l := open(t)
	l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	l.Append(Entry{Tool: "bank.fetch", Selector: "acct=2", Caller: "s2", At: "2026-11-01T10:01:00Z"})

	// missing: declaration claims a domain never queried
	rep := CheckCoverage(l, Declaration{QueriedTool: "credit-bureau.query", Selector: "subj=x"})
	if rep.OK || len(rep.Missing) != 1 {
		t.Fatalf("missing not caught: %+v", rep)
	}
	// honest declaration: covers acct=1, excludes acct=2 explicitly
	rep = CheckCoverage(l, Declaration{QueriedTool: "bank.fetch", Selector: "acct=1", ExcludedSelectors: []string{"acct=2"}})
	if !rep.OK || len(rep.Missing) != 0 {
		t.Fatalf("honest declaration failed: %+v", rep)
	}
	// hidden exclusion: acct=2 queried but NOT listed in the exclusion record
	rep = CheckCoverage(l, Declaration{QueriedTool: "bank.fetch", Selector: "acct=1"})
	if len(rep.Unaccounted) == 0 {
		t.Fatal("a queried-but-unlisted selector is invisible — the silent-zero face is blind")
	}
	// OK double-direction pin: hidden exclusions must make OK=false too
	// (R2 mut-1: reverting to单向 OK stayed green — this line pins the bidirectional semantics)
	rep = CheckCoverage(l, Declaration{QueriedTool: "bank.fetch", Selector: "acct=1"})
	if rep.OK {
		t.Fatal("OK=true with unaccounted entries — the bidirectional OK semantics regressed")
	}
}

// TestSeqGapRejected pins the density rule at doc level (mirrors the invalid fixture).
func TestSeqGapRejected(t *testing.T) {
	doc := map[string]any{
		"evidlog_version": "0.1.0",
		"entries": []any{
			map[string]any{"seq": 0, "tool": "t", "selector": "s1", "caller": "c", "at": "2026-11-01T10:00:00Z"},
			map[string]any{"seq": 2, "tool": "t", "selector": "s2", "caller": "c", "at": "2026-11-01T10:00:00Z"},
		},
	}
	errs := CheckDoc(doc)
	if len(errs) == 0 {
		t.Fatal("seq gap accepted at doc level")
	}
}
