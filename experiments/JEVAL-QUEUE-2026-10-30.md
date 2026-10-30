# E34 — explicit JEVal execution queue

Pre-registered before queue or recovery-fixture launch. Defects 12/16: executable
identity and measurement integrity. No new model training or metric change.
The unconstrained optimum of a completion count is to mark work complete without
running it. Its discrimination counterparts require actual retained Docker exit,
full native terminal/output binding and independent full-population audit; altered
config, incomplete terminal, foreign container and changed output must fail.

## Scope and sequence

An approved immutable plan names an ordered, nonduplicate subset of Open-Jev2,
Open-Jev9 and Nimble E33 formal configurations. Each configuration, parent approval,
queue source, wrapper, launch/resume commands, container specification and this
protocol are frozen. The plan does not select a model from test scores.

Each model needs its separately accepted native probe. Open-Jev additionally needs
an explicit frozen `batch_admission` file with `candidate_batch_admission: true`
and the exact `approved_config_sha256`. The longest single candidate prompt alone
does not establish worst candidate-batch memory. A plan cannot add an unapproved
future entry by mutating its files; a later queue gets a separate frozen plan.
Nimble can therefore execute first while Open-Jev admission is completed.

## Execution and identity

Use only 175 Docker daemon (`k8s-node1`) and immutable image
`sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7`.
The controller is a retained detached CPU container with the Docker socket and
CephFS mounted. All model entries explicitly use chip 1, acquired/released under
the shared allocation flock with actual live-device checks. No chips 6/7 adoption.

The old frozen host launcher depends on host Docker CLI/hostname. This controller
uses Docker API to execute its exact frozen `NPU_SPEC.json` and `run.sh`, adding
only queue-intent labels. It produces the same native launch receipt schema.
Model code, prompt, probability, metric and dataset files remain unchanged.
Image, command, entrypoint, complete explicit environment, mount multiset, device
triples, network mode and shared memory are checked. Finisher uses the same native
CPU wrapper, immutable image defaults, `TORCH_DEVICE_BACKEND_AUTOLOAD=0`, no device,
network none, CephFS and Docker socket mounts.

Before Docker create, the controller persists an intent bound to the plan hash,
entry, role and full spec hash. Only a matching labelled **created** container may
recover the create-before-receipt seam. Unknown containers fail closed. A saved
receipt must match actual ID/config/wrapper. Matching running entries are observed,
not restarted; created entries are started after locked resource reconciliation.
The finisher uses the same intent/receipt process. Controller SIGKILL without a
terminal resumes from actual identities and immutable evidence. A recorded model,
finisher or queue failure stops the sequence for reviewed intervention: no blind
or unlimited retry, no overwrite of successful evidence. Native item-resume
commands remain available for a separately reviewed failed-model continuation.

## Completion and release

A successful model requires inference and independent finisher actual exit 0,
ordered successful wrappers/terminals, config identity, all 11,257 expected items,
native `report.json`/`PROBE.json` hashes and independent audit hash/report binding.
`VERIFIED_SCOPED` and all review flags are preserved. This controller does not
upgrade that audit's token-provenance scope to independent tokenization.

Acceptance hashes are immutable evidence for subsequent steps. Before releasing
chip 1, the controller writes release intent, confirms exact ownership and no
live mapping, updates allocation atomically, then writes release receipt. A crash
between allocation release and receipt is recoverable only with matching release
intent and allocation evidence. No stale free record is sufficient.

Every poll writes bounded digest/status with item phase, count, per-chip throughput,
one-chip count and reserved memory from the underlying status. Failures produce a
pointer to a separate failure file. Logs, heartbeats, terminal and exact restart
command persist on CephFS. Successful prior acceptance is rechecked on restart.

## Admission checks and actual fixture

Focused tests must reject changed config/receipt, foreign container, unknown
created container, terminal loss/tampering, audit changes and failed-process retry;
flags survive successful acceptance. Tests cover create/receipt/finisher seams.

A separate CPU-only real Docker fixture injects actual SIGKILL into controller
children after inference creation, after inference receipt and after finisher
creation. Restart must use the same two retained container IDs and reach actual
exit 0 without duplicate launch. Its private allocation fixture is isolated from
the real chip registry, and it emits no model test score. This is bounded evidence
for those Docker seams, not an arbitrary host-failure or NPU recovery certificate.

## Additional independent audit and plan interface

Before final queue acceptance, the native finisher is followed by a separate
retained CPU container running `audit_jeval_inference_hardened.py`. Its source and
wrapper are frozen in the queue plan. It checks complete eligibility, independent
probe tokenization, schema and suspicious cells in addition to the original audit.
The queue binds its successful terminal and output to the exact config and model
report. Native, inherited and hardened review flags remain separate in acceptance.
A native success alone does not release the resource or advance the queue.

Plan schema 1 requires `out`, `container`, `image`, `allocation`, `files`,
`preparation_files` and `entries`. `files` contains the immutable queue source,
queue preparation files, configuration JSONs, their parent approvals, native
NPU specifications/wrappers, and hardened auditor/wrappers. Do not put all model
weights into queue `files`: each config already freezes them and they are fully
rehashed at admission, restart and final acceptance rather than every 10 seconds.

`preparation_files` has exactly `wrapper`, `launch`, `resume`, `preregistration`,
`container_spec`. The queue's actual retained Docker container must match this
frozen spec and `LAUNCH_RECEIPT.json` (container ID, image, command, entrypoint,
`plan_sha256`, `wrapper_sha256`). The specification uses explicit image-default
environment entries plus the CPU backend setting; never print their values.

Each entry contains `key`, `config`, `config_sha256`, and `hardened` with `auditor`,
`wrapper`, `out`, `container`. Open-Jev entries additionally require
`batch_admission` and `batch_admission_sha256`. All paths are absolute. The hardened
wrapper runs the frozen queue source with:

```
python3 -P <queue.py> --audit-config <config.json> --auditor <audit.py> --audit-out <out>
```

It redirects output to persistent log and writes the ordinary `EXIT` wrapper
marker after this command; the queue audit subcommand writes `COMPLETE.json`
including config/output hashes. Standard queue invocation is
`python3 -P <queue.py> --plan <plan.json>`. Its wrapper likewise records `EXIT`.
Parent approval and all per-entry admissions are engineering acceptance, not Astra
signoff. No production queue is launched by this implementation task.

## Read-only completion waiter for already running models

The separate `jeval_hardened_waiter.py` may be attached as an observer to three
explicitly named existing Kev inference/native-finisher pairs. Its frozen plan
binds exact source container IDs, complete configuration/resource specifications,
launch receipt hashes, source config hash and independent auditor. Docker access
is GET-only and the chip registry is never written. It waits for both actual
containers to exit 0 and successful native terminals/wrappers and audit hashes,
then performs the E35 audit in its own retained CPU container. A changed source
identity or unsuccessful exit terminates with failure evidence. Source workers
are never restarted or mutated. The separate waiter has its own persistent
heartbeat, bounded digest, terminal, wrapper and exact relaunch artifacts.
