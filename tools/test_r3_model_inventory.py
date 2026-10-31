import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('inventory',Path(__file__).with_name('r3_model_inventory.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Inventory(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.weight=self.root/'model.safetensors';self.weight.write_bytes(b'weights')
        (self.root/'config.json').write_text('{}')
        self.inventory=M.capture(self.root);self.pin=M.identity(self.inventory)

    def test_full_inventory_matches(self):
        self.assertEqual(M.verify(self.root,self.inventory,self.pin)['files'],2)

    def test_same_length_weight_change_with_restored_mtime_is_detected(self):
        st=self.weight.stat();self.weight.write_bytes(b'changed');os.utime(self.weight,ns=(st.st_atime_ns,st.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'byte inventory'):M.verify(self.root,self.inventory,self.pin)

    def test_configuration_added_and_missing_files_refused(self):
        (self.root/'config.json').write_text('{"changed":true}')
        with self.assertRaises(ValueError):M.verify(self.root,self.inventory,self.pin)
        (self.root/'config.json').write_text('{}');(self.root/'extra.json').write_text('{}')
        with self.assertRaises(ValueError):M.verify(self.root,self.inventory,self.pin)
        (self.root/'extra.json').unlink();(self.root/'config.json').unlink()
        with self.assertRaises(ValueError):M.verify(self.root,self.inventory,self.pin)

    def test_symlink_and_modified_inventory_pin_refused(self):
        (self.root/'linked').symlink_to(self.weight)
        with self.assertRaisesRegex(ValueError,'symlink'):M.verify(self.root,self.inventory,self.pin)
        (self.root/'linked').unlink();self.inventory['files']['config.json']['bytes']=100
        with self.assertRaisesRegex(ValueError,'pin differs'):M.verify(self.root,self.inventory,self.pin)


if __name__=='__main__':unittest.main()
