"""Prospective v2 full-vector output to existing panel-score compact input."""
import importlib.util, json, sys
from pathlib import Path

def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
I=load(Path(__file__).resolve().parent/'components/inference/native_inference.py','nga_export_inference')
P=I.protocol; N=I.native

def run(c):
    source=I.path(c['source']); output=I.path(c['output']); cp=I.path(c['source_config']); mp=I.path(c['panel_manifest'])
    I.require(not output.exists(),'export output exists')
    for p in (source,cp,mp): I.require(not output.is_relative_to(p) and not p.is_relative_to(output),'output overlaps input')
    I.require(I.sha(cp)==c['source_config_sha256'] and I.sha(mp)==c['panel_manifest_sha256'],'input pin differs')
    cfg=I.read_json(cp); I.require(cfg.get('schema')=='nga-unified-config-v1' and cfg.get('output')==str(source) and cfg.get('adapter') in ('native-full-label-v2','trained-full-label-v1'),'source config differs')
    import jsonschema
    jsonschema.Draft202012Validator(I.read_json(Path(__file__).resolve().parent/'schema.json')).validate(cfg)
    body={k:v for k,v in cfg.items() if k not in ('schema','output')}; panel=body['panel']
    trained=body['adapter']=='trained-full-label-v1'
    if trained:
        directory=Path(__file__).resolve().parent/'components/inference'
        sys.path.insert(0,str(directory))
        try:
            T=load(directory/'trained_inference.py','nga_export_trained_inference')
            rows,_,model_identity,model_hash,identity=T.admit(body)
        finally:
            sys.path.remove(str(directory))
        I.require(I.exact(I.read_json(source/'model-identity.json'),model_identity) and N.digest(model_identity)==model_hash,'model identity differs')
        owner={'schema':'nga-trained-owner-v1','identity_sha256':identity,'model_sha256':model_hash,'output':str(source)}
    else:
        rows=I.verify(body)
        sources={str(p.relative_to(I.SOURCE_ROOT)):I.sha(p) for p in [I.SOURCE_ROOT/'bev_native_runtime.py', *(I.SOURCE_ROOT/'anyjev'/n for n in sorted(N.PINS))]}
        for name,pin in N.PINS.items(): I.require(sources['anyjev/'+name]==pin,'source differs')
        I.require(sources['bev_native_runtime.py']=='25e1bd08d3fce43bc4d3b9827188e0329c62289bc7dcf4f12a09e4c37a0ea460','runtime differs')
        identity=N.digest({'config':body,'component_sha256':I.sha(Path(I.__file__)),'sources':sources})
        owner={'schema':'nga-native-owner-v1','identity_sha256':identity,'output':str(source)}
    I.require(I.sha(source/'OWNER.json')==c['owner_sha256'] and I.exact(I.read_json(source/'OWNER.json'),owner),'foreign owner')
    completion=I.read_json(source/'completion.json'); terminal=I.read_json(source/'EXIT.json')
    I.require(completion.get('schema')==('nga-trained-completion-v1' if trained else 'nga-native-completion-v3') and completion.get('identity_sha256')==identity and (trained or completion.get('config_sha256')==N.digest(body)) and completion.get('completed')==len(rows) and completion.get('contract_sha256')==panel['contract_sha256'] and completion.get('model_sha256')==panel['model_sha256'] and completion.get('ordered_requests_sha256')==panel['ordered_requests_sha256'] and completion.get('predictions_sha256')==I.sha(source/'predictions.json') and terminal.get('exit_code')==0 and terminal.get('identity_sha256')==identity and terminal.get('completed')==len(rows),'completion differs')
    manifest=I.read_json(mp); I.fields(manifest,('schema','population','records','receipts_sha256','model_sha256','plan_sha256','scope','model','engine'))
    I.require(manifest['schema']=='native-panel-input-manifest-v1' and manifest['model_sha256']==panel['model_sha256'],'manifest model differs')
    pop=manifest['population']; I.require(pop['count']==len(rows) and pop['contract_sha256']==panel['contract_sha256'] and pop['protocol_binding_sha256']==I.sha(I.SOURCE_ROOT/'bev_native_runtime.py'),'population differs')
    for k in ('contract','items','gold','requests'):
        p=I.path(pop[k]['path']); I.require(not output.is_relative_to(p.parent) and not p.is_relative_to(output),'output overlaps population'); I.require(I.sha(p)==pop[k]['sha256'],'population pin differs')
    contract=I.read_json(I.path(pop['contract']['path'])); I.require(I.exact(contract,I.read_json(I.path(panel['contract']))) and P.sha256_value(contract)==panel['contract_sha256'],'contract differs')
    def lines(k): return [json.loads(x,object_pairs_hook=I._unique) for x in I.path(pop[k]['path']).read_text().splitlines()]
    items=lines('items'); gold=lines('gold'); prepared=lines('requests'); P.validate_items(items)
    I.require(len(items)==len(gold)==len(prepared)==len(rows),'population count differs')
    from collections import Counter
    I.require(dict(Counter(x['kind'] for x in items))==pop['kinds'] and N.digest(prepared)==pop['ordered_inputs_sha256'],'prepared population differs')
    I.require(I.exact(contract,P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=manifest['model_sha256'],runtime_protocol_sha256=pop['protocol_binding_sha256'],tau=contract['tau'])),'population contract differs')
    itemroot=source/'items'; I.require({p.name for p in itemroot.iterdir()}=={f'{i:08d}' for i in range(len(rows))},'item population differs')
    ref=N.reference(I.SOURCE_ROOT); predictions=[]; source_receipts=[]
    for i,(item,g,req,row) in enumerate(zip(items,gold,prepared,rows)):
        I.require(P.request_hash(item)==N.digest(row)==req['request_sha256'] and g==dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)) and req['i']==i and req['qid']==item['qid'],'request population join differs')
        d=itemroot/f'{i:08d}'; pred=I.validate_record(d,req,identity,ref,panel['contract_sha256']);predictions.append(pred);source_receipts.append(I.sha(d/'COMMITTED.json'))
    expected=dict(schema='nga-trained-predictions-v1' if trained else 'nga-native-predictions-v1',identity_sha256=identity,predictions=predictions,item_receipt_sha256=source_receipts)
    if trained: expected.update(model_sha256=panel['model_sha256'],contract_sha256=panel['contract_sha256'])
    original=I.read_json(source/'predictions.json'); I.require(I.exact(original,expected),'prediction inventory differs')
    # Admission is complete before any destination effect.
    output.mkdir(parents=True); records=output/'records';records.mkdir();receipts=[]
    for i,pred in enumerate(predictions):
        d=records/f'{i:06d}';d.mkdir(); I.write(d/'record.json',dict(schema='bev-native-compact-v1',model_sha256=panel['model_sha256'],contract_sha256=panel['contract_sha256'],prediction=pred,forwards=1)); I.write(d/'COMMITTED.json',{'record.json':I.sha(d/'record.json')}); receipts.append(I.sha(d/'COMMITTED.json'))
    manifest.update(records=str(records),receipts_sha256=N.digest(receipts)); I.write(output/'manifest.json',manifest)

    if trained:
        receipt={'schema':'nga-trained-export-receipt-v1','source_config_sha256':c['source_config_sha256'],
                 'source_owner_sha256':c['owner_sha256'],'source_completion_sha256':I.sha(source/'completion.json'),
                 'source_exit_sha256':I.sha(source/'EXIT.json'),'source_predictions_sha256':I.sha(source/'predictions.json'),
                 'source_manifest_sha256':c['panel_manifest_sha256'],'model_sha256':model_hash,
                 'inference_identity_sha256':identity,'contract_sha256':panel['contract_sha256'],
                 'source_item_receipts_sha256':N.digest(source_receipts),
                 'export_manifest_sha256':I.sha(output/'manifest.json'),'export_receipts_sha256':N.digest(receipts)}
        I.write(output/'trained-export-receipt.json',receipt)
