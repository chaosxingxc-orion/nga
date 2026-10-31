import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('post',Path(__file__).with_name('r3_posttrain_eval_plan.py'))
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)


class PostTrainTests(unittest.TestCase):
    def test_wait_failure_and_probe_cannot_become_full_eval(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td);out=t/'evaluation'
            self.assertEqual(P.prepare(t,t,out)['status'],'waiting_training')
            (t/'TRAIN_EXIT.json').write_text('{"exit_code":1}')
            self.assertEqual(P.prepare(t,t,out)['status'],'training_failed')
            (t/'TRAIN_EXIT.json').write_text('{"exit_code":0}')
            (t/'plan.json').write_text('{"stop_after":100}')
            (t/'manifest.json').write_text('{"summary":{"final_step":100}}')
            self.assertEqual(P.prepare(t,t,out)['status'],'not_complete_training')
            self.assertFalse(out.exists())

    def test_completed_artifacts_bound_and_changed_base_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);t=root/'train';c=root/'closure';t.mkdir();c.mkdir()
            model=root/'base';model.mkdir();w=model/'model.safetensors';w.write_bytes(b'fixture')
            adapter=t/'adapter';adapter.mkdir()
            for name in ('adapter_config.json','adapter_model.safetensors'):(adapter/name).write_bytes(b'fixture')
            (t/'TRAIN_EXIT.json').write_text('{"exit_code":0}')
            (t/'manifest.json').write_text('{"summary":{"final_step":3116}}')
            (t/'plan.json').write_text(json.dumps({'model':str(model),'files':{str(w):P.sha(w)},'arm':'k2','image_sha256':'fixture'}))
            command=['python3','--arm','K1','--adapter','<COMPLETED_ADAPTER>']
            (c/'manifest.json').write_text(json.dumps({'data':{},'code':{},'mounts':[],'command_template':command}))
            out=root/'out';result=P.prepare(t,c,out);self.assertEqual(result['status'],'prepared')
            plan=json.loads((out/'plan.json').read_text())
            self.assertIn('K2',plan['command']);self.assertFalse(plan['scientific_acceptance'])
            self.assertEqual(plan['files'][str(w)],P.sha(w))
            w.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):P.prepare(t,c,root/'out2')


if __name__=='__main__':unittest.main()
