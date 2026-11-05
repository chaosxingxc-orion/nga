"""Trained full-label inference component v1. No configurable code loading."""
from pathlib import Path
import json, sys, fcntl, os, uuid, time, threading, types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'training'))
import family, training
import native_inference as base

VERSION = 'trained-full-label-v1'
# Shared across independently loaded copies of this module in the same interpreter.
_guard_module = sys.modules.setdefault('_nga_trained_process_guard', types.ModuleType('_nga_trained_process_guard'))
if not hasattr(_guard_module, 'lock'):
    _guard_module.lock = threading.Lock()

def model_identity(config):
    """Verify the registered base and terminal publication; return identity and its digest."""
    import torch
    recipe = family.RECIPES[config['recipe_id']]
    m=config['model']; a=config['adapter_publication']
    base.require(m['id']==recipe['model_id'], 'recipe/model mismatch')
    root=base.path(m['path']); manifest=base.path(m['manifest'])
    base.require(not any(p.is_symlink() for p in root.rglob('*')), 'model symlink')
    inventory=training.verify_manifest(root,manifest,m['manifest_sha256'])
    base.require(inventory=={'model_id':recipe['model_id'],'files':recipe['files']}, 'registered base inventory differs')
    cp=base.path(a['checkpoint']); base.pin(a['checkpoint_sha256'])
    base.require(cp.is_file() and base.sha(cp)==a['checkpoint_sha256'], 'checkpoint digest differs')
    st=torch.load(cp,map_location='cpu',weights_only=True)
    ident=family.identity({'seed':a['seed']},recipe)
    base.require(family.validate_v2(st,ident,family.expected_topology(recipe))==family.TOTAL, 'terminal checkpoint required')
    pub=base.path(a['path']); base.require(pub.name=='adapter' and pub.is_dir(), 'publication directory required')
    # Existing publisher's retry verification checks exact serialized PEFT config,
    # receipt, binding and every checkpoint tensor. Its existing-destination path is read-only.
    family.publish_adapter(pub.parent,st,ident,a['owner'],a['checkpoint_sha256'])
    # torch.equal accepts equal values across dtypes; publication must preserve checkpoint dtype.
    from safetensors.torch import load_file
    tensors=load_file(str(pub/'adapter_model.safetensors'),device='cpu')
    wanted={n.replace('.default.weight','.weight'):p for n,p in st['lora'].items()}
    base.require(tensors.keys()==wanted.keys() and all(tensors[n].dtype==p.dtype and tensors[n].shape==p.shape for n,p in wanted.items()), 'adapter tensor dtype or shape mismatch')
    publication={n:base.sha(pub/n) for n in ('adapter_config.json','adapter_model.safetensors','PUBLICATION.json','BINDING.json')}
    identity={'schema':'nga-trained-model-identity-v1','recipe_id':recipe['id'],'model_id':recipe['model_id'],'revision':recipe['revision'],'inventory_sha256':training.canonical(recipe['files']),'checkpoint_identity':ident,'checkpoint_sha256':a['checkpoint_sha256'],'publication_files':publication,'load_semantics':'fp32-frozen-base-peft-unmerged-eval-local-only-v1'}
    return identity,base.native.digest(identity)

model_identity_for_config = model_identity

def admit(config):
    import jsonschema
    jsonschema.Draft202012Validator(json.loads((HERE/'trained-schema.json').read_text())).validate(config)
    model_identity,model_hash=model_identity_for_config(config)
    d=config['dataset']
    dp=base.path(d['path']); base.pin(d['sha256']); base.require(base.sha(dp)==d['sha256'], 'dataset digest differs')
    rows=[json.loads(s,object_pairs_hook=base._unique) for s in dp.read_text().splitlines()]
    base.require(len(rows)==d['count'] and len(rows)>0, 'dataset count differs')
    ref=base.native.reference(base.SOURCE_ROOT)
    for i,row in enumerate(rows):
        base.fields(row,('i','qid','state','question','kind','options'))
        base.require(type(row['i']) is int and row['i']==i and type(row['qid']) is str and row['qid'] and type(row['state']) is str and type(row['question']) is str and row['question'] and row['kind'] in ('choice','score','yes_no') and type(row['options']) is list and all(type(x) is str for x in row['options']), 'invalid request')
        ref.make_question(row['question'],row['options'],row['kind'])
    base.require(len({r['qid'] for r in rows})==len(rows),'duplicate qid')
    sources={str(p.relative_to(base.SOURCE_ROOT)):base.sha(p) for p in [base.SOURCE_ROOT/'bev_native_runtime.py',*(base.SOURCE_ROOT/'anyjev'/n for n in sorted(base.native.PINS))]}
    for n,p in base.native.PINS.items(): base.require(sources['anyjev/'+n]==p,'source differs')
    base.require(sources['bev_native_runtime.py']=='25e1bd08d3fce43bc4d3b9827188e0329c62289bc7dcf4f12a09e4c37a0ea460','runtime source differs')
    panel=config['panel']; contract_path=base.path(panel['contract'])
    base.require(base.sha(contract_path)==panel['contract_file_sha256'],'contract file differs')
    contract=base.read_json(contract_path)
    base.fields(contract,('schema','count','items_sha256','source_sha256','model_sha256','runtime_protocol_sha256','tau'))
    base.require(contract['schema']==base.protocol.PROTOCOL and base.protocol.sha256_value(contract)==panel['contract_sha256'] and contract['count']==len(rows) and type(contract['count']) is int,'panel contract differs')
    base.require(contract['model_sha256']==model_hash==panel['model_sha256'], 'trained model identity differs')
    base.require(contract['runtime_protocol_sha256']==sources['bev_native_runtime.py'] and base.native.digest(rows)==panel['ordered_requests_sha256'], 'panel runtime or requests differ')
    for k in ('items_sha256','source_sha256','model_sha256','runtime_protocol_sha256'): base.pin(contract[k])
    run_identity=base.native.digest({'config':config,'model_identity':model_identity,'component_sha256':base.sha(Path(__file__)),'native_component_sha256':base.sha(HERE/'native_inference.py'),'family_sha256':base.sha(HERE.parent/'training/family.py'),'sources':sources})
    return rows,ref,model_identity,model_hash,run_identity

