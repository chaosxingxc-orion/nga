"""Record all production-tree bytes and the registered 55-file manifest."""
import hashlib,json,os,stat,sys
from pathlib import Path
root=Path('/opt/nga')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
entries={}
for p in sorted(root.rglob('*')):
    st=p.lstat(); name=str(p.relative_to(root)); item={'mode':stat.S_IMODE(st.st_mode)}
    if p.is_symlink(): item.update(type='link',target=os.readlink(p))
    elif p.is_file(): item.update(type='file',sha256=sha(p))
    elif p.is_dir(): item.update(type='dir')
    else: raise ValueError(str(p))
    entries[name]=item
manifest=json.loads((root/'SOURCE-MANIFEST.json').read_text())
bad=[x['image'] for x in manifest['files'] if sha(Path(x['image']))!=x['sha256']]
assert len(manifest['files'])==55 and not bad
site=Path('/usr/local/python3.12.13/lib/python3.12/site-packages')
fixture={n:(sha(site/n) if (site/n).is_file() else None) for n in ('sitecustomize.py','nga_qualification_fixture.py','trace_store.py')}
Path('/work/audit-'+sys.argv[1]+'.json').write_text(json.dumps({'manifest_files':len(manifest['files']),'manifest_sha256':sha(root/'SOURCE-MANIFEST.json'),'tree':entries,'fixture':fixture},sort_keys=True,indent=2)+'\n')
