"""Configured matched native DEV performance execution; fresh timing only."""
import argparse,fcntl,hashlib,json,os,threading,time,traceback,types
from pathlib import Path

def need(v,why):
    if not v:raise ValueError(why)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def module(ref):
    raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'source changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in [p,*p.parents]),'unsafe path');return p
def put(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
    with tmp.open('w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p);fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def mounts(d,path):
    refs=[{'source':d['model'],'destination':d['model'],'readonly':True}]
    refs += [{'source':p,'destination':p,'readonly':True} for p in sorted(d['files']) if p not in d['cpu_only'] and not Path(p).is_relative_to(d['model'])]
    refs += [{'source':str(path),'destination':str(path),'readonly':True},{'source':d['out'],'destination':d['out'],'readonly':False}]
    refs += [{'source':p,'destination':p,'readonly':True} for p in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']]
    return refs

def verify(path,pin,host=False,model_files=True):
    need(sha(path)==pin,'plan changed');d=read(path)
    need(d['schema']=='native-matched-dev6516-execution-v1' and d['scope']=='native_reference_adapter_collect' and d['test_read']is False and d['scientific_acceptance']is False,'scope')
    need(d['modules']['runtime']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'runtime binding')
    need(d['max_length']==4096 and d['poll_seconds']==600 and d['chips']==1 and d['host_name']=='k8s-node1','limits')
    need(d['run']=='r3_runs/'+d['experiment_id']+'/'+Path(d['out']).parent.name and Path(d['out']).name=='output','output identity')
    need(d['container']=='nga-matched-'+d['experiment_id'].replace('_','-'),'container identity')
    safe(d['out']);safe(d['model'])
    for p,h in d['files'].items():
        if host or p not in d['cpu_only']:need(sha(safe(p))==h,'dependency changed: '+p)
    for ref in [*d['modules'].values(),d['inputs'],d['population'],d['queue']]:need(d['files'].get(ref['path'])==ref['sha256'],'unbound reference')
    L=module(d['modules']['loader']);need(d['environment']==L.ENV and d['image']==L.IMAGE,'loader environment differs')
    if model_files:
        actual={str(p):sha(p) for p in Path(d['model']).rglob('*') if p.is_file()};need(actual==d['model_files'],'model manifest differs')
    N=module(d['modules']['native']);M=module(d['modules']['protocol']);pop=read(d['population']['path']);rows=[read_line for read_line in map(json.loads,Path(d['inputs']['path']).read_text().splitlines())]
    need(len(rows)==6516 and N.digest(rows)==pop['ordered_inputs_sha256'],'population differs')
    need([N.digest(x) for x in rows]==pop['ordered_input_sha256'],'ordered input binding')
    need(pop['native_requests']==d['inputs'] and pop['test_read']is False and pop['npu_used']is False,'population provenance')
    need(all(x['i']==i and len(x['input_ids'])<=4096 for i,x in enumerate(rows)),'order/truncation')
    for name,h in N.PINS.items():need(d['files'].get(str(Path(d['upstream_root'])/'anyjev'/name))==h,'upstream binding')
    contract={'model_files':d['model_files'],'population':d['population'],'inputs':d['inputs'],'native':d['modules']['native'],'loader':d['modules']['loader'],'probe':d['modules']['probe'],'reference_runtime':d['modules']['reference_runtime'],'precision':{'dtype':'float32','hf32':False,'batch_size':1,'padding_side':'left','max_length':4096},'schedule':M.schedule(6516)}
    need(N.digest(contract)==d['contract_sha256'],'contract differs');need(d['mounts']==mounts(d,path),'mount projection')
    need(d['cpu_only']==[d['modules']['consumer']['path']],'CPU exclusion')
    need(all(not Path(x).is_relative_to(m['source']) for x in d['cpu_only'] for m in d['mounts']),'consumer mounted')
    return d,rows

def run(path,pin,attempt):
    need(type(attempt)is int and attempt==1,'fresh complete experiment only');d=read(path);root=safe(d['out']);root.mkdir(parents=True,exist_ok=True)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);a=root/'attempts/1';a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
        def beat():
            while not stop.wait(30):put(a/'heartbeat.json',{'utc_seconds':time.time(),'state':'runtime_alive','attempt':1})
        worker=threading.Thread(target=beat,daemon=True);worker.start()
        try:
            d,rows=verify(path,pin);M=module(d['modules']['protocol']);B=module(d['modules']['backend']);backend=[]
            def load():
                b=B.Backend(d);backend.append(b);return b
            report=M.execute_fresh(root/'measurement',{'path':str(path),'sha256':pin},rows,load)
            # Driver duration is explicitly narrower than claim-to-release occupation.
            report['driver_seconds']=report.pop('whole_occupied_seconds');report['driver_chip_hours']=report.pop('whole_occupied_chip_hours');report['resource_occupied_seconds']=None
            report.update(backend[0].lifetime_memory());report.update(plan_sha256=pin,attempt=1,performance_accepted=False)
            put(a/'report.json',report);rc=0
        except BaseException:traceback.print_exc();raise
        finally:stop.set();worker.join(2);put(a/'EXIT.json',{'exit_code':rc,'plan_sha256':pin,'attempt':1,'scientific_acceptance':False,'test_read':False,'utc_seconds':time.time()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('op',choices=['run','verify']);p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256,host=True);print('MATCHED_CONFIG_VERIFIED')
    else:run(a.plan,a.sha256,a.attempt)
