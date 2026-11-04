"""Synthetic bridge boundaries; never assert live eligibility or selection."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import r3_final_eligibility_bridge_v1 as B

class Bridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.c={k:{'path':str(self.root/(k+'.json')),'sha256':str(i)*64} for i,k in enumerate(('bundle','adjudication','qualification','campaign','qualifier'),1)}
        entries={}
        for n in B.NINE:
            arm='K0' if n.startswith('k0') else 'K1-QO' if n=='qo_s2' else 'K1-PT' if n.startswith('pt') else 'K1'
            e={'arm':arm,'model':{'path':str(self.root/n/('base' if arm=='K0' else 'adapter')),'sha256':B.digest(n),'base_path':str(self.root/'base'),'kind':'checkpoint' if arm=='K0' else 'lora-adapter-unmerged'}}
            if arm!='K0':e.update(seed=3 if n.endswith('s3') else 2,training_variant={'fixture':True})
            entries[n]=e
        self.bundle={'schema':'r3-production-dev-bundle-v1','branch':'firstK1','test_read':False,'entries':entries,'files':{}}
        self.adj={'schema':'r3-independent-dev-adjudication-v1','bundle_sha256':self.c['bundle']['sha256']}
        checks={k:{'status':'VALIDATED','value':{}} for k in ['inventory','membership','adjudication','r0','role_bindings','chronology','numeric','final_inventory']+['member:'+n for n in B.NINE]}
        checks['numeric']['value']={'numeric_predicates_pass':True,'floor_qualification_indeterminate':False,'development_comparison':{'fixture':True}}
        self.result={'schema':'r3-production-dev-qualification-v1','status':'ELIGIBLE','completed':True,'candidate_eligibility_granted':True,'test_read':False,'scientific_acceptance':False,'final_test_logger_authority':False,'bundle_sha256':self.c['bundle']['sha256'],'adjudication_sha256':self.c['adjudication']['sha256'],'checks':checks}
        members=[]
        for n in B.SEVEN:
            e=entries[n];m={'arm':e['arm'],'model':copy.deepcopy(e['model']),'verified_evidence_sha256':B.digest({}),'role':'baseline' if e['arm']=='K0' else 'candidate' if e['arm']=='K1' else 'control'}
            if e['arm']!='K0':m['training']={'arm':e['arm'],'seed':e['seed'],'adapter_path':e['model']['path'],'training_variant':e['training_variant']}
            members.append(m)
        self.campaign={'size':'0.8B','selected_arm':'K1','members':members}
        self.decision={'schema':'r3-independent-first-k1-final-selection-v1','origin':'independent-parent-adjudication','authenticator_identity':'synthetic independent caller','reviewer_identity':'synthetic fixture, never actual review','verdict':'SELECT_FIRST_K1','selected_arm':'K1','candidate_test_read':False,'blocking_findings':[],'inputs':copy.deepcopy(self.c),'selected_members':list(B.SEVEN),'basis':{'branch':'firstK1','numeric_check_sha256':B.digest(checks['numeric']['value']),'r0_check_sha256':B.digest({}),'no_added_replacement_thresholds':True},'evidence_checks':['synthetic only']}
    def check(self):return B.validate_semantics(self.c,self.bundle,self.adj,self.result,self.campaign,self.decision)
    def test_positive_semantic_contract(self):self.assertEqual(set(self.check()),set(self.result['checks']))
    def test_nonpositive_and_incomplete_states_refused(self):
        for state in ['WAIT','FAIL','NEGATIVE','INDETERMINATE']:
            self.result['status']=state
            with self.assertRaisesRegex(ValueError,'not eligible'):self.check()
    def test_missing_member_check_even_status_eligible_refused(self):
        del self.result['checks']['member:pt_s2']
        with self.assertRaisesRegex(ValueError,'incomplete'):self.check()
    def test_false_predicate_not_rescued_by_selection(self):
        self.result['checks']['numeric']['value']['numeric_predicates_pass']=False
        with self.assertRaisesRegex(ValueError,'not affirmative'):self.check()
    def test_external_selection_binding_and_authorship_fields(self):
        for key,value in [('inputs',{}),('verdict','DEFER'),('authenticator_identity',''),('blocking_findings',['open']),('candidate_test_read',True)]:
            saved=self.decision[key];self.decision[key]=value
            with self.assertRaises(ValueError):self.check()
            self.decision[key]=saved
    def test_foreign_campaign_not_selected_by_path_only(self):
        self.campaign['members'][0]['model']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'model identity'):self.check()
    def test_auxiliary_cannot_replace_final_seed(self):
        self.campaign['members'][0]['model']=copy.deepcopy(self.bundle['entries']['samechip_s2']['model'])
        with self.assertRaisesRegex(ValueError,'qualified roster'):self.check()
    def test_member_evidence_mutation(self):
        self.campaign['members'][0]['verified_evidence_sha256']='d'*64
        with self.assertRaisesRegex(ValueError,'member evidence'):self.check()
    def test_no_replacement_rule_in_first_k1(self):
        self.bundle['branch']='replacement'
        with self.assertRaisesRegex(ValueError,'firstK1'):self.check()
    def test_symlink_and_occupied_write_refused(self):
        target=self.root/'value.json';target.write_text('{}');link=self.root/'link.json';link.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'unsafe'):B.sha(link)
        with self.assertRaises(FileExistsError):B.write(target,{})
    def test_replay_is_real_subprocess_and_exact_result(self):
        bundle=self.root/'bundle.json';bundle.write_text('{}');adj=self.root/'adj.json';adj.write_text('{}');result=self.root/'q.json';result.write_text('{"fixture":true}')
        code=self.root/'qualifier.py';code.write_text("import sys,json\np=sys.argv[sys.argv.index('--output')+1]\nopen(p,'x').write('{\"fixture\":true}')\n")
        c={'bundle':B.pin(bundle),'adjudication':B.pin(adj),'qualification':B.pin(result),'qualifier':B.pin(code),'python':str(Path(sys.executable).resolve()),'environment':{'TORCH_DEVICE_BACKEND_AUTOLOAD':'0','PYTHONDONTWRITEBYTECODE':'1'}}
        out=self.root/'replay';out.mkdir();self.assertEqual(B.replay(c,out),{'fixture':True})
        other=self.root/'other';other.mkdir();result.write_text('{"fixture":false}');c['qualification']=B.pin(result)
        with self.assertRaisesRegex(ValueError,'replay differs'):B.replay(c,other)
    def test_full_builder_output_contract_and_no_overwrite(self):
        import r3_model_inventory as M
        refs={}
        def put(name,value):
            path=self.root/(name+'.json');path.write_text(json.dumps(value));return B.pin(path)
        inventories={}
        for name in B.SEVEN:
            e=self.bundle['entries'][name];m=next(x for x in self.campaign['members'] if x['model']['path']==e['model']['path'])
            base=Path(e['model']['base_path']);base.mkdir(exist_ok=True);(base/'model.safetensors').write_bytes(b'fixture-base')
            inv=M.capture(base);ref=put(name+'-base',{'inventory':inv,'inventory_sha256':M.identity(inv)})
            inventories[name]={'base':ref};m['model']['base_inventory_sha256']=M.identity(inv)
            if e['arm']!='K0':
                adapter=Path(e['model']['path']);adapter.mkdir(parents=True);(adapter/'weights.pt').write_bytes(name.encode())
                inv=M.capture(adapter);inventories[name]['adapter']=put(name+'-adapter',{'inventory':inv,'inventory_sha256':M.identity(inv)})
                manifest=adapter.parent/'manifest.json';manifest.write_text('{}');self.bundle['files'][str(manifest)]=B.sha(manifest)
                m['training'].update(training_manifest=str(manifest),training_manifest_sha256=B.sha(manifest))
        self.c['bundle']=put('bundle',self.bundle);self.adj['bundle_sha256']=self.c['bundle']['sha256'];self.c['adjudication']=put('adjudication',self.adj)
        self.result.update(bundle_sha256=self.c['bundle']['sha256'],adjudication_sha256=self.c['adjudication']['sha256'])
        self.c['qualification']=put('qualification',self.result);self.c['campaign']=put('campaign',self.campaign)
        script=self.root/'qualifier.py';script.write_text('# fixture only');self.c['qualifier']=B.pin(script)
        self.decision['inputs']=copy.deepcopy(self.c)
        cfg={**self.c,'schema':'r3-first-k1-final-bridge-config-v1','selection_decision':put('decision',self.decision),
             'campaign_verifier':B.pin(Path(B.__file__).with_name('r3_final_campaign.py')),
             'inventory_verifier':B.pin(Path(M.__file__)),'inventories':inventories,'python':str(Path(sys.executable).resolve()),
             'environment':{'TORCH_DEVICE_BACKEND_AUTOLOAD':'0','PYTHONDONTWRITEBYTECODE':'1'},'output':str(self.root/'final')}
        ref=put('config',cfg);original=B.module
        def mod(ref):
            if ref==cfg['campaign_verifier']:return types.SimpleNamespace(verify=lambda x:None)
            return original(ref)
        # Only upstream qualifier/campaign are synthetic fixtures here. Real byte inventories and builder execute.
        with patch.object(B,'replay',return_value=self.result),patch.object(B,'module',side_effect=mod):
            result=B.build(ref['path'],ref['sha256'])
        artifact=B.read(result);eligible=B.read(artifact['eligibility']);final=B.read(artifact['final'])
        self.assertEqual(set(eligible['evidence']),set(B.EVIDENCE));self.assertEqual(len(final['models']),7)
        self.assertEqual(final['eligibility_sha256'],artifact['eligibility']['sha256'])
        with self.assertRaisesRegex(ValueError,'fresh output'):B.build(ref['path'],ref['sha256'])
    def test_changed_source_refused(self):
        p=self.root/'changed.json';p.write_text('{}');ref=B.pin(p);p.write_text('{"new":1}')
        with self.assertRaisesRegex(ValueError,'artifact changed'):B.read(ref)

if __name__=='__main__':unittest.main()
