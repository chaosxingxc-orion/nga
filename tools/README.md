# tools/

## watchdog.py

Tier-0 of the escalation design: a deterministic script (Python 3 standard library only, no model) that
turns raw experiment logs into a small digest. Routine status costs zero model tokens. A tier-1 reading
model is invoked only for runs the digest flags, and reads only the slices the digest points to; the
orchestrator (tier 2) reads the digest and the tier-1 diagnosis only.

    python3 -P tools/watchdog.py                       # one pass over /mnt/cephfs/xingchao/experiments/jev/
    python3 -P tools/watchdog.py --root DIR --print    # other root, also print digest.md
    python3 -P tools/watchdog.py --watch                # tick every 600 s (the floor); runs are re-read on their own tier cadence

Outputs go to `--out-dir` (default `<first root>/_watchdog/`): `digest.json` (complete but bounded), `digest.md` (hard cap
`--max-md-bytes`, default 16000) and `npu_history.json` (a few KB: the last 6 h of per-chip AICore passes, see Host utilisation), and `_retained/` (dated copies of passes
that carried a flag, see Retention).
Over the cap, content is dropped by priority, not by position, in whole blocks: (0) summary line (with the NPU fragment and the
dispositioned-by-WHY audit line) and status rows of failed/stalled/unknown runs that have no `expected` disposition, (1) other status
rows, (2) pointers and ERROR signatures of failed/stalled runs, (3) flags on the primary scorer (and pointers
of runs that have them), then the host-utilisation (NPU) block, (4) ERROR signatures of other runs, (5) WARNING signatures and flags on
other scorers, (priority 0 also holds due and invalid obligations and priority 3 pending ones, see Obligations; priority 5 also holds the status rows of runs with an `expected` disposition, own or inherited, so they never take space from an unexplained
run), (6) everything else (clean-done and archived lines, suppression audit, notes). Once a block of some priority does not fit, every lower-priority block is dropped
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
| terminal marker, content holds the exit code: plain text (`rc=0 utc=...`, `exit_code: 0`, a bare integer) or a JSON object whose exit code is an **integer** under the first present key of `exit_code`, `exit_status`, `returncode`, `return_code`, `rc` (and optionally `utc`; `{"exit_code": 0, "error": "..."}` with a non-empty `error` is a conflict, not a success) | `DONE`, `FAILED`, `exit_code`, `EXIT_CODE`, `EVAL_COMPLETE.json`, `K0_COMPLETE.json` | `--marker-names` |
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
  non-zero code, FAILED with 0), heartbeat in the future beyond `--clock-skew-seconds`, or no log and no marker. A marker problem is a
  **named condition** (`condition` in `digest.json`, shown in the row's state cell): `marker_unparseable` (`MARKER UNPARSEABLE`) or
  `marker_conflict` (`MARKER CONFLICT`), escalation `read`, state still `unknown` (exit code 20). **A run with a marker file is never
  `stalled`, whatever its heartbeats say**; the marker is the source of truth for whether it finished.

Container state is never consulted. Without a `heartbeat.log` the newest log mtime is the heartbeat, and the digest says so
(`heartbeat_source`). **A run's heartbeat is the newest sign of life across ALL its sources**: its own `heartbeat.log` (or the newest
log mtime when it has none) and every per-worker source below it, i.e. the heartbeat files, `perf.json` and `progress.log` found
`--throughput-depth` (default 2) levels down (`workers/w0..w4`, `res/p0..p3`), shown as `newest of N sub-sources (<dir>/<file>)`. The
liveness judgement and the throughput figure are built from one scan of those sources (`scan_sources`) and the full read and the
per-tick refresh share one function (`live_timestamp`), so they cannot read different timestamps. A launcher log in an otherwise
silent root no longer stands in for a run whose workers beat every few seconds (2026-10-30: `k0_fp32` was `stalled` on the mtime of
`join.log` while five workers were healthy). Limit: one live worker hides a dead one; per-worker staleness is not judged. Heartbeats are compared with the clock of the host running the watchdog, so run it where clocks agree
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

**The estimate assumes every row costs the same.** That is false for a run whose rows differ in cost (for example scorers with very
different prompt lengths, or trivial constant scorers beside an expensive model scorer): the fraction is then biased, and so are both
the midpoint and the width of the range, which is derived from the fraction. In such a case the estimate is biased in a direction a
reader cannot see, so a run says so: `{"tier": "slow", "total": 601980, "uniform_cost": false}`. `uniform_cost` is an optional JSON
boolean (default `true`; any non-boolean makes the run `unknown` with the file named). With `false` the digest shows the fraction and
the rate and `no ETA`, nothing else is computed (`eta_quality` is `suppressed`, `left_s` and the `eta_*` fields are null), and
`TOTAL UNREACHABLE` cannot fire; `TOTAL EXCEEDED` still can, since it counts rows. The watchdog does not infer non-uniformity or model
per-row cost: only the run knows its workload. The legend line under the table states the uniform-cost assumption.

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