def load_model(config):
    import torch, torch_npu, transformers
    from peft import PeftModel
    torch.npu.conv.allow_hf32=False; torch.npu.matmul.allow_hf32=False
    base.require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 enabled')
    return _load_peft(config, 'npu:0')

def _load_peft(config, device):
    import torch, transformers
    from peft import PeftModel
    model=transformers.AutoModelForCausalLM.from_pretrained(config['model']['path'],dtype=torch.float32,local_files_only=True,trust_remote_code=False)
    for p in model.parameters(): p.requires_grad_(False)
    model=PeftModel.from_pretrained(model,config['adapter_publication']['path'],is_trainable=False,local_files_only=True).to(device).eval()
    base.require(not model.training and all(not p.requires_grad and (not p.is_floating_point() or p.dtype==torch.float32) for p in model.parameters()),'model is not frozen fp32 eval')
    base.require(not any(getattr(m,'merged',False) for m in model.modules()),'merged adapter')
    return model

def run(config, output):
    if not _guard_module.lock.acquire(blocking=False):
        raise RuntimeError('trained inference already active in this process')
    stage=['admission']
    try:
        try:
            return _run(config, output, stage)
        except Exception as exc:
            try:
                if stage[0] != 'execution': _record_rejected_attempt(config, output, exc, stage[0])
            except Exception: pass
            raise
    finally:
        _guard_module.lock.release()

def _record_rejected_attempt(config, output, exc, stage):
    # Existing successful output and its enclosing directory must be in our custody.
    # Never create a new output, follow a symlink, or modify its historical markers.
    out=base.path(str(output))
    base.require(str(out)==os.path.normpath(str(out)) and out.is_dir(), 'unsafe output')
    base.require(out.stat().st_uid==os.geteuid() and out.parent.stat().st_uid==os.geteuid(), 'foreign custody')
    owner_path=base.path(str(out/'OWNER.json')); exit_path=base.path(str(out/'EXIT.json'))
    completion_path=base.path(str(out/'completion.json'))
    owner=base.read_json(owner_path); old_exit=base.read_json(exit_path); completion=base.read_json(completion_path)
    identity=owner.get('identity_sha256'); model=owner.get('model_sha256')
    base.pin(identity); base.pin(model)
    base.require(owner=={'schema':'nga-trained-owner-v1','identity_sha256':identity,'model_sha256':model,'output':str(out)} and
                 old_exit.get('exit_code')==0 and old_exit.get('identity_sha256')==identity and
                 completion.get('schema')=='nga-trained-completion-v1' and completion.get('identity_sha256')==identity and
                 completion.get('model_sha256')==model, 'historical ownership not authenticated')
    attempts=base.path(str(out/'attempt-failures')); attempts.mkdir(exist_ok=True)
    base.require(attempts.is_dir() and attempts.stat().st_uid==os.geteuid(), 'foreign attempts')
    attempt=uuid.uuid4().hex
    record={'schema':'nga-trained-attempt-failure-v1','attempt_id':attempt,
            'attempted_config_sha256':base.native.digest(config),'stage':stage,
            'nonlaunch':True,'error_type':type(exc).__name__,'utc_seconds':time.time(),
            'historical_terminal':'not_the_result_of_this_attempt',
            'historical_owner_sha256':base.sha(owner_path),'historical_completion_sha256':base.sha(completion_path)}
    dataset=config.get('dataset') if type(config) is dict else None
    if type(dataset) is dict and type(dataset.get('path')) is str:
        digest=dataset.get('sha256')
        if type(digest) is str and len(digest)==64 and all(x in '0123456789abcdef' for x in digest):
            record['attempted_input_ref']={'path_sha256':base.native.digest(dataset['path']),'sha256':digest}
    base.write(attempts/(attempt+'.json'),record)

