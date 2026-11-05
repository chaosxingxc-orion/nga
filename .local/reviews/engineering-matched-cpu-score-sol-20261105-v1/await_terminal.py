"""One event subscription; no stage polling. Collect only after queue terminal."""
import subprocess,pathlib,time,json,tarfile,io,hashlib
D=pathlib.Path(__file__).resolve().parent
R='/mnt/cephfs/xingchao/experiments/jev/r3_runs/engineering_matched_cpu_score_20261105_v1'
p=subprocess.Popen(['ssh','npu','docker wait nga-matched-cpu-sol-20261105-v1-queue-a2'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
while True:
 try:b,e=p.communicate(timeout=45);break
 except subprocess.TimeoutExpired:print('Waiting on automated summary terminal event; no stage polling.',flush=True)
assert p.returncode==0,e.decode()
b=subprocess.check_output(['ssh','npu','docker cp nga-matched-cpu-sol-20261105-v1-queue-a2:'+R+' -'],timeout=50)
(D/'completed-evidence-a2.tar').write_bytes(b)
files={}
with tarfile.open(fileobj=io.BytesIO(b)) as t:
 for m in t:
  if m.isfile():
   name='/'.join(m.name.split('/')[1:]);data=t.extractfile(m).read();files[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
   if name.endswith('.json') and not name.endswith('FAILURE.json'):
    dest=D/'evidence'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   if name in ['digest.md']: (D/name).write_bytes(data)
(D/'EVIDENCE-PINS.json').write_text(json.dumps(files,indent=2,sort_keys=True)+'\n')
print((D/'digest.md').read_text(),flush=True)
print((D/'evidence/TERMINAL.json').read_text(),flush=True)
