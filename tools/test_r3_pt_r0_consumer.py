"""Synthetic evidence-chain failures; no real task data, devices or model access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

s=importlib.util.spec_from_file_location('consumer',Path(__file__).with_name('r3_pt_r0_consumer.py'))
C=importlib.util.module_from_spec(s);s.loader.exec_module(C)


class Consumer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'run';self.run.mkdir();(self.run/'results').mkdir()
    def write(self,p,value):
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
    def released(self):
        e={'schema':'r3-engineering-posttrain-execution-v1','out':str(self.run),'test_read':False,'scientific_acceptance':False,
           'launcher':'/frozen/launcher.py','chip':2,'run':'r3_runs/run'}
        self.write(self.run/'execution.json',e);end={'exit_code':0,'attempt':1}
        self.write(self.run/'ENGINEERING_EVAL_EXIT.json',end);a=self.run/'attempts/1'
        self.write(a/'EXIT.json',end);self.write(a/'LAUNCH_RECEIPT.json',{'id':'container'})
        self.write(a/'RELEASE.json',{'exit_code':0,'container_id':'container','chip':2,'run':e['run'],'scientific_acceptance':False})
        cmd=['/usr/bin/python3.12','-P',e['launcher'],'supervise','--plan',str(self.run/'execution.json'),'--sha256',C.sha(self.run/'execution.json'),'--attempt','1']
        self.write(self.run/'SUPERVISOR_RECEIPT.json',{'command':cmd,'pid':123})
        return e
    def test_release_requires_every_identity_and_latest_attempt(self):
        e=self.released();self.assertEqual(len(C.release(self.run,e)),5)
        path=self.run/'attempts/1/RELEASE.json';proof=C.load(path)
        for field,value in [('container_id','other'),('exit_code',1),('chip',3),('run','foreign'),('scientific_acceptance',True)]:
            bad=dict(proof);bad[field]=value;self.write(path,bad)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'release|released'):C.release(self.run,e)
        self.write(path,proof);receipt=C.load(self.run/'SUPERVISOR_RECEIPT.json');receipt['command'][-1]='2'
        self.write(self.run/'SUPERVISOR_RECEIPT.json',receipt)
        with self.assertRaisesRegex(ValueError,'latest supervisor'):C.release(self.run,e)
    def test_marker_alone_and_failed_producer_cannot_publish(self):
        e=self.released();(self.run/'attempts/1/RELEASE.json').unlink()
        with self.assertRaises(FileNotFoundError):C.release(self.run,e)
        self.write(self.run/'ENGINEERING_EVAL_EXIT.json',{'exit_code':1,'attempt':1})
        with self.assertRaisesRegex(ValueError,'successful'):C.release(self.run,e)
    def test_frozen_code_exact_inventory_and_symlink_refused(self):
        root=self.root/'code';root.mkdir();f=root/'a.py';f.write_text('x=1')
        mounts=[{'source':str(root),'destination':'/frozen/r3_code','readonly':True}];files={str(f):C.sha(f)}
        self.assertEqual(C.code_map(mounts,files),{'r3_code/a.py':C.sha(f)})
        f.write_text('x=2')
        with self.assertRaisesRegex(ValueError,'unbound'):C.code_map(mounts,files)
        f.unlink();f.symlink_to(self.run)
        with self.assertRaisesRegex(ValueError,'unsafe'):C.code_map(mounts,files)
    def test_bad_config_and_unpinned_tool_refused(self):
        cfg=self.root/'config.json';self.write(cfg,{'schema':'wrong'})
        with self.assertRaisesRegex(ValueError,'schema'):C.config(cfg,C.sha(cfg))
        with self.assertRaisesRegex(ValueError,'pin'):C.config(cfg,'0'*64)
        d={'schema':'r3-pt-r0-consumer-config-v1','tools':{}}
        self.write(cfg,d)
        with self.assertRaisesRegex(ValueError,'inventory'):C.config(cfg,C.sha(cfg))
    def test_failed_reconstruction_leaves_no_output_and_reserved_output_refused(self):
        output=self.run/'results/PT_R0_REPORT.json'
        with patch.object(C,'config',return_value=({},{})),patch.object(C,'evaluate',side_effect=ValueError('R0 source mismatch')):
            with self.assertRaisesRegex(ValueError,'R0 source mismatch'):C.execute(self.run,'pin','/config','pin',output)
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(ValueError,'dedicated'):C.execute(self.run,'pin','/config','pin',self.run/'FINAL.json')
    def test_atomic_result_only_after_rechecks_no_overwrite(self):
        output=self.run/'results/PT_R0_REPORT.json';value={'scientific_acceptance':False,'consumer_verification':{}}
        with patch.object(C,'config',side_effect=[({},{}),ValueError('config changed')]),patch.object(C,'evaluate',return_value=value):
            with self.assertRaisesRegex(ValueError,'changed'):C.execute(self.run,'pin','/config','pin',output)
        self.assertFalse(output.exists())
        with patch.object(C,'config',return_value=({},{})),patch.object(C,'evaluate',return_value=value):
            result=C.execute(self.run,'pin','/config','pin',output)
        self.assertFalse(result['scientific_acceptance']);self.assertEqual(output.stat().st_mode&0o777,0o644)
        self.assertEqual(json.loads(output.read_text())['consumer_verification']['run'],str(self.run))
        original=output.read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'):C.publish(output,{'changed':True})
        self.assertEqual(output.read_bytes(),original)
    def test_pt_execution_queue_pin_refused_before_loading_launcher(self):
        e={'out':str(self.run)};self.write(self.run/'execution.json',e);self.write(self.run/'QUEUE_EXECUTION_PIN.json',{'sha256':'wrong'})
        with patch.object(C,'module') as loader:
            with self.assertRaisesRegex(ValueError,'queue pin'):C.pt_execution(self.run,C.sha(self.run/'execution.json'),{})
            loader.assert_not_called()

if __name__=='__main__':unittest.main()
