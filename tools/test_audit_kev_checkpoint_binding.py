import importlib.util
from pathlib import Path
import tempfile
import unittest

s=importlib.util.spec_from_file_location('binding',Path(__file__).with_name('audit_kev_checkpoint_binding.py'))
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class BindingTests(unittest.TestCase):
    def setUp(self):
        self.meta={'base':'Qwen/base','base_revision':'abc','temperature':2.3,'weights_dtype':'fp32'}
        self.config={'base_id':'Qwen/base','base_revision':'abc','runtime':{'torch':'fixture'}}
        self.env={'temperature':2.3,'runtime':{'torch':'fixture'},'model':{'dtype':'float32','attention':'eager','backend':'torch'}}
    def test_valid(self):
        self.assertEqual(m.verify_metadata(self.meta,self.config,self.env,'abc\n')['temperature'],2.3)
    def test_wrong_temperature(self):
        self.env['temperature']=2.4
        with self.assertRaisesRegex(ValueError,'temperature differs'):m.verify_metadata(self.meta,self.config,self.env,'abc')
    def test_wrong_base(self):
        self.meta['base_revision']='other'
        with self.assertRaisesRegex(ValueError,'revision'):m.verify_metadata(self.meta,self.config,self.env,'abc')
    def test_wrong_dtype(self):
        self.env['model']['dtype']='bfloat16'
        with self.assertRaisesRegex(ValueError,'protocol'):m.verify_metadata(self.meta,self.config,self.env,'abc')
    def test_head_hash_changed_or_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'head.pt';p.write_bytes(b'original');files={str(p):m.sha(p)}
            self.assertEqual(m.verify_frozen(p,files),files[str(p)])
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):m.verify_frozen(p,files)
            with self.assertRaisesRegex(ValueError,'omitted'):m.verify_frozen(p,{})
    def test_driver_override_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'driver.py';p.write_text("LoadOptions(dtype=torch.float32,attn='eager',merge=True)")
            self.assertFalse(m.verify_driver(p)['temperature_override'])
            p.write_text("LoadOptions(dtype=torch.float32,attn='eager',merge=True,temperature=1.)")
            with self.assertRaisesRegex(ValueError,'overrides'):m.verify_driver(p)
    def test_wrong_release_and_hash_prefix(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for n in ['head.pt','adapter_model.safetensors']:(p/n).write_bytes(n.encode())
            text=f"runs/release/kev-fixture.json adapter sha256 `{m.sha(p/'adapter_model.safetensors')[:8]}…`, `head.pt` sha256 `{m.sha(p/'head.pt')[:8]}…`"
            (p/'README.md').write_text(text);(p/'release.json').write_text(json.dumps({'release':'wrong','drop_ids':[]}))
            files={str(q):m.sha(q) for q in p.iterdir()};c={'release_spec':str(p/'release.json'),'drop_ids':[]}
            with self.assertRaisesRegex(ValueError,'Wrong release'):m.release_binding(p,c,files)
            (p/'head.pt').write_bytes(b'other')
            with self.assertRaisesRegex(ValueError,'weight prefix'):m.release_binding(p,c,files)

if __name__=='__main__':unittest.main()
