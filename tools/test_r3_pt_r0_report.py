"""Synthetic population tests; no real model, task data or device access."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('pt_report', Path(__file__).with_name('r3_pt_r0_report.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)

class Report(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root/'instruct'; self.base.mkdir()
        (self.base/'model.safetensors').write_bytes(b'base weights')
        (self.base/'config.json').write_text('{}')
        model_patch=patch.object(R,'PT_MODEL',str(self.base));model_patch.start();self.addCleanup(model_patch.stop)
        self.run = self.root/'run'; self.out=self.run/'results'
        self.readouts=self.out/'trackt/readouts'; self.readouts.mkdir(parents=True)
        self.training=self.root/'training'; self.training.mkdir(); self.data=self.root/'data'; self.data.mkdir()
        self.write(self.training/'plan.json', {'control_arm':'K1-PT','arm':'k1','model':R.PT_MODEL,'seed':2,'command':['python3','-P','/workspace/train_r3.py','--arm','k1','--seed','2','--model-path',R.PT_MODEL]})
        self.write(self.training/'manifest.json', {'arm':'k1','args':{'arm':'k1','drop_state':False},'total_steps':3116,'summary':{'final_step':3116}})
        tasks={'T1':'a','T2':'b','T3':'c'}; sources=['typed-decisions','openjev-synth','akhilaaa3']
        manifest={'tasks':{d:{s:{} for s in sources if t!='T3' or s=='typed-decisions'} for t,d in tasks.items()}}
        self.rows={}; files={}
        for task,directory in tasks.items():
            for source in sources:
                if task=='T3' and source!='typed-decisions':continue
                p=self.data/directory/(source+'.jsonl');p.parent.mkdir(exist_ok=True)
                row={'key':task+source};p.write_text(json.dumps(row)+'\n');self.rows[str(p)]=[row];files[str(p)]=R.sha(p)
                manifest['tasks'][directory][source]={'records':1,'sha256':R.hashlib.sha256(p.read_bytes()[:-1]).hexdigest()}
        self.write(self.data/'manifest.json',manifest);files[str(self.data/'manifest.json')]=R.sha(self.data/'manifest.json')
        self.model={'path':str(self.training/'adapter'),'kind':'lora-adapter-unmerged','sha256':'a'*64,'base_path':R.PT_MODEL,'base_revision':'rev'}
        self.scorer={'record_grade':True,'mode':'rightpad','dtype':'float32','hf32':{'hf32':False},'token_budget':16384, 'model_path':R.PT_MODEL, 'adapter':self.model['path'],
                     'layout':'right padded', 'dedup':True, 'score_chunk_questions':32}
        self.h={'arm':'K1-PT','stages':'t_score','track_t_config':'r0','partitions':['dev','calibration'],'limit':0,'limit_groups':0,
            'dry_run_warnings':[],'primary_input_mode':'full','render':'record_name','dtype':'float32','scorer':self.scorer,
            'prompt_version':'v','prompt_format':'f','track_t_sources':','.join(sources),'model':self.model,
            'data_files':{k:v for k,v in files.items() if Path(k).name!='manifest.json'}}
        self.contract={'model':self.model,'data':files,'training_plan':{'path':str(self.training/'plan.json'),'sha256':R.sha(self.training/'plan.json')}}
        self.receipt={'schema':'r3-scoring-receipt-v1','scientific_acceptance':False,'header':self.h}
        self.write(self.out/'SCORING_RECEIPT.track_t_pt_r0.json',self.receipt)
        self.write(self.out/'EVAL_COMPLETE.track_t_pt_r0.json',{'exit_code':0})
        self.identity={'arm':'K1-PT','seed':2,'training_manifest':str(self.training/'manifest.json')}
        flat=[r for rows in self.rows.values() for r in rows]
        for role in R.ROLES:
            (self.readouts/(role+'__data.jsonl')).write_text(''.join(json.dumps({'k':r['key'],'s':[1.,0.]})+'\n' for r in flat))
        def validate(rows, expected, key):
            if len(rows)!=len(expected) or {r['k'] for r in rows}!={key(r) for r in expected}:raise ValueError('population differs')
            lookup={r['k']:r for r in rows};return [lookup[key(r)] for r in expected]
        self.block={'config':'r0','tie_rule':'r0_published','tau_splitter':'group70'}
        self.line={'n_trained':7,'n_base':7,'flip_n_pairs_trained':7,'flip_n_pairs_base':7,'admissible':False,'verdict':'not admissible'}
        self.calls=[]
        def b4(t,b,half):self.calls.append(half);return [dict(self.line)]
        self.deps={'prompt':NS(PROMPT_VERSION='v',PROMPT_FORMAT='f'),
            'provenance_r3':NS(_scorer_problems=lambda s:[] if s==self.scorer else ['wrong']),
            'selection_evidence_r3':NS(train_identity=lambda r:self.identity,verify_run=lambda *a:{'manifests':{'one':{'scorer':self.scorer}}},
                validate_population=validate),
            'core_r3':NS(read_jsonl=lambda p:[json.loads(x) for x in Path(p).read_text().splitlines()]),
            'common':NS(SOURCE_FILES=sources,TASK_DIRS=tasks,task_path=lambda root,t,s:str(Path(root)/tasks[t]/(s+'.jsonl')),
                load_records=lambda p:self.rows[p]),
            'track_t_r3':NS(CONFIG_R0={'name':'r0'},records_needed=lambda rows,c:rows,make_readout=lambda row,s:{'k':row['key'],'s':s},
                constant_and_uniform_rows=lambda *a:{'constant':[],'uniform':[]},build_track_t=lambda *a:dict(self.block),b4_lines=b4)}
        self.baseline={'header':copy.deepcopy(self.h),'track_t':dict(self.block)}
        self.baseline['header'].update(arm='K0',model={'path':R.PT_MODEL,'base_path':R.PT_MODEL,'kind':'checkpoint','base_revision':'rev','sha256':'b'*64})
        self.baseline['header']['scorer']['adapter']=None
        self.contract['base_model']=copy.deepcopy(self.baseline['header']['model'])
        ms=importlib.util.spec_from_file_location('inventory',Path(__file__).with_name('r3_model_inventory.py'))
        M=importlib.util.module_from_spec(ms);ms.loader.exec_module(M)
        inventory=M.capture(self.base)
        inv=self.root/'inventory.json';self.write(inv,{'inventory':inventory,'inventory_sha256':M.identity(inventory)})
        self.contract['base_inventory']={'path':str(inv),'sha256':R.sha(inv)}
        basefiles={str(self.base/k):v['sha256'] for k,v in inventory['files'].items()}
        for key,profile,schema,path in [
            ('pt_scoring_spec','track_t_pt_r0','r3-posttrain-dev-spec-v1',self.run/'plan.json'),
            ('r0_scoring_spec','track_t_r0','r3-baseline-dev-spec-v1',self.root/'r0-plan.json')]:
            self.write(path,{'schema':schema,'evaluation_profile':profile,'model':R.PT_MODEL,
                'adapter':self.model['path'],'files':basefiles})
            self.contract[key]={'path':str(path),'sha256':R.sha(path)}
        self.count=patch.object(R,'EXPECTED_COUNT',7);self.count.start();self.addCleanup(self.count.stop)
    def write(self,p,v):p.write_text(json.dumps(v))
    def run_rebuild(self):return R.rebuild(self.run,self.contract,self.deps,self.baseline,R.canonical_sha(self.baseline))
    def test_full_population_rebuilt_and_no_approval(self):
        result=self.run_rebuild();self.assertEqual(self.calls,['all'])
        self.assertEqual(result['cpu_rebuild']['per_role'],dict.fromkeys(R.ROLES,7))
        self.assertFalse(result['scientific_acceptance']);self.assertFalse(result['publication_authorized'])
        self.assertEqual(result['B-4']['lines'][0]['verdict'],'not admissible')
    def test_wrong_partition_role_config_and_seed_refused(self):
        for field,value in [('arm','K1'),('partitions',['test']),('track_t_config','r3'),('primary_input_mode','drop'),('limit',1)]:
            wrong=copy.deepcopy(self.receipt);wrong['header'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):R.header_checks(wrong,self.contract,self.deps)
        self.identity['seed']=3
        with self.assertRaisesRegex(ValueError,'plan differs'):self.run_rebuild()
    def test_missing_duplicate_extra_roles_and_changed_source_refused(self):
        path=self.readouts/'primary__data.jsonl';saved=path.read_text()
        for data in ('',saved+saved):
            path.write_text(data)
            with self.assertRaisesRegex(ValueError,'population'):self.run_rebuild()
        path.write_text(saved);(self.readouts/'foreign__data.jsonl').write_text(saved)
        with self.assertRaisesRegex(ValueError,'unexpected readout'):self.run_rebuild()
        (self.readouts/'foreign__data.jsonl').unlink();Path(next(iter(self.rows))).write_text('changed')
        with self.assertRaisesRegex(ValueError,'task dependency'):self.run_rebuild()
    def test_baseline_protocol_and_binding_rejected(self):
        for field,value in [('track_t_config','r3'),('primary_input_mode','drop'),('data_files',{}),('scorer',{})]:
            wrong=copy.deepcopy(self.baseline);wrong['header'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'protocol differs'):
                R.compare_baseline(self.h,self.block,wrong,R.canonical_sha(wrong),self.deps['track_t_r3'])
        with self.assertRaisesRegex(ValueError,'binding differs'):
            R.compare_baseline(self.h,self.block,self.baseline,'0'*64,self.deps['track_t_r3'])
    def test_distinct_adapter_identities_and_complete_protocol(self):
        self.assertNotEqual(self.h['scorer']['adapter'], self.baseline['header']['scorer']['adapter'])
        R.compare_baseline(self.h,self.block,self.baseline,R.canonical_sha(self.baseline),self.deps['track_t_r3'])
        for field,value in [('mode','exact'),('token_budget',1),('layout','different'),('dedup',False),('new_option',True),
                            ('adapter','/wrong'),('model_path','/wrong')]:
            wrong=copy.deepcopy(self.baseline);wrong['header']['scorer'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'protocol differs'):
                R.compare_baseline(self.h,self.block,wrong,R.canonical_sha(wrong),self.deps['track_t_r3'])
        for field in ('adapter','model_path'):
            wrong=copy.deepcopy(self.baseline);wrong['header']['scorer'].pop(field)
            with self.assertRaisesRegex(ValueError,'missing producer identity'):
                R.compare_baseline(self.h,self.block,wrong,R.canonical_sha(wrong),self.deps['track_t_r3'])
        wrong=copy.deepcopy(self.h);wrong['scorer']['adapter']=None
        with self.assertRaisesRegex(ValueError,'adapter identity'):
            R.compare_baseline(wrong,self.block,self.baseline,R.canonical_sha(self.baseline),self.deps['track_t_r3'])

    def test_provenance_failure_and_separate_denominators(self):
        self.deps['selection_evidence_r3'].verify_run=lambda *a:{'manifests':{}}
        with self.assertRaisesRegex(ValueError,'descriptors'):self.run_rebuild()
        self.line['n_base']=6
        lines=R.compare_baseline(self.h,self.block,self.baseline,R.canonical_sha(self.baseline),self.deps['track_t_r3'])
        self.assertEqual((lines[0]['n_trained'],lines[0]['n_base']),(7,6))
    def test_baseline_bytes_and_b1_refusal_not_silently_accepted(self):
        self.baseline['header']['model']['sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'base identity'):self.run_rebuild()
        self.baseline['header']['model']['sha256']='b'*64
        self.line['verdict']='pass'
        with self.assertRaisesRegex(ValueError,'B-1 refusal'):self.run_rebuild()

    def test_real_base_mutation_detected_despite_unchanged_revision(self):
        (self.base/'model.safetensors').write_bytes(b'changed weights')
        with self.assertRaisesRegex(ValueError,'byte inventory differs'):self.run_rebuild()

    def test_each_producer_must_bind_complete_matching_base_inventory(self):
        for key in ('pt_scoring_spec','r0_scoring_spec'):
            path=Path(self.contract[key]['path']);original=path.read_text();value=json.loads(original)
            value['files'].pop(str(self.base/'config.json'));self.write(path,value)
            self.contract[key]['sha256']=R.sha(path)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'producer base file inventory'):self.run_rebuild()
            path.write_text(original);self.contract[key]['sha256']=R.sha(path)
        inv=Path(self.contract['base_inventory']['path']);inv.write_text('{}')
        with self.assertRaisesRegex(ValueError,'bound artifact'):self.run_rebuild()

    def test_builder_manifest_bytes_counts_and_framing(self):
        path=self.root/'builder.jsonl';raw=b'{"a": 1}\n{"a": 2}\n';path.write_bytes(raw)
        entry={'records':2,'sha256':R.hashlib.sha256(b'{"a": 1}{"a": 2}').hexdigest()}
        self.assertEqual(R.verify_task_manifest(path,entry)['records'],2)
        for wrong in (dict(entry,records=1),dict(entry,sha256='0'*64)):
            with self.assertRaisesRegex(ValueError,'builder manifest'):R.verify_task_manifest(path,wrong)
        for raw in (b'{"a": 1}',b'\n'):
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'framing'):R.verify_task_manifest(path,entry)

    def test_actual_frozen_r0_api_contract_in_clean_process(self):
        root=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/r0_current_gating_20261031_v1')
        if not root.exists():self.skipTest('frozen R0 source unavailable')
        program = r"""
