import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('q_fixed',R/'queue.py');q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
P=q.P
class Fixed(unittest.TestCase):
 def test_ownership_parser_fail_closed(self):
  table='npu-smi 25\n| NPU     Chip              | Process id | Process name | Process memory(MB) | status |\n| 4 0 | 12345 | python | 100 | NA |\n'
  self.assertEqual(q.HP.listing(table,[4]),{4:[12345]})
  for bad in ('', 'npu-smi 25\n| NPU     Chip              | Process id\n| garbage |'):
   with self.assertRaises(ValueError):q.HP.listing(bad,[4])
  with self.assertRaises(ValueError):q.free(3)
 def test_dependency_positive_and_binding_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);lane='q4b-s2';train=root/lane;dev=root/'adapter/full-q4b-s2';d=train/'result/adapter';d.mkdir(parents=True);dev.mkdir(parents=True);(dev/'result').mkdir();a='a'*64;b='b'*64
   bind={'owner':'rc1-functional-'+lane};P.save(d/'BINDING.json',bind);P.save(d/'PUBLICATION.json',{'binding':bind});P.save(train/'train-LAUNCH.json',{'phase':'train','chip':4,'container_id':a,'config_sha256':q.TRAIN_CONFIG[lane]});P.save(train/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False});P.save(dev/'infer-LAUNCH.json',{'chip':4,'container_id':b});P.save(dev/'infer-EXIT.json',{'container_id':b,'exit_code':0,'container_exit_code':0});P.save(dev/'infer-BINDING.json',{'binding':bind,'publication_sha256':P.sha(d/'PUBLICATION.json')})
   model=next(x['model'] for x in q.C['models'] if x['id']=='4b-k0');P.save(dev/'infer-COMMAND.json',['--model',model['path'],'--adapter',str(d),'--phase','infer']);P.save(dev/'infer-LAUNCH.json',{'chip':4,'container_id':b,'command_sha256':P.sha(dev/'infer-COMMAND.json')});h={'version':1,'model':model['path'],'adapter':str(d),'out':'/run/output/result','limit':0,'inference_header':{'stages':'k_score','model':{'base_path':model['base_path'],'base_revision':model['base_revision']}}};P.save(dev/'result/INFERENCE-READY.json',h)
   def inspect(cid):return {'Id':cid,'Name':'/nga-rc1-'+lane+'-train' if cid==a else '/nga-rc1-cpu-full-'+lane+'-infer','HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci4'}]},'State':{'Status':'exited','ExitCode':0}}
   with patch.object(q,'ROOT',root),patch.object(q,'ADAPTER',root/'adapter'),patch.object(q,'inspect',side_effect=inspect):
    self.assertTrue(q.ready(lane,4));h['model']='wrong';P.save(dev/'result/INFERENCE-READY.json',h)
    with self.assertRaises(ValueError):q.ready(lane,4)
 def test_artifact_hashes_and_tamper(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);mid='08b-k0';m=next(x for x in q.C['models'] if x['id']==mid);ident={**m['model'],'files':m['weight_shard_pins']};desc={'record_grade':True,'mode':'rightpad','token_budget':16384};header={'model':m['model'],'arm':'K0','stages':'k_score','device':'npu','dtype':'float32','limit':0,'limit_groups':0,'partitions':['dev','calibration'],'primary_input_mode':'full','scorer':desc,'dry_run_warnings':[]};stores={}
   for g,n in zip(P.GROUPS,P.COUNTS):
    suite,part,kind=g.split('/');path=out/'trackk'/(suite+'__'+part)/(kind+'.jsonl');path.parent.mkdir(parents=True);path.write_text('fixture');Path(str(path)+'.receipt.json').write_text('fixture receipt');stores[g]={'rows':n,'store_sha256':P.sha(path),'receipt_sha256':P.sha(str(path)+'.receipt.json')}
   h={'version':1,'model_id':mid,'out':str(out),'identity':ident,'groups':P.GROUPS,'config_sha256':P.sha(R/'config.json'),'stores':stores,'descriptor':desc,'inference_header':header};P.save(out/'INFERENCE-READY.json',h);ev=q.artifact_evidence(mid,out,'infer');report={'schema':'matched-k0-clean-dev-v1','model_id':mid,'identity':ident,'inference_receipt_sha256':ev['inference_sha256'],'stores':stores,'inference_header':header};P.save(out/'clean-report.json',report);self.assertIn('report_sha256',q.artifact_evidence(mid,out,'score'))
   (out/'clean-report.json').unlink()
   with self.assertRaises(FileNotFoundError):q.artifact_evidence(mid,out,'score')
   path.write_text('tamper')
   with self.assertRaises(ValueError):q.artifact_evidence(mid,out,'infer')
 def test_review_pin(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(q,'OUT',Path(tmp)):
   self.assertFalse(q.reviewed());review=Path(tmp)/'review.json';review.write_text('independent review');pin={'verdict':'pass','review_artifact':str(review),'review_artifact_sha256':P.sha(review)};pin.update({n.replace('.','_')+'_sha256':P.sha(R/n) for n in ('queue.py','producer.py','config.json','compare_dev.py','host_ownership_probe.py')});P.save(Path(tmp)/'REVIEW-APPROVED.json',pin);self.assertTrue(q.reviewed());pin['producer_py_sha256']='bad';P.save(Path(tmp)/'REVIEW-APPROVED.json',pin);self.assertFalse(q.reviewed())
if __name__=='__main__':unittest.main()
