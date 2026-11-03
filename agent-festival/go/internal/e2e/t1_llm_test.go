package e2e

// T1 — the real-LLM single-point S1 tier. Launch discipline: the real-LLM
// run is started by the USER (never the agent). Everything is prepared to
// "ready to fly": one command, fail-loud gates, pre-registered criteria.
//
// Launch (user executes — fill the three variables from YOUR provider
// setup; the operator's local runbook holds the concrete values, they are
// deliberately NOT in this repository):
//
//	T1_LLM=1 T1_ENDPOINT=<your anthropic-messages endpoint> \
//	T1_MODEL=<model id> T1_API_KEY=<the key> \
//	go test -count=1 -run TestT1RealLLMS1 -v ./internal/e2e/
//
// Gates (pre-registered BEFORE the first run — freeze the standard, then
// let the results speak; raising a bar after seeing results is a NEW
// pre-registration, never a silent edit):
//
//   - HARNESS health is a hard gate: every call must transport and parse,
//     else the run FAILS (fail-loud — an env problem may never silently
//     skip to rc=0, the XM2 静默空批 lesson).
//   - C1 (clean grant), C2 (the window-outside historical veto — the
//     reviewer's counterexample, the load-bearing discrimination case),
//     C3 (missing evidence → on_missing_evidence, never an auto-deny) and
//     C7 (in-window veto) are HARD capability bars: a model that misses
//     any of these is not ready for the S1 seat (D1: model readiness is a
//     separate gate; a green T0 framework tier claims nothing about it).
//   - CONSISTENCY pairs (C1↔C5, C2↔C4 — same facts, rephrased) must agree:
//     same-input-same-verdict is the S1 role's core contract.
//   - C6 (assets strictly between the bands → on_undefined_rule) is
//     REPORTED WITHOUT a bar: boundary discipline is the first measurement
//     on this model; a bar would be a guess, not a pre-registration.
//
// The readout prints every case's expected/got verdict, the model's stated
// reason, latency and attempts — the full auditable record (won-face AND
// failure-face both logged; no aggregate hides a case).
//
// RUN 2 pre-registration (frozen BEFORE the re-run, 2026-11-03; the run-1
// gate set is preserved in git history c696542 — raising a bar after
// seeing results is legitimate ONLY as this explicit new registration):
// the run-1 baseline (7/7, archived impl-2026-11-01/15-t1-readout.md)
// justifies the raise — C6 (between-bands) is PROMOTED to a hard bar per
// the documented candidate; five NEW cases probe what run 1 never did:
// precedence interactions (C8 veto beats missing evidence; C12 veto
// beats the lower band), the lower band itself (C9), a third rephrase
// extending the load-bearing case's consistency pair to a TRIPLE (C11),
// and the exact-cutoff boundary (C10). Hard bars = every case whose
// expected verdict follows UNAMBIGUOUSLY from the written spec (all
// seven originals, C8, C9, C11, C12); report-only = the exact-cutoff
// face (C10), a convention edge never measured — the next raise
// candidate. Cross-run repeatability is enforced by the same hard bars:
// correct verdicts ARE the run-1 verdicts, so repeat-correctness is the
// stability claim under test.

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

// t1Case is one judgment-seat probe: a dossier of facts and the verdict
// the corrected specification (the T0 stand-in's rules: unbounded veto per
// 08:181-183 / 10-walkthrough:145, window on the upper band only, open
// boundaries stay open, missing evidence requests evidence) requires.
type t1Case struct {
	id       string
	dossier  string
	expected string
	hardBar  bool // pre-registered hard capability bar (see the package doc)
}

