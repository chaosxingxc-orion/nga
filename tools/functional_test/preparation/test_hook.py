import copy, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import supervisor as H

class Hook(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.core=self.root/'core.py';self.core.write_text('core')
  self.exp=self.root/'exporter.py';self.exp.write_text('exporter')
  self.c={'member':H.EXPORT_MEMBER,'round_dir':str(self.root/'campaign/round'),'host':{'entry':str(self.core),'cpu_entry':str(self.exp),'implementation_files':{str(self.exp):H.sha(self.exp)}},'source_files':{str(self.core):H.sha(self.core)},'population_export':{'producer':{'path':str(self.core),'sha256':H.sha(self.core)},'exporter':{'path':str(self.exp),'sha256':H.sha(self.exp)},'scope':H.EXPORT_SCOPE,'member':H.EXPORT_MEMBER,'directory':str(self.root/'campaign/population-export')}}
 def test_positive_default_and_pins(self):
  self.assertEqual(H.cpu_entry(self.c),str(self.exp))
  c=copy.deepcopy(self.c);del c['host']['cpu_entry'];del c['population_export'];self.assertEqual(H.cpu_entry(c),str(self.core))
  self.exp.write_text('changed')
  with self.assertRaisesRegex(RuntimeError,'pin mismatch'):H.cpu_entry(self.c)
 def test_wrong_member_scope_directory_and_producer(self):
  for change in ('member','scope','directory','producer'):
   c=copy.deepcopy(self.c)
   if change=='member':c['member']='q2b-s2';c['population_export']['member']='q2b-s2'
   if change=='scope':c['population_export']['scope']='wrong'
   if change=='directory':c['population_export']['directory']=str(self.root/'elsewhere')
   if change=='producer':c['population_export']['producer']={'path':str(self.exp),'sha256':H.sha(self.exp)}
   with self.subTest(change=change),self.assertRaises(RuntimeError):H.cpu_entry(c)
