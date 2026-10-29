# tools/

## watchdog.py

Tier-0 of the escalation design: a deterministic script (Python 3 standard library only, no model) that
turns raw experiment logs into a small digest. Routine status costs zero model tokens. A tier-1 reading
model is invoked only for runs the digest flags, and reads only the slices the digest points to; the
orchestrator (tier 2) reads the digest and the tier-1 diagnosis only.

    python3 -P tools/watchdog.py                       # one pass over /mnt/cephfs/xingchao/experiments/jev/
    python3 -P tools/watchdog.py --root DIR --print    # other root, also print digest.md
    python3 -P tools/watchdog.py --watch --interval 120

Outputs go to `--out-dir` (default `<first root>/_watchdog/`): `digest.json` (complete but bounded) and
`digest.md` (hard cap `--max-md-bytes`, default 6000, cut at a line with an explicit `[TRUNCATED ...]` note).
Both are written to a temp file and renamed, under a lock, so a reader never sees a half-written file and
concurrent invocations cannot interleave. Directories whose name starts with `.` or `_` are never scanned
as runs, so the output directory is not mistaken for a run.

### Conventions (CLAUDE.md rule 7), all overridable

A run is a directory below a root (depth <= `--max-depth`, default 4) that contains any of: a marker file, `heartbeat.log`,
a log (`*.log`, `logs/*.log`), or `report.json`. A `<dir>.*log` file beside the directory also counts. Discovery does not
descend into a run directory.

| item | default | option |
|---|---|---|
| terminal marker, content holds the exit code (`rc=0 utc=...`, `exit_code: 0` or a bare integer) | `DONE`, `FAILED`, `exit_code`, `EXIT_CODE` | `--marker-names` |
| heartbeat file, lines start with an ISO-8601 UTC timestamp (naive timestamps are read as UTC) | `heartbeat.log` | `--heartbeat-name` |
| logs scanned for warnings/errors | `*.log`, `logs/*.log` | `--log-globs` |
| report scanned for suspicious metrics | `report.json` | `--report-name` |

Progress is read from heartbeat lines: `done=N total=M`, `N/M`, or `rows: name=N ...` (sum of counters; the total is
then unknown and stated as such; a `total.txt` in the run directory supplies one). Throughput is measured over the last
`--window-seconds` (default 900) of heartbeat samples, restarting after a counter decrease. The projected finish is
extrapolated only when a total is known and the rate is positive.

### States (exactly one per run, deterministic)

- `done`: marker present, exit code 0.  `failed`: marker present, non-zero exit code.
- `running`: no marker, heartbeat age <= `--stall-seconds` (default 300, five missed one-minute heartbeats).
- `stalled`: no marker, log exists, heartbeat older than that.
- `unknown`, with a stated reason: marker without a parseable exit code or contradicting itself (DONE with a
  non-zero code, FAILED with 0), heartbeat in the future beyond `--clock-skew-seconds`, or no log and no marker.

Container state is never consulted. Without a `heartbeat.log` the newest log mtime is the heartbeat, and the digest says so
(`heartbeat_source`). Heartbeats are compared with the clock of the host running the watchdog, so run it where clocks agree
with the writer (cephfs mtimes and UTC heartbeat stamps are both fine across hosts that run NTP).

### Error signatures

Lines matching error words (error, exception, traceback, fatal, failed, OOM, killed, ...) or warning words are normalized
(ANSI codes, timestamps, hex addresses, UUIDs, PIDs, absolute paths, line numbers, bare integers and `shardN`-style indices
become placeholders) and grouped. Per signature the digest has the count, first and last occurrence (timestamp when the
log has one, otherwise line numbers), one exemplar line cut to `--exemplar-width` (default 160), and a pointer: log path,
line range (`--ctx-before` 10, `--ctx-after` 3) and byte offset. At most `--max-signatures` (default 8) per run, errors
before warnings, then by count; the number omitted is stated. Only the exemplar line is shown, never a traceback. Credentials
(URL userinfo, `token=`, `password=` ...) are redacted before anything is stored. Logs are scanned incrementally in
`--watch` mode (only appended bytes).

### Suspicious metrics (`report.json`)

The detector walks the whole JSON and flags, each with its JSON path:

- `exact_zero` / `exact_one`: a rate or accuracy-like value (key matches `--rate-keys`) that is exactly 0 or 1.
- `identical_across_cells`: at least `--min-cells` (3) sibling cells (dict values, list rows, or flat numbers) with the same
  value for the same metric, which suggests an input that never varied.
- `low_sample_count`: a sample-count key (`n`, `n_units`, `count`, ...) below `--min-n` (default 30) in a dict.
- `non_finite`: NaN or infinity.

This is a tripwire, not a verdict: legitimate zeros exist (a constant-classifier baseline has rate 0.0 on some branches). The
digest counts per kind and lists up to `--max-flags-per-kind` items per run; a human or tier-1 model decides.

### Escalation level (one rule)

- `decide`: the run is `failed` or `stalled`, or it is `done` with any suspicious metric (the result must be accepted or rejected).
- `read`: otherwise, if the state is `unknown`, or there are suspicious metrics in a run still going, or error-severity lines.
- `none`: everything else (including warnings only).

For `read` and `decide` the digest lists pointers: tail of the newest log, the terminal marker, error exemplars, and the
`report.json` paths. Tier 1 reads those slices first; a `decide` run still gets a read before the orchestrator chooses.

### Exit code (worst state, for a scheduler)

0 all done and nothing to decide, 10 some running, 20 some unknown or no runs found, 30 some stalled, 40 some failed.
A done run with suspicious metrics counts as done here (see `escalation` in the digest). `--watch` exits with the last
pass's code on SIGTERM; usage errors exit 2; a second `--watch` on the same out-dir exits 3.

### Running it detached (rule 7)

    nohup setsid python3 -P tools/watchdog.py --watch --interval 120 \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

One watcher per out-dir (enforced with a lock; a restarted watcher takes over). A stale digest shows in `generated_utc`.
It only reads logs and writes two files; it never touches containers, processes or NPUs.

`-P` needs Python 3.11+ (this host); `npu` has 3.10, where plain `python3 tools/watchdog.py` is equivalent because only the script's
own directory lands on `sys.path`.

### Tests

    python3 -P tools/test_watchdog.py
