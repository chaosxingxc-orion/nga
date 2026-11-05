"""Post-terminal verification and bounded numerical/resource report."""
import pathlib,json,hashlib,tarfile,io,subprocess,statistics,datetime
D=pathlib.Path(__file__).resolve().parent;E=D/'evidence'
def read(p):return json.loads(p.read_text())
def put(n,v):(D/n).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ssh(s):return subprocess.check_output(['ssh','npu',s],timeout=50)
assert read(E/'TERMINAL.json')['exit_code']==0
result=read(E/'RESULT.json');pre=read(D/'PREFLIGHT.json');checks=[]
for row in result['runs']:
 i=row['run'];r=E/('run'+str(i));ins=read(r/'INSPECT.json');h=ins['host']
 assert h['Runtime']=='runc' and h['NetworkMode']=='none' and not h['Devices'] and not h['DeviceRequests'] and not h['Privileged'] and h['ReadonlyRootfs'] and not h['AutoRemove']
 assert h['NanoCpus']==8000000000 and h['Memory']==12884901888 and h['PidsLimit']==256
 cfg=read(r/'config.json');owner=read(r/'output/OWNER.json');report=read(r/'output/report.json');term=read(r/'output/EXIT.json');summ=read(r/'output/summary.json');launch=read(r/'LAUNCH.json')
 assert cfg['workers']==4 and cfg['chunk_size']==100 and cfg['runtime']=='cpu' and cfg['adapter']=='native-panel-score-v1'
 assert owner['config_sha256']==term['config_sha256']==report['config_sha256']==row['config_sha256']==sha(r/'config.json')
 assert owner['manifest_sha256']==term['manifest_sha256']==report['manifest_sha256']==result['runs'][0]['manifest_sha256']
 assert summ==read(D/'source-summary.json') and summ['n']==46320
 assert report['receipts_sha256']=='832f0583a7aa00d07f24dec4f2ab313bd621632f4848c14d3a0dd372a1f8095c'
 env=dict(x.split('=',1) for x in launch['config']['Env'])
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']:assert env[k]=='1'
 name=ins['Name'].lstrip('/');diff=ssh('docker diff '+name).decode().splitlines();assert not [x for x in diff if x[2:].startswith(('/opt/nga','/usr/local','/usr/lib','/usr/bin'))]
 archive=ssh('docker cp '+name+':/opt/nga -')
 with tarfile.open(fileobj=io.BytesIO(archive)) as t:files={m.name:hashlib.sha256(t.extractfile(m).read()).hexdigest() for m in t if m.isfile()}
 assert files==pre['images'][row['condition']]['files']
 checks.append({'run':i,'exact_summary':True,'runtime_receipts_and_owner':True,'installed_closure_matches_preflight':True,'diff':diff,'cpu_constraints_verified':True,'numeric_reference':summ})
 # Exact retained API request and restart command; no mutable tag.
 (r/'RELAUNCH.sh').write_text('#!/bin/bash\n# Retained stage; same installed immutable image/config. Refuses already-completed scorer output.\ndocker start '+name+'\n')
put('POSTCHECK.json',checks)
source_checks={}
for source,name in [('config.json','source-config.json'),('manifest.json','source-manifest.json'),('output/summary.json','source-summary.json'),('output/EXIT.json','source-terminal.json')]:
 archive=ssh('docker cp nga-unified-panel-score-20261105-v4:/mnt/cephfs/xingchao/experiments/jev/r3_runs/unified_score_20261105_v4/'+source+' -')
 with tarfile.open(fileobj=io.BytesIO(archive)) as t:
  members=[m for m in t if m.isfile()];assert len(members)==1;data=t.extractfile(members[0]).read()
 assert data==(D/name).read_bytes();source_checks[source]={'sha256':hashlib.sha256(data).hexdigest(),'unchanged':True}
put('SOURCE-POSTCHECK.json',source_checks)
# Same-host endpoint deltas only. Includes all host work; cannot assign to scorer.
contention=[]
for i in range(1,7):
 r=E/('run'+str(i));a=read(r/'HOST-BEFORE.json');b=read(r/'HOST-AFTER.json');aa=list(map(int,a['cpu_stat'].split()[1:]));bb=list(map(int,b['cpu_stat'].split()[1:]));delta=[y-x for x,y in zip(aa,bb)];total=sum(delta[:8])
 item={'run':i,'host_loadavg_before':a['loadavg'],'host_loadavg_after':b['loadavg'],'cpu_count':a['cpu_count'],'affinity_count':len(a['sched_affinity']),'same_boot':a['boot_id']==b['boot_id'],'host_busy_fraction':1-(delta[3]+delta[4])/total if total else None,'host_iowait_fraction':delta[4]/total if total else None,'psi':{}}
 def psi(s):
  if s is None:return {}
  return {line.split()[0]:dict(x.split('=') for x in line.split()[1:]) for line in s.splitlines()}
 for kind in ['cpu','io','memory']:
  x=psi(a['psi_'+kind]);y=psi(b['psi_'+kind]);item['psi'][kind]={z:int(y[z]['total'])-int(x[z]['total']) for z in x.keys()&y.keys()}
 contention.append(item)
