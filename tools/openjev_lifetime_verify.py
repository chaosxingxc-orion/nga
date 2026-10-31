#!/usr/bin/env python3
"""E40 independent report reconstruction; no accelerator import or forward."""
import argparse
import hashlib
import json
from pathlib import Path
import types


def reconstruct(items):
    def item(mode, rep): return items['4200_'+mode+'_'+str(rep)+'.json']
    def exact(a, b):
        return json.dumps(a, ensure_ascii=False, allow_nan=False, separators=(',', ':')) == json.dumps(
            b, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    controls = {}; differences = {}
    for mode in ('original', 'L1', 'L2', 'L1L2'):
        controls[mode+'_repeat'] = exact(item(mode, 0)['prediction'], item(mode, 1)['prediction'])
    for mode in ('L1', 'L2', 'L1L2'):
        for rep in (0, 1):
            a, b = item('original', rep)['prediction'], item(mode, rep)['prediction']
            key=mode+'_vs_original_'+str(rep); controls[key]=exact(a, b)
            differences[key]=dict(logits_max_delta=max(abs(x-y) for x,y in zip(a['logits'],b['logits'])),
                decision_changed=a['answer']['choice'] != b['answer']['choice'])
    flags=['Exact output mismatch: '+k for k,v in controls.items() if not v]
    flags.append('Review required: one input, two repeats; exact agreement is a narrow engineering result')
    memory = {mode:[item(mode, rep)['peak_allocated_gib'] for rep in (0,1)]
              for mode in ('original','L1','L2','L1L2')}
    return dict(controls=controls, exact_outputs=all(controls.values()), differences=differences,
                peak_allocated_gib=memory, review_flags=flags, candidate_batch_admission=False,
                scope='2B fixed input 4200 only; no full JEVal admission, score, stage liveness or general speedup claim')


def verify(plan_path, expected_sha, output):
    raw=plan_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha: raise ValueError('Pinned plan differs')
    p=json.loads(raw); out=plan_path.parent
    def module(filename,name):
        path=out/filename; data=path.read_bytes()
        if path.is_symlink() or hashlib.sha256(data).hexdigest()!=p['files'].get(str(path)):
            raise ValueError('Verifier executable changed')
        m=types.ModuleType(name);m.__file__=str(path);exec(compile(data,str(path),'exec'),m.__dict__);return m
    evidence=module('e38_evidence.py','e40_verify_evidence'); e=evidence.Evidence()
    proto=module('openjev_lifetime_protocol.py','e40_verify_protocol');proto.validate_plan(p)
    prior=module('verify_openjev_path_trace.py','e40_verify_prediction')
    q=module('jeval_reference_queue.py','e40_verify_docker')
    driver=module('openjev_lifetime_npu.py','e40_verify_binding')
    e.frozen(p['files']);gen,actual=driver.generation(q,e,p,expected_sha,running=False)
    proto.require(actual['State']['Status']=='exited' and actual['State']['ExitCode']==0,'NPU Docker not exited/0')
    proto.require(e.snapshot(out/'EXIT').data.decode().startswith('rc=0 utc='),'Wrapper EXIT differs')
    terminal=e.load(out/'COMPLETE.json');report=e.load(out/'report.json')
    proto.require(terminal['rc']==0 and terminal['stage']=='completed' and terminal['progress']==terminal['total']==8
        and terminal['plan_sha256']==expected_sha and terminal['output_sha256']==e.sha(out/'report.json'), 'Terminal binding differs')
    proto.require(e.load(out/'GENERATION.json')==gen==report['generation'],'Generation differs')
    items=proto.check_receipts(p,expected_sha,e,prior.check_prediction,complete=True,generation=gen)
    expected=reconstruct(items)
    proto.require(report['plan_sha256']==expected_sha and all(report.get(k)==v for k,v in expected.items()),'Report reconstruction differs')
    for folder,key in [('items','receipt_manifest'),('attempts','attempt_manifest')]:
        proto.require(report[key]=={f.name:e.sha(f) for f in sorted((out/folder).iterdir())},'Report manifest differs')
    e.verify();now=q.inspect(p['container'])
    proto.require(now['Id']==actual['Id'] and now['State']==actual['State'],'Docker exit generation changed')
    result=dict(plan_sha256=expected_sha,report_sha256=e.sha(out/'report.json'),terminal_sha256=e.sha(out/'COMPLETE.json'),
        generation=gen,finished_at=actual['State']['FinishedAt'],actual_exit=0,**expected)
    evidence.publish_new(output,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--plan-sha256',required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();verify(a.plan.absolute(),a.plan_sha256,a.output)
