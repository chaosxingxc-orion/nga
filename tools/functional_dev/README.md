# Active CPU/NPU separated RC1 entry

The deployed successor is `phased/queue_proposal.py`, with exact reviewed `phased/config.json` and `phased/phase_wrapper.py`. It waits for existing training, runs one bounded smoke, then eight full DEV bundles. NPU inference exits before scoring in a separate CPU container (two jobs, four cores each). The 27B waiter depends on selected inference exits, not CPU scoring. Output: `followup-cpu-separated-rc1`. Actual NPU smoke remains pending.

Run the host dispatcher detached from the phased directory with `python3 -I -u queue_proposal.py` only after reconciling its existing live handle; do not launch duplicates. The installed dispatcher is already waiting on175. Terminal identity and artifact tests passed independent review. The original files below are retained as the superseded monolithic source and integration reference; do not restart that queue.

# Fixed RC1 functional DEV entry

This is the reviewed deployment source for the eight trained-adapter DEV bundles on175. The configuration is consumed by queue.py; model/data/recipe identities remain fixed for this campaign. Protocol: experiments/RC1-FUNCTIONAL-DEV.md. These scripts depend on the pinned existing evaluation closure on Ceph and the installed image; they are not a standalone laptop evaluator.

Host: python3 -I -u queue.py (detached, persisted output, one queue lock). Do not launch another instance while the existing queue or its containers are alive. Host isolated mode is necessary because queue.py otherwise shadows Python's standard-library module. Container wrapper uses python3 -B -P, preserving Ascend PYTHONPATH.

Queue waits for actual training exit, matching3116-step publication and external hash-bound review; the first completed lane runs a fixed small smoke, followed by full lanes only if it succeeds. Retained containers, logs, per-lane EXIT and exact commands live in followup-record-grade on Ceph. An actual failed run remains failed and requires diagnosis before a new attempt. TEST and Track T are excluded. CPU metrics currently execute within the same process; independent CPU phase separation is in progress and is not claimed here.

Validation: five feature tests plus seven independent scoped checks, including actual frozen-stage mock execution and zero-score-call store resume, passed. ActualNPU FP32/memory/throughput remains pending. First-lane smoke does not establish all-model memory capacity. Run tests with python3 -B -P test_record_grade.py from this directory. Existing evidence and review are local process records; public current state is maintained in the GitHub Wiki.
