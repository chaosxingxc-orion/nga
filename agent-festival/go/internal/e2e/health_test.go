package e2e

// E4 (33号 B4) + E-GR (33号 B7): the health-reading face — the machine
// face of xia 2.5's first amendment ("a guard failing QUIETLY — never
// intercepting again while traffic continues — is the most dangerous
// failure form") and her 2.2 graveyard-sweep guardrail. E4 is a pure
// function over the machine's public event stream (Machine.Events);
// E-GR is a pure function over structured entries — R31 m-3 honesty: the
// minor-ledger demo is a SYNTHETIC shape-run (L-1..L-47 with constructed
// ages), NOT a load of docs/minor-ledger.md (the real ledger is never
// parsed here). Zero machine changes; determinism: langgraph _algo.py
// sorted-keys discipline for every aggregation walk.

import (
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"github.com/openjiuwen/agent-festival/go/internal/adopt"
	"github.com/openjiuwen/agent-festival/go/internal/ledger"
)

// frequencyReport aggregates control-family events by their status, in
// sorted-key order (deterministic output for diffing and alerting).
// R31 m-1: guardDied computes its own traffic face inline (the effect
// events it walks) — this report covers the control side only.
type frequencyReport struct {
	byStatus map[string]int
	total    int
}

// aggregateControl walks the event stream and counts control events by
// outcome status. Effect events are traffic, not interceptions — the
// death probe (guardDied) walks them itself.
func aggregateControl(events []ledger.Event) frequencyReport {
	rep := frequencyReport{byStatus: map[string]int{}}
	for _, e := range events {
		if e.EventType == "control" {
			rep.byStatus[e.Outcome.Status]++
			rep.total++
		}
	}
	return rep
}