put('CONTENTION.json',contention)
result.update({'postcheck':'PASS_ALL_SIX','numerical_summary_each_run':[{'run':x['run'],**x['numeric_reference']} for x in checks],'resource_contention':contention,'bottleneck':{'observed':'whole scorer path and runtime outside scorer interval measured; record loop combines small-file validation/hashing, prediction reconstruction and arithmetic in Python threads','specific_dominant_phase':None,'reason':'no phase timers in accepted images; CPU/wall and host endpoint counters do not separate record I/O, Python execution, hash, fsync or GIL waits'},'recommendation':'After this baseline, instrument a separately reviewed candidate to separate record load/hash, validation/arithmetic and heartbeat publish; evaluate authenticated chunk resume/hash reuse under unchanged exact equivalence. Do not presume speedup from four Python threads or relax provenance checks.','limitations':['Three pairs only, shared host, unknown record page-cache residency, fixed order only partly counters drift; no disruptive flush.','Same source arithmetic; changed heartbeat lock and admission tau are not a new numeric algorithm. Baseline bytecode caches are absent from candidate, so startup equivalence is not presumed.','Reported scorer timer starts after config and source hashes/owner admission; child timer adds process/startup/admission/terminal; total interval begins after Docker create, before start, ends after wait event returns.','No isolated per-phase timings: all listed uninstrumented phases remain null.','Linux RUSAGE_CHILDREN supplies user/system CPU and max RSS KiB for scorer child; max RSS is not reserved memory. Eight CPU equivalents and 12GiB memory limit are identical.','Logical read is last periodic /proc child sample, incomplete; no physical I/O or Ceph traffic conclusion.','Host PSI and CPU counters cover concurrent work; process attribution and precise contention cause remain unknown.','Exact output means exact deterministic reconstruction against saved records, not new TEST inference or scientific acceptance.','Existing accepted runtime recomputes whole population after interruption; no item-granular resume claim.','CPU saved-scorer measurement only; future combined release and whole-base performance gate remain unqualified.']})
for row in result['runs']:
 row['mean_cpu_cores_during_child']=(row['user_cpu_seconds']+row['system_cpu_seconds'])/row['child_elapsed_seconds']
 row['saved_records_per_reported_second']=46320/row['reported_score_elapsed_seconds']
result['bottleneck']['measured_average_cpu_cores']=[{'run':r['run'],'cores':r['mean_cpu_cores_during_child']} for r in result['runs']]
result['bottleneck']['reserved_cpu_equivalents']=8
put('RESULT.json',result)
pins={'schema':'engineering-matched-cpu-score-sol-pins-v1','images':read(D/'RUN-PINS.json')['images'],'source_manifest_sha256':sha(D/'source-manifest.json'),'source_summary_sha256':sha(D/'source-summary.json'),'protocol_sha256':sha(E/'MATCHED-EFFICIENCY-PROTOCOL.json'),'addendum_sha256':sha(D/'ENGINEERING-ADDENDUM.json'),'closure_preflight_sha256':sha(D/'PREFLIGHT.json'),'per_run':[{'run':r['run'],'image':r['image'],'config_sha256':r['config_sha256'],'summary_sha256':r['summary_sha256']} for r in result['runs']],'evidence_archive_sha256':sha(D/'completed-evidence-a2.tar'),'evidence_files':read(D/'EVIDENCE-PINS.json'),'review_inputs':{str(p):sha(p) for p in [D.parent/'engineering-auto-pipeline-real-astra-20261105-v5/HANDOFF.md',D.parent/'unified-score-astra-20261105-v4/HANDOFF.md',D.parent.parent/'preparations/unified-score-20261105-v4/HANDOFF.md']},'review_outputs':{n:sha(D/n) for n in ['RESULT.json','POSTCHECK.json','SOURCE-POSTCHECK.json','CONTENTION.json','CLOSURE-REVIEW.json','MEASUREMENT-REVIEW.json','BYTECODE-METADATA.json']}}
put('PINS.json',pins)
print(json.dumps({'status':result['status'],'pairs':result['pairs'],'per_condition':result['per_condition'],'paired_ratios':result['paired_ratios'],'contention':contention},indent=2))
