"""Versioned qualifier composition: imported DEV provenance plus frozen member().

Non-recovery members follow the exact frozen consumer. No review is authored;
recovery entries require a separately authenticated, externally pinned receipt.
"""
import hashlib
from pathlib import Path
import types

BASE = Path('/home/xingchao/workspace/nga/.local/preparations/production-dev-qualification-20261103-v9/r3_dev_qualification.py')
BASE_SHA = 'fb5f14a39eb917782cf8440ca86fc485b1404813684b9c11c088f3b5c15affb0'
HELPER = Path(__file__).with_name('r3_recovered_dev_member_v1.py')
HELPER_SHA = '8772ab1ac6c94be0b074f93189766de787ca3bba93a680dd12a735f44059fbf4'

def load_module(path, pin, name):
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != pin:
        raise ValueError('qualification composition dependency changed: '+str(path))
    value = types.ModuleType(name); value.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), value.__dict__)
    return value

Q = load_module(BASE, BASE_SHA, 'frozen_qualification')
H = load_module(HELPER, HELPER_SHA, 'recovered_dev_member')
original_member = Q.member

def member(name, entry, decision, bundle, api):
    execution = api.Q.bound(entry['execution'], bundle['files'])
    if 'resume_import' in execution:
        if 'recovery_result_review' not in entry:
            raise ValueError('imported DEV requires independently pinned recovery result review')
        H.verify_recovery(entry, bundle['files'], entry['recovery_result_review'])
    elif 'recovery_result_review' in entry:
        raise ValueError('recovery receipt supplied for a non-recovery execution')
    return original_member(name, entry, decision, bundle, api)

Q.member = member
for name in ('source_api','read_boundary','evaluate','main','entries','numerical','chronology',
             'protocol','verify_prelaunch','training_runtime','evaluation_runtime'):
    globals()[name] = getattr(Q, name)

if __name__ == '__main__':
    raise SystemExit(main())
