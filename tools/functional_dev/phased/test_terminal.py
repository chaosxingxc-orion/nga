import importlib.util,json,tempfile,types,threading,time,concurrent.futures
from pathlib import Path
from unittest.mock import patch
T=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('q',T/'queue_proposal.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
results=[]
for phase in ('infer','score'):
 for code,artifact in [(17,True),(0,False),(0,True)]:
  with tempfile.TemporaryDirectory(dir=T/'scratch') as d:
   out=Path(d);j=q.C['jobs'][0];target=out/('full-'+j['id']);calls=[]
   state={'Running':False,'ExitCode':code,'FinishedAt':'synthetic'}
   actual={'Name':'/nga-rc1-cpu-full-'+j['id']+'-'+phase,'Image':q.C['image'],'Config':{'Labels':{'nga.rc1.record-grade':q.C['deployment_id']}},'State':state}
   def cmd(*args):
    calls.append(args)
    if args[:2]==('docker','run'):return 'container-'+phase
    if args[:2]==('docker','inspect'):return json.dumps([actual])
    if args[:2]==('docker','wait'):
     if artifact:
      (target/'result').mkdir(exist_ok=True);(target/'result'/('INFERENCE-READY.json' if phase=='infer' else 'report.json')).write_text('{}')
     return str(code)
    raise AssertionError(args)
   with patch.object(q,'OUT',out),patch.object(q,'cmd',side_effect=cmd),patch.object(q,'reviewed',return_value=True),patch.object(q,'verify_sources'),patch.object(q,'free',return_value=True),patch.object(q.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)),patch.object(q.subprocess,'Popen',return_value=types.SimpleNamespace(wait=lambda **kw:0)):
    try:q.launch_phase(j,'full',{'publication_sha256':'original'},phase)
    except RuntimeError:assert code or not artifact
    else:assert code==0 and artifact
    term=target/(phase+'-EXIT.json');assert json.loads(term.read_text())['exit_code']==(code or (0 if artifact else 1))
    command=json.loads((target/(phase+'-COMMAND.json')).read_text())
    if phase=='score':
     assert '--device' not in command and command[command.index('--cpus')+1]=='4'
     for env in ('OMP_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4','MKL_NUM_THREADS=4'):assert env in command
    if code or not artifact:
     try:q.launch_phase(j,'full',{},phase)
     except RuntimeError as e:assert 'prior failure' in str(e)
     else:raise AssertionError('failure retried')
    else:
     saved=term.read_bytes();term.unlink();before=len([c for c in calls if c[:2]==('docker','run')]);q.launch_phase(j,'full',{'publication_sha256':'original'},phase)
     assert before==len([c for c in calls if c[:2]==('docker','run')])
     term.unlink()
     try:q.launch_phase(j,'full',{'publication_sha256':'changed'},phase)
     except RuntimeError as e:assert 'binding mismatch' in str(e)
     else:raise AssertionError('live resume changed binding accepted')
     term.write_bytes(saved)
     try:q.launch_phase(j,'full',{'publication_sha256':'changed'},phase)
     except RuntimeError:changed_rejected=True
     else:changed_rejected=False
     results.append({'phase':phase,'terminal_changed_binding_rejected':changed_rejected})
     doc=json.loads((target/(phase+'-COMMAND.json')).read_text());doc[-1]='changed-command';(target/(phase+'-COMMAND.json')).write_text(json.dumps(doc))
     try:q.launch_phase(j,'full',{'publication_sha256':'original'},phase)
     except RuntimeError:command_rejected=True
     else:command_rejected=False
     results.append({'phase':phase,'terminal_changed_command_rejected':command_rejected})
     assert changed_rejected and command_rejected
     (target/(phase+'-COMMAND.json')).write_text(json.dumps(command))
     # Restore the exact serialized command bytes from its persisted receipt checksum.
     q.put(target/(phase+'-COMMAND.json'),command)
     receipt_path=target/(phase+'-LAUNCH.json'); saved_receipt=receipt_path.read_bytes(); altered=json.loads(saved_receipt);altered['command_sha256']='0'*64;receipt_path.write_text(json.dumps(altered))
     try:q.launch_phase(j,'full',{'publication_sha256':'original'},phase)
     except RuntimeError: pass
     else:raise AssertionError('changed launch command SHA accepted')
     receipt_path.write_bytes(saved_receipt)
     before=len([c for c in calls if c[:2]==('docker','run')]);q.launch_phase(j,'full',{'publication_sha256':'original'},phase)
     assert before==len([c for c in calls if c[:2]==('docker','run')])
     results.append({'phase':phase,'terminal_sha_rejected':True,'unchanged_terminal_no_relaunch':True})
    results.append({'phase':phase,'exit':code,'artifact':artifact,'checked':True})
# Scheduling contract: infer failure never starts CPU; CPU slot bounded at 2.
events=[]
def fail(j,k,b,p):events.append(p);raise RuntimeError('infer failed')
with patch.object(q,'launch_phase',side_effect=fail):
 try:q.launch({},'full',{})
 except RuntimeError:pass
assert events==['infer']
lock=threading.Lock();active=0;peak=0
barrier=threading.Barrier(8)
def phasefn(j,k,b,p):
 global active,peak
 if p=='infer':barrier.wait(timeout=5);return
 with lock:active+=1;peak=max(peak,active)
 time.sleep(.025)
 with lock:active-=1
with patch.object(q,'launch_phase',side_effect=phasefn):
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(lambda j:q.launch(j,'full',{}),q.C['jobs']))
assert peak==2
results.append({'actual_infer_failure_prevents_cpu':True,'cpu_concurrency_peak':peak})
(T/'QUEUE-CHECKS.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
