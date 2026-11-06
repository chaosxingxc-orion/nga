#!/usr/bin/env python3
"""Detached CPU test harness with machine-readable terminal and heartbeat. No model work."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import threading
import time
import unittest

HERE=Path(__file__).resolve().parent

def save(name,value):
    p=HERE/name;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(t,p)

def main():
    cases=['test_consumer.py','test_watcher.py','test_frozen_integration.py'];results=[];stop=threading.Event()
    save('TEST-LAUNCH.json',{'pid':os.getpid(),'synthetic_cpu_only':True,'argv':sys.argv,'started':time.time()})
    (HERE/'TEST-RELAUNCH.sh').write_text(shlex.join([sys.executable,'-B','-P',str(HERE/'run_tests.py')])+'\n')
    def heartbeat():
        while not stop.wait(15):save('TEST-HEARTBEAT.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed_suites':len(results),'total_suites':len(cases)})
    threading.Thread(target=heartbeat,daemon=True).start()
    code=0
    try:
        for name in cases:
            start=time.monotonic();spec=importlib.util.spec_from_file_location('acceptance_'+name[:-3],HERE/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            suite=unittest.defaultTestLoader.loadTestsFromModule(module);r=unittest.TextTestRunner(verbosity=1).run(suite)
            results.append({'suite':name,'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'elapsed_seconds':time.monotonic()-start})
            save('TEST-RESULTS.json',{'synthetic_cpu_only':True,'suites':results,'success':all(x['failures']==x['errors']==0 for x in results)})
            if not r.wasSuccessful():code=1
    except BaseException as e:
        code=1;save('TEST-HARNESS-ERROR.json',{'type':type(e).__name__,'detail':str(e)});raise
    finally:
        stop.set();save('TEST-EXIT.json',{'exit_code':code,'tests':sum(x['tests'] for x in results),'synthetic_cpu_only':True,'finished':time.time()})
    return code

if __name__=='__main__':sys.exit(main())
