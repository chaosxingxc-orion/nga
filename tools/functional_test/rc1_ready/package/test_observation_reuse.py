"""CPU regression: accepted observation reuse and tamper rejection."""
import hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
from unittest.mock import patch
package=Path(__file__).resolve().parent
sys.path.insert(0,str(package))
spec=importlib.util.spec_from_file_location('integration_tested',package/'integration.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
import collector as B
class K:
 @staticmethod
 def verify_observation(spec,obs,id):
  assert spec=='spec' and obs['Id']==id
with tempfile.TemporaryDirectory() as t:
 root=Path(t);cfg={'configs':{}};auth={}
 for name in B.ROLES:
  launch=root/(name+'-launch.json');B.save(launch,{'id':name});c=root/(name+'-cfg.json');B.save(c,{'container':{'spec':'spec','launch_receipt':str(launch)}});cfg['configs'][name]=str(c)
  p=root/'observations'/(name+'.json');B.save(p,{'Id':name,'State':{'Status':'exited','ExitCode':0},'Mounts':[2,1]});auth[str(p.resolve())]=B.sha(p)
 review=root/'review.json';B.save(review,{'accepted':True,'authorized_files':auth});cfg['completed_access_review']=str(review)
 with patch.object(mod.subprocess,'check_output',side_effect=AssertionError('docker should not run')):
  assert len(mod.observations(cfg,root,K))==12
  assert all(B.sha(p)==h for p,h in auth.items())
  p=root/'observations'/(B.ROLES[0]+'.json');B.save(p,{'tampered':True})
  try:mod.observations(cfg,root,K);raise AssertionError('tampered pin accepted')
  except ValueError as e:assert 'reviewed observation missing or differs' in str(e)
  p.unlink()
  try:mod.observations(cfg,root,K);raise AssertionError('missing pin accepted')
  except ValueError as e:assert 'reviewed observation missing or differs' in str(e)
 del cfg['completed_access_review']
 def inspect(cmd,text):return json.dumps([{'Id':cmd[-1],'State':{'Status':'exited','ExitCode':0},'Mounts':[1,2]}])
 with patch.object(mod.subprocess,'check_output',side_effect=inspect) as docker:
  assert len(mod.observations(cfg,root,K))==12 and docker.call_count==12
print('PASS: 12 reviewed pins reused without docker; tampered/missing fail closed; unreviewed capture uses docker')
