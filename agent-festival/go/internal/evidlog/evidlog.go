// Package evidlog is piece-7's spike: the evidence-collection query log
// (夏 ruling round-1's machine-checkable query-trail). It is the append-only
// record of authorized tool calls an investigator (S2) made, so that a sealed
// evidence package's completeness declaration ("queried bank statements") can
// be verified against what actually happened — "trust honesty" becomes
// "check honesty".
//
// Deliberately NOT the piece-4 event ledger (the word-sense collision 夏's
// ruling surfaced): the event book keeps business events (adoption/effect,
// eight rule families, a state machine, replay); this log keeps
// evidence-collection calls (append-only density, no state machine). Two
// atoms, two logs. If a future need merges them, that is a new ruling, not a
// refactor.
//
// Collision-informed shape (frame-bench): the in-band seq follows codex
// rollout's writer-allocated ordinal (making coverage a pure density
// function — gaps are visible without an external clock); the append is
// temp+rename atomic like piece 2's durable form (process-crash contract
// only, no fsync — same honesty boundary).
package evidlog

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/openjiuwen/agent-festival/go/internal/schemalib"
)

// SchemaPath is where evidlog.schema.json was found.
var SchemaPath = schemalib.FindSchema("evidlog.schema.json")

var schema = schemalib.NewLazy(
	"https://agent-festival.local/schema/evidlog/0.1.0", SchemaPath)

// Entry is one evidence-collection call.
type Entry struct {
	Seq       int    `json:"seq"`
	Tool      string `json:"tool"`
	Selector  string `json:"selector"`
	Caller    string `json:"caller"`
	At        string `json:"at"`
	ResultRef string `json:"result_ref,omitempty"`
}

// Log is an in-memory evidence log; Open attaches the durable form.
type Log struct {
	entries  []Entry
	seq      int
	path     string
	tornTail bool // the durable form's tail was skipped at load — Append must refuse
}

// Open loads (or starts) the durable form at path.
func Open(path string) (*Log, error) {
	l := &Log{seq: -1, path: path}
	lines, tornTail, err := loadLines(path)
	if err != nil {
		return nil, err
	}
	l.tornTail = tornTail
	// The durable face runs the SAME density contract as the envelope face
	// (CheckDoc): writer-allocated seqs are dense from 0. A byte-clean file
	// with a dropped line is exactly the "incomplete record" the coverage
	// verdict must never go green on (R3 M1).
	for i, ln := range lines {
		if ln.Event.Seq != i {
			return nil, fmt.Errorf("[EVIDLOG.SEQ_GAP] %s: entries/%d has seq %d, want %d — the durable form must stay dense (a gap is a dropped line or a foreign writer)", path, i, ln.Event.Seq, i)
		}
		l.entries = append(l.entries, ln.Event)
		l.seq = ln.Event.Seq
	}
	return l, nil
}

// Append records one call (writer-allocated seq, temp+rename atomic).
func (l *Log) Append(e Entry) error {
	l.seq++
	e.Seq = l.seq
	line, err := json.Marshal(e)
	if err != nil {
		l.seq--
		return err
	}
	if l.path != "" {
		if l.tornTail {
			// The loader tolerated this file's unparseable tail by skipping
			// it. Appending would splice that tail into the middle of the
			// file and brick every future Open. The writer refuses instead
			// of silently destroying evidence bytes — repairing the tail is
			// a human decision on an audit record (R3 M2).
			l.seq--
			return fmt.Errorf("[EVIDLOG.TORN_TAIL_BLOCKED] %s: the durable form ends in an unparseable torn tail (tolerated at Open) — appending would turn it into a mid-file line and brick the log; repair the tail first", l.path)
		}
		existing, err := os.ReadFile(l.path)
		if err != nil && !os.IsNotExist(err) {
			l.seq--
			return err
		}
		var next []byte
		if len(existing) > 0 {
			next = append(bytes.TrimRight(existing, "\n"), '\n')
		}
		next = append(next, line...)
		next = append(next, '\n')
		dir, base := filepath.Split(l.path)
		tmp, err := os.CreateTemp(dir, "."+base+".*")
		if err != nil {
			l.seq--
			return err
		}
		renamed := false
		defer func() {
			if !renamed {
				tmp.Close()
				os.Remove(tmp.Name()) // no hidden .evid.jsonl.* residue on any failure path (R4 m-3)
			}
		}()
		if _, err := tmp.Write(next); err != nil {
			l.seq--
			return err
		}
		if err := tmp.Close(); err != nil {
			l.seq--
			return err
		}
		if err := os.Rename(tmp.Name(), l.path); err != nil {
			l.seq--
			return err
		}
		renamed = true
	}
	l.entries = append(l.entries, e)
	return nil
}

