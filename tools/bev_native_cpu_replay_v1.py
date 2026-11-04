"""Versioned read-only saved-panel CPU replay with invocation-local reference reuse.

Does not modify original consumer identity or authorize inference/scientific claims.
Source snapshots are checked before/after initialization and phase boundaries;
mutation during a phase is rejected before a successful terminal is published.
"""
import argparse, hashlib, json, os, threading, time, traceback, types
from pathlib import Path
from dataclasses import dataclass


def require(ok, why):
    if not ok: raise ValueError(why)

def sha(path):
    p=Path(path)
    require(p.is_absolute() and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def read(path): return json.loads(Path(path).read_bytes())
def canonical_directory(value):
    path=Path(value)
    require(path.is_absolute() and '..' not in path.parts, 'noncanonical directory')
    require(not any(x.is_symlink() for x in (path,*path.parents)), 'unsafe directory symlink')
    resolved=path.resolve(strict=False)
    require(path==resolved, 'noncanonical directory')
    return resolved
def exact(a,b): return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def load(ref):
    raw=Path(ref['path']).read_bytes()
    require(sha(ref['path'])==ref['sha256']==hashlib.sha256(raw).hexdigest(),'module changed')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path']
    exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

def put(path,obj):
    p=Path(path);tmp=p.with_name(p.name+'.pending')
    with tmp.open('w') as f:
        json.dump(obj,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

@dataclass(frozen=True)
class VerifiedReference:
    native: object
    native_path: str
    native_sha256: str
    source_root: str
    source_pins: tuple
    value: object
    restricted_logprobs: object
    result: object

    @classmethod
    def create(cls,N,native_ref,upstream):
        require(native_ref['path']==N.__file__ and sha(N.__file__)==native_ref['sha256'],'native source differs')
        root=Path(upstream['root'])
        require(set(upstream['files'])==set(N.PINS),'upstream inventory differs')
        pins=[]
        for name,pin in N.PINS.items():
            source=str(root/'anyjev'/name)
            require(upstream['files'][name]=={'path':source,'sha256':pin} and sha(source)==pin,'upstream source differs')
            pins.append((source,pin))
        value=N.reference(root)
        result=cls(N,N.__file__,native_ref['sha256'],str(root),tuple(pins),value,value.restricted_logprobs,value.Tacit._result)
        result.check_sources();return result

    def check_sources(self):
        require(sha(self.native_path)==self.native_sha256,'native source changed')
        for p,pin in self.source_pins: require(sha(p)==pin,'upstream source changed')
        self.for_native(self.native)

    def for_native(self,N):
        require(self.native is N and N.__file__==self.native_path,'foreign native/reference')
        require(self.value.restricted_logprobs is self.restricted_logprobs and self.value.Tacit._result is self.result,'reference mutated')
        return self.value

class Progress:
    def __init__(self,out):
        self.out=Path(out);self.started=time.monotonic();self.phase_started=self.started
        self.phase='verify_inventory';self.completed=0;self.total=0;self.timings={};self.lock=threading.RLock()
    def stage(self,phase,total=0):
        with self.lock:
            now=time.monotonic();self.timings[self.phase]=self.timings.get(self.phase,0)+now-self.phase_started
            self.phase=phase;self.phase_started=now;self.completed=0;self.total=total;self.emit()
    def emit(self):
        with self.lock:
            elapsed=time.monotonic()-self.phase_started
            v=dict(phase=self.phase,completed=self.completed,total=self.total,phase_seconds=elapsed,elapsed_seconds=time.monotonic()-self.started,phase_timings=self.timings,items_per_second=self.completed/max(elapsed,1e-9),utc_seconds=time.time(),scientific_acceptance=False)
            put(self.out/'heartbeat.json',v)
            print(json.dumps(v,sort_keys=True),flush=True)
    def tick(self,count):
        with self.lock: self.completed=count
        if count%1000==0 or count==self.total: self.emit()

def validate_prediction(pred,item,d,N,ref):
    require(type(ref) is VerifiedReference, "verified invocation reference required")
    reference=ref.for_native(N)
    import numpy as np
    require(all(type(pred.get(k)) is int for k in ('i','index','first_index','reasoning_tokens')),'integer alias')
    require(pred.get('label_ids')==item['label_ids'] and all(type(x) is int for x in pred['label_ids']),'label ids differ')
    vals=pred.get('label_values');require(type(vals) is list and len(vals)==len(item['label_ids']) and all(type(x) in (int,float) and np.isfinite(x) for x in vals),'invalid restricted operands')
    # Reconstruction uses only compact selected operands; production checked full-vector finiteness.
    z=np.zeros(248320,dtype=np.float32);z[item['label_ids']]=vals
    expected=N.read_logits(item,z,mode='transformers_full_labels',contract_sha256=d['contract_sha256'],prepared_sha256=N.digest(item),ref=reference)
    require(exact(pred,expected),'compact prediction arithmetic or identity differs')
    require(type(pred['first_margin']) in (int,float) and np.isfinite(pred['first_margin']) and pred['first_margin']>=0,'strict margin differs')
    return pred

def load_item(dest,item,d,N,ref):
    require(dest.is_dir() and not dest.is_symlink(),'item missing');receipt=read(dest/'COMMITTED.json')
    require(set(receipt)=={'record.json'} and receipt['record.json']==sha(dest/'record.json'),'partial/changed record')
    r=read(dest/'record.json');require(set(r)=={'schema','model_sha256','contract_sha256','prediction','forwards'} and r['schema']=='bev-native-compact-v1' and type(r['forwards']) is int and r['forwards']==1,'record shape differs')
    require(r['model_sha256']==d['model_sha256'] and r['contract_sha256']==d['contract_sha256'],'record generation differs')
    return validate_prediction(r['prediction'],item,d,N,ref)

def lifecycle(C,d,pin,attempt):
    root=Path(d['out']);a=root/'attempts'/str(attempt);h=root/'host_attempts'/str(attempt)
    terminal=C.read(a/'EXIT.json');host=C.read(h/'EXIT.json');receipt=C.read(h/'LAUNCH_RECEIPT.json');claim=C.read(h/'CLAIM.json');release=C.read(h/'RELEASE.json');spec=C.read(h/'LAUNCH_SPEC.json')
    integer=lambda value,wanted:type(value) is int and value==wanted
    C.require(integer(terminal.get('exit_code'),0) and integer(terminal.get('attempt'),attempt) and terminal.get('plan_sha256')==pin and terminal.get('test_read') is True and terminal.get('scientific_acceptance') is False,'runtime terminal differs')
    C.require(integer(host.get('exit_code'),0) and integer(host.get('container_exit_code'),0) and host.get('runner_terminal_matches') is True and host.get('plan_sha256')==pin and integer(host.get('attempt'),attempt) and host.get('scientific_acceptance') is False,'host terminal differs')
    C.require(receipt.get('plan_sha256')==pin and integer(receipt.get('attempt'),attempt) and receipt.get('container_id')==host.get('container_id')==release.get('container_id'),'container lineage differs')
    C.require(claim.get('schema')=='r3-resource-claim-v1' and release.get('schema')=='r3-resource-release-v1' and claim.get('run')==release.get('run')==d['run'] and integer(claim.get('chip'),d['chip']) and integer(release.get('chip'),d['chip']) and release.get('claim_sha256')==C.sha(h/'CLAIM.json'),'resource lineage differs')
    C.require(integer(release.get('exit_code'),0) and release.get('scientific_acceptance') is False and release.get('container')==d['container']+'-a'+str(attempt),'release differs')
    H=C.module(d['modules']['host']);view={**d,'runtime':d['modules']['runtime'],'image_sha256':d['image']};path=Path(d['out']).parent/'PLAN.json'
    C.require(spec.get('plan_sha256')==pin and spec.get('command')==H.command(view,str(path),pin,attempt),'command differs')
    C.require(receipt.get('command')==spec['command'][spec['command'].index(d['image'])+1:],'runtime command differs')
    report=C.read(a/'report.json')
    C.require(report.get('schema')=='bev-native-panel-completion-v1' and integer(report.get('attempt'),attempt) and report.get('plan_sha256')==pin and report.get('scientific_acceptance') is False,'completion identity differs')
    C.require(report.get('model_sha256')==d['model_sha256'] and report.get('contract_sha256')==d['population']['contract_sha256'] and report.get('ordered_inputs_sha256')==d['population']['ordered_inputs_sha256'],'completion protocol differs')
    C.require(report.get('adaptive')=='NOT_EVALUATED' and integer(report.get('forwards_per_new_item'),1),'completion readout scope differs')
    return report

def consume(C,path,pin,attempt,progress):
    d=C.verify(path,pin,cpu=True);view,L,N=C.plan_legacy_view(d);X=C.module(d['modules']['panel']);P=C.module(d['modules']['protocol'])
    # Frozen plan verifies its original consumer; this replay has its own pinned config.
    ref=VerifiedReference.create(N,d['modules']['native'],d['upstream'])
    pop=d['population'];items=X.rows(pop['items']['path']);gold=X.rows(pop['gold']['path']);requests=X.rows(pop['requests']['path']);contract=C.read(pop['contract']['path'])
    P.validate_items(items);C.require(len(items)==len(gold)==len(requests)==pop['count'],'population incomplete')
    expected=P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=d['model_sha256'],runtime_protocol_sha256=view['protocol_binding_sha256'])
    C.require(contract==expected and P.sha256_value(contract)==pop['contract_sha256'],'contract differs')
    ref.check_sources();progress.stage('imports',d['recovery']['imported_count'])
    completion=lifecycle(C,d,pin,attempt)
    count=C.check_imports(d);progress.tick(count)
    C.require(completion.get('imported_manifest_sha256')==d['recovery']['manifest']['sha256'] and completion.get('source_plan_sha256')==d['recovery']['source_plan']['sha256'],'completion source provenance differs')
    C.require(completion['reused']==count and completion['computed']==d['population']['count']-count,'completion import counts differ')
    ref.check_sources();progress.stage('records',len(items))
    root=Path(d['out']);pred=[];receipts=[]
    C.require({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(len(items))},'output population differs')
    for i,(item,req,g) in enumerate(zip(items,requests,gold)):
        X.item_check(req,i,8192);C.require(req['request_sha256']==P.request_hash(item),'input source join differs')
        C.require(g==dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)),'gold join differs')
        dest=root/'items'/f'{i:06d}';p=load_item(dest,req,view,N,ref)
        C.require(type(p.get('i')) is int and p['i']==i and p['qid']==item['qid'] and p['request_sha256']==req['request_sha256'] and p['input_sha256']==N.digest(req) and 'gold' not in p and 'y' not in p,'prediction join differs')
        pred.append(dict(p,y=item['y']));receipts.append(C.sha(dest/'COMMITTED.json'));progress.tick(i+1)
    C.require(type(completion.get('completed')) is int and completion['completed']==len(items) and completion.get('receipts_sha256')==N.digest(receipts) and completion.get('contract_sha256')==pop['contract_sha256'] and completion.get('ordered_inputs_sha256')==pop['ordered_inputs_sha256'] and completion.get('model_sha256')==d['model_sha256'],'completion binding differs')
    C.require(all(type(completion.get(k)) is int and completion[k]>=0 for k in ('computed','reused')) and completion['computed']+completion['reused']==len(items) and type(completion.get('forwards_per_new_item')) is int and completion['forwards_per_new_item']==1,'completion counts differ')
    ref.check_sources();progress.stage('summary',len(items))
    progress.receipts_sha256=N.digest(receipts)
    raw=P.summarise(items,pred,contract=contract,contract_sha256=pop['contract_sha256']);kinds={}
    for kind in ('choice','yes_no','score'):
        selected=[(i,p) for i,p in zip(items,pred) if i['kind']==kind];correct=sum(i['y']==p['first_index'] for i,p in selected)
        kinds[kind]=dict(n=len(selected),correct=correct,accuracy=correct/len(selected) if selected else None,metric_origin='NGA additive stratification')
    return dict(schema='native-config-panel-summary-v2',n=len(items),one_forward=dict(**raw['one_forward'],accuracy=raw['one_forward']['correct']/len(items)),by_type=kinds,adaptive='NOT_EVALUATED',scientific_acceptance=False,candidate_test_authority=False,plan_sha256=pin,attempt=attempt,scope=d['scope'],model=C.read(d['config']['path'])['model']['name']+' fixed checkpoint',engine='Transformers full-label fp32 b1 HF32 off')


