"""Generated receipt fixtures through exact callback CLI; only Docker/host observations synthetic."""
import hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parent
REPO=next(p for p in B.parents if (p/'tools/functional_dev/matched_k0').exists())
K=REPO/'tools/functional_dev/matched_k0'
Q=B/'callback_fixture'
CALL=B/'site_dependencies.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def module(p):
 s=importlib.util.spec_from_file_location('fixture_module',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class CallbackCLI(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name);r=self.r;self.objects={};self.a='a'*64;self.b='b'*64;self.c='c'*64
  self.k=r/'k';shutil.copytree(K,self.k);c=json.loads((self.k/'config.json').read_text());c['root']=str(r);put(self.k/'config.json',c);self.cmodels=c['models'];self.image=c['image'];self.out=r/'matched-k0-clean-dev'
  probe="import json,os\nfrom pathlib import Path\ndef check(chips):\n d=json.loads(Path(os.environ['FIXTURE_OBSERVATIONS']).read_text());return {'certain':True,'chips':chips,'unmanaged_owners':d['owners']}\n"
  (self.k/'host_ownership_probe.py').write_text(probe)
  self.bin=r/'bin';self.bin.mkdir();docker=self.bin/'docker';docker.write_text('#!'+sys.executable+"\nimport os,sys,json\nfrom pathlib import Path\nassert sys.argv[1]=='inspect'\nd=json.loads(Path(os.environ['FIXTURE_OBSERVATIONS']).read_text());print(json.dumps([d['containers'][sys.argv[2]]]))\n");docker.chmod(0o755)
  review=r/'review';review.write_text('fixture only\n');put(self.out/'REVIEW-APPROVED.json',dict(verdict='pass',review_artifact=str(review),review_artifact_sha256=sha(review),**{n.replace('.','_')+'_sha256':sha(self.k/n) for n in ('queue.py','producer.py','config.json','compare_dev.py','host_ownership_probe.py','resource.json')}))
  self.contract={'k0_source':str(self.k),'k0_pins':{n:sha(self.k/n) for n in ('queue.py','producer.py','config.json','host_ownership_probe.py','resource.json')},'k0_container_ids':{str(i):self.a for i in range(4)},'qwen_root':str(r/'q'),'qwen_config_sha256':'unused','qwen_queue_pins':{},'qwen_image':'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'}
  self.owners=[];self.observe()
 def obj(self,cid,name,chips,image=None,code=0):
  o={'Id':cid,'Name':'/'+name,'Image':image or self.image,'State':{'Status':'exited','ExitCode':code},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci'+str(i)} for i in chips]}};self.objects[cid]=o;return o
 def observe(self):put(self.r/'observations.json',{'containers':self.objects,'owners':self.owners})
 def invoke(self,dep,chip,source_hash=None):
  self.observe();cp=self.r/'DEPENDENCY-CONTRACT.json';put(cp,self.contract)
  # Same configured command shape as production CALLBACKS; fixture substitutions are paths and pins.
  argv=[sys.executable,'-B','-P',str(CALL),dep,'--contract',str(cp),'--contract-sha256',sha(cp),'--source-sha256',source_hash or sha(CALL)]
  put(self.r/'CALLBACKS.json',{dep:argv});argv=json.loads((self.r/'CALLBACKS.json').read_text())[dep]+['--chip',str(chip)]
  p=subprocess.run(argv,env={**os.environ,'PATH':str(self.bin)+':'+os.environ['PATH'],'FIXTURE_OBSERVATIONS':str(self.r/'observations.json')},capture_output=True,text=True,timeout=15)
  self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
 def kfixture(self):
  q=module(self.k/'queue.py');d=self.out/'08b-k0';result=d/'result';model=self.cmodels[0];m=model['model'];desc={'record_grade':True,'mode':'rightpad','token_budget':16384}
  header={'model':m,'arm':'K0','stages':'k_score','device':'npu','dtype':'float32','limit':0,'limit_groups':0,'partitions':['dev','calibration'],'primary_input_mode':'full','scorer':desc,'dry_run_warnings':[]};stores={}
  for group,n in zip(q.P.GROUPS,q.P.COUNTS):
   suite,part,kind=group.split('/');p=result/'trackk'/(suite+'__'+part)/(kind+'.jsonl');p.parent.mkdir(parents=True,exist_ok=True);p.write_text('generated fixture store\n');Path(str(p)+'.receipt.json').write_text('{}\n');stores[group]={'store_sha256':sha(p),'receipt_sha256':sha(str(p)+'.receipt.json'),'rows':n}
  put(result/'INFERENCE-READY.json',{'version':1,'model_id':'08b-k0','identity':dict(m,files=model['weight_shard_pins']),'out':str(result),'groups':list(stores),'descriptor':desc,'stores':stores,'inference_header':header,'config_sha256':sha(self.k/'config.json')})
  cmd=['docker','run','-d','--device','/dev/davinci0',self.image,'--phase','infer','--model-id','08b-k0'];put(d/'infer-COMMAND.json',cmd);put(d/'infer-LAUNCH.json',{'container_id':self.a,'chip':0,'command_sha256':sha(d/'infer-COMMAND.json')});put(d/'infer-EXIT.json',{'container_id':self.a,'exit_code':0,'container_exit_code':0,'artifact_evidence':q.artifact_evidence('08b-k0',result,'infer')});self.obj(self.a,'nga-rc1-matched-k0-08b-k0-infer',[0]);return d
 def trainfixture(self):
  q=module(self.k/'queue.py');lane='q4b-s2';entry=next(x for x in q.DEFAULT_RESOURCE['jobs'] if x['lane']==lane);train=self.r/lane;dev=self.r/'followup-cpu-separated-rc1'/('full-'+lane);d=train/'result/adapter';bind={'owner':'rc1-functional-'+lane};put(d/'BINDING.json',bind);put(d/'PUBLICATION.json',{'binding':bind});put(train/'train-LAUNCH.json',{'phase':'train','chip':4,'container_id':self.a,'config_sha256':entry['train_config']});put(train/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False});put(dev/'infer-EXIT.json',{'container_id':self.b,'exit_code':0,'container_exit_code':0});put(dev/'infer-BINDING.json',{'binding':bind,'publication_sha256':sha(d/'PUBLICATION.json')})
  m=next(x['model'] for x in q.C['models'] if x['id']==entry['dev_model']);put(dev/'infer-COMMAND.json',['--model',m['path'],'--adapter',str(d),'--phase','infer']);put(dev/'infer-LAUNCH.json',{'chip':4,'container_id':self.b,'command_sha256':sha(dev/'infer-COMMAND.json')});put(dev/'result/INFERENCE-READY.json',{'version':1,'model':m['path'],'adapter':str(d),'out':'/run/output/result','limit':0,'inference_header':{'stages':'k_score','model':{'base_path':m['base_path'],'base_revision':m['base_revision']}}});self.obj(self.a,'nga-rc1-'+lane+'-train',[4]);self.obj(self.b,'nga-rc1-cpu-full-'+lane+'-infer',[4]);return train,dev
 def qfixture(self,code=0):
  qr=self.r/'q';shutil.copytree(Q/'package',qr/'package');probe=qr/'package/host_ownership_probe.py';probe.write_text('#!'+sys.executable+"\nimport json,os\nfrom pathlib import Path\nd=json.loads(Path(os.environ['FIXTURE_OBSERVATIONS']).read_text());print(json.dumps({'certain':True,'chips':[0,1,2,3],'unmanaged_owners':d['owners']}))\n");probe.chmod(0o755)
  c=json.loads((Q/'CONFIG.json').read_text());c.update(out=str(self.r/'qout'),allocation=str(self.r/'allocation.json'),host_ownership_probe=str(probe));c['source_pins']={n:sha(qr/'package'/n) for n in c['source_pins']};put(qr/'CONFIG.json',c);self.contract['qwen_config_sha256']=sha(qr/'CONFIG.json');self.contract['qwen_queue_pins']={'CONFIG.json':sha(qr/'CONFIG.json')};put(c['allocation'],{'allocation':[],'free':[{'chip':i} for i in range(8)]});d=Path(c['out'])/'attempts'/c['name'];d.mkdir(parents=True)
  obj=self.obj(self.c,c['name'],[0,1,2,3],self.contract['qwen_image'],code);g=module(qr/'package/adapter/group_adapter.py')
  with patch.object(g.r3,'live_chip_conflict',return_value=False),patch.object(g.r3,'docker_inspect',return_value=obj):
   g.transact('claim',c['allocation'],c['chips'],c['name'],d/'CLAIM.json');g.transact('release',c['allocation'],c['chips'],c['name'],d/'RELEASE.json',claim_path=d/'CLAIM.json',container=c['name'],container_id=self.c)
  put(d/'CONTAINER.json',{'id':self.c,'name':c['name']});put(d/'EXIT.json',{'exit_code':code});put(d/'TERMINAL.json',{'container_id':self.c,'name':c['name'],'exit_code':code,'result':'success' if code==0 else 'failed','exit_marker_present':True});put(d/'HOST-RELEASE-CHECK.json',{'chips':c['chips'],'certain':True,'unmanaged_owners':[]})
  names=('DEV-MASKS.json','WORKLOAD.json','TENSOR-DIFF.json','code/core.py','code/prompt.py','code/raw_loading.py','code/score.py','code/inner.sh','code/cpu_reference.py','launch.py','controller.py','adapter/group_adapter.py','adapter/r3_resource_adapter.py')
  cmd=['docker','run','-d']+sum((['--device','/dev/davinci'+str(i)] for i in c['chips']),[])+['--mount','type=bind,src=/mnt/cephfs/models/Qwen3.8-27B,dst=/run/model,readonly',self.contract['qwen_image'],'--model','/run/model'];put(d/'COMMAND.json',{'chips':c['chips'],'docker':cmd,'source_pins':{n:c['source_pins'][n] for n in names}});return d
 def test_missing_pending_and_source_change(self):
  self.assertEqual(self.invoke('K0',0)['status'],'pending');self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'pending');self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'pending');self.assertEqual(self.invoke('K0',0,'0'*64)['status'],'failed');(self.k/'queue.py').write_text('changed');self.assertEqual(self.invoke('K0',0)['status'],'failed')
 def test_k0_real_artifacts_busy_failed_changed_identity(self):
  d=self.kfixture();put(self.out/'08b-k0-ERROR.json',{'error':'later CPU score failure; not inference release'});self.assertEqual(self.invoke('K0',0)['status'],'ready');self.owners=[{'pid':123}];self.assertEqual(self.invoke('K0',0)['status'],'pending');self.owners=[];self.objects[self.a]['State']['Status']='running';self.assertEqual(self.invoke('K0',0)['status'],'pending');self.objects[self.a]['State']['Status']='exited';self.objects[self.a]['Id']='f'*64;self.assertEqual(self.invoke('K0',0)['status'],'failed');self.objects[self.a]['Id']=self.a;put(d/'infer-EXIT.json',{'exit_code':1,'container_exit_code':1});self.assertEqual(self.invoke('K0',0)['status'],'failed');(d/'infer-EXIT.json').unlink();self.assertEqual(self.invoke('K0',0)['status'],'pending')
 def test_train_dev_real_ready_busy_failed_identity(self):
  train,dev=self.trainfixture();self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'ready');self.owners=[1];self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'pending');self.owners=[];self.objects[self.a]['State']['Status']='running';self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'pending');self.objects[self.a]['State']['Status']='exited';self.objects[self.b]['Name']='/wrong';self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'failed');self.objects[self.b]['Name']='/nga-rc1-cpu-full-q4b-s2-infer';put(train/'COMPLETE.json',{'exit_code':1});self.assertEqual(self.invoke('TRAIN_DEV',4)['status'],'failed')
 def test_retry_success_busy_missing_release_and_changed_identity(self):
  d=self.qfixture();self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'ready');self.owners=[1];self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'pending');self.owners=[];self.objects[self.c]['State']['Status']='running';self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'pending');self.objects[self.c]['State']['Status']='exited';self.objects[self.c]['Image']='wrong';self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed');self.objects[self.c]['Image']=self.contract['qwen_image'];(d/'RELEASE.json').unlink();self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'pending')
 def test_old_failure_cannot_satisfy_new_retry_and_incomplete_terminal(self):
  d=self.qfixture(1);old=self.r/'old-failed-attempt';shutil.move(str(d),old);self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'pending');shutil.move(str(old),d);(d/'CLAIM.json').unlink();self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed')
 def test_failed_retry_released_is_resource_only(self):
  d=self.qfixture(1);v=self.invoke('QWEN27B_ENVFIX',0);self.assertEqual(v['status'],'ready');self.assertIn('no scientific acceptance',v['scope']);put(d/'EXIT.json',{'exit_code':0});self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed')
 def test_retry_source_queue_and_release_pins(self):
  d=self.qfixture();p=d/'RELEASE.json';v=json.loads(p.read_text());v['claim_sha256']='wrong';put(p,v);self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed');(self.r/'q/package/controller.py').write_text('changed');self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed');(self.r/'q/CONFIG.json').write_text('{}');self.assertEqual(self.invoke('QWEN27B_ENVFIX',0)['status'],'failed')
if __name__=='__main__':unittest.main(verbosity=2)
