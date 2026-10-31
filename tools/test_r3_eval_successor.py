import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('successor',Path(__file__).with_name('r3_eval_successor.py'))
S=importlib.util.module_from_spec(s);s.loader.exec_module(S)

class Successors(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.prev=self.root/'previous';self.prev.mkdir();self.out=self.root/'next';self.out.mkdir()
        self.plan={'out':str(self.out),'launcher':'/frozen/launcher.py','container':'next','chip':1}
        self.write(self.out/'execution.json',self.plan)
        self.job={'id':'fixture','previous_eval':str(self.prev),'next_execution':str(self.out/'execution.json'),'next_sha256':S.sha(self.out/'execution.json'),'chip':1}
    def write(self,p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
    def previous(self,rc=0,attempt=1):
        plan={'out':str(self.prev),'chip':1,'run':'r3_runs/previous','launcher':'/frozen/previous.py','container':'previous'}
        p=self.prev/'execution.json';self.write(p,plan)
        end={'exit_code':rc,'attempt':attempt};self.write(self.prev/'ENGINEERING_EVAL_EXIT.json',end)
        a=self.prev/'attempts'/str(attempt);self.write(a/'EXIT.json',end)
        self.write(a/'RELEASE.json',{'container_id':'old-id','exit_code':rc,'chip':1,'run':plan['run'],'scientific_acceptance':False})
        self.write(a/'LAUNCH_RECEIPT.json',{'id':'old-id'})
        cmd=[S.sys.executable,'-P',plan['launcher'],'supervise','--plan',str(p),'--sha256',S.sha(p),'--attempt',str(attempt)]
        self.write(self.prev/'SUPERVISOR_RECEIPT.json',{'pid':99,'command':cmd})
        return {'Id':'old-id','State':{'Status':'exited','ExitCode':rc}}
    def test_idle_chip_without_predecessor_release_never_launches(self):
        with patch.object(S.subprocess,'run') as run:
            self.assertEqual(S.tick(self.job)['status'],'waiting_previous_release');run.assert_not_called()
    def test_failure_release_can_handoff_and_intent_prevents_duplicate(self):
        actual=self.previous(7,2)
        with patch.object(S,'inspect',return_value=actual),patch.object(S.subprocess,'run') as run:
            x=S.tick(self.job);self.assertEqual(x['status'],'launch_requested');self.assertEqual(x['previous']['exit_code'],7)
            self.assertEqual(run.call_count,2)
            self.assertEqual(S.tick(self.job)['status'],'needs_repair');self.assertEqual(run.call_count,2)
    def test_mismatch_live_container_and_uncertain_observation_refused(self):
        actual=self.previous()
        with patch.object(S,'inspect',return_value=dict(actual,Id='other')):
            with self.assertRaisesRegex(RuntimeError,'identity'):S.predecessor(self.job)
        actual['State']['Status']='running'
        with patch.object(S,'inspect',return_value=actual):
            with self.assertRaisesRegex(RuntimeError,'not terminal'):S.predecessor(self.job)
        with patch.object(S,'inspect',side_effect=RuntimeError('daemon timeout')):
            with self.assertRaisesRegex(RuntimeError,'timeout'):S.predecessor(self.job)
    def test_superseding_retry_does_not_handoff_old_marker(self):
        self.previous()
        p=self.prev/'SUPERVISOR_RECEIPT.json';r=S.load(p);r['command'][-1]='2';self.write(p,r)
        with self.assertRaisesRegex(RuntimeError,'supervisor identity'):S.predecessor(self.job)
    def test_successor_live_and_retained_observed(self):
        self.write(self.out/'SUCCESSOR_START_INTENT.json',{'previous':{'exit_code':0}})
        cmd=[S.sys.executable,'-P',self.plan['launcher'],'supervise','--plan',self.job['next_execution'],'--sha256',self.job['next_sha256'],'--attempt','1']
        self.write(self.out/'SUPERVISOR_RECEIPT.json',{'pid':123,'command':cmd})
        with patch.object(S,'process_matches',return_value=True):self.assertEqual(S.tick(self.job)['status'],'supervisor_live')
        self.write(self.out/'attempts/1/LAUNCH_RECEIPT.json',{'id':'new-id'})
        with patch.object(S,'inspect',return_value={'Id':'new-id','State':{'Status':'running'}}):
            self.assertEqual(S.tick(self.job)['status'],'handed_off')
    def test_process_identity_is_exact_not_pid_only(self):
        root=self.root/'proc';p=root/'123';p.mkdir(parents=True);(p/'cmdline').write_bytes(b'python\0one.py\0')
        self.assertTrue(S.process_matches({'pid':123,'command':['python','one.py']},root))
        self.assertFalse(S.process_matches({'pid':123,'command':['python','two.py']},root))
        self.assertFalse(S.process_matches({'pid':124,'command':['python','one.py']},root))
    def test_changed_execution_refused_before_wait(self):
        self.write(self.out/'execution.json',dict(self.plan,chip=2))
        with self.assertRaisesRegex(RuntimeError,'next plan changed'):S.tick(self.job)

    def test_engineering_training_predecessor_requires_exact_terminal_and_release(self):
        actual=self.previous()
        original=self.prev/'execution.json'; p=S.load(original)
        p.update(schema='r3-engineering-k1-plan-v1',review_sha256='PENDING')
        path=self.prev/'plan.json';self.write(path,p)
        (self.prev/'ENGINEERING_EVAL_EXIT.json').rename(self.prev/'TRAIN_EXIT.json')
        pin=S.hashlib.sha256((json.dumps(dict(p,review_sha256='PENDING'),indent=2,sort_keys=True)+'\n').encode()).hexdigest()
        r=S.load(self.prev/'SUPERVISOR_RECEIPT.json');r['command'][5]=str(path);r['command'][7]=pin
        self.write(self.prev/'SUPERVISOR_RECEIPT.json',r)
        self.job['previous_kind']='training'
        with patch.object(S,'inspect',return_value=actual):
            self.assertEqual(S.predecessor(self.job)['exit_code'],0)
            actual['State']['Status']='running'
            with self.assertRaisesRegex(RuntimeError,'not terminal'):S.predecessor(self.job)
        (self.prev/'attempts/1/RELEASE.json').unlink()
        self.assertIsNone(S.predecessor(self.job))

    def test_engineering_training_successor_uses_canonical_pin_and_same_handoff(self):
        self.plan.update(schema='r3-engineering-k1-plan-v1',review_sha256='PENDING')
        self.write(self.out/'execution.json',self.plan);self.job['next_kind']='training'
        self.job['next_sha256']=S.next_pin(self.job)
        actual=self.previous()
        with patch.object(S,'inspect',return_value=actual),patch.object(S.subprocess,'run') as run:
            self.assertEqual(S.tick(self.job)['status'],'launch_requested')
            self.assertEqual(run.call_args.args[0][-1],self.job['next_sha256'])
        self.plan['schema']='r3-formal-k1-plan-v1';self.write(self.out/'execution.json',self.plan)
        with self.assertRaisesRegex(RuntimeError,'engineering training'):S.next_pin(self.job)

if __name__=='__main__':unittest.main()
