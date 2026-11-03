#!/usr/bin/env python3
"""DEV smoke acquisition and device-free offline parsing. No scientific admission."""
import argparse, hashlib, json, os, shutil, threading, time, types
from pathlib import Path

BASE=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs')
EXPORTS=('kernel_details.csv','operator_details.csv','step_trace_time.csv','trace_view.json')

def zero(v):return type(v) is int and v==0
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
def accessible_tree(root):
    # Analysis artefacts only: make retained outputs readable by the host verifier.
    root=Path(root)
    for p in [root,*root.rglob('*')]:
        require(not p.is_symlink(),'output symlink')
        os.chmod(p,0o755 if p.is_dir() else 0o644)

def require(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.pending')
    with t.open('w') as f:json.dump(d,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'source changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(ref['path']).read_bytes(),ref['path'],'exec',dont_inherit=True),m.__dict__);return m
def snapshot(root):
    root=Path(root);require(root.is_dir() and not root.is_symlink(),'raw missing')
    files={}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(),'raw symlink')
        if p.is_file():files[str(p.relative_to(root))]={'sha256':sha(p),'bytes':p.stat().st_size}
    require(files and all(v['bytes']>0 for k,v in files.items() if k.endswith('profiler_info.json')),'raw empty')
    return files

def capture_manifest(trace,plan_pin):
    trace=Path(trace);dirs=[p for p in trace.iterdir() if p.is_dir() and p.name.endswith('_ascend_pt')]
    require(len(dirs)==1,'single trace generation required');raw=dirs[0];files=snapshot(raw)
    require(any(k.startswith('FRAMEWORK/') and v['bytes']>0 for k,v in files.items()),'framework raw missing')
    require(any(k.startswith('PROF_') and v['bytes']>0 for k,v in files.items()),'device raw missing')
    require(any(Path(k).name.startswith('profiler_info') and k.endswith('.json') for k in files),'profiler metadata missing')
    require(not any(k.startswith('ASCEND_PROFILER_OUTPUT/') for k in files),'capture already parsed')
    return {'schema':'r3-profile-raw-manifest-v1','plan_sha256':plan_pin,'raw':str(raw),'files':files,'completeness':'structural raw presence only; parser coverage still required'}

def expected_mounts(d,path,p):
    roots=[Path(p['model']),Path(p['adapter'])]
    result=[dict(source=str(x),destination=str(x),readonly=True) for x in roots]
    result += [dict(source=f,destination=f,readonly=True) for f in sorted(d['files']) if not any(Path(f).is_relative_to(x) for x in roots)]
    result += [dict(source=d['out'],destination=d['out'],readonly=False)]
    for x in ['/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']:result.append(dict(source=x,destination=x,readonly=True))
    result.append(dict(source=str(path),destination=str(path),readonly=True))
    return result

def installed_profiler():
    import importlib
    m=importlib.import_module('torch_npu.profiler.profiler')
    require(sha(m.__file__)=='1a04902572383b74a401449e73929b2c4ce728d6c81bb59341876b03c7a82168','installed profiler source differs')
    return m

def verify(path,pin):
    path=Path(path);require(sha(path)==pin,'plan changed');d=read(path)
    require(d['schema']=='r3-profile-named-async-v1' and type(d['chip']) is int and d['chip'] in (1,7),'scope/chip differs')
    require(all(d[k] is False for k in ('test_read','scientific_acceptance','candidate_selection_allowed')),'scope differs')
    require(d['selection']=='first_original_chunk_all_seven_phases' and d['poll_seconds']==600,'selection differs')
    refs=('runtime','host','resource','resource_base','original_plan','original_runtime','profile','profile_runner','named_forward','trace_join','batch_runtime','proposal','selection_manifest','reference_capture_plan','reference_capture_report','queue')
    original=read(d['original_plan']['path']);require(sha(d['original_plan']['path'])==d['original_plan']['sha256']=='e11709e6a2006a232c086d9ad582798820ce8c914511b27562fdccd40f80598b','original generation differs')
    required=dict(original['files']);required.update({d[k]['path']:d[k]['sha256'] for k in refs});required.update(d['support_files'])
    require(d['files']==required,'source closure differs')
    for f,h in d['files'].items():require(Path(f).is_file() and not any(x.is_symlink() for x in (Path(f),*Path(f).parents)) and sha(f)==h,'changed input '+f)
    require(d['runtime']['path']==str(Path(__file__).resolve()),'foreign runtime')
    for k in ('profile','profile_runner','original_runtime'):
        require(d[k]==original['runtime' if k=='original_runtime' else k],'original source differs')
    proposal=read(d['proposal']['path']);selection=read(d['selection_manifest']['path'])
    require(d['proposal']['sha256']=='11918d849df01354ee7b5b860376d58927c3a391e33fd379721278108014bac5','proposal differs')
    require(module(d['named_forward']).ADAPTER_ID=='named_model_forward_ranges_v1' and module(d['trace_join']).ADAPTER_ID=='named_forward_trace_join_v1','adapter version differs')
    P=module(d['profile_runner']);p,cells=P.verify(d['profile']['path'],d['profile']['sha256']);first=next(iter(cells))
    require(first==d['selected_cell']==selection['cell'] and len(cells[first])==32,'original selection differs')
    require([r['id'] for r in cells[first]]==selection['question_ids'] and [r['group_id'] for r in cells[first]]==selection['group_ids'],'ordered membership differs')
    require(all(p[k]==proposal[k] for k in ('model','adapter','dtype','mode','token_budget')) and proposal['hf32'] is False,'protocol differs')
    require(d['reference_capture_plan']['sha256']=='b1770ee475a977b2b56534e2e68f555cfc14d0cb144059e1c4db53533c83693f' and d['reference_capture_report']['sha256']=='f82d94bb4d6eb82935989e1a6648fbae3b5372a40d7d27a7b0d7ad330a9198a3','prior smoke differs')
    require(d['image_sha256']==read(p['source_spec']['path'])['image_sha256'],'image differs')
    require(d['environment']=={'PYTHONDONTWRITEBYTECODE':'1','TOKENIZERS_PARALLELISM':'false'},'environment differs')
    require(d['out']==str(BASE/d['package']/'output') and d['run']=='r3_runs/'+d['package'] and path==BASE/d['package']/'HOST-PLAN.json','paths differ')
    require(d['parse_attempts']==[1,2] and d['max_process_number']==4,'parser policy differs')
    require(d['mounts']==expected_mounts(d,path,p),'mounts differ')
    require(d['allocation']==str(BASE.parent/'CHIP-ALLOCATION.json') and d['container']=='nga-r3-profile-named-'+d['package'],'resource identity differs')
    require(d['modules']=={'resource_base':d['resource_base']},'resource composition differs')
    return d,P,p,{first:cells[first]}

def run(path,pin,attempt):
    require(type(attempt) is int and attempt==1,'fresh smoke only')
    d=read(path);root=Path(d['out']);a=root/'attempts/1';a.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(30):write(a/'heartbeat.json',{'utc_seconds':time.time(),'state':'capture_alive'})
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        d,P,p,cells=verify(path,pin);old=module(d['batch_runtime']);P.load_closure(p['files']);import torch,torch_npu
        installed_profiler()
        torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
        require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 enabled')
        S=__import__('scorer_r3');sc=S.R3Scorer(p['model'],adapter=p['adapter'],device='npu:0',dtype='float32',token_budget=16384)
        start=time.perf_counter();sc.load();sc._sync();loaded=time.perf_counter()-start
        def profiler(out):return torch_npu.profiler.profile(activities=[torch_npu.profiler.ProfilerActivity.CPU,torch_npu.profiler.ProfilerActivity.NPU],on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(str(out),analyse_flag=False))
        def meta():return dict(chips=1,reserved_gib=torch.npu.memory_reserved()/2**30,peak_reserved_gib=torch.npu.max_memory_reserved()/2**30,model_load_seconds=loaded)
        N=module(d['named_forward']);observer=N.NamedForward(sc,pin,1,torch.autograd.profiler.record_function)
        with observer:result=old.batches(P,sc,cells,root,1,pin,profiler,meta,forward_observer=observer)
        named=observer.manifest();write(a/'FORWARDS.json',named)
        require(len(result['trials'])==7 and result['reused_chunks']==0,'fresh phase population differs')
        prior=read(d['reference_capture_report']['path'])
        for trial,previous in zip(result['trials'],prior['trials']):
            require(trial['phase']==previous['phase'] and trial['cell']==previous['cell'] and trial['operand_sha256']==previous['operand_sha256'],'prior operands differ')
            require(all(trial['counter_delta'][k]==previous['counter_delta'][k] for k in ('forwards','tokens','padded_tokens','head_positions','items','dup_questions','dup_candidates_removed')),'prior counters differ')
        result['forward_manifest_sha256']=sha(a/'FORWARDS.json')
        result['forward_scope']='actual lm.model forward; output head and non-forward work remain separately visible'
        manifest=capture_manifest(a/'trace',pin);write(a/'RAW-MANIFEST.json',manifest)
        result.update(scope='32-question lifecycle smoke; no speed claim',timing_claim=False,plan_sha256=pin,attempt=1,raw_manifest_sha256=sha(a/'RAW-MANIFEST.json'))
        write(a/'report.json',result);rc=0
    finally:
        stop.set();t.join(2);write(a/'EXIT.json',dict(exit_code=rc,attempt=1,plan_sha256=pin,utc_seconds=time.time(),scientific_acceptance=False))

def released(d,pin,verify_raw=True):
    root=Path(d['out']);h=root/'host_attempts/1';a=root/'attempts/1'
    required=[h/'EXIT.json',h/'RELEASE.json',h/'CLAIM.json',h/'LAUNCH_RECEIPT.json',a/'EXIT.json',a/'RAW-MANIFEST.json',a/'report.json']
    require(all(p.is_file() and not p.is_symlink() for p in required),'capture/release incomplete')
    e,he,r,c,l=map(read,[a/'EXIT.json',h/'EXIT.json',h/'RELEASE.json',h/'CLAIM.json',h/'LAUNCH_RECEIPT.json'])
    require(zero(e['exit_code']) and zero(he['exit_code']) and zero(he['container_exit_code']) and he['runner_terminal_matches'] is True,'capture failure')
    require(e['scientific_acceptance'] is False and he['scientific_acceptance'] is False,'capture scope differs')
    require(e['plan_sha256']==l['plan_sha256']==he['plan_sha256']==pin and all(type(v['attempt']) is int and v['attempt']==1 for v in (e,l,he)) and l['scientific_acceptance'] is False,'capture generation differs')
    require(c['schema']=='r3-resource-claim-v1' and r['schema']=='r3-resource-release-v1','resource schema differs')
    require(r['claim_sha256']==sha(h/'CLAIM.json') and r['container_id']==l['container_id']==he['container_id'] and r['run']==c['run']==d['run'] and type(r['chip']) is int and type(c['chip']) is int and r['chip']==c['chip']==d['chip'],'release differs')
    m=read(a/'RAW-MANIFEST.json');report=read(a/'report.json')
    require(m['schema']=='r3-profile-raw-manifest-v1' and m['plan_sha256']==pin,'raw generation differs')
    raw=Path(m['raw'])
    require(raw.is_absolute() and raw.parent==a/'trace' and raw.name.endswith('_ascend_pt') and '..' not in raw.parts and not any(x.is_symlink() for x in (raw,*raw.parents)),'raw outside capture trace')
    require(report['schema']=='r3-profile-runtime-report-v1' and report['plan_sha256']==pin and type(report['attempt']) is int and report['attempt']==1 and report['raw_manifest_sha256']==sha(a/'RAW-MANIFEST.json'),'capture report/manifest binding differs')
    require(report['all_raw_exact'] is True and report['test_read'] is False and report['scientific_acceptance'] is False and report['timing_claim'] is False,'capture report scope differs')
    require(m['files'] and all(not Path(k).is_absolute() and '..' not in Path(k).parts for k in m['files']),'unsafe raw inventory')
    if verify_raw:require(canonical(snapshot(raw))==canonical(m['files']),'raw changed')
    return m

def parsed(d,pin,attempt):
    require(type(attempt) is int and attempt in (1,2),'parser attempt differs')
    m=released(d,pin,verify_raw=False);out=Path(d['out'])/'cpu/attempts'/str(attempt)
    terminal=read(out/'EXIT.json');report=read(out/'report.json')
    require(zero(terminal['exit_code']) and terminal['plan_sha256']==pin and type(terminal['attempt']) is int and terminal['attempt']==attempt and terminal['scientific_acceptance'] is False,'CPU terminal generation differs')
    require(report['schema']=='r3-profile-offline-report-v1' and report['plan_sha256']==pin and type(report['attempt']) is int and report['attempt']==attempt and report['raw_manifest_sha256']==sha(Path(d['out'])/'attempts/1/RAW-MANIFEST.json'),'CPU report generation differs')
    require(report['scientific_acceptance'] is False and report['test_read'] is False and report['coverage_adjudicated'] is False,'CPU report scope differs')
    export=out/Path(m['raw']).name/'ASCEND_PROFILER_OUTPUT'
    require(set(report['exports'])==set(EXPORTS),'incomplete exports')
    for name in EXPORTS:
        p=export/name
        require(not any(x.is_symlink() for x in (p,*p.parents)) and p.is_file() and p.stat().st_size>0 and sha(p)==report['exports'][name],'CPU export absent or changed')
    require(report['coverage_sha256']==sha(out/'COVERAGE.json'),'coverage changed')
    coverage=read(out/'COVERAGE.json');require(coverage['status']=='PASS_NAMED_FORWARD_CORRELATION' and coverage['plan_sha256']==pin and coverage['trace_sha256']==report['exports']['trace_view.json'] and coverage['scientific_acceptance'] is False,'coverage identity differs')
    return report

def parse(path,pin,attempt):
    require(type(attempt) is int and attempt in (1,2),'unsupported parser attempt')
    d=read(path);out=Path(d['out'])/'cpu/attempts'/str(attempt);out.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(30):write(out/'heartbeat.json',dict(utc_seconds=time.time(),state='offline_parsing'))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        verify(path,pin);require(not list(Path('/dev').glob('davinci[0-9]*')),'CPU parser has NPU device')
        m=released(d,pin);work=out/Path(m['raw']).name;shutil.copytree(m['raw'],work)
        require(snapshot(work)==m['files'],'copy differs')
        import torch_npu
        parser=installed_profiler()
        started=time.time();parser.analyse(str(work),max_process_number=d['max_process_number'])
        export=work/'ASCEND_PROFILER_OUTPUT';required=EXPORTS
        require(all((export/n).is_file() and (export/n).stat().st_size>0 for n in required),'parser returned without required exports')
        require(snapshot(m['raw'])==m['files'],'original raw changed during parse')
        accessible_tree(work)
        manifest=read(Path(d['out'])/'attempts/1/FORWARDS.json');capture=read(Path(d['out'])/'attempts/1/report.json')
        require(capture['forward_manifest_sha256']==sha(Path(d['out'])/'attempts/1/FORWARDS.json'),'forward manifest changed')
        J=module(d['trace_join']);coverage=J.join(J.iter_events(export/'trace_view.json'),manifest,pin,1)
        coverage.update(trace_sha256=sha(export/'trace_view.json'),forward_manifest_sha256=capture['forward_manifest_sha256'])
        write(out/'COVERAGE.json',coverage)
        write(out/'report.json',{'schema':'r3-profile-offline-report-v1','plan_sha256':pin,'attempt':attempt,'raw_manifest_sha256':sha(Path(d['out'])/'attempts/1/RAW-MANIFEST.json'),'exports':{n:sha(export/n) for n in required},'coverage_sha256':sha(out/'COVERAGE.json'),'parser_seconds':time.time()-started,'scientific_acceptance':False,'test_read':False,'coverage_adjudicated':False});rc=0
    finally:
        stop.set();t.join(2);write(out/'EXIT.json',dict(exit_code=rc,attempt=attempt,plan_sha256=pin,utc_seconds=time.time(),scientific_acceptance=False))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=['verify','run','parse']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args()
    if a.op=='verify':verify(a.plan,a.sha256);print('ASYNC_SMOKE_VERIFIED')
    else:(run if a.op=='run' else parse)(a.plan,a.sha256,a.attempt)
if __name__=='__main__':main()
