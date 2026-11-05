"""New-run recovery of a fixed public panel, preserving original numerical identity.

Imports are byte copies with pinned provenance, never fabricated runtime terminals.
The original loader, native readout, item executor and CPU scorer stay unchanged.
"""
import argparse,fcntl,hashlib,json,os,threading,time,traceback,types
from pathlib import Path

BASE_SHA='9cd0278b28b9aedc09c33e1902a3e6b52f246869646a8016c0a83d69ae4d88bd'
def need(ok,why):
    if not ok:raise ValueError(why)
def load(ref):
    raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'module changed')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
_base=Path(__file__).with_name('bev_native_config_panel.py')
C=load({'path':str(_base),'sha256':BASE_SHA})
read=C.read;sha=C.sha;put=C.put;module=C.module;require=C.require;safe=C.safe;digest=C.digest

def source(d,cpu=False,model_files=True):
    r=d['recovery'];need(set(r)=={'source_plan','manifest','validation','validation_exit','release','host_exit','claim','receipt','reconciliation_review','source_attempt','imported_count'},'recovery fields differ')
    need(type(r['source_attempt'])is int and r['source_attempt']==1 and type(r['imported_count'])is int and r['imported_count']>0,'source attempt/count differs')
    for k,v in r.items():
        if type(v)is dict:need(set(v)=={'path','sha256'} and d['files'].get(v['path'])==v['sha256'] and sha(v['path'])==v['sha256'],'unbound recovery source')
    old=read(r['source_plan']['path']);original=module(old['modules']['runtime']);old=original.verify(r['source_plan']['path'],r['source_plan']['sha256'],model_files=model_files,cpu=cpu)
    need(old['scope']=='public_fixed_base_test' and old['candidate_test_authority']is False,'source scope differs')
    val=read(r['validation']['path']);end=read(r['validation_exit']['path'])
    need(val['plan_sha256']==r['source_plan']['sha256'] and val['validated']==r['imported_count'] and val['record_generation_and_selected_arithmetic_exact']is True and val['gold_read']is False and val['resume_authorized']is False,'partial validation differs')
    need(type(end['exit_code'])is int and end['exit_code']==0 and end['scientific_acceptance']is False,'partial validation failed')
    rel=read(r['release']['path']);host=read(r['host_exit']['path']);claim=read(r['claim']['path']);receipt=read(r['receipt']['path']);review=read(r['reconciliation_review']['path'])
    h=Path(old['out'])/'host_attempts/1'
    for key,name in [('release','RELEASE.json'),('host_exit','EXIT.json'),('claim','CLAIM.json'),('receipt','LAUNCH_RECEIPT.json')]:need(r[key]['path']==str(h/name),'source lifecycle path differs')
    need(type(rel['exit_code'])is int and rel['exit_code']==1 and host['exit_code']==1 and host['container_exit_code']==1,'source not failed')
    need(host['source']=='retained-container-exit' and host['runtime_terminal_present']is False and host['runner_terminal_matches']is False and host['plan_sha256']==r['source_plan']['sha256'],'failure provenance differs')
    need(host['release_sha256']==r['release']['sha256'] and rel['claim_sha256']==r['claim']['sha256'],'failure release binding differs')
    need(all(x.get('scientific_acceptance',False)is False for x in (rel,host,claim,receipt)),'source scientific scope differs')
    need(rel['container_id']==host['container_id']==receipt['container_id'] and receipt['plan_sha256']==r['source_plan']['sha256'] and receipt['attempt']==1,'source receipt differs')
    need(rel['run']==claim['run']==old['run'] and rel['chip']==claim['chip']==old['chip'],'source resource identity differs')
    need(review['verdict']=='PASS' and review['release_authorized']is True and review['scientific_acceptance']is False and host['reconciliation_review']['sha256']==r['reconciliation_review']['sha256'],'source reconciliation review differs')
    return old

def mounts(d,path):
    # Original source protocol is verified, but old output is not mounted.
    excluded={d['population'][k]['path'] for k in ('items','gold','source','contract')}
    refs=[dict(source=d['model'],destination=d['model'],readonly=True)]
    refs += [dict(source=p,destination=p,readonly=True) for p in sorted(d['files']) if p not in excluded and not Path(p).is_relative_to(d['model'])]
    refs += [dict(source=str(path),destination=str(path),readonly=True),dict(source=d['out'],destination=d['out'],readonly=False)]
    refs += [dict(source=p,destination=p,readonly=True) for p in ('/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info')]
    need(all(not Path(p).is_relative_to(Path(m['source'])) for p in excluded for m in refs),'gold/source mounted')
    return refs

