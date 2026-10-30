#!/usr/bin/env python3
"""Prepare E29 immutable CPU token preflights; no NPU device or model execution."""
import argparse,hashlib,json,shlex,shutil
from pathlib import Path
ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);a=ap.parse_args()
 for size,prior in [('2','openjev2_test_20261030_v3'),('9','openjev9_test_20261030')]:
  old=json.loads((ROOT/prior/'config.json').read_text());out=ROOT/('typed_openjev'+size+'_preflight_20261030');out.mkdir();name='nga-typed-openjev'+size+'-preflight'
  for n in ['typed_openjev_preflight.py','test_typed_openjev_preflight.py','typed_openjev_prepare.py']:shutil.copy2(a.repo/'tools'/n,out/n)
  shutil.copy2(a.repo/'experiments/TYPED-OPENJEV-REFERENCE-2026-10-30.md',out/'PREREGISTRATION.md')
  c={k:old[k] for k in ['code','base','checkpoint','base_id','base_revision','temperature','image']};c.update(mode='preflight_only',max_length=4096,container=name,out=str(out),data='/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/all/test-00000-of-00001.parquet',scorer='/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py',preregistration=str(out/'PREREGISTRATION.md'))
  q=lambda p:shlex.quote(str(p))
  (out/'run.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\npython3 -P '+q(out/'typed_openjev_preflight.py')+' --config '+q(out/'config.json')+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
  (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\ndocker run -d --name '+name+' --network none -e TORCH_DEVICE_BACKEND_AUTOLOAD=0 -v /mnt/cephfs:/mnt/cephfs --entrypoint bash '+c['image']+' '+q(out/'run.sh')+'\n')
  (out/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I - '+q(out/'config.json')+''' <<'PYRESUME'
import json,subprocess,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);c=json.loads(p.read_text());o=Path(c['out']);receipt=json.loads((o/'LAUNCH_RECEIPT.json').read_text());d=json.loads(subprocess.check_output(['docker','inspect',c['container']]))[0]
assert d['Id']==receipt['container_id'] and d['Image']==receipt['image']==c['image']
assert d['Config']['Cmd']==receipt['command'] and d['Config']['Entrypoint']==receipt['entrypoint'] and not d['HostConfig']['Devices']
assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['config_sha256']
assert d['State']['Status']=='exited' and d['State']['ExitCode']!=0
if (o/'COMPLETE.json').exists():assert json.loads((o/'COMPLETE.json').read_text())['rc']!=0
subprocess.check_call(['docker','start',d['Id']])
PYRESUME
''')
  files=list(out.iterdir())+[Path(c['data']),Path(c['scorer'])]
  for role in ['base','checkpoint','code']:files.extend(p for p in Path(c[role]).rglob('*') if p.is_file() and '__pycache__'not in p.parts and p.suffix!='.pyc')
  c['files']={str(p.resolve()):sha(p) for p in files};(out/'config.json').write_text(json.dumps(c,indent=2)+'\n');print(json.dumps({'out':str(out),'files':len(c['files']),'config_sha256':sha(out/'config.json')}),flush=True)
if __name__=='__main__':main()
