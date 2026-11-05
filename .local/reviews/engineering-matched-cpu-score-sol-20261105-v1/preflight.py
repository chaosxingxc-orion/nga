import subprocess,pathlib,json,tarfile,io,hashlib,difflib,os
os.umask(0o077)
D=pathlib.Path(__file__).resolve().parent
B='sha256:5904bd2bdbce7e67a4dfb920879db40f96bd8370af20796781775c565a43dfd9'
C='sha256:27b2f9a84cbc3bc3eca95bb5ded98431f1a87ca8f0ef5d895970f4060ec4f325'
def ssh(s):return subprocess.check_output(['ssh','npu',s],timeout=50)
def put(n,v):(D/n).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def archive(c,p,n):
 b=ssh('docker cp '+c+':'+p+' -');(D/n).write_bytes(b)
 with tarfile.open(fileobj=io.BytesIO(b)) as t:return {m.name:t.extractfile(m).read() for m in t if m.isfile()}
rows={};maps={}
for label,c,img in [('baseline','nga-unified-panel-score-20261105-v4',B),('candidate','nga-cpu-f0c30a72953758397bdca26a1e717fc9962fb86bfe19cc53',C)]:
 x=json.loads(ssh('docker inspect '+c))[0];assert x['Image']==img
 diff=ssh('docker diff '+c).decode().splitlines();assert not [s for s in diff if s[2:].startswith(('/opt/nga','/usr/local','/usr/lib','/usr/bin'))],diff
 maps[label]=archive(c,'/opt/nga',label+'-installed.tar')
 im=json.loads(ssh('docker image inspect '+img))[0]
 rows[label]={'image':img,'container':c,'diff':diff,'files':{k:sha(v) for k,v in maps[label].items()},'rootfs':im['RootFS'],'architecture':im['Architecture'],'size':im['Size']}
reference=json.loads((D.parent/'unified-score-astra-20261105-v4/inputs/BUILD-SOURCES.json').read_text())
for k,v in reference.items():
 if k not in ('Dockerfile','INVENTORY.json'):assert rows['baseline']['files']['nga/'+k]==v,(k,v)
prior=json.loads((D.parent/'engineering-auto-pipeline-real-astra-20261105-v5/PINS.json').read_text())
# Compare to independently retained installed image archive, never current workspace code.
with tarfile.open(D.parent/'engineering-auto-pipeline-real-astra-20261105-v5/installed.tar') as t:
 old={m.name:sha(t.extractfile(m).read()) for m in t if m.isfile()}
assert rows['candidate']['files']==old
changed=[]
for k in sorted(set(maps['baseline'])|set(maps['candidate'])):
 a=maps['baseline'].get(k);b=maps['candidate'].get(k)
 if a!=b:
  changed.append({'path':k,'baseline':sha(a) if a else None,'candidate':sha(b) if b else None})
  if a and b and k in ['nga/panel_score.py','nga/adapter.py','nga/schema.json','nga/entrypoint.sh']:
   (D/(k.split('/')[-1]+'.diff')).write_text(''.join(difflib.unified_diff(a.decode().splitlines(True),b.decode().splitlines(True),fromfile='baseline',tofile='candidate')))
put('PREFLIGHT.json',{'images':rows,'changed':changed,'candidate_matches_astra_archive':True,'baseline_matches_accepted_build':True})
# Only accepted manifest/config/summary, obtained through readonly Docker archive API.
for p,n in [('config.json','source-config'),('manifest.json','source-manifest'),('output/summary.json','source-summary'),('output/EXIT.json','source-terminal')]:
 files=archive('nga-unified-panel-score-20261105-v4','/mnt/cephfs/xingchao/experiments/jev/r3_runs/unified_score_20261105_v4/'+p,n+'.tar')
 assert len(files)==1
 b=next(iter(files.values()));(D/(n+'.json')).write_bytes(b)
assert sha((D/'source-manifest.json').read_bytes())=='0c893733922a0f6cd11deece688d39f36eb161d14f959970d367f6cf2a8478c1'
assert sha((D/'source-summary.json').read_bytes())=='5809e7cded0944611d701e850639b1c9030d3e5693966a427f2af8c10c677368'
print(json.dumps({'changed_count':len(changed),'changed_scoring': [x for x in changed if x['path'] in ['nga/panel_score.py','nga/adapter.py','nga/schema.json','nga/entrypoint.sh']],'source_authenticated':True},indent=2))
