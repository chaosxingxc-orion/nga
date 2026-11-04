import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from tools import experiment_event_relay_v1 as R


class Relay(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.state={'events':{}}
    def put(self,name,d):
        p=self.root/name; p.write_text(json.dumps(d)); return str(p)
    def child(self):
        script=self.root/'child.py'; out=self.root/'signals'; ready=self.root/'ready'
        script.write_text("import signal,time,pathlib\np=pathlib.Path("+repr(str(out))+")\ndef handle(*_):\n with p.open('a') as f:f.write('wake\\n')\nsignal.signal(signal.SIGUSR1,handle)\npathlib.Path("+repr(str(ready))+").touch()\nwhile True:time.sleep(.02)\n")
        p=subprocess.Popen([sys.executable,'-B','-P',str(script)])
        self.addCleanup(lambda:(p.terminate(),p.wait()) if p.poll() is None else None)
        deadline=time.monotonic()+3
        while not ready.exists():
            self.assertLess(time.monotonic(),deadline);time.sleep(.01)
        i=R.identity(p.pid);s=self.put('service.json',{'process':i})
        return p,out,{'identity':i,'service':{'path':s,'sha256':R.sha(s)}}
    def event(self,kind='release'):
        plan=self.put('PLAN.json',{'run':'r3_runs/example','chip':1})
        trigger=self.put('RELEASE.json',{'schema':'r3-resource-release-v1','run':'r3_runs/example','chip':1,'exit_code':0,'scientific_acceptance':False})
        return dict(id='e',kind=kind,plan=plan,trigger=trigger,run='r3_runs/example',target={})
    def test_real_signal_and_duplicate_dedup(self):
        p,out,target=self.child();e=self.event();e['target']=target;c={'events':[e]}
        R.tick(c,self.state,lambda _:None);R.tick(c,self.state,lambda _:None)
        deadline=time.monotonic()+2
        while not out.exists():self.assertLess(time.monotonic(),deadline);time.sleep(.01)
        self.assertEqual(out.read_text(),'wake\n');self.assertEqual(self.state['events']['e']['state'],'delivered')
    def test_stale_pid_identity_never_signals(self):
        p,out,t=self.child();t['identity']['start_ticks']=str(int(t['identity']['start_ticks'])+1)
        with self.assertRaises(ValueError):R.wake(t)
        self.assertFalse(out.exists());self.assertIsNone(p.poll())
    def test_service_hash_change_never_signals(self):
        p,out,t=self.child();Path(t['service']['path']).write_text('{}')
        with self.assertRaises(ValueError):R.wake(t)
        self.assertFalse(out.exists())
    def test_missing_terminal_does_not_publish_or_signal(self):
        e=self.event('reviewed');Path(e['trigger']).unlink()
        R.tick({'events':[e]},self.state,lambda _:None,signaler=lambda _:self.fail('signal'))
        self.assertEqual(self.state['events'],{})
    def test_failed_or_boolean_terminal_rejected(self):
        for code in (1,False):
            e=self.event('reviewed');Path(e['trigger']).write_text(json.dumps({'exit_code':code,'npu_launched':False}))
            with self.assertRaises(ValueError):R.proof({},e)
    def test_bad_plan_hash_blocks(self):
        e=self.event();e['plan_sha256']='0'*64
        R.tick({'events':[e]},self.state,lambda _:None,signaler=lambda _:self.fail('signal'))
        self.assertEqual(self.state['events']['e']['state'],'blocked')
    def test_publication_is_byte_copy_no_overwrite(self):
        source=self.put('review.json',{'verdict':'PASS'});e={'review':source,'destination':str(self.root/'approved.json')};p={'review_sha256':R.sha(source)}
        R.publish(e,p);R.publish(e,p);self.assertEqual(Path(source).read_bytes(),Path(e['destination']).read_bytes())
        Path(e['destination']).write_text('{}')
        with self.assertRaises(ValueError):R.publish(e,p)
    def test_changed_review_refused(self):
        source=self.put('review.json',{});e={'review':source,'destination':str(self.root/'approved.json')}
        with self.assertRaises(ValueError):R.publish(e,{'review_sha256':'0'*64})
        self.assertFalse(Path(e['destination']).exists())
    def test_crash_after_publish_reconciles_identical_bytes(self):
        source=self.put('review.json',{'verdict':'PASS'});e=self.event('reviewed');e.update(review=source,destination=str(self.root/'approved.json'))
        p={'review_sha256':R.sha(source),'plan_sha256':R.sha(e['plan']),'trigger_sha256':R.sha(e['trigger'])}
        self.state['events']['e']={'state':'intent','proof':p}
        R.publish(e,p);signals=[];R.tick({'events':[e]},self.state,lambda _:None,signaler=lambda _:signals.append(1),prover=lambda *_:p)
        self.assertEqual(signals,[1]);self.assertEqual(self.state['events']['e']['state'],'delivered')
    def test_mutated_pending_event_requires_reconcile(self):
        e=self.event();self.state['events']['e']={'state':'intent','proof':{'old':1}}
        R.tick({'events':[e]},self.state,lambda _:None,signaler=lambda _:self.fail('signal'))
        self.assertEqual(self.state['events']['e']['state'],'blocked')
    def test_review_requires_bound_independent_approval_validator(self):
        from unittest.mock import patch
        e=self.event('reviewed');Path(e['trigger']).write_text(json.dumps({'exit_code':0,'npu_launched':False}))
        code=self.root/'exact.py';code.write_text('# independent code')
        e.update(review=self.put('review.json',{'reviewer':'independent','review_kind':'independent_execution_review',
            'review_evidence':{str(code):R.sha(code)}}),intent=self.put('intent.json',{'plan':{'path':e['plan'],'sha256':R.sha(e['plan'])},'npu_launched':False}),
            reviewer='independent',review_code={'path':str(code),'sha256':R.sha(code)},destination=str(self.root/'approved.json'),job='j',dispatcher={})
        dc=self.put('dispatch.json',{'jobs':[{'id':'j','plan':e['plan'],'review':e['destination']}]})
        e['dispatcher_config']={'path':dc,'sha256':R.sha(dc)}
        class D:
            @staticmethod
            def approved(c,j):
                self.assertEqual(j['review'],e['review'])
                return {'plan_sha256':R.sha(e['plan']),'review_sha256':R.sha(e['review'])}
        with patch.object(R,'module',return_value=D):
            result=R.proof({},e);self.assertEqual(result['review_sha256'],R.sha(e['review']))
        bad=R.read(e['review']);bad['reviewer']='other';Path(e['review']).write_text(json.dumps(bad))
        with patch.object(R,'module',side_effect=AssertionError('must reject before verifier')):
            with self.assertRaises(ValueError):R.proof({},e)

    def test_actual_controller_stop_and_lock(self):
        p,out,target=self.child();e=self.event();Path(e['trigger']).unlink();e['target']=target
        config={'schema':'experiment-event-relay-v1','poll_seconds':15,'npu_launch_allowed':False,'scientific_acceptance':False,'files':{target['service']['path']:target['service']['sha256']},'events':[e],'output':str(self.root/'relay')}
        cp=self.put('CONFIG.json',config);cmd=[sys.executable,'-B','-P',R.__file__,'--config',cp,'--sha256',R.sha(cp)]
        child=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);self.addCleanup(lambda:(child.kill(),child.wait()) if child.poll() is None else None)
        deadline=time.monotonic()+3
        while not (self.root/'relay/digest.json').exists():self.assertLess(time.monotonic(),deadline);time.sleep(.01)
        other=subprocess.run(cmd,capture_output=True,timeout=3);self.assertNotEqual(other.returncode,0)
        child.terminate();child.wait(timeout=3);self.assertEqual(R.read(self.root/'relay/EXIT.json')['exit_code'],0)


if __name__=='__main__':unittest.main()