// t1Spec is the S1 judgment specification presented to the model — the
// corrected credit rules, exactly the semantics the T0 stand-in embodies.
const t1Spec = `You are S1, the judgment expert for a natural-person credit eligibility task.
Apply EXACTLY this specification, nothing else:

- Precedence 0 (override): ANY overdue obligation longer than three months, AT ANY TIME in the
  applicant's credit history on record, denies credit — regardless of assets. This veto is NOT
  limited to any recent window; a years-old severe overdue still denies.
- Precedence 1: declared net assets above 30 (millions of USD) AND no overdue in the last six
  months → eligible for the 50,000 USD line (verdict "grant-50000").
- Precedence 2: declared net assets below 1 (millions of USD) → eligible for the 10,000 USD line
  (verdict "grant-10000"). The six-month condition attaches to the upper band only.
- Open specification questions: assets exactly at a cutoff, or strictly between 1 and 30, are
  UNSETTLED — output "on_undefined_rule" (record the issue; do NOT default to any grant).
- Missing evidence: if the asset valuation report cannot be retrieved, output
  "on_missing_evidence" (request the evidence; an automatic denial is forbidden).

Output STRICT JSON only, no other text, no code fences:
{"verdict": "<grant-50000|grant-10000|deny|on_missing_evidence|on_undefined_rule>", "reason": "<one sentence>"}`

var t1Cases = []t1Case{
	{
		id: "C1-clean-grant",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 35 (millions of USD)
- asset valuation report: present and valid
- payment history on record: no overdue entries at any time
- recent six months: no overdue`,
		expected: "grant-50000", hardBar: true,
	},
	{
		id: "C2-window-outside-veto",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 35 (millions of USD)
- asset valuation report: present and valid
- payment history on record: one obligation was overdue for 4 months, 2 years ago; no other overdue entries at any time
- recent six months: no overdue`,
		expected: "deny", hardBar: true, // the reviewer's counterexample: discrimination
	},
	{
		id: "C3-missing-evidence",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: unknown — the asset valuation report could not be retrieved
- payment history on record: no overdue entries at any time`,
		expected: "on_missing_evidence", hardBar: true, // never an automatic denial
	},
	{
		id: "C4-rephrase-of-C2",
		dossier: `EVIDENCE DOSSIER (sealed) — same applicant, restated record:
Two years back the applicant had a loan that went unpaid for four months. The last six months
show no overdue entries, and no other overdue entries exist anywhere on the record. The declared
net asset value is 35 million USD, and a valid asset valuation report is present.`,
		expected: "deny", hardBar: false, // consistency pair member (bar via the pair check)
	},
	{
		id: "C5-rephrase-of-C1",
		dossier: `EVIDENCE DOSSIER (sealed) — same applicant, restated record:
The declared net asset value is 35 million USD with a valid valuation report attached. Across the
entire payment history there is not a single overdue entry, including a clean last six months.`,
		expected: "grant-50000", hardBar: false, // consistency pair member (bar via the pair check)
	},
	{
		id: "C6-between-bands",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 12 (millions of USD)
- asset valuation report: present and valid
- payment history on record: no overdue entries at any time
- recent six months: no overdue`,
		// RUN 2: promoted to a hard bar per the run-1 candidate — the
		// baseline measurement (7/7, archived readout) is what makes the
		// raise a re-registration rather than a guess
		expected: "on_undefined_rule", hardBar: true,
	},
	{
		id: "C7-in-window-veto",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 35 (millions of USD)
- asset valuation report: present and valid
- payment history on record: one obligation was overdue for 3.5 months, 5 months ago (inside the recent window); no other overdue entries
- recent six months: the overdue above occurred in this window`,
		expected: "deny", hardBar: true,
	},
	{
		// RUN 2 — precedence interaction run 1 never probed: the veto is
		// precedence 0, so a historical severe overdue denies even when the
		// asset report is missing (the gap discipline does not shield the veto)
		id: "C8-veto-beats-missing-evidence",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: unknown — the asset valuation report could not be retrieved
- payment history on record: one obligation was overdue for 4 months, 3 years ago; no other overdue entries`,
		expected: "deny", hardBar: true,
	},
	{
		// RUN 2 — the lower band, never individually measured in run 1
		id: "C9-lower-band",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 0.5 (millions of USD)
- asset valuation report: present and valid
- payment history on record: no overdue entries at any time
- recent six months: no overdue`,
		expected: "grant-10000", hardBar: true,
	},
	{
		// RUN 2 — the exact-cutoff boundary: a convention edge never
		// measured; REPORTED WITHOUT a bar (the next raise candidate — a
		// bar on an unmeasured edge would be a guess, not a registration)
		id: "C10-exact-cutoff",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 30 (millions of USD) — exactly at the upper cutoff
- asset valuation report: present and valid
- payment history on record: no overdue entries at any time
- recent six months: no overdue`,
		expected: "on_undefined_rule", hardBar: false,
	},
	{
		// RUN 2 — a third rephrase of C2: the load-bearing case's
		// consistency evidence extends from a pair to a TRIPLE
		id: "C11-rephrase-of-C2-again",
		dossier: `EVIDENCE DOSSIER (sealed) — same applicant, second restatement:
The applicant's declared net asset value is 35 million USD with a valid valuation report on
file. The recent six months are clean, and the entire payment history holds a single blemish:
one obligation, settled two years back, spent four months past due.`,
		expected: "deny", hardBar: true,
	},
	{
		// RUN 2 — precedence interaction: the veto beats the lower band too
		id: "C12-veto-beats-lower-band",
		dossier: `EVIDENCE DOSSIER (sealed):
- declared net assets: 0.5 (millions of USD)
- asset valuation report: present and valid
- payment history on record: one obligation was overdue for 5 months, 18 months ago; no other overdue entries
- recent six months: no overdue`,
		expected: "deny", hardBar: true,
	},
}

