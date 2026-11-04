"""Reuse unchanged complete-panel CPU scoring after new recovery lifecycle."""
import argparse,types,hashlib
from pathlib import Path
p=Path(__file__).with_name('bev_native_panel_resume_v1.py')
C=types.ModuleType('recovery');C.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),C.__dict__)
ref={'path':str(p.with_name('bev_native_config_panel_consume.py')),'sha256':'3653e68e0354f70b1a3b29eaaab696d0b14cde5e74687b63cc76c479dd05fa02'}
B=C.load(ref);B.C=C;B.__file__=str(Path(__file__).resolve());original=B.lifecycle

def lifecycle(d,pin,attempt):
    report=original(d,pin,attempt);count=C.check_imports(d)
    C.need(report.get('imported_manifest_sha256')==d['recovery']['manifest']['sha256'] and report.get('source_plan_sha256')==d['recovery']['source_plan']['sha256'],'completion source provenance differs')
    C.need(report['reused']==count and report['computed']==d['population']['count']-count,'completion import counts differ')
    return report
B.lifecycle=lifecycle
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,required=True);a=p.parse_args();B.worker(a.plan,a.sha256,a.attempt)
