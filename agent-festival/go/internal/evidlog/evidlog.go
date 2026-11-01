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
	entries []Entry
	seq     int
	path    string
}

// Open loads (or starts) the durable form at path.
func Open(path string) (*Log, error) {
	l := &Log{seq: -1, path: path}
	lines, err := loadLines(path)
	if err != nil {
		return nil, err
	}
	for _, ln := range lines {
		l.entries = append(l.entries, ln.Event)
		if ln.Event.Seq > l.seq {
			l.seq = ln.Event.Seq
		}
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
		existing, err := os.ReadFile(l.path)
		if err != nil && !os.IsNotExist(err) {
			l.seq--
			return err
		}
		next := append(bytes.TrimRight(existing, "\n"), '\n')
		next = append(next, line...)
		next = append(next, '\n')
		dir, base := filepath.Split(l.path)
		tmp, err := os.CreateTemp(dir, "."+base+".*")
		if err != nil {
			l.seq--
			return err
		}
		if _, err := tmp.Write(next); err != nil {
			tmp.Close()
			os.Remove(tmp.Name())
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
}

// CheckCoverage verifies a declaration against the log: every claimed query
// must have a matching entry (差集告警); exclusions are checked in reverse —
// every log entry in the excluded domain must be listed, or the exclusion
// hid something. In-band seqs make both sides pure set/density functions.
func CheckCoverage(log *Log, decl Declaration) CoverageReport {
	rep := CoverageReport{OK: true}
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
	// exclusion — "沉默的零 vs 声明的零" are different audit facts)
	rep.OK = len(rep.Missing) == 0 && len(rep.Unaccounted) == 0
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

func loadLines(path string) ([]parsedLine, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var lines []parsedLine
	start := 0
	for i := 0; i <= len(raw); i++ {
		if i != len(raw) && raw[i] != '\n' {
			continue
		}
		line := raw[start:i]
		start = i + 1
		if len(line) == 0 {
			continue
		}
		var e Entry
		if json.Unmarshal(line, &e) != nil {
			continue // torn tail tolerance (mid-file unparseable lines are REJECTED by the caller's ParseLines — only this loader has the boundary)
		}
		doc := map[string]any{}
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.UseNumber()
		if dec.Decode(&doc) != nil {
			continue
		}
		lines = append(lines, parsedLine{Raw: line, Doc: doc, Event: e})
	}
	return lines, nil
}

func contains(hay []string, needle string) bool {
	for _, h := range hay {
		if h == needle {
			return true
		}
	}
	return false
}
