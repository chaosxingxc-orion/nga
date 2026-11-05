import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest

from tools import unified_cpu_consumer_v1 as C
from tools import test_unified_cpu_consumer_v1 as fixtures
from tools import watchdog

put = fixtures.put

FOLLOWER = Path(__file__).with_name('unified_container_log_follower_v1.py').resolve()
FAKE = '''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
r=Path(os.environ['FAKE_ROOT'])
with (r/'commands').open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1]=='inspect':
 print((r/'inspect.json').read_text())
elif sys.argv[1:4]==['logs','--follow','--timestamps']:
 os.write(1,b'2026-01-01T00:00:00Z first\\n2026-01-01T00:00:00Z second\\npart')
 (r/'started').touch()
 (r/'childpid').write_text(str(os.getpid()))
 while not (r/'release').exists(): time.sleep(.02)
 os.write(1,b'ial\\n')
 os.write(2,b'error: sample\\n')
 sys.exit(int(os.environ.get('LOG_EXIT','0')))
else: sys.exit(9)
'''

class FollowerTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ConsumerTest(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root; self.c=self.fixture.c; self.d=self.fixture.d
        self.release=threading.Event(); self.waiting=threading.Event(); self.errors=[]
        def wait():
            self.waiting.set(); self.release.wait(10)
        self.d.on_wait=wait
        def consumer():
            try: C.Consumer(self.d).run(self.c)
            except Exception as e: self.errors.append(e)
        self.thread=threading.Thread(target=consumer); self.thread.start()
        self.addCleanup(self.finish_consumer)
        self.assertTrue(self.waiting.wait(5))
        self.ob=next(iter(self.d.objects.values()))
        (self.root/'inspect.json').write_text(json.dumps([self.ob]))
        binary=self.root/'docker'; binary.write_text(FAKE); binary.chmod(0o755)
        self.env=dict(os.environ, PATH=str(self.root)+os.pathsep+os.environ['PATH'], FAKE_ROOT=str(self.root), PYTHONDONTWRITEBYTECODE='1')
        self.ref=put(self.root/'consumer.json',self.c)
        self.output=self.root/'capture'; self.output.mkdir(mode=0o700)
        self.command=[sys.executable,str(FOLLOWER),'--config',self.ref['path'],'--sha256',self.ref['sha256'],'--output',str(self.output)]
    def finish_consumer(self):
        self.release.set(); self.thread.join(5)
    def launch(self):
        return subprocess.Popen(self.command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def await_file(self,p):
        end=time.monotonic()+5
        while time.monotonic()<end:
            if p.exists(): return
            time.sleep(.02)
        self.fail('timed out waiting for '+str(p))
    def end_consumer(self):
        self.release.set(); self.thread.join(5); self.assertFalse(self.thread.is_alive()); self.assertFalse(self.errors)
        (self.root/'inspect.json').write_text(json.dumps([self.ob]))
    def test_live_replay_completion_and_lock(self):
        result=Path(self.c['output'])/'result'; result.mkdir()
        (result/'heartbeat.json').write_text('{"completed": 7, "total": 10, "unrelated": "secret"}')
        p=self.launch(); self.await_file(self.root/'started')
        log=self.output/'attempts/00000001/stdout.log'; self.await_file(log)
        self.assertIn(b'part',log.read_bytes())
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0)
        beat=json.loads((self.output/'heartbeat.json').read_text()); self.assertEqual(beat['completed'],7)
        self.assertEqual(beat['total'],10); self.assertNotIn('unrelated',str(beat))
        self.assertEqual(watchdog.read_json_heartbeat(self.output/'heartbeat.json')[0]['done'],7)
        other=self.root/'other'; other.mkdir(mode=0o700)
        q=subprocess.run(self.command[:-1]+[str(other)],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0)
        (self.root/'release').touch(); out,err=p.communicate(timeout=5)
        self.assertNotEqual(p.returncode,0,(out,err))
        t=json.loads(out); self.assertEqual(t['status'],'stream_eof_not_completion'); self.assertEqual(t['stream_returncode'],0)
        first=log.read_bytes(); self.assertEqual(first,b'2026-01-01T00:00:00Z first\n2026-01-01T00:00:00Z second\npartial\n')
        self.assertEqual(json.loads((self.output/'attempts/00000001/DIGEST.json').read_text())['signatures'][0]['line'],1)
        self.end_consumer()
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(q.returncode,0,q.stderr+q.stdout)
        self.assertEqual(json.loads(q.stdout)['consumer_completion']['exit_code'],0)
        self.assertEqual((self.output/'attempts/00000002/stdout.log').read_bytes(),first)
        cmds=[json.loads(x) for x in (self.root/'commands').read_text().splitlines()]
        self.assertIn(['logs','--follow','--timestamps',self.ob['Id']],cmds)
    def test_foreign_id_and_owner_rejected(self):
        foreign=dict(self.ob,Id='f'*64); (self.root/'inspect.json').write_text(json.dumps([foreign]))
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertEqual(json.loads(q.stdout)['status'],'error')
        self.assertNotIn('logs', (self.root/'commands').read_text())
        owner=next((Path(self.c['controller'])/'jobs').glob('*/OWNER.json')); data=json.loads(owner.read_text()); data['name']='foreign'; owner.write_text(json.dumps(data))
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertIn('owner',q.stderr)
    def test_false_boolean_completion_rejected(self):
        self.end_consumer(); (self.root/'release').touch()
        terminal=next((Path(self.c['controller'])/'jobs').glob('*/TERMINAL.json'))
        ack=terminal.parent/'ACK.json'; t=json.loads(terminal.read_text()); t['exit_code']=False; terminal.write_text(json.dumps(t))
        a=json.loads(ack.read_text()); a['exit_code']=False; a['terminal_sha256']=hashlib.sha256(terminal.read_bytes()).hexdigest(); ack.write_text(json.dumps(a))
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertEqual(json.loads(q.stdout)['status'],'error')

    def test_stream_failure_with_valid_completion(self):
        self.end_consumer(); (self.root/'release').touch()
        q=subprocess.run(self.command,env=dict(self.env, LOG_EXIT='7'),capture_output=True,text=True,timeout=5)
        t=json.loads(q.stdout); self.assertNotEqual(q.returncode,0)
        self.assertEqual(t['status'],'stream_failed'); self.assertEqual(t['stream_returncode'],7)
        self.assertEqual(t['consumer_completion']['exit_code'],0)

    def test_oversized_and_malformed_progress_is_unknown(self):
        result=Path(self.c['output'])/'result'; result.mkdir()
        hb=result/'heartbeat.json'; hb.write_text('{"completed":7,"extra":"'+'x'*70000+'"}')
        p=self.launch(); self.await_file(self.root/'started')
        beat=json.loads((self.output/'heartbeat.json').read_text())
        self.assertNotIn('completed',beat); self.assertLess((self.output/'heartbeat.json').stat().st_size,1024)
        self.assertIsNone(watchdog.read_json_heartbeat(self.output/'heartbeat.json')[1])
        hb.write_text('{bad'); (self.root/'release').touch(); p.communicate(timeout=5)
        self.assertNotIn('completed',json.loads((self.output/'heartbeat.json').read_text()))

    def test_owner_numeric_boolean_rejected(self):
        owner=next((Path(self.c['controller'])/'jobs').glob('*/OWNER.json'))
        data=json.loads(owner.read_text()); data['config']['slots']=True; owner.write_text(json.dumps(data))
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertIn('owner',q.stderr)
        self.assertFalse((self.root/'commands').exists())

    def test_closed_config_and_bad_cadence(self):
        cfg=put(self.root/'capture-config.json',{'schema':'unified-log-capture-v1','consumer_config':self.ref,'output':str(self.output),'heartbeat_seconds':9})
        cmd=[sys.executable,str(FOLLOWER),'serve','--config',cfg['path'],'--sha256',cfg['sha256']]
        q=subprocess.run(cmd,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertIn('cadence',q.stderr)
        cfg=put(self.root/'capture-config.json',{'schema':'unified-log-capture-v1','consumer_config':self.ref,'output':str(self.output),'heartbeat_seconds':10,'command':'bad'})
        cmd[-1]=cfg['sha256']; q=subprocess.run(cmd,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertIn('closed',q.stderr)

    def test_abrupt_follower_death_retains_attempt_and_replay(self):
        p=self.launch(); self.await_file(self.root/'childpid')
        log=self.output/'attempts/00000001/stdout.log'; self.await_file(log)
        p.kill(); p.communicate(timeout=5)
        os.kill(int((self.root/'childpid').read_text()),15)
        self.assertIn(b'first',log.read_bytes())
        self.assertFalse((log.parent/'TERMINAL.json').exists())
        (self.root/'release').touch()
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(json.loads(q.stdout)['status'],'stream_eof_not_completion')
        self.assertIn(b'second', (self.output/'attempts/00000002/stdout.log').read_bytes())

    def test_corrupt_config_pin_before_docker(self):
        Path(self.ref['path']).write_text('{}')
        q=subprocess.run(self.command,env=self.env,capture_output=True,text=True,timeout=5)
        self.assertNotEqual(q.returncode,0); self.assertIn('pinned file changed',q.stderr)
        self.assertFalse((self.root/'commands').exists())

if __name__=='__main__': unittest.main()
