"""CPU-only v2 panel consumer. Runs after exact durable release, never claims NPU."""
import argparse
import importlib.util
import threading
import time
from pathlib import Path

_spec=importlib.util.spec_from_file_location('panel_config',Path(__file__).with_name('bev_native_dataset_panel_v1.py'))
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)


def lifecycle(d,pin,attempt):
    root=Path(d['out']);a=root/'attempts'/str(attempt);h=root/'host_attempts'/str(attempt)
    terminal=C.read(a/'EXIT.json');host=C.read(h/'EXIT.json');receipt=C.read(h/'LAUNCH_RECEIPT.json');claim=C.read(h/'CLAIM.json');release=C.read(h/'RELEASE.json');spec=C.read(h/'LAUNCH_SPEC.json')
    integer=lambda value,wanted:type(value) is int and value==wanted
    C.require(integer(terminal.get('exit_code'),0) and integer(terminal.get('attempt'),attempt) and terminal.get('plan_sha256')==pin and terminal.get('test_read') is True and terminal.get('scientific_acceptance') is False,'runtime terminal differs')
    C.require(integer(host.get('exit_code'),0) and integer(host.get('container_exit_code'),0) and host.get('runner_terminal_matches') is True and host.get('plan_sha256')==pin and integer(host.get('attempt'),attempt) and host.get('scientific_acceptance') is False,'host terminal differs')
    C.require(receipt.get('plan_sha256')==pin and integer(receipt.get('attempt'),attempt) and receipt.get('container_id')==host.get('container_id')==release.get('container_id'),'container lineage differs')
    C.require(claim.get('schema')=='r3-resource-claim-v1' and release.get('schema')=='r3-resource-release-v1' and claim.get('run')==release.get('run')==d['run'] and integer(claim.get('chip'),d['chip']) and integer(release.get('chip'),d['chip']) and release.get('claim_sha256')==C.sha(h/'CLAIM.json'),'resource lineage differs')
    C.require(integer(release.get('exit_code'),0) and release.get('scientific_acceptance') is False and release.get('container')==d['container']+'-a'+str(attempt),'release differs')
    H=C.module(d['modules']['host']);view={**d,'runtime':d['modules']['runtime'],'image_sha256':d['image']};path=Path(d['out']).parent/'PLAN.json'
    C.require(spec.get('plan_sha256')==pin and spec.get('command')==H.command(view,str(path),pin,attempt),'command differs')
    C.require(receipt.get('command')==spec['command'][spec['command'].index(d['image'])+1:],'runtime command differs')
    report=C.read(a/'report.json')
    C.require(report.get('schema')=='bev-native-panel-completion-v1' and integer(report.get('attempt'),attempt) and report.get('plan_sha256')==pin and report.get('scientific_acceptance') is False,'completion identity differs')
    C.require(report.get('model_sha256')==d['model_sha256'] and report.get('contract_sha256')==d['population']['contract_sha256'] and report.get('ordered_inputs_sha256')==d['population']['ordered_inputs_sha256'],'completion protocol differs')
    C.require(report.get('adaptive')=='NOT_EVALUATED' and integer(report.get('forwards_per_new_item'),1),'completion readout scope differs')
    return report


