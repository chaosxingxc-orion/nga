import contextlib,io,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from tools import bev_native_config_runtime as R, bev_native_config_resource as Q, bev_native_config_host as H
class ConfigExecution(unittest.TestCase):
 def test_duplicate_json(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x';p.write_text('{"a":1,"a":2}')
   with self.assertRaises(ValueError):R.read(p)
 def test_queue_priority_and_coverage(self):
  d={'allocation':'/a','chip':0,'run':'new','queue':{'path':'q'}}
  q={'schema':'native-ready-queue-v1','allocation':'/a','writer_lock':'/a.lock','coverage':'all_ready_tasks','accepted_for_dispatch':True,'generation':1,'tasks':[]}
  resource=types.SimpleNamespace(load=lambda p:q,live_chip_conflict=lambda c,n:False,sha_bytes=lambda x:'h',read_bytes=lambda p:b'fixed')
  self.assertEqual(Q.queue_guard(d,resource)['queue_generation'],1)
  q['tasks']=[{'id':'prior','state':'ready','chips':[0]}]
  with self.assertRaisesRegex(ValueError,'priority'):Q.queue_guard(d,resource)
  q['tasks'][0]['chips']=[1];Q.queue_guard(d,resource)
  q['accepted_for_dispatch']=False
  with self.assertRaisesRegex(ValueError,'coverage'):Q.queue_guard(d,resource)
 def test_live_conflict(self):
  q={'schema':'native-ready-queue-v1','allocation':'/a','writer_lock':'/a.lock','coverage':'all_ready_tasks','accepted_for_dispatch':True,'generation':1,'tasks':[]}
  resource=types.SimpleNamespace(load=lambda p:q,live_chip_conflict=lambda c,n:True)
  with self.assertRaisesRegex(ValueError,'device'):Q.queue_guard({'allocation':'/a','chip':0,'run':'new','queue':{'path':'q'}},resource)
 def test_commands_vary_by_configuration(self):
  d={'container':'x','chip':0,'environment':{},'mounts':[],'image_sha256':'sha256:x','runtime':{'path':'/runtime'}}
  a=H.command(d,'/plan','pin',1);b=H.command({**d,'chip':6,'container':'y'},'/plan2','pin2',2)
  self.assertIn('/dev/davinci0',a);self.assertIn('/dev/davinci6',b);self.assertIn('y-a2',b);self.assertNotIn('--rm',a)
 def test_startup_failure_terminal(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'plan';out=Path(t)/'out';p.write_text(json.dumps({'out':str(out)}));pin=R.sha(p)
   with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(ValueError):R.run(str(p),pin,1)
   end=R.read(out/'attempts/1/EXIT.json');self.assertEqual(end['exit_code'],1);self.assertEqual(end['plan_sha256'],pin)
 def test_queue_malformed_identity(self):
  d={'allocation':'/a','chip':0,'run':'new','queue':{'path':'q'}}
  q={'schema':'native-ready-queue-v1','allocation':'/a','writer_lock':'/a.lock','coverage':'all_ready_tasks','accepted_for_dispatch':True,'generation':True,'tasks':[]}
  resource=types.SimpleNamespace(load=lambda p:q)
  with self.assertRaises(ValueError):Q.queue_guard(d,resource)
 def test_host_releases_exited_container_but_rejects_invalid_terminal(self):
  good={'exit_code':0,'plan_sha256':'real','attempt':1,'scientific_acceptance':False}
  cases=[good,*[dict(good,**{k:v}) for k,v in [('exit_code',False),('exit_code',0.0),('plan_sha256','foreign'),('attempt',True),('attempt',99),('scientific_acceptance',True),('execution_authorized',True),('container_id','foreign')]]]
  for terminal in cases:
   with self.subTest(terminal=terminal),tempfile.TemporaryDirectory() as td:
    root=Path(td);h=root/'host_attempts/1';h.mkdir(parents=True);a=root/'attempts/1';a.mkdir(parents=True);(a/'EXIT.json').write_text(json.dumps(terminal))
    d={'out':str(root),'modules':{'resource_base':{}},'resource':{'path':'/unused'},'container':'test','chip':0,'image_sha256':'image'}
    actual={'Id':'a'*64,'Image':'image','HostConfig':{'AutoRemove':False},'Config':{'Cmd':['runtime']},'State':{'Status':'exited','ExitCode':0}}
    seen=[];calls=[]
    def inspect(n):seen.append(n);return None if len(seen)==1 else actual
    def subprocess_run(cmd,**kw):calls.append(cmd);return types.SimpleNamespace(returncode=0)
    fake=types.SimpleNamespace(wait=lambda timeout:0,terminate=lambda:None);args=types.SimpleNamespace(plan='/plan',sha256='real',review='/review',review_sha256='review',attempt=1)
    with patch.object(H,'verify',return_value=d),patch.object(H,'approval'),patch.object(H,'preflight'),patch.object(H,'module',return_value=types.SimpleNamespace(live_chip_conflict=lambda c,n:False)),patch.object(H,'inspect',side_effect=inspect),patch.object(H,'command',return_value=['docker','run','image','runtime']),patch.object(H.subprocess,'run',side_effect=subprocess_run),patch.object(H.subprocess,'Popen',return_value=fake):H.supervise(args)
    result=json.loads((h/'EXIT.json').read_text());self.assertEqual(result['runner_terminal_matches'],terminal is good);self.assertEqual(result['exit_code'],0 if terminal is good else 1);self.assertTrue(any('release' in cmd for cmd in calls))
 def test_chip_scoped_queue_requires_pinned_admission_and_writer(self):
  q={'schema':'native-ready-queue-v1','allocation':'/a','writer_lock':'/a.lock','coverage':'chip_ready_tasks','chips':[0],'accepted_for_dispatch':True,'generation':1,'tasks':[],'writer':{'path':'writer','sha256':'h'}}
  auth={'schema':'native-chip-queue-admission-v1','allocation':'/a','writer_lock':'/a.lock','queue_path':'q','chips':[0],'writer':q['writer'],'accepted_for_dispatch':True,'scientific_acceptance':False}
  resource=types.SimpleNamespace(load=lambda p:q if p=='q' else auth,read_bytes=lambda p:b'fixed',sha_bytes=lambda x:'h',live_chip_conflict=lambda c,n:False)
  d={'allocation':'/a','chip':0,'run':'new','queue':{'path':'q','admission':{'path':'auth','sha256':'h'}}}
  self.assertEqual(Q.queue_guard(d,resource)['queue_generation'],1)
  auth['accepted_for_dispatch']=False
  with self.assertRaises(ValueError):Q.queue_guard(d,resource)
  auth['accepted_for_dispatch']=True;q['chips']=[1]
  with self.assertRaises(ValueError):Q.queue_guard(d,resource)
 def test_previous_attempt_exact_generation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);h=root/'host_attempts/1';h.mkdir(parents=True)
   d={'out':str(root),'container':'test','chip':0,'run':'r','image_sha256':'image'}
   claim={'schema':'r3-resource-claim-v1','run':'r','chip':0};(h/'CLAIM.json').write_text(json.dumps(claim))
   rel={'schema':'r3-resource-release-v1','run':'r','chip':0,'claim_sha256':H.sha(h/'CLAIM.json'),'scientific_acceptance':False,'exit_code':1,'container':'test-a1','container_id':'a'}
   end={'container_id':'a','plan_sha256':'pin','attempt':1,'scientific_acceptance':False,'exit_code':1,'container_exit_code':1,'runner_terminal_matches':True}
   receipt={'container_id':'a','plan_sha256':'pin','attempt':1,'scientific_acceptance':False,'command':['runtime']};spec={'plan_sha256':'pin','command':['docker','image','runtime']}
   actual={'Id':'a','Image':'image','Config':{'Cmd':['runtime']},'State':{'Status':'exited','Running':False,'ExitCode':1}}
   docs={'RELEASE.json':rel,'EXIT.json':end,'LAUNCH_RECEIPT.json':receipt,'LAUNCH_SPEC.json':spec}
   for name,v in docs.items():(h/name).write_text(json.dumps(v))
   with patch.object(H,'inspect',return_value=actual):H.previous(d,2,'pin')
   for name,key,value in [('RELEASE.json','chip',False),('RELEASE.json','exit_code',True),('EXIT.json','attempt',True),('EXIT.json','exit_code',True),('EXIT.json','plan_sha256','foreign'),('LAUNCH_RECEIPT.json','scientific_acceptance',True)]:
    with self.subTest(name=name,key=key):
     (h/name).write_text(json.dumps({**docs[name],key:value}))
     with patch.object(H,'inspect',return_value=actual),self.assertRaises(ValueError):H.previous(d,2,'pin')
     (h/name).write_text(json.dumps(docs[name]))
if __name__=='__main__':unittest.main()
