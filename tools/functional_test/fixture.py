import json,subprocess,sys,tempfile
from pathlib import Path
import rc1_trackk as C,supervisor as H
with tempfile.TemporaryDirectory(prefix='rc1-fixture-',dir=str(H.ROOT)) as d:
 p=Path(d); rows=[]; evidence=p/'fixture-evidence';evidence.write_text('SYNTHETIC ONLY')
 for member in C.LANES+C.BASES:
  size=member.split('-')[0];base=p/size;base.mkdir(exist_ok=True);(base/'.complete').write_text('fixture-revision\n');(base/'fake.safetensors').write_text(size)
  k1=member in C.LANES; adapter=None
  if k1:
   adapter=p/member;adapter.mkdir();(adapter/'fake.safetensors').write_text(member)
  ident=C.TL.model_identity(str(base),str(adapter) if adapter else None,str(p/'identity'))
  keys=['base_inventory','tokenizer','runtime']+(['publication','training_terminal','smoke_resume','dev_review'] if k1 else [])
  rows.append(dict(id=member,status='available',arm='K1' if k1 else 'K0',size=size,seed=int(member[-1]) if k1 else None,terminal_step=3116 if k1 else None,model=str(base),adapter=str(adapter) if adapter else None,identity_sha256=ident['sha256'],evidence={k:{'path':str(evidence),'sha256':C.sha(evidence)} for k in keys}))
 roster=p/'roster.json';roster.write_text(json.dumps(rows));camp=p/'campaign'
 subprocess.run([sys.executable,'-P',str(Path(__file__).with_name('assemble.py')),'--roster',str(roster),'--campaign',str(camp),'--chip','3'],check=True)
 docs=[]
 for row in rows:
  member=row['id'];c=json.loads((camp/'drafts'/(member+'.json')).read_text()); final=camp/'configs'/(member+'.json');review=camp/'reviews'/(member+'.json');review.parent.mkdir(exist_ok=True)
  review.write_text(json.dumps({'schema':'rc1-trackk-review-v1','reviewed':True,'config_sha256':C.digest(c),'fixture_only':True}));c['review']={'path':str(review),'sha256':C.sha(review)}
  H.validate(c,str(final));ids=C.validate(c); assert len(ids)==12
  docs.append(c)
 assert len({C.campaign_digest(c) for c in docs})==1
 assert len({c['out'] for c in docs})==12
 assert len({str(Path(c['host']['state_dir'])/c['member']) for c in docs})==12
 for c in docs: assert C.prepare(c)==C.prepare(docs[0])
 assert not (camp/'round'/'TEST-READS.log').exists()
 for c in docs:
  spec=c['container']['spec'];assert H.K.command(spec)[0:2]==['docker','run'];assert spec['cmd'][3]=='infer'; assert C.args(c,'k_score').device=='npu';assert C.args(c,'k').device=='cpu'
 print(json.dumps({'fixture_only':True,'members':12,'core_validate':12,'host_validate':12,'prepare':12,'campaign_sha256':C.campaign_digest(docs[0]),'unique_outputs':12,'unique_state_dirs':12,'test_reads':0,'infer_and_cpu_command_construction':True}))
