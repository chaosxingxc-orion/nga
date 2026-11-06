import importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import collector as C, integration as I, watcher
ROOT=Path(__file__).resolve().parents[1]
FIX=Path(os.environ.get('RC1_FIXTURE_ROOT',str(ROOT/'scratch/end-to-end')))
REF=ROOT/'comparison'
CONSUMER=REF/'consumer.py'

def consume(cfg,out):
 return subprocess.run([sys.executable,'-B','-P',str(CONSUMER),'--config',str(cfg),'--out',str(out)],capture_output=True,text=True)

class EndToEnd(unittest.TestCase):
 def test_success_and_wrong_order(self):
  cfg=FIX/'collected/consumer-config.json';r=consume(cfg,FIX/'result');self.assertEqual(r.returncode,2,r.stdout+r.stderr)
  result=C.read(FIX/'result/comparison.json');self.assertEqual((result['own_base_status'],result['reference_alignment_status'],result['status']),('complete','pending','partial'))
  with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as d:
   d=Path(d); config=C.read(cfg);packet=C.read(config['packet']['path']);key='decision-v7/test/clean';rows=C.read(packet['populations'][key]['path']);rows[0],rows[1]=rows[1],rows[0];path=d/'rows.json';C.save(path,rows);packet['populations'][key]=C.pin(path);packet['authorized_files'][str(path)]=C.sha(path)
   p=d/'packet.json';C.save(p,packet);config['packet']=C.pin(p);c=d/'config.json';C.save(c,config);r=consume(c,d/'out');self.assertEqual(r.returncode,2,r.stdout);bad=C.read(d/'out/comparison.json');self.assertNotEqual(bad['own_base_status'],'complete');self.assertTrue(all(x['status']=='invalid' and 'readout order differs' in x['reason'] for x in bad['roster'].values()))
 def test_altered_producer(self):
  cfg=C.read(FIX/'collected/consumer-config.json');packet=C.read(cfg['packet']['path'])
  with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as d:
   d=Path(d);p=d/'producer.py';p.write_bytes(Path(packet['producer']['path']).read_bytes()+b'\n# changed\n');packet['producer']=C.pin(p);packet['source_files'][str(p)]=C.sha(p);packet['authorized_files'][str(p)]=C.sha(p);q=d/'packet.json';C.save(q,packet);cfg['packet']=C.pin(q);c=d/'config.json';C.save(c,cfg);r=consume(c,d/'out');self.assertEqual(r.returncode,1,r.stdout);self.assertIn('wrong producer revision',C.read(d/'out/failure.json')['reason'])
 def test_model_and_release_evidence(self):
  cfg=C.read(FIX/'collector-config.json');name=C.ROLES[0]
  with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as d:
   p=Path(d)/'identity.json';ident=C.read(cfg['identities'][name]);ident['sha256']='0'*64;C.save(p,ident);cfg['identities'][name]=str(p);self.assertEqual(C.inspect(cfg)[0]['status'],'error')
   c=C.read(cfg['configs'][name]);out=Path(c['out']);r=Path(d)/'release.json';claim=Path(d)/'claim.json';launch=Path(d)/'launch.json';obs=Path(d)/'obs.json';C.save(claim,{'run':'r','chip':0});C.save(launch,{'id':'id'});C.save(obs,{'Id':'id','State':{'Status':'exited','ExitCode':0,'StartedAt':'a','FinishedAt':'b'}});C.save(r,{'container_id':'wrong','exit_code':0,'container_started_at':'a','container_finished_at':'b','run':'r','chip':0,'claim_sha256':C.sha(claim)});c['container']={'claim':str(claim),'release':str(r),'launch_receipt':str(launch),'run':'r','chip':0};cp=Path(d)/'config.json';C.save(cp,c);cfg['kind']='production';cfg['configs'][name]=str(cp);cfg['identities'][name]=C.read(FIX/'collector-config.json')['identities'][name];cfg['observations']={name:str(obs)}
   original=C.digest;original_config=C.read(C.read(FIX/'collector-config.json')['configs'][name])
   with patch.object(C,'digest',side_effect=lambda x: original(original_config) if x==c else original(x)):
    result=C.inspect(cfg)[0]
   self.assertEqual(result['status'],'error');self.assertIn('host receipt/container identity contradiction',result['error'])
 def test_capture_tamper(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'scratch') as d:
   p=Path(d);C.save(p/'CAPTURE.json',{'populations':{}});C.save(p/'COMPLETE.json',{'capture_sha256':'0'*64})
   with self.assertRaisesRegex(ValueError,'capture hash'):I.capture_populations({'export_dir':d})
if __name__=='__main__':unittest.main()
