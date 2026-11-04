"""Population registration gates and deterministic threaded consumption checks."""
import copy,unittest
from tools.test_bev_native_config_panel import PanelConfig
from tools import bev_native_dataset_panel_v1 as D

class DatasetPopulation(unittest.TestCase):
 def setUp(self):
  fixture=PanelConfig();fixture.setUp();self.addCleanup(fixture.doCleanups);self.c=copy.deepcopy(fixture.c);self.c['schema']='native-dataset-panel-config-v1';self.c['population'].update(count=2386,source_rows=2386,semantic_duplicates=0,kinds=dict(choice=1180,yes_no=804,score=402))
 def test_registered_nondefault_population(self):D.config_validate(self.c)
 def test_count_partition_and_integer_alias_rejected(self):
  for key,value in [('count',0),('count',2385),('source_rows',False),('semantic_duplicates',2386),('semantic_duplicates',True),('kinds',{'choice':1180,'yes_no':804,'score':401}),('kinds',{'choice':1180,'yes_no':804,'score':402,'unknown':0})]:
   c=copy.deepcopy(self.c);c['population'][key]=value
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):D.config_validate(c)
 def test_default_runtime_cannot_silently_admit_dataset(self):
  from tools import bev_native_config_panel as C
  c=copy.deepcopy(self.c);c['schema']='native-panel-config-v2'
  with self.assertRaises(ValueError):C.config_validate(c)
 def test_gold_mount_is_not_inherited_with_source_ancestor(self):
  d=dict(model=self.c['model']['path'],population=self.c['population'],files=self.c['files'],out=self.c['output']);mounts=D.mounts(d,'/tmp/test-plan.json')
  for kind in ('items','gold','source','contract'):self.assertNotIn(d['population'][kind]['path'],[x['source'] for x in mounts])
if __name__=='__main__':unittest.main()

class PhysicalResource(unittest.TestCase):
 def test_exact_generation_and_physical_exit(self):
  import json, tempfile,types
  from pathlib import Path
  from tools import bev_native_dataset_resource_v1 as R
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   def save(name,obj):
    p=root/name;p.write_text(json.dumps(obj));return dict(path=str(p),sha256=R.sha(p))
   claim=save('CLAIM.json',dict(schema='r3-resource-claim-v1',run='old',chip=2,allocation='/allocation'))
   free=dict(chip=2,previous_run='old',release_evidence=str(root/'RELEASE.json'))
   release=save('RELEASE.json',dict(schema='r3-resource-release-v1',run='old',chip=2,claim_sha256=claim['sha256'],allocation_after={'free':[free]},scientific_acceptance=False,exit_code=1,container='old-a1',container_id='id',container_started_at='s',container_finished_at='f'))
   priority=save('priority.json',{'selection':'matrix completion'})
   q=dict(schema='native-dataset-physical-free-v1',chip=2,run='new',allocation='/allocation',free_entry=free,pending_claims=[],predecessor={'claim':claim,'release':release},selection='independent public test',priority_refs=[priority],scientific_acceptance=False,test_read=False)
   queue=save('queue.json',q);d=dict(queue=queue,files={x['path']:x['sha256'] for x in (queue,claim,release,priority)},schema='native-dataset-panel-execution-v1',scope='public_fixed_base_test',test_read=True,scientific_acceptance=False,candidate_test_authority=False,chip=2,run='new',allocation='/allocation')
   actual=dict(Id='id',State={'Running':False,'Status':'exited','ExitCode':1,'StartedAt':'s','FinishedAt':'f'},HostConfig={'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci2','PathInContainer':'/dev/davinci2'}]},RestartCount=0)
   backend=types.SimpleNamespace(validate_doc=lambda x:None,docker_inspect=lambda n:actual,live_chip_conflict=lambda *a:False)
   allocation=dict(free=[free],allocation=[],pending_claims=[])
   self.assertTrue(R.guard(d,backend,allocation)['physical_release_verified'])
   for key,value in [('Running',True),('ExitCode',False),('FinishedAt','other')]:
    old=actual['State'][key];actual['State'][key]=value
    with self.subTest(key=key),self.assertRaises(ValueError):R.guard(d,backend,allocation)
    actual['State'][key]=old
   allocation['pending_claims']=[{'new':'priority'}]
   with self.assertRaises(ValueError):R.guard(d,backend,allocation)
