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
// line parses in BOTH views. Two forms of non-event content are tolerated: a
// torn tail — an unparseable remnant at EOF WITHOUT a trailing newline (a
// conservative compatibility boundary for externally-damaged files; under
// the machine's own temp+rename protocol a crash leaves the old or the new
// file, never a partial line) — and empty lines (zero-byte segments
// anywhere, carrying no audit data, healing away on rewrite). Any other
// unparseable line (mid-file, or newline-terminated), or a line whose JSON
// parses but whose fields do not fit the event type, is a bypass or
// corruption: an append-only audit ledger must not silently drop (and a
// rewrite must not silently erase) audit data — it fails. This is the ONE
// boundary definition for the durable form — the loader, the load-time
// checker, and the append-path rewrite all consume it.
func ParseLines(raw []byte) ([]ParsedLine, error) {
	var lines []ParsedLine
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
				continue // torn tail: tolerated at EOF without a newline
			}
			return nil, fmt.Errorf("durable form line is not valid UTF-8 — a bypass or corrupted write, not machine output (Go's json decoder would launder it to U+FFFD)")
		}
		var ev Event
		typedOK := json.Unmarshal(line, &ev) == nil
		doc, docErr := decodeUseNumber(line)
		if typedOK && docErr == nil && doc != nil {
			lines = append(lines, ParsedLine{Raw: line, Doc: doc, Event: ev})
			continue
		}
		if atEOF && docErr != nil {
			continue // torn tail: crash residue, tolerated at EOF only
		}
		if docErr != nil {
			return nil, fmt.Errorf("durable form has an unparseable line where no torn tail can be (not the last byte range) — a bypass or corrupted write, not machine output")
		}
		return nil, fmt.Errorf("durable form line is valid JSON but not an event (field type mismatch) — a bypass or corrupted write, not machine output")
	}
	return lines, nil
}

// LoadDocument reads a durable-form file into its parsed lines. A missing
// file is an empty document (a fresh machine's state), any other error fails.
func LoadDocument(path string) ([]ParsedLine, error) {
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
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
