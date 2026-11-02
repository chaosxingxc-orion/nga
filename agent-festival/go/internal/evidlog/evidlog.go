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
	"math"
	"os"
	"path/filepath"
	"unicode/utf8"

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
//
// Single-instance contract (R10 MAJOR-1, mirroring adopt.Machine): at most
// ONE Log instance per file. entries/tornTail are the Open-time view — a
// foreign writer's appends WHILE a Log is open are outside the contract:
// CheckCoverage's verdict reflects that Open-time snapshot (skipped bytes
// and later-added lines are not in it), and Append only re-checks the
// torn-tail byte shape of the current file, not its full content.
type Log struct {
	entries  []Entry
	seq      int
	path     string
	tornTail bool // the durable form's tail was skipped at load — Append must refuse
	opened   bool // Open only: a zero-value &Log{} never reaches the durable form (R10 m3 — the composite literal is legal outside the package, and a zero seq would violate dense-from-0)
}

// Open loads (or starts) the durable form at path.
func Open(path string) (*Log, error) {
	l := &Log{seq: -1, path: path}
	lines, tornTail, err := loadLines(path)
	if err != nil {
		return nil, err
	}
	l.tornTail = tornTail
	l.opened = true
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
	if !l.opened {
		// R10 m3: &Log{} is legal outside the package, but a zero seq would
		// emit Seq=1 on the first entry and violate dense-from-0. Open is
		// the only constructor.
		return fmt.Errorf("[EVIDLOG.NOT_OPEN] Append on a Log that never went through Open — Open is the only constructor")
	}
	// Writer-side UTF-8 gate (R9 F1), BEFORE any marshal: Go's json encoder
	// silently launders invalid UTF-8 to U+FFFD, so a laundered write would
	// make the durable form differ from what the caller holds in memory.
	// The loader rejects such lines on sight (ledger/load.go precedent);
	// this gate closes the write side of the same hole. All five string
	// fields ride, including the optional ResultRef — everything that ends
	// up as durable bytes must be byte-representable (adopt's R5 BLOCKER
	// doctrine: the gate rejects what it cannot byte-represent).
	for name, s := range map[string]string{"tool": e.Tool, "selector": e.Selector, "caller": e.Caller, "at": e.At, "result_ref": e.ResultRef} {
		if !utf8.ValidString(s) {
			return fmt.Errorf("[EVIDLOG.INVALID_ENTRY] Append refuses: field %q is not valid UTF-8 — the json encoder would launder it to U+FFFD and the durable form would diverge from the caller's copy", name)
		}
	}
	l.seq++
	e.Seq = l.seq
	line, err := json.Marshal(e)
	if err != nil {
		l.seq--
		return err
	}
	// Writer-side shape gate (R5 F1): a line the loader would reject must
	// fail HERE, at the Append that produced it — not at the next Open, far
	// from the guilty call, with the log bricked in between. The writer and
	// the reader run the SAME shape table (requiredEntryKeys via
	// entryShapeError); one table, both consumers, no drift.
	var probe map[string]any
	if err := json.Unmarshal(line, &probe); err != nil {
		l.seq--
		return err
	}
	if key, why := entryShapeError(probe); key != "" {
		l.seq--
		return fmt.Errorf("[EVIDLOG.INVALID_ENTRY] Append refuses: entry's %q is %s — a line the loader would reject must not enter the durable form", key, map[string]string{"without": "missing", "empty-or-null": "empty or null"}[why])
	}
	if l.path != "" {
		if l.tornTail {
			// The loader tolerated this file's torn tail (unparseable
			// bytes or a phantom shape) by skipping it. Appending would
			// splice that tail into the middle of the
			// file and brick every future Open. The writer refuses instead
			// of silently destroying evidence bytes — repairing the tail is
			// a human decision on an audit record (R3 M2).
			l.seq--
			return fmt.Errorf("[EVIDLOG.TORN_TAIL_BLOCKED] %s: the durable form ends in a skipped torn tail (unparseable bytes or a phantom shape) — appending would turn it into a mid-file line and brick the log; repair the tail first", l.path)
		}
		existing, err := os.ReadFile(l.path)
		if err != nil && !os.IsNotExist(err) {
			l.seq--
			return err
		}
		// Byte-level torn-tail re-check (R10 MAJOR-1 face B): l.tornTail is
		// Open-time memory and the file may have evolved since (a foreign
		// writer's aborted append). A final line without a newline survives
		// the splice below only if it is a conformant entry; anything else
		// would become a mid-file disease line — refuse while it is still
		// the writer's own fault, not the next Open's mystery.
		if len(existing) > 0 && existing[len(existing)-1] != '\n' {
			tail := existing[bytes.LastIndexByte(existing, '\n')+1:]
			if !conformantLine(tail) {
				l.seq--
				return fmt.Errorf("[EVIDLOG.TORN_TAIL_BLOCKED] %s: the durable form now ends in a torn tail the Open-time view did not see — appending would brick the log; repair the tail first", l.path)
			}
		}
		// Seq-continuity re-check (R11 singularity — the evidlog side of
		// adopt's ADOPT.STALE_WRITER gate, completing the three-piece
		// symmetry): even a VALID foreign line appended after Open would be
		// spliced into a duplicate/gap seq below, and a foreign TRUNCATION
		// would let a stale Seq write itself in as the new first line. The
		// last durable seq must be exactly e.Seq-1; the guard fires on a
		// non-empty file OR any e.Seq above 0 (an emptied file plus a
		// non-fresh view is the erase face of the same disease — R11 inner
		// MAJOR-1). Honest boundary: the gate is necessary, not sufficient —
		// a foreign line that PRESERVES the seq arithmetic (a duplicate of
		// the current last seq, or a truncation-preserving fractional seq
		// like 1.5 with the next view at 2) passes arithmetic inspection
		// and is left to the next Open's checks to catch.
		if len(existing) > 0 || e.Seq > 0 {
			lastSeq, ok := lastDurableSeq(existing)
			if !ok {
				l.seq--
				return fmt.Errorf("[EVIDLOG.STALE_SEQ] %s: append refused — the durable form's last line carries no numeric seq (empty or diseased file); repair the file before appending", l.path)
			}
			if lastSeq+1 != e.Seq {
				l.seq--
				return fmt.Errorf("[EVIDLOG.STALE_SEQ] %s: append refused — the durable form's last seq is %d but this instance is about to write %d; the Open-time view is stale (foreign or stale-instance write). Re-Open to absorb the file, then decide", l.path, lastSeq, e.Seq)
			}
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
// The verdict reflects the Open-time view (see the Log contract): an
// out-of-band foreign append after Open is not in it — one Log per file.
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

// parsedLine is one accepted durable line. Unlike ledger.ParsedLine it does
// NOT retain Raw/Doc: nothing re-derives bytes from parsed lines here (the
// writer re-reads the whole file, see Append), so carrying them would only
// invite wrong assumptions about byte-level rebuilds (R9 F6).
type parsedLine struct {
	Event Entry
}

// loadLines parses the durable JSONL form. The bool reports a TOLERATED torn
// tail: the final line lacked a newline and did not decode into a conformant
// entry (unparseable bytes or a phantom shape), so bytes were skipped — the
// caller (Open) must remember it, because appending to a file
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
		// torn tail (interrupted last write) and is tolerated. Any line
		// BEFORE the EOF position that is not a conformant entry is rejected
		// — invalid UTF-8, unparseable bytes, valid JSON that is not an
		// entry object, field-type mismatches, and everything
		// entryShapeError guards (missing keys, empty/null strings,
		// non-numeric seq) — silently skipping any of them would shrink the
		// coverage CheckCoverage accounts for and turn a completeness
		// verdict green on an incomplete record. A durable line is an entry
		// or the file is not loadable.
		atEOF := i == len(raw)
		// valid UTF-8 comes FIRST (ledger/load.go precedent, completed here
		// after evidlog rode only the JSON-classification arm of it — R9
		// F1): Go's json decoder silently replaces invalid bytes with
		// U+FFFD, so an invalid-UTF-8 line would parse "successfully" with
		// laundered keys and the audit record would silently differ from
		// what was written. The writer gate (Append) enforces valid UTF-8,
		// so such a line is provably not a machine write.
		if !utf8.Valid(line) {
			if atEOF {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.MIDFILE_UNPARSEABLE] %s: line at byte offset %d is not valid UTF-8 — a bypass or corrupted write (Go's json decoder would launder it to U+FFFD)", path, lineStart)
		}
		var e Entry
		if json.Unmarshal(line, &e) != nil {
			if atEOF {
				return lines, true, nil
			}
			// Valid JSON is a different audit fact from unparseable bytes —
			// classify by dynamic type (R6 m1: the map-typed probe mislabeled
			// arrays/scalars as unparseable, splitting them from `null` which
			// the doc==nil branch below calls NON_OBJECT_LINE): an object is
			// a field-type mismatch, any other valid JSON is simply not an
			// entry object (ledger/load.go precedent).
			var anyProbe any
			if json.Unmarshal(line, &anyProbe) == nil {
				switch anyProbe.(type) {
				case map[string]any:
					return nil, false, fmt.Errorf("[EVIDLOG.TYPE_MISMATCH] %s: line at byte offset %d is valid JSON but not an entry (field type mismatch) — evidence coverage must not silently shrink", path, lineStart)
				default: // array, string, number, bool
					return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d is valid JSON but not an entry object — a phantom entry must not enter the audit record", path, lineStart)
				}
			}
			return nil, false, fmt.Errorf("[EVIDLOG.MIDFILE_UNPARSEABLE] %s: unparseable line at byte offset %d (before EOF) — evidence coverage must not silently shrink", path, lineStart)
		}
		doc := map[string]any{}
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.UseNumber()
		if dec.Decode(&doc) != nil {
			// Defensively unreachable: the Entry unmarshal above already
			// proved the line is valid JSON (an object or null), and both
			// decode cleanly here. If this ever fires it means the decode
			// paths diverged — non-torn it is the mid-file disease; at the
			// torn position it is tail garbage like any other.
			if atEOF {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.MIDFILE_UNPARSEABLE] %s: unparseable line at byte offset %d (before EOF) — evidence coverage must not silently shrink", path, lineStart)
		}
		if doc == nil {
			if atEOF {
				return lines, true, nil
			}
			return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d is %q, not an entry object — a phantom entry must not enter the audit record", path, lineStart, string(line))
		}
		// Shape: the durable face rides the schema's required set, its
		// minLength:1 on the string fields, and seq's type:integer — and
		// NOTHING else (R5 F5 declares the ride scope here, at the single
		// shared gate; R8 fixed this declaration after the seq-type check
		// made the old "required + minLength only" text false). pattern
		// (at's timestamp shape) and additionalProperties:false stay
		// envelope-face-only. On the READER path, non-integer seq LITERALS
		// never reach this gate — "seq":1e2 / 1.5 fail the Entry decode
		// upstream as TYPE_MISMATCH; the gate's number check guards the
		// null→Seq=0 normalization. On the WRITER path (Append's probe is
		// marshal-of-Entry) seq is integral by construction, so the literal
		// question does not arise there. A `{"seq":1}`-style object that
		// parses cleanly is still a phantom: it would enter the audit record
		// and silently pass the density rule (R3 M1, phantom family).
		if key, why := entryShapeError(doc); key != "" {
			if atEOF {
				return lines, true, nil
			}
			if why == "without" {
				return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d is an object without %q — a durable line is a full entry (seq/tool/selector/caller/at), not a fragment", path, lineStart, key)
			}
			return nil, false, fmt.Errorf("[EVIDLOG.NON_OBJECT_LINE] %s: line at byte offset %d has an empty or null %q — the envelope schema's minLength:1 rides the durable face too", path, lineStart, key)
		}
		lines = append(lines, parsedLine{Event: e})
	}
	return lines, false, nil
}

// entryShapeError is the durable face's entry-shape contract, shared by the
// writer (Append's pre-write gate) and the reader (loadLines) — one table,
// both consumers, so neither side can drift from the other (R5 F1). It
// checks required-key presence, non-empty string values, and that seq is a
// NUMBER (the schema ride scope is declared at the loadLines call site —
// R8: the wording "required-key presence and non-empty string values only"
// went false when the seq-type check landed). Mechanically locked to
// schema/evidlog.schema.json's required list and the Entry struct's json
// tags by TestRequiredKeysLockstep (R4 M-1: the loader table drifted from
// the schema once — selector was missing while the comment claimed
// equality). Returns ("", "") when the shape is conformant; otherwise the
// offending key and "without" | "empty-or-null".
func entryShapeError(doc map[string]any) (string, string) {
	for _, k := range requiredEntryKeys {
		v, has := doc[k]
		if !has {
			return k, "without"
		}
		if k == "seq" {
			// seq must be a NUMBER (json.Number on the reader's UseNumber
			// path, float64 on Append's probe path). A JSON null would
			// otherwise unmarshal into a silent Seq=0 and enter coverage
			// accounting as a legal entry — the phantom doctrine does not
			// allow that normalization (R7).
			switch v.(type) {
			case float64, json.Number:
				// ok
			default:
				return k, "empty-or-null"
			}
			continue
		}
		s, isStr := v.(string)
		if !isStr || s == "" {
			return k, "empty-or-null"
		}
	}
	return "", ""
}

// conformantLine reports whether a raw line would survive loadLines intact —
// the same ladder (UTF-8, entry decode, object shape, entryShapeError) with
// no torn-tail tolerance. Used by Append's byte-level re-check on a final
// line without a newline (R10 MAJOR-1 face B).
func conformantLine(line []byte) bool {
	if !utf8.Valid(line) {
		return false
	}
	var e Entry
	if json.Unmarshal(line, &e) != nil {
		return false
	}
	var doc map[string]any
	if json.Unmarshal(line, &doc) != nil || doc == nil {
		return false
	}
	k, _ := entryShapeError(doc)
	return k == ""
}

// lastDurableSeq extracts the seq of the last non-empty line in the durable
// form (ok=false when no such line exists or the line carries no numeric
// seq — the caller refuses on !ok). Used by Append's seq-continuity
// re-check (R11).
func lastDurableSeq(existing []byte) (int, bool) {
	for start := len(existing); start > 0; {
		end := start
		start = bytes.LastIndexByte(existing[:start-1], '\n') + 1
		line := existing[start:end]
		line = bytes.TrimSuffix(line, []byte("\n"))
		if len(line) == 0 {
			continue
		}
		var doc map[string]any
		if json.Unmarshal(line, &doc) != nil || doc == nil {
			return 0, false
		}
		// plain Unmarshal produces float64 for numbers (json.Number would
		// need UseNumber, which this path does not use) — the json.Number
		// case below was dead code and is gone (R11 inner MINOR-3).
		// A non-integer seq (1.5 / 1e2 literals are the only way one gets
		// here — the loader rejects them upstream) is never a legal durable
		// state: report !ok so the caller's precise arm fires instead of a
		// silently truncated comparison (R11 inner MINOR-1 — the
		// truncation-preserving blind spot).
		if f, isNum := doc["seq"].(float64); isNum {
			if f != math.Trunc(f) {
				return 0, false
			}
			return int(f), true
		}
		return 0, false
	}
	return 0, false
}

// requiredEntryKeys is the shape table above; order matches the schema's
// required list (descriptive — the lockstep compares sets); "seq" is the
// only non-string key (writer-allocated int).
var requiredEntryKeys = []string{"seq", "tool", "selector", "caller", "at"}

func contains(hay []string, needle string) bool {
	for _, h := range hay {
		if h == needle {
			return true
		}
	}
	return false
}
