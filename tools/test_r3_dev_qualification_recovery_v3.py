"""Strict scorer identity composition; actual nine-member source fixtures."""
import copy
import ast
import hashlib
import json
from pathlib import Path
import types
import unittest
from tools import r3_dev_qualification_recovery_v3 as M

ROOT = Path('/home/xingchao/workspace/nga/.local/preparations/pt2-member-consume-actual-20261104-v1/qualification-generation/BUNDLE.json')
class Composition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads(ROOT.read_bytes())
    def setUp(self):
        self.b=copy.deepcopy(self.bundle)
        def bound(p,files):
            raw=Path(p).read_bytes()
            if files.get(str(p))!=hashlib.sha256(raw).hexdigest():raise ValueError('changed source')
            return json.loads(raw)
        self.api=types.SimpleNamespace(Q=types.SimpleNamespace(bound=bound))
    def header(self,n):return M.protocol(self.b,n,self.b['entries'][n],self.api)['protocol_header']
    def report_header(self,n):return json.loads(Path(self.b['entries'][n]['report']).read_bytes())['header']
    def assert_header_matches(self,n):
        got=self.report_header(n);expected=self.header(n)
        for k,v in expected.items():
            if got[k]!=v:raise ValueError('protocol differs: '+k)
    def test_all_nine_exact_report_protocols_and_no_mutation(self):
        original=copy.deepcopy(self.b)
        for n in self.b['entries']:self.assert_header_matches(n)
        self.assertEqual(self.b,original)
    def test_wrong_registered_model_rejected(self):
        self.b['entries']['primary_s2']['model']['base_path']=M.Q.INSTRUCT
        with self.assertRaises(ValueError):self.header('primary_s2')
    def test_wrong_adapter_rejected(self):
        self.b['entries']['pt_s2']['model']['path']='/wrong/adapter'
        with self.assertRaises(ValueError):self.header('pt_s2')
    def test_wrong_kind_rejected(self):
        self.b['entries']['pt_s2']['model']['kind']='checkpoint'
        with self.assertRaises(ValueError):self.header('pt_s2')
    def test_changed_pinned_spec_rejected(self):
        e=self.b['entries']['pt_s2'];x=json.loads(Path(e['execution']).read_bytes())
        self.b['files'][x['spec']]='0'*64
        with self.assertRaises(ValueError):self.header('pt_s2')
    def test_scientific_common_settings_remain_strict(self):
        cases=[('dtype','bfloat16'),('token_budget',8192),('hf32',{'conv':True,'hf32':True,'matmul':True}),('mode','leftpad')]
        for k,v in cases:
            self.b=copy.deepcopy(self.bundle);self.b['protocol_header']['scorer'][k]=v
            with self.assertRaises(ValueError):self.assert_header_matches('pt_s2')
    def test_report_inputmode_does_not_become_authority(self):
        self.assertEqual(self.header('qo_s2')['primary_input_mode'],'drop')
        self.assertEqual(self.header('pt_s2')['primary_input_mode'],'full')
    def test_unregistered_scorer_key_not_discarded(self):
        self.b['protocol_header']['scorer']['unexpected']=True
        with self.assertRaises(ValueError):self.assert_header_matches('primary_s2')
    def test_baselines_keep_no_adapter(self):
        for n in ['k0_base','k0_instruct']:self.assertIsNone(self.header(n)['scorer']['adapter'])

    def floor_reports(self):
        reports={n:json.loads(Path(self.b['entries'][n]['report']).read_bytes())
                 for n in ('primary_s2','samechip_s2','diffchip_s2')}
        return reports['primary_s2'],{n:reports[n+'_s2'] for n in ('samechip','diffchip')}
    def test_floor_private_views_preserve_all_but_adapter(self):
        first,others=self.floor_reports(); saved=copy.deepcopy((first,others))
        a,bs=M.floor_views(first,others)
        self.assertEqual((first,others),saved)
        for role,b in bs.items():
            self.assertEqual(a['header']['scorer'],b['header']['scorer'])
            expected=copy.deepcopy(others[role]);expected['header']['scorer']['adapter']=first['header']['scorer']['adapter']
            self.assertEqual(b,expected)
    def test_floor_bad_identity_rejected(self):
        for key,value in [('adapter','wrong'),('model_path','wrong')]:
            first,others=self.floor_reports();others['samechip']['header']['scorer'][key]=value
            with self.assertRaises(ValueError):M.floor_views(first,others)
    def test_floor_reused_adapter_rejected(self):
        first,others=self.floor_reports();others['samechip']=copy.deepcopy(first)
        with self.assertRaises(ValueError):M.floor_views(first,others)
    def test_floor_common_scorer_mutations_remain_different(self):
        for k,v in [('dtype','bfloat16'),('token_budget',8192),('hf32',{}),('unexpected',True)]:
            first,others=self.floor_reports();others['samechip']['header']['scorer'][k]=v
            a,bs=M.floor_views(first,others)
            self.assertNotEqual(a['header']['scorer'],bs['samechip']['header']['scorer'])
    def frozen_floor(self,first,others,gates):
        # Execute the unchanged production floor function, without loading torch.
        p=Path('.local/preparations/formal-qualification-consumer-20261101-v3/consumer.py')
        tree=ast.parse(p.read_text())
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef)
                  and n.name in ('floor_diagnostics','require','exact','canonical')]
        fields=('partitions','track_t_config','prompt_version','prompt_format','render',
                'primary_input_mode','dtype','readings','scorer','data_files')
        import math
        ns={'PROTOCOL_FIELDS':fields,'SUITES':('decision-v7','transfer-v4'),'math':math,'json':json}
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(p),'exec'),ns)
        scorer=types.SimpleNamespace(_dev_acc=lambda r,s:0.5)
        a,bs=M.floor_views(first,others)
        return ns['floor_diagnostics'](a,bs,scorer,gates)
    def test_actual_nominal_floor_runs_with_distinct_adapters(self):
        first,others=self.floor_reports();result=self.frozen_floor(first,others,['nominal'])
        self.assertEqual(set(result),{'samechip','diffchip'})
        self.assertGreater(result['diffchip']['flip']['nominal']['difference'],0)
    def test_actual_void_floor_remains_rejected(self):
        first,others=self.floor_reports()
        with self.assertRaisesRegex(ValueError,'invalid floor gating cell'):
            self.frozen_floor(first,others,['ordinal'])
    def test_actual_floor_protocol_mutation_rejected(self):
        for key,value in [('dtype','bfloat16'),('hf32',{}),('token_budget',8192),('unexpected',True)]:
            first,others=self.floor_reports();others['samechip']['header']['scorer'][key]=value
            with self.assertRaisesRegex(ValueError,'floor protocol differs'):
                self.frozen_floor(first,others,['nominal'])

if __name__=='__main__':unittest.main()
