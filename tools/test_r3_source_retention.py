import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('retention', Path(__file__).with_name('r3_source_retention.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)


class Retention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.run = self.root/'resume'; self.run.mkdir()
        self.training = self.root/'train'; (self.training/'ckpt').mkdir(parents=True)
        self.original = self.training/'ckpt/step_002200.pt'; self.original.write_bytes(b'opaque synthetic tensor bytes')
        (self.run/'SOURCE.pt').write_bytes(self.original.read_bytes()); h=R.sha(self.original)
        common={'seed':2,'schema':'r3-engineering-k1-plan-v1','model':'/model','train_file':'/train.jsonl',
                'image_sha256':'image','environment':{},'scientific_acceptance':False,'test_read':False}
        self.source=dict(common,out=str(self.training),command=['python3','-P','/workspace/train_r3.py',
            '--out',str(self.training),'--seed','2','--arm','k1','--model-path','/model','--total-steps','3116'])
        self.write('SOURCE_PLAN.json',self.source)
        self.write('SOURCE.json',{'training':str(self.training),'checkpoint':str(self.original),'step':2200,'sha256':h})
        self.write('CONTRACT.json',{'source_step':2200,'source_sha256':h,'test_read':False,'scientific_acceptance':False})
        self.plan=dict(common,out=str(self.run),validation_kind='current_k1_resume_contract',
            command=['python3','-P','/workspace/r3_resume_contract.py','--out',str(self.run)],
            files={str(p):R.sha(p) for p in self.run.iterdir()})
        self.path=self.run/'plan.json';self.pin=self.save_plan()

    def write(self,name,value): (self.run/name).write_text(json.dumps(value))
    def save_plan(self):
        self.path.write_text(json.dumps(self.plan));return R.identity(self.plan)
    def validate(self,**kw): return R.validate(self.path,self.pin,**kw)
    def mutate_bound(self,name,mutator):
        p=self.run/name;d=json.loads(p.read_text());mutator(d);self.write(name,d)
        self.plan['files'][str(p)]=R.sha(p);self.pin=self.save_plan()

    def test_present_original_matches_but_grants_nothing(self):
        d=self.validate();self.assertTrue(d['original_present']);self.assertFalse(d['reconstruction_accepted'])
        self.assertFalse(d['launch_authorized']);self.assertFalse(d['scientific_acceptance'])

    def test_missing_original_requires_explicit_proposal(self):
        self.original.unlink()
        with self.assertRaisesRegex(ValueError,'default contract rejects'):self.validate()
        d=self.validate(mode='pinned_copy_proposal');self.assertFalse(d['original_present'])
        self.assertNotIn(str(self.original),d['inputs']);self.assertFalse(d['reconstruction_accepted'])

    def test_tampered_retained_copy_rejected(self):
        (self.run/'SOURCE.pt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'prelaunch pin'):self.validate(mode='pinned_copy_proposal')

    def test_missing_copy_pin_rejected_even_when_original_matches(self):
        del self.plan['files'][str(self.run/'SOURCE.pt')];self.pin=self.save_plan()
        with self.assertRaisesRegex(ValueError,'prelaunch pin'):self.validate()

    def test_present_bad_original_never_uses_copy_fallback(self):
        self.original.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'present original'):self.validate(mode='pinned_copy_proposal')

    def test_swapped_source_plan_rejected_with_old_external_pin(self):
        self.source['out']='/different';self.write('SOURCE_PLAN.json',self.source)
        with self.assertRaisesRegex(ValueError,'prelaunch pin'):self.validate()
        self.plan['files'][str(self.run/'SOURCE_PLAN.json')]=R.sha(self.run/'SOURCE_PLAN.json');self.save_plan()
        with self.assertRaisesRegex(ValueError,'canonical plan'):self.validate()

    def test_rebound_inconsistent_source_or_step_rejected(self):
        self.mutate_bound('SOURCE.json',lambda d:d.update(step=2201))
        with self.assertRaisesRegex(ValueError,'source step'):self.validate()
        self.mutate_bound('SOURCE.json',lambda d:d.update(step=2200,training='/another'))
        with self.assertRaisesRegex(ValueError,'training identity'):self.validate()

    def test_original_checkpoint_path_step_mismatch_rejected(self):
        self.mutate_bound('SOURCE.json',lambda d:d.update(checkpoint=str(self.training/'ckpt/step_003000.pt')))
        with self.assertRaisesRegex(ValueError,'path/step'):self.validate(mode='pinned_copy_proposal')

    def test_unbound_source_metadata_rejected(self):
        del self.plan['files'][str(self.run/'CONTRACT.json')];self.pin=self.save_plan()
        with self.assertRaisesRegex(ValueError,'prelaunch pin'):self.validate()

    def test_dangling_original_symlink_is_not_pruning(self):
        self.original.unlink();self.original.symlink_to(self.root/'missing')
        with self.assertRaisesRegex(ValueError,'unsafe source path'):self.validate(mode='pinned_copy_proposal')

    def test_source_recipe_and_mode_rejected(self):
        self.mutate_bound('SOURCE_PLAN.json',lambda d:d['command'].__setitem__(d['command'].index('--arm')+1,'k2'))
        with self.assertRaisesRegex(ValueError,'command binding'):self.validate()
        with self.assertRaisesRegex(ValueError,'unknown'):self.validate(mode='allow')


if __name__=='__main__':unittest.main()
