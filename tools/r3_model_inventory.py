"""Full checkpoint-byte inventory for exact-plan admission, no hash cache.

All regular files, including configuration/tokenizer/index files, are bound.
Symlinks and nonregular entries are refused. The inventory is separate from the
legacy LoRA identity, which does not hash base weights. No scientific approval.
"""
import hashlib
import json
from pathlib import Path
import stat


def require(ok,message):
    if not ok:raise ValueError(message)


def tree(root):
    root=Path(root)
    require(root.is_absolute() and '..' not in root.parts
            and not any(p.is_symlink() for p in (root,*root.parents)),'unsafe model root')
    require(root.is_dir(),'model directory missing')
    result={}
    for p in sorted(root.rglob('*')):
        st=p.lstat()
        require(not stat.S_ISLNK(st.st_mode),'model symlink refused')
        require(stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode),'nonregular model entry')
        if stat.S_ISREG(st.st_mode):result[str(p.relative_to(root))]=st
    require(bool(result),'empty model inventory')
    require(any(Path(p).suffix in ('.safetensors','.bin','.pt') for p in result),'no weight files')
    return root,result


def fingerprint(st):
    return st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns


def capture(root):
    root,before=tree(root);files={}
    for rel,st in before.items():
        path=root/rel;h=hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1<<22),b''):h.update(chunk)
        require(fingerprint(path.lstat())==fingerprint(st),'model changed during hashing: '+rel)
        files[rel]={'bytes':st.st_size,'sha256':h.hexdigest()}
    _,after=tree(root)
    require(set(before)==set(after) and all(fingerprint(st)==fingerprint(after[p]) for p,st in before.items()),
            'model inventory changed during hashing')
    return {'schema':'r3-model-byte-inventory-v1','root':str(root),'files':files}


def identity(inventory):
    return hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def verify(root,inventory,pin):
    require(isinstance(pin,str) and len(pin)==64 and identity(inventory)==pin,'model inventory pin differs')
    actual=capture(root)
    require(actual==inventory,'model byte inventory differs')
    return {'files':len(actual['files']),'bytes':sum(v['bytes'] for v in actual['files'].values()),
            'inventory_sha256':pin,'scientific_acceptance':False}
