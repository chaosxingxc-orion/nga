#!/usr/bin/env python3
"""Prepare E30 isolated CPU fixture; never launches or approves a plan."""
import argparse,hashlib,json,shlex,shutil
from pathlib import Path
IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--preregistration',type=Path,required=True);a=p.parse_args();root=a.out;root.mkdir();run=root/'inference';run.mkdir();out=root/'controller';out.mkdir();q=lambda p:shlex.quote(str(p))
 for n in ['typed_recovery_controller.py','typed_recovery_fixture.py','prepare_typed_recovery_fixture.py','test_typed_recovery_controller.py']:shutil.copy2(a.source/n,root/n)
 worker=root/'typed_recovery_fixture.py';controller=root/'typed_recovery_controller.py'
 wrapper=run/'run.sh';wrapper.write_text('#!/usr/bin/env bash\nset -uo pipefail\npython3 -P '+q(worker)+' --config '+q(run/'config.json')+' >> '+q(run/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(run/'EXIT')+'\nexit "$rc"\n')
 c={'out':str(run),'container':'nga-e30-recovery-worker','image':IMAGE,'mode':'inference','expected_count':24,'files':{str(p):sha(p) for p in [worker,wrapper]}};cp=run/'config.json';cp.write_text(json.dumps(c,indent=2)+'\n')
 files={str(p):sha(p) for p in [controller,worker,wrapper,cp]};plan={'schema':1,'out':str(out),'config':str(cp),'kind':'cpu_fixture','max_retries':2,'retry_exit_codes':[137,143],'verifier':str(worker),'audit_binds':['/mnt/cephfs:/mnt/cephfs'],'inference':{'Image':IMAGE,'Cmd':['bash',str(wrapper)],'Entrypoint':[],'WorkingDir':'/tmp','HostConfig':{'Devices':[],'Binds':['/mnt/cephfs:/mnt/cephfs'],'NetworkMode':'none'}},'files':files};pp=out/'plan.json'
 (root/'run-controller.sh').write_text('#!/usr/bin/env bash\nset -uo pipefail\npython3 -P '+q(controller)+' --plan '+q(pp)+' >> '+q(out/'run.log')+' 2>&1\nrc=$?\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+q(out/'EXIT')+'\nexit "$rc"\n')
 (root/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\ndocker run -d --name nga-e30-recovery-controller --network none -v /mnt/cephfs:/mnt/cephfs -v /var/run/docker.sock:/var/run/docker.sock --entrypoint bash '+IMAGE+' '+q(root/'run-controller.sh')+'\n')
 (root/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\npython3 -I - '+q(pp)+''' <<'PYRESUME'
import json,subprocess,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);plan=json.loads(p.read_text());out=Path(plan['out']);assert not(out/'COMPLETE.json').exists();receipt=json.loads((out/'CONTROLLER_LAUNCH_RECEIPT.json').read_text());info=json.loads(subprocess.check_output(['docker','inspect','nga-e30-recovery-controller']))[0];assert info['Id']==receipt['container_id'] and info['Image']==receipt['image'] and not info['HostConfig']['Devices'];assert info['Config']['Cmd']==receipt['command'] and info['Config']['Entrypoint']==receipt['entrypoint'];assert info['State']['Status']=='exited' and info['State']['ExitCode']!=0;assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['plan_sha256'];assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in plan['files'].items());subprocess.check_call(['docker','start',info['Id']])
PYRESUME
''')
 prereg=root/'PREREGISTRATION.md';shutil.copy2(a.preregistration,prereg)
 dependencies={'controller_wrapper':root/'run-controller.sh','launch':root/'LAUNCH_EXACT.sh','resume':root/'RESUME_EXACT.sh','preregistration':prereg}
 files.update({str(p):sha(p) for p in list(dependencies.values())+[root/'prepare_typed_recovery_fixture.py',root/'test_typed_recovery_controller.py']});plan['preparation_files']={k:str(v) for k,v in dependencies.items()};pp.write_text(json.dumps(plan,indent=2)+'\n')
 print(json.dumps({'plan':str(pp),'plan_sha256':sha(pp),'files':files}))
if __name__=='__main__':main()
