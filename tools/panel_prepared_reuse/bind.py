import json,sys,hashlib,subprocess
from pathlib import Path
r=Path('/home/xingchao/workspace/nga/.local/releases/engineering-base-rc1/tasks/execution/instruct-family-successor-packs-20261108/packs/instruct2b_devtools_successor_20261108');sys.path.insert(0,str(r/'code'));import bev_native_dataset_panel_v1 as C
sha=C.sha;ref=lambda p:{'path':str(p),'sha256':sha(p)}
def save(p,x):
 p=Path(p)
 if p.exists():raise ValueError('refusing overwrite: '+str(p))
 p.write_text(json.dumps(x,sort_keys=True,indent=2)+'\n')
C.require(len(sys.argv)==3,'usage: bind.py CHIP EXTERNALLY_ACCEPTED_CPU_PREPARE_SHA256');prepared_pin=sys.argv[2];C.require(__import__('re').fullmatch('[0-9a-f]{64}',prepared_pin) is not None,'prepared pin differs')
c=C.read(r/'CPU-CONFIG.json');chip=int(sys.argv[1]);C.require(chip in (4,5),'chip must be 4 or 5');alloc=C.read(c['resources']['allocation']);free=next(x for x in alloc['free'] if x['chip']==chip);rel=Path(free['release_evidence']);claim=rel.with_name('CLAIM.json' if rel.name=='RELEASE.json' else 'claim.json');q={'schema':'instruct08-documents-resource-v1','chip':chip,'run':'r3_runs/'+r.name,'allocation':c['resources']['allocation'],'free_entry':free,'pending_claims':alloc['pending_claims'],'predecessor':{'claim':ref(claim),'release':ref(rel)}}
# Validate actual predecessor, live holder and generation before producing binding.
import resource_v3 as Q
R=Q.module(c['modules']['resource_base'])
import unified_resource_lease_v1 as U
R.validate_doc(alloc);C.require(not any(x['chip']==chip for x in alloc['allocation']),'allocated');U.predecessor({'allocation':q['allocation']},free,U.DockerQuery(),{'claim':q['predecessor']['claim'],'release':q['predecessor']['release'],'container':None,'terminal':None});C.require(not R.live_chip_conflict(chip,None),'live conflict')
save(r/'RESOURCE-POLICY.json',q);c['resources'].update(chip=chip,policy=ref(r/'RESOURCE-POLICY.json'))
for f in (r/'RESOURCE-POLICY.json',claim,rel):c['files'][str(f)]=sha(f)
save(r/'CONFIG.json',c);C.build(str(r/'CONFIG.json'),sha(r/'CONFIG.json'),str(r/'PLAN.json'),prepared_plan=str(r/'CPU-PREPARE.json'),prepared_pin=prepared_pin);d=C.verify(str(r/'PLAN.json'),sha(r/'PLAN.json'),cpu=True);subprocess.run(['/usr/bin/python3.12','-B','-P',str(r/'code/numeric_admission.py'),'--model','2b','--package','/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_rc1_family_numeric_20261107/2b/package','--admission','/mnt/cephfs/xingchao/experiments/jev/r3_runs/instruct_rc1_family_numeric_20261107/2b/output/cpu/ADMISSION.json','--sha256',c['numeric']['admission_sha256']],check=True);Q.guard(d,R,C.read(q['allocation']))
import bev_native_config_panel_host as H
pin=sha(r/'PLAN.json');out=r/'output/cpu/1';out.mkdir(parents=True,exist_ok=False);save(out/'PARENT-INTENT.json',{'schema':'kev-generic-parent-intent-v1','plan_sha256':pin,'attempt':1});save(out/'CHILD-CONFIG.json',C.build_child_config(d,str(r/'PLAN.json'),pin,1,out/'PARENT-INTENT.json'));v={**d,'runtime':d['modules']['runtime'],'resource':d['modules']['resource'],'image_sha256':d['image']};cmd=H.command(v,str(r/'PLAN.json'),pin,1);cpu=C.cpu_command(d,str(r/'PLAN.json'),pin,1)
import watcher
kev=r/'output/kev_cpu/1';kev.mkdir(parents=True,exist_ok=False)
for action in ('kev','watcher'):
 intent=kev/('KEV-PARENT-INTENT.json' if action=='kev' else 'WATCHER-PARENT-INTENT.json');save(intent,{'schema':'kev-'+action+'-parent-intent-v1','plan_sha256':pin,'attempt':1});config=watcher.build(str(r/'PLAN.json'),1,action,intent,r/'code/bootstrap.py',r/'code/loader.py');save(kev/(action.upper()+'-CONFIG.json'),config)
score_command=[config['interpreter'],'-B','-P',config['bootstrap']['path'],'--config',str(kev/'WATCHER-CONFIG.json'),'--sha256',sha(kev/'WATCHER-CONFIG.json')]
save(r/'ACCEPTANCE-REQUEST.json',{'schema':'instruct2b-devtools-operational-acceptance-request-v1','status':'REQUEST_ONLY_NOT_ACCEPTED','request':'Independent review of frozen TEST/chat/order, numeric dependency, exact execution and resource generation','verdict_required':'PASS','approved_plan_sha256':pin,'activation_authorized':True,'scientific_acceptance':False,'test_read':True,'candidate_test_authority':False,'scope':d['scope'],'attempts':[1],'expected_commands':{'1':cmd},'hashes':d['files'],'numeric_admission_sha256':c['numeric']['admission_sha256'],'cpu_command':cpu,'kev_watcher_command':score_command,'kev_child_config_sha256':sha(kev/'KEV-CONFIG.json'),'population':1073,'pairs':454,'no_acceptance_granted_by_request':True})
print(json.dumps({'status':'BOUND_REVIEW_REQUIRED','plan_sha256':pin,'chip':chip,'cpu_command':cpu}))