// Entries returns the log's entries.
func (l *Log) Entries() []Entry { return l.entries }

// Declaration is a completeness claim from a sealed evidence package
// (夏 ruling's field group).
type Declaration struct {
	QueriedTool       string   // "I queried bank statements"
	Selector          string   // what domain
	ExcludedSelectors []string // "no contradictory material found" — the exclusion record, explicit
}

// CoverageReport is the diff-check's outcome.
type CoverageReport struct {
	OK          bool
	Missing     []string // selectors the declaration claims but the log lacks
	Unaccounted []string // log entries the declaration does not cover — verdict-bearing: empties gate OK
	TornTail    bool     // the log's tail was skipped at load: the record is incomplete — OK is forced false
}

// CheckCoverage verifies a declaration against the log: every claimed query
// must have a matching entry (差集告警); exclusions are checked in reverse —
// every log entry in the excluded domain must be listed, or the exclusion
// hid something. In-band seqs make both sides pure set/density functions.
func CheckCoverage(log *Log, decl Declaration) CoverageReport {
	rep := CoverageReport{OK: true}
	// A tolerated torn tail means the record is provably incomplete — the
	// skipped tail may hold an unaccounted query. The verdict must never go
	// green on it (R4 M-2: Append refuses to brick the file, and the verdict
	// refuses to bless the gap — the same incompleteness, both consumers).
	// The flag lands in the FINAL verdict assignment below, not here — an
	// early OK=false would be clobbered by the Missing/Unaccounted clean-up.
	if log.tornTail {
		rep.TornTail = true
	}
	logHas := map[string]bool{}
	for _, e := range log.Entries() {
		k := e.Tool + "|" + e.Selector
		logHas[k] = true
		if e.Tool == decl.QueriedTool && !contains(decl.ExcludedSelectors, e.Selector) {
			// entry covered by the declaration's positive claim
			continue
		}
		if e.Tool == decl.QueriedTool && contains(decl.ExcludedSelectors, e.Selector) {
			continue // covered by the exclusion record
		}
		rep.Unaccounted = append(rep.Unaccounted, k)
	}
	if !logHas[decl.QueriedTool+"|"+decl.Selector] {
		rep.Missing = append(rep.Missing, decl.QueriedTool+"|"+decl.Selector)
	}
	// exclusion honesty: a claimed exclusion with log entries outside the list is a hidden exclusion
	for _, e := range log.Entries() {
		if e.Tool == decl.QueriedTool && e.Selector != decl.Selector && !contains(decl.ExcludedSelectors, e.Selector) {
			rep.Unaccounted = append(rep.Unaccounted, e.Tool+"|"+e.Selector)
		}
	}
	// OK requires BOTH directions clean: no claimed-but-absent query (Missing)
	// and no queried-but-unlisted selector on the declared tool (a hidden
	// exclusion — "沉默的零 vs 声明的零" are different audit facts) — and a
	// complete record: a torn tail forces false regardless of the diff.
	rep.OK = !log.tornTail && len(rep.Missing) == 0 && len(rep.Unaccounted) == 0
	return rep
}

// CheckDoc validates an evidlog document against the schema.
func CheckDoc(doc map[string]any) []string {
	if err := schema.Validate(doc); err != nil {
		return []string{"schema: " + err.Error()}
	}
	// in-band density: seq must be dense and increasing (writer-allocated)
	var d struct {
		Entries []Entry `json:"entries"`
	}
	raw, _ := json.Marshal(doc)
	if err := json.Unmarshal(raw, &d); err != nil {
		return []string{"evidlog: decode failed: " + err.Error()}
	}
	prev := -1
	for i, e := range d.Entries {
		if e.Seq != prev+1 {
			return []string{fmt.Sprintf("entries/%d: seq %d breaks the dense writer-allocated sequence (want %d) — a gap or a foreign writer", i, e.Seq, prev+1)}
		}
		prev = e.Seq
	}
	return nil
}