import ast,hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]);report=Path(sys.argv[2])
p=root/'code/selection_evidence_r3.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='a386dcbfccb65eeb85036a1fc9ae67d25a7cc4e94b9668da97247c9b4017f3d1'
spec=importlib.util.spec_from_file_location('source_report',sys.argv[3]);RR=importlib.util.module_from_spec(spec);spec.loader.exec_module(RR)
deps=RR.frozen_modules(json.loads((root/'PREPARATION.json').read_text()))
# Enumerate every dependency attribute actually referenced by the PT library.
alias={'C':'core_r3','T':'track_t_r3','E':'selection_evidence_r3','PV':'provenance_r3','RC':'common'}
for node in ast.walk(ast.parse(report.read_text())):
 if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id in alias:
  assert hasattr(deps[alias[node.value.id]],node.attr),(node.value.id,node.attr)
assert hasattr(deps['prompt'],'PROMPT_VERSION') and hasattr(deps['prompt'],'PROMPT_FORMAT')
E=deps['selection_evidence_r3'];assert not hasattr(E,'verify_task_manifest')
spec=importlib.util.spec_from_file_location('pt_report',report);R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory)/'task.jsonl';p.write_bytes(b'{"key":"synthetic"}\n')
 R.verify_task_manifest(p,{'records':1,'sha256':hashlib.sha256(p.read_bytes()[:-1]).hexdigest()})
 expected=[{'key':'synthetic','levels':[{'id':'a'},{'id':'b'}],'gold_id':'a'}]
 stored=[{'k':'synthetic','ids':['a','b'],'gold':'a','s':[1.,0.]}]
 assert E.validate_population(stored,expected,lambda r:r['key'])==stored
