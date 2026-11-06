import importlib.util, json, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('fixture',HERE/'fixtures.py'); f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
class Compatibility(unittest.TestCase):
 def test_configured_chips_and_mismatch(self):
  resource=json.loads((HERE.parent/'matched_k0/resource.json').read_text())
  mapping={x['id']:x['chip'] for x in resource['jobs']}
  with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
   c, inspections=f.build(tmp)
   self.assertEqual({x['id']:x['chip'] for x in f.M.obj(c['k0_resource']['path'])['jobs']},mapping)
   result,code=f.M.assemble(f.M.Consumer(c,inspector=inspections.__getitem__,allow_fixture=True))
   self.assertEqual(code,0,result)
   path=Path(c['k0_root'])/'08b-k0'/'infer-LAUNCH.json'; launch=f.M.obj(path);launch['chip']=4;f.put(path,launch)
   result,code=f.M.assemble(f.M.Consumer(c,inspector=inspections.__getitem__,allow_fixture=True))
   self.assertEqual(code,1);self.assertEqual(result['status'],'REFUSED_CONTRADICTION')
if __name__=='__main__':unittest.main()
