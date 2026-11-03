"""Freeze exact public-base TEST and synthetic long-DEV packages. CPU only, no launch."""
import argparse, json, shutil
from pathlib import Path
from tools import bev_native_panel_runner as X

def pin(p):return dict(path=str(Path(p).resolve()),sha256=X.sha(Path(p).resolve()))
def jsonl(path,items):
    with Path(path).open('x') as f:
        for item in items:f.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n')
def prepare(path,p):
    X.require(X.sha(path)==p,'config changed');c=X.read(path)
    for v in c['sources'].values():X.require(X.sha(v['path'])==v['sha256'],'config dependency changed')
    root=Path(c['root']);base=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs');X.require(root.is_relative_to(base) and root!=base and not root.exists(),'fresh root required')
    root.mkdir();(root/'code').mkdir();(root/'cpu').mkdir();(root/'inference').mkdir()
    refs={}
    for k in ('runtime','host','resource','loader_module','native','probe','protocol','consumer','preparer'):
        src=c['sources'][k];dst=root/'code'/Path(src['path']).name;shutil.copyfile(src['path'],dst);refs[k]=pin(dst)
    N=X.module(refs['native']);P=X.module(refs['protocol']);L=X.module(refs['loader_module'])
    model_files={str(q):X.sha(q) for q in sorted(Path(c['model']).rglob('*')) if q.is_file()};model_sha=N.digest(model_files)
    upstream={n:pin(Path(c['upstream_root'])/'anyjev'/n) for n in N.PINS}
    for n,h in N.PINS.items():X.require(upstream[n]['sha256']==h,'source pin differs')
    protocol_binding=N.digest(dict(native=refs['native']['sha256'],runner=refs['runtime']['sha256'],loader=refs['loader_module']['sha256'],protocol=refs['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=L.LOADER,image=L.IMAGE,model_sha256=model_sha))
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(c['model'],local_files_only=True,trust_remote_code=False);tok.padding_side='left'
    if c['scope']=='public_fixed_base_test':
        import pyarrow.parquet as pq
        source=c['sources']['source'];raw=pq.read_table(source['path']).to_pylist();X.require(len(raw)==24386,'source rows differ');items=P.bev_items(raw);P.validate_items(items);X.require(len(items)==46320,'mapped count differs')
        requests=X.rows(c['sources']['requests']['path']);gold=X.rows(c['sources']['gold']['path']);X.require(len(requests)==len(gold)==len(items),'prepared population differs')
        for i,(item,req,g) in enumerate(zip(items,requests,gold)):
            X.item_check(req,i,8192);X.require(req['request_sha256']==P.request_hash(item),'prepared identity differs')
            X.require(X.exact(g,dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item))),'gold join differs')
        # Re-render every request from source + fixed tokenizer: input cache is not an authority.
        ref=N.reference(Path(c['upstream_root']))
        for i,(item,req) in enumerate(zip(items,requests)):
            actual=N.prepare_request({k:v for k,v in item.items() if k!='y'},tok,ref);X.require(X.exact(actual,req),'rendered input differs')
            if i%5000==0:print(json.dumps({'heartbeat':'preparing','completed':i,'total':len(items)}),flush=True)
        contract=P.make_contract(items,source_sha256=source['sha256'],model_sha256=model_sha,runtime_protocol_sha256=protocol_binding)
        jsonl(root/'cpu/items.jsonl',items);jsonl(root/'cpu/gold.jsonl',gold);X.write(root/'cpu/CONTRACT.json',contract);contract_pin=P.sha256_value(contract)
    else:
        X.require(c['scope']=='synthetic_long_dev','scope differs');requests=[]
        # No TEST prompt or output used. Repeated-token boundaries exercise runtime context only.
        for i,length in enumerate((4097,5296,8192)):
            text='x'+(' x'*(length-1));ids=tok.encode(text,add_special_tokens=False);X.require(len(ids)==length,'synthetic tokenizer boundary differs')
            requests.append(dict(schema='bev-native-input-v1',i=i,qid='synthetic-length-'+str(length),request_sha256=N.digest(dict(i=i,text=text,purpose='context-only DEV')),input_ids=ids,rendered_prompt=text,labels=['A','B'],label_ids=[32,33],options=['A','B'],kind='choice'))
        contract=dict(schema='native-synthetic-long-dev-v1',ordered_inputs_sha256=N.digest(requests),model_sha256=model_sha,protocol_binding_sha256=protocol_binding);contract_pin=N.digest(contract);X.write(root/'cpu/CONTRACT.json',contract)
    jsonl(root/'inference/requests.jsonl',requests);inp=pin(root/'inference/requests.jsonl');(root/'output').mkdir()
    d=dict(schema='bev-native-panel-host-v1',scope=c['scope'],**{k:refs[k] for k in ('runtime','host','resource','loader_module','native','probe')},inputs=inp,model=c['model'],model_files=model_files,model_sha256=model_sha,upstream_root=c['upstream_root'],upstream_files=upstream,contract_sha256=contract_pin,protocol_binding_sha256=protocol_binding,ordered_inputs_sha256=N.digest(requests),count=len(requests),max_length=8192,batch_size=1,adapter=None,chip=c['chip'],image_sha256=L.IMAGE,environment=L.ENV,loader=L.LOADER,container=c['container'],out=str(root/'output'),run='r3_runs/'+root.name,allocation=str(base.parent/'CHIP-ALLOCATION.json'),poll_seconds=600,test_read=c['scope']=='public_fixed_base_test',scientific_acceptance=False,candidate_test_authority=False,candidate_selection_allowed=False)
    d['files']={**model_files,**{r['path']:r['sha256'] for r in upstream.values()},**{d[k]['path']:d[k]['sha256'] for k in ('runtime','host','resource','loader_module','native','probe','inputs')}}
    hp=root/'HOST-PLAN.json';d['mounts']=L.mounts(d,hp,{'model':c['model']});X.write(hp,d);d=X.read(hp)
    RR=X.module(refs['runtime']);RR.verify(str(hp),X.sha(hp));H=X.module(refs['host']);H.verify(str(hp),X.sha(hp))
    cpu=dict(schema='native-panel-cpu-plan-v1',host_plan_sha256=X.sha(hp),protocol=refs['protocol'],consumer=refs['consumer'],contract=pin(root/'cpu/CONTRACT.json'),python='/mnt/cephfs/xingchao/experiments/jev/r3_runs/reviewer_torch_runtime_20261101_v1/python/bin/python3.12')
    if c['scope']=='public_fixed_base_test':cpu.update(items=pin(root/'cpu/items.jsonl'),gold=pin(root/'cpu/gold.jsonl'),source=c['sources']['source'])
    X.write(root/'CPU-PLAN.json',cpu)
    review=dict(status='PREPARED_NOT_ADMITTED',config=pin(path),plan=pin(hp),cpu_plan=pin(root/'CPU-PLAN.json'),scope=d['scope'],npu_started=False,test_read=d['test_read'],test_model_outputs=False,candidate_test_authority=False,scientific_acceptance=False,count=len(requests),lengths=dict(max=max(len(r['input_ids']) for r in requests),over4096=sum(len(r['input_ids'])>4096 for r in requests)),expected_commands={'1':H.command(d,str(hp),X.sha(hp),1)},hashes=dict(d['files'],**{str(hp):X.sha(hp)}),remaining=['independent exact package review','synthetic long DEV execution and acceptance before public TEST launch'])
    if c['scope']=='public_fixed_base_test':
        review['cpu_commands']={'1':H.cpu_command(d,str(hp),X.sha(hp),str(root/'CPU-PLAN.json'),X.sha(root/'CPU-PLAN.json'),1)}
        review['hashes'].update({cpu[k]['path']:cpu[k]['sha256'] for k in ('protocol','consumer','contract','items','gold','source')})
        review['hashes'][str(root/'CPU-PLAN.json')]=X.sha(root/'CPU-PLAN.json')
    X.write(root/'REVIEW-INPUT.json',review);return review
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--config',required=True);a.add_argument('--sha256',required=True);v=a.parse_args();result=prepare(v.config,v.sha256);print(json.dumps({'status':result['status'],'plan':result['plan']},indent=2))
