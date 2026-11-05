"""Config-only frozen native full-label inference, version 1."""
import hashlib
import fcntl
import uuid
import traceback
import json
import os
from pathlib import Path
import sys
import time

# Fixed image-owned closure; never a path supplied by configuration.
SOURCE_ROOT = Path(__file__).resolve().parents[2]/'source/native'
sys.path.insert(0, str(SOURCE_ROOT))
import bev_native_runtime as native
import bev_native_protocol as protocol

MODELS = {f'Qwen3.5-{s}-Base': f'Qwen__Qwen3.5-{s}-Base' for s in ('0.8B','2B','4B')}
MODEL_ROOTS = (Path('/mnt/cephfs/xingchao/models/jev'), Path('/mnt/cephfs/xingchao/omni/models/jev'), Path('/model'))

def require(condition, message):
    if not condition: raise ValueError(message)

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def path(value):
    require(type(value) is str and Path(value).is_absolute(), 'absolute path required')
    p = Path(value)
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlinks forbidden')
    return p

def fields(obj, names):
    require(type(obj) is dict and set(obj) == set(names), 'unknown or missing fields')

def pin(value):
    require(type(value) is str and len(value) == 64 and all(x in '0123456789abcdef' for x in value), 'invalid sha256')

def _unique(pairs):
    d={}
    for k,v in pairs:
        require(k not in d, 'duplicate JSON key'); d[k]=v
    return d

def verify(config):
    v2=config['adapter']=='native-full-label-v2'
    fields(config, ('adapter','model','dataset','max_length','batch_size','runtime') + (('panel','image_sha256') if v2 else ()))
    require(config['adapter'] in ('native-full-label-v1','native-full-label-v2'), 'adapter differs')
    require(config['runtime']=='npu', 'runtime differs')
    require(type(config['max_length']) is int and config['max_length']==8192 and type(config['batch_size']) is int and config['batch_size']==1, 'unregistered length or batch')
    m=config['model']; fields(m, ('id','path','manifest','manifest_sha256'))
    require(m['id'] in MODELS and path(m['path']).name==MODELS[m['id']], 'wrong model')
    root=path(m['path']); require(root.is_dir(), 'model missing')
    if config['runtime']=='npu':
        require(root.parent in MODEL_ROOTS, 'unregistered model mirror')
    manifest=path(m['manifest']); pin(m['manifest_sha256']); require(sha(manifest)==m['manifest_sha256'], 'manifest hash differs')
    inventory=json.loads(manifest.read_bytes()); fields(inventory, ('schema','model_id','files'))
    require(inventory['schema']=='nga-model-manifest-v1' and inventory['model_id']==m['id'], 'wrong model manifest')
    files=inventory['files']; require(type(files) is dict and files and all(type(k) is str and k and not Path(k).is_absolute() and '..' not in Path(k).parts for k in files), 'invalid model manifest')
    entries=list(root.rglob('*'))
    require(not any(p.is_symlink() for p in entries), 'model symlinks forbidden')
    actual={str(p.relative_to(root)) for p in entries if p.is_file()}
    require(actual==set(files), 'model inventory differs')
    for name, expected in files.items():
        pin(expected); f=path(str(root/name)); require(sha(f)==expected, 'model file hash differs: '+name)
    d=config['dataset']; fields(d, ('path','sha256','count')); dp=path(d['path']); pin(d['sha256'])
    require(type(d['count']) is int and d['count']>0 and sha(dp)==d['sha256'], 'dataset identity differs')
    rows=[json.loads(x, object_pairs_hook=_unique) for x in dp.read_text().splitlines()]; require(len(rows)==d['count'], 'dataset count differs')
    ref=native.reference(SOURCE_ROOT)
    for i, row in enumerate(rows):
        fields(row, ('i','qid','state','question','kind','options') + (() if v2 else ('first_level',)))
        require(type(row['i']) is int and row['i']==i and type(row['qid']) is str and row['qid'] and type(row['state']) is str and type(row['question']) is str and row['question'], 'invalid request')
        require(row['kind'] in ('choice','score','yes_no') and type(row['options']) is list and all(type(x) is str for x in row['options']) and (v2 or (type(row['first_level']) is int and row['first_level'] in (0,1))), 'invalid question')
        ref.make_question(row['question'], row['options'], row['kind'])
    require(len({x['qid'] for x in rows})==len(rows), 'duplicate qid')
    if v2:
        pin(config['image_sha256'])
        panel=config['panel']; fields(panel,('contract','contract_file_sha256','contract_sha256','ordered_requests_sha256','model_sha256'))
        for key in ('contract_file_sha256','contract_sha256','ordered_requests_sha256','model_sha256'): pin(panel[key])
        contract_path=path(panel['contract']); require(sha(contract_path)==panel['contract_file_sha256'],'contract file differs')
        contract=read_json(contract_path)
        fields(contract,('schema','count','items_sha256','source_sha256','model_sha256','runtime_protocol_sha256','tau'))
        require(protocol.sha256_value(contract)==panel['contract_sha256'] and contract['schema']==protocol.PROTOCOL,'contract differs')
        require(contract['count']==len(rows) and type(contract['count']) is int,'contract count differs')
        require(contract['model_sha256']==panel['model_sha256']==native.digest(files),'contract model differs')
        require(contract['runtime_protocol_sha256']==sha(SOURCE_ROOT/'bev_native_runtime.py'),'contract runtime differs')
        require(native.digest(rows)==panel['ordered_requests_sha256'],'ordered requests differ')
        for key in ('items_sha256','source_sha256','model_sha256','runtime_protocol_sha256'): pin(contract[key])
    return rows