**In the digest**, each status row (columns run, state, esc, age, watch, progress, perf, why) has a `watch` cell: `tier/source last>next` with UTC HH:MM times, for example `slow/file 08:00>09:00`
(source `file` = WATCH.json, `hbNm` = inferred period, `dflt` = default). `digest.json` has per run `tier` (name, source, recheck_s,
stall_s) and `watch` (last_eval_utc, next_eval_utc, recheck_s).

**Making the declaration happen.** Documentation alone gets forgotten, so the launcher should write the file with the other
per-run files (relaunch command, log). For a shell launcher such as `experiments/run_sharded.sh`, one line next to the line that
writes the relaunch command is the natural place (that file is outside `tools/` and not edited here):

    echo '{"tier": "slow"}' > "$OUT_DIR/WATCH.json"      # R0 baseline rerun, verl training; use "fast" for smoke tests

Default to `slow` in the launchers for the R0 rerun and verl, and let smoke-test launchers write `fast`.

### Throughput (CLAUDE.md section 9)

Every training or evaluation run is expected to report its own per-chip throughput; the digest surfaces it and flags a drop against the
run's own early baseline. Sources, read at every full read of a run, looking in the run directory and its descendants down to
`--perf-depth` levels (default 2, so `run/res/p0/` of a concurrent cell is found; at most 16 directories, checkpoint-like directories
such as `ckpt`, `merged`, `adapter` are never listed):

| source | fields | notes |
|---|---|---|
| `heartbeat.log` (last line carrying them) | `tok_s_chip_w20`, `q_s_chip_w20` or `ex_s_chip_w20`, `chips`, `procs_on_chip`, `reserved_gib`, `step_s` | `key=number` pairs; the `_w20` suffix is the window |
| `perf.json` | trainer shape: `window.{tok_s,q_s}_chip_equiv`, `chips`, `procs_on_chip`, `reserved_gib_peak`, optional frozen `baseline` | the only source of a baseline |
| | eval-harness shape: `tokens_per_s_per_chip`, `examples_per_s_per_chip`; with `chips=0` the `*_total_for_reference` host rates | |
| `progress.log` | trainer step lines `step_s .. tok/s/chip .. q/s/chip .. chips .. reserved_gib ..` | fallback, only when the directory has neither of the above; median of the last 20 step lines |

