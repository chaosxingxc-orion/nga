"""Reuse producer-measured identity hashes; this does not approve DEV or training.

load_inventory(pin, source_review_pin), select(inventory, roster_row), and
seed_core_cache(core, round_dir, inventory, rows) form the integration API.
All inputs are bounded paths supplied by the pinned inventory/source config.
"""
import copy, fcntl, hashlib, json, os, re, tempfile
from pathlib import Path

FIELDS=('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')
ADAPTER={'adapter_config.json','adapter_model.safetensors','PUBLICATION.json','BINDING.json'}
BASE_IDS={'q0p8b-base':'08b-k0','q2b-base':'2b-k0','q4b-base':'4b-k0','q9b-base':'9b-k0'}
class PendingIdentity(Exception): pass

def require(ok, msg):
    if not ok: raise ValueError(msg)
def digest(x, ascii=False):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=ascii,allow_nan=False).encode()).hexdigest()
def stat(p):
    s=os.stat(p); return {k:getattr(s,k) for k in FIELDS}
def metadata(pin):
    p=Path(pin['path']); require(p.is_absolute() and p.resolve()==p,'noncanonical metadata path')
    before=stat(p)
    if pin.get('snapshot_stat') is not None: require(before==pin['snapshot_stat'],'metadata stat changed: '+str(p))
    with p.open('rb') as f: data=f.read(8*1024*1024+1)
    require(len(data)<=8*1024*1024,'metadata too large')
    require(stat(p)==before and hashlib.sha256(data).hexdigest()==pin['sha256'],'metadata changed: '+str(p))
    return data
def obj(pin): return json.loads(metadata(pin))
def load_inventory(pin, source_review_pin):
    doc=obj(pin); require(doc.get('schema')=='rc1-identity-reuse-inventory-v1','inventory schema')
    src=doc['source_acceptance']; require({k:src['review'][k] for k in ('path','sha256')}==source_review_pin,'source pin differs')
    review=obj(src['review']); require(review.get('verdict')=='PASS_FOR_MATCHED_CURRENT_DEV_CONSUMPTION','source review refusal')
    metadata(src['manifest']); require(review['source_pins_sha256']==src['manifest']['sha256'],'source manifest differs')
    required=src['checked_required_source_pins']
    for name,p in required.items():
        require(review['files_sha256'].get(name)==p['sha256'],'source pin mismatch'); metadata(p)
    require('config.json' in required,'source config missing')
    cfg=obj(required['config.json'])
    return {'doc':doc,'config':cfg,'pin':pin,'review_pin':source_review_pin}

def select(ctx, row):
    current=load_inventory(ctx['pin'],ctx['review_pin']); require(current['doc']==ctx['doc'],'inventory changed')
    return _select(ctx, row)

