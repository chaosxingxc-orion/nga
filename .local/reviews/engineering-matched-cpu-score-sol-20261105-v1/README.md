Private engineering measurement artifacts. Prospective protocol is copied unchanged;
ENGINEERING-ADDENDUM.json selects the current scoped CPU candidate only. No scientific
protocol amendment, release qualification, NPU execution, training, or new inference.

preflight.py obtains retained installed closures and source fixtures through Docker's
read-only archive API and compares accepted receipts. setup.py freezes measurement
pins and starts a detached retained queue. queue.py waits for Docker terminal events
(600-second fallback inside the controller); it accepts stages only from runtime
markers plus exact summary/config/manifest checks. await_terminal.py subscribes once
to the queue's terminal and copies its evidence archive. No agent stage polling.

instrument.py wraps the existing default scorer entrypoint without changing image
files. RESOURCE.json measures the child with same-host monotonic clock and Linux
getrusage; report.json is the existing narrower scorer interval. These intervals are
nested and must not be added. Last process-I/O sample is partial logical I/O only.
No physical Ceph I/O attribution is made. Warmup reads at most 16 MiB of the frozen
requests file, not all records; cache residency is unknown, and no cache is flushed.

Original saved-result source and installed code are read-only. Code snapshots are
hashed, never imported from archive extraction. The queue alone has the Docker socket;
stage containers have no socket and no devices. Queue socket access is orchestration
authority, not evidence of application sandbox security. All outputs remain private.
