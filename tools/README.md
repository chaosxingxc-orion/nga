# tools/

## watchdog.py

Tier-0 of the escalation design: a deterministic script (Python 3 standard library only, no model) that
turns raw experiment logs into a small digest. Routine status costs zero model tokens. A tier-1 reading
model is invoked only for runs the digest flags, and reads only the slices the digest points to; the
orchestrator (tier 2) reads the digest and the tier-1 diagnosis only.

    python3 -P tools/watchdog.py                       # one pass over /mnt/cephfs/xingchao/experiments/jev/
    python3 -P tools/watchdog.py --root DIR --print    # other root, also print digest.md
    python3 -P tools/watchdog.py --watch                # tick every 600 s (the floor); runs are re-read on their own tier cadence

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

Progress is read from heartbeat lines: `done=N total=M`, `N/M`, or `rows: name=N ...`. **For a `rows:` line the progress is the SUM of
all its counters across scorers** (the scorers are not weighted or deduplicated, so subset scorers such as a constant baseline count
too; the sum is monotone and comparable between reads, not a count of distinct items). An empty `rows:` section is zero rows. A
`rows:` line never falls through to the `N/M` matcher, so `alive_shards=6/6` is not read as 6 of 6 done. The total is then unknown and
stated as such; a `total.txt` in the run directory supplies one. The rate is the change between the first and last heartbeat sample inside the last
`--window-seconds` (default 900) of heartbeat samples divided by the time between them (never total divided by a fixed period), restarting after a counter decrease. The projected finish is
extrapolated only when a total is known and the rate is positive.

### States (exactly one per run, deterministic)

- `done`: marker present, exit code 0.  `failed`: marker present, non-zero exit code.
- `running`: no marker, heartbeat age <= the run's stall threshold (from its watch tier, see below; there is no global default).
- `stalled`: no marker, log exists, heartbeat older than the run's stall threshold.
- `archived`: no marker, **no heartbeat file**, and the newest log older than `--archive-seconds` (default 21600, 6 h). An ad hoc
  run that finished long ago; escalation `none`, exit code 0, listed on one summary line. Anything newer stays `stalled`, and a
  run that has a heartbeat file or a marker is never archived.
- `unknown`, with a stated reason: marker without a parseable exit code or contradicting itself (DONE with a
  non-zero code, FAILED with 0), heartbeat in the future beyond `--clock-skew-seconds`, or no log and no marker.

Container state is never consulted. Without a `heartbeat.log` the newest log mtime is the heartbeat, and the digest says so
(`heartbeat_source`). Heartbeats are compared with the clock of the host running the watchdog, so run it where clocks agree
with the writer (cephfs mtimes and UTC heartbeat stamps are both fine across hosts that run NTP).

### Watch tiers (how often each run is looked at, and when it counts as stalled)

One global poll rate is the wrong model: a 30-second smoke test and an 8-hour training run do not deserve the same attention, and
a fixed stall threshold wrongly flags any job whose heartbeat period is longer than it. Each run therefore gets a tier.

| Tier | Intended for | Re-read every | Stall threshold | flags |
|---|---|---|---|---|
| `fast` | short jobs, smoke tests, under about 30 min | 10 min | 10 min | `--fast-recheck`, `--fast-stall` |
| `medium` | roughly 30 min to 4 h | 20 min | 30 min | `--medium-recheck`, `--medium-stall` |
| `slow` | over about 4 h, training runs | 60 min | 2 h | `--slow-recheck`, `--slow-stall` |

**How a run gets its tier** (first match wins; the digest row shows the tier and its source):

1. `WATCH.json` in the run directory, e.g. `{"tier": "slow"}`. Only the exact strings `fast`, `medium`, `slow` are accepted. Anything
   else (wrong case, another word, a non-string, unreadable JSON, not an object) makes the run `unknown` with a reason naming the file;
   it is never silently defaulted. A `WATCH.json` without a `tier` key is ignored (so it can carry other notes).
