# E30 — Explicit-plan typed experiment recovery controller

Pre-registered before real E30 execution, 2026-10-30. Defects 12/16: execution and
measurement provenance. The unconstrained degenerate optimum is to publish a
success marker without executing or independently checking items. Counterparts
must reject a missing item, wrong container/device, forged success and failed
audit. No model score, training benefit or complete host-failure guarantee follows.

The new controller is outside every existing frozen run. It operates only on one
explicit immutable plan with parent review bound to its byte hash, a frozen model
configuration, exact worker/controller wrappers, launch/resume scripts, preparation
helper, tests, this preregistration, verifier and container specification. The approved
configuration fixes expected_count=24; equal progress/total alone is insufficient. It does not
discover or adopt arbitrary experiments. New containers carry plan/role labels;
only a labelled created container with a persisted creation intent may be adopted
across create/receipt/start interruption. Existing unlabelled containers are not
silently migrated. NPU ownership must already belong to this exact run in the
allocation file; every start holds its lock and checks actual live device maps.

Retries are limited to explicitly allowed signal exits 137/143, with at most two
for the E30 fixture. These codes alone do not prove an infrastructure cause. Semantic errors and nonzero audit verdicts block. Successful
inference terminal forbids rerun, including a contradictory nonzero Docker exit.
Item receipts remain untouched. Failed execution summaries are archived before
restart; each interrupted audit receives a separate retained container and output
generation. Full independent metric verification is rerun after inference resumes.
The controller never treats Docker exit 0 alone as success and keeps review flags.
At audit acceptance and every completed-state check, it verifies frozen inputs,
exact inference/audit identities and specifications, and both exited/0 states. Audit
terminals bind the audit plan, inference terminal and report hashes; receipt, report
and terminal file timestamps must follow the required generation order.

Real admission experiment: CPU-only on 175, immutable existing image, no NPU maps
or shared allocation changes. A deterministic 24-item worker atomically saves item
receipts and heartbeats; the independent verifier checks exact index coverage,
receipt checksums and sum of squares. Inject an actual Docker SIGKILL after at least
three receipts, record their hashes, and let the controller restart the same retained
container. Kill the first audit container while it is running; a new audit generation
must finish independently. Pass requires complete 24-item coverage, identical bytes
for the pre-interruption receipts, retained failed audit generation, successful
independent verification and a controller terminal with exact hashes. Exit 1 or a
missing receipt must not produce success (unit integration counterparts).

All real execution is detached and retained, with CephFS logs, timestamped progress,
terminal markers and exact relaunch scripts. Implementation tests are not proof of
real recovery. Parent review is required before the real CPU fixture is launched.
Known scope limits: host reboot during filesystem writes, Docker daemon data loss,
and arbitrary old unlabelled-run adoption remain outside this first admission.
