"""One command per model: every Track K and Track T number the R3 round-1 prereg requires (R3-SFT-PREREG.md).

    python3 -P eval_r3.py --full --model-path <HF dir> [--adapter <LoRA dir>] --arm K0|K1|... --out <run dir> \\
        [--partitions dev,calibration[,test]] [--limit N] [--limit-groups N] [--track-t-config r3|r0] \\
        [--stages k,t_score,report] [--shard i --num-shards n] [--b4-base <K0 run dir>] [--round-dir <dir with FINAL.json>]

The scorer is injected: `run_full(args, scorer_handle)` takes any callable `score_fn(rows, input_mode) -> raw per-option scores`
(core_r3 docstring), so the fast scorer of the other engineer can be dropped in without touching this module.

Order of work (sec 10.4): constant + uniform + gold-position distribution first; prompt hashes of one record per source;
then the first partition is scored and 20 stored argmaxes are recomputed from their stored s_i; only then are numbers computed.
Test partitions are opened only through testlock_r3 (sec 8.4). Everything is resumable at item granularity (stored readouts).
"""
import json
import os
import sys
import time
import traceback

import core_r3 as C
import degenerate_r3 as D
import prechecks_r3 as PC
import testlock_r3 as TL
import track_t_r3 as T
import variants_r3 as V
import clauses_r3 as CL
import prompt as P
import provenance_r3 as PV
import admissible_store_r3 as AS
import selection_evidence_r3 as SE
import common as RC

DECLARED_DIFFERENCES = [   # sec 3.3, stated in every Track K table header
    "(a) readout is the label log-probability continuation, not Kev's pointer head over </opt> states",
    "(b) prompt has a task definition, '- name: definition' options and 'Answer:', not Kev's special-token format; where Kev gives no description the definition equals the name",
    "(c) training unit is one question, not one record",
    "(d) K1's loss is over the full vocabulary",
    "(e) no new head: the existing LM head is used and kept frozen",
    "(f) record order is shuffled per question, not per record",
]
K_PARTITIONS_DEFAULT = ("dev", "calibration")
PRECHECK_REQUIRED_PARTITIONS = (("decision-v7", "dev"), ("transfer-v4", "dev"))
SCORE_CHUNK = 32
UNIT_TAG = ""            # --unit-tag of this process: names it in heartbeat.log lines and perf.<tag>.json when several chips share a run dir
MODEL_SHA = ""           # sha256 of the model being scored: stamped on every readout row (provenance_r3)
PRODUCED = set()         # readout files this process wrote or resumed: listed in its manifest
DATA_FILES = {}          # path -> sha256 of every data file this process read (sec 7.7: the data file sha256s are written with the run)


def note_data_file(path):
    if path and path not in DATA_FILES and os.path.exists(path):
        DATA_FILES[path] = C.sha256_file(path)


def make_progress(log, label, every_s=30.0, timer=None):
    """Progress callback for score_resumable: a HEARTBEAT line (UTC + done/total) at most every `every_s` seconds, and on completion.
    With a TimedScorer as `timer` the line also carries the windowed per-chip throughput (sec 10.2, CLAUDE.md sec 9), and the same
    fields go to heartbeat.log, the file tools/watchdog.py reads, so the digest shows them."""
    state = {"t": 0.0}

    def cb(done, total):
        now = time.time()
        if done >= total or now - state["t"] >= every_s:
            state["t"] = now
            fields = timer.heartbeat_fields() if timer is not None and hasattr(timer, "heartbeat_fields") else ""
            log(f"HEARTBEAT {label} {done}/{total} {fields}".rstrip())
            if hasattr(log, "heartbeat"):
                log.heartbeat(label, done, total, fields)
    return cb


class Logger:
    def __init__(self, out):
        self.path = os.path.join(out, "progress.log")
        self.heartbeat_path = os.path.join(out, "heartbeat.log")

    def __call__(self, msg):
        line = f"{C.utc_now()} {msg}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def heartbeat(self, label, done, total, fields=""):
        """heartbeat.log line in the convention of tools/watchdog.py (UTC, then done=N total=M and key=number pairs; no 'a/b' fraction,
        which the watchdog would read before done=). The label's '/' is replaced so that 'T1/typed-decisions' is not read as a fraction."""
        if UNIT_TAG:
            label = f"{label} @{UNIT_TAG}"
        with open(self.heartbeat_path, "a", encoding="utf-8") as f:
            f.write(f"{C.utc_now()} {label.replace('/', ':').replace(' ', '_')} done={done} total={total} {fields}".rstrip() + "\n")


def mock_score_fn(kind="mock", tie_rate=0.0):
    """Deterministic stand-in for a model (tests, pipeline dry runs without a model): s_i is a hash of (prompt text, candidate),
    so the score depends on the rendered prompt like a real readout does. tie_rate > 0 makes that share of rows exact ties."""
    import hashlib
    counted = {"forwarded": 0, "padded": 0, "unit": "mock: whitespace-separated words of prompt and candidates"}

    def score(rows, input_mode="full"):
        out = []
        for r in rows:
            if input_mode == "blank":
                r = P.blank_input(r)
            elif input_mode == "drop":
                r = P.drop_input(r)
            p = P.build_prompt(r, "record_name")
            s = []
            counted["forwarded"] += len(p.text.split()) + sum(len(c.split()) for c in p.candidates)
            for cand in p.candidates:
                h = hashlib.sha256((kind + "\x1f" + p.text + "\x1f" + cand).encode("utf-8")).digest()
                s.append(-(int.from_bytes(h[:4], "big") / 2 ** 32) * 8.0)
            if tie_rate and int.from_bytes(hashlib.sha256(("tie" + p.text).encode("utf-8")).digest()[:4], "big") / 2 ** 32 < tie_rate:
                s[-1] = s[0]
            out.append(s)
        return out
    score.describe = lambda: {"scorer": "mock", "kind": kind, "tie_rate": tie_rate}
    score.token_stats = lambda: dict(counted)
    return score