def verify(path,pin,model_files=True,cpu=False):
    need(sha(path)==pin,'plan changed');d=read(path)
    need(d['schema']=='native-panel-resume-execution-v1' and d['modules']['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'recovery runtime differs')
    old=source(d,cpu=cpu,model_files=model_files)
    unchanged=set(old)-{'schema','modules','files','queue','out','run','container','mounts'}
    need(set(d)==set(old)|{'recovery'},'plan shape differs')
    for k in unchanged:need(type(d[k])is type(old[k]) and d[k]==old[k],'numerical/source identity changed: '+k)
    for k in set(old['modules'])-{'runtime','resource','consumer'}:need(d['modules'][k]==old['modules'][k],'unregistered module replacement')
    need(d['modules']['runtime']['path']!=old['modules']['runtime']['path'] and d['out']!=old['out'],'new runtime/output required')
    need(d['run']=='r3_runs/'+Path(d['out']).parent.name and Path(d['out']).name=='output' and Path(path)==Path(d['out']).parent/'PLAN.json','new output identity differs')
    need(not Path(d['out']).is_relative_to(old['out']) and not Path(old['out']).is_relative_to(d['out']),'output overlaps source')
    need(d['container']!=old['container'] and d['container'].startswith('nga-native-panel-'),'new container identity required')
    need(all(d['files'].get(p)==h for p,h in old['files'].items()),'old closure not preserved')
    for ref in d['modules'].values():need(d['files'].get(ref['path'])==ref['sha256'],'unbound module')
    need(d['files'].get(d['queue']['path'])==d['queue']['sha256'],'unbound resource policy')
    excluded=set() if cpu else {d['population'][k]['path'] for k in ('items','gold','source','contract')}
    for p,h in d['files'].items():
        if p not in excluded:need(sha(p)==h,'recovery dependency changed')
    need(d['mounts']==mounts(d,path),'mount projection differs')
    return d

def plan_legacy_view(d):
    old=read(d['recovery']['source_plan']['path']);view,L,N=C.plan_legacy_view(old)
    return dict(view,out=d['out'],run=d['run'],container=d['container']),L,N

def check_imports(d):
    m=read(d['recovery']['manifest']['path']);r=d['recovery'];root=Path(d['out'])/'items'
    need(m['schema']=='native-panel-imported-commits-v1' and m['source_plan']==r['source_plan'] and m['source_out']==read(r['source_plan']['path'])['out'] and m['count']==r['imported_count'],'import provenance differs')
    need(len(m['items'])==m['count'] and [x['ordinal'] for x in m['items']]==list(range(m['count'])),'import ordinals differ')
    for item in m['items']:
        p=root/f"{item['ordinal']:06d}";need(set(item)=={'ordinal','record_sha256','commit_sha256'},'import entry differs')
        need(sha(p/'record.json')==item['record_sha256'] and sha(p/'COMMITTED.json')==item['commit_sha256'],'imported bytes changed')
        need(read(p/'COMMITTED.json')=={'record.json':item['record_sha256']},'import receipt changed')
    return m['count']

def admission(d,r,path,pin,attempt):
    need(type(attempt)is int and attempt==1,'recovery only fresh attempt1')
    old=read(d['recovery']['source_plan']['path'])
    # Original accepted long DEV and unchanged numeric components remain the gate.
    C.admission(old,dict(r,cpu_command=C.cpu_command(old,d['recovery']['source_plan']['path'],d['recovery']['source_plan']['sha256'],1)),d['recovery']['source_plan']['path'],d['recovery']['source_plan']['sha256'],1)
    need(r.get('cpu_command')==cpu_command(d,path,pin,attempt) and r.get('recovery_manifest_sha256')==d['recovery']['manifest']['sha256'],'recovery review differs')
    check_imports(d)

cpu_command=C.cpu_command
start_cpu=C.start_cpu

def run(path,pin,attempt):
    need(type(attempt)is int and attempt==1,'recovery only fresh attempt1');d=read(path);root=safe(d['out'])
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);a=root/'attempts'/str(attempt);a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
        def beat():
            while not stop.wait(30):put(a/'heartbeat.json',dict(state='runtime_alive',attempt=attempt,utc_seconds=time.time()))
        t=threading.Thread(target=beat,daemon=True);t.start()
        try:
            verify(path,pin);imported=check_imports(d);view,L,N=plan_legacy_view(d);X=module(d['modules']['panel']);items=X.rows(d['population']['requests']['path'])
            need(len(items)==46320 and N.digest(items)==d['population']['ordered_inputs_sha256'],'population differs')
            need({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(imported)},'unexpected preexisting new items')
            for i,item in enumerate(items):X.item_check(item,i,8192)
            model,tok,torch,T,TN=L.load_model({'model':d['model']});ref=N.reference(Path(d['upstream']['root']))
            def metadata():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,dtype='float32',hf32=False,torch=torch.__version__,torch_npu=TN.__version__,transformers=T.__version__)
            def collect(item):
                with torch.inference_mode():return N.read_model_batch(model,[item],tok,mode='transformers_full_labels',contract_sha256=view['contract_sha256'],prepared_pins=[N.digest(item)],max_length=8192,ref=ref)[0]
            result=X.execute(view,N,items,root,attempt,collect,metadata)
            need(result['reused']==imported and result['computed']==46320-imported,'recovery computed count differs')
            result.update(forwards_per_new_item=1,plan_sha256=pin,attempt=attempt,imported_manifest_sha256=d['recovery']['manifest']['sha256'],source_plan_sha256=d['recovery']['source_plan']['sha256'])
            put(a/'report.json',result);rc=0
        except BaseException:traceback.print_exc();raise
        finally:stop.set();t.join(2);put(a/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,scientific_acceptance=False,test_read=True,utc_seconds=time.time()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('op',choices=['verify','run']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('RECOVERY_VERIFIED')
    else:run(a.plan,a.sha256,a.attempt)