def _select(ctx, row):
    doc=ctx['doc']; cfg=ctx['config']; matches=[r for r in doc['roles'] if r['id']==row['id']]
    require(len(matches)==1,'identity row missing or duplicate'); r=matches[0]
    k1=row['id'] not in BASE_IDS
    lane=next((x for x in cfg['lanes'] if x['lane']==row['id']),None) if k1 else None
    require(not k1 or lane is not None,'lane missing')
    mid=lane['baseline_id'] if k1 else BASE_IDS[row['id']]
    models=[x for x in cfg['models'] if x['id']==mid]; require(len(models)==1,'model missing')
    m=models[0]; base=m['model']['path']; adapter=lane['new_adapter'] if k1 else None
    require(row.get('arm')==r['arm']==('K1' if k1 else 'K0') and row.get('size')==row['id'].split('-')[0], 'role or size differs')
    require(r['size']==m['size'] and (not k1 or lane['size']==m['size']),'source size differs')
    require(row.get('model')==r['model']==base and row.get('adapter')==r['adapter']==adapter,'model path differs')
    require(Path(base).is_absolute() and str(Path(base).resolve())==base and (not adapter or str(Path(adapter).resolve())==adapter),'noncanonical model path')
    require(row.get('seed')==r['seed']==(lane['seed'] if k1 else None) and row.get('terminal_step')==r['terminal_step']==(3116 if k1 else None),'seed or terminal differs')
    if r['identity'] is None: raise PendingIdentity(row['id'])
    metadata(r['base_inventory']); require(r['base_inventory']['sha256']==ctx['doc']['source_acceptance']['checked_required_source_pins']['config.json']['sha256'],'config pin differs')
    metadata(r['base_revision_receipt'])
    require(r['base_revision_receipt']['path']==str(Path(base)/'.complete') and m['asset_pins'][r['base_revision_receipt']['path']]==r['base_revision_receipt']['sha256'],'base revision receipt differs')
    identity=r['identity']; files=identity['files']; revision=m['model']['base_revision']
    require(revision!='unknown' and identity['base_revision']==revision and identity['base_path']==base and identity['path']==(adapter or base),'identity paths/revision differ')
    if k1:
        require(identity['kind']=='lora-adapter-unmerged' and set(files)==ADAPTER and set(os.listdir(adapter))==ADAPTER,'adapter inventory differs')
        require(r['publication']['path']==str(Path(adapter)/'PUBLICATION.json') and r['lineage']['binding']['path']==str(Path(adapter)/'BINDING.json') and r['lineage']['adapter_config']['path']==str(Path(adapter)/'adapter_config.json') and r['lineage']['owner']['path']==str(Path(adapter).parent/'OWNER.json'),'publication receipt path differs')
        require(all(r['training_receipts'][name]['path']==str(Path(adapter).parent.parent/name) for name in ('COMPLETE.json','smoke.json','train.json','smoke-LAUNCH.json','train-LAUNCH.json','smoke-EXIT.json','train-EXIT.json')),'training receipt path differs')
        pub=obj(r['publication']); binding=obj(r['lineage']['binding']); owner=obj(r['lineage']['owner']); obj(r['lineage']['adapter_config'])
        require(pub['binding']==binding and binding['owner']==owner['owner']=='rc1-functional-'+row['id'],'publication owner differs')
        require(digest(owner['identity'],True)==binding['identity_sha256'] and owner['identity']['seed']==row['seed'] and owner['identity']['model_revision']==revision,'training identity differs')
        require(pub['files']=={k:files[k] for k in ('adapter_config.json','adapter_model.safetensors')} and r['publication']['sha256']==files['PUBLICATION.json'] and r['lineage']['binding']['sha256']==files['BINDING.json'] and r['lineage']['adapter_config']['sha256']==files['adapter_config.json'],'publication hashes differ')
        tr=r['training_receipts']; complete=obj(tr['COMPLETE.json']); require(complete=={'exit_code':0,'steps':3116,'scientific_acceptance':False},'terminal differs')
        for phase in ('smoke','train'):
            config=obj(tr[phase+'.json']); launch=obj(tr[phase+'-LAUNCH.json']); ex=obj(tr[phase+'-EXIT.json'])
            require(config['seed']==row['seed'] and config['owner']==owner['owner'] and launch['config_sha256']==tr[phase+'.json']['sha256'] and ex['container_id']==launch['container_id'] and ex['exit_code']==0 and ex['image']==cfg['image'],'training receipts differ')
        require(config['resume']['sha256']==r['lineage']['smoke_resume_sha256'] and binding['checkpoint_sha256']==r['lineage']['terminal_checkpoint_sha256'],'lineage differs')
        canonical={'kind':'lora-adapter-unmerged','adapter_files':files,'base_revision':revision,'base_path':base}
    else:
        require(identity['kind']=='checkpoint' and files==m['weight_shard_pins'],'base inventory differs')
        require(obj(r['own_dev']['inference_ready'])['identity']==identity,'producer identity differs')
        canonical={'kind':'checkpoint','weight_files':files,'revision':revision}
    require(digest(canonical)==identity['sha256']==r['identity_sha256']==row.get('identity_sha256'),'canonical identity differs')
    run=obj(r['own_dev']['run_identity']); require(run['model_sha256']==identity['sha256'] and run['model_path']==identity['path'] and run['arm']==r['arm'],'run identity differs')
    runroot=Path(cfg['adapter_root'])/('full-'+row['id']) if k1 else Path(cfg['k0_root'])/mid
    require(r['identity_cache']['path']==str(runroot/'result/identity-cache/.model_hash_cache.json') and r['own_dev']['run_identity']['path']==str(runroot/'result/RUN_IDENTITY.json'),'producer receipt path differs')
    if not k1: require(r['own_dev']['inference_ready']['path']==str(runroot/'result/INFERENCE-READY.json'),'readiness path differs')
    cache=obj(r['identity_cache']); entries=r['reusable_hash_entries']; require(len(entries)==len(files),'hash entries missing')
    seen=set()
    for entry in entries:
        p=entry['path']; name=Path(p).name
        require(name in files and name not in seen and p==str(Path(identity['path'])/name),'hash entry path differs'); seen.add(name)
        s=stat(p); require(s==entry['stat'],'identity input changed')
        key=f"{p}|{s['st_size']}|{s['st_mtime_ns']}"
        require(entry['legacy_key']==key and cache.get(key)==entry['sha256']==files[name] and re.fullmatch('[0-9a-f]{64}',entry['sha256']) is not None,'producer hash differs')
    return identity

