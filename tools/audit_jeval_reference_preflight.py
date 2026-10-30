#!/usr/bin/env python3
"""Independent E31 artifact/identity audit, without retokenization or inference."""
import argparse,collections,hashlib,json,re,threading,time
from pathlib import Path
DATA_SHA='88f090a510e511d1236fdf5ddb428a8b965663ff0cc1061f950b88f0c99d2e82'
TOTAL=11257

def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8<<20),b''):h.update(b)
 return h.hexdigest()
def stamp(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def required_files(c,folder):
 roles={'kev':{'base','code','checkpoint'},'openjev':{'base','code','checkpoint'},'nimble':{'base','code','adapter'}}
 require(c['family'] in roles and set(c['dependency_roles'])==roles[c['family']],'Dependency roles')
 needed={str(Path(c[k]).resolve()) for k in ['data','preregistration']}
 needed.update(str((folder/n).resolve()) for n in ['jeval_reference_preflight.py','prepare_jeval_reference_preflight.py','test_jeval_reference_preflight.py','run.sh','LAUNCH_EXACT.sh','RESUME_EXACT.sh'])
 for role in roles[c['family']]:
  root=Path(c[role]);require(root.is_dir(),'Missing dependency root')
  files=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
  require(files,'Empty dependency root');needed.update(str(p.resolve()) for p in files)
 require(needed<=set(c['files']),'Required dependency omitted')
 return needed
def population(report,terminal,rows,data_hash):
 require(data_hash==report['data_sha256']==DATA_SHA,'Exact dataset identity')
 require(len(rows)==report['rows']==terminal['progress']==terminal['total']==TOTAL,'Population count')
 require(len({r['id'] for r in rows})==TOTAL,'Duplicate original IDs')
def reason_check(family,req,item):
 q=next(iter(req['questions'].values()));n=2 if q['type']=='noul' else len(q['criteria'])
 require(item['candidate_count']==n,'Candidate count')
 status=item['status'];reason=item['reason']
 if family=='nimble' and n>26:
  require((status,reason)==('unsupported','native_v1_candidate_limit_26'),'Candidate-width reason');return
 if family=='nimble' and not req['state'].strip():
  require((status,reason)==('unsupported','native_nonempty_context_required'),'Empty-context reason');return
 require(status!='unsupported','Unsupported reason')
 if status=='eligible':require(reason=='within_native_budget','Eligible reason')
 else:
  allowed={'kev':{'native_context_overflow','packed_limit_16384'},'openjev':{'candidate_limit_4096'},'nimble':{'native_prompt_limit_2048'}}
  require(status=='overlength' and reason in allowed[family],'Overlength reason')
 if 'max_tokens' in item:
  limit={'kev':16384,'openjev':4096,'nimble':2048}[family]
  require(type(item['max_tokens']) is int and item['max_tokens']>0,'Token length')
  require((item['max_tokens']<=limit)==(status=='eligible'),'Length classification')
def audit(folder,state,rows):
 c=json.loads((folder/'config.json').read_text());ch=digest(folder/'config.json');terminal=json.loads((folder/'COMPLETE.json').read_text());launch=json.loads((folder/'LAUNCH_RECEIPT.json').read_text());report=json.loads((folder/'report.json').read_text())
 require(state['Id']==launch['container_id'] and state['Image']==launch['image']==c['image'],'Docker identity')
 require(state['Config']['Cmd']==launch['command']==[str(folder/'run.sh')] and state['Config']['Entrypoint']==launch['entrypoint']==['bash'],'Docker command')
 require(not state['HostConfig']['Devices'] and state['HostConfig']['NanoCpus']==2000000000 and state['HostConfig']['NetworkMode']=='none','CPU isolation')
 require(state['State']['Status']=='exited' and state['State']['ExitCode']==terminal['rc']==0 and terminal['stage']=='completed','Successful terminal')
 require(re.fullmatch(r'rc=0 utc=\S+\n?',(folder/'EXIT').read_text()),'Wrapper exit')
 require((folder/'report.json').stat().st_mtime_ns<=(folder/'COMPLETE.json').stat().st_mtime_ns<=(folder/'EXIT').stat().st_mtime_ns,'Terminal chronology')
 require(ch==launch['config_sha256']==terminal['config_sha256']==report['config_sha256'],'Config identity')
 require(digest(folder/'run.sh')==launch['wrapper_sha256'],'Wrapper identity')
 require(digest(folder/'report.json')==terminal['outputs']['report.json'],'Report identity')
 needed=required_files(c,folder)
 for path,expected in c['files'].items():require(digest(Path(path))==expected,'Frozen file '+path)
 population(report,terminal,rows,digest(Path(c['data'])))
 paths=sorted((folder/'records').glob('*.json'));require([p.name for p in paths]==[f'{i:06d}.json' for i in range(11257)],'Receipt coverage')
 items=[]
 for i,(raw,path) in enumerate(zip(rows,paths)):
  env=json.loads(path.read_text());v=env['payload'];req={'state':raw['state'],'questions':json.loads(raw['questions_json'])}
  require(env['sha256']==stamp(v),'Receipt hash');require(v['index']==i and v['id']==raw['id'] and v['input_sha256']==stamp(raw) and v['request_sha256']==stamp(req) and v['config_sha256']==ch,'Original row identity')
  require(v['type']==next(iter(req['questions'].values()))['type'] and v['source']==raw['source'] and v['source_item_id']==raw['source_item_id'],'Row metadata')
  require(v['status'] in ('eligible','unsupported','overlength'),'Status');reason_check(c['family'],req,v);items.append(v)
 require(report['items']==items,'Report item identities')
 counts=dict(collections.Counter(x['status'] for x in items));by_type={t:dict(collections.Counter(x['status'] for x in items if x['type']==t)) for t in ('choice','noul','score')}
 require(counts==report['counts'] and by_type==report['by_type'],'Report summaries')
 require(report['max_observed_tokens']==max((x.get('max_tokens',0) for x in items),default=0),'Maximum token summary')
 require(report['frozen_files']==len(c['files']),'Frozen file count')
 return {'run':str(folder),'config_sha256':ch,'rows':len(items),'counts':counts,'by_type':by_type,'required_files_independently_checked':len(needed),'reasons':dict(collections.Counter(x['reason'] for x in items)),'status_sequence_sha256':stamp([(x['id'],x['status'],x['reason']) for x in items]),'scope':'Artifact and raw row identity audit using captured Docker state; no independent retokenization, inference or scorer audit'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();rc=1;results=[];stop=threading.Event()
 def heartbeat():
  while not stop.wait(15):
   line=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+f' audited {len(results)} runs\n'
   (a.out/'digest.md').write_text(line)
   with (a.out/'heartbeat.log').open('a') as f:f.write(line)
 thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
 try:
  import pyarrow.parquet as pq
  entries=json.loads(a.state.read_text());rows=pq.read_table('/mnt/cephfs/xingchao/omni/datasets/jev/carlosxiang__JEVal/data/test.parquet').to_pylist()
  for entry in entries:
   results.append(audit(Path(entry['run']),entry['docker'],rows));(a.out/'digest.md').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+f' audited {len(results)}/{len(entries)}\n')
  (a.out/'report.json').write_text(json.dumps(results,indent=2)+'\n');rc=0
 finally:
  stop.set();thread.join();(a.out/'COMPLETE.json').write_text(json.dumps({'rc':rc,'audited':len(results),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
  (a.out/'digest.md').write_text(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+f' terminal rc={rc} audited={len(results)}\n')
if __name__=='__main__':main()
