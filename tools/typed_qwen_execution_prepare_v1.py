"""Prepare complete BEV public TEST inputs; does not claim or launch any device.

Configuration supplies a prior model manifest and an explicit physical-resource
policy. A preparation-only policy deliberately fails launch. Source mapper,
full-label runtime and numerical protocol remain pinned and reproducible.
"""
import argparse,copy,hashlib,json,os,shutil,time,types
from pathlib import Path

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def put(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def ref(p):return {'path':str(p),'sha256':sha(p)}
def mod(p):
 m=types.ModuleType(Path(p).stem);m.__file__=str(p);exec(compile(Path(p).read_bytes(),str(p),'exec'),m.__dict__);return m
def lines(p,rows):
 with p.open('x') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def prepare(config):
 import pyarrow.parquet as pq
 from transformers import AutoTokenizer
 c=load(config);root=Path(c['root']);root.mkdir();(root/'output').mkdir();code=root/'code';code.mkdir();(root/'cpu').mkdir();(root/'inference').mkdir()
 base=load(c['template']);modelplan=load(c['model_plan']);model=modelplan.get('model')
 if isinstance(model,str):model=dict(path=model,files=modelplan['model_files'],manifest_sha256=modelplan['model_sha256'],family='qwen3.5_decoder',name=Path(model).name.removeprefix('Qwen__'),kind='fixed_base')
 actual={str(p):sha(p) for p in Path(model['path']).rglob('*') if p.is_file()}
 if actual!=model['files']:raise ValueError('model inventory changed')
 modules={}
 for k,r in dict(base['modules'],typed=c['typed_adapter']).items():
  source=Path(c['module_overrides'].get(k,r['path']));target=code/source.name
  if k not in c['module_overrides'] and sha(source)!=r['sha256']:raise ValueError('template source changed')
  shutil.copyfile(source,target);modules[k]=ref(target)
 C=mod(modules['runtime']['path']);N=C.module(modules['native']);P=C.module(modules['protocol']);X=C.module(modules['panel']);L=C.module(modules['loader'])
 source=Path(c['source']);raw=pq.read_table(source).to_pylist();T=C.module(modules['typed']);items,rich=T.map_rows(raw);P.validate_items(items)
 # Never let mapper exclusions silently change the advertised denominator.
 questions=sum(len(T.ordered_json(row['questions'])) for row in raw)
 if len(items)!=questions:raise ValueError('source contains excluded questions; explicit exclusion registration required')
 semantic=[N.digest({k:v for k,v in i.items() if k not in ('i','qid','y')}) for i in items]
 kinds={k:sum(i['kind']==k for i in items) for k in ('choice','yes_no','score')}
 observed=dict(source_sha256=sha(source),source_rows=len(raw),count=len(items),kinds=kinds,semantic_duplicates=len(semantic)-len(set(semantic)))
 if observed!=c['expected_population']:raise ValueError('registered population changed')
 tok=AutoTokenizer.from_pretrained(model['path'],local_files_only=True,trust_remote_code=False);tok.padding_side='left';reference=N.reference(Path(base['upstream']['root']));requests=[]
 for i,item in enumerate(items):
  req=N.prepare_request({k:v for k,v in item.items() if k!='y'},tok,reference);X.item_check(req,i,8192);requests.append(req)
  if i%200==0:print(json.dumps(dict(stage='render',completed=i,total=len(items),utc_seconds=time.time())),flush=True)
 gold=[dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)) for i,item in enumerate(items)]
 for name,rows in [('items',items),('gold',gold),('typed_gold',rich)]:lines(root/'cpu'/(name+'.jsonl'),rows)
 lines(root/'inference/requests.jsonl',requests)
 binding=N.digest(dict(native=modules['native']['sha256'],runner=modules['runtime']['sha256'],loader=modules['loader']['sha256'],protocol=modules['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=L.LOADER,image=base['image'],model_sha256=model['manifest_sha256']))
 contract=P.make_contract(items,source_sha256=sha(source),model_sha256=model['manifest_sha256'],runtime_protocol_sha256=binding);put(root/'cpu/CONTRACT.json',contract)
 population={k:ref(p) for k,p in dict(items=root/'cpu/items.jsonl',gold=root/'cpu/gold.jsonl',requests=root/'inference/requests.jsonl',source=source,contract=root/'cpu/CONTRACT.json').items()}
 population.update({k:v for k,v in observed.items() if k!='source_sha256'});population.update(ordered_inputs_sha256=N.digest(requests),contract_sha256=P.sha256_value(contract),protocol_binding_sha256=binding)
 policy=load(c['resource_policy']);put(root/'RESOURCE-POLICY.json',policy)
 base.update(schema='typed-qwen-execution-config-v1',run_id=root.name,container='nga-'+root.name.replace('_','-'),output=str(root/'output'),model=model,population=population,modules=modules,resources=dict(chip=c['chip'],allocation=base['resources']['allocation'],policy=ref(root/'RESOURCE-POLICY.json')))
 base['typed']=dict(protocol=T.PROTOCOL,rich_gold=ref(root/'cpu/typed_gold.jsonl'),scorer=c['scorer'],workers=c['cpu_workers'],chunk_size=c['cpu_chunk_size'])
 refs=[base['typed']['rich_gold'],base['typed']['scorer'],*modules.values(),*base['upstream']['files'].values(),base['resources']['policy'],*[population[k] for k in ('requests','items','gold','source','contract')]]
 refs += list(policy.get('predecessor',{}).values()) + policy.get('priority_refs',[])
 base['files']={r['path']:r['sha256'] for r in refs};put(root/'CONFIG.json',base)
 C.build(str(root/'CONFIG.json'),sha(root/'CONFIG.json'),str(root/'PLAN.json'));C.verify(str(root/'PLAN.json'),sha(root/'PLAN.json'),model_files=False,cpu=True)
 lengths=sorted(len(r['input_ids']) for r in requests)
 result=dict(schema='typed-qwen-execution-preparation-v1',status='PREPARED_NOT_ACTIVATED',config=ref(root/'CONFIG.json'),plan=ref(root/'PLAN.json'),model=model['name'],population=observed,lengths=dict(min=lengths[0],max=lengths[-1],median=lengths[len(lengths)//2]),overlength=0,npu_launched=False,resource_policy_activatable=policy.get('schema')!='PREPARATION_ONLY_NO_RESOURCE_CLAIM',pending=['independent exact plan review','host physical-resource verification','long DEV admission compatibility review'])
 put(root/'PREPARATION.json',result)
 put(root/'VERIFY.json',dict(command=[base['cpu_python'],'-B','-P',modules['runtime']['path'],'verify','--plan',str(root/'PLAN.json'),'--sha256',sha(root/'PLAN.json')],environment=base['cpu_environment']))
 put(root/'LAUNCH-TEMPLATE.json',dict(command=[base['host_python'],'-B','-P',modules['host']['path'],'start','--plan',str(root/'PLAN.json'),'--sha256',sha(root/'PLAN.json'),'--review','REQUIRES_INDEPENDENT_REVIEW_PATH','--review-sha256','REQUIRES_INDEPENDENT_REVIEW_PIN','--attempt','1'],environment=base['host_environment'],activation_authorized=False))
 return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--config',required=True);x=a.parse_args();print(json.dumps(prepare(x.config)),flush=True)
