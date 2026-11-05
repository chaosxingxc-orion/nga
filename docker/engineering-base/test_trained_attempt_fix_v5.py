import copy, json, unittest
from pathlib import Path
from unittest import mock
import test_trained_integration as F
m=F.m

class TrainedAttempt(unittest.TestCase):
 def test_real_tiny_success_then_distinct_rejections(self):
  f=F.TrainedIntegration('test_actual_chain');f.setUp()
  try:
   f.establish_bridge()
   with mock.patch.object(m,'load_model',side_effect=lambda c:m._load_peft(c,'cpu')):m.run(f.cfg,f.out)
   names=('OWNER.json','EXIT.json','completion.json','predictions.json'); before={n:(f.out/n).read_bytes() for n in names}
   bad=[]
   for value in ('0'*64,'1'*64):
    c=copy.deepcopy(f.cfg);c['dataset']['sha256']=value;bad.append(c)
    with self.assertRaisesRegex(ValueError,'dataset digest differs'):m.run(c,f.out)
   files=list((f.out/'attempt-failures').glob('*.json')); records=[json.loads(p.read_text()) for p in files]
   self.assertEqual({r['attempted_config_sha256'] for r in records},{m.base.native.digest(c) for c in bad})
   for p,r in zip(files,records):self.assertEqual(p.stem,r['attempt_id']);self.assertTrue(r['nonlaunch']);self.assertEqual(r['stage'],'admission');self.assertEqual(r['historical_terminal'],'not_the_result_of_this_attempt')
   self.assertEqual(before,{n:(f.out/n).read_bytes() for n in names})
   different=copy.deepcopy(f.cfg);different['image_sha256']='f'*64
   with self.assertRaisesRegex(ValueError,'output ownership differs'):m.run(different,f.out)
   ownership=[json.loads(p.read_text()) for p in (f.out/'attempt-failures').glob('*.json') if json.loads(p.read_text())['stage']=='ownership']
   self.assertEqual(len(ownership),1);self.assertEqual(ownership[0]['attempted_config_sha256'],m.base.native.digest(different))
   with mock.patch.object(m.base,'write',side_effect=OSError('disk')):
    with self.assertRaisesRegex(ValueError,'dataset digest differs'):m.run(bad[0],f.out)
   owner=f.out/'OWNER.json';saved=owner.read_bytes();owner.write_text('{}')
   with self.assertRaisesRegex(ValueError,'dataset digest differs'):m.run(bad[0],f.out)
   self.assertEqual(len(list((f.out/'attempt-failures').glob('*.json'))),3);owner.write_bytes(saved)
   link=f.root/'symlink';link.symlink_to(f.out,target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'dataset digest differs'):m.run(bad[0],link)
   self.assertEqual(len(list((f.out/'attempt-failures').glob('*.json'))),3)
  finally:f.doCleanups()
if __name__=='__main__':unittest.main()