type parsedLine struct {
	Raw   []byte
	Doc   map[string]any
	Event Entry
}

// loadLines parses the durable JSONL form. The bool reports a TOLERATED torn
// tail: the final line lacked a newline AND was unparseable, so bytes were
// skipped — the caller (Open) must remember it, because appending to a file
// whose tail was skipped would turn those bytes into a mid-file line and
// brick the log against this very loader (R3 M2).
func loadLines(path string) ([]parsedLine, bool, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	var lines []parsedLine
	tornTail := false
	start := 0
	for i := 0; i <= len(raw); i++ {
		if i != len(raw) && raw[i] != '\n' {
			continue
		}
		line := raw[start:i]
		lineStart := start
		start = i + 1
		if len(line) == 0 {
			continue
		}
		// The boundary: only the final line WITHOUT a trailing newline is a
		// torn tail (interrupted last write) and is tolerated. Any unparseable
		// line BEFORE the EOF position is rejected — silently skipping it
		// would shrink the coverage CheckCoverage accounts for and turn a
		// completeness verdict green on an incomplete record. The same holds
		// for lines that PARSE but are not entry objects (a bare `null`
		// unmarshals into a zero-value phantom entry) or entries without a
		// seq — a durable line is an entry or the file is not loadable.
		tornTail := i == len(raw)
		var e Entry
		if json.Unmarshal(line, &e) != nil {
			if tornTail {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.MIDFILE_UNPARSEABLE] %s: unparseable line at byte offset %d (before EOF) — evidence coverage must not silently shrink", path, lineStart)
		}
		doc := map[string]any{}
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.UseNumber()
		if dec.Decode(&doc) != nil {
			if tornTail {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.MIDFILE_UNPARSEABLE] %s: unparseable line at byte offset %d (before EOF) — evidence coverage must not silently shrink", path, lineStart)
		}
		if doc == nil {
			if tornTail {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d is %q, not an entry object — a phantom entry must not enter the audit record", path, lineStart, string(line))
		}
		// Shape: a durable line must carry every required Entry field —
		// seq/tool/selector/caller/at (the envelope schema's required set)
		// with the string fields non-empty non-null strings (the schema's
		// minLength:1; a present-but-null key would otherwise become an
		// empty-string phantom). A `{"seq":1}`-style object that parses
		// cleanly is still a phantom: it would enter the audit record and
		// silently pass the density rule (R3 M1, phantom family). The key
		// set is mechanically locked to the schema by
		// TestRequiredKeysLockstep (R4 M-1: the loader table drifted from
		// the schema once — selector was missing while the comment claimed
		// equality).
		badKey := ""
		badWhy := ""
		for _, k := range requiredEntryKeys {
			v, has := doc[k]
			if !has {
				badKey, badWhy = k, "without"
				break
			}
			if k != "seq" {
				s, isStr := v.(string)
				if !isStr || s == "" {
					badKey, badWhy = k, "empty-or-null"
					break
				}
			}
		}
		if badKey != "" {
			if tornTail {
				return lines, true, nil
			}
			if badWhy == "without" {
				return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d is an object without %q — a durable line is a full entry (seq/tool/selector/caller/at), not a fragment", path, lineStart, badKey)
			}
			return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d has an empty or null %q — the envelope schema's minLength:1 rides the durable face too", path, lineStart, badKey)
		}
		lines = append(lines, parsedLine{Raw: line, Doc: doc, Event: e})
	}
	return lines, tornTail, nil
}

// requiredEntryKeys is the durable face's entry-shape contract, mechanically
// locked to schema/evidlog.schema.json's required list and the Entry struct's
// json tags by TestRequiredKeysLockstep. Order matches the schema's required
// list; "seq" is the only non-string key (writer-allocated int).
var requiredEntryKeys = []string{"seq", "tool", "selector", "caller", "at"}

func contains(hay []string, needle string) bool {
	for _, h := range hay {
		if h == needle {
			return true
		}
	}
	return false
}
