"""Compose recovered PT2 training with the unchanged DEV member checks.

Eight ordinary members retain v1 behavior. The recovery branch authenticates the
actual recovery evidence before using a private copy of member()'s globals; it
does not mutate shared prelaunch/runtime validators or manufacture legacy files.
"""
import hashlib
from pathlib import Path
import types

def load(path, pin, name):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError('qualification composition source changed: '+str(path))
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(raw,str(path),'exec'),m.__dict__)
    return m

V=load(Path(__file__).with_name('r3_dev_qualification_recovery_v1.py'),
       '63f786f87e0d984376d42d9fa7db1a06c2855ed4381822cf47d5e45c027dd7e1','qualified_dev_v1')
T=load(Path(__file__).with_name('r3_recovered_training_member_v1.py'),
       '3de34a2a89e68cc75c2e8ffd4a851a14beb3276e7da00fe8d8663d72b289a5c6','recovered_training')
Q=V.Q

def member(name,entry,decision,bundle,api):
    files=bundle['files']
    plan=api.Q.bound(entry['plan'],files) if 'plan' in entry else None
    is_recovered=plan is not None and 'recovery' in plan
    if not is_recovered:
        if 'recovered_training' in entry:
            raise ValueError('recovery binding on ordinary member')
        return V.member(name,entry,decision,bundle,api)
    if name!='pt_s2':
        raise ValueError('recovered training only registered for pt_s2')
    execution=api.Q.bound(entry['execution'],files)
    if 'resume_import' in execution or 'recovery_result_review' in entry:
        raise ValueError('PT2 recovered training does not imply imported DEV authority')
    result=T.verify(name,entry,plan,decision,files,Q)
    # Preserve all protocol/report/evaluation/lineage checks. Scope the two
    # alternate training checks to this exact member invocation only.
    namespace=dict(V.original_member.__globals__)
    def prelaunch(n,e,p,d,f,a):
        if (n,e,p,d,f,a)!=(name,entry,plan,decision,files,api):
            raise ValueError('recovery prelaunch call differs')
        return result['prelaunch_completed']
    def runtime(e,p,d,a,f):
        if (e,p,d,a,f)!=(entry,plan,decision,api,files):
            raise ValueError('recovery runtime call differs')
        return result['training']
    namespace.update(verify_prelaunch=prelaunch,training_runtime=runtime)
    scoped=types.FunctionType(V.original_member.__code__,namespace,
                              V.original_member.__name__,V.original_member.__defaults__,
                              V.original_member.__closure__)
    return scoped(name,entry,decision,bundle,api)

Q.member=member
for name in ('source_api','read_boundary','evaluate','main','entries','numerical','chronology',
             'protocol','verify_prelaunch','training_runtime','evaluation_runtime'):
    globals()[name]=getattr(Q,name)

if __name__=='__main__':
    raise SystemExit(main())