def worker(config_path,config_pin):
    whole_started=time.monotonic()
    require(sha(config_path)==config_pin,'replay config changed')
    cfg=read(config_path)
    require(cfg['schema']=='native-saved-cpu-replay-v1' and cfg['read_only_saved_records'] is True,'replay scope differs')
    require(cfg['consumer']=={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)},'replay consumer differs')
    require(sha(cfg['plan']['path'])==cfg['plan']['sha256'],'source plan changed')
    original=read(cfg['plan']['path']);out=canonical_directory(cfg['output'])
    production=canonical_directory(original['out'])
    require(not out.is_relative_to(production) and not production.is_relative_to(out),'output overlaps production')
    require(out.is_dir() and not (out/'EXIT.json').exists() and not (out/'summary.json').exists(),'output exists or unprepared')
    progress=Progress(out);stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):progress.emit()
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        progress.emit();C=load(original['modules']['runtime'])
        summary=consume(C,cfg['plan']['path'],cfg['plan']['sha256'],cfg['attempt'],progress)
        expected=cfg['expected_summary'];require(sha(expected['path'])==expected['sha256'],'expected summary changed')
        require(summary==read(expected['path']),'full summary parity failed')
        put(out/'summary.json',summary)
        require(sha(out/'summary.json')==expected['sha256'],'serialized summary parity failed')
        terminal=read(cfg['expected_terminal']['path'])
        require(sha(cfg['expected_terminal']['path'])==cfg['expected_terminal']['sha256'] and terminal['exit_code']==0 and terminal['plan_sha256']==cfg['plan']['sha256'] and terminal['summary_sha256']==expected['sha256'] and terminal['attempt']==cfg['attempt'],'production terminal differs')
        # Check all pinned input/source files again before publishing success.
        for path,pin in original['files'].items():require(sha(path)==pin,'source changed during replay')
        require(sha(cfg['plan']['path'])==cfg['plan']['sha256'],'plan changed during replay')
        progress.tick(summary['n']);progress.stage('complete')
        put(out/'PARITY.json',dict(status='PASS',records=summary['n'],summary_sha256=sha(out/'summary.json'),receipts_sha256=progress.receipts_sha256,whole_process_seconds=time.monotonic()-whole_started,phase_timings=progress.timings,reference_initializations=1,scientific_acceptance=False,test_inference_rerun=False,production_modified=False))
        rc=0
    except BaseException as e:
        put(out/'ERROR.json',dict(error=str(e),phase=progress.phase,completed=progress.completed,traceback=traceback.format_exc()));traceback.print_exc()
    finally:
        stop.set();thread.join(2)
        put(out/'EXIT.json',dict(exit_code=rc,config_sha256=config_pin,plan_sha256=cfg['plan']['sha256'],summary_sha256=sha(out/'summary.json') if rc==0 else None,utc_seconds=time.time(),elapsed_seconds=time.monotonic()-whole_started,scientific_acceptance=False))
    return rc

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    raise SystemExit(worker(a.config,a.sha256))