// sortedStatuses returns the report's statuses in sorted order (E4's
// deterministic-walk discipline).
func (r frequencyReport) sortedStatuses() []string {
	keys := make([]string, 0, len(r.byStatus))
	for k := range r.byStatus {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// guardDied reports whether the control face has gone quiet under
// continued EFFECT traffic: effect events continue AFTER the last control
// interception with no further interception. B-1 (R29) honesty scope: the
// event stream cannot distinguish an AUTHORIZED effect from one the dead
// guard should have intercepted (the machine is semantically blind — the
// same blindness E0/E1 recorded), so a rejection followed by a healthy
// authorized dispatch is INDISTINGUISHABLE from death by this probe. The
// probe therefore answers a narrower question: "did the control face go
// quiet while effects kept flowing" — a review signal, not a verdict. A
// guard never challenged at all is not "dead" (no false positive there).
// R29 M-6 honesty note: the parameter is named controlStatus, not
// guardStatus — every control event shares the single status "rejected"
// (revocation, state gates, torn tail, E6 version gate all refuse via the
// same refuse() path), so the event stream CANNOT name an individual
// guard. The probe therefore watches the CONTROL FACE as a whole: one
// guard dying while others still fire is masked (a known, declared
// blind spot — naming guards would require refuse() detail-prefix
// parsing, deliberately out of scope for this fixture-tier probe).
func guardDied(events []ledger.Event, controlStatus string, canaryDetailPrefix string) bool {
	lastIntercept := -1
	lastTraffic := -1
	for i, e := range events {
		if e.EventType == "control" && e.Outcome.Status == controlStatus {
			// E7b canary filter (xia round-4 §2 discipline 2 extension,
			// 41号 report):
			// an alive canary stream masks business-guard death by keeping
			// lastIntercept fresh — probe-injected rejections carrying the
			// reserved prefix are excluded from the interception face. The
			// empty prefix = NO filtering (guard against the strings.HasPrefix
			// always-true trap; E4 semantics preserved).
			if canaryDetailPrefix != "" && strings.HasPrefix(e.Outcome.Detail, canaryDetailPrefix) {
				continue
			}
			lastIntercept = i
		}
		if e.EventType == "effect" {
			lastTraffic = i
		}
	}
	if lastIntercept < 0 {
		return false // never challenged — not "death" (no false positive)
	}
	return lastTraffic > lastIntercept
}

// TestE4_FrequencyAggregationAndGuardDeath is the E4 experiment: the
// aggregation reads a known event set correctly, and a guard that goes
// quiet under continued traffic is DETECTED. Mutation probe: remove the
// death condition and the dying-guard case passes silently (red).
func TestE4_FrequencyAggregationAndGuardDeath(t *testing.T) {
	path := newLedgerPath(t)
	m := mustOpenAdopt(t, path)

	// Phase 1 — the guard is ALIVE: three revocation rejections land
	// (control events). No effect dispatch happens in this phase — under
	// the B-1 narrowed semantics, a rejection followed by an authorized
	// dispatch is indistinguishable from death (the machine is blind), so
	// the alive assertion requires an effect-free tail.
	for _, op := range []string{"op-e4-1", "op-e4-2", "op-e4-3"} {
		if o := m.Adopt(adoptRequest(t, op)); o.Status != "adopted" {
			t.Fatalf("E4: adopt %s = %q: %s", op, o.Status, o.Detail)
		}
		if o := m.Dispatch(op, nil); o.Status != "rejected" {
			t.Fatalf("E4: revoked dispatch %s = %q, want rejected (the 14-A4 guard alive)", op, o.Status)
		}
	}
	if o := m.Adopt(adoptRequest(t, "op-e4-live")); o.Status != "adopted" {
		t.Fatalf("E4: live adopt = %q", o.Status)
	}
	// op-e4-live is deliberately NOT dispatched: dispatching it would be a
	// post-interception effect, which the narrowed probe reads as death.

	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	rep := aggregateControl(events)
	if rep.total != 3 {
		t.Fatalf("E4: control events = %d, want 3", rep.total)
	}
	if rep.byStatus["rejected"] != 3 {
		t.Fatalf("E4: rejected count = %d, want 3 (aggregation correctness)", rep.byStatus["rejected"])
	}
	got := strings.Join(rep.sortedStatuses(), ",")
	if got != "rejected" {
		t.Fatalf("E4: sorted statuses = %q, want \"rejected\" (deterministic walk)", got)
	}
	if died := guardDied(events, "rejected", ""); died {
		t.Fatal("E4: guard reported dead while actively intercepting — false positive")
	}

	// Phase 2 — the guard DIES: traffic continues (the dispatches are
	// the effect events guardDied walks — adoption events are NOT flow,
	// see guardDied), but no further interception ever fires (simulated:
	// the check is silently removed upstream — rejections stop while
	// effects keep flowing).
	for _, op := range []string{"op-e4-l1", "op-e4-l2", "op-e4-l3"} {
		if o := m.Adopt(adoptRequest(t, op)); o.Status != "adopted" {
			t.Fatalf("E4: post-death adopt %s = %q", op, o.Status)
		}
		if o := m.Dispatch(op, fullGrants()); o.Status != "dispatched" {
			t.Fatalf("E4: post-death dispatch %s = %q: %s (want dispatched — the guard is gone)", op, o.Status, o.Detail)
		}
	}
	events, err = m.Events()
	if err != nil {
		t.Fatal(err)
	}
	if died := guardDied(events, "rejected", ""); !died {
		t.Fatal("E4: the guard went quiet under continued traffic and the probe did NOT flag it — the death probe is not load-bearing")
	}
}

// TestE4_MixedFlowIsIndistinguishableFromDeath pins the B-1 narrowed
// semantics with the MIXED flow: one rejection → one AUTHORIZED dispatch.
// Under the event stream's expressiveness this reads as death (the probe
// cannot tell an authorized effect from an intercepted one) — the test
// documents that limitation as a pinned fact, and 37号's "健康流不误报"
// claim is corrected to "纯控制尾流不误报；混合流的死亡/授权不可区分"
// (the review signal, not a verdict). Mutation probe: if someone later
// makes the event stream expressive (a challenge channel), this test
// documents the old bound and should be rewritten with it.
func TestE4_MixedFlowIsIndistinguishableFromDeath(t *testing.T) {
	path := newLedgerPath(t)
	m := mustOpenAdopt(t, path)
	if o := m.Adopt(adoptRequest(t, "op-e4-mix-a")); o.Status != "adopted" {
		t.Fatalf("E4-mix: adopt = %q", o.Status)
	}
	if o := m.Dispatch("op-e4-mix-a", nil); o.Status != "rejected" {
		t.Fatalf("E4-mix: revoked dispatch = %q, want rejected", o.Status)
	}
	if o := m.Adopt(adoptRequest(t, "op-e4-mix-b")); o.Status != "adopted" {
		t.Fatalf("E4-mix: adopt b = %q", o.Status)
	}
	// the AUTHORIZED dispatch after the interception:
	if o := m.Dispatch("op-e4-mix-b", fullGrants()); o.Status != "dispatched" {
		t.Fatalf("E4-mix: authorized dispatch = %q", o.Status)
	}
	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	// the pinned limitation: the mixed flow READS as death under the
	// current probe semantics — a documented bound, not a desired state
	if died := guardDied(events, "rejected", ""); !died {
		t.Fatal("E4-mix: expected the mixed flow to read as death under the narrowed semantics — if this went false, the event stream became expressive and the pinned bound is obsolete (rewrite the E4 tests with the new expressiveness)")
	}
}

// TestE4_GuardNeverChallengedIsNotDeath pins the false-positive face: a
// machine with zero rejections and zero traffic is NOT a dead guard (it
// was never challenged).
func TestE4_GuardNeverChallengedIsNotDeath(t *testing.T) {
	path := newLedgerPath(t)
	m := mustOpenAdopt(t, path)
	if o := m.Adopt(adoptRequest(t, "op-e4-q")); o.Status != "adopted" {
		t.Fatalf("E4: adopt = %q", o.Status)
	}
	events, err := m.Events()
	if err != nil {
		t.Fatal(err)
	}
	if died := guardDied(events, "rejected", ""); died {
		t.Fatal("E4: a never-challenged guard reported dead — false positive")
	}
}

// ---------------------------------------------------------------------------
// E-GR (33号 B7): the graveyard sweep — xia 2.2's guardrail one. Ledger
// entries past a count/age threshold trigger a sweep list (the same
// control-event family carries the trigger). First user: the minor ledger
// itself (L1-L47 is the demo input).

// sweepThreshold is the graveyard guardrail's dial (pre-registered, not
// tuned after seeing data).
type sweepThreshold struct {
	maxEntries int // more than this many entries → sweep
	maxAgeDays int // entries older than this → sweep candidates
}

// graveyardSweep returns the entries that must be reviewed for recovery or
// retirement (sorted for determinism). Count face: if the ledger exceeds
// maxEntries, EXACTLY len−maxEntries oldest non-age-listed entries are
// listed (R41 m-3: this is a fixed arithmetic, NOT a "list until the
// remainder fits" minimal-cut — when the age face has already listed
// entries the two faces can over-list combined; direction is safe — the
// sweep list over-includes, it never under-reviews). Age face: any entry
// older than maxAgeDays is listed regardless of count.
func graveyardSweep(entries []graveyardEntry, th sweepThreshold) []string {
	var out []string
	// age face first (deterministic order: entries are walked in given order)
	for _, e := range entries {
		if e.ageDays > th.maxAgeDays {
			out = append(out, e.id)
		}
	}
	// count face: over the ceiling → the oldest non-age-listed entries
	if len(entries) > th.maxEntries {
		excess := len(entries) - th.maxEntries
		byAge := make([]graveyardEntry, len(entries))
		copy(byAge, entries)
		// R32 m-4: the id tiebreak makes the equal-age cut deterministic
		// (the file head's sorted-keys discipline — a tie at the excess
		// boundary previously picked arbitrarily)
		sort.Slice(byAge, func(i, j int) bool {
			if byAge[i].ageDays != byAge[j].ageDays {
				return byAge[i].ageDays > byAge[j].ageDays
			}
			return byAge[i].id < byAge[j].id
		})
		listed := map[string]bool{}
		for _, id := range out {
			listed[id] = true
		}
		for _, e := range byAge {
			if excess == 0 {
				break
			}
			if !listed[e.id] {
				out = append(out, e.id)
				listed[e.id] = true
				excess--
			}
		}
	}
	sort.Strings(out)
	return out
}

type graveyardEntry struct {
	id      string
	ageDays int
}

// TestEGr_GraveyardSweep is the E-GR experiment: threshold boundaries are
// exact (N stays, N+1 sweeps; age maxAgeDays stays, +1 sweeps), the age
// face fires independently, and the sweep list is complete. Mutation
// probes are scoped to the EXCESS ARITHMETIC only (R31 m-7: a >= ceiling
// mutation is unreachable in this function shape — zero excess lists
// nothing — so it is not claimed as red).
func TestEGr_GraveyardSweep(t *testing.T) {
	th := sweepThreshold{maxEntries: 3, maxAgeDays: 30}

	// R29 m-6: the AGE face's exact boundary — ageDays == maxAgeDays stays
	// silent, ageDays == maxAgeDays+1 sweeps (the count face has its N/N+1
	// pin below; the age face gets its own here)
	ageBoundary := []graveyardEntry{
		{id: "L-at", ageDays: 30}, {id: "L-over", ageDays: 31},
	}
	got := graveyardSweep(ageBoundary, th)
	if len(got) != 1 || got[0] != "L-over" {
		t.Fatalf("E-GR: age boundary = %v, want [L-over] (ageDays==maxAgeDays stays, +1 sweeps)", got)
	}

	// boundary: exactly maxEntries → no count-face sweep. The entries sit
	// just inside the age face (1..3 days vs 30) so ONLY the count
	// boundary is under test (a >= ceiling mutation is behavior-identical
	// here — see the scoping note above).
	three := []graveyardEntry{
		{id: "L-a", ageDays: 1}, {id: "L-b", ageDays: 2}, {id: "L-c", ageDays: 3},
	}
	if got := graveyardSweep(three, th); len(got) != 0 {
		t.Fatalf("E-GR: at exactly maxEntries the sweep fired: %v — the boundary is off-by-one (must stay quiet AT the limit)", got)
	}

	// one over → the oldest sweeps (count face). Mutation probes: change
	// the excess arithmetic (len-max+1 instead of len-max) and TWO entries
	// sweep instead of one (red); change > to >= on the ceiling and the
	// exactly-at-limit case above behaves identically — that mutation is
	// UNREACHABLE in this function shape (entering the count face with
	// zero excess lists nothing), so the doc's mutation claim is scoped
	// to the excess arithmetic only.
	four := append(three, graveyardEntry{id: "L-d", ageDays: 4})
	got = graveyardSweep(four, th)
	if len(got) != 1 || got[0] != "L-d" {
		t.Fatalf("E-GR: one-over sweep = %v, want [L-d] (the oldest)", got)
	}

	// age face: independent of count — an old entry sweeps even in a small ledger
	old := []graveyardEntry{
		{id: "L-old", ageDays: 99}, {id: "L-new", ageDays: 2},
	}
	got = graveyardSweep(old, th)
	if len(got) != 1 || got[0] != "L-old" {
		t.Fatalf("E-GR: age-face sweep = %v, want [L-old]", got)
	}

	// completeness: every over-threshold entry appears (age + count faces combined)
	mixed := []graveyardEntry{
		{id: "L-1", ageDays: 60}, {id: "L-2", ageDays: 10},
		{id: "L-3", ageDays: 20}, {id: "L-4", ageDays: 5},
		{id: "L-5", ageDays: 1},
	}
	got = graveyardSweep(mixed, th) // 5 > 3 → 2 excess; L-1 is age-dead
	if len(got) != 3 {
		t.Fatalf("E-GR: combined sweep = %v, want 3 entries (L-1 age + 2 oldest of the rest)", got)
	}
	for _, want := range []string{"L-1", "L-2", "L-3"} {
		found := false
		for _, g := range got {
			if g == want {
				found = true
			}
		}
		if !found {
			t.Fatalf("E-GR: combined sweep %v missing %q — the list is incomplete", got, want)
		}
	}

	// the first real user: the minor ledger itself — a SYNTHETIC shape-run
	// over L1-L47 (47 entries, demo threshold 30/45) → a 19-entry sweep
	// list (2 age + 17 count), listed deterministically (R32 m-3: the
	// block header previously said 17, contradicting the asserted 19)
	var demo []graveyardEntry
	for i := 1; i <= 47; i++ {
		demo = append(demo, graveyardEntry{id: fmt.Sprintf("L-%d", i), ageDays: i})
	}
	got = graveyardSweep(demo, sweepThreshold{maxEntries: 30, maxAgeDays: 45})
	// 47 > 30 → 17 excess; age>45 lists L-46,L-47 (2 entries); the count
	// face then lists the 17 oldest non-age-listed (L-45..L-29). Total 19.
	if len(got) != 19 {
		t.Fatalf("E-GR: minor-ledger demo sweep = %d entries, want 19", len(got))
	}
}

// --- test helpers (adopt-tier, package-scoped: consumed by
// health_test / e7_canary) ---

func newLedgerPath(t *testing.T) string {
	t.Helper()
	return filepath.Join(t.TempDir(), "adopt.jsonl")
}

func mustOpenAdopt(t *testing.T, path string) *adopt.Machine {
	t.Helper()
	m, err := adopt.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	return m
}

func adoptRequest(t *testing.T, op string) *adopt.Request {
	t.Helper()
	return &adopt.Request{
		AdoptionVersion:  "0.1.0",
		Identity:         ledger.Identity{BusinessRequestID: "br-e4", EvaluationRevision: "er-1", OperationID: op},
		Versions:         ledger.Versions{Evidence: "ev-1", Rule: "rule-1", Model: "m-1", Readout: "r-1", Policy: "p-1"},
		PayloadDigest:    "sha256:" + strings.Repeat("a", 64),
		GrantsAtDecision: fullGrants(),
		Accountability:   &ledger.Accountability{Session: "sess-e4", Skill: "skill-e4", Role: "employee"},
	}
}

func fullGrants() []ledger.Grant {
	return []ledger.Grant{
		{Kind: "data", Selector: "ledger://credit/t", Actions: []string{"read"}, Effect: "none"},
		{Kind: "tool", Selector: "tool://credit-transfer", Actions: []string{"execute"}, Effect: "irreversible"},
	}
}

// TestEGr_TieAtExcessBoundaryIsDeterministic is the R32 m-4 probe: two
// entries with the SAME age straddling the excess cut — the id tiebreak
// must pick the same one on every run (map/range order may vary).
func TestEGr_TieAtExcessBoundaryIsDeterministic(t *testing.T) {
	th := sweepThreshold{maxEntries: 1, maxAgeDays: 999} // count face only
	entries := []graveyardEntry{
		{id: "L-tie-b", ageDays: 10},
		{id: "L-tie-a", ageDays: 10}, // same age — the tiebreak decides
	}
	// R33 m-8: the deterministic property the tiebreak buys is INPUT-ORDER
	// independence (the sweep is a total order — run-to-run repeats are
	// trivially equal), so the probe scans INPUT PERMUTATIONS.
	perms := [][]graveyardEntry{
		entries,
		{entries[1], entries[0]}, // the swapped input order
	}
	for pi, perm := range perms {
		got := graveyardSweep(perm, th)
		if len(got) != 1 || got[0] != "L-tie-a" {
			t.Fatalf("m-4 probe: permutation %d winner = %v, want [L-tie-a] — the equal-age cut depends on input order", pi, got)
		}
	}
}
