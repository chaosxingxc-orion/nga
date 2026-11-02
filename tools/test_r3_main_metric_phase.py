import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import r3_main_metric_phase as M

CLOSURE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code')
PREP=Path(__file__).resolve().parents[1]/'.local/preparations/early-feedback-implementation-v1'
sys.path.insert(0,str(CLOSURE))
import full_eval_r3 as F
C,AS,SE=F.C,F.AS,F.SE
ARCHIVE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/k0_current_rescore_20261031_v1/08b/results')

def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(M.canonical(d))
class Scorer:
    def __init__(self,desc):self.desc=desc;self.calls=[]
    def describe(self):return self.desc
    def __call__(self,rows,input_mode='full'):
        self.calls.append(([C.kev_key(r) for r in rows],input_mode));return [[-float(i+1) for i in range(len(r['levels']))] for r in rows]

class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.out=self.root/'results';self.out.mkdir()
        self.header=copy.deepcopy(M.read(ARCHIVE/'SCORING_RECEIPT.track_kt.json')['header']);self.scorer=Scorer(self.header['scorer']);F.MODEL_SHA=self.header['model']['sha256']
        self.rows={};pop={}
        for label,n in M.COUNTS.items():
            suite=label.split('/')[0];rs,path=C.load_partition(suite,'dev');self.rows[label]=rs
            pop[label]={'input':M.pin(path),'n':n,'ordered_keys_sha256':M.digest([C.kev_key(r) for r in rs])}
        for n in ['plan.json','execution.json']:put(self.root/n,{'test_fixture':True,'kind':n})
        self.contract={'phase_implementation':M.pin(M.__file__),'schema':M.SCHEMA,'flags':M.FLAGS,'attempt':1,'evaluation_out':str(self.out),'evaluation_plan':M.pin(self.root/'plan.json'),'execution':M.pin(self.root/'execution.json'),
         'producer':M.pin(PREP/'full_eval_r3.py'),'libraries':{k:M.pin(v.__file__) for k,v in [('core',C),('store',AS),('population',SE)]},
         'files':{p.name:M.pin(p) for p in CLOSURE.glob('*.py')},'populations':pop,
         'header_identity':{k:self.header[k] for k in ['arm','model','scorer','primary_input_mode','dtype','prompt_version','prompt_format']}}
        self.path=self.root/'contract.json';self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):put(self.path,self.contract);self.pin=M.sha(self.path)
    def collector(self):return M.Collector(self.path,self.pin,C,AS,SE,self.header,PREP/'full_eval_r3.py',1,self.out)
    def score(self,label):
        suite,split,kind=label.split('/');p=C.k_readout_path(str(self.out),suite,split,kind)
        F._score_k(self.scorer,self.rows[label],p,self.header['primary_input_mode'],lambda _:None,label);return p
    def complete(self):
        co=self.collector();result=None
        for label in M.COUNTS:result=co.completed(label,self.score(label),self.header['primary_input_mode'])
        return result
    def test_full_producer_readouts_headline_and_later_failure(self):
        r=self.complete();self.assertEqual(set(r['partitions']),set(M.COUNTS));self.assertFalse(r['scientific_acceptance']);self.assertFalse(r['resources_released'])
        for label,rows in self.rows.items():self.assertEqual(r['partitions'][label]['headline'],C.headline(rows,[[-float(i+1) for i in range(len(x['levels']))] for x in rows]))
        put(self.out/'EVAL_FAILED.track_kt.json',{'exit_code':1});self.assertEqual(M.consume(self.path,self.pin,C,AS,SE),r)
        self.assertFalse((self.out/'EVAL_COMPLETE.track_kt.json').exists());self.assertFalse((self.out/'RELEASE.json').exists())
        self.assertEqual(self.complete(),r) # actual resumable _score_k does not call scorer again
    def test_real_cli_consumer_and_duplicate_output(self):
        import subprocess
        r=self.complete();out=self.root/'main_metric_diagnostic.json'
        cmd=[sys.executable,'-B','-P',M.__file__,'--contract',str(self.path),'--sha256',self.pin,'--output',str(out)]
        p=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(M.read(out),r)
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
    def test_one_block_no_marker(self):
        co=self.collector();label=next(iter(M.COUNTS));self.assertIsNone(co.completed(label,self.score(label),'full'));self.assertFalse((self.out/'MAIN_METRIC_COMPLETE.json').exists())
    def test_wrong_population_candidates_gold_nonfinite_refused(self):
        label=next(iter(M.COUNTS));p=self.score(label);original=Path(p).read_bytes()
        for change in ['key','candidates','gold','nonfinite','missing']:
            rows=C.read_jsonl(p)
            if change=='key':rows[0]['k']='FOREIGN'
            elif change=='candidates':rows[0]['ids']=list(reversed(rows[0]['ids']))
            elif change=='gold':rows[0]['gold']='FOREIGN'
            elif change=='nonfinite':rows[0]['s'][0]=float('nan')
            else:rows.pop()
            Path(p).write_text(''.join(json.dumps(x)+'\n' for x in rows));AS.publish_receipt(p,F.MODEL_SHA,self.scorer.describe())
            with self.assertRaises(Exception):self.collector().completed(label,p,'full')
            Path(p).write_bytes(original);AS.publish_receipt(p,F.MODEL_SHA,self.scorer.describe())
    def test_header_attempt_mode_and_scope_refused(self):
        for k,v in [('primary_input_mode','drop'),('model',dict(self.header['model'],sha256='f'*64)),('scorer',{})]:
            h=copy.deepcopy(self.header);h[k]=v
            with self.assertRaises(ValueError):M.Collector(self.path,self.pin,C,AS,SE,h,PREP/'full_eval_r3.py',1,self.out)
        with self.assertRaises(ValueError):M.Collector(self.path,self.pin,C,AS,SE,self.header,PREP/'full_eval_r3.py',2,self.out)
        co=self.collector();label=next(iter(M.COUNTS));p=self.score(label)
        with self.assertRaises(ValueError):co.completed(label,p,'drop')
        self.contract['populations']['decision-v7/test/clean']=self.contract['populations'].pop(label);self.save()
        with self.assertRaises(ValueError):self.collector()
    def test_snapshot_mutation_and_partial_never_publish(self):
        original=M.exclusive
        def fail(path,raw):
            if str(path).endswith('transfer-v4.jsonl'):raise OSError('injected crash before second snapshot')
            return original(path,raw)
        with patch.object(M,'exclusive',fail):
            with self.assertRaises(OSError):self.complete()
        self.assertFalse((self.out/'MAIN_METRIC_COMPLETE.json').exists())
        with self.assertRaisesRegex(ValueError,'partial snapshot'):self.complete()
    def test_mutation_after_success_rejects_snapshot_and_resume(self):
        self.complete();p=self.out/'main_metric_phase/decision-v7.jsonl';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):M.consume(self.path,self.pin,C,AS,SE)
    def test_mutation_during_copy_and_symlink_refused(self):
        original=M.exclusive
        def mutate(path,raw):
            original(path,raw)
            if str(path).endswith('decision-v7.original-receipt.json'):
                p=Path(C.k_readout_path(str(self.out),'decision-v7','dev','clean'));p.write_bytes(p.read_bytes()+b' ')
        with patch.object(M,'exclusive',mutate):
            with self.assertRaisesRegex(ValueError,'mutated during snapshot'):self.complete()
        self.assertFalse((self.out/'MAIN_METRIC_COMPLETE.json').exists())
        link=self.root/'link';link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError,'symlink'):M.sha(link)
    def test_optional_diagnostic_failure_does_not_abort_scorer(self):
        messages=[];co=M.OptionalCollector(self.path,self.pin,C,AS,SE,self.header,PREP/'full_eval_r3.py',1,self.out,messages.append)
        label=next(iter(M.COUNTS));p=self.score(label)
        co.completed(label,p,'drop')
        self.assertTrue((self.out/'MAIN_METRIC_DIAGNOSTIC_FAILED.json').exists());self.assertFalse((self.out/'MAIN_METRIC_COMPLETE.json').exists())
        self.score('transfer-v4/dev/clean');self.assertTrue(self.scorer.calls);self.assertIsNone(co.completed('transfer-v4/dev/clean',p,'full'))
    def test_qo_drop_mode_preserved(self):
        self.header['arm']='K1-QO';self.header['primary_input_mode']='drop';self.contract['header_identity']['arm']='K1-QO';self.contract['header_identity']['primary_input_mode']='drop';self.save()
        self.assertEqual(self.complete()['primary_input_mode'],'drop');self.assertTrue(all(mode=='drop' for _,mode in self.scorer.calls))
    def test_actual_run_track_k_hook_unchanged_scoring_sequence(self):
        spec=importlib.util.spec_from_file_location('prospective_full',PREP/'full_eval_r3.py');module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'r3_main_metric_phase':M}):spec.loader.exec_module(module)
        module.MODEL_SHA=F.MODEL_SHA
        from types import SimpleNamespace
        order=['decision-v7/dev/clean','decision-v7/dev/question_only','transfer-v4/dev/clean']
        a=SimpleNamespace(partitions=['dev'],limit=0,stages='k_score,t_score',k_only=','.join(order),primary_mode='full',main_feedback_contract=str(self.path),main_feedback_sha256=self.pin,main_feedback_attempt=1)
        with patch.object(module,'build_header',return_value=self.header),patch.object(module.PC,'check_kev_manifest'),patch.object(module.PC,'check_a',return_value={'train':{'gold_at_position_0':0,'n':1}}),patch.object(module.PC,'check_b'):
            self.assertEqual(module.run_track_k(a,self.scorer,self.header['model'],str(self.out),lambda _:None,{}),(None,[]))
        self.assertTrue((self.out/'MAIN_METRIC_COMPLETE.json').exists());self.assertEqual([mode for _,mode in self.scorer.calls[:40]],['full']*40)
        self.assertIn('drop',[mode for _,mode in self.scorer.calls]);self.assertEqual(self.scorer.calls[-1][1],'full')
        before=len(self.scorer.calls)
        with self.assertRaisesRegex(RuntimeError,'later control'):raise RuntimeError('later control failure')
        self.assertTrue(M.consume(self.path,self.pin,C,AS,SE)['diagnostic_only']);self.assertEqual(len(self.scorer.calls),before)

if __name__=='__main__':unittest.main()
