#!/usr/bin/env python3
"""Prepare E24 frozen files on 175; never launch or claim a chip."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import socket

ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
FILES=['openjev_reference_eval.py','verify_reference_openjev.py','openjev_original_protocol.py',
       'openjev_supplement_eval.py','verify_openjev_supplement.py','join_openjev_original_test.py',
       'openjev_reference_finish.py','openjev_supplement_queue.py','test_openjev_original_test.py',
       'prepare_openjev_supplement.py']


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def shell(path,text):
    path.write_text('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n'+text)
    path.chmod(0o755)


def prepare(source,prereg):
    if socket.gethostname()!='k8s-node1':raise ValueError('Prepare only on authorized 175')
    queue=ROOT/'openjev_original_test_queue_20261030';queue.mkdir()
    for name in FILES:shutil.copy2(source/name,queue/name)
    shutil.copy2(prereg,queue/'PREREGISTRATION.md')
    restore=ROOT/'openjev_original_restore_20261030';entries=[]
    for size,parent_name in [('2','openjev2_test_20261030_v3'),('9','openjev9_test_20261030')]:
        parent=ROOT/parent_name;parent_path=parent/'config.json';old=json.loads(parent_path.read_text())
        run=ROOT/('openjev'+size+'_original_test_supplement_20261030');run.mkdir()
        join=ROOT/('openjev'+size+'_original_test_join_20261030');join.mkdir()
        for name in FILES:shutil.copy2(source/name,run/name)
        shutil.copy2(prereg,run/'PREREGISTRATION.md')
        shutil.copy2(parent/'launch.sh',run/'launch.sh')
        config=dict(old);config.update(out=str(run),container='nga-openjev'+size+'-original-test-supplement',
            data=str(restore/'test-missing-wiki.jsonl'),original_data=str(restore/'release-v2/test.jsonl'),
            restoration_report=str(restore/'report.json'),parent_config=str(parent_path),
            parent_config_sha256=sha(parent_path),preregistration=str(run/'PREREGISTRATION.md'),
            expected_rows=176,hard_count=51,scope='176-row original-test Wikispeedia supplement; not full test')
        q=lambda x:shlex.quote(str(x))
        cfg=q(run/'config.json');driver=q(run/'openjev_supplement_eval.py')
        shell(run/'preflight.sh',f'''python3 -P {driver} --config {cfg} --mode preflight >> {q(run/'preflight.log')} 2>&1
rc=$?
printf 'rc=%s utc=%s\\n' "$rc" "$(date -u +%FT%TZ)" > {q(run/'preflight-EXIT')}
exit "$rc"
''')
        shell(run/'evaluate.sh',f'''if [[ ! -f {q(run/'preflight-COMPLETE.json')} ]]; then
  bash {q(run/'preflight.sh')}
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    printf 'rc=%s utc=%s\\n' "$rc" "$(date -u +%FT%TZ)" > {q(run/'evaluate-EXIT')}
    exit "$rc"
  fi
fi
python3 -P {driver} --config {cfg} --mode evaluate >> {q(run/'evaluate.log')} 2>&1
rc=$?
printf 'rc=%s utc=%s\\n' "$rc" "$(date -u +%FT%TZ)" > {q(run/'evaluate-EXIT')}
exit "$rc"
''')
        shell(run/'PREFLIGHT_EXACT.sh',f'''# Preflight runs inside the retained supplementary container before inference.
# Independent preflight invocation would require its own retained container and registration.
echo 'Use the guarded queue launch; preflight is its first stage.' >&2
exit 2
''')
        shell(run/'LAUNCH_EXACT.sh',f'''# Launch through the frozen dependency controller; it owns chip transfer.
bash {q(queue/'LAUNCH_EXACT.sh')}
''')
        shell(run/'RESUME_EXACT.sh',f'''# Run on 175 host; guarded_resume validates receipts, allocation and actual Docker state.
python3 -I {q(run/'openjev_reference_eval.py')} --config {cfg} --mode resume
''')
        execution=[queue/name for name in FILES]+[run/name for name in FILES]+[run/name for name in ['launch.sh','preflight.sh','evaluate.sh','PREFLIGHT_EXACT.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh']]
        config['execution_files']=[str(p) for p in execution]
        files=set(execution+[Path(config[k]) for k in ('data','export_manifest','preregistration','original_data','restoration_report','parent_config')])
        for key in ('code','base','checkpoint'):
            files.update(p for p in Path(config[key]).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
        config['files']={str(p.resolve()):sha(p) for p in sorted(files)};write(run/'config.json',config)
        joinplan={'out':str(join),'public_config':str(parent_path),'supplement_config':str(run/'config.json'),
                  'original_data':config['original_data'],'restoration_report':config['restoration_report'],
                  'preregistration':str(queue/'PREREGISTRATION.md')}
        joinfiles=[queue/name for name in FILES]+[Path(joinplan[k]) for k in ('public_config','supplement_config','original_data','restoration_report','preregistration')]
        joinplan['files']={str(p.resolve()):sha(p) for p in joinfiles};write(join/'plan.json',joinplan)
        shell(join/'RELAUNCH_EXACT.sh',f'''python3 -P {q(queue/'join_openjev_original_test.py')} --plan {q(join/'plan.json')}
''')
        entries.append({'name':size+'B','public_config':str(parent_path),'supplement_config':str(run/'config.json'),'join_plan':str(join/'plan.json')})
    shell(queue/'run.sh',f'''python3 -P {shlex.quote(str(queue/'openjev_supplement_queue.py'))} --plan {shlex.quote(str(queue/'plan.json'))} >> {shlex.quote(str(queue/'run.log'))} 2>&1
rc=$?
printf 'rc=%s utc=%s\\n' "$rc" "$(date -u +%FT%TZ)" > {shlex.quote(str(queue/'EXIT'))}
exit "$rc"
''')
    image=json.loads(Path(entries[0]['public_config']).read_text())['image']
    shell(queue/'LAUNCH_EXACT.sh',f'''set -e
# Fixed name prevents duplicate controllers; retained container keeps exit evidence.
docker run -d --name nga-openjev-original-test-queue --network host \\
  -v /mnt/cephfs:/mnt/cephfs -v /var/run/docker.sock:/var/run/docker.sock \\
  --entrypoint /bin/bash {shlex.quote(image)} {shlex.quote(str(queue/'run.sh'))}
''')
    paths=[queue/name for name in FILES]+[queue/'PREREGISTRATION.md',queue/'run.sh',queue/'LAUNCH_EXACT.sh']
    for entry in entries:paths.extend(Path(entry[key]) for key in ('public_config','supplement_config','join_plan'))
    plan={'out':str(queue),'entries':entries,'files':{str(p.resolve()):sha(p) for p in paths}}
    write(queue/'plan.json',plan)
    return {'queue':str(queue),'entries':entries,'status':'PREPARED_NOT_LAUNCHED'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--preregistration',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.source,args.preregistration),indent=2))
