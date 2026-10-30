#!/usr/bin/env python3
"""CPU checks for resource-guarded restart; no Docker or NPU mutation."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('restart',Path(__file__).with_name('resume_reference_kev.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.config={'physical_chip':3,'out':'/mnt/reference_inference/recovery','image':'sha256:test'}
        self.allocation={'allocation':[{'chip':3,'run':'reference_inference/recovery'}]}
        self.container={'Id':'test-id','Config':{'Cmd':['bash','/mnt/reference_inference/recovery/run.sh'],'Entrypoint':None},'State':{'Status':'exited'},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci3'}]},'Image':'sha256:test'}
        self.receipt={'container_id':'test-id','image':'sha256:test','command':self.container['Config']['Cmd'],'entrypoint':None}

    def check(self, marker=None, running=None):
        m.check_restart(self.config,self.allocation,self.container,running or [],marker,self.receipt)

    def test_valid_interrupted_and_failed(self):
        self.check();self.check({'rc':1})

    def test_success_refused(self):
        with self.assertRaisesRegex(ValueError,'Successful'):self.check({'rc':0})

    def test_reassigned_chip_refused(self):
        self.allocation['allocation'][0]['run']='other/run'
        with self.assertRaisesRegex(ValueError,'ownership'):self.check()

    def test_live_conflict_refused(self):
        with self.assertRaisesRegex(ValueError,'running container'):self.check(running=[self.container])

    def test_running_handle_refused(self):
        self.container['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'exited'):self.check()

    def test_wrong_image_or_mapping_refused(self):
        self.container['Image']='sha256:foreign'
        with self.assertRaisesRegex(ValueError,'image'):self.check()
        self.container['Image']='sha256:test';self.container['HostConfig']['Devices']=[]
        with self.assertRaisesRegex(ValueError,'physical chip'):self.check()


if __name__=='__main__':unittest.main()