// t1Verdict is the model's parsed answer.
type t1Verdict struct {
	Verdict string `json:"verdict"`
	Reason  string `json:"reason"`
}

// t1Call performs one anthropic-messages-protocol call. Transport errors
// get ONE retry (never a verdict mismatch); the attempt count is returned
// for the readout.
func t1Call(t *testing.T, endpoint, key, model, dossier string) (verdict t1Verdict, raw string, attempts int, err error) {
	t.Helper()
	body, _ := json.Marshal(map[string]any{
		"model":      model,
		"max_tokens": 4096, // glm thinking is always-on: reasoning eats the budget
		"system":     t1Spec,
		"messages":   []map[string]string{{"role": "user", "content": dossier}},
	})
	for attempts = 1; attempts <= 2; attempts++ {
		req, rerr := http.NewRequest("POST", strings.TrimRight(endpoint, "/")+"/v1/messages", bytes.NewReader(body))
		if rerr != nil {
			return verdict, "", attempts, rerr
		}
		req.Header.Set("x-api-key", key)
		req.Header.Set("anthropic-version", "2023-06-01")
		req.Header.Set("content-type", "application/json")
		resp, rerr := (&http.Client{Timeout: 180 * time.Second}).Do(req)
		if rerr != nil {
			if attempts == 1 {
				continue // one transport retry
			}
			return verdict, "", attempts, rerr
		}
		rawBody, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if resp.StatusCode != 200 {
			// a non-200 is a harness failure, not a capability finding —
			// retry once on 5xx only, fail loud otherwise
			if resp.StatusCode >= 500 && attempts == 1 {
				continue
			}
			return verdict, string(rawBody), attempts, fmt.Errorf("HTTP %d: %.200s", resp.StatusCode, rawBody)
		}
		var msg struct {
			Content []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
		}
		if jerr := json.Unmarshal(rawBody, &msg); jerr != nil {
			return verdict, string(rawBody), attempts, fmt.Errorf("response did not parse: %v", jerr)
		}
		var text string
		for _, c := range msg.Content {
			if c.Type == "text" {
				text += c.Text
			}
		}
		if text == "" {
			return verdict, string(rawBody), attempts, fmt.Errorf("no text block in the response (content: %.200s)", rawBody)
		}
		// strip optional code fences before parsing the strict-JSON ask
		clean := strings.TrimSpace(text)
		if strings.HasPrefix(clean, "```") {
			if i := strings.Index(clean, "\n"); i >= 0 {
				clean = clean[i+1:]
			}
			clean = strings.TrimSuffix(strings.TrimSpace(clean), "```")
		}
		if perr := json.Unmarshal([]byte(strings.TrimSpace(clean)), &verdict); perr != nil {
			return verdict, text, attempts, fmt.Errorf("verdict JSON did not parse (model text: %.300s)", text)
		}
		return verdict, text, attempts, nil
	}
	return verdict, "", attempts, fmt.Errorf("unreachable")
}