def _run(config, output, stage):
    rows,ref,model_identity,model_hash,identity=admit(config)
    stage[0]='ownership'
    out=base.path(str(output)); panel=config['panel']; contract=panel['contract_sha256']
    inputs=[config['model']['path'],config['model']['manifest'],config['adapter_publication']['path'],config['adapter_publication']['checkpoint'],config['dataset']['path'],panel['contract']]
    for s in inputs:
        p=base.path(s); base.require(not out.is_relative_to(p) and not p.is_relative_to(out),'output overlaps input')
    owner={'schema':'nga-trained-owner-v1','identity_sha256':identity,'model_sha256':model_hash,'output':str(out)}
    out.parent.mkdir(parents=True,exist_ok=True); lockpath=out.parent/(out.name+'.lock'); base.require(not lockpath.is_symlink(),'unsafe lock')
    with lockpath.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if out.exists(): base.require(out.is_dir() and base.exact(base.read_json(out/'OWNER.json'),owner),'output ownership differs')
        else: out.mkdir(); base.fsync_dir(out.parent); base.write(out/'OWNER.json',owner)
        stage[0]='execution'
        done=0; rc=1
        try:
            previous=[out/n for n in ('EXIT.json','completion.json','predictions.json','model-identity.json') if (out/n).exists()]
            if previous:
                import shutil
                history=out/'attempts'; history.mkdir(exist_ok=True); attempt=history/uuid.uuid4().hex; attempt.mkdir()
                for p in previous:
                    with p.open('rb') as src, (attempt/p.name).open('xb') as dst:
                        shutil.copyfileobj(src,dst); dst.flush(); os.fsync(dst.fileno())
                base.fsync_dir(attempt); base.fsync_dir(history); base.fsync_dir(out)
                for p in previous: p.unlink()
                base.fsync_dir(out)
            items=out/'items'; items.mkdir(exist_ok=True); quarantine=out/'quarantine'; quarantine.mkdir(exist_ok=True)
            for p in items.iterdir():
                if p.name.startswith('.partial-') or (p.is_dir() and not (p/'COMMITTED.json').exists()): os.rename(p,quarantine/(p.name+'-'+uuid.uuid4().hex)); base.fsync_dir(items); base.fsync_dir(quarantine)
            base.require(all(p.name in {f'{i:08d}' for i in range(len(rows))} for p in items.iterdir()),'extra items')
            tok=base.load_tokenizer(config); prepared=[base.native.prepare_request(r,tok,ref) for r in rows]
            base.require(all(len(p['input_ids'])<=8192 and p['request_sha256']==base.protocol.request_hash(r) for p,r in zip(prepared,rows)),'prepared request differs')
            valid={}
            for r,p in zip(rows,prepared):
                dest=items/f"{r['i']:08d}"
                if dest.exists(): valid[r['i']]=base.validate_record(dest,p,identity,ref,contract)
            model=load_model(config) if len(valid)<len(rows) else None
            import numpy as np, torch
            predictions=[]; receipts=[]
            for r,p in zip(rows,prepared):
                dest=items/f"{r['i']:08d}"
                if r['i'] in valid: pred=valid[r['i']]
                else:
                    captured=[]
                    class CaptureModel:
                        @property
                        def device(self): return model.device
                        def __call__(self, **kwargs):
                            result=model(**kwargs)
                            captured.append(result.logits[:, -1, :].detach().float().cpu().numpy()[0].copy())
                            return result
                    with torch.no_grad():
                        pred=base.native.read_model_batch(CaptureModel(),[p],tok,mode='transformers_full_labels',contract_sha256=contract,prepared_pins=[base.native.digest(p)],max_length=8192,ref=ref)[0]
                    base.require(len(captured)==1 and captured[0].shape==(248320,) and np.isfinite(captured[0]).all(),'invalid full vocabulary')
                    base.commit_item(items,dest,p,identity,captured[0],pred,contract)
                predictions.append(pred); receipts.append(base.sha(dest/'COMMITTED.json')); done+=1
                base.write(out/'heartbeat.json',{'utc_seconds':time.time(),'completed':done,'total':len(rows),'reused':len(valid)})
            checked=admit(config)
            base.require(checked[2:]==(model_identity,model_hash,identity), 'trained inputs changed during inference')
            base.write(out/'model-identity.json',model_identity)
            base.write(out/'predictions.json',{'schema':'nga-trained-predictions-v1','identity_sha256':identity,'model_sha256':model_hash,'contract_sha256':contract,'predictions':predictions,'item_receipt_sha256':receipts})
            result={'schema':'nga-trained-completion-v1','identity_sha256':identity,'model_sha256':model_hash,'contract_sha256':contract,'ordered_requests_sha256':panel['ordered_requests_sha256'],'completed':done,'reused':len(valid),'runtime':'npu','scientific_acceptance':False,'predictions_sha256':base.sha(out/'predictions.json')}
            base.write(out/'completion.json',result); rc=0; return result
        finally: base.write(out/'EXIT.json',{'exit_code':rc,'identity_sha256':identity,'completed':done,'utc_seconds':time.time()})
