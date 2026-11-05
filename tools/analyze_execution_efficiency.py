#!/usr/bin/env python3
"""Read-only execution audit. Exact roots only; no model imports or subprocesses.

Live collection saves normalized, credential-free observations locally. Replay:
  python3 -I tools/analyze_execution_efficiency.py --replay LOCAL/INPUTS.json \
      --output LOCAL/REPLAY.json --process-dir LOCAL/replay
Full audit output stays local. Use --public-summary for the conclusions-only export.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import time

RUN_BASE = Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
DISPATCH = '.local/dispatch/experiment-unblock-20261105-v1'
PHASE = '.local/planning/active-continuation-20261105-v1'
REVIEW = '.local/reviews'
RUN_NAMES = ['kev_documents-v1_08b_20261105_v7_configured'] + [
    f'kev_documents-v1_{m}_20261105_v11_ready' for m in ('2b', '4b', '9b')
] + [f'kev_devtools-v1_{m}_20261105_v9_ready' for m in ('08b', '2b', '4b', '9b')
] + [f'instruct_numeric_{m}_20261105_v1' for m in ('08b', '2b', '9b')]


def stamp(value):
    if type(value) in (int, float):
        return float(value)
    if not value or not isinstance(value, str) or value.startswith('0001-'):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def delta(a, b):
    return b-a if a is not None and b is not None and b >= a else None


def union_seconds(intervals):
    """Elapsed covered time, never summed parallel worker time."""
    spans = sorted((a, b) for a, b in intervals if a is not None and b is not None and b >= a)
    total = 0.0
    end = None
    for a, b in spans:
        total += b-max(a, end if end is not None else a) if end is None or b > end else 0
        end = max(b, end if end is not None else b)
    return total


def stats(values):
    v = sorted(x for x in values if x is not None)
    return dict(n=len(v), minimum=min(v) if v else None,
                median=statistics.median(v) if v else None,
                p95=v[max(0, int(len(v)*.95+.999999)-1)] if v else None,
                maximum=max(v) if v else None, sum=sum(v))


def category(name):
    if name.startswith(('astra-', 'sol-')):
        return 'review_or_analysis'
    if any(x in name for x in ('monitor', 'watcher', 'route', 'routing', 'status', 'queue')):
        return 'orchestration_observability'
    if any(x in name for x in ('unified', 'docker', 'bootstrap', 'runtime', 'release', 'host', 'permission', 'recovery')):
        return 'engineering_base_lifecycle'
    return 'experiment_preparation_integration'


def delivery(text):
    # Lexical flags are a reproducible triage, never an acceptance verdict.
    negative = re.search(r'\b(incomplete|unfinished|not complete|not ready|blocked|blockers|do not activate|NOT READY|pending)\b', text, re.I)
    return 'explicit_limit_or_incomplete' if negative else ('delivery_claim_needs_acceptance' if text.strip() else 'no_final')


class Collector:
    def __init__(self, repo):
        self.repo = repo
        self.sources = {}

    def raw(self, path):
        p = Path(path)
        if not p.is_absolute():
            p = self.repo/p
        if not p.is_file():
            self.sources[str(p)] = dict(exists=False)
            return None
        raw = p.read_bytes()
        self.sources[str(p)] = dict(exists=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        return raw

    def read(self, path):
        raw = self.raw(path)
        if raw is None:
            return {}
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            full=Path(path) if Path(path).is_absolute() else self.repo/path
            self.sources[str(full)]['parse_error'] = True
            return {}

    def text(self, path):
        raw = self.raw(path)
        return raw.decode(errors='replace') if raw is not None else ''


def collect(repo, as_of):
    c = Collector(repo)
    steering = c.read(PHASE+'/ENGINEERING-FIRST-STEERING.json')
    workers = []
    for d in sorted((repo/DISPATCH).iterdir()):
        if not d.is_dir():
            continue
        child, end = c.read(d/'CHILD.json'), c.read(d/'EXIT.json')
        final = c.text(d/'FINAL.txt')
        dep = c.read(d/'DEPENDENCY.json')
        scheduler = c.read(d/'SCHEDULER.json')
        brief = c.text(d/'BRIEF.txt')
        workers.append(dict(name=d.name, start=stamp(child.get('started_utc')),
                            finish=stamp(end.get('finished_utc')), exit_code=end.get('exit_code'),
                            model_route=child.get('model'), category=category(d.name),
                            delivery=delivery(final), final_sha256=hashlib.sha256(final.encode()).hexdigest() if final else None,
                            final_bytes=len(final.encode()), brief_bytes=len(brief.encode()),
                            parent=Path(dep.get('source','')).name or scheduler.get('source'),
                            dependency_observed=stamp(dep.get('utc')),
                            scheduler_created=stamp(scheduler.get('utc')),
                            artifact_links=len(re.findall(r'\]\([^)]+\)', final))))
    runs = []
    copies = []
    for name in RUN_NAMES:
        root = RUN_BASE/name
        plan = c.read(root/('HOST-PLAN.json' if name.startswith('instruct') else 'PLAN.json'))
        launch = c.read(root/'PARENT-LAUNCH-INTENT.json')
        # Preflight's top-level time is retained only; never infer a start from mtime.
        preflight = c.read(root/'PARENT-PREFLIGHT.json')
        output = root/'output'
        attempts = []
        hostdir = output/'host_attempts'
        for h in sorted(hostdir.iterdir()) if hostdir.exists() else []:
            if not h.is_dir():
                continue
            claim = c.read(h/'CLAIM.json'); release = c.read(h/'RELEASE.json')
            hostexit = c.read(h/'EXIT.json'); receipt = c.read(h/'LAUNCH_RECEIPT.json')
            intent = c.read(h/'START_INTENT.json')
            a = output/'attempts'/h.name
            report = c.read(a/'report.json'); terminal = c.read(a/'EXIT.json')
            heartbeat = c.read(output/'heartbeat.json')
            generic = c.read(output/'cpu'/h.name/'EXIT.json')
            kev = c.read(output/'kev_cpu'/h.name/'EXIT.json')
            gs = c.read(output/'cpu'/h.name/'SERVICE.json')
            ks = c.read(output/'kev_cpu'/h.name/'KEV-SERVICE.json')
            gh = c.read(output/'cpu'/h.name/'heartbeat.json')
            kh = c.read(output/'kev_cpu'/h.name/'heartbeat.json')
            # Missing stage boundaries justify script-only extraction of JSON stage
            # records from the exact retained runtime file. Never emit other lines.
            events = []
            log = h/'runtime.log'
            raw = c.raw(log)
            if raw:
                for line, text in enumerate(raw.decode(errors='replace').splitlines(), 1):
                    if not text.startswith('{'):
                        continue
                    try:
                        e = json.loads(text)
                        if e.get('stage') in ('startup','model_ready','complete','failed'):
                            events.append(dict(stage=e['stage'], time=stamp(e.get('utc_seconds')), line=line))
                    except ValueError:
                        pass
            # No raw container inspection is needed: release records preserve its
            # actual start/end/ID. Never collect Config.Env or shell commands.
            bound = dict(claim=stamp(claim.get('claimed_utc')),
                         container_start=stamp(release.get('container_started_at')),
                         container_finish=stamp(release.get('container_finished_at')),
                         release=stamp(release.get('released_utc')),
                         host_intent=stamp(intent.get('utc_seconds')),
                         generic_finish=stamp(generic.get('utc_seconds')),
                         kev_finish=stamp(kev.get('utc_seconds')),
                         runtime_finish=stamp(terminal.get('utc_seconds')),
                         generic_heartbeat=stamp(gh.get('utc_seconds')),
                         kev_heartbeat=stamp(kh.get('utc_seconds')))
            rt = report.get('runtime', heartbeat.get('runtime',{}))
            attempts.append(dict(attempt=h.name, boundaries=bound, events=events,
                chip=claim.get('chip',plan.get('chip')), container_id=release.get('container_id', receipt.get('container_id')),
                host_exit=hostexit.get('exit_code'), runtime_exit=terminal.get('exit_code'),
                container_exit=release.get('exit_code'), generic_exit=generic.get('exit_code'), kev_exit=kev.get('exit_code'),
                completed=report.get('completed'), expected=plan.get('population',{}).get('count',plan.get('count')),
                computed=report.get('computed'), reused=report.get('reused'),
                forwards_per_item=report.get('forwards_per_new_item'), runtime=rt,
                heartbeat_qps_per_chip=heartbeat.get('questions_per_second_per_chip'),
                cpu_start_gap_seconds=(ks['start_ticks']-gs['start_ticks'])/100
                if gs.get('boot_id') and gs.get('boot_id')==ks.get('boot_id') and type(gs.get('start_ticks')) is int and type(ks.get('start_ticks')) is int else None,
                claim_pin_matches=release.get('claim_sha256')==c.sources.get(str(h/'CLAIM.json'),{}).get('sha256') if release else None,
                allocation_transition=stamp(next((f.get('released_utc') for f in release.get('allocation_after',{}).get('free',[]) if f.get('chip')==claim.get('chip')),None)),
                last_heartbeat_time=stamp(heartbeat.get('utc_seconds'))))
            attempts[-1]['allocation_snapshot'] = dict(
                released_utc=release.get('released_utc'),
                allocated_chips=[x.get('chip') for x in release.get('allocation_after',{}).get('allocation',[])],
                free_chips=[x.get('chip') for x in release.get('allocation_after',{}).get('free',[])],
                meaning='Point observation only; not an interval of idleness')
        sizes = []
        items = output/'items'
        if items.exists():
            for d in items.iterdir():
                f=d/'record.json'
                if f.is_file(): sizes.append(f.stat().st_size)
        operands = [f.stat().st_size for f in (output/'long_operands').glob('*/*/operands.npz')]
        manifest = plan.get('model_files',{})
        weights = [Path(p) for p in manifest if p.endswith('.safetensors')]
        weight_bytes = sum(p.stat().st_size for p in weights if p.exists())
        # Only source files explicitly named in the accepted root's code directory.
        code=root/'code'
        if code.exists():
            for f in sorted(code.glob('*.py')):
                raw = c.raw(f)
                if raw is not None:
                    copies.append(dict(run=name, name=f.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        runs.append(dict(name=name, root=str(root), plan_schema=plan.get('schema'), model=plan.get('model'),
            model_manifest=plan.get('model_sha256'), weight_bytes=weight_bytes,
            launch_intent=stamp(launch.get('utc')), preflight_time=stamp(preflight.get('utc')),
            attempts=attempts, compact_records=len(sizes), compact_record_bytes=sum(sizes),
            record_size_stats=stats(sizes), npz_count=len(operands), npz_bytes=sum(operands),
            model_files_also_in_files=sum(p in plan.get('files',{}) for p in manifest),
            model_file_count=len(manifest)))
    reviews={}
    for name, path in {
        'dag': REVIEW+'/dag-native-independent-20261103-v1/ACCEPTANCE.json',
        'dag_validation': REVIEW+'/dag-native-independent-20261103-v1/FINAL-VALIDATION.json',
        'score_v4': REVIEW+'/unified-score-astra-20261105-v4/REVIEW.json',
        'integration_v5': REVIEW+'/unified-integrate-astra-20261105-v5/REVIEW.json',
        'instruct_results': REVIEW+'/instruct-numeric-results-sol-20261105-v1/RESULTS.json',
    }.items(): reviews[name]=c.read(path)
    numeric=[]
    for model in ('08b','2b','9b'):
        r=c.read(f'{REVIEW}/instruct-numeric-results-sol-20261105-v1/{model}/POSTRUN-REPORT.json')
        numeric.append(dict(model=model, status=r.get('status'), elapsed_seconds=r.get('elapsed_seconds'),
                            weight_bytes_rehashed=r.get('weight_bytes_rehashed'), operands=sum(len(x.get('variants',[])) for x in r.get('items',[]))))
    scores=[]
    for label,path in [('v4_submitted','unified-score-astra-20261105-v4/evidence/submitted-report.json'),
                       ('v4_independent','unified-score-astra-20261105-v4/evidence/replay-report.json'),
                       ('v4_recovered','unified-score-astra-20261105-v4/evidence/recovery-report.json'),
                       ('v5_independent','unified-integrate-astra-20261105-v5/evidence/report.json')]:
        r=c.read(REVIEW+'/'+path)
        scores.append(dict(label=label, elapsed_seconds=r.get('elapsed_seconds'), records=r.get('records'),
                           summary_sha256=r.get('summary_sha256')))
    primary=c.read(REVIEW+'/kev-devtools08-sol-20261105-v1/PRIMARY-RESULT.json')
    full_json=[]
    # Three retained v5 CPU fixtures, never model data or mutable current source.
    for f in sorted((repo/REVIEW/'unified-integrate-astra-20261105-v5/evidence/mock-inference/items').glob('*/record.json')):
        raw=c.raw(f)
        if raw is None: continue
        start=time.perf_counter(); row=json.loads(raw); decode=time.perf_counter()-start
        start=time.perf_counter(); encoded=json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False).encode(); encode=time.perf_counter()-start
        full_json.append(dict(path=str(f),record_bytes=len(raw),logit_values=len(row.get('logits',[])),
                              cpu_decode_seconds=decode,cpu_encode_seconds=encode,reserialized_bytes=len(encoded),
                              json_to_float32_payload_ratio=len(raw)/(248320*4)))
    # Pin the inspected historical source, not another worker's changing implementation.
    c.raw(REVIEW+'/unified-component-cpu-sol-20261105-v1/evidence/overlay/components/inference/native_inference.py')
    c.raw(repo/'tools/analyze_execution_efficiency.py')
    return dict(schema='nga-efficiency-normalized-inputs-v1', as_of=as_of,
                collection_finished_utc=datetime.now(timezone.utc).isoformat(), steering=steering,
                workers=workers, runs=runs, copies=copies, reviews=reviews, numeric=numeric,
                score_reports=scores, kev_analysis_seconds=primary.get('elapsed_seconds'),
                full_json_fixtures=full_json, sources=c.sources)


def worker_audit(data):
    phase=stamp(data['steering']['utc'])
    workers=[dict(w) for w in data['workers']]
    byname={w['name']:w for w in workers}
    for w in workers:
        w['seconds']=delta(w['start'], w['finish'])
        w['queue_after_dependency_seconds']=None
        parent=byname.get(w['parent'],{})
        if parent.get('finish') is not None:
            # A successor can intentionally start before its dependency finishes;
            # that is overlap, not a negative queue wait.
            w['queue_after_dependency_seconds']=delta(parent['finish'],w['start'])
        w['dependency_detection_seconds']=delta(parent.get('finish'),w['dependency_observed'])
    spans=[(w['start'],w['finish']) for w in workers if w['seconds'] is not None]
    cats={}
    for cat in sorted({w['category'] for w in workers}):
        ws=[w for w in workers if w['category']==cat]
        cats[cat]=dict(tasks=len(ws), durations=stats(w['seconds'] for w in ws),
                       union_seconds=union_seconds((w['start'],w['finish']) for w in ws),
                       exit_zero=sum(w['exit_code']==0 for w in ws),
                       explicit_limit_or_incomplete=sum(w['delivery']=='explicit_limit_or_incomplete' for w in ws))
    family=[]
    for v in range(1,7):
        if v==1: names=['terra-unified-docker-base-v1','astra-unified-docker-base-v1']
        elif v==2: names=['terra-unified-docker-build-v2','astra-unified-docker-build-v2']
        elif v==3: names=['terra-unified-docker-runtime-v3','astra-unified-docker-runtime-v3']
        elif v==4: names=['terra-unified-score-v4','astra-unified-score-v4']
        elif v==5: names=['terra-unified-integrate-components-v5','astra-unified-integrate-v5']
        else: names=['terra-unified-launch-ready-v6','astra-unified-launch-ready-v6']
        ws=[byname[n] for n in names if n in byname]
        starts=[w['start'] for w in ws if w['start'] is not None];ends=[w['finish'] for w in ws if w['finish'] is not None]
        family.append(dict(version=v, workers=names, worker_seconds=sum(w['seconds'] or 0 for w in ws),
                           elapsed_seconds=delta(min(starts),max(ends)) if starts and ends else None,
                           statuses=[w['delivery'] for w in ws]))
    # Longest verified dependency chain. Do not invent edges from temporal adjacency.
    memo={}
    def chain(name, visiting):
        if name in memo:return memo[name]
        if name in visiting:return (0,[],0)
        w=byname[name];duration=w['seconds'] or 0
        p=byname.get(w['parent'])
        if p and p.get('finish') is not None and w['start'] is not None and p['finish']<=w['start']:
            cost,names,wait=chain(p['name'],visiting|{name})
            gap=w['start']-p['finish'];answer=(cost+gap+duration,names+[name],wait+gap)
        else:answer=(duration,[name],0)
        memo[name]=answer;return answer
    chains=[chain(w['name'],set()) for w in workers if w['seconds'] is not None]
    longest=max(chains,default=(0,[],0))
    return dict(total_directories=len(workers), started=sum(w['start'] is not None for w in workers),
        terminal=sum(w['finish'] is not None for w in workers), exit_zero=sum(w['exit_code']==0 for w in workers),
        exit_nonzero=sum(w['exit_code'] is not None and w['exit_code']!=0 for w in workers),
        missing_final=sum(w['delivery']=='no_final' for w in workers),
        zero_exit_with_explicit_limit=sum(w['exit_code']==0 and w['delivery']=='explicit_limit_or_incomplete' for w in workers),
        artifact_completion_accepted_count=None, classification='lexical triage; no independent delivery acceptance inferred',
        summed_worker_seconds=sum(w['seconds'] or 0 for w in workers), union_worker_seconds=union_seconds(spans),
        elapsed_span_seconds=delta(min(a for a,b in spans),max(b for a,b in spans)) if spans else None,
        earliest_start=iso(min(a for a,b in spans)) if spans else None,
        latest_finish=iso(max(b for a,b in spans)) if spans else None,
        pre_steering_worker_seconds=sum(max(0,min(b,phase)-a) for a,b in spans if a<phase),
        post_steering_worker_seconds=sum(max(0,b-max(a,phase)) for a,b in spans if b>phase),
        categories=cats, queue_wait_seconds=stats(w['queue_after_dependency_seconds'] for w in workers),
        dependency_detection_seconds=stats(w['dependency_detection_seconds'] for w in workers),
        verified_chain=dict(seconds=longest[0], nodes=longest[1], queue_seconds=longest[2],
                            interpretation='longest observed dependency chain; lower bound on full critical path'),
        unified_versions=family, tasks=workers,
        token_distribution=dict(available=False, reason='CHILD/EXIT/FINAL contain no actual usage; raw token events deliberately excluded'))


def run_audit(run):
    out=dict(run)
    for a in out['attempts']:
        b=a['boundaries'];e={x['stage']:x['time'] for x in a['events']}
        seconds=dict(lease=delta(b['claim'],b['release']),container=delta(b['container_start'],b['container_finish']),
            claim_to_container=delta(b['claim'],b['container_start']),exit_to_release=delta(b['container_finish'],b['release']),
            parent_intent_to_claim=delta(run['launch_intent'],b['claim']),
            host_intent_to_claim=delta(b['host_intent'],b['claim']),
            release_to_generic_terminal=delta(b['release'],b['generic_finish']),
            release_to_kev_terminal=delta(b['release'],b['kev_finish']),
            generic_to_kev_terminal=delta(b['generic_finish'],b['kev_finish']),
            startup_to_model_ready=delta(e.get('startup'),e.get('model_ready')),
            model_ready_to_complete=delta(e.get('model_ready'),e.get('complete')),
            queue_ready_to_claim=None,preflight=None,
            weight_hash=None,model_load=None,npu_kernel_compute=None, cpu_score_exact=None)
        # The final heartbeat may overwrite the initial one: this is only a lower
        # bound on time in the service, never the complete CPU score duration.
        seconds['generic_last_heartbeat_to_terminal_lower_bound']=delta(b['generic_heartbeat'],b['generic_finish'])
        seconds['kev_last_heartbeat_to_terminal_lower_bound']=delta(b['kev_heartbeat'],b['kev_finish'])
        if a['heartbeat_qps_per_chip'] and a['computed']:
            seconds['execute_loop_from_heartbeat']=a['computed']/a['heartbeat_qps_per_chip']
        else: seconds['execute_loop_from_heartbeat']=None
        a['seconds']=seconds
        a['artifact_completion']=bool(all(type(a[k]) is int and a[k]==0 for k in ('runtime_exit','host_exit','container_exit')) and
            type(a['completed']) is int and type(a['expected']) is int and a['completed']==a['expected'] and a['claim_pin_matches'])
        a['phase_bounds_seconds']=dict(
            startup_hash_and_load_combined_upper_bound=seconds['startup_to_model_ready'],
            npu_compute_lower_bound=0,
            npu_compute_upper_bound=seconds['model_ready_to_complete'] or seconds['execute_loop_from_heartbeat'],
            interpretation='Bounds only, no decomposition of overlapped CPU, load, hashing and device work.')
        a['container_questions_per_second_per_chip']=(a['computed']/seconds['container']/a['runtime'].get('chips',1)
            if a['computed'] is not None and seconds['container'] else None)
        a['missing_boundaries']=['weight hash begin/end','model load begin/end','synchronized NPU forward begin/end',
                                 'CPU service start UTC/monotonic anchor (start_ticks alone is not UTC)']
        if not a['events']: a['missing_boundaries'].append('startup/model_ready/complete structured stages')
    return out


def occupancy(runs, steering):
    rows=[]
    for r in runs:
        for a in r['attempts']:
            b=a['boundaries']
            if b['claim'] is not None:
                rows.append(dict(run=r['name'],chip=a['chip'],claim=b['claim'],release=b['release'],
                                 start=b['container_start'],finish=b['container_finish'],claim_pin_matches=a['claim_pin_matches']))
    closed=[r for r in rows if r['release'] is not None]
    start=min((r['claim'] for r in closed),default=None);end=max((r['release'] for r in closed),default=None)
    chips={}
    for chip in sorted({r['chip'] for r in rows if type(r['chip']) is int}):
        rs=[r for r in rows if r['chip']==chip]
        chips[str(chip)]=dict(lease_seconds=union_seconds((r['claim'],r['release']) for r in rs),
            container_seconds=union_seconds((r['start'],r['finish']) for r in rs))
    capacity=(end-start)*8 if start is not None else None
    lease=sum(x['lease_seconds'] for x in chips.values());container=sum(x['container_seconds'] for x in chips.values())
    return dict(window_start=iso(start),window_end=iso(end),chips=8,selected_run_intervals=rows,
        window_capacity_chip_seconds=capacity,selected_lease_chip_seconds=lease,selected_container_chip_seconds=container,
        selected_lease_fraction=lease/capacity if capacity else None,
        selected_container_fraction=container/capacity if capacity else None,
        whole_host_actual_occupancy_fraction_bounds=[container/capacity,1] if capacity else None,
        per_chip=chips,unclosed_claims=sum(r['release'] is None for r in rows),
        ai_core_utilization=None,
        limits=['Selected exact roots only: other jobs may occupy every uncovered interval.',
                'Container existence and ledger reservations are not AI Core utilization.',
                'Release receipt contains retained physical container times; no fresh docker/NPU query.',
                'UTC intervals are descriptive; known cross-host skew about 94.5 seconds. Same-host ordering preferred.',
                'An eight-card-free ledger snapshot cannot establish a free interval.',
                'No claim that unobserved time is idle; lease union and container union are separate.'])


def analyze(data):
    workers=worker_audit(data);runs=[run_audit(json.loads(json.dumps(r))) for r in data['runs']]
    groups=defaultdict(list)
    for f in data['copies']: groups[f['sha256']].append(f)
    repeated=[fs for fs in groups.values() if len(fs)>1]
    duplication=dict(files=len(data['copies']),unique_byte_identities=len(groups),
        copied_bytes=sum(f['bytes'] for f in data['copies']),
        duplicate_instances=sum(len(fs)-1 for fs in repeated),
        duplicate_bytes=sum((len(fs)-1)*fs[0]['bytes'] for fs in repeated),
        repeated_groups=[dict(name=fs[0]['name'],copies=len(fs),bytes_each=fs[0]['bytes'],sha256=fs[0]['sha256']) for fs in repeated],
        limitation='Exact source copies across eleven roots; copy/review CPU cost not instrumented; copies may be intentional frozen provenance.')
    kev_bytes=sum(r['weight_bytes'] for r in runs if r['name'].startswith('kev'))
    numeric_bytes=sum(r['weight_bytes'] for r in runs if r['name'].startswith('instruct'))
    unified_names={name for v in workers['unified_versions'] for name in v['workers']}
    unified=[w for w in workers['tasks'] if w['name'] in unified_names and w['seconds'] is not None]
    unified_elapsed=delta(min((w['start'] for w in unified),default=None),max((w['finish'] for w in unified),default=None))
    return dict(schema='nga-engineering-efficiency-v1', observed_as_of=data['as_of'], steering=data['steering'],
        collection_finished_utc=data.get('collection_finished_utc'),
        scope=dict(direct_analysis=True,nested_models=False,npu_commands=False,experiments_launched=False,
                   existing_runs_mutated=False,commit_or_push=False),
        worker_summary={k:v for k,v in workers.items() if k!='tasks'},runs=runs,
        occupancy=occupancy(runs,data['steering']),code_duplication=duplication,
        weight_hash_audit=dict(kev_one_pass_weight_bytes=kev_bytes,numeric_one_pass_weight_bytes=numeric_bytes,
             numeric_manifest_and_inventory_passes_per_verify=2,
             minimum_completed_runtime_and_two_kev_cpu_routes_logical_weight_bytes=3*kev_bytes+2*numeric_bytes,
             source_path_nominal_total_passes=dict(kev=6,instruct_numeric=11),
             source_path_nominal_weight_bytes=6*kev_bytes+11*numeric_bytes,
             elapsed_seconds=None,physical_ceph_bytes=None,
             interpretation='Logical hash bytes from successful required verifier paths; page cache may serve reads. Extra preflight/review calls unknown. Nominal totals require start/main/supervise call-path composition; not measured I/O counters.',
             inspected_boundaries=['Kev runtime verify model inventory','Kev generic CPU verify(cpu=True), default model_files=True',
                                   'Kev consumer CPU verify(cpu=True), default model_files=True',
                                   'numeric verify d.files includes model_files then full model inventory',
                                   'host main start + main supervise + supervise verify; numeric approval rehashes d.files']),
        reused_instruct_analysis=data['numeric'],reused_kev_analysis_seconds=data['kev_analysis_seconds'],
        score_reports=data['score_reports'],
        accepted_capabilities=dict(dag=data['reviews']['dag'].get('verdict'),dag_tests=data['reviews']['dag'].get('tests'),
             dag_production=data['reviews']['dag'].get('production_dispatch_verdict'),
             managed_actions=len(data['reviews']['dag_validation'].get('proposed',[])),
             score_v4=data['reviews']['score_v4'].get('decision'),integration_v5=data['reviews']['integration_v5'].get('decision'),
             npu_ready_subset=data['reviews']['integration_v5'].get('parent_npu_ready_subset')),
        ranked_bottlenecks=[
            dict(rank=1, issue='Fragmented delivery and serialized component review',
                 measured_elapsed_seconds=unified_elapsed,
                 measured_worker_seconds=sum(w['seconds'] for w in unified),
                 outcome='No integrated NPU-ready subset in reviewed v5/v6',
                 confidence='high for durations/scope; avoidable fraction unknown'),
            dict(rank=2, issue='600s Kev CPU watcher fallback',
                 measured_cpu_start_gap_sum_seconds=sum(a['cpu_start_gap_seconds'] or 0 for r in runs for a in r['attempts']),
                 confidence='high for same-boot gaps; not all gap is proven sleep'),
            dict(rank=3, issue='Repeated model weight hashing across lifecycle/CPU boundaries',
                 confidence='high for source path/logical bytes; missing measured hash seconds and physical I/O'),
            dict(rank=4, issue='Full-vector JSON in unified v5 inference fixtures',
                 confidence='high for bytes and CPU microbenchmark; no production/Ceph speedup established'),
            dict(rank=5, issue='CPU whole-panel replay variability and full recomputation recovery',
                 confidence='high for observed reports; uncontrolled host/cache differences'),
            dict(rank=6, issue='Dependency polling delay',
                 confidence='high for 65 explicit edges; queue intent is not execution readiness')],
        prospective_engineering_targets=dict(scientific_metrics_changed=False, activation_now=False,
            release_to_cpu_start_p95_seconds=5, release_to_cpu_start_max_seconds=15,
            ready_to_dispatch_p95_seconds=10, exit_to_release_p95_seconds=10,
            warm_admission_p95_seconds=5, weight_full_hashes_per_immutable_generation_max=1,
            binary_vector_bytes_max=1013280, synthetic_roundtrip_mismatches=0,
            paired_serialization_cpu_reduction_min_fraction=.75,
            paired_serialization_bytes_reduction_min_fraction=.75,
            full_panel_score_warm_target_seconds=150, full_panel_score_regression_max_fraction=.10,
            checkpoint_resume_extra_committed_items_max=100, cpu_fault_cycles_min=20,
            duplicate_launches_allowed=0, source_capture_bypasses_allowed=0,
            synchronized_phase_timing_coverage_min_fraction=.99,
            note='Recommendations for a future reviewed release; no current passing claim or NPU qualification granted'),
        full_vector_cost=dict(vocabulary=248320,float32_bytes_per_vector=248320*4,
            theoretical_46320_vectors_binary_bytes=248320*4*46320,
            evidence='Kev cells persist compact candidates; numeric runs persist NPZ. Retained unified v5 CPU fixtures persist full-vocabulary JSON.',
            json_fixture_measurements=data.get('full_json_fixtures',[]),
            benchmark_scope='One stdlib encode/decode per retained fixture in this CPU process; warm local filesystem. No Ceph I/O timing or NPU measured.',
            warning='Projected population storage is not observed JSON I/O; fixture timings are not controlled production speedups.'),
        timing_limits=['Stage model_ready-to-complete includes forwards, CPU validation, serialization, Ceph fsync and Python scheduling.',
                      'Heartbeat inverse-rate duration is whole execute loop, including I/O and CPU; never isolated NPU compute.',
                      'Dependency waits use only explicit DEPENDENCY/SCHEDULER edges; scheduling intent is not a ready timestamp.',
                      'All thresholds in companion release plan are prospective engineering targets, not scientific metrics.'],
        source_manifest=data['sources'])


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def public_summary(result, audit_sha256):
    """Explicit publication boundary: no run, worker or source-path records."""
    summary = {k: result[k] for k in (
        'observed_as_of', 'collection_finished_utc', 'timing_limits',
        'prospective_engineering_targets', 'weight_hash_audit', 'accepted_capabilities')}
    summary.update(schema='nga-engineering-efficiency-public-summary-v1',
                   audit_sha256=audit_sha256,
                   audit_scope='eleven selected roots; not whole-host utilization or token accounting',
                   implementation_status='engineering hold; no full-base release',
                   engineering_action_priorities=result['ranked_bottlenecks'],
                   priority_limit='Engineering judgment, not measured avoidable-time dominance')
    summary['worker_summary'] = {k: result['worker_summary'][k] for k in (
        'started', 'terminal', 'exit_zero', 'exit_nonzero', 'zero_exit_with_explicit_limit',
        'classification', 'summed_worker_seconds', 'elapsed_span_seconds',
        'union_worker_seconds', 'categories', 'token_distribution', 'queue_wait_seconds')}
    summary['occupancy'] = {k: result['occupancy'][k] for k in (
        'chips', 'selected_container_chip_seconds', 'selected_lease_chip_seconds',
        'window_capacity_chip_seconds', 'selected_container_fraction',
        'whole_host_actual_occupancy_fraction_bounds', 'ai_core_utilization', 'limits')}
    summary['code_duplication'] = {k: result['code_duplication'][k] for k in (
        'files', 'unique_byte_identities', 'duplicate_instances', 'copied_bytes',
        'duplicate_bytes', 'limitation')}
    summary['full_vector_cost'] = {k: result['full_vector_cost'][k] for k in (
        'vocabulary', 'float32_bytes_per_vector', 'theoretical_46320_vectors_binary_bytes',
        'evidence', 'benchmark_scope', 'warning')}
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--as-of',help='UTC observation cutoff, default current UTC; not an experiment boundary')
    p.add_argument('--replay',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--process-dir',type=Path,required=True)
    p.add_argument('--public-summary',type=Path,help='Optional aggregate-only publication export')
    a=p.parse_args()
    data=json.loads(a.replay.read_text()) if a.replay else collect(a.repo,a.as_of or datetime.now(timezone.utc).isoformat())
    result=analyze(data)
    write(a.process_dir/'INPUTS.json',data)
    write(a.process_dir/'WORKERS.json',worker_audit(data))
    write(a.output,result)
    if a.public_summary:
        write(a.public_summary,public_summary(result,hashlib.sha256(a.output.read_bytes()).hexdigest()))
    print(json.dumps(dict(output=str(a.output),workers=result['worker_summary']['started'],runs=len(result['runs']),
                          npu_commands=False,experiment_launch=False)))


if __name__=='__main__': main()
