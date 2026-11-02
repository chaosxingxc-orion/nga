package evidlog

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
)

func open(t *testing.T) *Log {
	t.Helper()
	l, err := Open(filepath.Join(t.TempDir(), "evid.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	return l
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

// phantomShapeCases is the SINGLE shared phantom-shape table — one table,
// two consumers (R8 inner-review F1, the same move as R5 F1): every shape
// IN THIS LIST — each of them rejected by the mid-file ladder — is pinned
// by TestNullLineRejected (expected key) AND pinned as tolerated tail
// garbage by TestTornPhantomShapesTolerated. A list shape can no longer
// exist on one face without the other: on the two tests' pin faces, the
// "all of these shapes" class of claim is structurally equal to the pins
// (comments elsewhere in the file can still overclaim — that stays a
// review target).
var phantomShapeCases = []struct {
	name string
	line []byte
	want string // expected neutral key at the mid-file position
}{
	{"invalid UTF-8", []byte("{\"seq\":1,\"tool\":\"ba\xffnk.fetch\",\"selector\":\"r\",\"caller\":\"s\",\"at\":\"y\"}"), "EVIDLOG.MIDFILE_UNPARSEABLE"},
	{"bare null", []byte(`null`), "EVIDLOG.NON_OBJECT_LINE"},
	{"array line", []byte(`[1,2]`), "EVIDLOG.NON_OBJECT_LINE"},
	{"scalar line", []byte(`42`), "EVIDLOG.NON_OBJECT_LINE"},
	{"string line", []byte(`"hello"`), "EVIDLOG.NON_OBJECT_LINE"},
	{"bool line", []byte(`true`), "EVIDLOG.NON_OBJECT_LINE"},
	{"fragment with seq", []byte(`{"seq":9}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"fragment missing selector+caller", []byte(`{"seq":1,"tool":"x"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"missing caller", []byte(`{"seq":1,"tool":"x","selector":"r","at":"y"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"missing selector", []byte(`{"seq":1,"tool":"x","caller":"s","at":"y"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"null caller", []byte(`{"seq":1,"tool":"x","selector":"r","caller":null,"at":"y"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"empty selector", []byte(`{"seq":1,"tool":"x","selector":"","caller":"s","at":"y"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"null seq", []byte(`{"seq":null,"tool":"x","selector":"r","caller":"s","at":"y"}`), "EVIDLOG.NON_OBJECT_LINE"},
	{"seq type mismatch", []byte(`{"seq":"x","tool":"x","selector":"r","caller":"s","at":"y"}`), "EVIDLOG.TYPE_MISMATCH"},
	{"tool type mismatch", []byte(`{"seq":1,"tool":123,"selector":"r","caller":"s","at":"y"}`), "EVIDLOG.TYPE_MISMATCH"},
}

// TestNullLineRejected drives every shared phantom shape through the
// mid-file position and requires its per-case expected key (R7: the
// previous loop asserted one key for every case, so the TYPE_MISMATCH arm
// could be deleted and the suite stayed green — the per-case want column is
// what keeps each dispatch arm pinned). Legal-JSON-but-not-an-entry shapes
// reject with EVIDLOG.NON_OBJECT_LINE; object rows whose field types
// mismatch the Entry shape reject with EVIDLOG.TYPE_MISMATCH.
func TestNullLineRejected(t *testing.T) {
	l1, _ := json.Marshal(Entry{Seq: 0, Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	l2, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	for _, tc := range phantomShapeCases {
		path := filepath.Join(t.TempDir(), "evid.jsonl")
		var body []byte
		body = append(body, l1...)
		body = append(body, '\n')
		body = append(body, tc.line...)
		body = append(body, '\n')
		body = append(body, l2...)
		body = append(body, '\n')
		if err := os.WriteFile(path, body, 0o644); err != nil {
			t.Fatal(err)
		}
		if _, err := Open(path); err == nil {
			t.Fatalf("%s: phantom line absorbed into the audit record", tc.name)
		} else if !strings.Contains(err.Error(), tc.want) {
			t.Fatalf("%s: got %v, want key %s", tc.name, err, tc.want)
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
	if err := l2.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "2026-11-01T10:02:00Z"}); err == nil {
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
	if err := l3.Append(Entry{Tool: "t", Selector: "s=2", Caller: "s2", At: "2026-11-01T10:02:00Z"}); err != nil {
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

// TestRequiredKeysLockstep mechanically locks the durable face's key table
// to its two siblings (R4 M-1 — the table drifted once: selector was missing
// while the comment claimed equality): schema/evidlog.schema.json's
// entries.items.required list, the shared requiredEntryKeys (one table, both consumers since R5 F1), and the Entry
// struct's json tags (minus the omitempty optional) must agree as sets.
func TestRequiredKeysLockstep(t *testing.T) {
	schemaRaw, err := os.ReadFile(filepath.Join(filepath.Dir(SchemaPath), "evidlog.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	var schemaDoc struct {
		Properties struct {
			Entries struct {
				Items struct {
					Properties map[string]json.RawMessage `json:"properties"`
					Required   []string                   `json:"required"`
				} `json:"items"`
			} `json:"entries"`
		} `json:"properties"`
	}
	if err := json.Unmarshal(schemaRaw, &schemaDoc); err != nil {
		t.Fatal(err)
	}
	schemaKeys := map[string]bool{}
	for _, k := range schemaDoc.Properties.Entries.Items.Required {
		schemaKeys[k] = true
	}
	// Fourth face (R5 F2): the OPTIONAL surface — schema properties must
	// equal the Entry struct's FULL json tag set (including omitempty). A
	// Go field the schema lacks, or a schema property no Go field writes,
	// is the same drift family, silent because nothing consumes either side.
	propKeys := map[string]bool{}
	for k := range schemaDoc.Properties.Entries.Items.Properties {
		propKeys[k] = true
	}
	allTags := map[string]bool{}
	ety := reflect.TypeOf(Entry{})
	for i := 0; i < ety.NumField(); i++ {
		allTags[strings.Split(ety.Field(i).Tag.Get("json"), ",")[0]] = true
	}
	if !reflect.DeepEqual(propKeys, allTags) {
		t.Fatalf("optional-surface lockstep broken:\nschema properties %v\nEntry json tags %v", sortedKeys(propKeys), sortedKeys(allTags))
	}
	loaderKeys := map[string]bool{}
	for _, k := range requiredEntryKeys {
		loaderKeys[k] = true
	}
	entryKeys := map[string]bool{}
	et := reflect.TypeOf(Entry{})
	for i := 0; i < et.NumField(); i++ {
		tag := et.Field(i).Tag.Get("json")
		name := strings.Split(tag, ",")[0]
		if strings.Contains(tag, ",omitempty") {
			continue // optional by construction
		}
		entryKeys[name] = true
	}
	for name, want := range map[string]map[string]bool{"schema required": schemaKeys, "Entry json tags": entryKeys} {
		if !reflect.DeepEqual(loaderKeys, want) {
			t.Fatalf("%s lockstep broken:\nloader  %v\n%s %v", name, sortedKeys(loaderKeys), name, sortedKeys(want))
		}
	}
}

func sortedKeys(m map[string]bool) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	return ks
}

// TestAppendRejectsUnwritableEntry pins the writer-side shape gate (R5 F1):
// an entry the loader would reject (empty Tool, or the zero value) must fail
// at the Append that produced it — not at the next Open, far from the guilty
// call, with the log bricked in between. After refusals the writer still
// works and the file stays loadable and dense.
func TestAppendRejectsUnwritableEntry(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "", Selector: "s", Caller: "c", At: "a"}); err == nil {
		t.Fatal("Append accepted an entry the loader would reject — the log is bricked at the next Open")
	} else if !strings.Contains(err.Error(), "EVIDLOG.INVALID_ENTRY") {
		t.Fatalf("refusal lacks the neutral key: %v", err)
	}
	if err := l.Append(Entry{}); err == nil {
		t.Fatal("zero-value entry accepted")
	}
	// dual-field violation (R13 F5): the ordered-slice form must report
	// the FIRST field deterministically — a map-iteration regression would
	// flip between "tool" and "selector" run to run
	if err := l.Append(Entry{Tool: "ba\xffnk", Selector: "se\xfflect", Caller: "c", At: "a"}); err == nil {
		t.Fatal("dual-field invalid-UTF-8 entry accepted")
	} else if !strings.Contains(err.Error(), `field "tool"`) {
		t.Fatalf("dual-field violation did not report the first field: %v", err)
	}
	// invalid UTF-8 (R9 F1 write side): the json encoder would launder it to
	// U+FFFD, making the durable form diverge from the caller's copy — the
	// gate must refuse before any bytes are produced.
	if err := l.Append(Entry{Tool: "ba\xffnk.fetch", Selector: "s", Caller: "c", At: "a"}); err == nil {
		t.Fatal("Append accepted an invalid-UTF-8 field — the durable write would be laundered")
	} else if !strings.Contains(err.Error(), "EVIDLOG.INVALID_ENTRY") {
		t.Fatalf("UTF-8 refusal lacks the neutral key: %v", err)
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "z"}); err != nil {
		t.Fatalf("valid append refused after gate rejections: %v", err)
	}
	l2, err := Open(path)
	if err != nil {
		t.Fatalf("file not loadable after gate refusals: %v", err)
	}
	if es := l2.Entries(); len(es) != 1 || es[0].Seq != 0 {
		t.Fatalf("unexpected entries after refusals: %+v", es)
	}
}

// TestDurableAcceptsExtraFieldLine pins the deliberate asymmetry (R9 F3):
// the durable face does NOT ride the schema's additionalProperties:false —
// a line carrying an extra field loads fine here, while the envelope face
// (CheckDoc) rejects the same document. This is a declared ride-scope
// decision (see the loadLines shape-gate comment), not drift: this test
// exists so the acceptance cannot silently flip in either direction.
func TestDurableAcceptsExtraFieldLine(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l1, _ := json.Marshal(Entry{Seq: 0, Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	extra := []byte(`{"seq":1,"tool":"bureau.q","selector":"subj=x","caller":"s2","at":"2026-11-01T10:01:00Z","fabricated":"counterclaim"}`)
	var body []byte
	body = append(body, l1...)
	body = append(body, '\n')
	body = append(body, extra...)
	body = append(body, '\n')
	if err := os.WriteFile(path, body, 0o644); err != nil {
		t.Fatal(err)
	}
	l2, err := Open(path)
	if err != nil {
		t.Fatalf("extra-field line rejected on the durable face (ride scope says additionalProperties is envelope-only): %v", err)
	}
	if len(l2.Entries()) != 2 {
		t.Fatalf("unexpected entries: %d", len(l2.Entries()))
	}
	// The same content reorganized as an envelope document IS rejected by
	// the envelope face — the two faces intentionally disagree on this
	// shape. Construction must be plain decoded JSON values (R9 inner
	// review: json.RawMessage's underlying []byte makes the v6 validator
	// reject ANY document, so the old pin was vacuous — it passed even with
	// additionalProperties:false deleted from the schema). Two directions:
	// the clean twin must PASS (attribute the rejection to the extra field,
	// not to a broken construction) and the extra-field doc must FAIL.
	envelope := func(entries ...json.RawMessage) map[string]any {
		raw, err := json.Marshal(map[string]any{"evidlog_version": "0.1.0", "entries": entries})
		if err != nil {
			t.Fatal(err)
		}
		var doc map[string]any
		if err := json.Unmarshal(raw, &doc); err != nil {
			t.Fatal(err)
		}
		return doc
	}
	clean := []byte(`{"seq":1,"tool":"bureau.q","selector":"subj=x","caller":"s2","at":"2026-11-01T10:01:00Z"}`)
	if errs := CheckDoc(envelope(json.RawMessage(l1), clean)); len(errs) != 0 {
		t.Fatalf("clean envelope twin rejected — construction broken, pin vacuous: %v", errs)
	}
	if errs := CheckDoc(envelope(json.RawMessage(l1), extra)); len(errs) == 0 {
		t.Fatal("envelope face accepted an extra-field document — additionalProperties:false disappeared")
	}
}

// TestNullSeqFirstLineRejected pins the scenario the seq-type check exists
// for (R8: the mid-file table case never exercises it — there the pre-fix
// behavior was SEQ_GAP, not silent absorption): a `{"seq":null,...}` FIRST
// line normalizes to Seq=0, so pre-fix the file loaded "fine" and the ghost
// tool entered coverage accounting. The check must reject it at index 0.
func TestNullSeqFirstLineRejected(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	ghost := []byte(`{"seq":null,"tool":"ghost.tool","selector":"hidden=1","caller":"s2","at":"2026-11-01T10:00:00Z"}`)
	l2, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	var body []byte
	body = append(body, ghost...)
	body = append(body, '\n')
	body = append(body, l2...)
	body = append(body, '\n')
	if err := os.WriteFile(path, body, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Open(path); err == nil {
		t.Fatal("null-seq ghost first line absorbed as Seq=0 — phantom doctrine violated at the exact index the check exists for")
	} else if !strings.Contains(err.Error(), "EVIDLOG.NON_OBJECT_LINE") {
		t.Fatalf("rejection lacks the neutral key: %v", err)
	}
}

// TestTornPhantomShapesTolerated is the torn-tail consumer of the shared
// phantom-shape table: every shape the mid-file ladder rejects, WITHOUT a
// trailing newline at EOF, is tolerated at load (skipped), remembered as
// torn (Append refuses), and must stay tolerated if the loader is ever
// refactored. Same list, other face — TestNullLineRejected and this test
// cannot drift apart by construction.
func TestTornPhantomShapesTolerated(t *testing.T) {
	for _, tc := range phantomShapeCases {
		path := filepath.Join(t.TempDir(), "evid.jsonl")
		l, err := Open(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, append(mustRead(t, path), tc.line...), 0o644); err != nil {
			t.Fatal(err)
		}
		l2, err := Open(path)
		if err != nil {
			t.Fatalf("tail %s (%s): phantom shape at the torn-tail position must be tolerated: %v", tc.line, tc.name, err)
		}
		if len(l2.Entries()) != 1 {
			t.Fatalf("tail %s (%s): phantom entered the record: %d entries", tc.line, tc.name, len(l2.Entries()))
		}
		if err := l2.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "z"}); err == nil || !strings.Contains(err.Error(), "EVIDLOG.TORN_TAIL_BLOCKED") {
			t.Fatalf("tail %s (%s): torn-tail memory lost: %v", tc.line, tc.name, err)
		}
	}
}

// TestCoverageTornTailNotGreen pins the verdict face of the torn-tail
// contract (R4 M-2): on a log whose tail was skipped at load, CheckCoverage
// must refuse a green verdict even when the visible entries match the
// declaration — the skipped tail may hold an unaccounted query. TornTail
// carries the reason so callers can distinguish it from a coverage miss.
func TestCoverageTornTailNotGreen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	torn, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=hidden"})
	if err := os.WriteFile(path, append(mustRead(t, path), torn[:len(torn)-5]...), 0o644); err != nil {
		t.Fatal(err)
	}
	l2, err := Open(path) // tolerated at load, tail remembered
	if err != nil {
		t.Fatal(err)
	}
	rep := CheckCoverage(l2, Declaration{QueriedTool: "bank.fetch", Selector: "acct=1"})
	if rep.OK {
		t.Fatal("coverage verdict green on an incomplete record — the skipped tail is unblessed evidence")
	}
	if !rep.TornTail {
		t.Fatalf("OK=false without the TornTail reason: %+v", rep)
	}
}

// (TestTornNullToleratedAtLoad from R4 m-5 was superseded by
// TestTornPhantomShapesTolerated, whose per-case table includes the bare
// null tail this test pinned alone.)

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

// TestCoverageOtherToolUnaccounted pins the other-tool face of the coverage
// diff (R10 m2: the Unaccounted branch for entries OUTSIDE the declared tool
// had no pin — deleting it kept the suite green, yet an investigator
// querying a DIFFERENT tool than declared is the core coverage-audit
// scenario).
func TestCoverageOtherToolUnaccounted(t *testing.T) {
	l := open(t)
	l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	l.Append(Entry{Tool: "credit-bureau.query", Selector: "subj=9", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	rep := CheckCoverage(l, Declaration{QueriedTool: "bank.fetch", Selector: "acct=1"})
	if rep.OK {
		t.Fatal("other-tool query not flagged — the coverage audit is blind to undeclared tools")
	}
	found := false
	for _, u := range rep.Unaccounted {
		if strings.Contains(u, "credit-bureau.query") {
			found = true
		}
	}
	if !found {
		t.Fatalf("Unaccounted lacks the other-tool entry: %+v", rep)
	}
}

// TestAppendRechecksEvolvingTail pins the byte-level torn-tail re-check
// (R10 MAJOR-1 face B): tornTail is Open-time memory; a foreign writer may
// append unparseable tail bytes AFTER Open. The Append must refuse — the
// splice would brick the next Open, and the refusal must happen while it is
// still this writer's own decision. A conformant no-newline last line (the
// legal face) still appends fine.
func TestAppendRechecksEvolvingTail(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	cleanOpenState := mustRead(t, path) // the Open-time content, for the legal face below
	// foreign aborted append AFTER Open: l.tornTail is false (Open-time)
	if err := os.WriteFile(path, append(mustRead(t, path), []byte(`{"seq":`)...), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "z"}); err == nil {
		t.Fatal("Append spliced over an evolved torn tail — the log is bricked at the next Open")
	} else if !strings.Contains(err.Error(), "EVIDLOG.TORN_TAIL_BLOCKED") {
		t.Fatalf("evolved-tail refusal lacks the neutral key: %v", err)
	}
	// foreign VALID line (with newline) AFTER Open (R11 singularity): the
	// splice would fix a duplicate seq into the file — the seq-continuity
	// re-check must refuse in the guilty caller (STALE_SEQ). Reset to the
	// clean Open-time content FIRST (the leftover garbage from the previous
	// sub-case would fuse with the ghost line into a seq-is-an-object row,
	// which trips the !ok arm instead of this continuity arm), so this case
	// genuinely exercises the continuity comparison.
	if err := os.WriteFile(path, cleanOpenState, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, append(mustRead(t, path), []byte("{\"seq\":1,\"tool\":\"ghost.q\",\"selector\":\"g\",\"caller\":\"s2\",\"at\":\"x\"}\n")...), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "z"}); err == nil {
		t.Fatal("stale instance wrote a duplicate seq — false success poisoning the durable form")
	} else if !strings.Contains(err.Error(), "EVIDLOG.STALE_SEQ") {
		t.Fatalf("stale-seq refusal lacks the neutral key: %v", err)
	}
	// foreign ERASE face (R11 inner MAJOR-1): the file is truncated to zero
	// bytes after Open, and the stale view's next Append must refuse — a
	// bare len>0 guard would let a stale Seq=1 write itself in as the new
	// first line and brick the log at the next Open.
	if err := os.WriteFile(path, nil, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s=1", Caller: "s2", At: "z"}); err == nil {
		t.Fatal("stale instance wrote onto an erased file — false success resetting the log base")
	} else if !strings.Contains(err.Error(), "EVIDLOG.STALE_SEQ") {
		t.Fatalf("erase-face refusal lacks the neutral key: %v", err)
	}
	// legal face: a CONFORMANT last line without a newline survives splicing
	// — reset the file to the clean Open-time content first (the garbage
	// tail above would fuse with the appended line into one diseased line,
	// which the gate correctly refuses), then append through a FRESH Open:
	// the single-instance contract keeps the stale l out of the file after
	// foreign evolution (its seq no longer knows about the good line).
	if err := os.WriteFile(path, cleanOpenState, 0o644); err != nil {
		t.Fatal(err)
	}
	good, _ := json.Marshal(Entry{Seq: 1, Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"})
	if err := os.WriteFile(path, append(mustRead(t, path), good...), 0o644); err != nil {
		t.Fatal(err)
	}
	l4, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l4.Append(Entry{Tool: "t", Selector: "s=2", Caller: "s2", At: "z"}); err != nil {
		t.Fatalf("conformant no-newline last line refused: %v", err)
	}
	if l3, err := Open(path); err != nil {
		t.Fatalf("reopened log rejected after legal-face append: %v", err)
	} else if len(l3.Entries()) != 3 {
		t.Fatalf("unexpected entries: %d", len(l3.Entries()))
	}
}

// TestConformantLineSharesLadder pins the third consumer of the shared
// table (R10 inner MINOR-1): conformantLine claims to be "the same ladder"
// as loadLines — every phantom shape must read NOT conformant through it,
// or the Append byte-level re-check would splice lines the loader rejects.
// A positive twin (a conformant line reads true) guards the over-reject
// direction.
func TestConformantLineSharesLadder(t *testing.T) {
	for _, tc := range phantomShapeCases {
		if conformantLine(tc.line) {
			t.Fatalf("%s: conformantLine accepted a shape the loader ladder rejects", tc.name)
		}
	}
	good, err := json.Marshal(Entry{Seq: 1, Tool: "t", Selector: "s", Caller: "c", At: "a"})
	if err != nil {
		t.Fatal(err)
	}
	if !conformantLine(good) {
		t.Fatalf("conformantLine rejected a well-formed entry: %s", good)
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

// TestTruncationBlindSpot pins the Append gate's rejection of float-syntax
// foreign lines (R16 数值域章程; born in R12 as the truncation blind spot,
// rebuilt R13, narrowed to the literal-gate form R16): the log holds
// [seq0, seq1], a foreign writer REPLACES the last line with a
// float-syntax twin (1.5 / 1e0), and the stale view's Append (e.Seq=2)
// must refuse — lastDurableSeq reports !ok for any non-integer literal.
func TestTruncationBlindSpot(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "bureau.q", Selector: "subj=x", Caller: "s2", At: "2026-11-01T10:01:00Z"}); err != nil {
		t.Fatal(err) // l.seq is now 1 — the next Append allocates e.Seq=2
	}
	// foreign writer replaces the seq=1 line with a float-syntax twin —
	// two forms below: fractional (1.5) and exponent-notation integral
	// (1e0, carrying the last seq's VALUE so a weakened gate that accepted
	// float syntax would satisfy the arithmetic and false-succeed). R16
	// 数值域章程: no float syntax is a legal durable seq — Int64 rejects
	// both classes.
	first, _ := json.Marshal(Entry{Seq: 0, Tool: "bank.fetch", Selector: "acct=1", Caller: "s2", At: "2026-11-01T10:00:00Z"})
	// The exponent-notation form must carry the VALUE of the last seq (1e0
	// = 1) so a weakened gate accepting float syntax would false-succeed —
	// a mismatched value would be rejected by the plain continuity arm
	// either way (the vacuity form BOTH blank reviewers found in R12).
	for _, tail := range []string{
		`{"seq":1.5,"tool":"frac.q","selector":"f","caller":"s2","at":"x"}`,
		`{"seq":1e0,"tool":"exp.q","selector":"e","caller":"s2","at":"x"}`,
	} {
		var body []byte
		body = append(body, first...)
		body = append(body, '\n')
		body = append(body, tail...)
		body = append(body, '\n')
		if err := os.WriteFile(path, body, 0o644); err != nil {
			t.Fatal(err)
		}
		if err := l.Append(Entry{Tool: "t", Selector: "s=2", Caller: "s2", At: "z"}); err == nil {
			t.Fatalf("foreign seq %s passed the continuity arm — false success bricking the next Open", tail)
		} else if !strings.Contains(err.Error(), "EVIDLOG.STALE_SEQ") {
			t.Fatalf("foreign seq %s: refusal lacks the neutral key: %v", tail, err)
		}
	}
}

// TestUTF8GateFieldCoverage pins the UTF-8 write-side gate through the REAL
// Append, per field (R14 A-M1, adopt's TestRequestUTF8ScanIsComplete form):
// reflection walks the Entry struct's string fields and drives each field
// individually with an invalid-UTF-8 value through Append — the gate must
// refuse with EVIDLOG.INVALID_ENTRY naming THAT field. This is a two-way
// lock the previous literal-map comparison was not: a gate row dropped from
// the production slice makes its field's probe pass silently-green→RED
// (the A-position mutation reproduced: deleting the result_ref row kept
// the whole suite green); a new Entry string field without a gate row
// gets a probe naming it whose Append is ACCEPTED → the loop fails red
// at the acceptance branch.
func TestUTF8GateFieldCoverage(t *testing.T) {
	ety := reflect.TypeOf(Entry{})
	for i := 0; i < ety.NumField(); i++ {
		f := ety.Field(i)
		if f.Type.Kind() != reflect.String {
			continue
		}
		name := strings.Split(f.Tag.Get("json"), ",")[0]
		path := filepath.Join(t.TempDir(), "evid.jsonl")
		l, err := Open(path)
		if err != nil {
			t.Fatal(err)
		}
		entry := Entry{Tool: "t", Selector: "s", Caller: "c", At: "a"}
		reflect.ValueOf(&entry).Elem().Field(i).SetString("ba\xffnk")
		if err := l.Append(entry); err == nil {
			t.Fatalf("field %s: invalid-UTF-8 value passed the write-side gate — laundered into the durable form", name)
		} else if !strings.Contains(err.Error(), "EVIDLOG.INVALID_ENTRY") {
			t.Fatalf("field %s: refusal lacks the neutral key: %v", name, err)
		} else if !strings.Contains(err.Error(), fmt.Sprintf("field %q", name)) {
			t.Fatalf("field %s: refusal does not name the offending field: %v", name, err)
		}
	}
}

// TestZeroValueLogAppendRefused pins the NOT_OPEN guard (R14 A-m2: the
// guard had no test — deleting it and the opened field kept the suite
// green; a zero-value Log's first Append would emit Seq=1, violating
// dense-from-0 in the in-memory view (the durable form is never reached
// — the zero value's path is empty, per the Log contract).
func TestZeroValueLogAppendRefused(t *testing.T) {
	l := &Log{}
	if err := l.Append(Entry{Tool: "t", Selector: "s", Caller: "c", At: "a"}); err == nil {
		t.Fatal("zero-value Log accepted an Append — first entry would be Seq=1, violating dense-from-0 in the in-memory view")
	} else if !strings.Contains(err.Error(), "EVIDLOG.NOT_OPEN") {
		t.Fatalf("refusal lacks the neutral key: %v", err)
	}
}

// TestSeqExhaustionRefuses pins the counter-domain guard (R13 B-m4): at
// MaxInt64 the writer refuses instead of wrapping — a wrapped seq would
// emit a file the loader's density rule immediately rejects.
func TestSeqExhaustionRefuses(t *testing.T) {
	l := open(t)
	l.seq = math.MaxInt64
	if err := l.Append(Entry{Tool: "t", Selector: "s", Caller: "c", At: "a"}); err == nil {
		t.Fatal("Append wrapped the seq domain — the loader would reject the writer's own file")
	} else if !strings.Contains(err.Error(), "EVIDLOG.SEQ_EXHAUSTED") {
		t.Fatalf("exhaustion refusal lacks the neutral key: %v", err)
	}
}

// TestWhitespaceOnlyFileAppend pins the whitespace-only + fresh-view arm
// (R15 B-1): a file of only blank lines is the loader's EMPTY log (empty
// lines heal away) — a fresh Open's first Append must treat it exactly
// like a zero-byte file, not refuse it forever with a diseased-file
// message. The erase-with-junk + stale-view refusal stays pinned by
// TestAppendRechecksEvolvingTail.
func TestWhitespaceOnlyFileAppend(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	if err := os.WriteFile(path, []byte("\n\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(l.Entries()) != 0 {
		t.Fatalf("whitespace-only file loaded entries: %d", len(l.Entries()))
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s=1", Caller: "c", At: "a"}); err != nil {
		t.Fatalf("fresh view's first append onto a whitespace-only file refused (loader semantics = empty log, same as zero bytes): %v", err)
	}
	if l2, err := Open(path); err != nil {
		t.Fatalf("file not loadable after the append: %v", err)
	} else if len(l2.Entries()) != 1 || l2.Entries()[0].Seq != 0 {
		t.Fatalf("unexpected entries: %+v", l2.Entries())
	}
}

// TestUncuredBlankLineRefused pins the NOT-exempt face of the R15 B-1
// exemption (R15 inner M1): a file whose lines are blank but non-empty
// (" \n") is one the loader REJECTS (it only heals zero-length lines) —
// the fresh view's first Append must refuse it (STALE_SEQ !ok arm), not
// ride the exemption and splice a write the loader cannot reload (the
// TrimSpace predicate used to brick exactly this).
func TestUncuredBlankLineRefused(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evid.jsonl")
	l, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(" \n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := l.Append(Entry{Tool: "t", Selector: "s", Caller: "c", At: "a"}); err == nil {
		t.Fatal("blank-but-nonempty line rode the empty-log exemption — the loader rejects this file and the write would brick it")
	} else if !strings.Contains(err.Error(), "EVIDLOG.STALE_SEQ") {
		t.Fatalf("refusal lacks the neutral key: %v", err)
	}
}
