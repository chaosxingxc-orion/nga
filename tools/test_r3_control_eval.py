"""Control evaluation identities; synthetic metadata, no model/test access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

def module(name):
 p=Path(__file__).with_name(name+'.py');s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
P=module('r3_posttrain_eval_plan');L=module('r3_posttrain_eval_launcher')

class ControlEval(unittest.TestCase):
 def fixture(self,arm='K1-QO',seed=2):
  model=P.BASE_MODEL if arm=='K1-QO' else P.PT_MODEL
  plan={'control_arm':arm,'arm':'k1','seed':seed,'model':model,'command':['train']+(['--drop-state'] if arm=='K1-QO' else [])}
  manifest={'arm':'k1','model_path':model,'args':{'arm':'k1','model_path':model,'seed':seed,'drop_state':arm=='K1-QO'}}
  return plan,manifest
 def test_completed_control_identity_and_original_primary_mode(self):
  for arm,seed in [('K1-QO',2),('K1-PT',2),('K1-PT',3)]:
   plan,manifest=self.fixture(arm,seed);self.assertEqual(P.semantic_arm(plan,manifest),arm)
   spec={'schema':'r3-posttrain-dev-spec-v1','training_variant':{'arm':arm.lower()},'model':plan['model'],'adapter':'/adapter','evaluation_profile':'track_kt'}
   cmd=L.expected_command(spec,Path('/output'));self.assertEqual(cmd[cmd.index('--arm')+1],arm)
   self.assertNotIn('--primary-mode',cmd);self.assertEqual(cmd[cmd.index('--partitions')+1],'dev,calibration')
  source=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code/full_eval_r3.py')
  if source.exists():self.assertIn('a.primary_mode = "drop" if a.arm == "K1-QO" else "full"',source.read_text())
 def test_conflicting_control_identity_rejected(self):
  for change in ('seed','drop','model','objective','label','flag'):
   p,m=self.fixture()
   if change=='seed':p['seed']=3;m['args']['seed']=3
   elif change=='drop':m['args']['drop_state']=False
   elif change=='model':p['model']=P.PT_MODEL
   elif change=='objective':m['args']['arm']='k2'
   elif change=='label':p.pop('control_arm')
   elif change=='flag':p['command']=[]
   with self.subTest(change=change),self.assertRaises(RuntimeError):P.semantic_arm(p,m)
 def test_pt_dropped_state_and_invalid_seed_rejected(self):
  for seed,drop in [(1,False),(2,True),(True,False)]:
   p,m=self.fixture('K1-PT',seed);m['args']['drop_state']=drop
   with self.assertRaises(RuntimeError):P.semantic_arm(p,m)
 def test_launcher_cross_checks_real_manifest_and_pinned_plan(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);p,m=self.fixture();plan=root/'plan.json';plan.write_text(json.dumps(p));(root/'manifest.json').write_text(json.dumps(m))
   spec={'schema':'r3-posttrain-dev-spec-v1','training':str(root),'model':p['model'],
         'training_variant':{'arm':'k1-qo','seed':2,'training_plan_sha256':L.sha(plan)},'files':{str(plan):L.sha(plan)}}
   L.verify_control_manifest(spec)
   bad=copy.deepcopy(spec);bad['training_variant']['arm']='k1'
   with self.assertRaisesRegex(RuntimeError,'relabeled'):L.verify_control_manifest(bad)
   m['args']['drop_state']=False;(root/'manifest.json').write_text(json.dumps(m))
   with self.assertRaisesRegex(RuntimeError,'QO requires'):L.verify_control_manifest(spec)
 def test_prepare_binds_control_plan_and_preserves_dev_template(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);training=root/'training';training.mkdir();closure=root/'closure';closure.mkdir()
   p,m=self.fixture();p.update(files={},image_sha256=L.IMAGE);m['summary']={'final_step':3116}
   for name,doc in [('plan.json',p),('manifest.json',m),('TRAIN_EXIT.json',{'exit_code':0})]:
    (training/name).write_text(json.dumps(doc))
   adapter=training/'adapter';adapter.mkdir();(adapter/'adapter_config.json').write_text('{}');(adapter/'adapter_model.safetensors').write_bytes(b'fixture')
   command=['python3','--arm','K1','--model-path','<FROZEN_BASE_MODEL>','--adapter','<COMPLETED_ADAPTER>','--out','<FRESH_EVAL_OUTPUT>','--partitions','dev,calibration']
   (closure/'manifest.json').write_text(json.dumps({'data':{},'code':{},'mounts':[],'command_template':command}))
   out=root/'output';P.prepare(training,closure,out);spec=json.loads((out/'plan.json').read_text())
   self.assertEqual(spec['training_variant']['arm'],'k1-qo')
   self.assertEqual(spec['command'][spec['command'].index('--arm')+1],'K1-QO')
   self.assertIn(str(training/'plan.json'),spec['files']);L.verify_control_manifest(spec)

 def test_ordinary_legacy_recipe_keeps_identity(self):
  self.assertEqual(P.semantic_arm({'model':'/model','arm':'k2'},{'summary':{'final_step':3116}}),'K2')

if __name__=='__main__':unittest.main()
