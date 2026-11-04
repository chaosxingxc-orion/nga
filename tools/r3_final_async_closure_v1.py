"""Build a new source-pinned asynchronous final closure. Never launches TEST.

Input is an exact existing final closure, not a mutable experiment. Output is a
new directory. Eligibility and exact-plan review requirements remain unchanged.
"""
import argparse,ast,hashlib,importlib.util,json
from pathlib import Path
S=importlib.util.spec_from_file_location('closure',Path(__file__).with_name('r3_final_closure.py'));C=importlib.util.module_from_spec(S);S.loader.exec_module(C)
MODULES=('r3_final_async_transaction_v1','r3_final_async_adapter_v1','r3_final_async_release_v1','r3_final_async_handoff_v1')


def replace(text,old,new):
    C.require(text.count(old)==1,'transform anchor differs: '+old[:80]);return text.replace(old,new,1)


def driver(text):
    start=text.index('def evaluate(plan,pin,review):');end=text.index('\ndef export_reference_metrics(',start)
    original=text[start:end];prefix=original[:original.index('    # Do not instantiate/configure')]
    prefix=replace(prefix,'import r3_final_test_adapter as adapter',"adapter=local('r3_final_async_adapter_v1')")
    score=replace(prefix,'def evaluate(', 'def evaluate_score(')
    score+='''    if (Path(plan['out'])/'TEST-SCORED-UNVERIFIED.json').exists():
        def scorer(*args,**kwargs):raise RuntimeError('score recovery must never score')
    else:scorer=eval_r3.make_score_fn(args)
    owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,final_sha256=plan['final']['sha256'])
    return adapter.score_phase(args,scorer,evaluator,owner=owner,validate_admission=validate)

'''
    cpu=replace(prefix,'def evaluate(plan,pin,review):','def evaluate_cpu(plan,pin,review,plan_path,attempt):')
    # Imports eval_r3 for identity closure but never constructs/configures scorer.
    cpu+='''    handoff=local('r3_final_async_handoff_v1')
    owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,final_sha256=plan['final']['sha256'])
    result=adapter.consume(args,evaluator,owner=owner,validate_admission=validate,
        validate_release=lambda owner,manifest:handoff.verify_release(plan,plan_path,pin,review,attempt),
        validate_publication=validate)
    C.require(result.get('state')=='completed','publication transaction incomplete')
    report=json.loads((Path(plan['out'])/'TEST-PRODUCER-REPORT.json').read_text())
    validate()
    export_vector(plan,pin,result,report,training_state.get('verified'),prompt=evaluator.P)
    result['reference_metrics_artifact']=export_reference_metrics(plan,pin,result,report)
    return result

'''
    text=text[:start]+score+cpu+text[end:]
    text=replace(text,'result=evaluate(plan,pin,review)','result=evaluate_score(plan,pin,review)')
    text=replace(text,"'publication_complete':rc==0,'scientific_acceptance':False}","'schema':'r3-final-score-exit-v1','scoring_complete':rc==0,\n                      'scored_manifest_sha256':result.get('manifest_sha256') if rc==0 else None,\n                      'publication_complete':False,'scientific_acceptance':False}")
    text=replace(text,"atomic(directory/'EXIT.json',terminal)\n            atomic(out/'FINAL_EVAL_EXIT.json',terminal)","atomic(directory/'SCORE-EXIT.json',terminal)")
    ast.parse(text);return text