assert 'torch' not in sys.modules
print('FROZEN_API_AND_SYNTHETIC_POPULATION_OK')
"""
        source_report=root.parent/'r0_cpu_report_closure_20261031_v2/r3_r0_report.py'
        result=subprocess.run([sys.executable,'-B','-I','-c',program,str(root),str(Path(R.__file__).resolve()),str(source_report)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('FROZEN_API_AND_SYNTHETIC_POPULATION_OK',result.stdout)

    def test_real_b4_rule_preserves_b1_admissibility(self):
        path=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code/track_t_r3.py')
        if not path.exists():self.skipTest('frozen metric source unavailable')
        self.assertEqual(R.sha(path),'52a6d21e2901136f9d98adb4b28ca768f5627124115c3e4e90fef39ab5cc7295')
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='b4_lines')
        ns={'LEVEL_TYPES':['boolean'],'B4_ACCURACY_FLOOR':'T1','B4_MAX_FLIP_RISE':.02,'EPS':1e-9,'MIN_N':30}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        cell={'floor_T1':{'acc_cumulative':.8,'n':40},'flip_T1':{'argmax_reference':{'overall':.1,'n_pairs_used':40}},'floor_T2':{'acc_cumulative':.5}}
        block={'config':'r0','meta':{'prompt_version':'v'},'decision_lines':{'all':{'B-1_by_source':{'source':{'pass':False}}}},
               'cells':{'all':{'source':{'boolean':{'primary':cell}}}}}
        T=NS(b4_lines=ns['b4_lines'])
        trained=copy.deepcopy(block);untuned=copy.deepcopy(block)
        for b in (trained,untuned):b.update(tie_rule='r0_published',tau_splitter='group70')
        untuned['cells']['all']['source']['boolean']['primary']['floor_T1']['n']=39
        untuned['cells']['all']['source']['boolean']['primary']['flip_T1']['argmax_reference']['n_pairs_used']=38
        baseline=copy.deepcopy(self.baseline);baseline['track_t']=untuned
        lines=R.compare_baseline(self.h,trained,baseline,R.canonical_sha(baseline),T)
        self.assertEqual(lines[0]['verdict'],'not admissible')
        self.assertEqual((lines[0]['n_trained'],lines[0]['n_base']),(40,39))
        self.assertEqual((lines[0]['flip_n_pairs_trained'],lines[0]['flip_n_pairs_base']),(40,38))

class FormalControlObjectiveTests(unittest.TestCase):
    def plan(self):
        return {'seed':3,'model':'/model','command':['python3','-P','/workspace/train_r3.py',
                '--arm','k1','--seed','3','--model-path','/model']}

    def test_formal_plan_without_duplicate_arm_is_supported(self):
        self.assertEqual(R.control_objective(self.plan()),'k1')

    def test_duplicate_alias_unknown_and_mismatch_reject(self):
        variants=[]
        for suffix in (['--arm','k1'],['--ar','k1'],['--unknown','x'],['--arm=k1']):
            p=self.plan();p['command']+=suffix;variants.append(p)
        for k,v in (('arm','k2'),('seed',True),('model','/other')):
            p=self.plan();p[k]=v;variants.append(p)
        for p in variants:
            with self.subTest(plan=p),self.assertRaises(ValueError):R.control_objective(p)

if __name__=='__main__':unittest.main()
