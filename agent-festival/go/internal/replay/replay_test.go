package replay

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"festival-dev/go/internal/adopt"
	"festival-dev/go/internal/ledger"
)

func loadCase(t *testing.T, name string) *Case {
	t.Helper()
	if SchemaPath == "" {
		t.Fatal("replay-case schema not found")
	}
	raw, err := os.ReadFile(filepath.Join(filepath.Dir(SchemaPath), "examples", "replay", "valid", name))
	if err != nil {
		t.Fatal(err)
	}
	var c Case
	if err := json.Unmarshal(raw, &c); err != nil {
		t.Fatal(err)
	}
	return &c
}

// TestRecomputeIsNotPlayback is the machine-checked form of pre-registered
// attack surface B (piece-6 priors): a pure PLAYBACK checker — one that
// "verifies" by returning the record as its own recomputation — matches the
// tampered-conclusion fixture and catches nothing, while the real Replay
// recomputes by driving the production machine and diverges at the tampered
// event. Recomputation, not playback.
func TestRecomputeIsNotPlayback(t *testing.T) {
	c := loadCase(t, "tampered-conclusion.json")

	// the playback strawman: "recomputation" == the record, byte for byte
	playbackFidelity := "match" // a playback checker always matches by construction
	if playbackFidelity != string(Match) {
		t.Fatal("strawman misconstructed")
	}

	// the real engine
	rep, err := Replay(c)
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Divergence {
		t.Fatalf("replay fidelity = %q, want divergence — the recomputation degraded into playback", rep.Fidelity)
	}
	if rep.DivergenceAt != 2 {
		t.Fatalf("divergence located at %d, want 2 (the tampered conclusion event)", rep.DivergenceAt)
	}
	// and the tampered record is itself a legal transition: conformance passes
	if rep.Conformance != Pass {
		t.Fatalf("conformance = %q, want pass (completed→failed is legal — only recomputation catches it)", rep.Conformance)
	}
}

// TestReevaluateSubstitutionIsolates pins mode 3: a substitution changes the
// recomputation and the ORIGINAL case is untouched (isolated run).
func TestReevaluateSubstitutionIsolates(t *testing.T) {
	c := loadCase(t, "happy-chain.json")
	orig, _ := json.Marshal(c)
	rep, err := Reevaluate(c, func(sub *Case) {
		// a different model version for the same chain
		for i := range sub.Steps {
			if sub.Steps[i].Op == "adopt" {
				var m map[string]any
				json.Unmarshal(sub.Steps[i].Request, &m)
				m["versions"].(map[string]any)["model"] = "m-2"
				sub.Steps[i].Request, _ = json.Marshal(m)
			}
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	if rep.Fidelity != Match {
		t.Fatalf("version-only substitution changed the event stream: %s (versions ride the pin but do not fork transitions)", rep.Detail)
	}
	// a material substitution forks it
	rep2, err := Reevaluate(c, func(sub *Case) {
		sub.Steps[1].OpID = "op-nonexistent"
	})
	if err != nil {
		t.Fatal(err)
	}
	if rep2.Fidelity != Divergence {
		t.Fatalf("material substitution (dispatch a different op) should diverge, got %q", rep2.Fidelity)
	}
	if string(orig) != string(mustMarshal(t, c)) {
		t.Fatal("Reevaluate mutated the original case — mode 3 must be isolated")
	}
}

func mustMarshal(t *testing.T, c *Case) []byte {
	t.Helper()
	b, err := json.Marshal(c)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

// TestInspectProjectsAndExposesGaps pins mode 1: the projection reducer
// rebuilds states from the record and exposes the ledger checker's gaps —
// no recomputation (a bypassed record's gap shows up here, not in Replay).
func TestInspectProjectsAndExposesGaps(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	rep, err := Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(rep.Events) != 0 || len(rep.Gaps) != 0 {
		t.Fatalf("empty ledger should project empty, got %d events / %d gaps", len(rep.Events), len(rep.Gaps))
	}
	// build a real record then inspect it
	digest := "sha256:" + strings.Repeat("a", 64)
	if o := m.Adopt(&adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-i", OperationID: "op-i"},
		Versions:         ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:    digest,
		GrantsAtDecision: []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}},
	}); o.Status != "adopted" {
		t.Fatalf("adopt = %q", o.Status)
	}
	rep, err = Inspect(path)
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-i"] != "adopted" {
		t.Fatalf("projection state = %q, want adopted", rep.States["op-i"])
	}
	if len(rep.Gaps) != 0 {
		t.Fatalf("machine-written record has gaps: %v", rep.Gaps)
	}
}

// TestRecoversToDispatchableNotBeyond pins mode 4: recovery restores machine
// state from the durable record and reports reconciliation exits — it never
// dispatches (0.1.0 boundary: dispatching is the gate's live-effect
// authority).
func TestRecoversToDispatchableNotBeyond(t *testing.T) {
	path := filepath.Join(t.TempDir(), "adopt.jsonl")
	m, _ := adopt.Open(path)
	digest := "sha256:" + strings.Repeat("a", 64)
	grants := []ledger.Grant{{Kind: "data", Selector: "s", Actions: []string{"read"}, Effect: "none"}}
	m.Adopt(&adopt.Request{
		AdoptionVersion: "0.1.0",
		Identity:        ledger.Identity{BusinessRequestID: "br-r", OperationID: "op-r"},
		Versions:        ledger.Versions{Evidence: "e", Rule: "r", Model: "m", Readout: "ro", Policy: "p"},
		PayloadDigest:   digest, GrantsAtDecision: grants,
	})
	m.Dispatch("op-r", grants)
	m.MarkUnresolved("op-r")

	rep, err := Recover(path)
	if err != nil {
		t.Fatal(err)
	}
	if rep.States["op-r"] != "unresolved" {
		t.Fatalf("recovered state = %q, want unresolved", rep.States["op-r"])
	}
	if len(rep.Unresolved) != 1 || !strings.Contains(rep.Unresolved[0], "never re-dispatch") {
		t.Fatalf("reconciliation exit report wrong: %v", rep.Unresolved)
	}
	// recovery must not have written anything (read-only consumer)
	events, _ := m.Events()
	if len(events) != 3 {
		t.Fatalf("Recover wrote to the durable form: %d events", len(events))
	}
}

// TestMachineProducedFixtures pins the anti-rot mechanism (collision
// ruling): the race fixtures' records are reproducible by driving the
// production machine through the same steps — hand-written records that
// drift from machine behavior fail here.
func TestMachineProducedFixtures(t *testing.T) {
	for _, name := range []string{"race-outcome-a-first.json", "race-outcome-b-first.json", "happy-chain.json"} {
		c := loadCase(t, name)
		rep, err := Replay(c)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if rep.Fidelity != Match {
			t.Fatalf("%s: machine could not reproduce the fixture record (%s) — fixture drifted from machine behavior", name, rep.Detail)
		}
	}
}