THROUGHPUT_WINDOW = 20      # calls (chunks of SCORE_CHUNK questions) in the windowed rate of the heartbeat, as train_r3.Perf's window


class TimedScorer:
    """Wraps a score_fn and accounts the rows it scored, the tokens it forwarded and the wall time inside it, for the sec 10.2
    throughput line (tokens/s/chip and examples/s/chip, chip count stated, never an aggregate alone). Rows served from stored readouts
    (resume) never reach the wrapper, so the figures are for newly scored rows only.

    Tokens: the score_fn may expose `token_stats() -> {"forwarded": int, "padded": int, "unit": str}`, cumulative counters. `forwarded` is
    every token position the model computed (prompt and candidate tokens, padding positions included, as scorer_r3.R3Scorer counts
    stats['tokens']); `padded` is the part of it that is padding, so real = forwarded - padded. Without token_stats the token figures are
    absent and the line says so (never zero)."""

    def __init__(self, inner, device, window=THROUGHPUT_WINDOW):
        from collections import deque
        self.inner, self.device = inner, device
        self.rows = 0
        self.seconds = 0.0
        self.tok_forwarded = 0
        self.tok_padded = 0
        self.recent = deque(maxlen=window)        # (rows, forwarded tokens, seconds) of the last calls
        self.window = window
        self.token_unit = None
        self.perf_path = None                     # set by run_full: perf.json beside the heartbeat, as train_r3.Perf writes one

    def _tokens(self):
        f = getattr(self.inner, "token_stats", None)
        if f is None:
            return None
        st = f()
        self.token_unit = st.get("unit")
        return st["forwarded"], st["padded"]

    def __call__(self, rows, input_mode="full"):
        before = self._tokens()
        t0 = time.time()
        out = self.inner(rows, input_mode)
        dt = time.time() - t0
        after = self._tokens()
        self.seconds += dt
        self.rows += len(rows)
        d_fwd = None
        if before is not None and after is not None:
            d_fwd = after[0] - before[0]
            self.tok_forwarded += d_fwd
            self.tok_padded += after[1] - before[1]
        self.recent.append((len(rows), d_fwd, dt))
        return out

    def describe(self):
        return getattr(self.inner, "describe", lambda: {})()

    def dedup_stats(self):
        """Scorer-side half of the duplicate-candidate vacuity audit: {"dup_questions": int, "dup_candidates_removed": int} counted by the
        scorer over everything it scored in this process (0 and 0 when the safeguard was never exercised); None if the scorer cannot say."""
        f = getattr(self.inner, "dedup_stats", None)
        return f() if f else None

    def chips(self):
        if self.device.startswith("npu"):
            vis = os.environ.get("ASCEND_RT_VISIBLE_DEVICES", "")
            return len([x for x in vis.split(",") if x]) or 1
        return 0

    def reserved_gib(self):
        """HBM reserved by the caching allocator on the visible chip(s), GiB, as (current, peak); None off-NPU or if torch_npu is unavailable
        (CLAUDE.md sec 9: every throughput figure carries reserved memory). Read only after the scorer has loaded a model."""
        if not self.device.startswith("npu"):
            return None
        try:
            import torch
            import torch_npu  # noqa: F401
            return torch.npu.memory_reserved() / 2 ** 30, torch.npu.max_memory_reserved() / 2 ** 30
        except Exception:    # noqa: BLE001
            return None

    def heartbeat_fields(self):
        """key=number pairs for the heartbeat: windowed rates per chip (chips=0 on CPU: per-chip is undefined, the host rate is then
        printed under the name tok_s_host_nochip so that no figure is mistaken for a per-chip one)."""
        self._write_perf()
        rg = self.reserved_gib()
        mem = f" reserved_gib={rg[0]:.2f} peak_reserved_gib={rg[1]:.2f}" if rg else ""
        rows = sum(r for r, _, _ in self.recent)
        sec = sum(d for _, _, d in self.recent)
        if not rows or sec <= 0:
            return f"chips={self.chips()}{mem}"
        toks = [t for _, t, _ in self.recent]
        have_tok = all(t is not None for t in toks)
        tok = sum(toks) if have_tok else None
        chips = self.chips()
        w = self.window
        if chips:
            out = f"ex_s_chip_w{w}={rows / sec / chips:.2f}"
            if tok is not None:
                out += f" tok_s_chip_w{w}={tok / sec / chips:.0f}"
        else:
            out = f"ex_s_host_nochip_w{w}={rows / sec:.2f}"
            if tok is not None:
                out += f" tok_s_host_nochip_w{w}={tok / sec:.0f}"
        return f"{out} chips={chips}{mem}"

    def _write_perf(self):
        """perf.json: cumulative throughput of this process (the same dict as the report header's) for whoever reads the run directory."""
        if self.perf_path:
            with open(self.perf_path, "w", encoding="utf-8") as f:
                json.dump({"utc": C.utc_now(), "window_calls": self.window, **self.throughput()}, f, indent=1)

    def throughput(self):
        chips = self.chips()
        counted = self.token_unit is not None
        rg = self.reserved_gib()
        out = {"rows_scored": self.rows, "scoring_seconds": round(self.seconds, 3), "chips": chips, "device": self.device,
               "reserved_gib": rg[0] if rg else None, "peak_reserved_gib": rg[1] if rg else None,
               "note": "sec 10.2: tokens/s/chip and examples/s/chip over newly scored rows; chips=0 means CPU, where per-chip is undefined"}
        out["examples_per_s_per_chip"] = (self.rows / self.seconds / chips) if (chips and self.seconds) else None
        out["examples_per_s_total_for_reference"] = (self.rows / self.seconds) if self.seconds else None
        if counted:
            real = self.tok_forwarded - self.tok_padded
            out.update({"token_unit": self.token_unit, "tokens_forwarded": self.tok_forwarded, "tokens_padding": self.tok_padded,
                        "tokens_real": real,
                        "tokens_per_s_per_chip": (self.tok_forwarded / self.seconds / chips) if (chips and self.seconds) else None,
                        "tokens_real_per_s_per_chip": (real / self.seconds / chips) if (chips and self.seconds) else None,
                        "tokens_per_s_total_for_reference": (self.tok_forwarded / self.seconds) if self.seconds else None})
        else:
            out["tokens_note"] = "the scorer exposes no token_stats; token throughput not available (examples/s/chip only)"
        return out


