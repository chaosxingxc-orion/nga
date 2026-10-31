"""Compare separate CPU reconstruction with the original Track K producer."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
SOURCE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/selection_cpu_closure_20261031_v2/r3_code')
PRODUCER=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/combined_eval_closure_20261031_v1/r3_code/full_eval_r3.py')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


class Metrics(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():self.skipTest('frozen closure missing')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.data=self.root/'data';self.run=self.root/'run'
        context=patch.dict(sys.modules);context.start();self.addCleanup(context.stop)
        original=list(sys.path);self.addCleanup(lambda:sys.path.__setitem__(slice(None),original))
        sys.path[:0]=[str(SOURCE),str(SOURCE.parent/'r0_code')]
        self.C=load('core_r3',SOURCE/'core_r3.py')
        sys.path[:0]=[str(SOURCE),str(SOURCE.parent/'r0_code')]
        self.TL=load('testlock_r3',SOURCE/'testlock_r3.py')
        self.E=load('selection_evidence_r3',SOURCE/'selection_evidence_r3.py')
        self.D=load('degenerate_r3',SOURCE/'degenerate_r3.py')
        self.V=load('variants_r3',SOURCE/'variants_r3.py')
        self.PC=load('prechecks_r3',SOURCE/'prechecks_r3.py')
        self.M=load('final_metrics_fixture',HERE/'r3_final_metrics.py')
        def row(i):
            return dict(kev={'id':str(i),'qindex':0},source='synthetic',qname='q',level_type='nominal',
                gold='a',levels=[dict(id='a',name='A',definition='A'),dict(id='b',name='B',definition='B')])
        self.rows={('decision-v7','train'): [row('train'+str(i)) for i in range(24)],
                   ('decision-v7','calibration'):[row('cal'+str(i)) for i in range(24)]}
        self.vars={};self.scores={};self.files={};manifest={'suites':{}}
        for suite,n in [('decision-v7',1200),('transfer-v4',656)]:
            rows=[row(i) for i in range(n)];self.rows[(suite,'test')]=rows
            p=copy.deepcopy(rows[0]);p['levels'].reverse();p['variant']='permuted';p['kev'].update(id='perm',parent_id='0')
            present=copy.deepcopy(rows[0]);present['variant']='none_present';present['kev'].update(id='present',parent_id='0',none_key='n')
            present['levels'].append(dict(id='n',name='None',definition='None'))
            absent=copy.deepcopy(present);absent['variant']='none_absent';absent['kev']['id']='absent';absent['gold']='n';absent['levels']=absent['levels'][1:]
            self.vars[(suite,'test')]=[p,present,absent]
        for (suite,split),rows in self.rows.items():
            populations={'clean':rows}
            if split=='test':populations['variants']=self.vars[(suite,split)]
            outputs={}
            for kind,population in populations.items():
                path=self.C.partition_path(suite,split,kind=='variants',str(self.data));self.C.write_jsonl(path,population)
                outputs[kind]={'path':str(Path(path).relative_to(self.data)),'sha256':self.C.sha256_file(path)}
                self.files[path]=self.C.sha256_file(path)
            manifest['suites'].setdefault(suite,{'partitions':{}})['partitions'][split]={'outputs':outputs}
            if split=='train':continue
            for kind,population in [('clean',rows)]+([('variants',self.vars[(suite,split)]),('question_only',rows),('empty_input',rows)] if split=='test' else []):
                path=self.C.k_readout_path(str(self.run),suite,split,kind)
                values=[[0. if j==(i%len(r['levels'])) else -2. for j in range(len(r['levels']))] for i,r in enumerate(population)]
                # Exercise a true tie, distinct from the ordinary paired rows.
                if kind=='clean' and split=='test':values[3]=[0.,0.]
                self.scores[path]=values
                self.C.write_jsonl(path,[self.C.readout_row(r,s) for r,s in zip(population,values)])
        (self.data/'manifest.json').write_text(json.dumps(manifest))
        self.identity={'path':str(self.root/'model'),'sha256':'a'*64}
        rounddir=self.root/'round';rounddir.mkdir();(rounddir/'FINAL.json').write_text(json.dumps({'models':[self.identity]}))
        self.tickets={(s,'test'):self.TL.authorize_test_read(self.identity,s,'test',str(rounddir)) for s in self.C.SUITES}
        # Execute the exact original producer function, with in-memory fixtures
        # replacing only data IO/prechecks/scoring; metric implementations real.
        source=ast.parse(PRODUCER.read_text());node=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='run_track_k')
        proxy=SimpleNamespace(**vars(self.C))
        def partition(s,split,variants=False,**kw):
            return (self.vars[(s,split)] if variants else self.rows[(s,split)]),self.C.partition_path(s,split,variants,str(self.data))
        proxy.load_partition=partition
        proxy.partition_path=lambda s,split,variants=False:self.C.partition_path(s,split,variants,str(self.data))
        pc=SimpleNamespace(check_kev_manifest=lambda *a,**k:None,
            check_a=lambda *a,**k:{'train':{'gold_at_position_0':24,'n':24}},check_b=lambda *a,**k:None,check_c=lambda *a,**k:None)
        env=dict(C=proxy,D=self.D,V=self.V,PC=pc,DATA_FILES={},os=__import__('os'),note_data_file=lambda p:None,
            limit_partition=lambda rows,var,limit:(rows,var),DECLARED_DIFFERENCES=[],
            _score_k=lambda scorer,rows,path,*a,**kw:self.scores[path])
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<original-run-track-k>','exec'),env)
        args=SimpleNamespace(partitions=['calibration','test'],stages='k',limit=0,arm='K1',arm_kind='K1',primary_mode='full')
        block,_=env['run_track_k'](args,None,self.identity,str(self.run),lambda text:None,self.tickets)
        self.report={'header':{'model':self.identity,'arm':'K1','data_files':self.files},'track_k':block}

    def verify(self,report=None):
        for ticket in self.tickets.values():
            self.M.verify(ticket,str(self.run),kev_dir=str(self.data),report=report or self.report)

    def test_original_producer_matches_every_rebuilt_field(self):
        self.verify()
        self.assertEqual(self.report['track_k']['partitions']['decision-v7/test']['headline']['tie_count'],1)

    def test_secondary_calibration_and_degenerate_changes_refused(self):
        for kind in ('permutation','nota','operator','constant','fitted'):
            with self.subTest(kind=kind):
                report=copy.deepcopy(self.report);part=report['track_k']['partitions']['decision-v7/test']
                if kind in ('permutation','nota','operator'):part['secondary'][kind]['n']=999
                elif kind=='constant':part['arms']['constant']['kev_rule_accuracy']=.123
                else:report['track_k']['operator_fit']['fitted']={'forged':True}
                with self.assertRaisesRegex(ValueError,'differs'):self.verify(report)

    def test_producer_data_hash_mismatch_refused(self):
        report=copy.deepcopy(self.report);report['header']['data_files'][next(iter(self.files))]='0'*64
        with self.assertRaisesRegex(ValueError,'producer dataset hash'):self.verify(report)

    def test_extra_unverified_metric_refused(self):
        report=copy.deepcopy(self.report);report['track_k']['partitions']['decision-v7/test']['fabricated_accuracy']=1.
        with self.assertRaisesRegex(ValueError,'unverified partition'):self.verify(report)


if __name__=='__main__':unittest.main()
