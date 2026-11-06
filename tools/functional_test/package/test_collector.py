import json,sys,tempfile,unittest
from pathlib import Path
import collector as C
HERE=Path(__file__).resolve().parent
REF=HERE.parents[2]/'science/same-test-reference-fix'
P=REF/'scratch/generated/packet.json'
def fixture_config():
 p=json.loads(P.read_text());example=json.loads((REF/'config.example.json').read_text());return {'kind':'generated','configs':{r:e['config']['path'] for r,e in p['members'].items()},'identities':{r:e['identity']['path'] for r,e in p['members'].items()},'producer':p['producer']['path'],'bootstrap_wrapper':p['bootstrap_wrapper']['path'],'module_dirs':p['module_dirs'],'populations':{k:v['path'] for k,v in p['populations'].items()},'data_pins':p['data_pins'],'consumer':str(REF/'consumer.py'),'consumer_sha256':C.sha(REF/'consumer.py'),'reference_metadata':example['reference_metadata'],'reference_performance_export':example['reference_performance_export'],'workers':2}
class Collector(unittest.TestCase):
 def test_producer_fixture_collection_and_consumer(self):
  cfg=fixture_config()
  with tempfile.TemporaryDirectory(dir=HERE.parent/'scratch') as out:
   self.assertEqual(C.build(cfg,out)['status'],'ready_for_consumer')
   import subprocess
   r=subprocess.run([sys.executable,'-B','-P',cfg['consumer'],'--config',out+'/consumer-config.json','--out',out+'/comparison'],capture_output=True,text=True)
   self.assertEqual(r.returncode,2,r.stderr)
   result=C.read(out+'/comparison/comparison.json');self.assertEqual(result['own_base_status'],'complete');self.assertEqual(result['reference_alignment_status'],'pending');self.assertEqual(result['status'],'partial')
 def test_pending_and_wrong_identity(self):
  cfg=fixture_config();name=C.ROLES[0];cfg['configs'][name]='/no/such/config';self.assertEqual(C.inspect(cfg)[0]['status'],'pending')
  cfg=fixture_config()
  with tempfile.TemporaryDirectory() as out:
   p=Path(out)/'identity.json';p.write_text('{"sha256":"wrong"}');cfg['identities'][name]=str(p);self.assertEqual(C.inspect(cfg)[0]['status'],'error')
 def test_changed_saved_receipt(self):
  from unittest.mock import patch
  cfg=fixture_config();name=C.ROLES[0];c=C.read(cfg['configs'][name]);target=str(Path(c['out'])/'trackk/decision-v7__calibration/clean.jsonl.receipt.json');original=C.sha
  with tempfile.TemporaryDirectory() as out, patch.object(C,'sha',side_effect=lambda p: '0'*64 if str(p)==target else original(p)):
   with self.assertRaisesRegex(ValueError,'saved store/receipt differs'): C.build(cfg,out)
 def test_wrong_terminal(self):
  cfg=fixture_config();name=C.ROLES[0]
  with tempfile.TemporaryDirectory() as out:
   c=C.read(cfg['configs'][name]);c['member']='q2b-s3';p=Path(out)/'bad.json';C.save(p,c);cfg['configs'][name]=str(p);self.assertEqual(C.inspect(cfg)[0]['status'],'error')
if __name__=='__main__':unittest.main()
