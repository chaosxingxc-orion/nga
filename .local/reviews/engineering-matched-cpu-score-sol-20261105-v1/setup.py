import pathlib,json,hashlib,shutil,subprocess,shlex,os,datetime
D=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/engineering_matched_cpu_score_20261105_v1')
R.mkdir(exist_ok=False)
def put(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
B='sha256:5904bd2bdbce7e67a4dfb920879db40f96bd8370af20796781775c565a43dfd9';C='sha256:27b2f9a84cbc3bc3eca95bb5ded98431f1a87ca8f0ef5d895970f4060ec4f325'
protocol=D.parent.parent/'planning/active-continuation-20261105-v1/MATCHED-EFFICIENCY-PROTOCOL.json'
pre=json.loads((D/'PREFLIGHT.json').read_text())
assert all(x['path'].split('/')[-1].endswith('.pyc') for x in pre['changed'] if x['path'].startswith('nga/source/native/'))
add={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'ENGINEERING_ONLY_SAVED_SCORER_MEASUREMENT','candidate_image':C,'baseline_image':B,'protocol_sha256':sha(protocol),'reason':'pending combined image resolved prospectively to current Astra scoped accepted CPU image for saved scorer measurement only','future_combined_release_qualification':False,'scientific_protocol_changes':False,'research_dispatch':'hold','scorer_difference':'same numerical algorithm and source dependencies; candidate adds heartbeat lock, resolves same fixed path, admits frozen contract tau explicitly','conditions':{'workers':4,'chunk_size':100,'thread_limit':1,'cpus':8,'memory_bytes':12884901888,'pids':256},'resume':'queue skips terminal validated stages; interrupted scorer fully recomputes, no item-granular resume claim'}
put(D/'ENGINEERING-ADDENDUM.json',add)
for f in ['queue.py','instrument.py','ENGINEERING-ADDENDUM.json','PREFLIGHT.json','source-config.json','source-manifest.json','source-summary.json']:
 shutil.copy2(D/f,R/f)
shutil.copy2(protocol,R/'MATCHED-EFFICIENCY-PROTOCOL.json')
pins={'images':{'baseline':B,'candidate':C},'source_config':json.loads((D/'source-config.json').read_text()),'manifest_sha256':sha(D/'source-manifest.json'),'summary_sha256':sha(D/'source-summary.json'),'protocol_sha256':sha(protocol),'addendum_sha256':sha(D/'ENGINEERING-ADDENDUM.json'),'scripts':{f:sha(R/f) for f in ['queue.py','instrument.py']},'closure':{'baseline':pre['images']['baseline']['files'],'candidate':pre['images']['candidate']['files']}}
put(R/'RUN-PINS.json',pins);put(D/'RUN-PINS.json',pins)
name='nga-matched-cpu-sol-20261105-v1-queue'
args=['docker','run','-d','--pull=never','--name',name,'--runtime','runc','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','1','--memory','512m','--pids-limit','64','--mount','type=bind,src=/mnt/cephfs,dst=/mnt/cephfs,readonly','--mount','type=bind,src='+str(R)+',dst='+str(R),'--mount','type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock','--entrypoint','/bin/bash',B,'-c','exec python3 -B -P '+shlex.quote(str(R/'queue.py'))+' >> '+shlex.quote(str(R/'queue.log'))+' 2>&1']
(R/'RELAUNCH.sh').write_text('#!/bin/bash\n# Initial launch. Retained queue restart after interruption: docker start '+name+'\n'+shlex.join(args)+'\n')
put(R/'PRE-REGISTRATION.json',{'purpose':'matched CPU saved-result replay','hypothesis':'no algorithm change; no presumed speedup','setup':add,'acceptance':'all six exact reference summary hashes and runtime provenance; no research gate promotion'})
put(D/'LAUNCH.json',{'root':str(R),'container':name,'command':args,'terminal':str(R/'TERMINAL.json'),'result':str(R/'RESULT.json'),'event_wait':'Docker wait event with 600 second controller fallback; agent does not poll stage state','cache':'bounded 16MiB requests warmup, no flush, unmeasured record residency','git_scope':'private review artifacts only; no root/consumer/service/training edits'})
x=subprocess.run(['ssh','npu',shlex.join(args)],capture_output=True,text=True,timeout=40);x.check_returncode();print(x.stdout.strip())