def consume(path,pin,attempt):
    d=C.verify(path,pin,cpu=True);view,L,N=C.plan_legacy_view(d);X=C.module(d['modules']['panel']);P=C.module(d['modules']['protocol'])
    C.require(d['modules']['consumer']=={'path':str(Path(__file__).resolve()),'sha256':C.sha(__file__)},'consumer differs')
    pop=d['population'];items=X.rows(pop['items']['path']);gold=X.rows(pop['gold']['path']);requests=X.rows(pop['requests']['path']);contract=C.read(pop['contract']['path'])
    P.validate_items(items);C.require(len(items)==len(gold)==len(requests)==pop['count'],'population incomplete')
    expected=P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=d['model_sha256'],runtime_protocol_sha256=view['protocol_binding_sha256'])
    C.require(contract==expected and P.sha256_value(contract)==pop['contract_sha256'],'contract differs')
    completion=lifecycle(d,pin,attempt);root=Path(d['out']);pred=[];receipts=[]
    native_reference=N.reference(Path(d['upstream']['root']))
    N.reference=lambda *args,**kwargs:native_reference
    C.require({p.name for p in (root/'items').iterdir()}=={f'{i:06d}' for i in range(len(items))},'output population differs')
    def validate_one(i):
        item,req,g=items[i],requests[i],gold[i]
        X.item_check(req,i,8192);C.require(req['request_sha256']==P.request_hash(item),'input source join differs')
        C.require(g==dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)),'gold join differs')
        dest=root/'items'/f'{i:06d}';p=X.load_item(dest,req,view,N)
        C.require(type(p.get('i')) is int and p['i']==i and p['qid']==item['qid'] and p['request_sha256']==req['request_sha256'] and p['input_sha256']==N.digest(req) and 'gold' not in p and 'y' not in p,'prediction join differs')
        return dict(p,y=item['y']),C.sha(dest/'COMMITTED.json')
    # Bounded batches preserve ordinal order and exception propagation.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4,thread_name_prefix='native-score') as pool:
        for start in range(0,len(items),64):
            for record,receipt in pool.map(validate_one,range(start,min(start+64,len(items)))):
                pred.append(record);receipts.append(receipt)
    C.require(type(completion.get('completed')) is int and completion['completed']==len(items) and completion.get('receipts_sha256')==N.digest(receipts) and completion.get('contract_sha256')==pop['contract_sha256'] and completion.get('ordered_inputs_sha256')==pop['ordered_inputs_sha256'] and completion.get('model_sha256')==d['model_sha256'],'completion binding differs')
    C.require(all(type(completion.get(k)) is int and completion[k]>=0 for k in ('computed','reused')) and completion['computed']+completion['reused']==len(items) and type(completion.get('forwards_per_new_item')) is int and completion['forwards_per_new_item']==1,'completion counts differ')
    raw=P.summarise(items,pred,contract=contract,contract_sha256=pop['contract_sha256']);kinds={}
    for kind in ('choice','yes_no','score'):
        selected=[(i,p) for i,p in zip(items,pred) if i['kind']==kind];correct=sum(i['y']==p['first_index'] for i,p in selected)
        kinds[kind]=dict(n=len(selected),correct=correct,accuracy=correct/len(selected) if selected else None,metric_origin='NGA additive stratification')
    return dict(schema='native-config-panel-summary-v2',n=len(items),one_forward=dict(**raw['one_forward'],accuracy=raw['one_forward']['correct']/len(items)),by_type=kinds,adaptive='NOT_EVALUATED',scientific_acceptance=False,candidate_test_authority=False,plan_sha256=pin,attempt=attempt,scope=d['scope'],model=C.read(d['config']['path'])['model']['name']+' fixed checkpoint',engine='Transformers full-label fp32 b1 HF32 off')


def worker(path,pin,attempt):
    d=C.read(path);out=Path(d['out'])/'cpu'/str(attempt);C.require(out.is_dir() and not (out/'EXIT.json').exists() and not (out/'summary.json').exists(),'CPU output exists or unprepared')
    stop=threading.Event();rc=1
    def beat():
        while not stop.wait(30):C.put(out/'heartbeat.json',dict(state='cpu_consuming',attempt=attempt,utc_seconds=time.time()))
    t=threading.Thread(target=beat,daemon=True);t.start()
    try:
        C.put(out/'heartbeat.json',dict(state='cpu_consuming',attempt=attempt,utc_seconds=time.time()));result=consume(path,pin,attempt);C.put(out/'summary.json',result);rc=0
    finally:
        stop.set();t.join(2);C.put(out/'EXIT.json',dict(exit_code=rc,plan_sha256=pin,attempt=attempt,scientific_acceptance=False,summary_sha256=C.sha(out/'summary.json') if rc==0 else None,utc_seconds=time.time()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--attempt',type=int,required=True);a=p.parse_args();worker(a.plan,a.sha256,a.attempt)
