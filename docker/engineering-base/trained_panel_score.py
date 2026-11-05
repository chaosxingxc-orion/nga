"""Authenticate trained publication and exported provenance before native scoring."""
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj)
    return obj

def run(c,config_path):
    directory=HERE/'components/inference';sys.path.insert(0,str(directory))
    try:
        T=load(directory/'trained_inference.py','nga_score_trained_inference')
        I=T.base; provenance=c['trained_provenance']
        cp=I.path(provenance['source_config']); rp=I.path(provenance['receipt']); mp=I.path(c['manifest']); sm=I.path(provenance['source_manifest'])
        I.require(I.sha(cp)==provenance['source_config_sha256'] and I.sha(rp)==provenance['receipt_sha256'] and I.sha(mp)==c['manifest_sha256'] and I.sha(sm)==provenance['source_manifest_sha256'],'trained provenance pin differs')
        cfg=I.read_json(cp)
        import jsonschema
        jsonschema.Draft202012Validator(I.read_json(HERE/'schema.json')).validate(cfg)
        I.require(cfg['adapter']=='trained-full-label-v1','trained source required')
        body={k:v for k,v in cfg.items() if k not in ('schema','output')}
        rows,_,model_identity,model_hash,identity=T.admit(body)
        receipt=I.read_json(rp); manifest=I.read_json(mp)
        I.fields(receipt,('schema','source_config_sha256','source_owner_sha256','source_completion_sha256','source_exit_sha256','source_predictions_sha256','source_manifest_sha256','model_sha256','inference_identity_sha256','contract_sha256','source_item_receipts_sha256','export_manifest_sha256','export_receipts_sha256'))
        original=I.read_json(sm)
        I.require(receipt['source_manifest_sha256']==I.sha(sm) and set(original)==set(manifest) and all(manifest[k]==v for k,v in original.items() if k not in ('records','receipts_sha256')), 'trained source manifest differs')
        I.require(receipt['schema']=='nga-trained-export-receipt-v1' and receipt['source_config_sha256']==I.sha(cp) and receipt['model_sha256']==model_hash and receipt['inference_identity_sha256']==identity and receipt['contract_sha256']==body['panel']['contract_sha256'], 'trained identity or source differs')
        I.require(receipt['export_manifest_sha256']==I.sha(mp) and receipt['export_receipts_sha256']==manifest['receipts_sha256'] and manifest['model_sha256']==model_hash and manifest['population']['contract_sha256']==receipt['contract_sha256'] and manifest['population']['count']==len(rows), 'trained export binding differs')
        I.require(rp.parent==mp.parent and rp.name=='trained-export-receipt.json', 'trained receipt location differs')
        for key in ('contract','items','gold','requests'):
            item=manifest['population'][key]; I.require(I.sha(I.path(item['path']))==item['sha256'], 'trained population pin differs')
        source=I.path(provenance['source']); owner=I.read_json(source/'OWNER.json'); panel=body['panel']
        I.require(I.sha(source/'OWNER.json')==receipt['source_owner_sha256'] and I.exact(owner,{'schema':'nga-trained-owner-v1','identity_sha256':identity,'model_sha256':model_hash,'output':cfg['output']}), 'trained owner differs')
        for name,key in (('completion.json','source_completion_sha256'),('EXIT.json','source_exit_sha256'),('predictions.json','source_predictions_sha256')):
            I.require(I.sha(source/name)==receipt[key], 'trained source evidence differs')
        completion=I.read_json(source/'completion.json'); terminal=I.read_json(source/'EXIT.json')
        I.require(completion.get('identity_sha256')==identity and completion.get('model_sha256')==model_hash and completion.get('contract_sha256')==panel['contract_sha256'] and completion.get('completed')==len(rows) and completion.get('predictions_sha256')==I.sha(source/'predictions.json') and terminal.get('identity_sha256')==identity and terminal.get('exit_code')==0 and terminal.get('completed')==len(rows), 'trained completion differs')
        pop=manifest['population']; requests=[json.loads(x,object_pairs_hook=I._unique) for x in I.path(pop['requests']['path']).read_text().splitlines()]
        I.require(len(requests)==len(rows) and I.native.digest(requests)==pop['ordered_inputs_sha256'], 'trained requests differ')
        ref=I.native.reference(I.SOURCE_ROOT); predictions=[]; source_receipts=[]; compact_receipts=[]
        for i,(row,req) in enumerate(zip(rows,requests)):
            I.require(I.native.digest(row)==req['request_sha256'], 'trained request join differs')
            d=source/'items'/f'{i:08d}'; pred=I.validate_record(d,req,identity,ref,panel['contract_sha256']); predictions.append(pred);source_receipts.append(I.sha(d/'COMMITTED.json'))
            record=I.path(manifest['records'])/f'{i:06d}'
            I.require(I.exact(I.read_json(record/'record.json'),{'schema':'bev-native-compact-v1','model_sha256':model_hash,'contract_sha256':panel['contract_sha256'],'prediction':pred,'forwards':1}) and I.exact(I.read_json(record/'COMMITTED.json'),{'record.json':I.sha(record/'record.json')}), 'trained compact output differs')
            compact_receipts.append(I.sha(record/'COMMITTED.json'))
        I.require(I.native.digest(source_receipts)==receipt['source_item_receipts_sha256'] and I.native.digest(compact_receipts)==receipt['export_receipts_sha256'] and I.exact(I.read_json(source/'predictions.json'),{'schema':'nga-trained-predictions-v1','identity_sha256':identity,'model_sha256':model_hash,'contract_sha256':panel['contract_sha256'],'predictions':predictions,'item_receipt_sha256':source_receipts}), 'trained receipt population differs')
        before=(I.sha(cp),I.sha(rp),I.sha(mp),I.sha(sm),model_identity,identity)
        score=load(HERE/'panel_score.py','nga_trained_native_score');score.run(c,config_path)
        after=T.admit(body)
        I.require((I.sha(cp),I.sha(rp),I.sha(mp),I.sha(sm),after[2],after[4])==before,'trained input changed during score')
        out=I.path(c['output'])
        I.write(out/'trained-report.json',{'schema':'nga-trained-panel-score-report-v1','model_sha256':model_hash,'inference_identity_sha256':identity,'source_config_sha256':I.sha(cp),'export_receipt_sha256':I.sha(rp),'manifest_sha256':I.sha(mp),'score_config_sha256':I.sha(I.path(config_path)),'native_report_sha256':I.sha(out/'report.json'),'summary_sha256':I.sha(out/'summary.json')})
    finally:
        sys.path.remove(str(directory))
