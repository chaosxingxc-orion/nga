import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_ownership_probe as probe
import waiter

class TestHost(unittest.TestCase):
 def test_process_grammar(self):
  self.assertEqual(probe.processes('NPU ID : 0\nChip Count : 1\nNo process in device.\nChip ID : 0\n',0),[])
  self.assertEqual(probe.processes('NPU ID : 0\nChip Count : 1\nProcess id:77 Process name:python3 Process memory(MB):42\nChip ID : 0\n',0),[77])
  for x in ('', 'NPU ID : 0\nChip Count : 1\nwhat\nChip ID : 0'):
   with self.assertRaises(ValueError): probe.processes(x,0)
 def test_listing(self):
  h='npu-smi 26\n| NPU     Chip              | Process id    | Process name | Process memory(MB) | Process id in container |\n'
  free=''.join('| No running processes found in NPU %d |\n'%i for i in range(4))
  self.assertEqual(probe.listing(h+free,[0,1,2,3])[0],[])
  busy=free.replace('| No running processes found in NPU 0 |','| 0 0 | 77 | python3 | 42 | NA |')
  self.assertEqual(probe.listing(h+busy,[0,1,2,3])[0],[77])
  with self.assertRaises(ValueError):probe.listing(h+free+'| unknown |\n',[0,1,2,3])
 def test_queue_wait_and_failure(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);train=root/'train';dev=root/'dev';train.mkdir();dev.mkdir();cid='a'*64
   c={'dev_dependency':{'launch_file':'infer-LAUNCH.json','exit_file':'infer-EXIT.json','artifact_file':'result/INFERENCE-READY.json','container_name_template':'nga-rc1-cpu-full-{id}-infer'},'dependencies':[{'chip':0,'id':'x','train':str(train),'dev':str(dev)}]}
   (train/'train-LAUNCH.json').write_text(json.dumps({'chip':0,'phase':'train','container_id':cid}))
   with patch.object(waiter,'terminal',return_value=False): self.assertTrue(waiter.ready(c))
   with patch.object(waiter,'terminal',return_value=True):
    self.assertTrue(waiter.ready(c))
    (train/'COMPLETE.json').write_text(json.dumps({'exit_code':0,'steps':3116,'scientific_acceptance':False}))
    (dev/'infer-LAUNCH.json').write_text(json.dumps({'chip':0,'container_id':cid}))
    (dev/'infer-EXIT.json').write_text(json.dumps({'container_id':cid,'exit_code':0,'container_exit_code':0}))
    self.assertTrue(waiter.ready(c))
    (dev/'result').mkdir();(dev/'result/INFERENCE-READY.json').write_text('{}')
    self.assertEqual(waiter.ready(c),[])
    (dev/'infer-EXIT.json').write_text(json.dumps({'container_id':cid,'exit_code':1,'container_exit_code':1}))
    with self.assertRaises(RuntimeError):waiter.ready(c)
 def test_phase_binding_real_terminal(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); train=root/'train'; dev=root/'dev'; train.mkdir(); dev.mkdir(); (dev/'result').mkdir(); cid='a'*64
   spec={'launch_file':'infer-LAUNCH.json','exit_file':'infer-EXIT.json','artifact_file':'result/INFERENCE-READY.json','container_name_template':'nga-rc1-cpu-full-{id}-infer'}
   c={'dev_dependency':spec,'dependencies':[{'chip':0,'id':'x','train':str(train),'dev':str(dev)}]}
   def put(path,obj): path.write_text(json.dumps(obj))
   put(train/'train-LAUNCH.json',{'chip':0,'phase':'train','container_id':cid}); put(train/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False})
   put(dev/'infer-LAUNCH.json',{'chip':0,'container_id':cid}); put(dev/'infer-EXIT.json',{'container_id':cid,'exit_code':0,'container_exit_code':0})
   obj={'Name':'/nga-rc1-cpu-full-x-infer','HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0'}],'AutoRemove':False},'State':{'Status':'running','ExitCode':0}}
   with patch.object(waiter,'inspect',return_value=obj):
    self.assertTrue(waiter.ready(c))
    obj['State']['Status']='exited'
    self.assertTrue(waiter.ready(c)) # artifact missing
    put(dev/'result/INFERENCE-READY.json',{})
    self.assertEqual(waiter.ready(c),[]) # no score receipt or report needed
    obj['State']['ExitCode']=1
    with self.assertRaises(RuntimeError): waiter.ready(c)
    obj['State']['ExitCode']=0; obj['Name']='/wrong'
    with self.assertRaises(RuntimeError): waiter.ready(c)
    obj['Name']='/nga-rc1-rg-full-x'
    spec.update(launch_file='LAUNCH.json',exit_file='EXIT.json',artifact_file='result/report.json',container_name_template='nga-rc1-rg-full-{id}')
    put(dev/'LAUNCH.json',{'chip':0,'container_id':cid}); put(dev/'EXIT.json',{'container_id':cid,'exit_code':0,'container_exit_code':0}); put(dev/'result/report.json',{})
    self.assertEqual(waiter.ready(c),[])
 def test_busy_uncertain_probe(self):
  with patch.object(probe,'containers',return_value=[{'container':'busy'}]),patch.object(probe,'listing',return_value={i:[] for i in range(4)}),patch.object(probe,'processes',return_value=[]),patch.object(probe,'run',return_value='x'),patch.object(probe.Path,'exists',return_value=False),patch.object(probe.Path,'read_text',return_value='systemd'),patch.object(probe.os,'uname') as u:
   u.return_value.nodename='k8s-node1'
   self.assertTrue(probe.check([0,1,2,3])['unmanaged_owners'])
   with patch.object(probe,'listing',side_effect=ValueError('malformed')):
    with self.assertRaises(ValueError):probe.check([0,1,2,3])
if __name__=='__main__':unittest.main()