// TestT1RealLLMS1 is the real-LLM S1 tier — LAUNCHED BY THE USER (see the
// launch command and the pre-registered gates in the file doc above). The
// default state is OFF (explicit skip naming the launch path); enabled
// with an incomplete environment FAILS LOUD (never a silent green).
func TestT1RealLLMS1(t *testing.T) {
	if os.Getenv("T1_LLM") != "1" {
		t.Skip("T1 real-LLM tier not launched — the launch key is the user's (see internal/e2e/t1_llm_test.go doc for the one command)")
	}
	endpoint := os.Getenv("T1_ENDPOINT")
	key := os.Getenv("T1_API_KEY")
	model := os.Getenv("T1_MODEL")
	if endpoint == "" || key == "" || model == "" {
		t.Fatalf("T1 enabled but the environment is incomplete — T1_ENDPOINT=%q T1_MODEL=%q T1_API_KEY=%q (len %d); "+
			"a misconfigured run must FAIL, not silently pass", endpoint, model, "<masked>", len(key))
	}

	type result struct {
		got      string
		reason   string
		raw      string
		attempts int
		err      error
		latency  time.Duration
	}
	results := map[string]*result{}
	harnessFail := false

	for _, c := range t1Cases {
		start := time.Now()
		v, raw, attempts, err := t1Call(t, endpoint, key, model, c.dossier)
		r := &result{raw: raw, attempts: attempts, err: err, latency: time.Since(start)}
		if err == nil {
			r.got = v.Verdict
			r.reason = v.Reason
		} else {
			harnessFail = true
		}
		results[c.id] = r
		t.Logf("[T1] %-24s expected=%-19s got=%-19s attempts=%d latency=%s %s",
			c.id, c.expected, firstNonEmpty(r.got, "<harness-error>"), attempts, r.latency.Round(time.Millisecond),
			func() string {
				if err != nil {
					return "HARNESS ERROR: " + err.Error()
				}
				if r.got == c.expected {
					return "OK"
				}
				return "MISMATCH"
			}())
		if r.reason != "" {
			t.Logf("[T1]   reason: %s", truncate(r.reason, 200))
		}
	}

	// pre-registered hard bars: harness health, the four capability cases
	if harnessFail {
		t.Fatalf("T1 harness failure — at least one call did not transport/parse; the readout above names it")
	}
	for _, c := range t1Cases {
		if c.hardBar && results[c.id].got != c.expected {
			t.Errorf("T1 hard bar FAILED: %s expected %q, got %q (reason: %s)", c.id, c.expected, results[c.id].got, truncate(results[c.id].reason, 200))
		}
	}
	// consistency groups: same facts, rephrased — same verdict. RUN 2
	// extends the load-bearing case's group from a pair to a TRIPLE
	// (C2/C4/C11); the clean-grant pair stays (C1/C5)
	for _, group := range [][]string{
		{"C1-clean-grant", "C5-rephrase-of-C1"},
		{"C2-window-outside-veto", "C4-rephrase-of-C2", "C11-rephrase-of-C2-again"},
	} {
		first := results[group[0]].got
		ok := first != ""
		for _, id := range group[1:] {
			if results[id].got == "" || results[id].got != first {
				ok = false
			}
		}
		if !ok {
			verdicts := make([]string, len(group))
			for i, id := range group {
				verdicts[i] = fmt.Sprintf("%s=%q", id, results[id].got)
			}
			t.Errorf("T1 consistency group FAILED: %s (same facts must yield the same verdict)", strings.Join(verdicts, ", "))
		} else {
			t.Logf("[T1] consistency group OK: %s ≡ %q", strings.Join(group, " ≡ "), first)
		}
	}
	// the readout: every case, both faces logged, nothing hidden
	correct := 0
	for _, c := range t1Cases {
		if results[c.id].got == c.expected {
			correct++
		}
	}
	t.Logf("[T1] READOUT: %d/%d verdicts correct; hard-bar cases enforced (RUN 2 re-registration: "+
		"C6 promoted; C8/C9/C11/C12 added); C10 (exact-cutoff, expected %q) is reported WITHOUT "+
		"a bar — the next raise candidate (an unmeasured edge is not a bar)",
		correct, len(t1Cases), "on_undefined_rule")
}

func firstNonEmpty(s, fallback string) string {
	if s == "" {
		return fallback
	}
	return s
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