def limit_partition(clean, variants, n):
    """--limit N for dry runs: the first N clean rows plus the clean parents of the first N variants of each kind; the variants
    kept are those whose parent is kept. n=0 keeps everything."""
    if not n:
        return clean, variants
    want = {C.kev_key(r) for r in clean[:n]}
    for kind in C.KEV_VARIANTS:
        want |= {C.parent_key(v) for v in [v for v in variants if v["variant"] == kind][:n]}
    return [r for r in clean if C.kev_key(r) in want], [v for v in variants if C.parent_key(v) in want]


# ---- Track K ------------------------------------------------------------------------------------------------------------------

def _score_k(score_fn, rows, path, input_mode, log, label, variant=None):
    run_dir = os.path.dirname(os.path.dirname(os.path.dirname(path)))
    desc = score_fn.describe()
    require_record = desc.get("scorer") != "mock"
    store = AS.VerifiedStore(run_dir, path, MODEL_SHA, desc, require_record)
    progress = make_progress(log, label, timer=score_fn)
    def committed_progress(done, total):
        store.commit()
        progress(done, total)
    try:
        PRODUCED.add(path)
        res = C.score_resumable(score_fn, rows, C.kev_key, lambda r, s: PV.stamp(C.readout_row(r, s, variant), MODEL_SHA), store, input_mode, SCORE_CHUNK,
                                progress=committed_progress)
    finally:
        store.close()
    stored = AS.read_verified(run_dir, path, MODEL_SHA, desc, require_record)
    ordered = SE.validate_population(stored, rows, C.kev_key)
    return [r["s"] for r in ordered]


