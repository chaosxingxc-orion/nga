# Prospective control successor

`tools/r3_formal_control_successor.py` consumes one immutable config for exactly
QO seed2 → PT seed2 on chip3 and PT seed3 on chip4. Each lane first requires its
exact current engineering DEV predecessor to succeed and release. CPU selection
reports do not gate unrelated NPU work. Polling is machine-driven at 600 seconds.

Preparation creates no activation ticket. The parent must authenticate the actual
independent Astra review of the exact controller and config, publish the required
prelaunch registration, then create a separately pinned
`r3-formal-control-activation-v1` ticket. Its required fields are `config_sha256`,
`controller_sha256`, `allowed_jobs` (the exact ordered three IDs), `attempt: 1`,
`root_review_accepted: true`, `prepublished: true`, `activation_authorized: true`,
`test_read: false`, `scientific_acceptance: false`, and exact `{path, sha256}`
references `controller_review` and `parent_receipt`. This document is not a ticket.

The controller review must bind `config_sha256` and `controller_sha256`, carry an
actual `verdict: PASS` and `reviewer_model: gpt-6-astra`. Field validation cannot
authenticate authorship; parent authentication and chronology remain external.

Use the frozen controller's `verify --config ... --sha256 ...` to inspect a
prepared config. `watch` additionally requires `--activation ...` and
`--activation-sha256 ...` and must run detached on host 175 (`k8s-node1`) with
durable CephFS output. Launch it through a parent-owned pinned-byte bootstrap:
read source once, validate its exact SHA256, compile those same bytes. Never
invoke a mutable working-tree controller in production. No production watch
service is created by preparation.

The separately reviewed composition compiles exact existing launcher/resource
adapter source bytes. The original launcher performs full `reviewed=True` and
the original supervisor owns container lifecycle. A narrow adapter dispatcher
supplies the config-bound external prerequisite guard to the original resource
adapter, which calls it twice inside its actual allocation lock. The original
adapter alone writes claim/release transactions. Scientific plans and recipes
are unchanged. This composition itself requires the new controller review.

Each start writes an exclusive intent, then spawns a detached CPU supervisor. Its
bootstrap waits for the persisted service PID/command receipt and executes exact
pinned controller bytes. No long SSH connection is used. Ambiguous starts are
never replayed: missing service, dead service with or without a running container, uncertain
claim/start, or mismatched retained generation becomes `needs_repair`. A failed
prerequisite blocks its lane while the other lane continues. Final queue exit is
nonzero if any lane fails or requires reconciliation.

The v2 repair separates immutable controller/config/activation validation from
per-job plan, review, source and preparation-file validation. Global authority
failures stop the controller. Per-job integrity failures remain within their lane:
`failed` before intent, `needs_repair` after intent, with no release, kill or replay.
The independent lane continues; aggregate failure is published only after every
lane reaches a terminal state. Offline `verify` still checks all jobs. Supervisors
verify their own job, so another lane's corrupted files cannot prevent startup.

The v3 host repair explicitly records `host_dependencies` as plan-bound source
path, immutable copy, SHA-256 and affected job IDs. A missing original dependency
is deployed with exactly the plan-pinned bytes; an existing different file is
never overwritten. Host verification checks both copies before the affected job.
`evaluation_interfaces` binds the specific legacy predecessor execution and
launcher hashes to `legacy-command-results-v1`. Only that exact historical
launcher receives the declared output-directory adapter, derived from its own
reproduced `expected_command`; there is no attribute fallback or mutable checkout
substitution. Read-only validation on host175 must verify both actual predecessor
interfaces and completed prerequisite lineage before new activation. Frozen v2
failure evidence is retained, and its terminal controller is never restarted.

Evidence lives under config `state_root`: `SERVICE.json`, `START_INTENT` per job,
`STATE.json`, `heartbeat.json`, `digest.md`, `RELAUNCH.json`, durable supervisor
logs and `EXIT.json`. Training's own supervisor receipt, retained container,
claim/release, final manifest and trained adapter remain in each plan output.
Do not restart a terminal controller or delete an intent to make a retry work.