def supervisor(text):
    text=replace(text,"R=sibling('r3_resource_adapter');D=sibling('r3_final_driver')","R=sibling('r3_resource_adapter');D=sibling('r3_final_driver')\nV=sibling('r3_final_async_release_v1');H=sibling('r3_final_async_handoff_v1')")
    text=replace(text,"A.require(previous.get('publication_complete') is False,'completed final run cannot restart')","A.require(previous.get('publication_complete') is False,'completed final run cannot restart')\n                H.reconcile_prior_cpu(plan,pin,attempt)")
    text=replace(text,"marker_path=driver_directory/'EXIT.json'","marker_path=driver_directory/'SCORE-EXIT.json'")
    text=replace(text,"terminal=K.reconcile_exit(observed,marker,plan_sha256=pin,attempt=attempt)","manifest_pin=None\n        if marker is not None and marker.get('exit_code')==0:\n            owner=dict(model_sha256=plan['model_sha256'],run_dir=plan['out'],execution_sha256=pin,final_sha256=plan['final']['sha256'])\n            manifest_pin=V.G.digest(V.X.load_scored(out,owner))\n        terminal=V.reconcile_score_exit(observed,marker,plan_sha256=pin,attempt=attempt,manifest_sha256=manifest_pin)")
    text=replace(text,"D.atomic(marker_path,terminal);D.atomic(out/'FINAL_EVAL_EXIT.json',terminal)","D.atomic(driver_directory/'SCORE-MISSING.json',terminal)")
    text=replace(text,"D.atomic(digest,{'utc':D.utc(),'state':'released','terminal':terminal})\n        return terminal","D.atomic(digest,{'utc':D.utc(),'state':'released','terminal':terminal})\n        if terminal['exit_code']==0:\n            dispatched=H.start_cpu(plan,plan_path,pin,review,attempt)\n            D.atomic(directory/'CPU-DISPATCH.json',dispatched)\n        return terminal")
    ast.parse(text);return text


def prepare(source,source_pin,output):
    source=C.safe(source);output=C.safe(output);C.verify(source,source_pin)
    C.require(not output.exists(),'async output exists');old=json.loads((source/'manifest.json').read_text())
    files={rel:(source/rel).read_bytes() for rel in old['files']}
    files['r3_code/r3_final_driver.py']=driver(files['r3_code/r3_final_driver.py'].decode()).encode()
    files['r3_code/r3_final_supervisor.py']=supervisor(files['r3_code/r3_final_supervisor.py'].decode()).encode()
    text=files['r3_code/r3_final_admission.py'].decode()
    anchor="    out=C.safe(plan['out']);round_dir=C.safe(plan['round_dir'])"
    text=replace(text,anchor,"""    cpu=plan.get('cpu_execution')
    require(isinstance(cpu,dict) and set(cpu)=={'python','environment'},'explicit CPU execution config required')
    C.safe(cpu['python'])
    require(isinstance(cpu['environment'],dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in cpu['environment'].items()),'CPU environment differs')
    require(cpu['environment'].get('PYTHONDONTWRITEBYTECODE')=='1' and cpu['environment'].get('TORCH_DEVICE_BACKEND_AUTOLOAD')=='0','CPU environment unsafe')
"""+anchor)
    files['r3_code/r3_final_admission.py']=text.encode()
    sp=importlib.util.spec_from_file_location('async_prepare',Path(__file__).with_name('r3_final_async_eval_prepare_v1.py'));P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
    text=files['r3_code/testlock_r3.py'].decode();C.require(text.count('def verify_reserved_test_result(')==1 and 'def verify_scored_test_result(' not in text,'testlock generation differs')
    files['r3_code/testlock_r3.py']=(text+'\n'+P.extension()).encode()
    for name in MODULES:files['r3_code/'+name+'.py']=Path(__file__).with_name(name+'.py').read_bytes()
    for rel,raw in files.items():ast.parse(raw) if rel.endswith('.py') else None
    output.mkdir(parents=True)
    for rel,raw in files.items():p=output/rel;p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
    result={**old,'files':{rel:hashlib.sha256(raw).hexdigest() for rel,raw in sorted(files.items())},'source_final_closure_sha256':source_pin,'asynchronous_score_cpu_v1':True,'deployable':False,'remaining':['real nine-member eligibility and FINAL','exact-plan independent review','real release/CPU integration qualification'],'scientific_acceptance':False}
    (output/'manifest.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    pin=C.sha(output/'manifest.json');verified=C.verify(output,pin)
    return {'root':str(output),'sha256':pin,'files':verified['files'],'deployable':False,'scientific_acceptance':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--source-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.source,a.source_sha256,a.output),indent=2))
