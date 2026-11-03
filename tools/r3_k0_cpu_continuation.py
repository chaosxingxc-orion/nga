"""CPU-only replay of immutable K0 inference; separate continuation output."""
import argparse,hashlib,json,time,traceback,types
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def load(ref):
    if sha(ref['path'])!=ref['sha256']:raise ValueError('continuation source changed')
    m=types.ModuleType(Path(ref['path']).stem);m.__file__=ref['path'];exec(compile(Path(m.__file__).read_bytes(),m.__file__,'exec'),m.__dict__);return m

def stage_event(put,out,stage,**kw):
    # ReadBoundary is process-wide and explicitly single-threaded. Liveness is
    # owned by the separate host process; runtime writes only between stages.
    put(Path(out)/'heartbeat.json',{'utc_seconds':time.time(),'state':'cpu_consuming','stage':stage})
    print(json.dumps(dict(utc_seconds=time.time(),stage=stage,**kw)),flush=True)

def audited_stage(action,event):
    event('strict_reports_start')
    result=action()
    event('strict_reports_reconstructed')
    return result

def main(path,pin):
    if sha(path)!=pin:raise ValueError('continuation config changed')
    c=read(path)
    if c['schema']!='k0-cpu-continuation-v1' or c['scientific_acceptance']is not False or c['test_read']is not False:raise ValueError('scope differs')
    for p,h in c['files'].items():
        if sha(p)!=h:raise ValueError('evidence changed: '+p)
    if c['runner']!={'path':str(Path(__file__).resolve()),'sha256':sha(__file__)}:raise ValueError('runner differs')
    C=load(c['consumer']);plan=c['original_plan'];d=C.read(plan['path']);U=C.load(d['runtime']);d,sample=U.verify(plan['path'],plan['sha256'])
    attempt=c['npu_attempt'];release=C.lifecycle(d,plan['sha256'],attempt)
    old=C.read(c['failed_cpu_terminal']['path'])
    if type(old.get('exit_code'))is not int or old['exit_code']==0:raise ValueError('failed predecessor required')
    out=Path(c['out']);out.mkdir(parents=True,exist_ok=False);rc=1
    def event(stage,**kw):stage_event(U.put,out,stage,**kw)
    try:
        event('cpu_continuation_start',config_sha256=pin,npu_attempt=attempt)
        r=C.read(Path(d['out'])/'attempts'/str(attempt)/'report.json')
        C.require(r['plan_sha256']==plan['sha256'] and type(r['attempt'])is int and r['attempt']==attempt and r['scientific_acceptance']is False and r['test_read']is False,'NPU report generation differs')
        C.require(r['sample_sha1']==sample['sample_sha1'] and r['own_failures']==[] and r['cross_passes']==[],'NPU success metadata differs')
        C.verify_model_identity(d,r,U,out);event('disk_identity_verified')
        controls=C.reconstruct(d,sample,r,U);event('controls_reconstructed',**controls)
        reports=audited_stage(lambda:C.strict_reports(d),event)
        result={'schema':'r3-k0-current-cpu-continuation-v1','config_sha256':pin,'original_plan_sha256':plan['sha256'],'npu_attempt':attempt,'controls':controls,'reports':reports,'npureport_sha256':sha(Path(d['out'])/'attempts'/str(attempt)/'report.json'),'release_sha256':sha(Path(d['out'])/'host_attempts'/str(attempt)/'RELEASE.json'),'sample_sha1':sample['sample_sha1'],'scientific_acceptance':False,'test_read':False,'independent_scoped_adjudication_pending':True}
        U.put(out/'report.json',result);U.put(out/'COMPLETE.json',{'exit_code':0,'config_sha256':pin,'report_sha256':sha(out/'report.json'),'scientific_acceptance':False});rc=0;event('cpu_continuation_complete')
    except BaseException:
        event('cpu_continuation_failed');traceback.print_exc();raise
    finally:
        U.put(out/'EXIT.json',{'exit_code':rc,'config_sha256':pin,'original_plan_sha256':plan['sha256'],'npu_attempt':attempt,'scientific_acceptance':False,'utc_seconds':time.time()})
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);v=a.parse_args();main(v.config,v.sha256)
