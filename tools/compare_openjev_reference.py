#!/usr/bin/env python3
"""Read-only Open-Jev original-test checkpoint/source binding and aggregate comparison."""
import argparse,ast,hashlib,json,math,os,shutil,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def render_functions(path):
    tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_render','candidate_prompts')]
    assert {n.name for n in nodes}=={'_render','candidate_prompts'}
    scope={'json':json};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return scope['candidate_prompts']
def run(repo,run,join,search_roots):
    ap=repo/'reports/full-data-eval-n1-v1/2b-audit.json';a=json.loads(ap.read_text());c=json.loads((run/'config.json').read_text());jp=json.loads((join/'plan.json').read_text());local=json.loads((join/'report.json').read_text());pin=repo/'reports/full-data-eval-expansion-n1-v1/pinned-source'
    assert a['model']==c['base_id'] and a['revision']==c['base_revision']
    assert a['checkpoint']['temperature']==c['temperature']==local['temperature']
    package=[]
    for name,item in a['package_bound_inference_files'].items():
        p=Path(c['checkpoint'])/Path(name).relative_to('checkpoint');actual=sha(p);assert actual==item['sha256']==c['files'][str(p)]
        package.append(dict(name=name,sha256=actual,bytes=p.stat().st_size))
    data=Path(jp['original_data']);assert sha(data)==a['data_identity']['split_sha256']['test']==local['original_data_sha256'];rows=[json.loads(x) for x in data.read_text().splitlines()]
    assert len(rows)==10532 and len({r['id'] for r in rows})==10532
    source=[]
    for name,expected in a['verification']['implementation_sha256'].items():
        old=pin/name;current=Path(c['code'])/name
        source.append(dict(name=name,upstream_sha256=expected,pinned_path=str(old),pinned_matches=old.is_file() and sha(old)==expected,current_sha256=sha(current) if current.is_file() else None))
    assert all(s['pinned_matches'] for s in source if s['name'].startswith('jev/'))
    old=render_functions(pin/'jev/api.py');new=render_functions(Path(c['code'])/'jev/api.py')
    hashes=[];prompts=0
    for i,row in enumerate(rows):
        lhs,rhs=old(row),new(row);assert lhs==rhs;prompts+=len(lhs)
        hashes.append(dict(index=i,id=row['id'],prompt_sha256=hashlib.sha256(json.dumps(lhs,ensure_ascii=False).encode()).hexdigest()))
    joined=json.loads((join/'joined-records.json').read_text());assert len(joined)==len(rows)
    hard=correct=0
    for i,(row,pred) in enumerate(zip(rows,joined)):
        assert pred['original_index']==i and pred['id']==row['id']
        if max(row['target'])==1:
            hard+=1;correct+=max(range(len(pred['logits'])),key=pred['logits'].__getitem__)==row['target'].index(1)
    upstream=a['metrics']['test']['probability_metrics_all_rows'];ours=local['metrics']['serving'];assert hard==10046 and correct==9507 and math.isclose(correct/hard,ours['accuracy'])
    searches=[];matches=[]
    for root in search_roots:
        if shutil.which('rg'):
            result=subprocess.run(['rg','--files','--hidden','--no-ignore',str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
            paths=result.stdout.splitlines();found=[p for p in paths if Path(p).name=='merged-test.jsonl'];detail=dict(method='rg --files --hidden --no-ignore',returncode=result.returncode,error_count=len(result.stderr.splitlines()),files_listed=len(paths))
        else:
            errors=[];found=[];count=0
            for directory,dirs,files in os.walk(root,onerror=lambda e:errors.append(type(e).__name__)):
                count+=len(files)
                if 'merged-test.jsonl' in files:found.append(str(Path(directory)/'merged-test.jsonl'))
            detail=dict(method='os.walk fallback; no symlink directory recursion',error_count=len(errors),files_listed=count)
        matches+=found;searches.append(dict(root=str(root),exists=root.exists(),matching_paths=found,**detail))
    fields=['accuracy','expected_accuracy','nll','brier','expected_brier','multiclass_ece']
    return dict(status='SCOPED_BINDING_AND_AGGREGATE_COMPARISON',source_hashes={str(p):sha(p) for p in [ap,run/'config.json',join/'report.json',join/'joined-records.json',data,Path(__file__)]},model=c['base_id'],revision=c['base_revision'],temperature=c['temperature'],checkpoint_files=package,source_comparison=source,original_rows=len(rows),candidate_prompt_count=prompts,all_candidate_prompts_equal=True,prompt_identity_sha256=hashlib.sha256(json.dumps(hashes).encode()).hexdigest(),hard_count=hard,local_hard_correct=correct,upstream_hard_correct=round(upstream['accuracy']*hard),hard_correct_delta=correct-round(upstream['accuracy']*hard),metrics={k:dict(upstream=upstream[k],local=ours[k],delta=ours[k]-upstream[k]) for k in fields},upstream_predictions_expected=a['verification']['source_files']['merged-test.jsonl'],upstream_prediction_search=searches,upstream_prediction_matches=matches,limitations=['No upstream per-item predictions located; net -8 correct is not a claim of exactly eight argmax flips.','Source bytes differ. Exact candidate prompts agree for this population; no inference numerical equivalence claim.','Checkpoint binding and prompt equality do not isolate hardware/library/kernel cause.','Original review flags remain unchanged; no Astra approval or new training benefit.'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--join',type=Path,required=True);p.add_argument('--search-root',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();result=run(a.repo,a.run,a.join,a.search_root);a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['status','original_rows','candidate_prompt_count','hard_count','local_hard_correct','upstream_hard_correct','hard_correct_delta','upstream_prediction_matches']}))
