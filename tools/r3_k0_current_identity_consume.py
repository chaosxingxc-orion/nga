#!/usr/bin/env python3
"""CPU continuation: rederive controls, replay strict current reports, bind completion."""
import argparse,hashlib,json,tempfile,types,threading,time
from pathlib import Path

def require(ok,msg):
    if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(ref):
    require(sha(ref['path'])==ref['sha256'],'module changed');m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m

def integer(x,value):return type(x)is int and x==value

def lifecycle(d,pin,attempt):
    require(type(attempt)is int and attempt in (1,2),'attempt integer differs')
    root=Path(d['out']);h=root/'host_attempts'/str(attempt);a=root/'attempts'/str(attempt)
    release=read(h/'RELEASE.json');claim=read(h/'CLAIM.json');ht=read(h/'EXIT.json');rt=read(a/'EXIT.json');spec=read(h/'LAUNCH_SPEC.json');receipt=read(h/'LAUNCH_RECEIPT.json')
    for obj in (release,ht,rt):require(integer(obj['exit_code'],0) and obj.get('scientific_acceptance')is False,'failed terminal or scientific scope differs')
    require(integer(ht['container_exit_code'],0) and ht['runner_terminal_matches']is True,'host actual code differs')
    require(release['schema']=='r3-resource-release-v1' and release['claim_sha256']==sha(h/'CLAIM.json'),'release schema/claim differs')
    require(release['run']==claim['run']==d['run'] and integer(release['chip'],d['chip']) and integer(claim['chip'],d['chip']),'release binding differs')
    require(release['container_id']==ht['container_id']==receipt['container_id'] and release['container']==d['container']+'-a'+str(attempt),'container binding differs')
    require(type(ht['container_id'])is str and len(ht['container_id'])==64 and all(c in '0123456789abcdef' for c in ht['container_id']),'container id malformed')
    require(rt['plan_sha256']==pin and integer(rt['attempt'],attempt) and spec['plan_sha256']==receipt['plan_sha256']==pin,'terminal generation differs')
    H=load(d['host']);cmd=H.command(d,Path(d['out']).parent/'HOST-PLAN.json',pin,attempt)
    require(spec['command']==cmd and receipt['command']==cmd[cmd.index(d['image_sha256'])+1:],'actual launch command differs')
    return release

def verify_model_identity(d,report,U,cache_root):
    U.load_code(d)
    import importlib
    T=importlib.import_module('testlock_r3');require(set(report['identity'])==set(U.MODELS),'identity matrix differs')
    for m in U.MODELS:
        cache=Path(cache_root)/('disk_identity_'+m);require(not cache.exists(),'CPU identity cache not fresh')
        actual=T.model_identity(d['targets'][m]['model']['path'],None,str(cache))
        require(U.canonical(actual)==U.canonical(report['identity'][m]) and actual['sha256']==d['targets'][m]['model']['sha256'],'report/disk model identity differs')

def record_grade(d,r):
    z=r['describe'];require(z['scorer']=='scorer_r3.R3Scorer' and z['mode']=='rightpad' and z['dtype']=='float32' and type(z['hf32']) is dict and set(z['hf32'])=={'conv','hf32','matmul'} and all(v is False for v in z['hf32'].values()),'scorer implementation differs')
    require(integer(z['token_budget'],16384) and integer(z['score_chunk_questions'],32) and z['dedup']is True and z['render']=='record_name','scorer record path differs')
    require(z['model_path']==d['targets'][r['weights']]['model']['path'] and z['adapter']is None and z['record_grade']is True and z['record_grade_problems']==[],'record grade/weight identity differs')

def reconstruct(d,sample,report,U):
    require(report['schema']=='r3-k0-current-control-report-v1' and report['verdict']=='VERIFIED','NPU control verdict not verified')
    require(len(report['c32'])==10 and [x['id'] for x in report['c32']]==[x['id'] for x in d['controls']],'c32 population differs')
    def scores_from(parts,context,rows):
        require(isinstance(parts,list) and parts,'parts absent');by={}
        for ref in parts:
            p=Path(ref['path']);require(p.is_relative_to(Path(d['out'])/'resumable'),'part outside generation');z=U.bound(ref)
            ident=z['identity'];require(ident['context']==context,'part context differs');ids=ident['indices']
            require(isinstance(ids,list) and ids and all(type(i)is int and 0<=i<len(rows) for i in ids),'part indices differ')
            require(ident['rows_sha256']==U.digest([rows[i] for i in ids]) and len(z['scores'])==len(ids),'part rows differ')
            for i,s in zip(ids,z['scores']):require(i not in by,'duplicate recovered question');U.scores(s,len(rows[i]['levels']));by[i]=s
        require(set(by)==set(range(len(rows))),'missing recovered question');return [by[i] for i in range(len(rows))]
    for c,r in zip(d['controls'],report['c32']):
        rows=U.bound(c['data'])['rows'];modes={}
        require(set(r['parts'])==set(U.MODES),'c32 mode coverage differs')
        for mode in U.MODES:
            ctx={'plan_sha256':report['plan_sha256'],'phase':'c32','cell':c['id'],'mode':mode,'data_sha256':c['data']['sha256']}
            modes[mode]=scores_from(r['parts'][mode],ctx,rows)
        checks={m:U.strict_compare(modes['exact'],modes[m]) for m in U.MODES[1:]}
        checks['fresh_exact_vs_historical_exact']=U.strict_compare(U.bound(c['historical_exact'])['scores'],modes['exact'])
        require(checks==r['checks'] and all(x['pass_bar'] for x in checks.values()),'c32 rederivation differs')
    want=[(w,c['checkpoint'],c['suite']) for w in U.MODELS for c in sample['cells']]
    require([(r['weights'],r['checkpoint'],r['suite']) for r in report['rescores']]==want,'rescore matrix/order differs')
    for r in report['rescores']:
        record_grade(d,r)
        c=next(c for c in sample['cells'] if (c['checkpoint'],c['suite'])==(r['checkpoint'],r['suite']))
        ctx={k:r[k] for k in ['plan_sha256','phase','checkpoint','suite','weights','sample_sha1']}
        require(ctx['plan_sha256']==report['plan_sha256'] and ctx['phase']=='rescore' and ctx['sample_sha1']==sample['sample_sha1'],'rescore context differs')
        v=scores_from(r['parts'],ctx,c['rows']);cmp=U.strict_compare(c['stored'],v)
        require(cmp==r['comparison'] and cmp['pass_bar']==(r['weights']==r['checkpoint']),'own/counterpart bar differs')
    return {'c32_cells':10,'own_pass':10,'counterpart_fail':10}

