import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('E',Path(__file__).with_name('r3_training_evidence.py'))
E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.files={};self.code=self.root/'code';self.model=self.root/'model'
        self.train=self.put('train.jsonl','{}');self.put('model/weights','weights')
        codes={}
        for name in ['train_r3.py','build_kev_sft.py','kev_aug.py','r0_code/prompt.py']:
            p=self.put('code/'+name,'source '+name);codes[str(p)]=E.sha(p)
        aug=self.put('augmentation.json',{'status':'PASS','mismatches':[],'records':20,'comparisons':80,'seeds':[2,3],'epochs':[0,1],'inputs':{**codes,str(self.train):E.sha(self.train)}})
        digest=self.put('lora/results/digest.json',{'status':'PASS','pairs':186,'trainable_tensors':372,'trainable_parameters':10822656,'trainable_dtype':'float32','device':'cpu','frozen_non_lora':True,'frozen_embeddings_lm_head':True,'gradient_checkpointing':True})
        terminal=self.put('lora/results/EXIT.json',{'exit_code':0})
        lv=self.put('lora/VERIFICATION.json',{'image':'image','exit_code':0,'state':'exited','npu_devices':[],'model_mount_readonly':True,'digest_sha256':E.sha(digest),'terminal_sha256':E.sha(terminal),'code':codes,'model_hashes_after_run':{str(self.model/'weights'):E.sha(self.model/'weights')}})
        self.doc={'schema':'r3-training-evidence-pack-v1','scientific_acceptance':False,'test_read':False,'files':self.files,'augmentation_digest':str(aug),'lora_verification':str(lv),'byte_identical_local_snapshot_map':{},'training_code_sha256':E.sha(self.code/'train_r3.py')}
        self.bundle=self.root/'EVIDENCE.json';self.repin()

    def put(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value) if isinstance(value,dict) else value);self.files[str(p)]=E.sha(p);return p

    def repin(self):
        self.bundle.write_text(json.dumps(self.doc));self.pin=E.sha(self.bundle)

    def validate(self,**overrides):
        kwargs=dict(path=self.bundle,pin=self.pin,code=self.code,model=self.model,train=self.train,image='image');kwargs.update(overrides)
        return E.validate(**kwargs)

    def test_bound_pack_passes_and_wrong_pin_or_image_refused(self):
        self.assertIn(str(self.bundle),self.validate())
        with self.assertRaisesRegex(ValueError,'pin differs'):self.validate(pin='0'*64)
        with self.assertRaisesRegex(ValueError,'execution evidence'):self.validate(image='other')

    def test_changed_model_code_and_training_data_refused(self):
        for p in [self.model/'weights',self.code/'train_r3.py',self.train]:
            old=p.read_bytes();p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'dependency changed'):self.validate()
            p.write_bytes(old)
        self.put('model/extra','additional weights')
        with self.assertRaisesRegex(ValueError,'planned model'):self.validate()

    def test_incomplete_or_failed_evidence_refused_even_when_repinned(self):
        p=Path(self.doc['augmentation_digest']);d=json.loads(p.read_text());d['seeds']=[2];self.put(p.relative_to(self.root),d);self.repin()
        with self.assertRaisesRegex(ValueError,'augmentation'):self.validate()
        d['seeds']=[2,3];self.put(p.relative_to(self.root),d)
        self.files.pop(str(self.code/'kev_aug.py'));self.repin()
        with self.assertRaisesRegex(ValueError,'not bound'):self.validate()


if __name__=='__main__':unittest.main()
