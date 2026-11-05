"""Host controller: each stage is an independent retained Docker container."""
import hashlib,json,os,subprocess,time
from pathlib import Path
R=Path('/mnt/cephfs/xingchao/experiments/jev/engineering_training_shell_fixture_20261105_v7')
IMAGE=(R/'image-id').read_text().strip(); PROD='sha256:a2b20ba160230b3e8c538ce588e256bec55cdb4b4e5e5a294e70ba9107dca6d9'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def config(out,stop,resume=None):
    c={'schema':'nga-unified-config-v1','adapter':'k1-family-train-v2','output':f'/work/{out}','recipe_id':'k1-base-0.8b-3116-v2','owner':'cpu-fixture','seed':2,'model':{'id':'Qwen3.5-0.8B-Base','path':'/fixture-model','manifest':'/opt/nga/components/training/family-assets-v2/model-0.8B.json','manifest_sha256':'042f1303b1542254e0a7696bbf95938e7bc947de556e7937448f94611507ce7f'},'dataset':{'id':'decision-v7-train','path':'/fixture-data','manifest':'/opt/nga/components/training/family-assets-v2/dataset.json','manifest_sha256':'2d71ef2dee50883d6e42c4b3a2e8217c8c0e69aea41d447071fe945881431831'},'resume':None,'engineering_stop_after':stop}
    if resume: c['resume']={'path':f'/work/{out}/ckpt/{resume}','sha256':sha(R/out/'ckpt'/resume)}
    return c
def stage(name,image,command,expected=0):
    terminal=R/f'{name}.terminal'
    if terminal.exists():
        assert int(terminal.read_text())==expected
        return
    cname=f'nga-shell-v7-r5-{name}'
    shell='(while :; do date -u "+%FT%TZ heartbeat '+name+'=running" >> /work/'+name+'.heartbeat; sleep 15; done) & b=$!; '+command+' > /work/'+name+'.log 2>&1; rc=$?; kill "$b"; echo "$rc" > /work/'+name+'.terminal.tmp; mv /work/'+name+'.terminal.tmp /work/'+name+'.terminal; exit "$rc"'
    cmd=['docker','run','-d','--name',cname,'--runtime','runc','--network','none','-e','TORCH_DEVICE_BACKEND_AUTOLOAD=0','-e','OMP_NUM_THREADS=1','-e','MKL_NUM_THREADS=1','-e',f'NGA_QUAL_ATTEMPT={name}','--mount',f'type=bind,src={R},dst=/work','--entrypoint','/bin/sh',image,'-c',shell]
    exists=subprocess.run(['docker','inspect',cname],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not exists: subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
    while not terminal.exists():
        state=subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',cname],text=True).strip()
        if state=='false': raise RuntimeError(f'{name}: container stopped without terminal marker')
        time.sleep(2)
    rc=int(terminal.read_text()); print(name,'terminal',rc,flush=True)
    if rc!=expected: raise RuntimeError(f'{name}: expected {expected} got {rc}')
def run(name,out,stop,resume=None):
    p=R/f'{name}.json'
    if not p.exists(): p.write_text(json.dumps(config(out,stop,resume),sort_keys=True)+'\n')
    stage(name,IMAGE,f'/opt/nga/entrypoint.sh /work/{name}.json')
for x in ('a','b'): (R/x).mkdir(exist_ok=True)
# The original image must reject the missing synthetic model; caller PYTHONPATH cannot inject.
p=R/'negative.json'
if not p.exists(): p.write_text(json.dumps(config('negative',1))+'\n')
(R/'negative').mkdir(exist_ok=True)
stage('original-negative',PROD,'PYTHONPATH=/work/hostile /opt/nga/entrypoint.sh /work/negative.json',1)
run('a-six','a',6); run('b-three','b',3); run('b-resume','b',3,'step_000003.pt')
for x in ('a','b'):
    stage(x+'-advance',IMAGE,'python3 -P /work/utility.py advance '+x)
    run(x+'-final',x,1,'step_003115.pt')
    run(x+'-retry',x,1,'step_003116.pt')
stage('verify',IMAGE,'python3 -P /work/utility.py verify')
stage('audit-production',PROD,'python3 -S -P /work/audit.py production')
stage('audit-derivative',IMAGE,'python3 -S -P /work/audit.py derivative')
x=json.loads((R/'audit-production.json').read_text()); y=json.loads((R/'audit-derivative.json').read_text())
assert x['tree']==y['tree'] and x['manifest_sha256']==y['manifest_sha256'] and x['manifest_files']==y['manifest_files']==55
assert x['fixture']['nga_qualification_fixture.py'] is None and y['fixture']['nga_qualification_fixture.py'] is not None
(R/'audit-result.json').write_text(json.dumps({'production_tree_equal':True,'manifest_equal':True,'manifest_count':55,'production_fixture_absent':True,'derivative_fixture_present':True},indent=2)+'\n')
(R/'hostile').mkdir(exist_ok=True)
(R/'hostile/sitecustomize.py').write_text("open('/work/HOSTILE-EXECUTED','w').write('bad')\n")
(R/'negative2').mkdir(exist_ok=True)
p=R/'negative2.json'
if not p.exists(): p.write_text(json.dumps(config('negative2',1))+'\n')
stage('original-negative2',PROD,'PYTHONPATH=/work/hostile /opt/nga/entrypoint.sh /work/negative2.json',1)
assert not (R/'HOSTILE-EXECUTED').exists()
print('qualification complete',flush=True)
