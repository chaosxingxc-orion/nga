"""Fresh-run DEV recovery: authenticate imported prefixes before unchanged scoring."""
import hashlib,json,math,os,types
from pathlib import Path
BASE_SHA='ff4b272a1b2a5f33e83ee922628bed7957ef1afc8180e5d82d0763fd13a8e5c5'
def need(ok,why):
    if not ok:raise RuntimeError(why)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def safe(p):
    p=Path(p);need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in [p,*p.parents]),'unsafe import path');return p

def validate_imports(p):
    ref=p['resume_import'];need(sha(ref['path'])==ref['sha256'],'import manifest changed');m=read(ref['path'])
    need(m['schema']=='r3-dev-imported-prefixes-v1' and m['source_execution']==p['successor_guard']['source_execution'],'import source differs')
    snapshot=safe(m['source_snapshot']['path']);need(snapshot.is_relative_to(Path(p['out'])) and sha(snapshot)==m['source_execution']['sha256']==m['source_snapshot']['sha256'],'source snapshot changed');source=read(snapshot)
    popref=m['population'];need(safe(popref['path']).is_relative_to(Path(p['out'])) and sha(popref['path'])==popref['sha256'],'population changed');pop=read(popref['path']);need(pop['schema']=='r3-dev-resume-population-v1' and pop['test_read']is False,'population scope differs')
    need(m['target_out']==p['out'] and m['source_out']==source['out'] and m['test_read'] is False and m['scientific_acceptance'] is False,'import scope differs')
    seen=set();total=0
    for e in m['entries']:
        rel=Path(e['relative']);need(not rel.is_absolute() and '..' not in rel.parts and str(rel) not in seen and rel.parts[0] in ('trackk','trackt') and rel.suffix=='.jsonl','invalid import name');seen.add(str(rel))
        data=safe(e['data']['path']);receipt=safe(e['receipt']['path']);need(data.is_relative_to(Path(p['out'])/'imported') and receipt.is_relative_to(Path(p['out'])/'imported'),'staging path differs')
        need(sha(data)==e['data']['sha256'] and sha(receipt)==e['receipt']['sha256'],'import bytes changed');r=read(receipt);b=data.read_bytes()
        need(r['path']==str(Path(m['source_out'])/'results'/rel) and r['committed_bytes']==len(b) and r['sha256']==sha(data),'original receipt differs')
        rows=[json.loads(x) for x in b.splitlines()];need(len(rows)==r['rows'] and len({x['k'] for x in rows})==len(rows) and all(x['m']==r['model_sha256'][:16] for x in rows),'rows/keys/stamps differ');total+=len(rows)
        need(r['model_sha256']==m['model_sha256'] and r['scorer']==m['scorer'],'mixed model/scorer')
        need(str(rel) in pop['files'],'unexpected population file')
        expected=pop['files'][str(rel)]
        for row in rows:
            need(row['k'] in expected and {k:v for k,v in row.items() if k not in ('s','p','argmax','tie','m')}==expected[row['k']],'population metadata differs')
            scores=row['s'];need(len(scores)==len(row['ids']) and scores and all(type(x)in(int,float) and math.isfinite(x) for x in scores),'invalid score vector')
            top=max(scores);need(row['tie']==(scores.count(top)>1),'tie differs')
            if 'argmax' in row:need(row['argmax']==scores.index(top),'argmax differs')
            if 'p' in row:
                ex=[math.exp(x-top) for x in scores];z=math.fsum(ex);need(len(row['p'])==len(scores) and all(type(v)in(int,float) and math.isfinite(v) and abs(v-e/z)<=1e-12 for v,e in zip(row['p'],ex)),'probability differs')
    need(len(seen)==m['file_count'] and total==m['rows'] and m['model_sha256']==m['run_identity']['model_sha256'],'import counts differ')
    return m

def materialize(p):
    m=validate_imports(p);root=Path(p['out'])/'results';need(not root.exists(),'fresh recovery results required');root.mkdir()
    for e in m['entries']:
        dst=root/e['relative'];dst.parent.mkdir(parents=True,exist_ok=True)
        with dst.open('xb') as f:f.write(Path(e['data']['path']).read_bytes());f.flush();os.fsync(f.fileno())
        receipt=read(e['receipt']['path']);receipt['path']=str(dst)
        with Path(str(dst)+'.receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True);f.flush();os.fsync(f.fileno())
    with (root/'RUN_IDENTITY.json').open('x') as f:json.dump(m['run_identity'],f,sort_keys=True)
    return {'imported_files':m['file_count'],'imported_rows':m['rows'],'manifest_sha256':p['resume_import']['sha256'],'path_only_receipt_relocation':True,'scientific_acceptance':False}

base=Path(__file__).with_name('base_posttrain_eval_launcher.py');need(sha(base)==BASE_SHA,'original launcher changed')
B=types.ModuleType('resume_base_launcher');B.__file__=str(Path(__file__).resolve());exec(compile(base.read_bytes(),str(base),'exec'),B.__dict__)
original_verify=B.verify;original_drive=B.drive

def verify(path,pin):
    p,s=original_verify(path,pin);need(p['resume_import']['path']==str(Path(p['out'])/'IMPORTS.json'),'manifest location differs');validate_imports(p);return p,s

def drive(path,pin,number):
    need(sha(path)==pin and type(number)is int and number==1,'fresh attempt1 only');p=read(path);need(sha(p['spec'])==p['spec_sha256'],'spec changed')
    try:
        facts=materialize(p);B.atomic(Path(p['out'])/'attempts/1/IMPORT-ACCEPTED.json',facts)
    except BaseException:
        B.atomic(Path(p['out'])/'attempts/1/EXIT.json',{'exit_code':125,'attempt':1,'stage':'import_failed','scientific_acceptance':False});B.atomic(Path(p['out'])/'ENGINEERING_EVAL_EXIT.json',{'exit_code':125,'attempt':1,'stage':'import_failed','scientific_acceptance':False});raise
    return original_drive(path,pin,number)
B.verify=verify;B.drive=drive
for name in ['bind','expected_command','verify_spec','docker_command','resource_module','safe_file','profile','result_directory']:globals()[name]=getattr(B,name)
main=B.main
if __name__=='__main__':raise SystemExit(main())
