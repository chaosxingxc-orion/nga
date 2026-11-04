"""Stage a new PT2 qualification config only after externally accepted member evidence.

Never creates BUNDLE, ADJUDICATION, member decisions or qualification authority.
Inspect is cheap; full immutable inventories are hashed only when build is ready.
"""
import argparse, copy, hashlib, json, os, types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NAMES={'primary_s2','primary_s3','samechip_s2','diffchip_s2','qo_s2','pt_s2','pt_s3','k0_base','k0_instruct'}
def need(ok,why):
    if not ok: raise ValueError(why)
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p
def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(safe(p).read_bytes())
def bound(r):
    need(set(r)=={'path','sha256'} and sha(r['path'])==r['sha256'],'changed reference');return read(r['path'])
def put(p,d):
    p=safe(p)
    with p.open('x') as f:json.dump(d,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(p):return {'path':str(p),'sha256':sha(p)}
def prepare_inputs(c):
    need(c['schema']=='pt2-next-qualification-prepare-v1' and c['activation_authorized'] is False,'builder scope')
    old=bound(c['base']);m=bound(c['migration']);training=bound(c['training_inputs'])
    need(m['source_config']==c['base'] and set(old['members'])==NAMES,'base migration identity')
    need(set(m['unchanged_accepted_members'])==NAMES-{'pt_s2'},'accepted roster differs')
    for name,r in m['unchanged_accepted_members'].items():
        need(old['members'][name]['descriptor']==r['path'] and sha(r['path'])==r['sha256'],'accepted descriptor changed')
    fields={'required_paths':16,'event_wake_paths':3};seen=set();new=copy.deepcopy(old)
    for x in m['changes']:
        field,index=x['field'],x['index'];need(field in fields and (field,index) not in seen,'duplicate/invalid migration')
        seen.add((field,index));item=new[field][index];value=item['path'] if isinstance(item,dict) else item
        need(value==x['old'] and x['new']!=x['old'],'stale migration')
        safe(x['new'])
        if field=='required_paths':need(item['member']=='pt_s2','foreign member migration');item['path']=x['new']
        else:new[field][index]=x['new']
    for f,n in fields.items():need(sum(x['field']==f for x in m['changes'])==n,'migration count differs')
    stale={x['old'] for x in m['changes']}
    need(not stale.intersection([x['path'] for x in new['required_paths']]+new['event_wake_paths']),'stale prerequisite remains')
    expected=training['entry_fields'];need(expected['arm']=='K1-PT' and expected['seed']==2,'training scope')
    return old,new,m,training

def member(c,training):
    r=c.get('member_index')
    if r is None:return None
    index=bound(r);a=bound(index['acceptance']);d=bound(index['descriptor']);b=bound(index['bundle']);auth=bound(index['authentication'])
    need(a['status']=='PASS' and a['full_member_passed'] is True and a['full_report_exact'] is True,'member not independently accepted')
    for obj in (a,d,b,auth):need(obj['scientific_acceptance'] is False and obj['test_read'] is False,'member scope')
    need(d['member']==b['member']=='pt_s2' and d['status']=='EXACT_MEMBER_ACCEPTED_PENDING_PARENT_BINDING','descriptor scope')
    need(d['entry']==b['entry'] and d['decision']==b['independent_decision'] and d['files']==b['files'],'member descriptor/bundle differs')
    need(d['authentication']==index['authentication'] and d['bundle']==index['bundle'],'member authentication binding')
    need(d['consumer']==a['consumer']==c['qualifier'],'reviewed consumer differs')
    need(bound(a['consumer_exit'])['exit_code']==0 and bound(a['consumer_check'])['full_member_passed'] is True,'member replay absent')
    for k in ('authentication','bundle','descriptor'):need(a[k]==index[k],'acceptance binding differs')
    for k,v in training['entry_fields'].items():need(d['entry'].get(k)==v,'recovered training member field differs: '+k)
    e=d['entry'];need(e['execution']==c['pt2_execution'] and e['report']==c['pt2_report'],'actual DEV path differs')
    # Parent supplies the exact independent index pin. These checks bind evidence;
    # they cannot authenticate authorship. No booleans are manufactured here.
    return index,a,d,b,auth

def status(c):
    old,new,m,t=prepare_inputs(c)
    missing=[x['new'] for x in m['changes'] if not safe(x['new']).is_file()]
    if c.get('member_index') is None:missing.append('externally pinned independent PT2 member index')
    elif not safe(c['member_index']['path']).is_file():missing.append(c['member_index']['path'])
    if missing:return {'status':'WAIT','missing':sorted(set(missing)),'activation_authorized':False,'candidate_eligibility_granted':False}
    member(c,t)
    return {'status':'READY_TO_BUILD_CONFIGURATION_ONLY','missing':[],'activation_authorized':False,'candidate_eligibility_granted':False}

def build(c,verify=True):
    ready=status(c)
    if ready['status']=='WAIT':return ready
    old,new,m,t=prepare_inputs(c);index,a,d,b,auth=member(c,t);root=safe(c['output'])
    need(not root.exists(),'output exists; reconcile/new generation required')
    pins=dict(old['immutable_files'])
    def add(p,h):
        need(p not in pins or pins[p]==h,'conflicting immutable pin');pins[p]=h
    for group in [t['files'],b['files']]:
        for p,h in group.items():add(p,h)
    for r in [c['base'],c['migration'],c['training_inputs'],c['member_index'],c['qualifier'],*c['qualifier_dependencies'],*[v for v in index.values() if isinstance(v,dict) and set(v)=={'path','sha256'}],a['consumer_check'],a['consumer_exit']]:
        need(set(r)=={'path','sha256'},'invalid explicit reference');add(r['path'],r['sha256'])
    for r in auth.values():
        if isinstance(r,dict) and set(r)=={'path','sha256'}:add(r['path'],r['sha256'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        actual=list(pool.map(sha,pins))
    need(actual==list(pins.values()),'immutable closure changed')
    # Only now create non-authoritative configuration output, never a result bundle.
    root.mkdir();(root/'member-evidence').mkdir();mapping={};copied={}
    for name,v in new['members'].items():
        source=Path(index['descriptor']['path']) if name=='pt_s2' else Path(v['descriptor'])
        target=root/'member-evidence'/(name+'.json');target.write_bytes(source.read_bytes())
        need(sha(target)==sha(source),'descriptor copy differs');mapping[v['descriptor']]=str(target);v['descriptor']=str(target)
        add(str(target),sha(target));copied[name]=ref(target)
    for k in ('bundle_path','adjudication_path','state_root'):
        before=new[k];new[k]=str(root/Path(before).name);mapping[before]=new[k]
    for x in new['required_paths']:x['path']=mapping.get(x['path'],x['path'])
    e=d['entry'];q=new['members']['pt_s2'];plan=read(e['plan'])
    q.update(training=plan['out'],plan={'path':e['plan'],'sha256':pins[e['plan']]},evaluation_out=str(Path(e['execution']).parent),execution=e['execution'],report=e['report'],checkpoint=e['model']['base_path'],binding_status='independently_accepted_member_candidate_pending_parent_binding',evaluation_path_authority='actual independently accepted PT2 DEV member',member_acceptance=index['acceptance'],accepted_member_bundle=index['bundle'])
    for k in ('postrun_collection','postrun_review','producer_manifest'):
        if k in e:q[k]={'path':e[k],'sha256':pins[e[k]]}
    new['qualifier']=c['qualifier'];new['immutable_files']=pins
    for k in ('activation_authorized','test_read','scientific_acceptance'):need(new[k] is False,'scope changed')
    for name,r in m['unchanged_accepted_members'].items():need(sha(new['members'][name]['descriptor'])==r['sha256'],'accepted descriptor changed')
    put(root/'CONFIG.json',new)
    if verify:
        need(sha(new['controller'])==new['controller_sha256'],'controller changed');module=types.ModuleType('frozen_service');module.__file__=new['controller']
        exec(compile(safe(new['controller']).read_bytes(),new['controller'],'exec'),module.__dict__)
        need(module.verify(str(root/'CONFIG.json'),sha(root/'CONFIG.json'))==new,'frozen verifier differs')
    result={'status':'CONFIGURATION_BUILT_PENDING_INDEPENDENT_REVIEW','configuration':ref(root/'CONFIG.json'),'old_pins_preserved':len(old['immutable_files']),'pins':len(pins),'unchanged_accepted_descriptors':8,'copied':copied,'bundle_written':False,'adjudication_written':False,'candidate_eligibility_granted':False,'activation_authorized':False}
    put(root/'BUILD.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);p.add_argument('--build',action='store_true');p.add_argument('--result');a=p.parse_args()
    c=bound({'path':a.config,'sha256':a.sha256});result=build(c) if a.build else status(c)
    if a.result:put(a.result,result)
    print(json.dumps(result));return 2 if result['status']=='WAIT' else 0
if __name__=='__main__':raise SystemExit(main())
