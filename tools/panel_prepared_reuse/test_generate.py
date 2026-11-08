import ast, copy, importlib.util, json, sys, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('generator',ROOT/'generate.py'); G=importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
source=ROOT/'test_fixtures/fixture.py'
spec=importlib.util.spec_from_file_location('fixture',source); F=importlib.util.module_from_spec(spec); spec.loader.exec_module(F)

class Generator(unittest.TestCase):
 def test_fresh_generation_prepare_and_bind(self):
  # Reuse the independently reviewed tiny fixture, but run the generated runtime.
  f=F.Prepared('test_reuse_and_projection'); f.setUp(); self.addCleanup(f.doCleanups); self.addCleanup(patch.stopall)
  t=f.root/'template'; (t/'code').mkdir(parents=True)
  for p in F.CODE.iterdir():
   if p.is_file(): (t/'code'/p.name).write_bytes(p.read_bytes())
  (t/'bind.py').write_text((ROOT/'bind.py').read_text())
  c=copy.deepcopy(f.config); oldcode=F.CODE
  # The fixture's modules already refer to this copied source directory.
  c['population']['count']=1073; c['population']['kinds']={'choice':1073,'yes_no':0,'score':0}
  # Synthetic modules execute real contract-generation wiring.
  module_src={
   'native':'import hashlib,json\ndef digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()\n',
   'loader':"LOADER={}\nENV={}\nIMAGE='sha256:'+'4'*64\n",
   'panel':'def rows(path): return [1]\n',
   'protocol':"import hashlib,json\ndef make_contract(items,**kw): return {'items':items,**kw}\ndef sha256_value(x): return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()\n"}
  for key,src in module_src.items():
   p=t/'code'/(key+'_fixture.py'); p.write_text(src); ref={'path':str(oldcode/p.name),'sha256':G.sha(p)}; c['modules'][key]=ref; c['files'][ref['path']]=ref['sha256']
  # Generator checks every old code file against template, including loader/consumer.
  for path,pin in list(c['files'].items()):
   if Path(path).parent==oldcode and not (t/'code'/Path(path).name).exists(): (t/'code'/Path(path).name).write_bytes(Path(path).read_bytes())
  cpu=f.root/'injected.json'; cpu.write_text(json.dumps(c)); dest=f.root/'generated'
  with patch.object(G,'ORIGINAL_RUNTIME',G.sha(t/'code/bev_native_dataset_panel_v1.py')), patch.object(G,'ORIGINAL_BINDER',G.sha(t/'bind.py')), patch.object(G,'sha',side_effect=lambda p: f.asset_pin if str(p)==f.asset_path else F.C.sha(p)):
   G.generate(t,cpu,G.sha(cpu),dest)
  cfg=json.loads((dest/'CPU-CONFIG.json').read_text()); self.assertEqual(cfg['modules']['runtime']['sha256'],G.sha(ROOT/'bev_native_dataset_panel_v1.py'))
  self.assertEqual(json.loads((dest/'cpu/CONTRACT.json').read_text())['runtime_protocol_sha256'],cfg['population']['protocol_binding_sha256'])
  spec=importlib.util.spec_from_file_location('generated_runtime',dest/'code/bev_native_dataset_panel_v1.py'); C=importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
  sha=C.sha; read=C.read; counter=[]
  with patch.object(C,'sha',side_effect=lambda p:f.asset_pin if str(p)==f.asset_path else sha(p)), patch.object(C,'read',side_effect=lambda p:f.asset if str(p)==f.asset_path else read(p)), patch.object(C,'validate_population',side_effect=lambda c:counter.append(1)):
   prep=dest/'CPU-PREPARE.json'; C.build(str(dest/'CPU-CONFIG.json'),C.sha(dest/'CPU-CONFIG.json'),str(prep),cpu_prepare=True); pin=C.sha(prep)
   claim=dest/'CLAIM.json'; claim.write_text('{}'); release=dest/'RELEASE.json'; release.write_text('{}')
   ref=lambda p:{'path':str(p),'sha256':C.sha(p)}
   alloc={'free':[{'chip':4,'generation':1,'release_evidence':str(release)}],'allocation':[],'pending_claims':[]}; Path(cfg['resources']['allocation']).write_text(json.dumps(alloc))
   R=types.SimpleNamespace(validate_doc=lambda d:None,live_chip_conflict=lambda *a:False); U=types.ModuleType('unified_resource_lease_v1'); U.predecessor=lambda *a:None; U.DockerQuery=lambda:None
   qspec=importlib.util.spec_from_file_location('resource_v3',dest/'code/resource_v3.py'); Q=importlib.util.module_from_spec(qspec); qspec.loader.exec_module(Q)
   tree=ast.parse((dest/'bind.py').read_text()); body=[]
   for node in tree.body:
    if isinstance(node,ast.Import) and any(x.name=='bev_native_config_panel_host' for x in node.names): break
    body.append(node)
   with patch.dict(sys.modules,{'bev_native_dataset_panel_v1':C,'resource_v3':Q,'unified_resource_lease_v1':U}), patch.object(sys,'argv',[str(dest/'bind.py'),'4',pin]), patch.object(Q,'module',return_value=R), patch('subprocess.run') as numeric, patch.object(Q,'guard',wraps=Q.guard) as guard:
    exec(compile(ast.Module(body=body,type_ignores=[]),str(dest/'bind.py'),'exec'),{'__name__':'__main__'})
    numeric.assert_called_once(); guard.assert_called_once()
   self.assertEqual(len(counter),1); plan=dest/'PLAN.json'; result=json.loads(plan.read_text()); plan.unlink()
   full=C.build(str(dest/'CONFIG.json'),C.sha(dest/'CONFIG.json'),str(plan)); self.assertEqual(len(counter),2); self.assertEqual(result,full)
   plan.unlink()
   with self.assertRaises(ValueError): C.build(str(dest/'CONFIG.json'),C.sha(dest/'CONFIG.json'),str(plan),prepared_plan=str(prep),prepared_pin='0'*64)
   self.assertFalse(plan.exists())
  print('generator path: prepare=1, prepared bind=1, full build=2; full outputs identical; substituted pin rejected')

if __name__=='__main__': unittest.main(verbosity=2)
