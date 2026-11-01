package evidlog

import (
	"encoding/json"
	"os"
	"path/filepath"
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
