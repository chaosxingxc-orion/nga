import pathlib,json,hashlib,statistics,shutil
D=pathlib.Path(__file__).resolve().parent;R=pathlib.Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/engineering_matched_cpu_score_20261105_v1')
r=json.loads((D/'RESULT.json').read_text());c=r['per_condition'];pairs=r['pairs']
rows=['| Run | Image | Start→terminal s | Reported score s | User CPU s | System CPU s | Peak RSS KiB |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
for x in r['runs']:rows.append(f"| {x['run']} | {x['condition']} | {x['total_to_terminal_seconds']:.6f} | {x['reported_score_elapsed_seconds']:.6f} | {x['user_cpu_seconds']:.6f} | {x['system_cpu_seconds']:.6f} | {x['max_rss_kib']} |")
text='''PASS — exact CPU saved-scorer benchmark completed; no demonstrated code speedup.

All six fresh 46,320-record runs completed with runtime EXIT=0 and the exact accepted
summary SHA-256 `5809e7cded0944611d701e850639b1c9030d3e5693966a427f2af8c10c677368`.
All installed scorer closures still match preflight; source config/manifest/summary/terminal
are unchanged. Required runtime population/join/inventory/receipt checks passed; no
missing/duplicate inventory is accepted by the registered runtime. Source contains nine
pre-existing semantic duplicates, unchanged; this is not a claim of semantic deduplication.
The same exact numerical summary is included for every run in RESULT.json.

'''+ '\n'.join(rows)+f'''

Baseline start→terminal median/min/max: {c['baseline']['total_to_terminal_seconds']['median']:.6f} / {c['baseline']['total_to_terminal_seconds']['min']:.6f} / {c['baseline']['total_to_terminal_seconds']['max']:.6f} s.
Candidate: {c['candidate']['total_to_terminal_seconds']['median']:.6f} / {c['candidate']['total_to_terminal_seconds']['min']:.6f} / {c['candidate']['total_to_terminal_seconds']['max']:.6f} s.
Reported-score median baseline {c['baseline']['reported_score_elapsed_seconds']['median']:.6f} s,
candidate {c['candidate']['reported_score_elapsed_seconds']['median']:.6f} s.

Pair (baseline run, candidate run) ratios B/C:
'''+ '\n'.join(f"- ({p['baseline_run']}, {p['candidate_run']}): {p['baseline_over_candidate']:.6f}× total; {p['reported_baseline_over_candidate']:.6f}× reported score." for p in pairs)+f'''

Paired total ratio median/min/max: {r['paired_ratios']['median']:.6f} / {r['paired_ratios']['min']:.6f} / {r['paired_ratios']['max']:.6f}×.
These are descriptive ratios, not a proven implementation speedup. Three pairs, fixed
order, shared host and unknown record cache state do not establish a causal improvement.
The median of per-pair ratios and ratio of condition medians are different statistics;
both are retained rather than selecting whichever looks faster.

Measured bottleneck evidence: first baseline used 675.113 system CPU seconds, versus
about 30 seconds for each of the last four runs. Early overhead is therefore real and
strongly changes the observed pair; its cause is unknown. The later runs use about
1.53–1.57 average CPU cores, despite four Python thread workers and an eight-CPU quota.
Thus later replay does not saturate its reserved CPU quota. The accepted record loop
combines small-file receipt/hash reads, Python validation, numerical reconstruction,
and ordered heartbeat publication; no internal phase is separately timed. It is not
possible to assign the dominant phase to Ceph, GIL, hashing, fsync or arithmetic from
this measurement. Host endpoint counters/PSI are in CONTENTION.json and cover all work.

Next optimization: profile those phases in a separately reviewed candidate, then evaluate
authenticated chunk resume/hash reuse with exact-output and corruption/recovery checks.
Do not increase workers blindly or remove provenance verification. No speedup is assumed.

Numerical reference for every run: whole panel 46,320, correct 30,465; choice 18,808 /
12,404 correct; score 9,940 / 4,305; yes_no 17,572 / 13,756. These are retained descriptive
reference fields, not a consistency metric or a new TEST evaluation. Scientific acceptance
and candidate TEST authority remain false; adaptive remains NOT_EVALUATED.

Baseline: `sha256:5904bd2bdbce7e67a4dfb920879db40f96bd8370af20796781775c565a43dfd9`.
Candidate: `sha256:27b2f9a84cbc3bc3eca95bb5ded98431f1a87ca8f0ef5d895970f4060ec4f325`.
Manifest: `0c893733922a0f6cd11deece688d39f36eb161d14f959970d367f6cf2a8478c1`.

The unchanged prospective protocol is supplemented by ENGINEERING-ADDENDUM.json selecting
27b2 for this saved-scorer engineering measurement only. Astra's final v5 verdict was
PASS_SCOPED_ACTUAL_DOCKER_QUALIFICATION with engineering HOLD; it is not broadened here.
The scorer's arithmetic dependency source is identical. Candidate adds heartbeat locking,
same-path resolution and explicit frozen tau admission; baseline ships runtime bytecode
caches absent from candidate. No new inference/training/NPU or scientific selection ran.

Every replay used CPU runc, network none, read-only installed image and source mount,
four ThreadPoolExecutor workers, chunk 100, numerical-library thread limits one, eight
CPU equivalents, 12 GiB limit and 256 PIDs. RSS is measured usage, not reserved memory.
Monotonic clocks and boot IDs are pinned per stage. Total timing excludes Docker create
and includes start through wait-event observation. Child and reported-score intervals are
nested, not additive. Reported score excludes initial config/source hashes and owner admission.
Internal uninstrumented phase times remain null. The external wrapper does not patch image code.

Warmup read the first 16 MiB of the shared requests file in 0.063213 s. This does not
warm all records; no cache was flushed. Logical /proc reads are partial last periodic
samples, not physical I/O or Ceph traffic. Physical I/O remains null. Resource counters
and interference evidence cannot establish cache residency or per-phase contention.

Detached retained queue: `nga-matched-cpu-sol-20261105-v1-queue-a2`; six retained stage
names `nga-matched-cpu-sol-20261105-v1-1` through `-6`, plus `-warmup`. Terminal source of
truth is root TERMINAL.json exit 0 and each output/EXIT.json, not container state.
Event waits use a 600-second controller fallback; no agent stage polling/raw-log reading.
Initial API-version rejection launched zero stages; retained failure receipts are under
failed-launch-api-v1/. Exact launch requests and relaunch instructions are persisted.
Interrupted scorer recovery remains full recomputation, not item-granular resume.

Ceph root: `/mnt/cephfs/xingchao/experiments/jev/r3_runs/engineering_matched_cpu_score_20261105_v1`.
Local report: `.local/reviews/engineering-matched-cpu-score-sol-20261105-v1/`.
PINS.json binds source, protocol, addendum, images, per-run configs and evidence.
RESULT.json contains all runs, pairs, median/min/max, numerical summaries and caveats.

The user's prerequisite to measure this CPU scorer before research resumes is now met
within this scope. Research is not resumed by this report: engineering HOLD, future
combined release, NPU qualification and the whole-base performance gate remain separate.
No root code, consumer, service or training edits, and no nested models were used.
'''
(D/'HANDOFF.md').write_text(text)
pins=json.loads((D/'PINS.json').read_text());pins['review_outputs']['HANDOFF.md']=hashlib.sha256((D/'HANDOFF.md').read_bytes()).hexdigest();(D/'PINS.json').write_text(json.dumps(pins,indent=2,sort_keys=True)+'\n')
for name in ['HANDOFF.md','RESULT.json','PINS.json','POSTCHECK.json','SOURCE-POSTCHECK.json','CONTENTION.json','ENGINEERING-ADDENDUM.json','CLOSURE-REVIEW.json']:
 shutil.copy2(D/name,R/('analyst-'+name))
print('Final report written and copied to Ceph.')