def run_track_k(a, score_fn, identity, out, log, tickets):
    """Returns the report's track_k block and the test-read log entries to append (after everything is computed)."""
    train, train_path = C.load_partition("decision-v7", "train")
    note_data_file(train_path)
    parts, variants, paths = {}, {}, {}
    plan = [("decision-v7", "dev"), ("decision-v7", "calibration"), ("transfer-v4", "dev")]
    plan = [p for p in plan if p[1] in a.partitions]
    if "test" in a.partitions:
        plan += [("decision-v7", "test"), ("transfer-v4", "test")]
    for suite, split in plan:
        t = tickets.get((suite, split))
        clean, paths[(suite, split)] = C.load_partition(suite, split, ticket=t)
        note_data_file(paths[(suite, split)])
        if split != "calibration":
            note_data_file(C.partition_path(suite, split, True))
        var, _ = C.load_partition(suite, split, variants=True, ticket=t) if split != "calibration" else ([], None)
        parts[(suite, split)], variants[(suite, split)] = limit_partition(clean, var, a.limit)
    kev_files = [train_path] + [paths[k] for k in plan] + [C.partition_path(s_, p_, True) for (s_, p_) in plan if p_ != "calibration"]
    for f in kev_files:
        note_data_file(f)
    PC.check_kev_manifest([f for f in kev_files if os.path.exists(f)], out, hashes=DATA_FILES)
    # ---- sec 10.4 (a): constant + uniform + gold positions, before any model number ----
    pre_a = PC.check_a(train, {f"{s}/{p}": parts[(s, p)] for (s, p) in plan}, out)
    log(f"precheck a ok: train gold@0 {pre_a['train']['gold_at_position_0']}/{pre_a['train']['n']}")
    # ---- sec 10.4 (b): prompt hashes, one record per source ----
    for suite, split in plan:
        if split == "dev":
            PC.check_b(parts[(suite, split)], variants[(suite, split)], out, name=f"b_prompt_hashes_{suite}")
    log("precheck b ok")
    if "k" not in set(a.stages.split(",")):
        # stage k_score: score only the (suite/split/kind) readout files named by --k-only into their stores, compute nothing. The final "k,report"
        # pass reads them back (nothing is rescored) and computes every number; this is how one model's Track K is spread over several chips.
        for spec in [x for x in a.k_only.split(",") if x]:
            suite, split, kind = spec.split("/")
            key = (suite, split)
            if key not in parts:
                raise SystemExit(f"--k-only {spec}: partition {suite}/{split} is not in --partitions {a.partitions}")
            rows_, mode_ = {"clean": (parts[key], a.primary_mode), "variants": (variants[key], a.primary_mode),
                            "question_only": (parts[key], "drop"), "empty_input": (parts[key], "blank")}[kind]
            _score_k(score_fn, rows_, C.k_readout_path(out, suite, split, kind), mode_, log, f"{suite}/{split} {kind}")
        return None, []
    fit_const = D.fit_constant(train)
    track = {"declared_differences_from_kev": DECLARED_DIFFERENCES, "tie_rule": "headline: first maximal index of raw fp32 s_i (sec 4.2); R0-convention accuracy and tie count beside",
             "partitions": {}, "prechecks": {"a": "prechecks/a_constant_uniform_gold_position.json"},
             "arm_kind": "untrained (K0)" if a.arm == "K0" else f"trained ({a.arm}): permutation flip rate is a sanity metric (sec 4.8)"}
    scores = {}
    first = True
    # calibration first: the operator column's tau is fitted on it
    order = sorted(plan, key=lambda p: (p[1] != "calibration", plan.index(p)))
    for suite, split in order:
        rows = parts[(suite, split)]
        label = f"{suite}/{split}"
        key = (suite, split)
        s = _score_k(score_fn, rows, C.k_readout_path(out, suite, split, "clean"), a.primary_mode, log, label + " clean")
        scores[key] = {C.kev_key(r): x for r, x in zip(rows, s)}
        if first:
            PC.check_c(C.k_readout_path(out, suite, split, "clean"), run_dir=out)
            log("precheck c ok")
            first = False
        if variants[key]:
            sv = _score_k(score_fn, variants[key], C.k_readout_path(out, suite, split, "variants"), a.primary_mode, log, label + " variants")
            scores[key].update({C.kev_key(r): x for r, x in zip(variants[key], sv)})
        arms = {}
        if split != "calibration":
            cs, tiers = D.score_constant(fit_const, rows)
            arms["constant"] = {**C.headline(rows, cs), "tier_usage": tiers}
            arms["uniform"] = C.headline(rows, D.score_uniform(rows))
            for name, mode in (("question_only", "drop"), ("empty_input", "blank")):
                sq = _score_k(score_fn, rows, C.k_readout_path(out, suite, split, name), mode, log, f"{label} {name}")
                arms[name] = C.headline(rows, sq)
        model_s = [scores[key][C.kev_key(r)] for r in rows]
        track["partitions"][label] = {"n": len(rows), "headline": C.headline(rows, model_s),
                                      # R3 sec 14.9 item 5: the near-tie census rides with every headline of record; the duplicate-option
                                      # audit is the string-level half of the vacuity check of the duplicate-candidate safeguard
                                      "near_tie_census": C.near_tie_census(model_s, gold=[C.gold_index(r) for r in rows], keys=[C.kev_key(r) for r in rows], option_ids=[C.level_ids(r) for r in rows]),
                                      "duplicate_option_audit": C.duplicate_option_audit(rows),
                                      "gold_position_distribution": C.gold_position_distribution(rows), "arms": arms,
                                      "n_variants": {k: sum(1 for v in variants[key] if v["variant"] == k) for k in C.KEV_VARIANTS}}
    # ---- operator column (sec 4.4) and the variant measures ----
    fitted = None
    if ("decision-v7", "calibration") in parts:
        cal = parts[("decision-v7", "calibration")]
        fitted = V.fit_operator(cal, [scores[("decision-v7", "calibration")][C.kev_key(r)] for r in cal])
        track["operator_fit"] = {"partition": "decision-v7/calibration", "n": len(cal), "fitted": fitted.summary(),
                                 "note": "tau fitted per model on decision-v7 calibration (sec 4.4); not the Track T carve-out (sec 2.6, F1)"}
    op = (lambda row, s: V.operator_decision(fitted, row, s)[0]) if fitted else None
    for suite, split in plan:
        if split == "calibration":
            continue
        key = (suite, split)
        rows, var = parts[key], variants[key]
        sec = {}
        pairs = V.build_permutation_pairs(rows, var)
        sec["permutation"] = V.permutation_metrics(pairs, scores[key], op, a.arm_kind)
        sec["nota"] = V.nota_metrics(V.build_nota_units(rows, var), scores[key])
        if fitted:
            sec["operator"] = V.operator_column(rows, [scores[key][C.kev_key(r)] for r in rows], fitted, f"{suite}/{split}")
        track["partitions"][f"{suite}/{split}"]["secondary"] = sec
        track["partitions"][f"{suite}/{split}"]["secondary_note"] = "secondary metrics gate nothing in this round (sec 4.7)"
    reads = []
    for (suite, split), t in tickets.items():
        if (suite, split) in parts:
            h = track["partitions"][f"{suite}/{split}"]["headline"]
            reads.append((t, h["n"], h["kev_rule_accuracy"]))
    return track, reads


# ---- Track T ------------------------------------------------------------------------------------------------------------------

def load_track_t_files(a, log):
    files = {}
    for task, src in [(t, s) for t in ("T1", "T2", "T3") for s in RC.SOURCE_FILES if s in a.track_t_sources.split(",")]:
        path = RC.task_path(a.data_root, task, src)
        if task == "T3" and not os.path.exists(path):
            continue
        note_data_file(path)
        files[(task, src)] = (path, RC.load_records(path))
        log(f"loaded {task}/{src}: {len(files[(task, src)][1])} records")
    return files


def needed_all_list(needed_by_file):
    return [r for recs in needed_by_file.values() for r in recs]


def declare_watch(out):
    """WATCH.json for tools/watchdog.py (CLAUDE.md sec 7.1): a scoring pass heartbeats every 30 s and the work per row is not uniform
    (prompt lengths differ by source, and the staged roles differ), so no completion estimate is derived from the row count."""
    path = os.path.join(out, "WATCH.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tier": "medium", "uniform_cost": False}, f)


def ensure_run_identity(out, identity, a):
    """A run directory belongs to ONE model / prompt / configuration: stored readouts are resumed, so mixing is refused."""
    path = os.path.join(out, "RUN_IDENTITY.json")
    ident = {"model_sha256": identity["sha256"], "model_path": identity["path"], "prompt_version": P.PROMPT_VERSION,
             "track_t_config": a.track_t_config, "arm": a.arm}
    if os.path.exists(path):
        old = json.load(open(path))
        diff = {k: (old.get(k), v) for k, v in ident.items() if old.get(k) != v}
        if diff:
            raise SystemExit(f"{out} was started for a different model/prompt/configuration {diff}; use a new --out")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ident, f, indent=1)


