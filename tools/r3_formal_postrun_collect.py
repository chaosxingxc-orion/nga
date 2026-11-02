"""Configured formal-wave CPU postrun collection; never grants independent acceptance."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import types

LEGACY_SHA='5b4f62baba6ab9588b4fabad95be995bebda6bd192fa0df2a525f845cb005c41'
SCHEMA='r3-formal-postrun-collector-config-v2'
OWNERSHIP_SHA='89fa709d4f830f38ebbc7bd449d89a8e3c527ed3e986dc71ff6faa64f755df4f'

def require(ok, why):
    if not ok: raise ValueError(why)
def safe(path):
    p=Path(path);require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');require(not any(x.lower().split('.')[0]=='test' for x in p.parts),'TEST path forbidden');return p
def sha(path):
    h=hashlib.sha256()
    with safe(path).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def unique(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'duplicate JSON key');result[k]=v
    return result
def raw(path,pin=None):
    data=safe(path).read_bytes();require(len(data)<=2**20,'metadata exceeds bound');require(pin is None or hashlib.sha256(data).hexdigest()==pin,'source pin differs: '+str(path));return data
def read(path,pin=None):return json.loads(raw(path,pin),object_pairs_hook=unique,parse_constant=lambda x:require(False,'nonfinite JSON'))
def pinned(ref):
    p=safe(ref['path']);require(sha(p)==ref['sha256'],'source pin differs: '+str(p));return p
def module(ref):
    p=safe(ref['path']);data=raw(p,ref['sha256']);m=types.ModuleType(p.stem);m.__file__=str(p);exec(compile(data,str(p),'exec',dont_inherit=True),m.__dict__);return m

def identity(path,pin):
    c=read(path,pin)
    require(c['schema']==SCHEMA and c['test_read'] is False and c['scientific_acceptance'] is False,'config scope differs')
    require(pinned(c['controller'])==Path(__file__).resolve(),'collector executable differs')
    require(c['legacy']['sha256']==LEGACY_SHA,'accepted legacy source required')
    require(c['ownership_verifier']['sha256']==OWNERSHIP_SHA,'accepted ownership verifier required')
    pinned(c['ownership_verifier'])
    L=module(c['legacy']);H=module(c['handoff_controller']);pinned(c['handoff'])
    b,jobs,_=H.identity(c['handoff']['path'],c['handoff']['sha256'])
    require(c['role'] in jobs,'unknown formal role');job=jobs[c['role']]
    require(b['source_files'].get(c['handoff_controller']['path'])==c['handoff_controller']['sha256'],'handoff controller unbound')
    require(c['training_plan']==job['training_plan'],'configured training plan differs')
    plan=H.load(job['training_plan']['path'],job['training_plan']['sha256'])
    require(plan.get('formal_role')==c['role'] and plan['seed']==job['seed'] and plan['chip']==job['chip'],'role identity differs')
    state=safe(b['state_root'])/c['role'];out=safe(c['output']);training=safe(job['training'])
    require(out.name.endswith('.json') and not out.is_relative_to(safe(b['state_root'])) and all(not out.is_relative_to(safe(v['training'])) and not out.is_relative_to(safe(v['fresh_eval_out'])) for v in jobs.values()),'output inside producer trees')
    require(out.parent.is_dir(),'output parent missing')
    return c,L,H,b,job,plan,state,out

def missing(c,H,b,job,state):
    root=Path(job['training']);names=job['late_bound_hashes']+H.EXTRA
    paths=[root/n for n in names]+[state/'CAPTURE.json']
    end=root/'TRAIN_EXIT.json'
    if end.exists():
        e=H.load(end);require(type(e.get('exit_code')) is int and e['exit_code']==0,'training failed or invalid terminal')
    return [str(p) for p in paths if not p.is_file()]

def inspect(path,pin):
    c,L,H,b,j,p,state,out=identity(path,pin);absent=missing(c,H,b,j,state)
    return dict(status='WAIT' if absent else 'READY_FOR_EXTERNAL_OBSERVATIONS',training=j['training'],missing=absent,independent_review_granted=False,scientific_acceptance=False,test_read=False)

def manifest_check(L,m,p):
    args=m.get('args',{});command=p['command']
    flags=[x for x in command if isinstance(x,str) and x.startswith('--')];require(len(flags)==len(set(flags)),'duplicate command flag')
    require(type(p['seed']) is int and p['seed'] in (2,3) and type(args.get('seed')) is int and args['seed']==p['seed'],'seed differs')
    for flag,value in [('--seed',str(p['seed'])),('--arm','k1'),('--model-path',p['model']),('--out',p['out'])]:
        require(command.count(flag)==1 and command.index(flag)+1<len(command) and command[command.index(flag)+1]==value,'command identity differs: '+flag)
    require(p.get('arm','k1')=='k1' and not p.get('control_arm') and '--drop-state' not in command and not args.get('drop_state'),'formal K1 only')
    # The frozen legacy verifier hardcodes seed2. Only this already-checked scalar
    # is adapted in a copy; original manifest/plan bytes remain pinned evidence.
    view=copy.deepcopy(m);view['args']['seed']=2;L.verify_manifest(view,p)

def moment(value):
    t=datetime.datetime.fromisoformat(value.replace('Z','+00:00'));require(t.tzinfo is not None,'timezone required');return t

def collect(path,pin,capture_pin,observations_path,observations_pin):
    c,L,H,b,j,p,state,out=identity(path,pin);absent=missing(c,H,b,j,state)
    if absent:return dict(status='WAIT',missing=absent,scientific_acceptance=False,test_read=False)
    require(capture_pin and observations_path and observations_pin,'real capture and external observations required')
    with L.owned_snapshot() as snap:
        L.ACTIVE=snap
        try:
            snap.capture(path,pin);snap.capture(c['legacy']['path'],LEGACY_SHA);snap.capture(c['controller']['path'],c['controller']['sha256'])
            for ref in [c['handoff'],c['handoff_controller'],c['ownership_verifier'],c['training_plan'],b['queue'],b['closure']]:snap.capture(ref['path'],ref['sha256'])
            for f,h in b['source_files'].items():snap.capture(f,h)
            cap_path=state/'CAPTURE.json';captured=L.load(cap_path,pin=capture_pin);training=Path(j['training']);adapter=training/'adapter/adapter_model.safetensors'
            snap.inventory(training/'adapter');snap.capture(adapter,captured['files'][str(adapter)],payload=True)
            for f,h in captured['files'].items():snap.capture(f,h)
            H.raw=lambda f,pin=None,limit=2**20:L.raw(f,pin,limit)
            H.sha=L.sha;H.load=lambda f,pin=None:L.load(f,pin=pin)
            H.check_capture(captured,b,j,p)
            end=L.load(training/'TRAIN_EXIT.json');require(end==L.load(training/'attempts/1/EXIT.json') and end.get('source')!='retained-container-exit','genuine terminal differs')
            refs=L.load(observations_path,pin=observations_pin);require(refs.get('schema')=='r3-postrun-external-observations-v1' and set(refs['observations'])=={'container','image','daemon'},'observation manifest differs')
            require(refs['training']==j['training'] and refs['capture_sha256']==capture_pin,'observations belong to another capture')
            op=safe(observations_path);require(not op.is_relative_to(training) and not op.is_relative_to(Path(b['state_root'])),'observations inside producer')
            docs={};opins={str(op):observations_pin}
            for name,ref in refs['observations'].items():
                f=safe(ref['path']);require(not f.is_relative_to(training) and not f.is_relative_to(Path(b['state_root'])),'observation inside producer')
                docs[name]=L.load(f,pin=ref['sha256']);opins[str(f)]=ref['sha256']
            for name in ('container','image'):require(isinstance(docs[name],list) and len(docs[name])==1,'single external observation required')
            actual=docs['container'][0];L.verify_container(p,j,actual,docs['image'][0],docs['daemon'])
            # Reuse the accepted current full-transition validator. The v1
            # legacy helper hardcodes an older producer's updated_by label.
            # No ledger bytes are normalized and no label is allowlisted.
            ownership=module(c['ownership_verifier'])
            ownership.ownership(p,L.load(training/'attempts/1/CLAIM.json'),
                L.load(training/'attempts/1/RELEASE.json'),
                captured['files'][str(training/'attempts/1/CLAIM.json')],
                training/'attempts/1/RELEASE.json',actual)
            require(moment(actual['State']['StartedAt'])<=moment(end['started_utc'])<=moment(end['finished_utc'])<=moment(actual['State']['FinishedAt']),'driver chronology differs')
            verified={}
            for f,h in p['files'].items():snap.capture(f,h);verified[f]=h
            manifest_check(L,L.load(training/'manifest.json'),p)
            config=L.load(training/'adapter/adapter_config.json');L.verify_config(config,p['model']);payload=L.verify_payload(adapter,L.expected_shapes(p['model'],config))
            require(payload['scanned_sha256']==captured['files'][str(adapter)],'payload differs')
            H.check_capture(captured,b,j,p)
            report=dict(schema='formal-postrun-evidence-collection-v2',status='EVIDENCE_COLLECTED_REVIEW_REQUIRED',training=j['training'],capture_sha256=capture_pin,files=captured['files'],static_pins={str(path):pin,**{r['path']:r['sha256'] for r in [c['legacy'],c['controller'],c['handoff'],c['handoff_controller'],c['ownership_verifier'],b['queue'],b['closure']]}},verified_training_files=verified,external_observation_pins=opins,adapter_payload=payload,adapter_file_count=len(captured['adapter_files']),supported_existing_checks=['genuine_train_exit','retained_container_identity','claim_release_done_identity','training_inputs_and_code','adapter_provenance','final_step_3116'],independent_review_granted=False,prepare_authorized=False,evaluation_authorized=False,test_read=False,scientific_acceptance=False,boundary='Offline pinned observations; parent authenticates origin/time and independent reviewer judges. No Docker calls or model load.',role=c['role'],seed=p['seed'])
            report['snapshot']=dict(scope='Validated captured byte snapshot',source_identities={f:list(e['identity']) for f,e in snap.entries.items()},source_sha256={f:e['sha256'] for f,e in snap.entries.items()},full_source_reads=dict(snap.full_reads),final_check='descriptor-relative identities and adapter inventory before exclusive publication')
            L.save(out,report,guard=snap.final_check);return report
        finally:L.ACTIVE=None

def main():
    a=argparse.ArgumentParser();a.add_argument('op',choices=['inspect','collect']);a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);a.add_argument('--capture-sha256');a.add_argument('--observations');a.add_argument('--observations-sha256');v=a.parse_args()
    result=inspect(v.config,v.sha256) if v.op=='inspect' else collect(v.config,v.sha256,v.capture_sha256,v.observations,v.observations_sha256)
    print(json.dumps({k:result[k] for k in ('status','training','missing','independent_review_granted','scientific_acceptance','test_read') if k in result},indent=2));return 2 if result['status']=='WAIT' else 0
if __name__=='__main__':raise SystemExit(main())
