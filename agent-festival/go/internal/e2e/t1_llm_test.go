package e2e

// T1 — the real-LLM single-point S1 tier. Launch discipline: the real-LLM
// run is started by the USER (never the agent). Everything is prepared to
// "ready to fly": one command, fail-loud gates, pre-registered criteria.
//
// Launch command (user executes; the key is read from the provider config
// without echoing it):
//
//	T1_LLM=1 T1_ENDPOINT=https://az.gptplus5.com T1_MODEL=glm-5.3-flash \
//	T1_API_KEY=$(python3 -c "import json;print(json.load(open('$HOME/.zcode/v2/provider_config.json'))['config']['providerConfigRules']['providerRules'][4]['config']['access']['apiKey'])") \
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
		expected: "on_undefined_rule", hardBar: false, // reported without a bar: first measurement
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
	// consistency pairs: same facts, rephrased — same verdict
	for _, pair := range [][2]string{{"C1-clean-grant", "C5-rephrase-of-C1"}, {"C2-window-outside-veto", "C4-rephrase-of-C2"}} {
		a, b := results[pair[0]].got, results[pair[1]].got
		if a == "" || b == "" || a != b {
			t.Errorf("T1 consistency pair FAILED: %s vs %s → %q vs %q (same facts must yield the same verdict)", pair[0], pair[1], a, b)
		} else {
			t.Logf("[T1] consistency pair OK: %s ≡ %s → %q", pair[0], pair[1], a)
		}
	}
	// the readout: every case, both faces logged, nothing hidden
	correct := 0
	for _, c := range t1Cases {
		if results[c.id].got == c.expected {
			correct++
		}
	}
	t.Logf("[T1] READOUT: %d/%d verdicts correct; hard-bar cases %s; pair members logged above; "+
		"C6 (between-bands, expected %q) is reported WITHOUT a pre-registered bar (first measurement)",
		correct, len(t1Cases), "enforced", "on_undefined_rule")
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
