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
`digest.md` (hard cap `--max-md-bytes`, default 12000).
Over the cap, content is dropped by priority, not by position, in whole blocks: (0) summary line and status rows of
failed/stalled/unknown runs, (1) other status rows, (2) pointers and errors of failed/stalled runs, (3) flags on the primary
scorer (and pointers of runs that have them), (4) error signatures, (5) flags on other scorers, (6) everything else (clean-done
and archived lines, suppression audit, notes). Once a block of some priority does not fit, every lower-priority block is dropped
too. A final `[TRUNCATED ...]` line says how many blocks and bytes were dropped and which kinds. `digest.json` is never cut.
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
- `archived`: no marker, **no heartbeat file**, and the newest log older than `--archive-seconds` (default 21600, 6 h). An ad hoc
  run that finished long ago; escalation `none`, exit code 0, listed on one summary line. Anything newer stays `stalled`, and a
  run that has a heartbeat file or a marker is never archived.
- `unknown`, with a stated reason: marker without a parseable exit code or contradicting itself (DONE with a
  non-zero code, FAILED with 0), heartbeat in the future beyond `--clock-skew-seconds`, or no log and no marker.

Container state is never consulted. Without a `heartbeat.log` the newest log mtime is the heartbeat, and the digest says so
(`heartbeat_source`). Heartbeats are compared with the clock of the host running the watchdog, so run it where clocks agree
with the writer (cephfs mtimes and UTC heartbeat stamps are both fine across hosts that run NTP).

### Explanations

If a run directory holds `WHY_STOPPED.json` or `WHY_FAILED.json` (`--why-names`), its `note` (else `why`, `reason`, `summary`, or
the first string value, else the raw text) is shown as one line, clipped, under that run, so an expected failure is not re-diagnosed.
A note alone changes nothing.

### Expected failures (the only downgrade)

An explicit boolean `"expected": true` in the WHY file (strictly JSON `true`; not a string, not `1`, not a keyword in the note)
sets the escalation to `none` when, and only when, the run has a terminal marker that parsed (state `done` or `failed`) or is
`archived`. A `running`, `stalled` or `unknown` run keeps its escalation whatever the file says. When applied, the status row shows
`expected=yes` (the reason reads "expected=yes (was decide: ...)"), the digest's `expected_downgrades` lists the count and run ids
for audit, and the run keeps its `state` and its exit-code contribution; flags and error lines are still reported. Deciding that a
failure is acceptable is a judgement, so it needs this explicit key.

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

Suppression by scorer role (`--suppress-roles`, default `constant,uniform,mock-*`, fnmatch patterns). Degenerate baselines are
supposed to be degenerate, so `exact_zero`, `exact_one` and `identical_across_cells` whose JSON path passes through a
segment with a suppressed role are not flagged; they are counted, and the digest prints one line per run, "suppressed N
expected-degenerate values (constant x.., uniform x..)", so the suppression is auditable (`suppressed` in digest.json).
Never suppressed: `--protect-roles` (default `primary,empty_input,question_only`; a protected segment wins), and every
`low_sample_count` and `non_finite` flag for every scorer, so an `n = 0` cell always shows. Judgment call: when the report's
own `primary` scorer name matches a suppress pattern (a mock check run), the `primary` segment and `decision_lines` are
treated as that mock and suppressed as `primary=<name>`; a real primary is never suppressed. `--no-suppress` turns the whole
mechanism off and shows everything.

This is a tripwire, not a verdict: legitimate zeros exist (a constant-classifier baseline has rate 0.0 on some branches). The
digest counts per kind and lists up to `--max-flags-per-kind` items per run; a human or tier-1 model decides.

### Escalation level (one rule)

- `decide`: the run is `failed` or `stalled`, or it is `done` with any suspicious metric (the result must be accepted or rejected).
- `read`: otherwise, if the state is `unknown`, or there are suspicious metrics in a run still going, or error-severity lines.
- `none`: everything else (including warnings only, and every `archived` run).

For `read` and `decide` the digest lists pointers: tail of the newest log, the terminal marker, error exemplars, and the
`report.json` paths. Tier 1 reads those slices first; a `decide` run still gets a read before the orchestrator chooses.

### Exit code (worst state, for a scheduler)

0 all done or archived, 10 some running, 20 some unknown or no runs found, 30 some stalled, 40 some failed.
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

## Final interface summary

**States** (one per run): `done` (marker, exit 0), `failed` (marker, non-zero), `running` (no marker, heartbeat within
`--stall-seconds`, default 300), `stalled` (no marker, older heartbeat), `archived` (no marker, no heartbeat file, newest log older
than `--archive-seconds`, default 21600), `unknown` (reason given). The marker is the source of truth; container state is never read.

**Escalation**: `none`; `read` (tier-1 model reads the listed pointers); `decide` (orchestrator chooses, after the read). `decide`:
failed, stalled, or done with suspicious metrics. `read`: unknown, suspicious metrics in a running run, or error lines. `none`:
otherwise, archived, and runs downgraded by `"expected": true`.

**Exit codes**: 0 all done or archived, 10 some running, 20 some unknown or no runs, 30 some stalled, 40 some failed; 2 usage error;
3 a second `--watch` on the same out-dir. Exit codes follow state, not escalation, so an expected failure still exits 40 until it is
moved out of the scanned tree (for example under `_archive/`).

**Suppression** (`--suppress-roles`, default `constant,uniform,mock-*`): exact 0/1 and identical-across-cells values under those scorer
names are counted, not flagged, with an audit line per run. **Protection** (`--protect-roles`, default
`primary,empty_input,question_only`): never suppressed; `low_sample_count` and `non_finite` are never suppressed for anyone; a mock
primary (`primary` whose report name matches a suppress pattern) is suppressed as `primary=<name>`. The rule keys off the scorer name;
`--no-suppress` shows everything.

**Digest size**: `digest.md` is capped at `--max-md-bytes` (default 12000) with priority-ordered dropping and an explicit note of what
was dropped; `digest.json` is complete.

**Launch detached (CLAUDE.md rule 7)**

This host (Python 3.11, `-P`):

    mkdir -p /mnt/cephfs/xingchao/experiments/jev/_watchdog
    cd /home/xingchao/workspace/nga && nohup setsid python3 -P tools/watchdog.py --watch --interval 120 \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

`npu` (Python 3.10 has no `-P`, so plain `python3`; run it from a directory you do not distrust, and the repo checkout path there
may differ, so give the script's absolute path):

    mkdir -p /mnt/cephfs/xingchao/experiments/jev/_watchdog
    cd / && nohup setsid python3 /path/to/nga/tools/watchdog.py --watch --interval 120 \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

Run one watcher per out-dir (a second exits with code 3). Both hosts write the same out-dir, so run it on only one of them. Check
liveness through `generated_utc` in `digest.json`.
