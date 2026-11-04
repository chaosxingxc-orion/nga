"""CPU-only recovered PT2 capture/review/DEV preparation; never starts a service.

Production configuration must be independently reviewed after the recovery plan is
final. This component does not authenticate an external reviewer's identity: the
caller supplies an authenticated exact review pin. No NPU or TEST interface.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

SCHEMA='r3-training-resume-handoff-v1'
MODEL='/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'

def need(ok,why):
    if not ok:raise ValueError(why)
def safe(path):
    p=Path(path)
    need(p.is_absolute() and str(p)==str(path) and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'unsafe path')
    need(not any(x.lower().split('.')[0]=='test' for x in p.parts),'TEST path forbidden')
    return p
def sha(path):
    with safe(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path,pin=None):
    p=safe(path);raw=p.read_bytes();need(pin is None or hashlib.sha256(raw).hexdigest()==pin,'pin changed')
    return json.loads(raw)
def ref(r):
    need(set(r)=={'path','sha256'},'invalid reference');p=safe(r['path']);need(sha(p)==r['sha256'],'reference changed');return p
def module(r):
    p=ref(r);m=types.ModuleType(p.stem);m.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
def canonical(p):return hashlib.sha256((json.dumps(dict(p,review_sha256='PENDING'),sort_keys=True,indent=2)+'\n').encode()).hexdigest()
def disjoint(*paths):
    for i,a in enumerate(paths):
        for b in paths[i+1:]:need(not (a==b or a.is_relative_to(b) or b.is_relative_to(a)),'state/output overlap')

def identity(path,pin):
    c=read(path,pin)
    need(c['schema']==SCHEMA and all(c[k] is False for k in ('test_read','scientific_acceptance','evaluation_authorized')),'scope differs')
    need(ref(c['controller'])==Path(__file__).resolve(),'controller differs')
    need(type(c['poll_interval_seconds']) is int and c['poll_interval_seconds']>=600,'cadence too short')
    need(set(c['sources'])=={'handoff','binder'},'sources differ')
    H=module(c['sources']['handoff']);B=module(c['sources']['binder'])
    p=read(ref(c['training_plan']));root=safe(p['out']);state=safe(c['state_root']);out=safe(c['evaluation_out']);disjoint(root,state,out)
    need(c['training_plan']['path']==str(root/'plan.json'),'training plan location differs')
    need(p['control_arm']=='K1-PT' and type(p['seed']) is int and p['seed']==2 and p['chip']==3 and p['model']==MODEL,'PT2 identity differs')
    need(p['test_read'] is False and p['scientific_acceptance'] is False,'training authority differs')
    need(canonical(p)==c['canonical_plan_sha256'],'canonical training identity differs')
    r=p['recovery'];need(r['source_step']==2400 and r['total_steps']==3116,'resume steps differ')
    old=read(ref(r['source_plan']));need(old['control_arm']=='K1-PT' and old['seed']==2 and old['model']==p['model'],'original control differs')
    command=list(old['command']);command[command.index('--out')+1]=p['out'];need(command==p['command'],'training recipe differs')
    need(r['checkpoint']['sha256']==r['original_checkpoint']['sha256'],'checkpoint identity differs');ref(r['checkpoint']);ref(r['original_checkpoint']);ref(r['cpu_binding']);ref(r['failed_release'])
    review=read(ref(c['training_review']));need(c['training_review']['path']==p['review_path'] and c['training_review']['sha256']==p['review_sha256'],'training review differs')
    need(review.get('verdict')=='PASS' and review.get('approved_plan_sha256')==c['canonical_plan_sha256'] and review.get('scientific_acceptance') is False,'training not independently admitted')
    closure=read(ref(c['closure']));need(closure['evaluation_profile']=='track_kt','combined DEV required')
    for f,h in closure['data'].items():safe(f);need('/test' not in f and sha(f)==h,'data changed or TEST')
    need(c['protocol_template']['sha256']==sha(ref(c['protocol_template'])),'protocol template changed')
    template=read(c['protocol_template']['path']);need(template['evaluation_profile']=='track_kt' and template['training_variant']['arm']=='k1-pt' and template['test_read'] is False,'template scope differs')
    c.update(_pin=pin,_path=str(path));job=dict(role='pt_s2',seed=2,training=p['out'],new_adapter=str(root/'adapter'),canonical_plan_sha256=c['canonical_plan_sha256'],required_final_step=3116,training_plan=c['training_plan'],fresh_eval_out=str(out),late_bound_hashes=H.LATE,chip=3)
    return c,p,job,H,B

def capture(c,p,j,H,B):
    # Reuse only saved-artifact validation; never pretend to be a legacy queue.
    H.EXTRA=[x for x in H.EXTRA if x!='SUCCESSOR_PRECONDITION.json']
    value=H.capture({'queue':{'sha256':c['_pin']},'_pin':c['_pin']},j,p)
    if value['status']!='REVIEW_REQUIRED':return value
    need(B.semantic_arm(dict(p,arm='k1'),read(Path(p['out'])/'manifest.json'))=='K1-PT','completed control differs')
    value.pop('queue_sha256');value['schema']='r3-recovery-posttrain-capture-v1';value['training_plan_sha256']=c['training_plan']['sha256']
    value['canonical_plan_sha256']=c['canonical_plan_sha256']
    value['source_checkpoint']=p['recovery']['checkpoint'];value['source_plan']=p['recovery']['source_plan']
    value['scope']='Saved recovered PT2 provenance only; external actual postrun and recovery predecessor verification required'
    return value

def inspect(path,pin,persist=False):
    c,p,j,H,B=identity(path,pin);value=capture(c,p,j,H,B)
    if persist and value['status']=='REVIEW_REQUIRED':
        state=safe(c['state_root']);state.mkdir(parents=True,exist_ok=True);target=state/'CAPTURE.json'
        if target.exists():need(read(target)==value,'capture changed')
        else:H.write(target,value,exclusive=True)
    return value

def review_check(c,p,j,H,B,review_ref):
    state=safe(c['state_root']);cp=state/'CAPTURE.json';cap=read(cp);need(cap==capture(c,p,j,H,B) and cap['status']=='REVIEW_REQUIRED','capture incomplete or changed')
    rp=ref(review_ref);need(not rp.is_relative_to(state) and not rp.is_relative_to(safe(p['out'])),'review inside producer')
    r=read(rp);need(r.get('schema')=='r3-recovery-independent-postrun-v1' and r.get('verdict')=='PASS' and r.get('independent') is True,'independent postrun review required')
    need(r.get('binding_sha256')==c['_pin'] and r.get('capture_sha256')==sha(cp) and r.get('training_plan_sha256')==c['training_plan']['sha256'] and r.get('files')==cap['files'],'postrun review binding differs')
    need(r.get('scientific_acceptance') is False and r.get('test_read') is False,'postrun authority differs')
    checks=('genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116','recovery_checkpoint_and_step_identity','recovery_predecessor_identity_and_release','observation_origin_authenticated')
    need(all(r.get('checks',{}).get(k) is True for k in checks),'postrun verification incomplete')
    need(r.get('evidence_files'),'external evidence missing')
    for f,h in r['evidence_files'].items():need(sha(f)==h,'external evidence changed')
    return cap,r

def prepare(path,pin,review_ref):
    c,p,j,H,B=identity(path,pin);state=safe(c['state_root']);cap,r=review_check(c,p,j,H,B,review_ref);out=safe(c['evaluation_out'])
    need(not out.exists() and not (state/'PREPARE_INTENT.json').exists(),'existing output or uncertain prepare; never retry')
    H.write(state/'PREPARE_INTENT.json',dict(binding_sha256=pin,review=review_ref,output=str(out)),exclusive=True)
    semantic=B.semantic_arm
    def control_semantic(plan,manifest):
        need(plan==p,'builder training changed');return semantic(dict(plan,arm='k1'),manifest)
    B.semantic_arm=control_semantic
    result=B.prepare(Path(p['out']),Path(c['closure']['path']).parent,out)
    need(result['status']=='prepared','builder did not prepare');spec=read(out/'plan.json');template=read(c['protocol_template']['path'])
    need(c['relocated_command_flags']==['--adapter','--out','--round-dir'],'only output locations may relocate')
    def normalized(x):
        cmd=list(x['command'])
        for flag in c['relocated_command_flags']:
            need(cmd.count(flag)==1,'location flag missing/duplicate');cmd[cmd.index(flag)+1]='<BOUND>'
        return cmd
    need(normalized(spec)==normalized(template),'DEV protocol differs')
    need(spec['training']==p['out'] and spec['model']==MODEL and spec['adapter']==j['new_adapter'] and spec['training_variant']['arm']=='k1-pt' and spec['training_variant']['seed']==2 and spec['training_variant']['training_plan_sha256']==c['training_plan']['sha256'],'generated identity differs')
    need(spec['test_read'] is False and spec['scientific_acceptance'] is False and spec['execution_review']==spec['chip_assignment']=='PENDING','generated authority differs')
    review_check(c,p,j,H,B,review_ref)
    result.update(evaluation_authorized=False,scientific_acceptance=False,test_read=False,scope='DEV specification only; exact execution and result review remain required')
    H.write(state/'PREPARED.json',result,exclusive=True);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','inspect','capture','prepare']);ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--review');ap.add_argument('--review-sha256');a=ap.parse_args()
    if a.op=='verify':identity(a.config,a.sha256);r={'status':'VERIFIED_CPU_COMPONENT_ONLY'}
    elif a.op=='prepare':need(a.review and a.review_sha256,'external authenticated review pin required');r=prepare(a.config,a.sha256,{'path':a.review,'sha256':a.review_sha256})
    else:r=inspect(a.config,a.sha256,persist=a.op=='capture')
    print(json.dumps({k:v for k,v in r.items() if k not in ('files','adapter_files')},indent=2));return 2 if r['status'].startswith('waiting_') else 0
if __name__=='__main__':raise SystemExit(main())