2. Inference from the run's own heartbeat period, over its last 20 distinct heartbeat timestamps. One positive gap is enough.
   With 3 or more gaps the period is their **median**; with 1 or 2 gaps it is the **maximum** gap, because thin evidence errs long
   (a false stall costs an escalation and trains us to ignore the flag; a stall noticed one cycle late costs almost nothing).
   Stall threshold = `--stall-multiple` (default 5) x the period, never below `--stall-floor` (default 600 s). Re-read cadence =
   the period, clamped between the `fast` and `slow` cadences. The source is shown, e.g. `max of 1 gap` or `median of 7 gaps`
   in `digest.json`, `hb2.0h` in the row. A job that beats every 10 minutes is stalled after 50 minutes of silence, not 5; a run
   with a single 2-hour gap is stalled only after 10 hours.
3. Otherwise `medium` (no positive heartbeat gap, that is at most one distinct timestamp; source `dflt`).

`--stall-seconds N` still exists as a global override of the stall threshold for every run; leave it unset normally.

**Declare a tier when you launch a job** (a one-line `WATCH.json` beside the log). Inference needs several heartbeats and sees only
the past, so a run that is just starting, or whose heartbeat period changes (for example a long evaluation phase between training
steps), is best declared. Guidance for this project:

- `slow`: the R0 baseline rerun, every verl or other training run, full-benchmark sweeps, anything planned to run past 4 hours.
- `medium`: single-model evaluation passes, data-build jobs, cell sweeps of 30 minutes to a few hours.
- `fast`: smoke tests, one-cell checks, import or config checks, anything you expect to finish in under about 30 minutes.

**Progress tracks the run between full reads.** On a tick where a run is not due, only its heartbeat tail is re-read, so
progress, rate, heartbeat time and age follow the run every tick; state, errors and the report change only at a full read (or when a
new terminal marker appears).

**Fresh heartbeat, flat progress** (a wedged shard, hung device call or deadlock: the heartbeat thread lives, the work has stopped).
A `running` run is flagged when its progress count has been unchanged over at least 3 consecutive heartbeat samples spanning
`--flat-multiple` (default 2) x its stall threshold, and, in `--watch`, two consecutive full reads both saw it flat at the same
count. A one-shot pass cannot count reads and uses the heartbeat history alone. The state stays `running` (the heartbeat is alive);
the run's escalation becomes `read` with the reason `PROGRESS FLAT <duration> at <count> with a fresh heartbeat`, and the row's
`why` cell shows it. Exit code is still 10. Runs without a progress counter are not checked. Err long: a tier whose quiet patches
are longer than the threshold should be declared `slow`.

**Shards.** With `alive_shards=a/M` in the heartbeat and exactly M `logs/shard*.log`, a shard whose log ends in `shard N/M done` finished
normally; if alive + finished falls short of M the digest notes "K of M shards neither alive nor finished". With any other layout it
says finished vs lost is not determinable (in `digest.json` `shards`) and does not guess. Healthy completions add no digest line.

**Declared total, estimate and anomalies.** `WATCH.json` may also carry `"total"`: a positive JSON integer, the run's own count of
rows it intends to write, in the unit of the progress count (the sum of the heartbeat row counters over all scorers). Example:
`{"tier": "slow", "total": 601980}`. Anything else (string, zero, negative, float, bool, null) makes the run `unknown` with the
file named. Without a declaration the digest keeps saying `(total unknown)`: the watchdog never derives a total from file sizes or
record counts (a total in the heartbeat line or `total.txt` is still honoured, and a `WATCH.json` total wins over both).
With a total the progress cell reads `27584/601980 5% 2561/min ~2-4h left`:

- The remaining time is a **range**, not a time of day. The optimistic end uses the faster of (the last `--window-seconds` rate,
  the average rate since the run or its last restart began), the pessimistic end the slower, and both ends are widened by
  `1 + (1 - fraction complete)`: wide early, narrow late. Scoring speed depends on prompt length and the sources are interleaved,
  so no early estimate is reliable; the range says so. It is prefixed `rough` while fewer than 5 samples or 15 minutes have been
  observed. `digest.json` has `left_s`, `eta_lo_utc`, `eta_hi_utc`, `eta_utc` (midpoint of the two rates) and `eta_quality`.
- `TOTAL EXCEEDED` (running or done, only with a declared total): rows written exceed the declaration, so the declaration or the run is
  wrong. `TOTAL UNREACHABLE` (running): even the optimistic end is further than `--deadline-hours` (default 48) away, checked only
  once the estimate is no longer `rough`. Both raise the run to escalation `read` with the text in the `why` cell.

