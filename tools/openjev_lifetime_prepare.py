#!/usr/bin/env python3
"""Freeze E40 first-stage artifacts. No Docker, allocation, approvals or launch."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil

NAMES=['openjev_lifetime_protocol.py','openjev_lifetime_npu.py','openjev_lifetime_verify.py',
       'openjev_lifetime_prepare.py','openjev_lifetime_candidate.py','openjev_lifetime_launch.py',
       'prepare_openjev_path_trace.py',
       'e38_evidence.py','jeval_reference_queue.py','openjev_path_trace_run.py',
       'openjev_batch_diagnostic.py','verify_openjev_path_trace.py']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def prepare(source,e38_plan,native_source,prereg,out,container):
    if out.exists():raise ValueError('New generation required')
    old=load(e38_plan);c=load(old['source_config'])
    if c['base_id']!='Qwen/Qwen3.5-2B':raise ValueError('First E40 stage requires 2B')
    proto=module(source/'openjev_lifetime_protocol.py','e40_prepare_protocol')
    candidate=module(source/'openjev_lifetime_candidate.py','e40_prepare_candidate')
    raw=native_source.read_bytes();candidate.native_tree(raw)
    out.mkdir(parents=False)
    for n in NAMES:shutil.copy2(source/n,out/n)
    shutil.copy2(prereg,out/'PREREGISTRATION.md');shutil.copy2(native_source,out/'modeling_qwen3_5.py')
    wrapper=('#!/usr/bin/env bash\nset -uo pipefail\ncd /tmp\n'
        'pin=$(cat '+shlex.quote(str(out/'PLAN.sha256'))+')\n'
        'python3 -B -P '+shlex.quote(str(out/'openjev_lifetime_npu.py'))+' --plan '+shlex.quote(str(out/'plan.json'))+
        ' --plan-sha256 "$pin" >> '+shlex.quote(str(out/'run.log'))+' 2>&1\nrc=$?\nset -o noclobber\n'
        'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+shlex.quote(str(out/'EXIT'))+'\nexit "$rc"\n')
    (out/'run.sh').write_text(wrapper)
    spec=copy.deepcopy(load(old['container_spec']));spec['Cmd']=['bash',str(out/'run.sh')];spec['Labels']={'nga.e40.name':container}
    for d in spec['HostConfig']['Devices']:
        if d['PathOnHost'].startswith('/dev/davinci') and d['PathOnHost'][12:].isdigit():
            d['PathOnHost']=d['PathInContainer']='/dev/davinci1'
    if '/var/run/docker.sock:/var/run/docker.sock' not in spec['HostConfig']['Binds']:
        spec['HostConfig']['Binds'].append('/var/run/docker.sock:/var/run/docker.sock')
    (out/'NPU_SPEC.json').write_text(json.dumps(spec,indent=2)+'\n')
    names=[n.rsplit('.core:output',1)[0] for n in old['trace_contract']['order'] if n.endswith('.core:output')]
    p=dict(schema=proto.SCHEMA,image=proto.IMAGE,out=str(out),container=container,physical_chip=1,logical_device='npu:0',
        schedule=proto.schedule(),input=old['input'],source_config=old['source_config'],source_config_sha256=old['source_config_sha256'],
        numeric_contract=old['numeric_contract'],expected_core_names=names,native_source=str(out/'modeling_qwen3_5.py'),
        native_source_sha256=candidate.SOURCE_SHA256,candidate_sources={'original':candidate.SOURCE_SHA256,
          **{v:hashlib.sha256(candidate.generated_source(raw,v).encode()).hexdigest() for v in candidate.VARIANTS}},
        wrapper=str(out/'run.sh'),container_spec=str(out/'NPU_SPEC.json'),preregistration=str(out/'PREREGISTRATION.md'),
        e38_plan=str(e38_plan),e38_plan_sha256=sha(e38_plan),candidate_batch_admission=False,
        safety=dict(max_reserved_gib=48,min_free_gib=8,chips=1,on_error='stop_and_preserve_generation',larger_inputs_authorized=False),
        performance_scope='full forward including identical passive token guard; no internal instrumentation',
        resume_policy='verified fixed prefix, same Docker start generation only; unmatched intent fails closed',
        files={**old['files'],str(e38_plan):sha(e38_plan)})
    p['files'].update({str(x):sha(x) for x in out.iterdir() if x.is_file()})
    proto.validate_plan(p)
    (out/'plan.json').write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
    ph=sha(out/'plan.json');(out/'PLAN.sha256').write_text(ph+'\n')
    (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\n'+shlex.join(['python3','-B','-I',str(out/'openjev_lifetime_launch.py'),'--plan',str(out/'plan.json'),'--plan-sha256',ph])+'\n')
    (out/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\nbash '+shlex.quote(str(out/'LAUNCH_EXACT.sh'))+'\n')
    (out/'LAUNCH_REQUIREMENTS.md').write_text('No launch authorized. Exact plan SHA: '+ph+'\n\nRequire independent Astra review, parent review, actual physical host/occupancy and allocation checks, durable claim/launch receipt, retained fixed-name Docker, then exact wrapper. PLAN.sha256 is convenience only; trust comes from external exact-plan reviews. Same-start process resume only; Docker restart needs a new reviewed generation. Independent verifier must run detached with no devices after actual NPU exit.\n')
    return {'plan':str(out/'plan.json'),'sha256':ph,'launched':False,'resource_claimed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('source','e38-plan','native-source','prereg','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--container',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.source,a.e38_plan,a.native_source,a.prereg,a.out,a.container)))