def strict_reports(d):
    # This in-process compatibility is scoped to the exact two raw-only K0 producers
    # whose complete reports were independently reviewed. No global consumer file changes.
    cfg=read(d['qualification_config']['path']);require(sha(d['qualification_config']['path'])==d['qualification_config']['sha256'],'qualifier config changed');Q=load(cfg['qualifier'])
    Q.SOURCE_COMPATIBILITY.update({'selection_evidence_r3':('26f4fed70b3817b2c37550df766ea3cfa1ae8d78c03fa832c59e5c0d2a927787','655444d945b9e4d9570186a1b86f78338a36eef5c2552dfb3596812b0df4f38a'),'track_t_r3':('52a6d21e2901136f9d98adb4b28ca768f5627124115c3e4e90fef39ab5cc7295','834e872593f9bc6013f1d4131e33bfabb0194ac618abd66052be177a67217127')})
    api=Q.source_api();result={}
    exact={'base':'fcfe5b4bde340497712ea79a045b02ddac1270b0f19c9d9eb623c46ab660c2df','instruct':'4261e76402ff9b61fee41c98067fcecdaddb7af9a2b28964ea6d2a2203b2441b'}
    for name in ('base','instruct'):
        t=d['targets'][name];require(t['execution']['sha256']==exact[name] and sha(t['execution']['path'])==exact[name],'unreviewed K0 execution')
        b=read(t['bundle']['path']);require(sha(t['bundle']['path'])==t['bundle']['sha256'],'bundle differs');e=b['entry'];execution=read(e['execution']);spec=read(execution['spec']);cmd=spec['command']
        require(cmd[cmd.index('--arm')+1]=='K0' and cmd[cmd.index('--stages')+1]=='k_score,t_score' and cmd[cmd.index('--partitions')+1]=='dev,calibration','non-raw-only producer')
        with tempfile.TemporaryDirectory(prefix='k0-identity-report-') as scratch:
            with Q.read_boundary(api,b['files'],scratch):
                api.Q.inventory(b['files']);context=Q.protocol(b,'k0_'+name,e,api);mod=Q.module(b['selection_report_source']['path'],b['selection_report_source']['sha256']);old=api.R
                try:api.R=mod;api.Q.report(e,context,api)
                finally:api.R=old
                api.Q.inventory(b['files'])
        result[name]={'execution_sha256':exact[name],'report_sha256':sha(e['report']),'canonical_json_identical':True,'selection_only_strict_consumer':True}
    return result

def consume(plan,pin,attempt):
    d=read(plan);U=load(d['runtime']);d,sample=U.verify(plan,pin);root=Path(d['out']);h=root/'host_attempts'/str(attempt);a=root/'attempts'/str(attempt)
    release=lifecycle(d,pin,attempt)
    out=root/'cpu'/str(attempt);out.mkdir(parents=True,exist_ok=False);rc=1;stop=threading.Event()
    def beat():
        while not stop.wait(60):U.put(out/'heartbeat.json',{'utc_seconds':time.time(),'state':'cpu_control_reconstruction'})
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:
        r=read(a/'report.json');require(r['plan_sha256']==pin and type(r['attempt'])is int and r['attempt']==attempt and r['scientific_acceptance'] is False and r['test_read'] is False,'control report generation differs')
        require(r['sample_sha1']==sample['sample_sha1'] and r['own_failures']==[] and r['cross_passes']==[],'report success metadata differs')
        verify_model_identity(d,r,U,out)
        controls=reconstruct(d,sample,r,U);reports=strict_reports(d)
        result={'schema':'r3-k0-current-complete-v1','plan_sha256':pin,'attempt':attempt,'controls':controls,'reports':reports,'npureport_sha256':sha(a/'report.json'),'release_sha256':sha(h/'RELEASE.json'),'sample_sha1':sample['sample_sha1'],'scientific_acceptance':False,'test_read':False,'independent_scoped_adjudication_pending':True}
        U.put(out/'report.json',result);U.put(out/'COMPLETE.json',{'exit_code':0,'plan_sha256':pin,'report_sha256':sha(out/'report.json'),'scientific_acceptance':False});rc=0
    finally:
        stop.set();thread.join(2);U.put(out/'EXIT.json',{'exit_code':rc,'plan_sha256':pin,'attempt':attempt,'scientific_acceptance':False})
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,default=1);a=ap.parse_args();consume(a.plan,a.sha256,a.attempt)
