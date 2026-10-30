#!/usr/bin/env python3
"""Read-only E29 preflight artifact/coverage audit, not independent re-tokenization."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def stamp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);a=ap.parse_args();p=a.run;c=json.loads((p/'config.json').read_text());ch=sha(p/'config.json');needed={str(Path(c[k]).resolve()) for k in ['data','scorer','preregistration']}
 needed.update(str((p/n).resolve()) for n in ['typed_openjev_preflight.py','test_typed_openjev_preflight.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 for role in ['base','checkpoint','code']:needed.update(str(x.resolve()) for x in Path(c[role]).rglob('*') if x.is_file() and '__pycache__'not in x.parts and x.suffix!='.pyc')
 require(needed<=set(c['files']),'Omitted dependencies')
 for path,h in c['files'].items():require(sha(path)==h,'Changed dependency: '+path)
 t=json.loads((p/'COMPLETE.json').read_text());r=json.loads((p/'PREFLIGHT.json').read_text());receipt=json.loads((p/'LAUNCH_RECEIPT.json').read_text());d=json.loads(subprocess.check_output(['docker','inspect',c['container']]))[0]
 require(t['rc']==0 and t['config_sha256']==ch==r['config_sha256']==receipt['config_sha256'],'Config terminal binding')
 require(t['outputs']['PREFLIGHT.json']==sha(p/'PREFLIGHT.json'),'Output hash')
 require(d['Id']==receipt['container_id'] and d['Image']==receipt['image']==c['image'] and d['Config']['Cmd']==receipt['command'] and d['Config']['Entrypoint']==receipt['entrypoint'] and not d['HostConfig']['Devices'],'Container identity or device')
 require(d['State']['Status']=='exited' and d['State']['ExitCode']==0,'Container not successful')
 require(re.fullmatch(r'rc=0 utc=\S+\n?',(p/'EXIT').read_text()) and (p/'EXIT').stat().st_mtime_ns>=(p/'COMPLETE.json').stat().st_mtime_ns>=(p/'PREFLIGHT.json').stat().st_mtime_ns,'Wrapper chronology')
 require(r['rows']==len(r['items'])==400 and r['questions']==2000 and r['overlength']==0,'Population')
 require(sorted(x.name for x in (p/'records').glob('*.json'))==[f'{i:06d}.json' for i in range(400)],'Item coverage')
 require(len({v['id'] for v in r['items']})==400,'Duplicate IDs');lengths=[]
 for i,item in enumerate(r['items']):
  env=json.loads((p/'records'/f'{i:06d}.json').read_text());require(env['payload']==item and env['sha256']==stamp(item),'Item receipt mismatch');require(item['index']==i and item['config_sha256']==ch and len(item['fields'])==5,'Item binding')
  for f in item['fields']:
   require(len(f['lengths'])==len(f['token_sha256'])==(1 if f['kind']=='noul' else len(f['candidate_keys'])),'Prompt count')
   require(all(type(n)is int and 0<n<=4096 for n in f['lengths']),'Length bound');lengths+=f['lengths']
 require(len(lengths)==r['candidate_prompts'] and max(lengths)==r['max_tokens'],'Summary mismatch')
 out={'status':'VERIFIED_PREFLIGHT_ARTIFACTS','config_sha256':ch,'report_sha256':sha(p/'PREFLIGHT.json'),'frozen_files':len(c['files']),'required_files':len(needed),'rows':400,'questions':2000,'candidate_prompts':len(lengths),'max_tokens':max(lengths),'container_id':d['Id'],'scope':'Frozen dependency, complete receipt coverage, lengths and terminal/container binding; does not independently re-tokenize or prove model quality.'}
 require(not(p/'PRECHECK_AUDIT.json').exists(),'Existing audit preserved');(p/'PRECHECK_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
if __name__=='__main__':main()
