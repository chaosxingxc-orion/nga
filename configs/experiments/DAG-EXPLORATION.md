# Configured exploration task adapters

`tools/experiment_dag_exploration_v1.py` and its service register the accepted
native DEV72 shard and named-forward profiling schemas. They compose with the
existing DAG policy without changing the frozen native implementation. The
accepted example contains two completed `external_frozen` tasks; it is not a
production queue activation.

## Functional baseline

- Exact plan, attempt, host source, image, command, device and binding identity
  are checked. Unknown schemas remain unsupported until a reviewed adapter is
  registered; the new model-specific DEV72 reference and dual-identity shard
  interfaces are not implicitly admitted by this version.
- Resource release is separate from result validity, CPU artifact availability,
  numerical equivalence and scientific admission. Operational success never
  creates numerical or scientific acceptance.
- Retained-container identity includes its actual start and finish timestamps.
  Reusing the same container ID after a restart cannot reuse an old release.
- Durable dispatch intent precedes effects. Uncertain launches retain ownership
  and are not blindly retried; same-configuration service restart retains its
  journal. An all-external graph does not justify deploying an idle controller.
- Existing per-package guards retain allocation-lock, applicable queue priority
  and actual-device admission authority. A historical released snapshot does
  not prove a device remains idle.

The accepted component passed 69 combined regression tests and 39 independent
checks on November 3, 2026. This is an ordinary independent engineering review,
not designated Astra/Fable scientific acceptance or evidence of deployment.

## Add useful executable queue depth

Prepare independent branches concurrently; distinguish planned, blocked,
executable, running and completed work. Keep completed work external and do not
repeat it to fill a queue. Shared multi-card experiments appear in each card's
coverage but count once in the unique experiment total. Ready-depth targets are
operational replenishment goals, not reasons to invent experiments.

Bind only causal dependencies: required artifacts, numerical acceptance,
scientific admission, execution success or physical release. Unrelated CPU
analysis must not hold NPU resources. A new task must use the actual most recent
owner of its requested card, including an already-started successor.

Changes to a dispatch graph create a new immutable generation with explicit
reconciliation of existing owners and intents. Production activation requires
real managed successor actions and exact independent composition review.

## Launch and monitoring lessons

The host launch projection is a complete configuration contract: interpreter,
argv and environment. Preserve validated `PYTHONPATH`, backend-autoload flags
and other required environment fields, not just the Docker command. A host
preflight and actual detached launch must use the same complete projection.
On host175 the explicit validated interpreter is `/usr/bin/python3.12`; the
default `/usr/bin/python3` does not support `-P`.

Distinguish transport receipt from actual execution proof. Confirm the retained
container, command, image, device mapping and generation once after launch. A
failure before host-attempt creation may be repaired only after proving that no
claim or launch occurred, retaining the original failure and a new transport
record. Do not erase attempts or retry uncertain starts.

Routine monitoring remains scripted, at events or approximately 600 seconds,
reading logs, heartbeat, progress, terminal and release records. CPU scoring and
independent result reconstruction run asynchronously. Agents read bounded
digests and investigate only pointed exceptions.
