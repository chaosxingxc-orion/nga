package ledger

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"unicode/utf8"
)

// ParsedLine is one complete durable-form line in three views: the raw bytes
// (what a rewrite must preserve byte-for-byte), the raw document (what the
// schema validates — the on-disk truth, decoded with UseNumber so integers
// survive the map domain exactly), and the typed event (the replay
// projection). A line yields a ParsedLine only when it parses in BOTH views.
type ParsedLine struct {
	Raw   []byte
	Doc   map[string]any
	Event Event
}

// ParseLines returns the parsed lines of a JSONL byte stream, or an error
// naming a line that is not a machine write. The boundary rule: a complete
// line parses in BOTH views. Two forms of non-event content are tolerated,
// and a torn tail is REPORTED (P1-2, 2026-11-03 doctrine convergence): the
// torn tail — an unparseable remnant at EOF WITHOUT a trailing newline (an
// externally damaged file; under the machine's own temp+rename protocol a
// crash leaves the old or the new file, never a partial line) — sets the
// returned flag so callers can refuse mutations instead of healing over
// damage. Empty lines (zero-byte segments anywhere) carry no audit data.
// Any other unparseable line (mid-file, or newline-terminated), or a line
// whose JSON parses but whose fields do not fit the event type, is a
// bypass or corruption: an append-only audit ledger must not silently
// drop (and a rewrite must not silently erase) audit data — it fails.
// This is the ONE boundary definition for the durable form — the loader,
// the load-time checker, and the append-path rewrite all consume it.
func ParseLines(raw []byte) ([]ParsedLine, bool, error) {
	var lines []ParsedLine
	torn := false
	lineStart := 0
	for i := 0; i <= len(raw); i++ {
		if i != len(raw) && raw[i] != '\n' {
			continue
		}
		line := raw[lineStart:i]
		atEOF := i == len(raw) // the segment not terminated by a newline
		lineStart = i + 1
		if len(line) == 0 {
			continue
		}
		// valid UTF-8 comes FIRST: Go's json decoder silently replaces
		// invalid bytes with U+FFFD, so an invalid-UTF-8 line would parse
		// "successfully" with laundered keys. The machine's own writes are
		// always valid UTF-8 (the gate enforces it), so such a line is
		// provably not a machine write.
		if !utf8.Valid(line) {
			if atEOF {
				torn = true
				continue // torn tail: tolerated at EOF without a newline, reported via the flag
			}
			return nil, false, fmt.Errorf("durable form line is not valid UTF-8 — a bypass or corrupted write, not machine output (Go's json decoder would launder it to U+FFFD)")
		}
		var ev Event
		// R14' M-1 fix: strict shape judgment (the evidlog entryShapeError
		// twin — P1-2 claimed "unified doctrine" but adopt's typed view was
		// non-strict: a legal JSON object with NO event fields — e.g.
		// {"note":"out-of-band"} — unmarshal-OK'd into a zero-value Event,
		// passed both write-time gates (tornNow=false, STALE_WRITER on the
		// last REAL line's seq), got preserved by the rebuild, and poisoned
		// the file for the next Open. DisallowUnknownFields + the two
		// required-field probes close the phantom-object form; the schema
		// check in checkLoaded remains the full-field authority.
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.DisallowUnknownFields()
		typedOK := dec.Decode(&ev) == nil && ev.ArbitrationSeq >= 0 && ev.EventType != "" && ev.Identity.OperationID != ""
		doc, docErr := decodeUseNumber(line)
		if typedOK && docErr == nil && doc != nil {
			lines = append(lines, ParsedLine{Raw: line, Doc: doc, Event: ev})
			continue
		}
		if atEOF && docErr != nil {
			torn = true
			continue // torn tail: externally damaged remnant at EOF only, reported via the flag
		}
		if docErr != nil {
			return nil, false, fmt.Errorf("durable form has an unparseable line where no torn tail can be (not the last byte range) — a bypass or corrupted write, not machine output")
		}
		return nil, false, fmt.Errorf("durable form line is valid JSON but not an event (field type mismatch or missing required fields: event_type/arbitration_seq/identity.operation_id) — a bypass or corrupted write, not machine output")
	}
	return lines, torn, nil
}

// LoadDocument reads a durable-form file into its parsed lines, plus
// whether the byte stream ended in a torn tail (external damage — the
// caller decides what to refuse on it). A missing file is an empty
// document (a fresh machine's state), any other error fails.
func LoadDocument(path string) ([]ParsedLine, bool, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return ParseLines(raw)
}

// decodeUseNumber parses one line into a raw map with UseNumber (R16 数值域
// 章程): integers survive as json.Number so the literal gate stays decidable
// and exact — a plain float64 map would fold 2^53-adjacent integers and make
// 0.0 indistinguishable from 0.
func decodeUseNumber(line []byte) (map[string]any, error) {
	dec := json.NewDecoder(bytes.NewReader(line))
	dec.UseNumber()
	var doc map[string]any
	if err := dec.Decode(&doc); err != nil {
		return nil, err
	}
	return doc, nil
}
