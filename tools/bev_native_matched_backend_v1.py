"""Actual native matched-DEV collection and committed operand comparison.

No host or resource authority. Numerical calls reuse pinned DEV72 collect and
operand persistence; caller supplies an independently reviewed plan.
"""
import hashlib,json,os,time,types
from pathlib import Path

def need(v,why):
    if not v:raise ValueError(why)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(ref):
    raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'module changed')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def read(p):return json.loads(Path(p).read_bytes())
def atomic(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
    with tmp.open('w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def pin(p):return {'path':str(p),'sha256':sha(p)}

class Backend:
    def __init__(self,plan):
        self.plan=plan;self.mods={k:module(plan['modules'][k]) for k in ('loader','native','probe','reference_runtime')}
        L,N,P=[self.mods[k] for k in ('loader','native','probe')]
        self.model,self.tok,self.torch,self.T,self.TN=L.load_model({'model':plan['model']})
        self.ref=N.reference(Path(plan['upstream_root']));self.engine=P.upstream_engine(str(Path(plan['upstream_root'])/'anyjev/tacit.py'),N.PINS['tacit.py'],self.ref)
        self.load_peak_reserved=self.torch.npu.max_memory_reserved();self.load_peak_allocated=self.torch.npu.max_memory_allocated();self.lifetime_reserved=self.load_peak_reserved;self.lifetime_allocated=self.load_peak_allocated;self.started=time.monotonic();self.completed=0
    def synchronize(self):self.torch.npu.synchronize()
    def collect(self,arm,item):
        need(arm in ('reference','adapter_sequential'),'unknown arm')
        variant='reference' if arm=='reference' else 'adapter'
        with self.torch.inference_mode():return self.mods['reference_runtime'].collect(self.model,self.tok,item,variant,self.mods['loader'],self.mods['native'],self.mods['probe'],self.ref,self.engine,self.plan['contract_sha256'],self.plan['max_length'])
    def persist(self,target,item,arrays,result):
        target=Path(target);need(not target.exists(),'operand already exists');self.mods['probe'].persist_operand(target,arrays,result)
        return {'directory':str(target),'commit':pin(target/'COMMITTED.json')}
    def memory(self):
        reserved=self.torch.npu.max_memory_reserved();allocated=self.torch.npu.max_memory_allocated();self.lifetime_reserved=max(self.lifetime_reserved,reserved);self.lifetime_allocated=max(self.lifetime_allocated,allocated)
        return {'peak_reserved_bytes':reserved,'peak_allocated_bytes':allocated}
    def reset_peak(self):self.memory();self.torch.npu.reset_peak_memory_stats()
    def progress(self,done,compute,tokens):
        self.completed+=1
        if done%100==0 or done==6516:
            m=self.memory();atomic(Path(self.plan['out'])/'heartbeat.json',{'utc_seconds':time.time(),'stage':'matched_trial','trial_done':done,'trial_total':6516,'measured_forwards_completed':self.completed,'measured_forwards_total':26064,'items_per_second_per_chip':done/max(compute,1e-9),'tokens_per_second_per_chip':tokens/max(compute,1e-9),'chips':1,'reserved_gib':m['peak_reserved_bytes']/2**30})
    def lifetime_memory(self):
        self.memory();return {'process_peak_reserved_bytes':self.lifetime_reserved,'process_peak_allocated_bytes':self.lifetime_allocated,'model_load_peak_reserved_bytes':self.load_peak_reserved,'model_load_peak_allocated_bytes':self.load_peak_allocated}

def check_operand(path,expected,item,plan):
    """Independently reads actual saved tensors; no supplied PASS dictionary."""
    import numpy as np
    root=Path(path);need(root.is_dir() and not any(p.is_symlink() for p in [root,*root.parents]),'unsafe operand')
    receipt=read(root/'COMMITTED.json');need(set(receipt)=={'operands.npz','result.json'},'commit fields')
    for n,h in receipt.items():need(sha(root/n)==h,'changed operand')
    result=read(root/'result.json');need(result['variant']==expected and result['forwards']==1,'variant/forward differs')
    pred=result['prediction'];need(pred['contract_sha256']==plan['contract_sha256'] and pred['input_sha256']==plan['protocol_module'].digest(item),'operand identity')
    with np.load(root/'operands.npz',allow_pickle=False) as z:a={k:z[k] for k in z.files}
    plan['protocol_module'].full(a,result,item)
    N=plan['native_module'];expected_pred=N.read_logits(item,a['logits'][0],mode='transformers_full_labels',contract_sha256=plan['contract_sha256'],prepared_sha256=N.digest(item),ref=plan['reference'])
    need(result['prediction']==expected_pred and result['restricted_logprobs']==expected_pred['restricted_logprobs'],'stored prediction not derived from logits')
    return a,result

def compare_all(plan,rows):
    """Four actual timing populations compared with first reference, plus warmups."""
    import numpy as np
    M=module(plan['modules']['protocol']);N=module(plan['modules']['native']);context=dict(plan,protocol_module=M,native_module=N,reference=N.reference(Path(plan['upstream_root'])))
    root=Path(plan['out'])/'measurement';comparisons=0;operands=0;files={}
    trials=[]
    for t in M.schedule(len(rows)):
        d=root/'trials'/str(t['trial']);report=read(d/'report.json');need(report['trial']==t['trial'],'trial differs');trials.append(report)
    for i,item in enumerate(rows):
        first=None
        for t in M.schedule(len(rows)):
            path=root/'trials'/str(t['trial'])/'items'/str(i);variant='reference' if t['arm']=='reference' else 'adapter';a,r=check_operand(path,variant,item,context);operands+=1
            obs=trials[t['trial']]['observations'][i];need(obs['persisted']=={'directory':str(path),'commit':pin(path/'COMMITTED.json')},'timing operand binding')
            if first is None:first=a
            else:
                need(all(np.array_equal(first[k],a[k]) for k in ('input_ids','attention_mask','logits')),'full operand mismatch');comparisons+=1
        if (i+1)%100==0:atomic(Path(plan['out'])/'cpu/heartbeat.json',{'utc_seconds':time.time(),'state':'comparing_full_operands','items':i+1,'total':len(rows)})
    for arm in ('reference','adapter_sequential'):
        for i in M.warmup_indices(rows):check_operand(root/'warmup'/arm/str(i),'reference' if arm=='reference' else 'adapter',rows[i],context);operands+=1
    pop=read(plan['population']['path']);eq={'verdict':'PASS','population_sha256':pop['ordered_inputs_sha256'],'full_operand_comparisons':comparisons,'zero_tolerance':True}
    summary=M.summarize(trials,pop,eq)
    return {'summary':summary,'full_operand_comparisons':comparisons,'operands_checked':operands,'independent_external_review_required':True,'scientific_acceptance':False,'test_read':False}