**Launcher line** (a run's launcher knows the count; the watchdog cannot). In a shell launcher, replace the line that writes
`WATCH.json` by one that also takes an optional `WATCH_TOTAL`:

    printf '{"tier": "%s"%s}\n' "${WATCH_TIER:-slow}" "${WATCH_TOTAL:+, \"total\": $WATCH_TOTAL}" > "$out/WATCH.json"

and pass `WATCH_TOTAL=<rows>` in the launch environment. For the R0 full pass over the default tasks and sources (no `--limit-groups`,
no `--sample`, `--scorers all`) the count is 5 x N + N_akhilaaa3 = 5 x 119690 + 3530 = 601980: five scorers score every record and
`constant@question70` only the akhilaaa3 sources (this reproduces the `r0_smoke2` coverage 8685 / 2085). Recompute it from the loader if
the scorer set, tasks or sources change.

**Scheduling.** The `--watch` loop ticks every `--interval` seconds (default and minimum 600) and rewrites `digest.json` and
`digest.md` on every tick, so the digest's own `generated_utc` stays a reliable liveness signal. A run is re-read (markers, tail of
heartbeat, new log bytes, report) only when its own next-due time has arrived; between those times its last result is reused with the
age refreshed. A slow run is parsed once an hour. A `failed` or `stalled` run is re-checked at the `fast` cadence whatever its tier,
because something is already wrong. **A terminal marker overrides the due time:** on every tick the watcher stats the marker files (`--marker-names`) of every run, due or
not, and a marker not seen at the run's last read makes it due at once. A finished run is reported on the next tick, and the cost is
one stat per marker name per run. A run that dies without writing a marker is still found only at its own cadence (or the stall
threshold), as before.

**Floor.** `--watch` refuses `--interval` below 600 and exits 2 with the reason, unless `--allow-fast-poll` is given (tests, debugging).
A one-shot run (no `--watch`) reads everything and is unaffected.

**In the digest**, each status row has a `watch` cell: `tier/source last>next` with UTC HH:MM times, for example `slow/file 08:00>09:00`
(source `file` = WATCH.json, `hbNm` = inferred period, `dflt` = default). `digest.json` has per run `tier` (name, source, recheck_s,
stall_s) and `watch` (last_eval_utc, next_eval_utc, recheck_s).

**Making the declaration happen.** Documentation alone gets forgotten, so the launcher should write the file with the other
per-run files (relaunch command, log). For a shell launcher such as `experiments/run_sharded.sh`, one line next to the line that
writes the relaunch command is the natural place (that file is outside `tools/` and not edited here):

    echo '{"tier": "slow"}' > "$OUT_DIR/WATCH.json"      # R0 baseline rerun, verl training; use "fast" for smoke tests

Default to `slow` in the launchers for the R0 rerun and verl, and let smoke-test launchers write `fast`.

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

    nohup setsid python3 -P tools/watchdog.py --watch \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

One watcher per out-dir (enforced with a lock; a restarted watcher takes over). A stale digest shows in `generated_utc`.
It only reads logs and writes two files; it never touches containers, processes or NPUs.

`-P` needs Python 3.11+ (this host); `npu` has 3.10, where plain `python3 tools/watchdog.py` is equivalent because only the script's
own directory lands on `sys.path`.

### Tests

    python3 -P tools/test_watchdog.py

## Final interface summary

**States** (one per run): `done` (marker, exit 0), `failed` (marker, non-zero), `running` (no marker, heartbeat within
the run's tier stall threshold: fast 10 min, medium 30 min, slow 2 h, or 5x its inferred period), `stalled` (no marker, older heartbeat), `archived` (no marker, no heartbeat file, newest log older
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
    cd /home/xingchao/workspace/nga && nohup setsid python3 -P tools/watchdog.py --watch \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

`npu` (Python 3.10 has no `-P`, so plain `python3`; run it from a directory you do not distrust, and the repo checkout path there
may differ, so give the script's absolute path):

    mkdir -p /mnt/cephfs/xingchao/experiments/jev/_watchdog
    cd / && nohup setsid python3 /path/to/nga/tools/watchdog.py --watch \
        >> /mnt/cephfs/xingchao/experiments/jev/_watchdog/watchdog.log 2>&1 < /dev/null &

Run one watcher per out-dir (a second exits with code 3). Both hosts write the same out-dir, so run it on only one of them. Check
liveness through `generated_utc` in `digest.json`.
