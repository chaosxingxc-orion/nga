"""Real finisher and verifier subprocesses against a fixture Docker HTTP socket.

Only fixture adapter-byte identity and the Docker socket path are injected in
isolated test launchers. Production has no bypass or test mode.
"""
import functools
import http.server
import importlib.util
import json
from pathlib import Path
import socketserver
import subprocess
import sys
import threading
import unittest

spec=importlib.util.spec_from_file_location('fixtures',Path(__file__).with_name('test_verify_reference_nimble.py'))
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
v=fixtures.v

class ChainTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CompleteArtifactTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.p=self.fixture.p
        self.out=self.p/'finisher';self.out.mkdir()
        self.info={'Id':'fixture-id','Image':'image','Config':{'Cmd':['bash','run.sh'],'Entrypoint':None},
                   'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci3'}]},
                   'State':{'Status':'exited','ExitCode':0}}
        outer=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.assertEqual(self.path,'/containers/fixture-container/json')
                body=json.dumps(outer.info).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        self.sock=self.p/'docker.sock'
        self.server=socketserver.UnixStreamServer(str(self.sock),Handler)
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        source=Path(__file__).resolve().parent
        auditor=self.out/'fixture_auditor.py'
        auditor.write_text('import importlib.util\nfrom pathlib import Path\n'+
            f"s=importlib.util.spec_from_file_location('audit',{str(source/'verify_reference_nimble.py')!r})\n"+
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\noriginal=m.sha\n"+
            f"m.sha=lambda p:m.ADAPTER_SHA if str(p)=={str(self.p/'adapter/adapter_model.safetensors')!r} else original(p)\n"+
            "m.main()\n")
        launcher=self.out/'fixture_finisher.py'
        launcher.write_text('import importlib.util,functools\n'+
            f"s=importlib.util.spec_from_file_location('finish',{str(source/'nimble_reference_finish.py')!r})\n"+
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"+
            f"m.container_info=functools.partial(m.container_info,socket_path={str(self.sock)!r})\n"+
            "m.main()\n")
        files=[auditor,launcher,source/'verify_reference_nimble.py',source/'nimble_reference_finish.py',self.p/'config.json']
        self.plan=self.out/'plan.json'
        self.plan.write_text(json.dumps({'out':str(self.out),'config':str(self.p/'config.json'),'auditor':str(auditor),'files':{str(p):v.sha(p) for p in files}}))
        self.command=[sys.executable,'-P',str(launcher),'--plan',str(self.plan)]
    def run_chain(self):
        return subprocess.run(self.command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
    def test_valid_real_chain_and_terminal_preserved_on_retry(self):
        result=self.run_chain();self.assertEqual(result.returncode,0,result.stderr)
        terminal=self.out/'FINISH_COMPLETE.json';before=terminal.read_bytes();data=json.loads(before)
        self.assertEqual(data['rc'],0);self.assertEqual(data['status'],'COMPLETED_SCOPED_REVIEW_REQUIRED')
        audit=v.load(self.out/'INDEPENDENT_AUDIT.json');self.assertEqual(audit['records_verified'],1884)
        for name,h in data['outputs'].items():self.assertEqual(v.sha(self.out/name),h)
        retry=self.run_chain();self.assertNotEqual(retry.returncode,0);self.assertEqual(terminal.read_bytes(),before)
    def test_forged_report_with_rebound_terminal_rejected_by_real_auditor(self):
        report=v.load(self.p/'report.json');report['suites']['paws']['summary']['all']['accuracy']=.5
        self.fixture.write(self.p/'report.json',report);self.fixture.rebind()
        result=self.run_chain();self.assertNotEqual(result.returncode,0)
        data=v.load(self.out/'FINISH_COMPLETE.json');self.assertEqual(data['rc'],1);self.assertEqual(data['stage'],'independent_audit')
        self.assertFalse((self.out/'INDEPENDENT_AUDIT.json').exists())
    def test_wrong_actual_device_rejected_before_audit(self):
        self.info['HostConfig']['Devices']=[{'PathOnHost':'/dev/davinci2'}]
        result=self.run_chain();self.assertNotEqual(result.returncode,0)
        data=v.load(self.out/'FINISH_COMPLETE.json');self.assertEqual(data['rc'],1)
        self.assertIn('device binding',data['error'])
        self.assertFalse((self.out/'INDEPENDENT_AUDIT.json').exists())

if __name__=='__main__':unittest.main()