def seed_core_cache(core, round_dir, ctx, rows):
    rd=Path(round_dir); rd.mkdir(parents=True,exist_ok=True)
    with (rd/'cpu-readiness-hashes.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=rd/'cpu-readiness-hashes.json'; cache=core.read(path) if path.exists() else {}
        # Revalidate every selected receipt under the actual core lock, then again
        # before save so ordinary concurrent mutation refuses rather than seeds.
        current=load_inventory(ctx['pin'],ctx['review_pin']); require(current['doc']==ctx['doc'],'inventory changed')
        for row in rows:
            _select(ctx,row)
            r=next(x for x in ctx['doc']['roles'] if x['id']==row['id'])
            for e in r['reusable_hash_entries']:
                s=stat(e['path']); key=json.dumps([str(Path(e['path']).resolve()),*(s[k] for k in FIELDS)])
                require(key not in cache or cache[key]==e['sha256'],'existing core cache conflict')
                cache[key]=e['sha256']
        current=load_inventory(ctx['pin'],ctx['review_pin']); require(current['doc']==ctx['doc'],'inventory changed')
        for row in rows: _select(ctx,row)
        core.save(path,cache)


def _capture(path):
    p=Path(path)
    require(p.is_absolute() and p.resolve()==p, 'noncanonical receipt path')
    before=stat(p)
    with p.open('rb') as f: data=f.read(8*1024*1024+1)
    require(len(data)<=8*1024*1024 and stat(p)==before, 'receipt changed: '+str(p))
    return {'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),
            'snapshot_stat':before,'exists':True,'hash_origin':'bounded refresh metadata'}, json.loads(data)

def _roster(r):
    return {'id':r['id'],'arm':r['arm'],'size':r['id'].split('-')[0],
            'seed':r['seed'],'terminal_step':r['terminal_step'],'model':r['model'],
            'adapter':r['adapter'],'identity_sha256':r['identity_sha256']}

def refresh_inventory(inventory_pin, source_review_pin, output_path):
    """Write one immutable new inventory generation; return its path/SHA pin.

    Read only the fixed receipt paths derived from the reviewed config. Missing
    receipts leave a role pending; inconsistent present complete chains fail.
    The output path must be new. No payload contents are read.
    """
    ctx=load_inventory(inventory_pin,source_review_pin)
    doc=copy.deepcopy(ctx['doc']); cfg=ctx['config']; changed=[]
    for r in doc['roles']:
        if r['identity'] is not None: continue
        lane=next((x for x in cfg['lanes'] if x['lane']==r['id']),None)
        require(lane is not None and r['arm']=='K1', 'pending role is not configured adapter')
        models=[m for m in cfg['models'] if m['id']==lane['baseline_id']]
        require(len(models)==1, 'model missing'); m=models[0]
        adapter=Path(lane['new_adapter']); base=m['model']['path']; root=adapter.parent.parent
        runroot=Path(cfg['adapter_root'])/('full-'+r['id'])/'result'
        paths={'publication':adapter/'PUBLICATION.json','binding':adapter/'BINDING.json',
               'adapter_config':adapter/'adapter_config.json','owner':adapter.parent/'OWNER.json',
               'run':runroot/'RUN_IDENTITY.json','cache':runroot/'identity-cache/.model_hash_cache.json'}
        names=('COMPLETE.json','smoke.json','train.json','smoke-LAUNCH.json','train-LAUNCH.json','smoke-EXIT.json','train-EXIT.json')
        paths.update({n:root/n for n in names})
        try:
            captures={k:_capture(p) for k,p in paths.items()}
            payload_stat={n:stat(adapter/n) for n in ADAPTER}
        except FileNotFoundError:
            continue
        pin=lambda k:captures[k][0]
        val=lambda k:captures[k][1]
        # Existing non-null training pins are part of the parent generation.
        for n, previous in (r.get('training_receipts') or {}).items():
            if n in captures and previous.get('sha256'):
                require(previous['path']==str(paths[n]) and previous['sha256']==pin(n)['sha256'] and (previous.get('snapshot_stat') is None or previous['snapshot_stat']==pin(n)['snapshot_stat']), 'existing training receipt changed: '+n)
        pub=val('publication'); binding=val('binding'); train=val('train.json')
        files={**pub['files'],'PUBLICATION.json':pin('publication')['sha256'],'BINDING.json':pin('binding')['sha256']}
        require(set(files)==ADAPTER, 'publication files differ')
        revision=m['model']['base_revision']
        ident={'path':str(adapter),'kind':'lora-adapter-unmerged','base_path':base,'base_revision':revision,'files':files,
               'sha256':digest({'kind':'lora-adapter-unmerged','adapter_files':files,'base_revision':revision,'base_path':base})}
        entries=[]
        for n in sorted(ADAPTER):
            p=str(adapter/n); st=payload_stat[n]; key=f"{p}|{st['st_size']}|{st['st_mtime_ns']}"
            entries.append({'path':p,'stat':st,'legacy_key':key,'sha256':files[n],
                            'hash_origin':'existing producer cache, copied without payload read'})
        r.update(identity=ident,identity_sha256=ident['sha256'],identity_cache=pin('cache'),
                 reusable_hash_entries=entries,publication=pin('publication'),
                 lineage={'owner':pin('owner'),'binding':pin('binding'),'adapter_config':pin('adapter_config'),
                          'training_identity_sha256':binding['identity_sha256'],
                          'terminal_checkpoint_sha256':binding['checkpoint_sha256'],
                          'smoke_resume_sha256':train['resume']['sha256'],
                          'hash_origin':'inherited producer metadata; checkpoint bytes not read'},
                 training_receipts={n:pin(n) for n in names},
                 inventory_status='IDENTITY_ONLY_DEV_PENDING',
                 identity_reuse_basis='actual producer cache, canonical digest and RUN_IDENTITY',
                 next_action='reuse identity; own DEV and any required deep validation remain separate')
        r['own_dev']['run_identity']=pin('run')
        changed.append(r)
    # Validate constructed rows against the same source and all live receipts twice.
    fresh={'doc':doc,'config':cfg}
    for r in changed: _select(fresh,_roster(r))
    current=load_inventory(inventory_pin,source_review_pin)
    require(current['doc']==ctx['doc'],'inventory changed during refresh')
    for r in changed: _select(fresh,_roster(r))
    if 'counts' in doc:
        doc['counts']['published_identity_reusable']=sum(r['identity'] is not None for r in doc['roles'])
        doc['counts']['current_identity_pending']=sum(r['identity'] is None for r in doc['roles'])
        doc['counts']['identity_only_dev_pending']=sum(r.get('inventory_status')=='IDENTITY_ONLY_DEV_PENDING' for r in doc['roles'])
    doc['refresh_generation']={'parent_inventory':inventory_pin,'source_review':source_review_pin,
                               'updated_roles':[r['id'] for r in changed],
                               'scope':'metadata identity reuse; no deep validation or DEV approval'}
    data=(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    out=Path(output_path); require(out.is_absolute() and out.resolve()==out,'noncanonical output path')
    # Link a completed same-directory temporary file without replacing a generation.
    fd, tmp=tempfile.mkstemp(prefix='.identity-refresh-', dir=out.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.link(tmp,out)
    finally:
        os.unlink(tmp)
    return {'path':str(out),'sha256':hashlib.sha256(data).hexdigest()}
