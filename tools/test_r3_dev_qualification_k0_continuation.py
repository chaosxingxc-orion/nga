"""Continuation adapter tests; synthetic acceptance/actual observation stay in memory."""
import copy,json,types,unittest
from pathlib import Path
from tools import r3_dev_qualification as Q

BASE=Path('/home/xingchao/workspace/nga/.local/preparations/k0-cpu-continuation-20261103-v2')
REVIEW=Path('/home/xingchao/workspace/nga/.local/reports/k0-cpu-continuation-v2-independent-current.json')

class Continuation(unittest.TestCase):
 def fixture(self):
  docs={};files={}
  def add(p):
   p=str(p);docs[p]=json.loads(Path(p).read_bytes());files[p]=Q.sha(p);return docs[p]
  def ref(p):return {'path':str(p),'sha256':files[str(p)]}
  plan=add(Q.K0_CURRENT_PLAN);root=Path(plan['out']);config=add(BASE/'CONFIG.json');ops=add(BASE/'OPERATIONS.json');review=add(REVIEW)
  for path,pin in {**config['files'],**ops['files']}.items():files[path]=pin
  for p in [root/'attempts/1/report.json',root/'attempts/1/EXIT.json',root/'host_attempts/1/EXIT.json',root/'host_attempts/1/CLAIM.json',root/'host_attempts/1/RELEASE.json',root/'cpu/1/EXIT.json',plan['sample']['path']]:add(p)
  cpu=Path(config['out']);host=Path(ops['host_output'])
  for p in [cpu/'report.json',cpu/'COMPLETE.json',cpu/'EXIT.json',host/'EXIT.json',host/'LAUNCH_RECEIPT.json']:add(p)
  targets={k:{z:v[z] for z in ('execution','report','model')} for k,v in plan['targets'].items()}
  for t in targets.values():
   for k in ('execution','report'):files[t[k]['path']]=t[k]['sha256']
  receipt=docs[str(host/'LAUNCH_RECEIPT.json')];cmd=ops['docker_command'];mounts=[]
  for i,t in enumerate(cmd):
   if t=='--mount':
    fields=cmd[i+1].split(',');m=dict(x.split('=',1) for x in fields if '=' in x);mounts.append(dict(Type='bind',Source=m['src'],Destination=m['dst'],RW='readonly' not in fields))
  actual={'Id':receipt['container_id'],'Name':'/'+cmd[cmd.index('--name')+1],'Image':ops['image'],'Config':{'Cmd':receipt['command'],'Env':[cmd[i+1] for i,t in enumerate(cmd) if t=='-e']},'State':{'Status':'exited','Running':False,'ExitCode':0,'OOMKilled':False,'StartedAt':'2026-11-03T07:50:28Z','FinishedAt':'2026-11-03T07:52:30Z'},'HostConfig':{'Devices':[],'Privileged':False,'AutoRemove':False,'NetworkMode':'none'},'Mounts':mounts}
  ap='/synthetic/in-memory-only/actual.json';docs[ap]=actual;files[ap]='f'*64
  identity={'schema':'r3-k0-current-identity-acceptance-v2','verdict':'PASS','scientific_acceptance':False,'test_read':False,'independent_reconstruction':True,'lifecycle_verified':True,'reviewer':'synthetic fixture, not real review','control_plan':ref(Q.K0_CURRENT_PLAN),'attempt':1,'controls_report':ref(cpu/'report.json'),'sample_sha1':docs[plan['sample']['path']]['sample_sha1'],'targets':targets,'cpu_continuation':{'schema':'r3-k0-cpu-continuation-binding-v1','config':ref(BASE/'CONFIG.json'),'operations':ref(BASE/'OPERATIONS.json'),'launch_review':ref(REVIEW),'actual_container':{'path':ap,'sha256':'f'*64}}}
  entry={'arm':'K0','execution':targets['base']['execution']['path'],'report':targets['base']['report']['path'],'model':targets['base']['model']}
  def bound(p,f):
   if str(p) not in f:raise ValueError('unbound fixture')
   return docs[str(p)]
  return identity,entry,files,types.SimpleNamespace(bound=bound),docs,config,ops,actual
 def test_valid_legacy_data_with_synthetic_observation_in_memory(self):
  i,e,f,q,d,c,o,a=self.fixture();r=Q.k0_identity_acceptance('k0_base',e,i,f,q);self.assertEqual(r['controls_report_sha256'],f[str(Path(c['out'])/'report.json')])
 def test_binding_and_scope_reject(self):
  for change in ('missing_binding','foreign_schema','missing_actual','unbound_config','generic_review','no_reconstruction','legacy_schema'):
   i,e,f,q,d,c,o,a=self.fixture()
   if change=='missing_binding':i.pop('cpu_continuation')
   if change=='foreign_schema':i['cpu_continuation']['schema']='foreign'
   if change=='missing_actual':i['cpu_continuation'].pop('actual_container')
   if change=='unbound_config':f.pop(str(BASE/'CONFIG.json'))
   if change=='generic_review':d[str(REVIEW)]['verdict']='PASS'
   if change=='no_reconstruction':i['independent_reconstruction']=False
   if change=='legacy_schema':i['schema']='r3-k0-current-identity-acceptance-v1'
   with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):Q.k0_identity_acceptance('k0_base',e,i,f,q)
 def test_continuation_terminals_and_generation_reject(self):
  for target,key,value in [('runtime','exit_code',False),('runtime','exit_code',1),('runtime','npu_attempt',True),('runtime','config_sha256','foreign'),('host','exit_code',False),('host','operations_sha256','foreign'),('summary','npu_attempt',True),('summary','config_sha256','foreign'),('summary','original_plan_sha256','foreign'),('summary','controls',{}),('complete','exit_code',False),('complete','report_sha256','foreign'),('failed','exit_code',0),('failed','exit_code',True),('failed','attempt',True),('receipt','container_id','b'*64),('receipt','operations_sha256','foreign')]:
   i,e,f,q,d,c,o,a=self.fixture();cpu=Path(c['out']);host=Path(o['host_output']);paths={'runtime':cpu/'EXIT.json','summary':cpu/'report.json','complete':cpu/'COMPLETE.json','host':host/'EXIT.json','receipt':host/'LAUNCH_RECEIPT.json','failed':c['failed_cpu_terminal']['path']};d[str(paths[target])][key]=value
   with self.subTest(target=target,key=key,value=value),self.assertRaises((ValueError,KeyError)):Q.k0_identity_acceptance('k0_base',e,i,f,q)
 def test_actual_container_isolation_and_command_reject(self):
  for target,key,value in [('State','ExitCode',False),('State','Status','running'),('State','OOMKilled',True),('State','StartedAt','2026-11-03T01:00:00Z'),('HostConfig','Devices',[{}]),('HostConfig','Privileged',True),('HostConfig','AutoRemove',True),('HostConfig','NetworkMode','host'),('Config','Cmd',[]),('Config','Env',[])]:
   i,e,f,q,d,c,o,a=self.fixture();a[target][key]=value
   with self.subTest(target=target,key=key),self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,i,f,q)
  i,e,f,q,d,c,o,a=self.fixture();a['Mounts'][0]['RW']=1
  with self.assertRaises(ValueError):Q.k0_identity_acceptance('k0_base',e,i,f,q)
 def test_config_and_launch_review_mutations_reject(self):
  for change in ('attempt','plan','output','runner','consumer','opsconfig','reviewconfig','reviewsource','pred','source','writable'):
   i,e,f,q,d,c,o,a=self.fixture()
   if change=='attempt':c['npu_attempt']=True
   if change=='plan':c['original_plan']={}
   if change=='output':c['out']=str(Q.K0_CURRENT_PLAN.parent/'output/cpu/1')
   if change=='runner':c['runner']['sha256']='0'*64
   if change=='consumer':c['consumer']['sha256']='0'*64
   if change=='opsconfig':o['config_sha256']='foreign'
   if change=='reviewconfig':d[str(REVIEW)]['approved_config']={}
   if change=='reviewsource':d[str(REVIEW)]['source_and_input_pins']={}
   if change=='pred':c['failed_cpu_terminal']={}
   if change=='source':c['files'][str(BASE/'r3_k0_cpu_continuation.py')]='0'*64
   if change=='writable':
    pos=o['docker_command'].index('--mount')+1;o['docker_command'][pos]=o['docker_command'][pos].replace(',readonly','')
   with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):Q.k0_identity_acceptance('k0_base',e,i,f,q)

if __name__=='__main__':unittest.main()