def run_track_t(a, score_fn_lazy, out, log, stages):
    config = T.CONFIGS[a.track_t_config]
    files = load_track_t_files(a, log)
    all_records = [r for _, recs in files.values() for r in recs]
    if not a.limit_groups and set(a.track_t_sources.split(",")) == set(RC.SOURCE_FILES):
        chk = T.check_totals(all_records)
        os.makedirs(os.path.join(out, "prechecks"), exist_ok=True)
        with open(os.path.join(out, "prechecks", "track_t_counts_sec_2_5.json"), "w", encoding="utf-8") as f:
            json.dump(chk, f, indent=1, sort_keys=True)
        if not chk["ok"]:
            raise PC.PrecheckFailure(f"sec 2.5 totals do not match: {chk['mismatches']}")
        log("track T counts match sec 2.5")
    needed_by_file = {}
    for (task, src), (path, recs) in files.items():
        lim = T.limit_groups(recs, a.limit_groups)
        needed_by_file[(task, src)] = T.records_needed(lim, config)
    rdir = os.path.join(out, "trackt", "readouts")
    if "t_score" in stages:
        for role, mode in T.MODEL_ROLES.items():
            mode = a.primary_mode if role == "primary" else mode
            for (task, src), recs in needed_by_file.items():
                mine = [r for r in recs if T.shard_of(r["group_id"], a.num_shards) == a.shard]
                path = os.path.join(rdir, f"{role}__{task}__{src}__shard{a.shard}of{a.num_shards}.jsonl")
                desc = score_fn_lazy.describe()
                store = AS.VerifiedStore(out, path, MODEL_SHA, desc, desc.get("scorer") != "mock")
                progress = make_progress(log, f"trackT {role} {task}/{src}", timer=score_fn_lazy)
                def committed_progress(done, total):
                    store.commit()
                    progress(done, total)
                PRODUCED.add(path)
                try:
                    C.score_resumable(score_fn_lazy, mine, lambda r: r["key"], lambda r, s: PV.stamp(T.make_readout(r, s), MODEL_SHA), store, mode, SCORE_CHUNK,
                                      progress=committed_progress)
                finally:
                    store.close()
    if "report" not in stages:
        return None
    rows_by_role = {role: [] for role in T.ROLES}
    needed_keys = {r["key"] for r in needed_all_list(needed_by_file)}
    suffix = f"__shard{{}}of{a.num_shards}.jsonl"
    for fn in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        role = fn.split("__")[0]
        if role in T.MODEL_ROLES and any(fn.endswith(suffix.format(i)) for i in range(a.num_shards)):   # ignore files of another shard layout
            desc = score_fn_lazy.describe()
            rows_by_role[role].extend(AS.read_verified(out, os.path.join(rdir, fn), MODEL_SHA, desc,
                                                       desc.get("scorer") != "mock"))
    needed_all = needed_all_list(needed_by_file)
    for role in T.MODEL_ROLES:
        ordered = SE.validate_population(rows_by_role[role], needed_all, lambda r: r["key"])
        rows_by_role[role] = [T.make_readout(rec, row["s"]) for rec, row in zip(needed_all, ordered)]
    deg = T.constant_and_uniform_rows(all_records, needed_all)
    rows_by_role["constant"], rows_by_role["uniform"] = deg["constant"], deg["uniform"]
    meta = {"prompt_version": P.PROMPT_VERSION, "render": "record_name", "limit_groups": a.limit_groups, "num_shards": a.num_shards,
            "n_records_needed": len(needed_all), "config": config["name"]}
    block = T.build_track_t(rows_by_role, all_records if not a.limit_groups else [r for rs in needed_by_file.values() for r in rs], config, meta)
    if a.b4_base:
        base_report = C.load_report(a.b4_base)
        if not a.model_path.startswith("mock"):
            SE.verify_run(a.b4_base, base_report)
            base = SE.rebuild_track_t(a.b4_base, a.track_t_config)
        else:
            base = base_report["track_t"]
        half = "report" if config["halves"] else "all"
        block["B-4"] = {"base_run": a.b4_base, "half": half, "lines": T.b4_lines(block, base, half),
                        "note": "ruling 3: 'not admissible' where the trained model fails B-1 on the source"}
    return block


# ---- arguments ----------------------------------------------------------------------------------------------------------------

