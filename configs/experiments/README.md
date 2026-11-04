# Configuration-triggered experiment entrypoint

This is the first functional adapter of the versioned experiment interface. It
reuses the **existing reviewed BEV host supervisor and runner**. New runs of this
contract supply a reviewed package and a JSON configuration; they do not copy or
rewrite a launch script. It does not generate new plans, grant admission, bypass
TEST rules, launch CPU consumers, assemble training queues or publish results.
Those integrations are still required before claiming a complete configuration-only
engineering foundation. Existing admitted experiments continue independently.

## Commands

Run on the host which owns the paths and NPU. Host checks and resource acquisition
remain inside the existing supervisor. Use a pinned repository release containing
`tools/experiment_entrypoint.py`; never replace a running frozen package.

```bash
python3 -B -P tools/experiment_entrypoint.py dry-run --config /absolute/path/config.json
python3 -B -P tools/experiment_entrypoint.py validate --config /absolute/path/config.json
python3 -B -P tools/experiment_entrypoint.py status --config /absolute/path/config.json
python3 -B -P tools/experiment_entrypoint.py start --config /absolute/path/config.json --config-sha256 EXACT_CONFIG_SHA256
```

- `dry-run` validates schema and all reviewed dependency hashes, then shows the
  exact argument arrays. It does not execute a model or a supervisor.
- `validate` additionally calls the real existing runner's `verify` operation,
  including its request/protocol checks. It does not start inference.
- `start` requires the exact configuration hash and approved attempt, calls real
  validation, then the existing detached/guarded start API. Reusing an existing
  attempt is rejected. On a timeout/failure, inspect receipts before any retry:
  a timeout is not proof that no process started.
- `status` reads structured receipts only. A launch receipt does not prove
  current liveness; complete marker files do not independently validate results.
  It never reads raw experiment logs or declares scientific acceptance.

Routine monitoring still uses watchdog events/approximately 600-second polling.
This command hashes the package and model dependencies, so it is intended for
configuration admission and occasional manual status, not high-frequency polling.

## Configuration contract v1

Exactly these fields are accepted: `schema`, `kind`, `plan`, `review`, `attempt`.
Schema is `nga-experiment-entrypoint-v1`, kind is `bev-dev-v1`, and attempt is a
positive integer. Each pin contains exactly an absolute `path` and a lowercase
SHA256. Symlinks and parent traversal are rejected. No shell, command string,
credentials, arbitrary environment, or `unreviewed` override is accepted.

The plan must be a frozen `bev-dev-plan-v1` TRAIN-derived DEV package. The review
must bind that exact plan and every code/input/model dependency, authorize the
attempt, and explicitly carry `scientific_acceptance: false`. The existing runner
is responsible for the task's fixed population and numerical contract. Input
configuration, review and executable package are trusted operator artifacts; this
launcher is not a sandbox for untrusted code.

[`bev-2b-dev-v1.json`](bev-2b-dev-v1.json) is an actual pinned instance, not a
synthetic experiment. Its attempt 1 was already launched by the existing workflow
on 2026-11-02; use it for validation/status and do not try to launch it again.
It does not acquire new permission from being committed.

For a new model or task instance, create its required reviewed package and new
configuration. If the existing adapter does not support the contract, add a named
adapter with real integration and negative tests, review and release a new tool
version. Do not embed an ad-hoc shell recipe in the configuration.

## Verification and limits

`python3 -B -P tools/test_experiment_entrypoint.py` covers actual CLI/subprocess
argument propagation through executable CPU fixtures, changed dependency/config
rejection, review/attempt binding, duplicate start refusal and honest status
classification. These fixtures do **not** prove a new live NPU launch. Separately,
`dry-run`, `validate` and `status` were run successfully on the real host175 2B
package, using the actual runner. No NPU/service was launched by this change and
no frozen package or allocation ledger was modified.

This first increment locks the trigger interface for one existing inference
contract. Config-driven package preparation, CPU scoring, multi-task queues and
report publication remain explicit functional backlog, rather than claimed
features. Performance tuning of the wrapper follows functional integration.

Reusable reliability and efficiency acceptance criteria: [Recovery and efficiency contract](NFR-RECOVERY-CONTRACT.md). This records requirements and known gaps, not a claim of complete deployment.
