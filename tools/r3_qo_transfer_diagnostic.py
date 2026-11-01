"""Development-only trained question-only comparison, preregistration section 5.5.

Rebuild reports before comparing. QO is one registered seed2 control, evaluated
with input dropped. Candidate seeds stay separate; no averaged arm pass, formal
admission, FINAL selection or test gain is produced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def safe(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe path')
    require(not any(x == 'test' or x.startswith('test.') for x in path.parts), 'test path forbidden')
    return path


def source(path, pin):
    path = safe(path); raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == pin, 'source identity differs')
    value = types.ModuleType('qo_report_source'); value.__file__ = str(path)
    exec(compile(raw, str(path), 'exec', dont_inherit=True), value.__dict__)
    return value


def compare(candidates, qo, E):
    E.validate_seed_reports(candidates, required_seeds=(2, 3))
    E.validate_seed_reports([qo], required_seeds=(2,), required_arm='K1-QO')
    require(candidates[0]['header']['arm'] in ('K1','K2'), 'adoption candidate arm required')
    reports = candidates + [qo]
    keys = qo['selection_evidence']['keys']
    require(len(keys) == 1920 and len({tuple(k) for k in keys}) == 1920, 'development population differs')
    require([k[0] for k in keys] == ['decision-v7']*1264 + ['transfer-v4']*656, 'suite order differs')
    base = qo['header']['model']
    require(Path(base['base_path']).name == 'Qwen__Qwen3.5-0.8B-Base', 'registered QO base required')
    for report in reports:
        h=report['header']; e=report['selection_evidence']
        require(report.get('schema')=='r3-selection-report-v1' and report.get('scientific_acceptance') is False, 'report scope differs')
        require(h['arm']==e['arm'], 'arm identity differs')
        require(h['model']['kind']=='lora-adapter-unmerged', 'trained adapter required')
        require(h['model']['base_path']==base['base_path'] and h['model']['base_revision']==base['base_revision'], 'base identity differs')
        require(set(h['partitions'])=={'dev','calibration'} and h['track_t_config']=='r3', 'partition/config differs')
        require(h['primary_input_mode']==('drop' if h['arm']=='K1-QO' else 'full'), 'input mode differs')
        for field in ('data_files','prompt_version','prompt_format','render','dtype','readings'):
            require(field in h and h[field]==qo['header'].get(field), 'protocol differs: '+field)
        require(e['keys']==keys, 'paired population differs')
        require(len(e['correct'])==1920 and all(type(x) is int and x in (0,1) for x in e['correct']), 'invalid correctness vector')
        for field in ('cells','question70','decision_lines'):
            require(not report['track_t'].get(field,{}).get('report'), 'report-half metrics forbidden')
    require(len({r['selection_evidence']['adapter_path'] for r in reports})==3, 'candidate/control artifacts alias')
    q=sum(qo['selection_evidence']['correct'][1264:]); rows=[]
    for candidate in sorted(candidates,key=lambda r:r['selection_evidence']['seed']):
        e=candidate['selection_evidence'];correct=sum(e['correct'][1264:]);difference=correct-q
        rows.append({'seed':e['seed'],'candidate_correct':correct,'candidate_accuracy':correct/656,
                     'qo_correct':q,'qo_accuracy':q/656,'difference_pp':100*difference/656,
                     'meets_registered_five_pp_margin':20*difference>=656,
                     'interpretation':'meets development margin only' if 20*difference>=656 else 'not a semantic-transfer claim'})
    return {'schema':'r3-qo-transfer-dev-diagnostic-v1','suite':'transfer-v4','partition':'dev','n':656,
            'qo_seed':2,'candidate_arm':candidates[0]['header']['arm'],'minimum_margin_pp':5,
            'per_seed':rows,'scientific_acceptance':False,'test_read':False,'adoption_authorized':False,
            'scope':'Section 5.5 per-seed development diagnostic only; no seed averaging or overall arm-pass decision; other admission evidence remains required.'}


def rebuilt(path, R, deps, kev, data):
    path=safe(path);require(path.name=='selection_report.json','selection report required')
    raw=path.read_bytes();stored=json.loads(raw)
    actual=R.rebuild(path.parent,kev,data,deps)
    require(canonical(stored)==canonical(actual),'saved report differs from verified readouts')
    require(path.read_bytes()==raw,'report changed during reconstruction')
    return actual,hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',nargs=2,required=True);p.add_argument('--qo',required=True)
    p.add_argument('--report-tool',required=True);p.add_argument('--report-tool-sha256',required=True)
    p.add_argument('--closure',required=True);p.add_argument('--closure-sha256',required=True)
    p.add_argument('--kev-dir',required=True);p.add_argument('--data-root',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();paths=[safe(x) for x in a.candidate+[a.qo]]
    closure=safe(a.closure);kev=safe(a.kev_dir);data=safe(a.data_root);output=safe(a.output)
    require(output.name=='qo_transfer_diagnostic.json','diagnostic output name required')
    require(hashlib.sha256((closure/'manifest.json').read_bytes()).hexdigest()==a.closure_sha256,'closure identity differs')
    R=source(a.report_tool,a.report_tool_sha256);deps=R.modules(closure/'r3_code')
    loaded=[rebuilt(path,R,deps,kev,data) for path in paths]
    result=compare([x[0] for x in loaded[:2]],loaded[2][0],deps[1])
    result['inputs']={str(path):item[1] for path,item in zip(paths,loaded)}
    result['code']={'report_tool_sha256':a.report_tool_sha256,'closure_sha256':a.closure_sha256}
    with output.open('x') as f:f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'scientific_acceptance':False}))


if __name__=='__main__':main()