def add_arguments(ap):
    """The options of the one-command full evaluation (shared with eval_r3.py --full)."""
    ap.add_argument("--arm", default="K0", help="K0 (untrained) | K1 | K1-PT | K1-QO | K2 | K3 | K4 | ladder: K0 permutation numbers are invariance, all others a sanity metric (sec 4.8)")
    ap.add_argument("--partitions", default=",".join(K_PARTITIONS_DEFAULT), help="comma list of dev, calibration, test (test needs FINAL.json, sec 8.4)")
    ap.add_argument("--limit-groups", type=int, default=0, help="Track T dry runs: N groups per category (carve-out / selection / report / train rest) per task file")
    ap.add_argument("--stages", default="k,t_score,report", help="k = Track K; t_score = score Track T readouts (shardable); report = merge Track T and write report.json/report.md. "
                    "Multi-chip: one process per chip with --stages t_score --shard i --num-shards n, then one final --stages k,report (stored readouts are reused, nothing is rescored)")
    ap.add_argument("--k-only", default="", help="with --stages k_score: comma list of suite/split/kind (kind = clean|variants|question_only|empty_input) to score, nothing else")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--track-t-config", default="r3", choices=sorted(T.CONFIGS), help="r3 (carve-out tau, halves) | r0 (sec 6.3: full train-side tau, whole held-out side; for K1-PT against R0)")
    ap.add_argument("--b4-base", default=None, help="run dir of the K0 evaluation of the same base checkpoint under the same configuration: adds B-4 (sec 6.3)")
    ap.add_argument("--round-dir", default=C.ROUND_DIR, help="directory holding FINAL.json and TEST-READS.log (sec 8.4)")
    ap.add_argument("--data-root", default=C.DATA_ROOT)
    ap.add_argument("--track-t-sources", default=",".join(RC.SOURCE_FILES), help="comma list of task files to score for Track T (all three for every reported number; a subset only for dry runs)")
    ap.add_argument("--dtype", default="float32", help="scorer dtype; float32 (HF32 off) for every reported number (sec 14.6 item 2); bfloat16 is for smoke runs only and is flagged as a dry run")
    ap.add_argument("--no-hf32", action="store_true", help="turn the NPU HF32 matmul/conv flags off before the model loads (sec 14.6 item 2; required for a reported number)")
    ap.add_argument("--require-record-grade", action="store_true", help="refuse to start unless the scorer is the scorer of record: rightpad, float32, HF32 off, token_budget 16384, NPU (sec 14.9 item 3)")
    ap.add_argument("--unit-tag", default="", help="names this process in perf.<tag>.json and in its heartbeat lines when several processes (chips) share one run dir")
    return ap


