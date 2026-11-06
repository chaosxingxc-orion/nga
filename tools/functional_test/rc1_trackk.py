#!/usr/bin/env python3
"""RC1 fixed-roster Track K producer. See HANDOFF for configuration and launch contract."""
import argparse, contextlib, fcntl, hashlib, importlib, json, math, os, re, subprocess, sys, time
from pathlib import Path

REPO=Path('/mnt/cephfs/xingchao/experiments/jev/rc1-host-stage-20261106-2600925')
CLOSURE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code')
sys.path[:0]=[str(CLOSURE),str(REPO/'tools')]
import core_r3 as C, testlock_r3 as TL, admissible_store_r3 as AS, selection_evidence_r3 as SE
import full_eval_r3 as FULL, r3_reference_metrics as RM

LANES=[f'q{s}-s{n}' for s in ('0p8b','2b','4b','9b') for n in (2,3)]
BASES=[f'q{s}-base' for s in ('0p8b','2b','4b','9b')]
SUITES=('decision-v7','transfer-v4')
PLAN=[('decision-v7','calibration'),('decision-v7','test'),('transfer-v4','test')]
GROUPS=[f'{s}/{p}/{k}' for s,p in PLAN for k in (('clean',) if p=='calibration' else ('clean','variants','question_only','empty_input'))]
DATA={('decision-v7','train','clean'):(15576,'5ddc8e94f3e0af1c8abdb887ed77c1e8813879efcc428edc6d4ea0bed537daf6'),('decision-v7','calibration','clean'):(1148,'c3eeeda72740fbde6fbcc28e1dff0928c98407242543d0bd8f0819497f502b69'),('decision-v7','test','clean'):(1200,'55e21d63b93550ff2e1c98b32c2be558af02bde31c0633f8448d8f38d23fe1b2'),('decision-v7','test','variants'):(240,'72a095a26d9ac0052bd7825b745475b551d343a78409202576570dbdd2f63d6e'),('transfer-v4','test','clean'):(656,'43de4b7d6efb2d4b6b78b670ba82b98fefa324076fdda1b0462f5902ac02f7fc'),('transfer-v4','test','variants'):(108,'228b9cfe82ded8495eac7aa1490b062b2ffedf4e0e737f4dacbec6b38aef5e8c')}
MANIFEST='c2e8cbc6e0c686be2cc730890928d803e3f4de1b9b745abbea90adb6f3903afd'
R0_NAMES=('prompt','common','metrics','split','thresholds','decision','scorer')
R0_DIR=Path(C.R0_CODE).resolve()

def required_sources():
    paths={str(p.resolve()) for p in CLOSURE.glob('*.py')} | {str(Path(__file__).resolve()),str(REPO/'tools/r3_reference_metrics.py'),str(REPO/'tools/r3_final_container.py')}
    for name in R0_NAMES:
        expected=(R0_DIR/(name+'.py')).resolve()
        module=importlib.import_module(name)
        require(Path(module.__file__).resolve()==expected,'R0 import location differs: '+name)
        paths.add(str(expected))
    return paths

PROTOCOL='7c464d587f746b18237ee14c7ab46dea8e950f0ed7406552ff6b62cb29a85739'

def require(x,msg):
    if not x: raise ValueError(msg)