def load_tokenizer(config):
    import transformers
    tok=transformers.AutoTokenizer.from_pretrained(config['model']['path'], local_files_only=True, trust_remote_code=False)
    tok.padding_side='left'
    return tok

def load_model(config):
    import torch, torch_npu, transformers
    torch.npu.conv.allow_hf32=False; torch.npu.matmul.allow_hf32=False
    require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32, 'HF32 enabled')
    p=config['model']['path']
    model=transformers.AutoModelForCausalLM.from_pretrained(p, dtype=torch.float32, local_files_only=True, trust_remote_code=False).to('npu:0').eval()
    require(not model.training and all(x.dtype==torch.float32 for x in model.parameters() if x.is_floating_point()), 'model dtype/eval differs')
    return model

def write(p, obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name('.'+p.name+'.pending-'+uuid.uuid4().hex)
    with tmp.open('x') as f:
        json.dump(obj,f,sort_keys=True,ensure_ascii=False,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def read_json(p):
    def unique(pairs):
        d={}
        for k,v in pairs:
            require(k not in d, 'duplicate JSON key'); d[k]=v
        return d
    return json.loads(p.read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def exact(a,b):
    if type(a) is not type(b): return False
    if type(a) is dict: return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
    if type(a) is list: return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b

def fsync_dir(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def validate_record(dest, prepared, identity, ref, contract_sha256=None):
    import numpy as np
    require(dest.is_dir() and not dest.is_symlink(), 'incomplete item')
    receipt=read_json(dest/'COMMITTED.json')
    # Version 1 is read-only compatibility; never convert historical records.
    if set(receipt)=={'record_sha256'}:
        require(contract_sha256 is None, 'v1 item cannot bind panel contract')
        pin(receipt['record_sha256']); require(sha(dest/'record.json')==receipt['record_sha256'], 'item receipt differs')
        record=read_json(dest/'record.json'); fields(record, ('schema','identity','prepared','logits','prediction'))
        require(record['schema']=='nga-native-item-v1', 'item schema differs')
        z=np.asarray(record['logits'],dtype=np.float32)
    else:
        fields(receipt, ('schema','manifest_sha256','logits_sha256'))
        require(receipt['schema']=='nga-native-item-receipt-v2', 'receipt schema differs')
        for k in ('manifest_sha256','logits_sha256'): pin(receipt[k])
        require(sha(dest/'record.json')==receipt['manifest_sha256'] and sha(dest/'logits.npy')==receipt['logits_sha256'], 'item receipt differs')
        record=read_json(dest/'record.json'); fields(record, ('schema','identity','prepared','prediction','logits_file','dtype','shape') + (('contract_sha256',) if contract_sha256 else ()))
        if contract_sha256: require(record['contract_sha256']==contract_sha256, 'item contract differs')
        require(record['schema']==('nga-native-item-v3' if contract_sha256 else 'nga-native-item-v2') and record['logits_file']=='logits.npy' and record['dtype']=='float32' and exact(record['shape'],[248320]), 'item schema differs')
        with (dest/'logits.npy').open('rb') as f:
            z=np.load(f,allow_pickle=False)
            require(f.read(1)==b'', 'trailing logits bytes')
        require(z.dtype==np.dtype('float32'), 'logits dtype differs')
    require(record['identity']==identity and exact(record['prepared'],prepared), 'item identity differs')
    require(z.ndim==1 and len(z)==248320 and np.isfinite(z).all(), 'invalid saved full logits')
    pred=native.read_logits(prepared,z,mode='transformers_full_labels',contract_sha256=contract_sha256 or identity,prepared_sha256=native.digest(prepared),ref=ref)
    require(exact(record['prediction'],pred), 'prediction differs')
    return pred

def commit_item(items, dest, prepared, identity, z, pred, contract_sha256=None):
    import numpy as np
    tmp=items/('.partial-'+dest.name+'-'+uuid.uuid4().hex); tmp.mkdir()
    with (tmp/'logits.npy').open('xb') as f:
        np.save(f,z,allow_pickle=False); f.flush(); os.fsync(f.fileno())
    record=dict(schema='nga-native-item-v3' if contract_sha256 else 'nga-native-item-v2',identity=identity,prepared=prepared,prediction=pred,logits_file='logits.npy',dtype='float32',shape=[248320])
    if contract_sha256: record['contract_sha256']=contract_sha256
    write(tmp/'record.json',record)
    write(tmp/'COMMITTED.json',dict(schema='nga-native-item-receipt-v2',manifest_sha256=sha(tmp/'record.json'),logits_sha256=sha(tmp/'logits.npy')))
    fsync_dir(tmp); require(not dest.exists(), 'duplicate item'); os.rename(tmp,dest); fsync_dir(items)

def export_compact(source, destination, prepared_rows, identity, model_sha256, ref):
    """V1 did not bind a panel contract at inference; do not relabel records."""
    raise ValueError('v1 inference did not bind a panel population contract before inference; compact export is forbidden')


def run(config, output):
    # Establish ownership only after closed configuration and all input admission.
    rows=verify(config); out=path(str(output)); contract_sha256=config['panel']['contract_sha256'] if config['adapter']=='native-full-label-v2' else None
    for p in (path(config['model']['path']),path(config['model']['manifest']),path(config['dataset']['path'])) + ((path(config['panel']['contract']),) if contract_sha256 else ()):
        require(not out.is_relative_to(p) and not p.is_relative_to(out), 'output overlaps input')
    sources={str(p.relative_to(SOURCE_ROOT)):sha(p) for p in [SOURCE_ROOT/'bev_native_runtime.py', *(SOURCE_ROOT/'anyjev'/n for n in sorted(native.PINS))]}
    for name, expected in native.PINS.items(): require(sources['anyjev/'+name]==expected, 'installed AnyJev source differs')
    require(sources['bev_native_runtime.py']=='25e1bd08d3fce43bc4d3b9827188e0329c62289bc7dcf4f12a09e4c37a0ea460', 'installed native source differs')
    identity=native.digest({'config':config,'component_sha256':sha(Path(__file__)),'sources':sources})
    owner={'schema':'nga-native-owner-v1','identity_sha256':identity,'output':str(out)}
    out.parent.mkdir(parents=True,exist_ok=True)
    lockpath=out.parent/(out.name+'.lock'); require(not lockpath.is_symlink(),'unsafe lock')
    with lockpath.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if out.exists(): require(out.is_dir() and (out/'OWNER.json').is_file() and exact(read_json(out/'OWNER.json'),owner), 'output ownership differs')
        else: out.mkdir(); fsync_dir(out.parent); write(out/'OWNER.json',owner)
        rc=1; done=0
        try:
            # Copy evidence before replacing it: a crash at any point retains the
            # previous files or their durable copies, including partial archives.
            previous=[out/n for n in ('EXIT.json','ERROR.json','completion.json','predictions.json') if (out/n).exists()]
            if previous:
                import shutil
                history=out/'attempts'; history.mkdir(exist_ok=True)
                attempt=history/uuid.uuid4().hex; attempt.mkdir()
                for p in previous:
                    with p.open('rb') as src, (attempt/p.name).open('xb') as dst:
                        shutil.copyfileobj(src,dst); dst.flush(); os.fsync(dst.fileno())
                fsync_dir(attempt); fsync_dir(history); fsync_dir(out)
                for p in previous: p.unlink()
                fsync_dir(out)
            items=out/'items'; items.mkdir(exist_ok=True)
            quarantine=out/'quarantine'; quarantine.mkdir(exist_ok=True)
            for p in list(items.iterdir()):
                if p.name.startswith('.partial-') or (p.is_dir() and not (p/'COMMITTED.json').exists()):
                    os.rename(p,quarantine/(p.name+'-'+uuid.uuid4().hex)); fsync_dir(items); fsync_dir(quarantine)
            require(all(p.name in {f'{i:08d}' for i in range(len(rows))} for p in items.iterdir()), 'extra items')
            ref=native.reference(SOURCE_ROOT)
            tok=load_tokenizer(config)
            # Prepare every input and label before loading weights or the first forward.
            prepared_rows=[native.prepare_request(row,tok,ref) for row in rows]
            if contract_sha256: require(all(p['request_sha256']==protocol.request_hash(r) for p,r in zip(prepared_rows,rows)), 'request hash differs')
            require(all(len(p['input_ids'])<=8192 for p in prepared_rows), 'input exceeds registered max; no truncation')
            # Reject every corrupt committed item before any weights are loaded.
            validated={}
            for row, prepared in zip(rows,prepared_rows):
                dest=items/f"{row['i']:08d}"
                if dest.exists(): validated[row['i']]=validate_record(dest,prepared,identity,ref,contract_sha256)
            model=load_model(config) if len(validated)<len(rows) else None
            import numpy as np
            if model is not None: import torch
            reused=0; predictions=[]; receipts=[]
            for row,prepared in zip(rows,prepared_rows):
                dest=items/f"{row['i']:08d}"
                if dest.exists():
                    pred=validated[row['i']]; reused+=1
                else:
                    captured=[]; original=native.read_logits
                    def capture(p,z,**kw):
                        captured.append(np.asarray(z,dtype=np.float32).copy()); return original(p,z,**kw)
                    native.read_logits=capture
                    try:
                        with torch.no_grad():
                            preds=native.read_model_batch(model,[prepared],tok,mode='transformers_full_labels',contract_sha256=contract_sha256 or identity,prepared_pins=[native.digest(prepared)],max_length=8192,ref=ref)
                    finally: native.read_logits=original
                    require(len(captured)==1 and captured[0].shape==(248320,) and np.isfinite(captured[0]).all(), 'invalid full vocabulary')
                    pred=preds[0]; commit_item(items,dest,prepared,identity,captured[0],pred,contract_sha256)
                predictions.append(pred); receipts.append(sha(dest/'COMMITTED.json')); done+=1
                write(out/'heartbeat.json',dict(utc_seconds=time.time(),completed=done,total=len(rows),reused=reused))
            # Native prediction objects are the scoring arithmetic contract; receipt list preserves full-vector provenance.
            write(out/'predictions.json',dict(schema='nga-native-predictions-v1',identity_sha256=identity,predictions=predictions,item_receipt_sha256=receipts))
            result=dict(schema='nga-native-completion-v2',identity_sha256=identity,config_sha256=native.digest(config),completed=done,reused=reused,runtime=config['runtime'],scientific_acceptance=False,predictions_sha256=sha(out/'predictions.json'))
            if contract_sha256: result.update(schema='nga-native-completion-v3',contract_sha256=contract_sha256,model_sha256=config['panel']['model_sha256'],ordered_requests_sha256=config['panel']['ordered_requests_sha256'])
            write(out/'completion.json',result); rc=0
            return result
        except BaseException as e:
            write(out/'ERROR.json',{'error':str(e),'completed':done,'traceback':traceback.format_exc()}); raise
        finally:
            write(out/'EXIT.json',{'exit_code':rc,'identity_sha256':identity,'completed':done,'utc_seconds':time.time()})
