"""Synthetic seven-member bindings; never real eligibility or approval."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).parent
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2')
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
C=load('closure_admission_fixture',HERE/'r3_final_closure.py')

class Admission(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen source absent')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);closure=self.root/'closure';receipt=C.prepare(SOURCE,closure)
        self.A=load('frozen_admission_fixture',closure/'r3_code/r3_final_admission.py')
        # Only test-local registered paths are substituted; byte verifiers are real.
        self.base=self.root/'Base';self.instruct=self.root/'Instruct'
        self.A.K.BASE=str(self.base);self.A.K.INSTRUCT=str(self.instruct)
        self.inventories={}
        for model in (self.base,self.instruct):
            model.mkdir();(model/'model.safetensors').write_bytes(str(model).encode())
            inv=self.A.M.capture(model);self.inventories[str(model)]=self.write(model.name+'-inventory',{'inventory':inv,'inventory_sha256':self.A.M.identity(inv)})
        self.members=[]
        for i,(arm,seed,base) in enumerate([('K1',2,self.base),('K1',3,self.base),('K0',None,self.base),('K0',None,self.instruct),('K1-QO',2,self.base),('K1-PT',2,self.instruct),('K1-PT',3,self.instruct)]):
            path=base if arm=='K0' else self.root/('train'+str(i))/'adapter'
            member={'arm':arm,'role':'baseline' if arm=='K0' else 'candidate' if arm=='K1' else 'control',
                    'verified_evidence_sha256':'f'*64,'model':{'path':str(path),'sha256':str(i+1)*64,'base_path':str(base),
                    'kind':'checkpoint' if arm=='K0' else 'lora-adapter-unmerged','base_inventory_sha256':self.A.artifact(self.inventories[str(base)])['inventory_sha256']}}
            if seed is not None:
                path.mkdir(parents=True);(path/'adapter_model.safetensors').write_bytes(str(i).encode())
                manifest={'arm':'k1','model_path':str(base),'args':{'arm':'k1','model_path':str(base),'seed':seed,'out':str(path.parent),'drop_state':arm=='K1-QO'},'kernel':'ref','total_steps':3116,'summary':{'final_step':3116}}
                entry=self.write('train'+str(i)+'/manifest',manifest)
                member['training']={'seed':seed,'arm':arm,'adapter_path':str(path),'training_manifest':entry['path'],'training_manifest_sha256':entry['sha256'],
                  'training_variant':self.A.training_recipe(manifest,closure)}
            self.members.append(member)
        self.campaign={'schema':'r3-final-campaign-v1','size':'0.8B','selected_arm':'K1','members':self.members}
        self.evidence={k:self.write(k,{'synthetic_fixture':True}) for k in ('development_comparison','r0_gating','resume_reconstruction','training_eligibility','selection_decision')}
        rd=self.root/'round';rd.mkdir()
        self.plan={'schema':'r3-final-test-plan-v1','host':'k8s-node1','image':self.A.IMAGE,'chip':1,'suites':self.A.SUITES,'partitions':['calibration','test'],
          'scoring':{'mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,'stages':'k','shards':1},'out':str(self.root/'out'),'round_dir':str(rd),
          'evidence':self.evidence,'dataset_manifest':self.write('dataset-manifest',{'suites':{s:{} for s in self.A.SUITES}}),'closure':{'root':str(closure),'sha256':receipt['manifest_sha256']}}
        self.select(2)
    def write(self,name,value):
        p=self.root/(name+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def select(self,index):
        m=self.members[index];model=m['model'];self.plan.update(arm=m['arm'],role=m['role'],model=model['base_path'],model_sha256=model['sha256'],base_inventory=self.inventories[model['base_path']])
        if m['arm']=='K0':
            self.plan.update(adapter=None,adapter_inventory=None,training_manifest=None);self.plan.pop('seed',None)
        else:
            inv=self.A.M.capture(model['path']);t=m['training'];self.plan.update(adapter=model['path'],adapter_inventory=self.write('adapter-inventory',{'inventory':inv,'inventory_sha256':self.A.M.identity(inv)}),seed=t['seed'],training_manifest={'path':t['training_manifest'],'sha256':t['training_manifest_sha256']})
        self.rebind()
    def rebind(self):
        self.plan['campaign']=self.write('campaign',self.campaign);cp=self.plan['campaign']['sha256'];views=[self.A.member_view(m) for m in self.members]
        self.eligible={'schema':'r3-final-eligibility-v1','status':'ELIGIBLE','candidate_test_read':False,'seed_set':[2,3],'suites':self.A.SUITES,'evidence':self.evidence,'selected_models':views,'campaign_sha256':cp}
        self.plan['eligibility']=self.write('eligibility',self.eligible)
        self.final={'eligibility_sha256':self.plan['eligibility']['sha256'],'campaign_sha256':cp,'models':views};self.plan['final']=self.write('round/FINAL',self.final)
        self.refresh_review()
    def refresh_review(self):
        self.pin=self.A.identity(self.plan);self.review={'schema':'r3-final-test-review-v1','review_kind':'independent_astra','reviewer_model':'gpt-6-astra','verdict':'PASS','approved_plan_sha256':self.pin,'blocking_findings':[],'evidence_checks':['synthetic fixture only'],'eligibility_sha256':self.plan['eligibility']['sha256'],'evidence':self.evidence,'campaign_sha256':self.plan['campaign']['sha256']};self.review_entry=self.write('review',self.review)
    def verify(self):return self.A.verify(self.plan,self.pin,self.review_entry)
    def test_all_seven_current_members_bind_without_approval(self):
        for i in range(7):
            self.select(i);r=self.verify();self.assertTrue(r['artifact_bindings_verified']);self.assertFalse(r['scientific_acceptance'])
    def test_missing_campaign_and_incomplete_roster_refused(self):
        self.campaign['members']=self.members[:-1];self.rebind()
        with self.assertRaisesRegex(ValueError,'seven-member'):self.verify()
        self.campaign['members']=self.members;self.rebind();self.final['models']=self.final['models'][:-1];self.plan['final']=self.write('round/FINAL',self.final);self.refresh_review()
        with self.assertRaisesRegex(ValueError,'FINAL campaign'):self.verify()
    def test_campaign_hash_role_seed_and_base_refused(self):
        self.review['campaign_sha256']='e'*64;self.review_entry=self.write('review',self.review)
        with self.assertRaisesRegex(ValueError,'campaign binding'):self.verify()
        self.select(4);self.plan['seed']=3;self.refresh_review()
        with self.assertRaisesRegex(ValueError,'seed differs'):self.verify()
        self.select(4);self.plan['role']='candidate';self.refresh_review()
        with self.assertRaisesRegex(ValueError,'campaign identity'):self.verify()
        self.select(5);self.plan['model']=str(self.base);self.refresh_review()
        with self.assertRaisesRegex(ValueError,'campaign identity'):self.verify()
    def test_changed_manifest_and_base_bytes_refused(self):
        self.select(5)
        with Path(self.plan['training_manifest']['path']).open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.verify()
        self.select(2);(self.base/'model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'byte inventory'):self.verify()
    def test_wrong_training_input_refused_even_rebound(self):
        self.select(4);p=Path(self.plan['training_manifest']['path']);d=json.loads(p.read_text());d['args']['drop_state']=False
        entry=self.write(str(p.relative_to(self.root))[:-5],d);self.members[4]['training']['training_manifest_sha256']=entry['sha256'];self.select(4)
        with self.assertRaisesRegex(ValueError,'training objective'):self.verify()
    def test_actual_recipe_must_match_campaign_recipe(self):
        self.members[0]['training']['training_variant']['args']['lr']=0.5;self.members[1]['training']['training_variant']['args']['lr']=0.5;self.select(0)
        with self.assertRaisesRegex(ValueError,'training recipe differs'):self.verify()
    def test_missing_campaign_and_wrong_selected_roster_are_refused(self):
        self.plan.pop('campaign');self.pin=self.A.identity(self.plan)
        self.review['approved_plan_sha256']=self.pin;self.review_entry=self.write('review',self.review)
        with self.assertRaises(KeyError):self.verify()
        self.select(2);self.eligible['selected_models']=self.eligible['selected_models'][:-1]
        self.plan['eligibility']=self.write('eligibility',self.eligible)
        self.final['eligibility_sha256']=self.plan['eligibility']['sha256'];self.plan['final']=self.write('round/FINAL',self.final);self.refresh_review()
        with self.assertRaisesRegex(ValueError,'eligibility campaign'):self.verify()
    def test_review_and_evidence_still_required(self):
        self.review['blocking_findings']=['unresolved'];self.review_entry=self.write('review',self.review)
        with self.assertRaisesRegex(ValueError,'blockers'):self.verify()
        self.refresh_review();p=Path(self.evidence['r0_gating']['path']);p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.verify()

if __name__=='__main__':unittest.main()