def sha(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def pinfile(x):
    require(set(x)=={'path','sha256'} and Path(x['path']).is_absolute() and re.fullmatch('[0-9a-f]{64}',x['sha256']) is not None,'invalid file pin')
    require(sha(x['path'])==x['sha256'],'file pin mismatch: '+x['path'])

def validate(c):
    require(c['schema']=='rc1-trackk-v1','config schema')
    require(c['protocol']=={'path':str(REPO/'experiments/RC1-FUNCTIONAL-TEST.md'),'sha256':PROTOCOL},'protocol binding')
    pinfile(c['protocol'])
    require(c['manifest']=={'path':str(Path(C.KEV_DIR)/'manifest.json'),'sha256':MANIFEST},'manifest binding');pinfile(c['manifest'])
    manifest=read(c['manifest']['path'])
    for (s,p,k),(n,h) in DATA.items():
        x=manifest['suites'][s]['partitions'][p]['outputs'][k]
        require(x['path']==f'{s}/{p}'+('.variants' if k=='variants' else '')+'.jsonl' and x['sha256']==h and x['rows']==n,'manifest population mismatch')
        # Existence and manifest metadata only; do not open TEST payload here.
        require((Path(C.KEV_DIR)/x['path']).is_file(),'population missing')
    source=c['source_files']; required=required_sources()
    require(set(source)==required,'source closure pin set differs')
    for path,h in source.items(): pinfile({'path':path,'sha256':h})
    require(re.fullmatch('sha256:[0-9a-f]{64}',c['image']) is not None,'image digest')
    roster=c['roster'];require([r['id'] for r in roster]==LANES+BASES,'fixed roster/order differs')
    require(c['member'] in LANES+BASES,'member not in roster')
    require(Path(c['round_dir']).is_absolute() and Path(c['out']).is_absolute() and c['out']!=c['round_dir'],'paths')
    # Review attaches the exact configuration (excluding the review pin itself), not a historical passflag.
    pinfile(c['review']);review=read(c['review']['path'])
    require(review.get('schema')=='rc1-trackk-review-v1' and review.get('config_sha256')==digest({k:v for k,v in c.items() if k!='review'}) and review.get('reviewed') is True,'review binding differs')
    identities={}
    for r in roster:
        require(r['status'] in ('available','unavailable','failed'),'invalid status')
        if r['status']!='available':
            require(isinstance(r.get('reason'),str) and r['reason'],'missing failure reason');continue
        require(r.get('arm')==('K0' if r['id'] in BASES else 'K1'),'role differs')
        size=r['id'].split('-')[0]
        require(r.get('size')==size and (r.get('seed') is None if r['arm']=='K0' else r.get('seed')==int(r['id'][-1]) and r.get('terminal_step')==3116),'size/seed/terminal differs')
        require((r.get('adapter') is None)==(r['arm']=='K0'),'adapter role differs')
        require(isinstance(r.get('evidence'),dict) and set(r['evidence']) >= ({'base_inventory','tokenizer','runtime'} if r['arm']=='K0' else {'base_inventory','tokenizer','runtime','publication','training_terminal','smoke_resume','dev_review'}),'missing evidence')
        for v in r['evidence'].values():pinfile(v)
        ident=TL.model_identity(r['model'],r['adapter'],c['round_dir'])
        require(ident['base_revision']!='unknown' and ident['sha256']==r['identity_sha256'],'model identity differs')
        identities[r['id']]=ident
    for size in ('q0p8b','q2b','q4b','q9b'):
        models={str(Path(r['model']).resolve()) for r in roster if r['status']=='available' and r['id'].startswith(size+'-')}
        require(len(models)<=1,'same-size base differs')
    require(c['member'] in identities,'member unavailable')
    require(len({x['sha256'] for x in identities.values()})==len(identities),'duplicate identity')
    return identities

def campaign_digest(c):
    # Member deployment and lifecycle settings are bound by the member review
    # and owner, while FINAL binds the shared scientific campaign.
    return digest({k:c[k] for k in ('schema','protocol','manifest','source_files','image','roster','round_dir')})

def prepare(c):
    ids=validate(c); rd=Path(c['round_dir']);rd.mkdir(parents=True,exist_ok=True)
    doc={'round':'RC1-functional-test','protocol_sha256':PROTOCOL,'campaign_sha256':campaign_digest(c),'models':[{'label':r['id'],'path':ids[r['id']]['path'],'sha256':ids[r['id']]['sha256']} for r in c['roster'] if r['id'] in ids], 'roster_status':[{'id':r['id'],'status':r['status'],'reason':r.get('reason')} for r in c['roster']]}
    p=rd/'FINAL.json'
    if p.exists():require(read(p)==doc,'FINAL differs; create a new round')
    else:
        require(not (rd/'TEST-READS.log').exists(),'existing access log forbids new FINAL');save(p,doc)
    return doc

def admitted(c):
    ids=validate(c); final=TL.read_final(c['round_dir'])
    require(final.get('campaign_sha256')==campaign_digest(c) and TL.is_named(final,ids[c['member']]),'FINAL/config mismatch')
    return ids[c['member']]

@contextlib.contextmanager
def lock(c,identity):
    out=Path(c['out']);out.mkdir(parents=True,exist_ok=True)
    # shared round lock prevents two output dirs from racing for the same model.
    p=Path(c['round_dir'])/('owner-'+identity['sha256']+'.lock');p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        owner={'config_sha256':digest(c),'out':c['out'],'model_sha256':identity['sha256']}
        op=p.with_suffix('.json')
        if op.exists():require(read(op)==owner,'model already bound to another execution')
        else:save(op,owner)
        yield owner

def args(c,stage,full=FULL):
    r=next(x for x in c['roster'] if x['id']==c['member'])
    a=['--model-path',r['model'],'--out',c['out'],'--arm',r['arm'],'--partitions','calibration,test','--stages',stage,'--scorer','rightpad','--dtype','float32','--no-hf32','--require-record-grade','--device','npu' if stage=='k_score' else 'cpu','--round-dir',c['round_dir'],'--limit','0']
    if r['adapter']:a+=['--adapter',r['adapter']]
    if stage=='k_score':a+=['--k-only',','.join(GROUPS)]
    result=full.parse_full_args(a);result.token_budget=16384;return result

class Offline:
    def __init__(self,desc):self.desc=desc
    def describe(self):return self.desc
    def __call__(self,*a,**kw):raise RuntimeError('offline readout missing')

def checked(score):
    def call(rows,mode='full'):
        values=score(rows,mode)
        require(len(values)==len(rows),'scorer count mismatch')
        for row,v in zip(rows,values):require(len(v)==len(row['levels']) and all(type(x) in (int,float) and math.isfinite(x) for x in v),'invalid scores')
        return values
    for n in ('describe','token_stats','dedup_stats'):
        if hasattr(score,n):setattr(call,n,getattr(score,n))
    return call

def verify(c,identity,desc,expected=None):
    evidence={};clean_rows={}
    for s,p in PLAN:
        ticket=TL.authorize_test_read(identity,s,'test',c['round_dir']) if p=='test' else None
        clean,_=C.load_partition(s,p,ticket=ticket)
        variants,_=C.load_partition(s,p,variants=True,ticket=ticket) if p=='test' else ([],None)
        require(len(clean)==DATA[(s,p,'clean')][0] and (p!='test' or len(variants)==DATA[(s,p,'variants')][0]),'population count differs')
        if p=='test':
            counts={k:sum(v['variant']==k for v in variants) for k in C.KEV_VARIANTS}
            expected_counts=([72,72,96] if s=='decision-v7' else [36,36,36])
            require(sorted(counts.values())==expected_counts and sum(counts.values())==len(variants),'variant kind counts differ')
        for kind in (('clean',) if p=='calibration' else ('clean','variants','question_only','empty_input')):
            group=f'{s}/{p}/{kind}';pop=variants if kind=='variants' else clean
            path=C.k_readout_path(c['out'],s,p,kind); receipt=AS.receipt_path(path)
            stored=AS.check_receipt(path,identity['sha256'],desc,recover=False)
            rows=SE.validate_population(stored,pop,C.kev_key)
            evidence[group]={'store_sha256':sha(path),'receipt_sha256':sha(receipt),'rows':len(rows)}
            if kind=='clean':clean_rows[group]=(pop,rows)
    if expected is not None:require(evidence==expected,'readout evidence changed')
    return evidence,clean_rows

def check_data(c,ident):
    for suite in SUITES: TL.authorize_test_read(ident,suite,'test',c['round_dir'])
    for (s,p,k),(_,h) in DATA.items():
        path=C.partition_path(s,p,k=='variants')
        require(sha(path)==h,'data pin mismatch: '+path)

def previous(c,ident):return {s:TL.earlier_reads(c['round_dir'],ident,s,'test') for s in SUITES}

def infer(c,full=FULL,score_factory=None,verify_fn=verify):
    ident=admitted(c)
    with lock(c,ident) as owner:
        require(not any(previous(c,ident).values()),'need_reconcile: existing TEST completion')
        check_data(c,ident)
        ready=Path(c['out'])/'INFERENCE-READY.json'
        if ready.exists():
            doc=read(ready);require(doc['owner']==owner,'inference owner differs');verify_fn(c,ident,doc['descriptor'],doc['stores']);return doc
        intent=Path(c['out'])/'INFERENCE-INTENT.json'
        if intent.exists():require(read(intent)==owner,'inference intent differs')
        else:save(intent,owner)
        a=args(c,'k_score',full)
        if score_factory is None:
            import eval_r3
            score_factory=eval_r3.make_score_fn
        scorer=checked(score_factory(a));desc=scorer.describe();started=time.monotonic()
        result=full.run_full(a,scorer);require('track_k' not in result and not any(previous(c,ident).values()),'inference unexpectedly completed TEST')
        evidence,_=verify_fn(c,ident,desc)
        doc={'schema':'rc1-inference-ready-v1','owner':owner,'groups':GROUPS,'descriptor':desc,'stores':evidence,'header':result['header'],'elapsed_seconds':time.monotonic()-started}
        save(ready,doc);return doc

def fit_document(fitted, ready, identity):
    # Tuple keys are represented as ordered JSON arrays, never stringified tuples.
    entries=[{'tier':tier,'key':list(key),'tau':value[0],'n_fit':value[1]}
             for (tier,key),value in fitted._table.items()]
    entries.sort(key=lambda e: json.dumps([e['tier'],e['key']],sort_keys=True,separators=(',',':')))
    import thresholds
    return {'schema':'rc1-operator-fit-v1','partition':'decision-v7/calibration',
            'population_n':ready['stores']['decision-v7/calibration/clean']['rows'],
            'calibration_data_sha256':DATA[('decision-v7','calibration','clean')][1],
            'calibration_store':ready['stores']['decision-v7/calibration/clean'],
            'descriptor':ready['descriptor'],'model_sha256':identity['sha256'],
            'splitter':fitted.splitter_name,'summary':fitted.summary(),
            'default_tau':thresholds.DEFAULT_TAU,'min_fit_items':thresholds.MIN_FIT_ITEMS,
            'tau_grid':list(thresholds.TAU_GRID),'entries':entries}

@contextlib.contextmanager
def readonly_evaluator(full, c, ident, ready):
    # Frozen evaluator uses module globals; this phase must run alone in its process.
    # Restore both callbacks even on exception. The owner lock isolates each lane,
    # but is not a cross-lane thread lock: do not run concurrent lanes in one process.
    if not hasattr(full, '_score_k'): # lightweight supplied test double
        yield
        return
    original_score=full._score_k
    original_fit=full.V.fit_operator
    fit_count=[]
    def score(_score, rows, path, mode, log, label, variant=None):
        stored=AS.check_receipt(path,ident['sha256'],ready['descriptor'],recover=False)
        return [r['s'] for r in SE.validate_population(stored,rows,C.kev_key)]
    def fit(rows, scores):
        require(not fit_count and len(rows)==ready['stores']['decision-v7/calibration/clean']['rows'],'operator fit must run once on calibration')
        fitted=original_fit(rows,scores)
        fit_count.append(fitted)
        save(Path(c['out'])/'CPU'/'OPERATOR-FIT.json',fit_document(fitted,ready,ident))
        return fitted
    full._score_k=score
    full.V.fit_operator=fit
    try:
        yield
        require(len(fit_count)==1,'operator fit missing')
    finally:
        full._score_k=original_score
        full.V.fit_operator=original_fit

def check_completed_evidence(c, owner, doc):
    # Hash whole files, including bytes beyond a receipt's committed prefix.
    try:
        fit=doc['operator_fit_artifact']
        require(fit['path']==str(Path(c['out'])/'CPU'/'OPERATOR-FIT.json'), 'operator fit path differs')
        pinfile(fit)
        ready_path=Path(c['out'])/'INFERENCE-READY.json'
        require(sha(ready_path)==doc['inference_ready_sha256'], 'inference handoff hash differs')
        ready=read(ready_path)
        require(ready['owner']==owner and ready['groups']==GROUPS and set(ready['stores'])==set(GROUPS), 'inference handoff differs')
        for group in GROUPS:
            suite,partition,kind=group.split('/')
            path=C.k_readout_path(c['out'],suite,partition,kind)
            evidence=ready['stores'][group]
            require(sha(path)==evidence['store_sha256'] and sha(AS.receipt_path(path))==evidence['receipt_sha256'], 'inference evidence differs: '+group)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError('need_reconcile: completed evidence missing or changed; retain evidence') from exc

def cpu(c,full=FULL,verify_fn=verify):
    ident=admitted(c)
    with lock(c,ident) as owner:
        report=Path(c['out'])/'K-REPORT.json'; prior=previous(c,ident)
        if any(prior.values()):
            if report.exists() and all(len(prior[s])==1 for s in SUITES):
                doc=read(report);require(doc['rc1_owner']==owner and doc['test_reads']==['\t'.join(prior[s][0][k] for k in ('utc','path','sha256','suite','partition','n','headline_accuracy')) for s in SUITES],'need_reconcile: report/log mismatch')
                check_completed_evidence(c,owner,doc);return doc
            raise RuntimeError('need_reconcile: partial or unpersisted TEST completion; retain intent, stores and log')
        check_data(c,ident)
        ready=read(Path(c['out'])/'INFERENCE-READY.json');require(ready['owner']==owner and ready['groups']==GROUPS,'inference handoff differs')
        _,rows=verify_fn(c,ident,ready['descriptor'],ready['stores'])
        probabilities={g:RM.summarize([r['s'] for r in stored],[C.gold_index(r) for r in pop]) for g,(pop,stored) in rows.items()}
        intent=Path(c['out'])/'CPU-INTENT.json'
        if intent.exists():require(read(intent)==owner,'cpu intent differs')
        else:save(intent,owner)
        cpu_dir=Path(c['out'])/'CPU';cpu_dir.mkdir(parents=True,exist_ok=True)
        for name in ('trackk','manifests'):
            link=cpu_dir/name; target=(Path(c['out'])/name).resolve()
            if link.is_symlink():require(link.resolve()==target,'CPU evidence link differs')
            else:
                require(not link.exists(),'CPU evidence path occupied')
                link.symlink_to(target, target_is_directory=True)
        a=args(c,'k',full);a.out=str(cpu_dir)
        with readonly_evaluator(full,c,ident,ready):
            result=full.run_full(a,Offline(ready['descriptor']))
        if hasattr(full,'_score_k'):
            fit_path=cpu_dir/'OPERATOR-FIT.json'
            result['operator_fit_artifact']={'path':str(fit_path),'sha256':sha(fit_path)}
        parts=result['track_k']['partitions']
        for s,p in PLAN:
            require(parts[f'{s}/{p}']['n']==DATA[(s,p,'clean')][0],'report population differs')
            if p=='test':require(sum(parts[f'{s}/{p}']['n_variants'].values())==DATA[(s,p,'variants')][0],'report variants differ')
        require(all(len(v)==1 for v in previous(c,ident).values()),'need_reconcile: completion log incomplete')
        result['rc1_owner']=owner;result['probability_panels']=probabilities;result['inference_ready_sha256']=sha(Path(c['out'])/'INFERENCE-READY.json')
        save(report,result);return result

def host_release(c,config_path):
    """Host-only fresh Docker observation and allocation-release verification."""
    import r3_final_container as K
    spec=c['container']['spec']
    launch=read(c['container']['launch_receipt']);release=read(c['container']['release'])
    require(spec['image']==c['image'] and spec['cmd']==['-B','-P',str(Path(__file__).resolve()),'infer','--config',str(Path(config_path).resolve())],'container command/image mismatch')
    observed=json.loads(subprocess.check_output(['docker','inspect',spec['name']],text=True))[0]
    K.verify_observation(spec,observed,launch['id'])
    state=observed['State'];require(state['Status']=='exited' and type(state['ExitCode']) is int and state['ExitCode']==0 and not state.get('OOMKilled',False),'inference container not successfully exited')
    ready=Path(c['out'])/'INFERENCE-READY.json';marker=read(Path(c['out'])/'INFER-EXIT.json')
    require(marker=={'schema':'rc1-infer-exit-v1','config_sha256':digest(c),'exit_code':0,'ready_sha256':sha(ready)},'infer terminal differs')
    require(release.get('schema')=='r3-resource-release-v1' and release.get('container_id')==launch['id']==observed['Id'] and release.get('container')==spec['name'] and release.get('exit_code')==0 and release.get('container_finished_at')==state['FinishedAt'] and release.get('container_started_at')==state['StartedAt'],'release identity differs')
    claim=read(c['container']['claim'])
    require(release.get('claim_sha256')==sha(c['container']['claim']) and claim.get('run')==release.get('run')==c['container']['run'] and claim.get('chip')==release.get('chip')==c['container']['chip'],'claim/release differs')
    before=release['allocation_before'];after=release['allocation_after'];chip=c['container']['chip'];run=c['container']['run']
    for value,key in ((before,'allocation_before_sha256'),(after,'allocation_after_sha256')):
        require(hashlib.sha256((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()==release[key],'allocation digest differs')
    require(any(x.get('chip')==chip and x.get('run')==run for x in before['allocation']) and not any(x.get('chip')==chip for x in after['allocation']) and any(x.get('chip')==chip and x.get('previous_run')==run for x in after['free']),'allocation transition differs')
    return {'container_id':observed['Id'],'ready_sha256':sha(ready),'release_sha256':sha(c['container']['release'])}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=('prepare','infer','host-cpu'));p.add_argument('--config',required=True)
    a=p.parse_args();c=read(a.config)
    if a.phase=='prepare': result=prepare(c)
    elif a.phase=='infer':
        try:
            result=infer(c)
        except BaseException:
            save(Path(c['out'])/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':digest(c),'exit_code':1,'ready_sha256':None})
            raise
        save(Path(c['out'])/'INFER-EXIT.json',{'schema':'rc1-infer-exit-v1','config_sha256':digest(c),'exit_code':0,'ready_sha256':sha(Path(c['out'])/'INFERENCE-READY.json')})
    else:
        admitted(c);evidence=host_release(c,a.config);save(Path(c['out'])/'HOST-RELEASE-VERIFIED.json',evidence);result=cpu(c)
    print(json.dumps({'phase':a.phase,'state':'ok','result_sha256':digest(result)},sort_keys=True))
if __name__=='__main__':main()