def parse_full_args(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-path", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="npu")
    ap.add_argument("--limit", type=int, default=0, help="Track K dry runs: first N clean rows (+ parents of the first N variants of each kind) per partition; refused with test")
    ap.add_argument("--scorer", default="exact")
    add_arguments(ap)
    return ap.parse_args(argv)


# ---- driver -------------------------------------------------------------------------------------------------------------------

def _g(x):
    return "-" if x is None else f"{x:.4f}"


def render_markdown(report):
    h = report["header"]
    out = ["# R3 round 1 evaluation report", ""]
    if h.get("dry_run_warnings"):
        out += ["**DRY RUN, no number below is a reported number:** " + "; ".join(h["dry_run_warnings"]), ""]
    out += ["## Header", "", "```"]
    for k in ("utc", "arm", "primary_input_mode", "model", "prompt_version", "render", "scorer", "device", "dtype", "checkpoint_revision", "stages", "limit", "limit_groups", "track_t_config"):
        out.append(f"{k}: {h.get(k)}")
    out += ["```", "", "### Clauses in force (a test names them) and not in force (sec 10.5)", ""]
    cs = h["clauses"]
    out += ["In force:", ""] + [f"- {c}  (`{t}`)" for c, t in sorted(cs["in_force"].items())] + ["", "NOT in force:", ""] + [f"- {c}" for c in cs["not_in_force"]] + [""]
    out += ["### Readings of ambiguous clauses (named constants)", "", "```"] + [f"{k}: {v}" for k, v in sorted(h["readings"].items())] + ["```", ""]
    out += ["### Declared differences from Kev (sec 3.3)", ""] + [f"- {d}" for d in h["declared_differences_from_kev"]] + [""]
    out += ["### Pre-number checks (sec 10.4)", ""] + [f"- {k}: {v}" for k, v in h["prechecks"].items()] + [""]
    th = h.get("throughput")
    if th:
        def fx(x, f):
            return "n/a (CPU, no chip)" if x is None else f.format(x)
        out += ["### Throughput (sec 10.2: per chip, chip count stated)", "",
                f"- chips: {th['chips']} ({th['device']}); rows newly scored: {th['rows_scored']}; scoring seconds: {th['scoring_seconds']}",
                f"- examples/s/chip: {fx(th['examples_per_s_per_chip'], '{:.2f}')}",
                (f"- tokens/s/chip: {fx(th['tokens_per_s_per_chip'], '{:.0f}')} forwarded (padding positions included), "
                 f"{fx(th['tokens_real_per_s_per_chip'], '{:.0f}')} real; tokens forwarded {th['tokens_forwarded']}, padding {th['tokens_padding']} ({th['token_unit']})")
                if "tokens_forwarded" in th else f"- tokens/s/chip: not available ({th.get('tokens_note')})", ""]
    tk = report.get("track_k")
    if tk:
        out += ["## Track K", "", f"Arm: {tk['arm_kind']}. Tie rule: {tk['tie_rule']}.", ""]
        rows = []
        for name, p in tk["partitions"].items():
            hl = p["headline"]
            rows.append([name, hl["n"], f"{hl['kev_rule_accuracy']:.4f}", f"{hl['r0_rule_accuracy']:.4f}", hl["tie_count"]]
                        + [f"{p['arms'][x]['kev_rule_accuracy']:.4f} (ties {p['arms'][x]['tie_count']})" if x in p["arms"] else "-"
                           for x in ("constant", "uniform", "question_only", "empty_input")])
        out += ["### Headline accuracy and degenerate arms (n, Kev-rule accuracy, R0-rule accuracy, ties)", "",
                T._table(["partition", "n", "accuracy (Kev rule)", "accuracy (R0 rule)", "ties", "constant", "uniform", "question-only", "empty-state"], rows), ""]
        rows = []
        for name, p in tk["partitions"].items():
            c, d = p.get("near_tie_census"), p.get("duplicate_option_audit")
            if not c:
                continue
            ex = c.get("headline_exposure") or {}
            iv = ex.get("kev_accuracy_interval")
            rows.append([name, c["n"], c["exact_tie_count"], c["n_gap_le_tau"], c["n_gap_le_10tau"], c["n_gap_le_100tau"],
                         "-" if c["min_gap"] is None else f"{c['min_gap']:.3g}",
                         f"{iv[0]:.4f} to {iv[1]:.4f}" if iv else "-", f"{d['questions_with_duplicate_option_string']} of {d['n']}" if d else "-"])
        out += [f"### Near-tie census (sec 14.9 item 5; tau = {C.TAU_S:g} nats; the headline's resolution, not a confidence interval)", "",
                T._table(["partition", "n", "exact ties", "gap <= tau", "gap <= 10 tau", "gap <= 100 tau", "min gap", "Kev accuracy if every listed item went the other way", "questions with a duplicate option string"], rows), ""]
        rows = [[name, str(p["gold_position_distribution"])] for name, p in tk["partitions"].items()]
        out += ["### Gold-position distribution", "", T._table(["partition", "position: count"], rows), ""]
        for name, p in tk["partitions"].items():
            sec = p.get("secondary")
            if not sec:
                continue
            pm, nm, om = sec["permutation"], sec["nota"], sec.get("operator")
            pa = pm["discrimination_counterpart"]["permuted_rows_accuracy"]
            out += [f"### Secondary measures, {name} (gate nothing, sec 4.7)", "",
                    f"- Permutation flip rate (sec 4.5): {pm['label']}",
                    f"  - pairs {pm['n_pairs_total']}, excluded same-order {pm['n_excluded_same_order']}, dropped tied {pm['n_dropped_tied_pairs']}, "
                    f"n (flip denominator) {pm['n']}, flip rate {_g(pm['flip_rate'])}, C-branch rate {_g(pm['c_branch']['rate'])} (n rows {pm['c_branch']['n']})",
                    f"  - discrimination counterpart: permuted-row accuracy {_g(pa['kev_rule_accuracy']) if pa else '-'} (n {pa['n'] if pa else 0}, ties {pa['tie_count'] if pa else 0}), "
                    f"both-sides-correct share {_g(pm['discrimination_counterpart']['both_sides_correct']['share'])} (n {pm['discrimination_counterpart']['both_sides_correct']['n']})",
                    f"- None-of-the-above pair (sec 4.6), n parents {nm['n_parents_with_both']} (ties none_absent/none_present {nm['tie_count_none_absent']}/{nm['tie_count_none_present']}; "
                    f"primary tie rule `{nm['primary_tie_rule']}`, R0-rule numbers in report.json): NOTA selection on none_absent {_g(nm['none_absent_nota_selection_rate'])}, "
                    f"none_present accuracy {_g(nm['none_present_accuracy'])}, false-NOTA {_g(nm['none_present_false_nota_rate'])}, **both-sides-right {_g(nm['both_sides_right'])}**"]
            if om:
                out += [f"- Operator column (sec 4.4, a statement about the harness, never compared with a Kev number): n {om['n']}, accuracy {_g(om['accuracy'])} (ties {om['tie_count']}), "
                        f"C-branch rate {_g(om['c_branch']['rate'])}, rows by tau {om['rows_by_tau']}, rows by tier {om['rows_by_tier']}"]
            out += [""]
    tt = report.get("track_t")
    if tt:
        out += [T.render_markdown(tt), ""]
        if "B-4" in tt:
            out += ["### B-4 (sec 6.3) against the untuned base of the same checkpoint", "",
                    T._table(["source", "level type", "verdict", "acc trained", "acc base", "gain", "T1 flip trained", "T1 flip base", "rise", "n"],
                             [[l["source"], l["level_type"], l["verdict"], T._f(l["trained_accuracy"]), T._f(l["base_accuracy"]), T._f(l["accuracy_gain"]),
                               T._f(l["trained_t1_flip"]), T._f(l["base_t1_flip"]), T._f(l["flip_rise"]), l["n_trained"]] for l in tt["B-4"]["lines"]]), ""]
    return "\n".join(out)


def build_header(a, identity, scorer_desc, tickets):
    score_desc = scorer_desc if isinstance(scorer_desc, dict) else {}
    return {"utc": C.utc_now(), "argv": sys.argv, "arm": a.arm, "model": {k: identity[k] for k in ("path", "sha256", "kind", "base_path", "base_revision")},
            "checkpoint_revision": identity.get("base_revision"), "prompt_version": P.PROMPT_VERSION, "render": "record_name",
            "prompt_format": P.PROMPT_FORMAT, "scorer": scorer_desc, "device": a.device, "stages": a.stages, "limit": a.limit, "primary_input_mode": a.primary_mode,
            "limit_groups": a.limit_groups, "track_t_config": a.track_t_config, "partitions": a.partitions,
            "declared_differences_from_kev": DECLARED_DIFFERENCES, "clauses": CL.clause_status(),
            "readings": {**{f"variants.{k}": getattr(V, k) for k in ("NOTA_TIE_RULE_PRIMARY", "BOTH_CORRECT_DENOMINATOR", "OPERATOR_FALLBACK_READING")},
                         **{f"track_t.{k}": getattr(T, k) for k in ("TIE_NOT_CORRECT_IN_CUM_COLUMN", "HALF_HASH_FIELD", "QUESTION70_TAU_FROM_GROUP70_CARVEOUT",
                                                                  "B1_ROLLUP_INCLUDES_BELOW_MIN_N", "B4_ACCURACY_FLOOR", "GATING_VOID_RULE")}},
            "dtype": a.dtype, "track_t_sources": a.track_t_sources,
            "dry_run_warnings": [w for w in (
                f"dtype {a.dtype} is not float32: bf16 is not admissible for a reported number (sec 14.6 item 2)" if a.dtype != "float32" and not a.model_path.startswith("mock") else None,
                (f"scorer {score_desc.get('mode')!r} / hf32 {score_desc.get('hf32')} / token_budget {score_desc.get('token_budget')}: not the scorer of record (sec 14.9 item 3): "
                 + "; ".join(score_desc.get("record_grade_problems", []))) if score_desc.get("record_grade") is False and not a.model_path.startswith("mock") else None,
                f"--limit {a.limit} / --limit-groups {a.limit_groups}: partial sets, pipeline check only" if (a.limit or a.limit_groups) else None,
                f"Track T sources restricted to {a.track_t_sources}" if set(a.track_t_sources.split(",")) != set(RC.SOURCE_FILES) else None) if w],
            "prechecks": {}}


def run_full(a, score_fn):
    """`score_fn(rows, input_mode)`; may carry `.describe()`. Returns the report dict (also written to <out>/report.json)."""
    global UNIT_TAG, MODEL_SHA
    UNIT_TAG = getattr(a, "unit_tag", "") or ""
    PRODUCED.clear()
    out = a.out
    os.makedirs(out, exist_ok=True)
    DATA_FILES.clear()
    log = Logger(out)
    with open(os.path.join(out, "RELAUNCH_EVAL.txt"), "w", encoding="utf-8") as f:
        f.write("python3 -P " + " ".join(sys.argv) + "\n")
    stages = set(a.stages.split(","))
    a.partitions = [p for p in a.partitions.split(",") if p] if isinstance(a.partitions, str) else a.partitions
    a.arm_kind = "K0" if a.arm == "K0" else a.arm
    # sec 7.9: K1-QO is trained with the state removed and "is scored with the state dropped, matching how it was trained"
    a.primary_mode = "drop" if a.arm == "K1-QO" else "full"
    if a.model_path.startswith("mock"):
        identity = {"path": a.model_path, "sha256": C.sha256_text(a.model_path), "kind": "mock", "base_path": a.model_path, "base_revision": "mock"}
    else:
        identity = TL.model_identity(a.model_path, a.adapter, a.round_dir)
    ensure_run_identity(out, identity, a)
    MODEL_SHA = identity["sha256"]
    declare_watch(out)
    tickets = {}
    if "test" in a.partitions:
        if a.limit or a.limit_groups:
            raise C.TestLockRefusal("sec 8.4: a limited read of a test partition still counts as the one read; --limit is refused with test")
        for suite in C.SUITES:
            tickets[(suite, "test")] = TL.authorize_test_read(identity, suite, "test", a.round_dir)
        log("test partitions authorized: " + ", ".join(f"{s}/{p}" for s, p in tickets))
    score_fn = TimedScorer(score_fn, a.device)
    score_fn.perf_path = os.path.join(out, f"perf.{a.unit_tag}.json" if getattr(a, "unit_tag", "") else "perf.json")
    report = {"header": build_header(a, identity, score_fn.describe(), tickets)}
    report["header"]["data_files"] = {}
    reads = []
    if stages & {"k", "k_score"}:
        tk, reads = run_track_k(a, score_fn, identity, out, log, tickets)
        if tk is not None:
            report["track_k"] = tk
            report["header"]["prechecks"] = {f: "ok" for f in sorted(os.listdir(os.path.join(out, "prechecks"))) if f.endswith(".json")}
    if stages & {"t_score", "report"}:
        block = run_track_t(a, score_fn, out, log, stages)
        if block is not None:
            report["track_t"] = block
    if PRODUCED:      # provenance_r3: what this process wrote or resumed, with sha256 and row count, the model sha and the scorer descriptor
        report["header"]["provenance_manifest"] = PV.write_unit_manifest(out, getattr(a, "unit_tag", ""), identity["sha256"], score_fn.describe(), PRODUCED, C.utc_now())
    report["header"]["throughput"] = score_fn.throughput()
    ds = score_fn.dedup_stats()
    report["header"]["duplicate_candidate_safeguard"] = {
        "clause": "R3 sec 14.6 item 4 (declared vacuous): candidates of one question with identical token sequences are scored once and share the score",
        "scorer_counts_this_process": ds,
        "scorer_counts_note": ("rows served from stored readouts (resume) never reach the scorer, so the scorer counts cover newly scored rows only; "
                               "the string-level audit per partition is in track_k.partitions.*.duplicate_option_audit"
                               if ds is not None else "the scorer exposes no dedup_stats"),
        "exercised": (None if ds is None else bool(ds.get("dup_questions", 0)))}
    report["header"]["data_files"].update(DATA_FILES)
    C.refuse_harness_identity(report, "report of record")             # sec 14.5 item 1: before a test read is logged, not after
    for ticket, n, acc in reads:        # sec 8.4 step 3, after every number is computed and before any report is written
        line = TL.record_test_read(ticket, n, acc, a.round_dir, run_dir=out)
        log("TEST-READS.log: " + line)
        report.setdefault("test_reads", []).append(line)
    if "report" in stages:
        with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1, sort_keys=True)
        with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as f:
            f.write(render_markdown(report))
        log(f"report: {os.path.join(out, 'report.md')}")
    return report


def run_full_marked(a, score_fn):
    """run_full with the CLAUDE.md sec 7 terminal marker beside the log: EVAL_COMPLETE.json holds the exit code."""
    tag = getattr(a, "unit_tag", "") or ""      # several processes (chips) share one run dir: each unit has its own marker, the final pass owns EVAL_COMPLETE.json
    marker = os.path.join(a.out, f"EVAL_COMPLETE.{tag}.json" if tag else "EVAL_COMPLETE.json")
    os.makedirs(a.out, exist_ok=True)
    if os.path.exists(marker):
        os.remove(marker)
    try:
        rep = run_full(a, score_fn)
        rc, err = 0, None
    except BaseException as e:    # noqa: BLE001 (marker must be written whatever happened)
        rc, err, rep = 1, traceback.format_exc(), None
        print(err, file=sys.stderr, flush=True)
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"exit_code": rc, "utc": C.utc_now(), "error": err}, f)
    if rc:
        raise SystemExit(rc)
    return rep
