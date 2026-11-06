import json,tempfile,unittest,sys
from pathlib import Path
import fixture_dev as F, materializer as P, collector as T
C=P.C
class Pipeline(unittest.TestCase):
 def test_end_to_end(self):
  with tempfile.TemporaryDirectory(prefix='materializer-fixture-',dir=str(P.A.H.ROOT)) as tmp:
   root=Path(tmp);saved=dict(sys.modules);config,inspections=F.build(root);T.ROOT=root/'train';jobs={};objects={}
   for lane in config['lanes']:
    ident=lane['lane'];size=lane['size'];seed=lane['seed'];model=next(x for x in config['models'] if x['id']==lane['baseline_id']);d=T.ROOT/ident;ad=Path(lane['new_adapter']);jobs[ident]={'model':model['model']['path']}
    for phase in ('smoke','train'):
     cfg={'owner':'rc1-functional-'+ident,'seed':seed,'model':{'id':'Qwen3.5-'+size+'-Base'},'recipe_id':'k1-base-'+size.lower()+'-3116-v2','adapter':'k1-family-train-v2','engineering_stop_after':2 if phase=='smoke' else 3114,'resume':None if phase=='smoke' else {'path':'/run/nga/output/result/ckpt/step_000002.pt','sha256':T.sha(d/'result/ckpt/step_000002.pt')}}
     F.put(d/(phase+'.json'),cfg);cid=ident+phase;F.put(d/(phase+'-LAUNCH.json'),{'phase':phase,'chip':2,'container_id':cid,'config_sha256':T.sha(d/(phase+'.json'))});F.put(d/(phase+'-EXIT.json'),{'phase':phase,'chip':2,'container_id':cid,'image':T.IMAGE,'exit_code':0});objects[cid]={'Id':cid,'Name':'/nga-rc1-'+ident+'-'+phase,'Image':T.IMAGE,'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci2'}]},'State':{'Status':'exited','ExitCode':0}}
   def collect():return {i:T.collect(T.ROOT,i,s,n,Path(jobs[i]['model']),objects.__getitem__) for i,s,n in T.JOBS}
   train=collect();self.assertTrue(all(x['status']=='training_verified' for x in train.values()),train)
   result,code=F.M.assemble(F.M.Consumer(config,inspector=inspections.__getitem__,allow_fixture=True));self.assertEqual(code,0,result)
   
   for name in ('common','split','decision','thresholds','metrics','core_r3','variants_r3','degenerate_r3','provenance_r3'):
    if name in saved:sys.modules[name]=saved[name]
    else:sys.modules.pop(name,None)
   status=P.examine(config,result,train,F.M);self.assertTrue(all(x['status']=='ready' for x in status),status)
   evidence={'config':root/'fixture-config.json','review':root/'existing-fixture-review.json','comparison':root/'comparison.json'};F.put(evidence['review'],{'fixture_only':True});F.put(evidence['comparison'],result)
   rows=P.roster(config,status,train,evidence,root/'identity-cache');rp=root/'roster.json';F.put(rp,rows);resources=root/'resources.json';F.put(resources,{i:{'chip':n%8,'dependencies':(['K0','QWEN27B_ENVFIX'] if n%8<4 else ['TRAIN_DEV'])} for n,i in enumerate(C.LANES+C.BASES)})
   g=P.A.assemble(str(rp),str(resources),str(root/'campaign'));self.assertEqual(len(g['members']),12)
   for m,node in g['members'].items():
    draft=C.read(node['draft']);review=Path(node['review']);F.put(review,{'schema':'rc1-trackk-review-v1','reviewed':True,'config_sha256':C.digest(draft),'fixture_only':True});draft['review']=P.pin(review);P.A.H.validate(draft,node['config']);C.validate(draft)
   self.assertFalse((root/'campaign/round/TEST-READS.log').exists())
   # Producer-format wrong seed/config and genuinely missing evidence.
   d=T.ROOT/'q2b-s2';path=d/'train.json';original=path.read_text();v=json.loads(original);v['seed']=3;F.put(path,v);self.assertEqual(collect()['q2b-s2']['status'],'contradiction');path.write_text(original)
   v=json.loads(original);v['recipe_id']='wrong';F.put(path,v);self.assertEqual(collect()['q2b-s2']['status'],'contradiction');path.write_text(original)
   done=d/'COMPLETE.json';data=done.read_text();done.unlink();self.assertEqual(collect()['q2b-s2']['status'],'pending');done.write_text(data)
   # Already bound evidence cannot change between roster and assembler.
   (root/'comparison.json').write_text('changed')
   with self.assertRaisesRegex(ValueError,'pin mismatch'):P.A.assemble(str(rp),str(resources),str(root/'bad-campaign'))
if __name__=='__main__':unittest.main(verbosity=2)
