// Package e2e is the Tier-0 end-to-end scenario suite: the full credit
// chain driven through the REAL governance components (adopt machine,
// event ledger, evidlog, replay) with deterministic model stand-ins
// playing S1 (judgment) and S2 (investigation) and a stubbed business
// API — the "model stand-in validates the framework, not the model"
// tier of the four-layer evidence declaration (xingchao MR#2 评论①
// §11.B; the model-capability tier is separate and real-LLM).
//
// The scenarios are his §11.B list: historical-overdue veto, missing
// evidence then supplement, new evidence forcing a revision, a late
// stale proposal, new evidence after the request went out, restart
// while waiting, duplicate response, and mid-flight revocation — plus
// the happy-path skeleton of the eight-step chain. What each scenario
// asserts is the CONTROL semantics (idempotency, revocation re-check,
// first-class unresolved, torn-tail refusal, control-event audit,
// replay projection), never the business verdict of a real model: the
// S1 stand-in embodies the corrected credit rules (08:181-183 and
// 10-walkthrough:145 — the historical veto is unbounded; the fixture's
// window-scoped wording is the pending P3 correction) so the scenario
// data can use the reviewer's counterexample.
package e2e
