import hashlib, importlib.util, json, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import site_dependencies as s
REPO=Path(__file__).resolve().parents[7]
K=REPO/'tools/functional_dev/matched_k0'
Q=REPO/'.local/releases/engineering-base-rc1/tasks/execution/qwen38-host-bind/package/adapter/group_adapter.py'
def put(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def module(p):
 spec=importlib.util.spec_from_file_location('group',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class Callbacks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.cid='a'*64
 def docker(self,name,image,chips):return {'Id':self.cid,'Name':'/'+name,'Image':image,'State':{'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci'+str(i)} for i in chips]}}
 def kfixture(self):
  src=self.root/'src';shutil.copytree(K,src);c=json.loads((src/'config.json').read_text());c['root']=str(self.root);put(src/'config.json',c)
  pins={n:s.sha(src/n) for n in s.KPINS};out=self.root/'matched-k0-clean-dev';d=out/'08b-k0';result=d/'result';model=c['models'][0];desc={'record_grade':True,'mode':'rightpad','token_budget':16384};m=model['model']
  header={'model':m,'arm':'K0','stages':'k_score','device':'npu','dtype':'float32','limit':0,'limit_groups':0,'partitions':['dev','calibration'],'primary_input_mode':'full','scorer':desc,'dry_run_warnings':[]}
  stores={}
  for group,n in zip(['decision-v7/calibration/clean','decision-v7/dev/clean','transfer-v4/dev/clean'],[1148,1264,656]):
   suite,part,kind=group.split('/');p=result/'trackk'/(suite+'__'+part)/(kind+'.jsonl');p.parent.mkdir(parents=True,exist_ok=True);p.write_text('frozen store\n');Path(str(p)+'.receipt.json').write_text('{}\n');stores[group]={'store_sha256':s.sha(p),'receipt_sha256':s.sha(str(p)+'.receipt.json'),'rows':n}
  put(result/'INFERENCE-READY.json',{'version':1,'model_id':'08b-k0','identity':dict(m,files=model['weight_shard_pins']),'out':str(result),'groups':list(stores),'descriptor':desc,'stores':stores,'inference_header':header,'config_sha256':s.sha(src/'config.json')})
  cmd=['docker','run','-d','--device','/dev/davinci4',s.KIMAGE,'--phase','infer','--model-id','08b-k0'];put(d/'infer-COMMAND.json',cmd);put(d/'infer-LAUNCH.json',{'container_id':self.cid,'chip':4,'command_sha256':s.sha(d/'infer-COMMAND.json'),'started':'frozen'})
  put(d/'infer-EXIT.json',{'container_id':self.cid,'exit_code':0,'container_exit_code':0,'finished_at':'frozen','artifact_evidence':{'inference_sha256':s.sha(result/'INFERENCE-READY.json'),'stores':stores}})
  review=self.root/'review';review.write_text('accepted\n');put(out/'REVIEW-APPROVED.json',dict(verdict='pass',review_artifact=str(review),review_artifact_sha256=s.sha(review),**{n.replace('.','_')+'_sha256':s.sha(src/n) for n in ('queue.py','producer.py','config.json','compare_dev.py','host_ownership_probe.py')}))
  return src,pins,d
 def qfixture(self):
  group=module(Q);alloc=self.root/'allocation.json';chips=[0,1,2,3];name='qwen38-dev-host-smoke-rc1';out=self.root/'out';d=out/'attempts'/name;d.mkdir(parents=True);put(alloc,{'allocation':[],'free':[{'chip':i} for i in range(8)]})
  docker=self.docker(name,s.QIMAGE,chips)
  with patch.object(group.r3,'live_chip_conflict',return_value=False),patch.object(group.r3,'docker_inspect',return_value=docker):
   group.transact('claim',str(alloc),chips,name,d/'CLAIM.json');group.transact('release',str(alloc),chips,name,d/'RELEASE.json',claim_path=d/'CLAIM.json',container=name,container_id=self.cid)
  put(d/'CONTAINER.json',{'id':self.cid,'name':name});put(d/'EXIT.json',{'exit_code':0,'utc':'frozen'});put(d/'TERMINAL.json',{'container_id':self.cid,'name':name,'exit_code':0,'result':'success','exit_marker_present':True,'utc':1});put(d/'HOST-RELEASE-CHECK.json',{'chips':chips,'certain':True,'unmanaged_owners':[]})
  cmd=['docker','run','-d']+sum((['--device','/dev/davinci'+str(i)] for i in chips),[])+['--mount','type=bind,src=/mnt/cephfs/models/Qwen3.8-27B,dst=/run/model,readonly',s.QIMAGE,'--model','/run/model'];put(d/'COMMAND.json',{'docker':cmd,'source_pins':{},'relaunch_argv':[],'chips':chips,'note':'claim retained until detached controller confirms and releases'})
  qr=self.root/'qroot';(qr/'package').mkdir(parents=True);c={'schema':'qwen38-dev-controller-v1','chips':chips,'name':name,'out':str(out),'allocation':str(alloc),'host_ownership_probe':'probe','source_pins':{}};put(qr/'CONFIG.json',c)
  return qr,d,docker
 def test_k0_producer_format_and_faults(self):
  src,pins,d=self.kfixture();docker=self.docker('nga-rc1-matched-k0-08b-k0-infer',s.KIMAGE,[4])
  with patch.object(s,'K0',src),patch.object(s,'KPINS',pins),patch.object(s,'inspect',return_value=docker),patch('subprocess.run'):
   # Mock only host observation, leaving review, receipt, producer and store checks real.
   with patch.object(s,'mod',wraps=s.mod) as load:
    def patched(p):
     q=load(p);q.HP.check=lambda chips:{'certain':True,'unmanaged_owners':[]};return q
    with patch.object(s,'mod',side_effect=patched):
     self.assertEqual(s.k0(4),'ready')
     for field,val in [('Image','wrong'),('HostConfig',{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci5'}]})]:
      bad=dict(docker,**{field:val})
      with patch.object(s,'inspect',return_value=bad),self.assertRaises(ValueError):s.k0(4)
     p=d/'infer-LAUNCH.json';orig=p.read_text();v=json.loads(orig);v['chip']=5;put(p,v)
     with self.assertRaises(ValueError):s.k0(4)
     p.write_text(orig);v=json.loads((d/'result/INFERENCE-READY.json').read_text());v['config_sha256']='wrong';r=d/'result/INFERENCE-READY.json';saved=r.read_text();put(r,v)
     with self.assertRaises(ValueError):s.k0(4)
     r.write_text(saved);p=d/'infer-EXIT.json';orig=p.read_text();v=json.loads(orig);v['exit_code']=1;put(p,v)
     with self.assertRaises(ValueError):s.k0(4)
     p.write_text(orig);(d/'result/INFERENCE-READY.json').unlink()
     with self.assertRaises(ValueError):s.k0(4)
     (d/'infer-EXIT.json').unlink();self.assertEqual(s.k0(4),'pending')
 def test_qwen_group_receipts_and_faults(self):
  qr,d,docker=self.qfixture()
  class Result:
   returncode=0;stdout=json.dumps({'chips':[0,1,2,3],'certain':True,'unmanaged_owners':[]})
  with patch.object(s,'QROOT',qr),patch.object(s,'QCONFIG',s.sha(qr/'CONFIG.json')),patch.object(s,'inspect',return_value=docker),patch.object(s.subprocess,'run',return_value=Result()):
   self.assertEqual(s.qwen(0),'ready')
   for field,val in [('Image','wrong'),('HostConfig',{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci0'}]})]:
    with patch.object(s,'inspect',return_value=dict(docker,**{field:val})),self.assertRaises(ValueError):s.qwen(0)
   for filename,key,value in [('RELEASE.json','claim_sha256','bad'),('CLAIM.json','after_sha256','bad'),('EXIT.json','exit_code',1),('COMMAND.json','chips',[1,2,3,4]),('CONTAINER.json','name','wrong')]:
    p=d/filename;raw=p.read_text();v=json.loads(raw);v[key]=value;put(p,v)
    with self.assertRaises(ValueError,msg=filename):s.qwen(0)
    p.write_text(raw)
   p=d/'CLAIM.json';raw=p.read_text();p.unlink()
   with self.assertRaises(ValueError):s.qwen(0)
   p.write_text(raw);(d/'RELEASE.json').unlink();(d/'TERMINAL.json').unlink();self.assertEqual(s.qwen(0),'pending')
   with patch.object(s,'QCONFIG','bad'),self.assertRaises(ValueError):s.qwen(0)
   (qr/'package').mkdir(exist_ok=True);(self.root/'out/CONTROLLER-ESCALATION.json').write_text('{}')
   with self.assertRaises(ValueError):s.qwen(0)
if __name__=='__main__':unittest.main()
