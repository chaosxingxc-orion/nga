"""Retained-container final evaluation entry; exact-plan inputs only.

Does not create approvals, select models, allocate devices or start containers.
Run only through a reviewed supervisor. Success is publication completion, not
scientific acceptance. Attempt output is durable and an active attempt is locked.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import threading
import traceback


def local(name):
    loader=globals().get('__loader__')
    if hasattr(loader,'sources') and hasattr(loader,'load'):
        return loader.load(name)
    path=Path(__file__).with_name(name+'.py')
    import types
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec',dont_inherit=True),m.__dict__)
    return m


C=local('r3_final_closure')


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,value):
    import tempfile
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        # Containers write as root; host CPU consumers must read terminal and
        # heartbeat evidence after exit without a privileged repair step.
        os.fchmod(fd,0o644)
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def export_vector(plan, pin, result, report, training=None, *, prompt):
    """Persist only vectors returned by the completed source/metric transaction."""
    G=local('r3_final_gain_compare')
    C.require(result.get('state')=='completed','publication not completed')
    suites=result.get('verified_suites',{})
    C.require(set(suites)==set(G.SUITES),'complete verified test vectors required')
    identity=report['header']['model']
    C.require(identity['sha256']==plan['model_sha256'] and report['header']['arm']==plan['arm'],
              'vector model/arm differs')
    header=report['header']
    M=local('r3_final_metrics')
    protocol=M.validate_header(header,prompt=prompt,expected_arm=plan['arm'],
        expected_model=plan['model'],expected_adapter=plan['adapter'],expected_sha256=plan['model_sha256'])
    C.require(protocol==G.protocol_for_arm(plan['arm']),'vector producer protocol differs')
    C.require(plan['scoring']=={'mode':'rightpad','dtype':'float32','hf32':False,
              'token_budget':16384,'stages':'k','shards':1},'vector plan scoring protocol differs')
    scorer=header['scorer']
    inventory=json.loads(Path(plan['base_inventory']['path']).read_text())
    evidence_binding={'plan_sha256':pin,'result':result,'report':report,'training':training}
    vector={'schema':'r3-verified-test-vector-v1','partition':'test','protocol':protocol,
        'arm':plan['arm'],'suites':suites,'model':{**identity,
            'base_inventory_sha256':inventory['inventory_sha256']},
        'scoring_protocol_sha256':hashlib.sha256(G.canonical({'closure':plan['closure']['sha256'],
            'scoring':plan['scoring'],'protocol':protocol,
            'prompt_version':header['prompt_version'],'prompt_format':header['prompt_format'],
            'scorer':{k:v for k,v in scorer.items() if k not in ('model_path','adapter')}}).encode()).hexdigest(),
        'verified_evidence_sha256':hashlib.sha256(G.canonical(evidence_binding).encode()).hexdigest(),
        'scientific_acceptance':False,'execution_plan_sha256':pin,
        'role':'control' if plan['arm'] in ('K1-QO','K1-PT') else 'baseline' if plan['arm']=='K0' else 'candidate'}
    if plan['arm']!='K0':
        C.require(training is not None and training['arm']==plan['arm'] and type(training.get('seed')) is int
                  and training['seed'] in ((2,) if plan['arm']=='K1-QO' else (2,3)),
                  'verified training seed/arm required')
        vector.update(seed=training['seed'],training_variant=training['training_variant'])
    G.validate(vector)
    path=Path(plan['out'])/'TEST-VERIFIED-VECTOR.json'
    if path.exists():C.require(json.loads(path.read_text())==vector,'published vector changed')
    else:atomic(path,vector)
    return {'path':str(path),'sha256':C.sha(path)}


def evaluate(plan,pin,review):
    """All checks precede construction of a lazy real scorer and every commit."""
    root=C.safe(plan['closure']['root'])
    C.require(Path(__file__).resolve()==root/'r3_code/r3_final_driver.py','driver outside pinned closure')
    C.verify(root,plan['closure']['sha256'],import_runtime=True)
    import r3_final_admission as admission
    import full_eval_r3 as evaluator
    import eval_r3
    import r3_final_test_adapter as adapter
    C.require(Path(eval_r3.__file__).resolve()==root/'r3_code/eval_r3.py','scorer factory outside closure')
    training_state={}
    def validate():
        admission.verify(plan,pin,review)
        C.require(Path(plan['dataset_manifest']['path'])==Path(evaluator.C.KEV_DIR)/'manifest.json',
                  'runtime dataset root differs from plan manifest')
        if plan['arm']!='K0':
            import selection_evidence_r3 as evidence
            identity=evaluator.TL.model_identity(plan['model'],plan['adapter'],plan['round_dir'])
            training=evidence.train_identity({'header':{'arm':plan['arm'],'model':identity}})
            C.require(training['training_manifest']==plan['training_manifest']['path']
                      and training['training_manifest_sha256']==plan['training_manifest']['sha256'],
                      'training manifest binding differs')
            training_state['verified']=training
    validate()
    args=evaluator.parse_full_args(['--model-path',plan['model'],'--out',plan['out'],
        '--arm',plan['arm'],'--partitions','calibration,test','--stages','k','--round-dir',plan['round_dir'],
        '--dtype','float32','--no-hf32','--require-record-grade','--scorer','rightpad','--device','npu']
        +(['--adapter',plan['adapter']] if plan['adapter'] else []))
    args.token_budget=16384
    # Do not instantiate/configure an NPU scorer when merely reconciling an
    # already staged publication. The transaction must never call this fallback.
    if (Path(plan['out'])/'TEST-STAGED-RESULTS.json').exists():
        def scorer(*args,**kwargs):raise RuntimeError('recovery must never score')
    else:
        scorer=eval_r3.make_score_fn(args)
    owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,
               final_sha256=plan['final']['sha256'])
    result=adapter.run(args,scorer,evaluator,owner=owner,validate_admission=validate,
                       validate_publication=validate)
    C.require(result.get('state')=='completed','publication transaction incomplete')
    report=json.loads((Path(plan['out'])/'TEST-PRODUCER-REPORT.json').read_text())
    validate()
    export_vector(plan,pin,result,report,training_state.get('verified'),prompt=evaluator.P)
    result['reference_metrics_artifact'] = export_reference_metrics(plan,pin,result,report)
    return result


def export_reference_metrics(plan, pin, result, report):
    """Separate, repeatable export from the same completed source transaction."""
    RM = local('r3_reference_metrics')
    G = local('r3_final_gain_compare')
    C.require(result.get('state') == 'completed', 'publication not completed')
    values = result.get('reference_metrics', {})
    C.require(set(values) == set(G.SUITES), 'complete reference metrics required')
    producer_pin = G.canonical(report)
    producer_pin = hashlib.sha256(producer_pin.encode()).hexdigest()
    panels = {}
    sources = {}
    for suite, value in values.items():
        C.require(value.get('schema') == 'r3-source-reference-metrics-v1'
                  and value.get('suite') == suite and value.get('scientific_acceptance') is False
                  and value.get('publication_authorized') is False
                  and value.get('specification_sha256') == RM.SPECIFICATION_SHA256
                  and value.get('producer_report_sha256') == producer_pin, 'reference metrics binding differs')
        C.require(set(value.get('panels', {})) == {suite+'/test','decision-v7/calibration'},
                  'reference metric panels differ')
        for name, panel in value['panels'].items():
            metric = panel['metrics']; headline = report['track_k']['partitions'][name]['headline']
            C.require(metric.get('schema') == 'r3-reference-probability-metrics-v1'
                      and metric.get('specification_sha256') == RM.SPECIFICATION_SHA256
                      and metric.get('temperature') == 1
                      and metric.get('scientific_acceptance') is False
                      and metric.get('publication_authorized') is False
                      and metric.get('n') == headline['n']
                      and metric.get('accuracy') == headline['kev_rule_accuracy']
                      and metric.get('tie_count') == headline['tie_count'], 'reference metric headline/scope differs')
            C.require(name not in panels or panels[name] == panel, 'calibration panels differ')
            panels[name] = panel
        for name, digest in value['source_sha256'].items():
            G.pin(digest)
            C.require(name not in sources or sources[name] == digest, 'source bindings differ')
            C.require(C.sha(C.safe(name)) == digest, 'reference metric source changed before export')
            sources[name] = digest
    C.require(report['header']['model']['sha256'] == plan['model_sha256']
              and report['header']['arm'] == plan['arm'], 'reference metric model differs')
    output = {'schema':'r3-final-reference-metrics-v1','execution_plan_sha256':pin,
              'closure_sha256':plan['closure']['sha256'],
              'producer_report_sha256':producer_pin,'specification_sha256':RM.SPECIFICATION_SHA256,
              'model':report['header']['model'],'arm':plan['arm'],
              'input_mode':report['header']['primary_input_mode'],
              'panels':panels,'source_sha256':sources,'scientific_acceptance':False,
              'scope':'descriptive T1 metrics after existing publication transaction; no new adoption decision'}
    path = C.safe(Path(plan['out'])/'TEST-REFERENCE-METRICS.json')
    if path.exists():
        C.require(json.loads(path.read_text()) == output, 'published reference metrics changed')
    else:
        atomic(path,output)
    return {'path':str(path),'sha256':C.sha(path)}


def run(plan_path,pin,review,attempt):
    import hashlib
    C.require(type(attempt) is int and attempt>0,'positive attempt required')
    plan_path=C.safe(plan_path);plan=json.loads(plan_path.read_text())
    actual=hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    C.require(actual==pin,'plan differs before opening output')
    out=C.safe(plan['out']);out.mkdir(parents=True,exist_ok=True)
    lockpath=C.safe(out/'final-driver.lock')
    fd=os.open(lockpath,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        directory=C.safe(out/'final-attempts'/str(attempt));directory.mkdir(parents=True,exist_ok=False)
        started=utc();stop=threading.Event()
        def heartbeat():
            count=0
            while not stop.is_set():
                count+=1
                atomic(directory/'heartbeat.json',{'utc':utc(),'count':count,'pid':os.getpid(),
                    'state':'driver_alive','progress_source':str(out/'heartbeat.log')})
                stop.wait(30)
        worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
        rc=125;result=None
        command=[sys.executable,'-B','-P',str(Path(__file__).resolve()),'--plan',str(plan_path),
                 '--sha256',pin,'--review',review['path'],'--review-sha256',review['sha256'],'--attempt',str(attempt)]
        (directory/'COMMAND.txt').write_text(shlex.join(command)+'\n')
        (directory/'RECOVERY.txt').write_text('Use the reviewed supervisor with the same plan/pins and next attempt after actual exit/release.\n')
        try:
            with (directory/'run.log').open('a',buffering=1) as log, redirect_stdout(log),redirect_stderr(log):
                try:
                    result=evaluate(plan,pin,review)
                    atomic(directory/'RESULT.json',result)
                    rc=0
                except BaseException:
                    traceback.print_exc();rc=1
        finally:
            stop.set();worker.join(5)
            terminal={'exit_code':rc,'attempt':attempt,'plan_sha256':pin,'started_utc':started,'finished_utc':utc(),
                      'publication_complete':rc==0,'scientific_acceptance':False}
            atomic(directory/'EXIT.json',terminal)
            atomic(out/'FINAL_EVAL_EXIT.json',terminal)
        return rc
    finally:os.close(fd)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--review',required=True);parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--attempt',required=True,type=int)
    a=parser.parse_args()
    sys.exit(run(a.plan,a.sha256,{'path':a.review,'sha256':a.review_sha256},a.attempt))
