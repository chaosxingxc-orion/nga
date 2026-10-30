#!/usr/bin/env python3
"""Prepare an immutable E31 token-only run; launch is a separate command."""
import argparse,hashlib,json,shlex,shutil
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
SOURCES={'kev08':('kev','typed_kev08_preflight_20261030'),'kev4':('kev','typed_kev4_preflight_20261030'),'kev9':('kev','typed_kev9_preflight_20261030'),'openjev2':('openjev','typed_openjev2_preflight_20261030'),'openjev9':('openjev','typed_openjev9_preflight_20261030'),'nimble':('nimble','typed_nimble_preflight_20261030')}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def prepare(repo,key,revision=''):
 if revision and not (revision.startswith('v') and revision[1:].isdigit()):raise ValueError('Revision must be v followed by digits')
 suffix='_'+revision if revision else '';container_suffix='-'+revision if revision else ''
 family,prior=SOURCES[key];old=json.loads((ROOT/prior/'config.json').read_text());out=ROOT/('jeval_'+key+'_preflight_20261030'+suffix);out.mkdir();c={k:v for k,v in old.items() if k not in ['files','out','mode','data','scorer','preregistration','container']};c['code']=old.get('code',old.get('kev_code'));c.pop('kev_code',None)
 roles=['base','code','adapter' if family=='nimble' else 'checkpoint'];c.update(family=family,mode='token_only',out=str(out),container='nga-jeval-'+key+'-preflight'+container_suffix,dependency_roles=roles,data='/mnt/cephfs/xingchao/omni/datasets/jev/carlosxiang__JEVal/data/test.parquet',preregistration=str(out/'PREREGISTRATION.md'))
 for n in ['jeval_reference_preflight.py','test_jeval_reference_preflight.py','prepare_jeval_reference_preflight.py']:shutil.copy2(repo/'tools'/n,out/n)
 shutil.copy2(repo/'experiments/JEVAL-NATIVE-PREFLIGHT-2026-10-30.md',out/'PREREGISTRATION.md');q=lambda p:shlex.quote(str(p))
 (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'jeval_reference_preflight.py')+' --config '+q(out/'config.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
 (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\ndocker run -d --name '+c['container']+' --network none --cpus 2 -e TORCH_DEVICE_BACKEND_AUTOLOAD=0 -e TOKENIZERS_PARALLELISM=false -v /mnt/cephfs:/mnt/cephfs --entrypoint bash '+c['image']+' '+q(out/'run.sh')+'\n')
 (out/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I - '+q(out/'config.json')+''' <<'PYRESUME'
import json,subprocess,hashlib,shutil,time
from pathlib import Path
import sys
p=Path(sys.argv[1]);c=json.loads(p.read_text());o=Path(c['out']);r=json.loads((o/'LAUNCH_RECEIPT.json').read_text());d=json.loads(subprocess.check_output(['docker','inspect',c['container']]))[0]
assert d['Id']==r['container_id'] and d['Image']==r['image']==c['image'] and d['Config']['Cmd']==r['command'] and d['Config']['Entrypoint']==r['entrypoint'] and not d['HostConfig']['Devices']
assert hashlib.sha256(p.read_bytes()).hexdigest()==r['config_sha256'] and hashlib.sha256((o/'run.sh').read_bytes()).hexdigest()==r['wrapper_sha256']
assert d['State']['Status']=='exited' and d['State']['ExitCode']!=0
if (o/'COMPLETE.json').exists():assert json.loads((o/'COMPLETE.json').read_text())['rc']!=0
archive=o/('resume-before-'+str(time.time_ns()));archive.mkdir()
for n in ['COMPLETE.json','EXIT','STATUS.json']:
 if(o/n).exists():shutil.move(str(o/n),str(archive/n))
subprocess.check_call(['docker','start',d['Id']])
PYRESUME
''')
 paths=list(out.iterdir())+[Path(c['data'])]
 for role in roles:paths.extend(p for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
 c['files']={str(p.resolve()):sha(p) for p in paths};(out/'config.json').write_text(json.dumps(c,indent=2)+'\n');print(json.dumps({'prepared':str(out),'config_sha256':sha(out/'config.json'),'frozen':len(c['files'])}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--model',choices=list(SOURCES),required=True);p.add_argument('--revision',default='');a=p.parse_args();prepare(a.repo,a.model,a.revision)
