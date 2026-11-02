# Read-only feedback latency diagnostics

`tools/nfr_feedback_latency.py` consumes explicit, hash-pinned control receipts and writes one bounded JSON report to stdout. It does not schedule work, start a service, call SSH/Docker, read experiment logs or score data. It does not write source receipts. The caller may redirect stdout to a **new local diagnostic output**, never to an input path.

Run with a frozen configuration and its exact byte SHA256:

```sh
python3 -B -P tools/nfr_feedback_latency.py --config /absolute/config.json --sha256 EXACT_CONFIG_SHA256
python3 -B -m unittest discover -s tools -p test_nfr_feedback_latency.py
```

The config uses `schema: nga-nfr-feedback-latency-v1` and exactly three arrays:

| Array | Required fields | Meaning |
| --- | --- | --- |
| `receipts` | `id`, `path`, `sha256`, `clock_domain`, `clock_basis` | Explicit allowed inputs; absolute canonical regular JSON files; exact bytes; declared producing clock and its evidence basis |
| `events` | `id`, `receipt`, `timestamp_field`, `kind` | `kind` is `start` or `terminal`; timestamp field is `utc_seconds`, `started_utc` or `finished_utc` |
| `intervals` | `id`, `start_events`, `end_event`, `required_terminals` | Start is the latest listed dependency, then the end event; nonempty required terminal events must all have integer `exit_code: 0` |

Only `START_INTENT.json`, `EXIT.json`, `TRAIN_EXIT.json` and `ENGINEERING_EVAL_EXIT.json` are admitted names. All IDs are unique; repeated paths and event sources are rejected. A receipt that is absent gives a typed missing state; an existing file with incorrect bytes rejects the report. No optional switch disables terminal checks or hash checks. The configuration schema is exact: unknown fields and versions reject.

Example configuration structure (paths and SHA strings must be replaced by real frozen control receipts):

```json
{
  "schema": "nga-nfr-feedback-latency-v1",
  "receipts": [
    {"id": "start", "path": "/absolute/job/START_INTENT.json", "sha256": "EXACT_START_SHA256", "clock_domain": "local-cpu", "clock_basis": "Both receipts produced by the same CPU host for this run."},
    {"id": "done", "path": "/absolute/job/EXIT.json", "sha256": "EXACT_EXIT_SHA256", "clock_domain": "local-cpu", "clock_basis": "Both receipts produced by the same CPU host for this run."}
  ],
  "events": [
    {"id": "started", "receipt": "start", "timestamp_field": "utc_seconds", "kind": "start"},
    {"id": "completed", "receipt": "done", "timestamp_field": "utc_seconds", "kind": "terminal"}
  ],
  "intervals": [
    {"id": "report", "start_events": ["started"], "end_event": "completed", "required_terminals": ["completed"]}
  ]
}
```

`clock_domain` is a nonempty identifier or JSON `null`. Known domains require a textual `clock_basis`. The declared domain is **operator-provided provenance**, not independently verified host synchronization. Unknown domains produce `unknown_clock_domain`; different domains produce `incomparable_clock_domains`. Both leave `elapsed_seconds: null`. Version 1 deliberately has no cross-host calibration or clock-offset correction: a shared filesystem is not evidence of a shared clock.

Successful same-domain intervals report wall-clock differences, not monotonic execution durations or NPU idle time. A negative difference produces `clock_or_order_anomaly`, never zero. A true zero remains zero. Missing/invalid timestamps, absent terminals and failed terminal markers produce `unavailable_event` with typed reasons. A terminal endpoint must also appear among required terminals. Terminal checks confirm receipt-level successful completion, not retained-container/device state, scientific acceptance or release permission.

Exit code 0 means the bounded diagnostic report was produced; it can contain unknown intervals. Consumers must inspect each interval status. Exit code 2 is rejected input and emits a bounded error object. Neither is a scheduler completion signal. Raw input contents and tracebacks are not emitted.

Limits: at most 64 receipts, 64 events, 32 intervals; config ≤64 KiB; each receipt ≤1 MiB; report ≤128 KiB. Counts include successfully read config and receipt snapshots; `runtime_seconds` and `cpu_seconds` measure only this diagnostic invocation. Each input hash and parsed object comes from the same snapshot. The tool does not provide a cross-file atomic snapshot, detect same-host clock adjustments, or authenticate asserted producer identities. Use terminal/frozen receipts and independently reviewed config provenance.

The first real fixture is local-only under `.local/reports/nfr-feedback-latency-evidence/`. It rebuilds four intervals from six completed v15 CPU receipts plus one config. Three intervals match previous float readings exactly; report-to-comparison wait differs by 0.477 microseconds because the historical calculation used an ISO endpoint rounded to microseconds. Both readings and source hashes are retained; this is consistent within original timestamp precision and does not revise the historical report. The diagnostic is not evidence of a production scheduling speedup.