Per directory the freshest source is the displayed rate. Aggregate over the live processes of a run (those within the larger of the
stall threshold and 600 s of the newest): rate = mean of the per-chip-equivalent rates (the writer already multiplies by
`procs_on_chip`, assuming equal shares), chips = sum of `chips / procs_on_chip` (so k processes sharing a chip count once), reserved =
the largest per-process figure. **Where a heartbeat line names its chip (`chip=N`, as the k0 workers do), chips = the number of distinct
chip ids among the live sources** (`perf.chip_ids`), one record per chip, and sources that name no chip (shared per-unit streams such
as `base/` and `instruct/`, which repeat the workers' lines) are left out of the count and the mean; `perf.note` says how many.

**Scope is never relabelled.** `*_chip_*` keys are per chip. `*_host_nochip_*` keys, or `chips=0` in `perf.json`, are a **host** rate of a
run with no chip (a CPU run); the row says `host ... (chips=0)` and never `/chip`. A per-chip key beside `chips=0` is kept per chip and
noted as contradictory.

**Row.** `perf` column, `running` and `stalled` rows only (`digest.json` has `perf` for every run, finished or not, to keep the md
small): `27464 tok/s/chip 4.21 q/s/chip x1/2p 20.5GiB r=0.53`: `xN` chips, `/Kp` = K processes share a chip, GiB reserved per process,
`r=` ratio to the declared baseline, `base?` = **no baseline declared** (nothing is invented). `digest.json` `perf`: `scope`
(`chip`|`host`|`mixed`), `tok_s`, `ex_s`, `ex_unit` (`q`|`ex`), `window`, `chips`, `n_procs`, `procs_on_chip`, `reserved_gib`, `utc`, `age_s`,
`sources`, `baseline` (`declared`|`undeclared`), `ratio`, `ratio_dir`, `ratio_stale`, `threshold`, `regressed`, `procs[]`.

**Regression flag.** Only `perf.json` can declare a baseline: the trainer freezes `baseline` (its aggregate over steps 20-120, in
per-process units; note it is a token-weighted aggregate, not a median of steps) after step 120 and keeps it across resumes. The ratio is
computed here as `window.{tok_s,q_s}_proc / baseline.{tok_s,q_s}_proc` (the writer's own `ratio_to_baseline` is not trusted or copied). A
**running** run whose ratio, for the worst process, is below `--perf-regress-ratio` (default 0.7, the trainer's own noise note: a 20-step
window has about +-15% sampling noise) is flagged: escalation `decide` (like a stall), `why` = `THROUGHPUT REGRESSION 0.53x of the declared
baseline (tokens/s, flag below 0.70x)`, first pointer = that process's `perf.json` (`$.window`, `$.baseline`, `$.ratio_to_baseline`).
`--perf-ratio-key tok_s|q_s` chooses which ratio decides (default tokens/s, which does not move with the question-length mix; both are
shown in `perf.json`, only the chosen one is computed in the digest). Not flagged: a run without a baseline (the row says `base?`), a
finished run, a `perf.json` older than the stall threshold (`r=0.53(stale)`). The row's rate and ratio follow every tick; the
escalation is set at the run's full reads, like the flat-progress flag. A low AICore is **not** a regression: the reference
gated-delta-rule kernel is launch-bound, so a healthy job can sit at 9-22% AICore; judge by the ratio to the run's own baseline.
Until a run lasts past step 120 no baseline exists, so nothing in the live tree has been flagged yet (all current `perf.json` have
`baseline: null`); the flag is covered by the tests and by a replay of a real `perf.json` with a doctored baseline.

### Host utilisation (NPU)

`digest.json` has an `npu` block and `digest.md` a compact form of it, from **one ssh call per pass** to `--npu-host` (default `npu`;
`local` runs the same shell command here). `--no-npu` (or the environment variable `WATCHDOG_NO_NPU=1`, which the tests set) disables
it. It is optional and non-fatal: ssh missing, host down, a timeout (`--npu-timeout`, default 45 s), `npu-smi` absent or output that
does not parse all become `npu.available: false` with a `reason`, the summary line says `npu n/a`, and the rest of the digest, the exit
code and the other blocks are unaffected. Read-only: it runs `npu-smi info` (`--npu-samples` snapshots, default 4, `--npu-sample-gap` 3 s
apart), `npu-smi info -l`, `npu-smi info -t proc-mem -i N` per NPU, and `ps -eo pid=,args=`. The `ps` output stays in memory and is used
only to match process ids to run directories; command lines are never stored or printed (credentials in arguments cannot leak).
Nothing is launched on an NPU.

**Parsing.** `npu-smi info` prints each chip on **two lines**: line 1 `| <npu> <name> | <health> | <power W> <temp C> <hugepages> |`,
line 2 `| <chip> | <bus id> | <AICore %> <mem used>/<mem total> <HBM used>/<HBM total> |` (HBM-Usage(MB) is the last pair), then a process
table. `proc-mem` prints `Process id:1479047 Process name:python3 Process memory(MB):3936` with **no space after the colons**, or
`No process in device.`.

**Two things per chip, kept apart and never merged into one word.** *Ownership* (who may use the chip) comes only from
`CHIP-ALLOCATION.json`, read-only (`--chip-allocation`, default `<first root>/CHIP-ALLOCATION.json`): `allocation[]` gives the owner,
run and release condition, `free[]` the chips that are free, `pending_claims[]` who is waiting (shown as `pending: ...`). *Activity*
comes only from the samples. A sample never says that a chip is free: a chip between shards reads 0% with baseline HBM and is still
owned (the file's own rule, after two incidents where a momentary reading was used as an ownership claim).

- `ownership`: `owned` | `free` | `unlisted` (the file lists the chip neither as allocated nor as free) | `conflict` (listed twice, or both
  allocated and free) | `unknown` (the file is missing or does not parse). `unlisted`, `conflict` and `unknown` are shown as **ownership
  unknown** and flagged `read` (`ownership_unknown`), loudly, with the path and the reason; nothing is inferred and no chip is then
  reported free. Staleness of the file is not judged (its `updated_utc` is printed).
- *resident*: a resident process (in `proc-mem` or in the `npu-smi info` process table; 31 MB is enough), or HBM above
  `--npu-idle-hbm-mb` (default 4096; the driver baseline is about 3450 MB). Not an ownership claim.
- *activity*: AICore, the latest snapshot and the mean of the pass, plus a rolling history of earlier passes (`npu_history.json`, last
  6 h, survives a restart and serves one-shot passes against the same `--out-dir`, or against another directory's history with
  `--npu-history-from DIR`, read only).

| activity | meaning | flag |
|---|---|---|
| `no-process` | no resident process, baseline HBM | combined with ownership: **owned** -> `owned_idle` (`read`): "chip 7 idle, owner X (run), for >=Nm (N passes)", wasted capacity, never "available"; once idle for at least `--npu-owned-idle-seconds` (default 1800 = 30 min: several times the longest legitimate between-shards or checkpoint-loading gap seen, equal to the medium stall threshold) **and** at least `--npu-owned-idle-passes` (3) consecutive passes it becomes `owned_idle_long` (**`decide`**: a forgotten release or a dead job; the line carries the elapsed idle time and pass count). A busy pass, or a gap in watching longer than three ticks, restarts the count. **free** per the file -> `free_unused`: `decide` while any run is `running` or queued, `read` otherwise. Anything else -> the ownership flag |
| `quiet` | a process, every snapshot at or below `--npu-near-zero-pct` (5) | none (a single low sample, or a load, is normal) |
| `wedged?` | a process and quiet for at least `--npu-wedged-passes` (3) consecutive passes spanning at least `--npu-wedged-seconds` (1200) | **escalation `read`**, with the duration (`for >=30m (4 passes)`); a gap longer than three ticks, or one busy pass, resets the streak |
| `low` | a process, **window** mean AICore below `--npu-low-pct` (30) but not quiet | informational line, no escalation (launch-bound kernels run healthy at 9-22%) |
| `busy` | a process, window mean at or above 30 | none |
| `unknown` | a process, fewer than `--npu-min-passes` (3) passes in the window | none; never `low` on thin evidence. The table row still shows this pass (`this pass mean 70%`) |

Also flagged (`read`): `free_in_use`, a chip the file lists free that has a resident process (use not recorded).

**A one-shot pass and the window.** A pass has four snapshots over about 9 s, which is not enough to call a chip low, so a one-shot
pass with no history reports every chip's activity `unknown` (the summary fragment says `util unknown on all chips`, and the table gives
this pass's mean). The default invocation (`--out-dir` = the daemon's `_watchdog/`) has the daemon's history and gets full windows. For
a scratch `--out-dir`, add `--npu-history-from /mnt/cephfs/xingchao/experiments/jev/_watchdog`: the history is read from there (never
written) and the pass is saved to the scratch directory.

**Utilisation window.** The low/busy verdict is the mean of the pass means over the trailing claimed stretch inside
`--npu-window-seconds` (default 3600 s: about six 10-minute passes of four snapshots, long enough to average out the 14-94% swings a
bursty eval shows within seconds, short enough that an idle stretch hours ago cannot colour it). Unclaimed passes end the stretch and
the first claimed pass after one is dropped as warm-up. Before 2026-10-30 the verdict was the mean of the current pass alone (four
snapshots, about 9 s) and nothing stated it. The digest now states the window and the passes it had: `aicore_window_pct`,
`window_passes`, `window_s` per chip, `window_s`/`min_passes` on the block, `win 78%/60m n=7` in the table, and
`low chips 5 (mean AICore over 60m window)` in the summary fragment (numbers after `chips` are chip ids, not counts).

A container that has started but has not yet opened the device is invisible to `npu-smi`, so a first sighting of a chip with no process can
be a startup; the flag text says "first seen this pass" or "for >=Xm (N passes)" so a reader can discount it. In a one-shot pass without
history, `wedged?` cannot be reached.

**Queued.** The watchdog has no queue of its own. A directory below a root that holds a file named in `--queued-names` (default
`QUEUED`) and has neither a terminal marker nor a heartbeat file counts as queued (`queued` in `digest.json`, counted in the flag text).
No launcher writes `QUEUED` today, so until one does only `running` runs count as work. The flag compares against runs in state
`running`, whether or not they use the NPUs (a CPU run beside idle chips is exactly the situation to see).

**Claims.** Each resident process id is looked up in the `ps` listing; every absolute path in its command line is walked up through its
parents and the first directory that is a discovered run claims the process (`claimed_by`, with the claimant's state in `claimed_state`;
a claimant that is not `running` is shown as `run(done)`). A process whose command line names no run directory is counted in
`processes_without_run`. The mapping is by command line, so it names a run only if the run's directory is in its arguments.

`npu` in `digest.json`: `available`, `reason`, `host`, `sampled_utc`, `samples`, `allocation` (`ok`, `path`, `reason`, `updated_utc`, `allocated`, `free`, `pending`), `chips[]` (`npu`, `ownership`, `owner`, `owner_run`, `pending_claims`, `activity`, `resident`, `aicore_last`,
`aicore_pct` mean, `aicore_samples`, `aicore_recent_passes`, `hbm_used_mb`, `hbm_total_mb`, `power_w`, `temp_c`, `claimed_by`,
`claimed_state`, `processes[]`, `quiet_s`, `no_process_s`), the chip-id lists `no_process`, `owned_idle`, `free_unused`, `ownership_unknown`, `wedged`, `quiet`, `low`, `unknown`, `running_runs`,
`queued_runs`, `flags[]` (`kind`, `escalation`, `chips`, `text`) and `escalation`. `queued` (run ids) sits at the top level. The probe adds
about 10 s to a pass. The NPU flags do not change the exit code (exit codes follow run states).

**In `digest.md`.** A fragment on the summary line, always present (`| npu owned but idle chips 7; low chips 0,3 (mean AICore over 60m window) of 8, AICore window 60m`,
`| npu OWNERSHIP UNKNOWN chips 0,1,2 (CHIP-ALLOCATION.json unreadable) of 3, AICore window 60m`,
`| npu 8/8 resident, owners per file, AICore window 60m`, `| npu n/a`), and one `## Host utilisation` block at **priority 3**, after the primary-scorer flags: the escalation
lines and the per-chip table (owner from the allocation file, AICore latest [earlier passes] and window, HBM GiB, activity, process claimed by), about 1 KB. It ranks above the ERROR
signatures of ordinary runs and above every warning, and below the status rows, the failed/stalled runs' pointers and their own errors.
Whether it fits depends on how much sits above it: on the live tree at the default 16000 bytes it does not (the failures and
stalls ahead of it need about 22500 bytes before it shows; with every stalled run dispositioned about 20750; with every stalled and
failed run dispositioned about 12250). `digest.json` always has the full block.

### Retention of flagged passes

`digest.json` is rewritten every pass, so evidence that lives only there has a ten-minute lifetime. A pass that carries **any flag** is
copied, with its rendered `digest.md`, to `<out-dir>/_retained/digest-<utc>.json` and `.md` (`--no-retain` disables it).

**Retention is half of a pair, and neither half is sufficient alone.** Under CLAUDE.md 7.1 the digest carries pointers and signatures,
never the evidence. A retained digest preserves what the digest carries: run states, marker names, exit codes and timestamps,
suspicious-metric paths and values, and the clustered error-signature exemplars with their pointers. It does **not** preserve the
log or report files those pointers name. The other half is a pre-registration clause: a relaunch must never delete a directory that holds
a terminal marker; it moves it to `<name>.crash-<utc>/`. Retain digests but let the logs be deleted, and the pointers in your retained
copy point at nothing, while it still looks like preserved evidence. The retained file says so itself (`retention.NOT_PRESERVED` and a
comment on its first lines in the `.md`). The watchdog cannot enforce the relaunch clause; it lives in the pre-registration and in the
launchers.

**What counts as a flag** (`pass_flags`, any of them, explained or not: tier 0 does not judge what is explained, and a dispositioned
flag is still a flag):

- a run in state `failed`, `stalled` or `unknown`;
- a suspicious metric that is not suppressed as expected-degenerate: **including suspicious successes** (a rate of exactly 0.0 or 1.0,
  identical across cells, a cell below the minimum sample count, non-finite), which need no failure anywhere in the tree;
- an error-severity signature in a run's log (one flag per run and signature); warning-only signatures are not flags;
- `PROGRESS FLAT`, `TOTAL EXCEEDED/UNREACHABLE`, a throughput regression;
- any escalation `read` or `decide`, including the level a WHY disposition removed (`expected: true` runs are still flagged);
- an escalating NPU flag (`ownership_unknown`, `owned_idle`, `owned_idle_long`, `free_unused`, `free_in_use`, `possibly_wedged`); the informational low line is not.

**When a pass is retained** (non-empty flag set only): (a) **a flag key appears that was not in the previous pass**, unless that same key
was retained within `--retain-flap-seconds` (default 1 h), so a flag that toggles does not retain every tick; (b) **refresh**: the newest
retained copy is older than `--retain-refresh-hours` (default 6) and flags are still present, so the pointers and exemplars of a
long-lived flag are re-captured. A flag that merely clears does not trigger. Keys are per run (and per signature, metric path or chip
list), so a second failed run, a different error in the same run, or a new suspicious path is new. Case that deduplication loses: a flag
that persists while its evidence changes under the same key (for example a rewritten log with the same signature) is captured only at
the refresh, up to 6 h later. State lives in `_retained/index.json`, so a restart neither forgets what it saw nor retains it again.

**Bounds.** At most `--retain-max` copies (default 60, a `.json`/`.md` pair is one copy) and `--retain-max-mb` MB in total (default
200); the oldest pair is deleted first and the newest is always kept. Both caps, because `digest.json` is large (about 1 MB on the live
tree and growing with the run count) and a count alone would let a growing tree fill the disk, while a size alone would let small
digests accumulate for months. Because "any flag" is true on most passes while the tree has long-lived failures, dedup does the real
work and the caps are a backstop: at the default 60 copies a flap-heavy day keeps about the last 10 hours at six per hour.

**Self-describing.** Each retained `.json` begins with a `retention` object: `retained_utc`, `trigger` (`new_flags` or `refresh`), `why`,
`new_flags` (up to 100 keys), `new_flags_total`, `cleared_since_previous_pass`, `flags_total`, `flag_kinds` (counts per kind),
`previous_retained`, `NOT_PRESERVED`; the rest is the digest of that pass unchanged. The live `digest.json` carries `retention_status`
(`enabled`, `flags`, `retained` file name or null, `trigger`, `kept` copies, `bytes`, `dir`). Retention is non-fatal: an error becomes
`retention_status.error` and the digest is written as usual.

### Obligations (absent artefacts)

A failure and a stall are things that happened. Some of what a round owes is a thing that **has not** happened: a product nobody has
written, which no rule over logs and heartbeats can flag. `obligations.json` declares such products; the digest keeps listing them until
they exist. The watchdog reads the file and knows nothing about any round: the human who writes an entry owns its trigger predicate, and a
wrong predicate makes a real obligation invisible, which is why an entry it cannot evaluate is shown as `INVALID` and not skipped.

**Where.** `<root>/obligations.json` for every `--root` that has one, or the files named by `--obligations FILE` (repeatable; this
replaces the default). Relative paths inside a file resolve against **that file's directory**; absolute paths are allowed. Paths are globs
(`**` allowed); at most 200 matches are looked at.

**Schema (version 1).**

    {"schema": 1,
     "obligations": [
       {"id": "r0-erratum",                       # required, [A-Za-z0-9_.-]{1,64}, unique across all files
        "title": "R0 erratum",                    # optional, one line
        "clause": "experiments/R3-SFT-PREREG.md amendment 11 item 3",   # optional pointer to the clause
        "owner": "orchestrator",                  # optional
        "artifact": {"path": "r0_baseline/ERRATUM.md"},                 # required: what discharges it
        "trigger": {"path": "r3_runs/TEST-READS.log", "predicate": "min_lines", "n": 1},   # optional: what makes it due
        "escalation_when_due": "decide"           # optional, "decide" (default) or "read"
       }]}

A **predicate** is one of: `{"path": GLOB, "predicate": P, ...}` with P = `nonempty` (default: a file with at least one byte, or a
directory with at least one entry), `exists` (also an empty file), `min_lines` (with `"n": N >= 1`; some matching file has at least N
lines, so `n: 1` means "a first line was written"), `matches` (with `"pattern": REGEX`; some line of some matching file matches); or
`{"after_utc": "2026-11-01T00:00:00Z"}`; or `{"any": [predicate, ...]}` / `{"all": [predicate, ...]}` (nested at most 3 deep). A glob
predicate holds if **any** matching file satisfies it. The artefact default is `nonempty`, not `exists`: a zero-byte file does not
discharge an obligation unless the entry says `exists`.

**Status** (per obligation, recomputed every pass):

| status | when | escalation |
|---|---|---|
| `discharged` | the artifact predicate holds (whatever the trigger says) | none; listed in full for **one pass**, then only counted |
| `due` | artifact absent and the trigger predicate holds | `escalation_when_due` (default `decide`) |
| `pending` | artifact absent and the trigger does not hold yet, or **no trigger is declared** (such an entry never becomes due, and says so) | none, informational |
| `invalid` | the entry cannot be evaluated: no `id`, duplicate id, no `artifact`, unknown predicate, `min_lines` without a positive `n`, a regex that does not compile, a malformed `after_utc`, an empty `any`/`all`, a bad `escalation_when_due` | `read` |

An unreadable `obligations.json` (not JSON, wrong `schema`, `obligations` not a list) is a **file error**: it is shown in the summary block
as `FILE UNREADABLE` with `[read]`, nothing in that file is tracked, and the rest of the digest is unaffected. Other files and other
entries still work. If no obligations file exists at all, the summary says `Obligations: NONE DECLARED ... not the same as nothing owed`.

**In the digest.** Always one line in the summary block (`Obligations: 1 DUE, 1 pending, 0 discharged of 2 declared`). Due and invalid
obligations and unreadable files are one block at **priority 0**, kept with the summary and the failed/stalled rows, and listed before
the status rows: a dropped obligation block reads as "nothing owed", so it is the last thing to go. Pending and newly discharged ones are
priority 3, level with the host-utilisation block and above ERROR/WARNING signatures. A due line reads
`- [decide] DUE r0-erratum: R0 erratum | artefact ABSENT: r0_baseline/ERRATUM.md | triggered since 2026-10-30T10:00Z by <path> (min_lines) | clause: ...`.
`digest.json` has `obligations` (`files`, `counts`, `escalation`, `items[]` with `status`, `escalation`, `artifact`, `trigger`,
`artifact_evidence`, `trigger_evidence`, `since_utc`, `reason`, `newly_discharged`). At most 12 lines per block in `digest.md`, the rest
counted. Due and invalid obligations and unreadable files are flags for retention. They do not change the exit code, which follows run
states only.

**State.** `<out-dir>/obligations_state.json` records when each obligation first became due or discharged and that a discharge has been
listed, written after each full pass by `run_once`. It is what makes "listed for one pass" work, so a one-shot run against the live
out-dir counts as a pass and consumes the listing; develop with a separate `--out-dir`. An artefact that disappears reopens the
obligation (due or pending) and a later discharge is listed again. `since` is the first pass that saw the trigger, not the moment it
happened.

**What this block is not.** It does not know whether an artefact is correct, complete, current or the right one: only whether a file or
directory satisfying the declared predicate exists. A `discharged` obligation means a file is present and nothing more; the digest says
"presence only, correctness not checked" on every such line. It also does not know about the trigger's meaning: it evaluates the
predicate the author wrote, so a predicate that is true too early shows a spurious `due`, and one that never becomes true hides the
obligation as `pending`. And it cannot see an obligation nobody declared.

### Explanations

If a run directory holds `WHY_STOPPED.json` or `WHY_FAILED.json` (`--why-names`), its `note` (else `why`, `reason`, `summary`, or
the first string value, else the raw text) is shown as one line, clipped, under that run, so an expected failure is not re-diagnosed.
A note alone changes nothing.

### Expected failures (the only downgrade)

An explicit boolean `"expected": true` in the WHY file (strictly JSON `true`; not a string, not `1`, not a keyword in the note)
sets the escalation to `none` when, and only when, the run has a terminal marker that parsed (state `done` or `failed`), is
`archived`, or is `stalled` (no marker and an old heartbeat: the file is someone's written statement that the stop is deliberate, for
example a run superseded by later work). A `running` or `unknown` run keeps its escalation whatever the file says, and a stalled run
whose heartbeat resumes is `running` again and loses the downgrade. The watchdog never guesses which stalls are expected. The
downgrade is audited, never silent: the status row shows `expected=yes` (the reason reads "expected=yes (was decide: ...)"); the
second line of `digest.md` says `Dispositioned by a WHY file with expected=true ...: stalled 11, failed 2`; `digest.json` has
`expected_downgrades` (count and run ids) and `expected_by_state`; the run keeps its `state`, the summary-line counts and its
exit-code contribution (30 for a stalled run); flags and error lines are still reported. An explained row ranks as an ordinary
status row but at priority 5, so it never takes digest space from an unexplained run (the audit lines in the summary block carry the
counts and files whether or not the rows fit), and its errors do not count as a failed run's. Deciding that a failure is acceptable
is a judgement, so it needs this explicit key.

**Directory dispositions (`applies_to_subtree`).** Quarantine is a property of a directory, not of one run. A run with no WHY file of its
own inherits a disposition from an ancestor directory:

- the walk goes up from the run's parent to, but **not including**, the root; the nearest ancestor whose WHY file has
  `"applies_to_subtree": true` decides. With `"expected": true` the run is dispositioned exactly as if it had its own file (same state
  rules: done, failed, archived or stalled only; a running or unknown run is never downgraded; a resumed heartbeat cancels it).
  With anything else (`"expected": false`, absent) the search stops and nothing is inherited: a nearer explicit refusal is not
  overridden by a farther file.
- both keys must be the JSON boolean `true` (strings and `1` do not count). A WHY file without `applies_to_subtree: true` never reaches
  below its own directory, and one placed at a root applies to nothing, so a single run's file cannot silently disposition its
  neighbours or a whole tree.
- a run's own WHY file always wins, whatever it says (an own `"expected": false` beside a quarantine file keeps the run escalating).
- the note shown for the directory is its `subtree_note`, else `note`.

Audit, so that the digest reads "N runs dispositioned by M files at these paths" and never "N runs are fine": the status row's reason
reads `expected=yes inherited from <dir id>/WHY_FAILED.json (was decide: ...)`; the summary block of `digest.md` says
`... | 7 own, 27 inherited by 1 subtree file` followed by one line per directory (`inherited: <id>/WHY_FAILED.json
(applies_to_subtree) covers 27 runs (done 26, failed 1): <note>`, at most four, then a count of the rest); `digest.json` has per run
`expected_from` (`kind` `own` or `inherited`, `id`, `dir`, `file`) and in `expected_downgrades.inherited_sources` one entry per
directory file (`id`, `dir`, `file`, `note`, `runs`, `by_state`, `run_ids`). The runs stay in the state counts and the exit code.
`expected_downgrades.runs` lists, as before, the runs whose escalation actually fell.

### Error signatures

**Deliberate-shutdown records are not errors.** Two phrases are removed from a line before the error-word test (`BENIGN_SPANS` in
`watchdog.py`): `killed (disarmed|deliberate|intentional)` (a process the run's own launcher stopped on purpose) and
`waiting for <path>/DONE (or FAILED)` (FAILED is a marker file name there). Only the matched span is silenced: any other error word on
the same line still counts, and a bare `killed`, `Killed` or `FAILED` is still an error. There is no per-run declaration mechanism,
on purpose: a run could then silence a real error; a new benign phrase is added to the list in the code, with a test.

Lines matching error words (error, exception, traceback, fatal, failed, OOM, killed, ...) or warning words are normalized
(ANSI codes, timestamps, hex addresses, UUIDs, PIDs, absolute paths, line numbers, bare integers and `shardN`-style indices
become placeholders) and grouped. Per signature the digest has the count, first and last occurrence (timestamp when the
log has one, otherwise line numbers), one exemplar line cut to `--exemplar-width` (default 160), and a pointer: log path,
line range (`--ctx-before` 10, `--ctx-after` 3) and byte offset. At most `--max-signatures` (default 8) per run, errors
before warnings, then by count; the number omitted is stated. Only the exemplar line is shown, never a traceback.

**Clustered across runs.** In `digest.md` and `digest.json` `signature_clusters`, an identical normalised signature in several runs is
one entry: total count, number of runs, first..last, one exemplar, and a pointer (log, line range, count) per run. `digest.md` lists
three pointers and says how many more runs there are; `digest.json` lists up to 50 runs per cluster (`runs_omitted` counts the rest)
and 100 clusters, errors first, then by number of runs. Each run's own `errors.signatures` is unchanged. Priority: ERROR clusters
involving a failed or stalled run that has no `expected` disposition are 2, other ERROR clusters 4, WARNING clusters 5. Credentials
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
- `decide` also: a `running` run with a throughput regression (see Throughput; `PERF_ESCALATION` in `watchdog.py`, one line to change to `read`).
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
It reads logs, heartbeats and `perf.json`, writes `digest.json`, `digest.md` and `npu_history.json`, and (unless `--no-npu`) runs read-only
`npu-smi` and `ps` once per pass over ssh. It never touches containers or starts anything on an NPU.

To switch a running daemon over to a new version: stop it (`pkill -f 'tools/watchdog.py --watch'`; it exits on SIGTERM), then start it
with the same arguments as below. Its current arguments are visible with `pgrep -af watchdog.py`.

`-P` needs Python 3.11+ (this host); `npu` has 3.10, where plain `python3 tools/watchdog.py` is equivalent because only the script's
own directory lands on `sys.path`.

### Tests

    python3 -P tools/test_watchdog.py          # 174 tests; the module sets WATCHDOG_NO_NPU=1 so no test ever opens an ssh session

The NPU tests use a fake `npu-smi`, `ps` and `ssh` on `PATH` (`--npu-host local` for the end-to-end probe).

## Final interface summary

**States** (one per run): `done` (marker, exit 0), `failed` (marker, non-zero), `running` (no marker, heartbeat within
the run's tier stall threshold: fast 10 min, medium 30 min, slow 2 h, or 5x its inferred period), `stalled` (no marker, older heartbeat), `archived` (no marker, no heartbeat file, newest log older
than `--archive-seconds`, default 21600), `unknown` (reason given). The marker is the source of truth; container state is never read.

**Escalation**: `none`; `read` (tier-1 model reads the listed pointers); `decide` (orchestrator chooses, after the read). `decide`:
failed, stalled, or done with suspicious metrics. `read`: unknown, suspicious metrics in a running run, or error lines. `none`:
otherwise, archived, and runs downgraded by `"expected": true` (done, failed, archived or stalled; audited in the summary and `expected_by_state`).

**Exit codes**: 0 all done or archived, 10 some running, 20 some unknown or no runs, 30 some stalled, 40 some failed; 2 usage error;
3 a second `--watch` on the same out-dir. Exit codes follow state, not escalation, so an expected failure still exits 40 until it is
moved out of the scanned tree (for example under `_archive/`).

**Suppression** (`--suppress-roles`, default `constant,uniform,mock-*`): exact 0/1 and identical-across-cells values under those scorer
names are counted, not flagged, with an audit line per run. **Protection** (`--protect-roles`, default
`primary,empty_input,question_only`): never suppressed; `low_sample_count` and `non_finite` are never suppressed for anyone; a mock
primary (`primary` whose report name matches a suppress pattern) is suppressed as `primary=<name>`. The rule keys off the scorer name;
`--no-suppress` shows everything.

**Digest size**: `digest.md` is capped at `--max-md-bytes` (default 16000) with priority-ordered dropping and an explicit note of what
was dropped; `digest.json` is complete. Signatures are clustered across runs; the NPU block is priority 3 (after status rows, failure
pointers and the primary flags, before ordinary-run errors and all warnings).

**Throughput and NPUs**: `perf` per run (per chip, chip count, reserved GiB; `host` for chip-less runs; `r=` against the run's declared
`perf.json` baseline, `decide` below 0.7 for a running run, `base?` when undeclared); `npu` block (ownership from
CHIP-ALLOCATION.json vs activity from the samples; `free_unused` beside work is `decide`, `owned_idle` / `ownership_unknown` / `wedged?` are
`read`, `low` is informational; optional, `--no-npu`).

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
