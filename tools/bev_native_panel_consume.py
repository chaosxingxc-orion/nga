"""CPU-only strict full-population consumption; public base TEST only."""
import argparse, json, importlib.util, threading, time, traceback
from pathlib import Path
_spec=importlib.util.spec_from_file_location('frozen_native_panel_runner',Path(__file__).with_name('bev_native_panel_runner.py'))
X=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(X)

def integer(value,expected):return type(value) is int and value==expected

def join(items,prepared,gold,predictions,contract,P,N):
    P.validate_items(items);n=len(items)
    X.require(len(prepared)==len(gold)==len(predictions)==n,'incomplete population')
    joined=[]
    for i,(item,req,g,pred) in enumerate(zip(items,prepared,gold,predictions)):
        X.item_check(req,i,8192)
        X.require(req['request_sha256']==P.request_hash(item)==N.digest({k:v for k,v in item.items() if k!='y'}),'gold-free identity differs')
        X.require(X.exact(g,dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item))),'gold join/order differs')
        X.require(pred['i']==i and type(pred['i']) is int and pred['qid']==item['qid'] and pred['request_sha256']==req['request_sha256'] and pred['input_sha256']==N.digest(req),'prediction input identity differs')
        X.require('y' not in pred and 'gold' not in pred,'producer included gold');joined.append(dict(pred,y=item['y']))
    raw=P.summarise(items,joined,contract=contract,contract_sha256=P.sha256_value(contract))
    kinds={}
    for kind in ('choice','yes_no','score'):
        selected=[(item,pred) for item,pred in zip(items,joined) if item['kind']==kind];correct=sum(item['y']==pred['first_index'] for item,pred in selected)
        kinds[kind]=dict(n=len(selected),correct=correct,accuracy=correct/len(selected) if selected else None,metric_origin='NGA additive stratification')
    return dict(n=n,one_forward=dict(**raw['one_forward'],accuracy=raw['one_forward']['correct']/n),by_type=kinds,adaptive='NOT_EVALUATED',scientific_acceptance=False)

def lifecycle(d,pin,attempt,X):
    X.require(type(attempt) is int and attempt>0,'attempt integer required')
    root=Path(d['out']);a=root/'attempts'/str(attempt);h=root/'host_attempts'/str(attempt)
    terminal=X.read(a/'EXIT.json');host=X.read(h/'EXIT.json');receipt=X.read(h/'LAUNCH_RECEIPT.json');claim=X.read(h/'CLAIM.json');release=X.read(h/'RELEASE.json');spec=X.read(h/'LAUNCH_SPEC.json')
    H=X.module(d['host']);plan=Path(d['out']).parent/'HOST-PLAN.json'
    X.require(integer(terminal['exit_code'],0) and integer(terminal['attempt'],attempt) and terminal['plan_sha256']==pin and terminal.get('scientific_acceptance') is False,'runtime terminal differs')
    X.require(integer(host['exit_code'],0) and integer(host['container_exit_code'],0) and host['runner_terminal_matches'] is True and host.get('scientific_acceptance') is False,'host terminal differs')
    X.require(receipt['plan_sha256']==pin and receipt['container_id']==host['container_id']==release['container_id'],'container lineage differs')
    X.require(spec['plan_sha256']==pin and spec['command']==H.command(d,str(plan),pin,attempt),'launch command differs')
    X.require(receipt['command']==spec['command'][spec['command'].index(d['image_sha256'])+1:],'runtime command differs')
    X.require(claim['run']==release['run']==d['run'] and integer(claim['chip'],d['chip']) and integer(release['chip'],d['chip']) and release['schema']=='r3-resource-release-v1' and release['claim_sha256']==X.sha(h/'CLAIM.json'),'resource lineage differs')
    X.require(integer(release['exit_code'],0) and release.get('scientific_acceptance') is False and release['container']==d['container']+'-a'+str(attempt),'release failed or identity differs')
    X.require(type(host['container_id']) is str and len(host['container_id'])==64 and all(c in '0123456789abcdef' for c in host['container_id']),'container ID malformed')
    report=X.read(a/'report.json')
    X.require(report.get('schema')=='bev-native-panel-completion-v1' and report.get('scientific_acceptance') is False and report.get('adaptive')=='NOT_EVALUATED','completion scope differs')
    return report

