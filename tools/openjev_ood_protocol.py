#!/usr/bin/env python3
"""Exact original OOD population; no public projection or renamed test rows."""
from collections import Counter
import hashlib,json
from pathlib import Path
OOD_SHA='9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee'
def require(v,m):
    if not v:raise ValueError(m)
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()
def validate_dataset(c,rows):
    require(c['expected_split']=='ood' and c['expected_rows']==15920 and len(rows)==15920,'Wrong OOD population')
    require(sha(c['data'])==OOD_SHA,'Original OOD data hash differs')
    require(all(r['split']=='ood' for r in rows) and len({r['id'] for r in rows})==15920,'Wrong OOD identity')
    require(sum(max(r['target'])==1 for r in rows)==c['hard_count']==15446,'Hard denominator differs')
    restoration=json.loads(Path(c['restoration_report']).read_text())
    require(restoration['status']=='RESTORED_EXACT_ORIGINAL' and restoration['splits']['ood']=={'count':15920,'sha256':OOD_SHA},'Restoration binding differs')
    for k in ['restoration_report','parent_config']:
        require(c['files'].get(str(Path(c[k]).resolve()))==sha(c[k]),'Unfrozen OOD dependency '+k)
    parent=json.loads(Path(c['parent_config']).read_text())
    require(sha(c['parent_config'])==c['parent_config_sha256'],'Parent configuration changed')
    for k in ['image','base_id','base_revision','max_length','temperature']:
        require(c[k]==parent[k],'Parent native protocol changed '+k)
    for role in ['base','checkpoint','code']:
        require(c[role]==parent[role],'Parent native source path changed')
        root=Path(c[role])
        for p in root.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                path=str(p.resolve());require(c['files'].get(path)==parent['files'].get(path)==sha(p),'Parent native dependency changed')
    model=json.loads(Path(c['checkpoint'],'model.json').read_text())
    require((model['model_id'],model['revision'],model['max_length'])==(c['base_id'],c['base_revision'],4096),'Checkpoint protocol differs')
    return dict(count=15920,raw_uncompressed_sha256=OOD_SHA,sources=dict(Counter(r['source'] for r in rows)),kinds=dict(Counter(r['kind'] for r in rows)))
