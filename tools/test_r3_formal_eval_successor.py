import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from tools import r3_formal_dev_successor as G
from tools import r3_formal_eval_guard_prepare as P

class EvalEdgeTests(unittest.TestCase):
    def test_relocation_preserves_only_declared_paths(self):
        original={'code_mounts':[{'source':'/original/code','destination':'/code','readonly':True}],
          'files':{'/original/code/x.py':'a','/model/weight':'b'},'command':['python','--out','/original/results','--round-dir','/original/identity'],
          'training_variant':{'seed':2}}
        actual=copy.deepcopy(original);actual['code_mounts'][0]['source']='/copy/code'
        actual['files']={'/copy/code/x.py':'a','/model/weight':'b'}
        actual['command']=['python','--out','/actual/results','--round-dir','/actual/identity']
        self.assertEqual(G.normalized_spec(actual,original,'/actual','/original'),original)
        for mutate in [lambda d:d['training_variant'].update(seed=3),lambda d:d['files'].update({'/model/weight':'c'}),lambda d:d['command'].append('--test')]:
            bad=copy.deepcopy(actual);mutate(bad)
            with self.assertRaises(RuntimeError):G.normalized_spec(bad,original,'/actual','/original')

    def fixture(self,root):
        out=Path(root);a=out/'attempts/1';a.mkdir(parents=True)
        p={'successor_guard':{'previous_evaluation':{'execution':{'path':str(out/'execution.json'),'sha256':'a'*64}}}}
        previous={'out':root}
        core=types.SimpleNamespace(predecessor=lambda *a:None)
        return out,a,p,previous,core

    def test_missing_terminal_does_not_accept_old_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            out,a,p,previous,core=self.fixture(d)
            self.assertIsNone(G.evaluation_predecessor(p,None,core,previous))

    def test_failed_synthetic_boolean_and_later_attempt_reject(self):
        for end in [{'attempt':1,'exit_code':1,'scientific_acceptance':False},
                    {'attempt':1,'exit_code':0,'scientific_acceptance':False,'source':'retained-container-exit'},
                    {'attempt':True,'exit_code':0,'scientific_acceptance':False},
                    {'attempt':1,'exit_code':False,'scientific_acceptance':False},
                    {'attempt':2,'exit_code':0,'scientific_acceptance':False}]:
            with tempfile.TemporaryDirectory() as d:
                out,a,p,previous,core=self.fixture(d);(out/'ENGINEERING_EVAL_EXIT.json').write_text(json.dumps(end))
                with self.assertRaises(RuntimeError):G.evaluation_predecessor(p,None,core,previous)
        with tempfile.TemporaryDirectory() as d:
            out,a,p,previous,core=self.fixture(d);(out/'attempts/2').mkdir()
            with self.assertRaises(RuntimeError):G.evaluation_predecessor(p,None,core,previous)

    def test_release_claim_pin_required(self):
        with tempfile.TemporaryDirectory() as d:
            out,a,p,previous,core=self.fixture(d)
            (out/'ENGINEERING_EVAL_EXIT.json').write_text(json.dumps({'attempt':1,'exit_code':0,'scientific_acceptance':False}))
            (a/'CLAIM.json').write_text('{}');(a/'RELEASE.json').write_text(json.dumps({'claim_sha256':'0'*64}))
            core.predecessor=lambda *args:{'attempt':1}
            with self.assertRaisesRegex(RuntimeError,'claim binding'):G.evaluation_predecessor(p,None,core,previous)
            (a/'RELEASE.json').write_text(json.dumps({'claim_sha256':G.sha(a/'CLAIM.json')}))
            self.assertEqual(G.evaluation_predecessor(p,None,core,previous),{'attempt':1})

    def test_registered_eval_edge_only(self):
        with tempfile.TemporaryDirectory() as d:
            spec={'training_variant':{'formal_role_identity':{'role':'samechip_s2','chip':1,'schedule_sha256':'s'}},'training':'/train/repeat'}
            previous={'schema':'r3-engineering-posttrain-execution-v1','test_read':False,'scientific_acceptance':False,'chip':1,'out':d,'spec':d+'/plan.json'}
            Path(previous['spec']).write_text(json.dumps({'training_variant':{'formal_role_identity':{'role':'primary_s2','chip':1,'schedule_sha256':'s'}},'training':'/train/primary'}))
            schedule={'nodes':[{'id':'samechip_s2_dev','training_id':'samechip_s2','kind':'dev_calibration_track_t_readout','depends_on':['primary_s2_dev_release'],'chip':1},{'id':'samechip_s2','out':'/train/repeat'},{'id':'primary_s2','out':'/train/primary'}]}
            self.assertEqual(P.edge(spec,{'chip':1},previous,schedule,{'path':d+'/execution.json'},{'sha256':'s'}),('samechip_s2','samechip_s2_dev'))
            for bad in [dict(schedule,nodes=[dict(schedule['nodes'][0],depends_on=['primary_s2_release'])]+schedule['nodes'][1:]),dict(schedule,nodes=[dict(schedule['nodes'][0],chip=2)]+schedule['nodes'][1:])]:
                with self.assertRaises(ValueError):P.edge(spec,{'chip':1},previous,bad,{'path':d+'/execution.json'},{'sha256':'s'})

if __name__=='__main__':unittest.main()