def consume(path,pin,cpu_path,cpu_pin,attempt):
    global X
    X.require(X.sha(cpu_path)==cpu_pin and X.sha(path)==pin,'CPU/host plan changed');c=X.read(cpu_path)
    X=X.module(X.read(path)['runtime'])
    d,L,N,prepared=X.verify(path,pin)
    X.require(d['scope']=='public_fixed_base_test' and c['host_plan_sha256']==pin and c['schema']=='native-panel-cpu-plan-v1','not public base panel')
    for k in ('protocol','items','gold','contract','source'):
        X.require(X.sha(c[k]['path'])==c[k]['sha256'],'CPU dependency changed')
    P=X.module(c['protocol']);X.require(c['consumer']['sha256']==X.sha(Path(__file__).resolve()),'consumer source changed');items=X.rows(c['items']['path']);gold=X.rows(c['gold']['path']);contract=X.read(c['contract']['path'])
    binding=N.digest(dict(native=d['native']['sha256'],runner=d['runtime']['sha256'],loader=d['loader_module']['sha256'],protocol=c['protocol']['sha256'],max_length=8192,batch_size=1,mode='transformers_full_labels',loader_config=d['loader'],image=d['image_sha256'],model_sha256=d['model_sha256']))
    X.require(binding==d['protocol_binding_sha256'],'runtime protocol binding differs')
    expected=P.make_contract(items,source_sha256=c['source']['sha256'],model_sha256=d['model_sha256'],runtime_protocol_sha256=d['protocol_binding_sha256'])
    X.require(X.exact(contract,expected) and P.sha256_value(contract)==d['contract_sha256'],'frozen contract differs')
    completion=lifecycle(d,pin,attempt,X);root=Path(d['out']);pred=[];receipts=[]
    X.require({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(len(prepared))},'item inventory differs')
    for i,item in enumerate(prepared):
        dest=root/'items'/f'{i:06d}';pred.append(X.load_item(dest,item,d,N));receipts.append(X.sha(dest/'COMMITTED.json'))
    X.require(completion['completed']==len(items) and type(completion['completed']) is int and completion['receipts_sha256']==N.digest(receipts) and completion['contract_sha256']==d['contract_sha256'] and completion['ordered_inputs_sha256']==d['ordered_inputs_sha256'] and completion['model_sha256']==d['model_sha256'],'completion differs')
    X.require(all(type(completion[k]) is int and completion[k]>=0 for k in ('computed','reused')) and completion['computed']+completion['reused']==len(items) and integer(completion['forwards_per_new_item'],1),'completion counts differ')
    result=join(items,prepared,gold,pred,contract,P,N)
    result.update(schema='bev-native-panel-summary-v1',plan_sha256=pin,cpu_plan_sha256=cpu_pin,attempt=attempt,scope=d['scope'],model=X.fixed_base_name(d['model'])+' fixed checkpoint',engine='Transformers full-label fp32 b1 HF32 off',published_comparison='vLLM top20/H100/Tacit trained weights separate; upstream exact revision lineage unknown')
    return result

def worker(v):
    root=Path(v.output).parent
    X.require(Path(v.output).name=='summary.json' and root==Path(v.plan).parent/'output'/'cpu'/str(v.attempt),'CPU output identity differs')
    X.require(root.is_dir() and not (root/'EXIT.json').exists() and not Path(v.output).exists(),'CPU duplicate or unprepared worker')
    stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):X.write(root/'heartbeat.json',dict(utc_seconds=time.time(),state='cpu_consuming',attempt=v.attempt))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        result=consume(v.plan,v.sha256,v.cpu_plan,v.cpu_sha256,v.attempt)
        with open(v.output,'x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
        rc=0
    finally:
        stop.set();t.join(2)
        X.write(root/'EXIT.json',dict(exit_code=rc,attempt=v.attempt,plan_sha256=v.sha256,cpu_plan_sha256=v.cpu_sha256,summary_sha256=X.sha(Path(v.output)) if rc==0 else None,scientific_acceptance=False,utc_seconds=time.time()))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--cpu-plan',required=True);a.add_argument('--cpu-sha256',required=True);a.add_argument('--attempt',type=int,required=True);a.add_argument('--output',required=True);a.add_argument('--worker',action='store_true');v=a.parse_args()
    if v.worker:worker(v)
    else:
        report=consume(v.plan,v.sha256,v.cpu_plan,v.cpu_sha256,v.attempt)
        with open(v.output,'x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
