"""Portable provider tests: run the real wrapper and child with the source tree hidden."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import test_unified_resource_provider_v1 as provider_fixture
from tools import unified_configured_resource_v1 as W
from tools import unified_resource_lease_v1 as lease

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT/'tools/resource-provider-v3-runtime'
REVIEW = ROOT/'.local/reviews/engineering-resource-strict-json-astra-20261105-v3'


def put(path, data):
    path.write_text(json.dumps(data))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


DRIVER = '''import importlib.util,json,os,signal,subprocess,sys,time
from pathlib import Path
s=importlib.util.spec_from_file_location('wrapper',sys.argv[1]); w=importlib.util.module_from_spec(s); s.loader.exec_module(w)
a=json.loads(Path(sys.argv[2]).read_text())
if a['mode']=='timeout':
    original=w.subprocess.Popen
    def stop(*args,**kwargs):
        p=original(*args,**kwargs); os.kill(p.pid,signal.SIGSTOP); return p
    w.subprocess.Popen=stop
start=time.monotonic()
try:
    result=w.observe(a['config'],a['graph_pin'],a['graph'],'/caller/cannot-select-python',a['state'])
    print(json.dumps({'result':result,'elapsed':time.monotonic()-start}))
except Exception as e:
    print(json.dumps({'error':type(e).__name__,'detail':str(e),'elapsed':time.monotonic()-start}))
'''


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nga-portable-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        target = self.root/'copy/tools'
        target.mkdir(parents=True)
        shutil.copy2(ROOT/'tools/unified_configured_resource_v1.py', target)
        shutil.copytree(ASSET, target/'resource-provider-v3-runtime')
        # An ambient regular tools package must not shadow the reviewed one.
        (target/'__init__.py').write_text("raise RuntimeError('wrong tools package')\n")
        self.driver = self.root/'driver.py'
        self.driver.write_text(DRIVER)
        p = provider_fixture.ProviderTests('test_free_real_lineage_and_dag')
        p.setUp(); self.addCleanup(p.doCleanups); p.setup_provider(1)
        self.fixture = p
        p.pc['max_age_seconds'] = 5
        pc = put(p.root/'portable-pc.json', p.pc)
        self.config = put(p.root/'portable-config.json', {'schema':'unified-configured-resource-v1','provider_config':pc})
        self.graph = copy.deepcopy(p.g)
        binding = put(p.root/'portable-binding.json', {'schema':'unified-dag-binding-v1','host_config':p.pc['host_configs'][0]})
        self.graph['nodes'][0]['action'] = {'binding':binding,'review':binding}
        self.graph_pin = put(p.root/'portable-graph.json', self.graph)
        self.state = self.root/'state'; self.state.mkdir(mode=0o700)

    def run_copy(self, mode='normal', config=None):
        args = {'config':config or self.config, 'graph_pin':self.graph_pin, 'graph':self.graph, 'state':str(self.state), 'mode':mode}
        data = self.root/'args.json'; data.write_text(json.dumps(args))
        # Hide the entire original repository, including .local/reviews, from both
        # parent and provider child. The fixture and copied package are elsewhere.
        cmd = ['bwrap','--ro-bind','/','/','--dev','/dev','--bind','/tmp','/tmp','--tmpfs',str(ROOT),'--chdir',str(self.root), '--', sys.executable,'-B','-I',str(self.driver),str(self.root/'copy/tools/unified_configured_resource_v1.py'),str(data)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_actual_child_snapshot_and_source_pins(self):
        out = self.run_copy()
        self.assertIn('result',out)
        snapshot = out['result']
        saved = next((self.state/'resource-observations').glob('*/snapshot.json'))
        self.assertEqual(snapshot,json.loads(saved.read_text()))
        self.assertEqual(snapshot, {'schema':'nga-dag-observation-v1', 'graph_sha256':hashlib.sha256(json.dumps(self.graph,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(), 'as_of':snapshot['as_of'], 'authority':'adapter_observations', 'observations':{}, 'resources':{str(i):'unknown' for i in range(8)}})
        receipt = json.loads(saved.with_name('receipt.json').read_text())
        paths = {p['path'] for p in receipt['source_pins']}
        for rel in W.CLOSURE:
            self.assertIn(str(self.root/'copy/tools/resource-provider-v3-runtime'/rel), paths)
        self.assertTrue(receipt['fresh'])

    def test_malformed_changed_payload_and_interpreter_ignored(self):
        bad=put(self.root/'bad.json',{'schema':'bad'})
        self.assertEqual(self.run_copy(config=bad)['error'],'ValueError')
        f=self.root/'copy/tools/resource-provider-v3-runtime/tools/experiment_dag.py'
        f.write_bytes(f.read_bytes()+b'\n# changed\n')
        self.assertEqual(self.run_copy()['error'],'ValueError')

    def test_schema_rejects_invalid_host_task(self):
        p=self.fixture
        host=json.loads(Path(p.pc['host_configs'][0]['path']).read_text())
        host['task']['unexpected_fixture_field']=True
        host['config']=put(p.root/'bad-task.json',host['task'])
        launch={k:host[k] for k in ('name','image','entrypoint','mounts','task','config','output')}
        host['lease']['task_sha256']=lease.digest(launch)
        host['lease']['acceptance']=put(p.root/'bad-task-accept.json',{'schema':'unified-resource-acceptance-v1','decision':'accept','policy_sha256':host['lease']['policy']['sha256'],'config_sha256':lease.config_hash(host['lease'])})
        p.pc['host_configs']=[put(p.root/'bad-host.json',host)]
        pc=put(p.root/'bad-schema-provider.json',p.pc)
        cfg=put(p.root/'bad-schema-configured.json',{'schema':'unified-configured-resource-v1','provider_config':pc})
        self.assertEqual(self.run_copy(config=cfg)['error'],'ValueError')

    def test_actual_child_deadline(self):
        result=self.run_copy('timeout')
        self.assertEqual(result['error'],'TimeoutError')
        self.assertGreaterEqual(result['elapsed'],4.8)
        self.assertLess(result['elapsed'],6.5)

    def test_rebuild_is_exact_and_refuses_changed_input(self):
        dest=self.root/'built'
        cmd=[sys.executable,'-B','-I',str(ROOT/'tools/build_resource_provider_v3.py'),'--pin-manifest',str(REVIEW/'PINS.json'),'--source-root',str(REVIEW/'verification'),'--output',str(dest)]
        subprocess.run(cmd,check=True)
        for f in ASSET.rglob('*'):
            if f.is_file(): self.assertEqual(f.read_bytes(), (dest/f.relative_to(ASSET)).read_bytes())
        manifest=json.loads((REVIEW/'PINS.json').read_text())
        for x in manifest['verification_copy']:
            if x['path'].endswith('/verification/tools/experiment_dag.py'): x['sha256']='0'*64
        fake=self.root/'fake.json'; fake.write_text(json.dumps(manifest)); cmd[cmd.index(str(REVIEW/'PINS.json'))]=str(fake); cmd[-1]=str(self.root/'invalid')
        self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.assertFalse((self.root/'invalid').exists())

if __name__ == '__main__': unittest.main()
