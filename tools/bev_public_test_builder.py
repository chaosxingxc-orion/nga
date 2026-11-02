"""Build a frozen, gold-separated BEV numeric_temporal public TEST package."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

E=module(Path(__file__).with_name('experiment_entrypoint.py'),'bev_builder_entry')
A=module(Path(__file__).with_name('bev_public_test_schema.py'),'bev_public_schema')
B=module(Path(__file__).with_name('bev_public_test_bridge.py'),'bev_public_bridge')
SOURCE_SHA='d06e1948260e07f70435fab8435b687fbff3fcae4e7db871b02127aed60416b8'
POP={'choice':3002,'noul':2835,'score':681}
PROTOCOL='bev-local-typed-exact-release-test-v1'


def pin(p):
    p=E.safe(str(p));return {'path':str(p),'sha256':E.digest(p)}


def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write(chr(10))


def jsonl(p,values):
    with Path(p).open('x') as f:
        for value in values:f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+chr(10))


def extract(rows, source_sha):
    """Strict full release enumeration. Never drop a malformed release question."""
    requests=[];gold=[];identities=[]
    for i,row in enumerate(rows):
        E.require(set(row)=={'state','questions_json','question_count','question_types','domain'},'source columns differ')
        E.require(isinstance(row['state'],str) and row['state'].strip(),'invalid state')
        qs=A.strict_json(row['questions_json'])
        E.require(isinstance(qs,dict) and qs and set(qs)!={'questions'},'wrong public TEST question layout')
        E.require(type(row['question_count']) is int and row['question_count']==len(qs),'question_count differs')
        E.require(sorted(set(row['question_types']))==sorted({q['type'] for q in qs.values()}),'question_types differs')
        for name,spec in qs.items():
            E.require(isinstance(name,str) and name,'question key required')
            E.require('label_probs' not in spec,'soft labels unsupported')
            request,g=A.question(spec);request={'input':row['state'],**request};B.to_r3_row(request)
            identifier=A.digest([source_sha,i,name])
            requests.append({'id':identifier,'request':request})
            gold.append({'id':identifier,'type':spec['type'],'gold_index':g})
            identities.append({'id':identifier,'row_index':i,'type':spec['type']})
    E.require(len({r['id'] for r in requests})==len(requests),'duplicate question IDs')
    return requests,gold,identities


def tokenizer_proof(plan,requests,prompt):
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(plan['model'],local_files_only=True,trust_remote_code=False)
    sizes=[]
    for row in requests:
        rendered=prompt.build_prompt(B.to_r3_row(row['request']),render='record_name',input_mode='full')
        prefix=tok(rendered.text,add_special_tokens=False)['input_ids']
        labels=[tok(x,add_special_tokens=False)['input_ids'] for x in rendered.candidates]
        E.require(prefix and all(labels),'empty tokenized input')
        E.require(len(set(tuple(x) for x in labels))==len(labels),'tokenized candidate collision')
        sizes.append(max(len(prefix)+len(x) for x in labels))
    E.require(max(sizes)<=4096,'release requires overlength policy review')
    sizes.sort()
    return {'schema':'bev-public-test-tokenizer-proof-v1','questions':len(requests),'model':plan['model'],
            'prompt_sha256':plan['code']['prompt']['sha256'],'requests_sha256':plan['inputs']['requests']['sha256'],
            'tokenizer_files':{n:v for n,v in plan['model_files'].items() if n in ('config.json','tokenizer.json','tokenizer_config.json','vocab.json','merges.txt')},
            'min':min(sizes),'median':sizes[len(sizes)//2],'p95':sizes[(len(sizes)-1)*95//100],'max':max(sizes),
            'overlength':0,'candidate_collisions':0,'model_scored':False}


def prepare(config_path, expected_sha):
    c=E.read_json(E.pinned({'path':str(config_path),'sha256':expected_sha}))
    required={'schema','template_plan','contract','root','run','container','chip'}
    E.require(set(c) in (required, required|{'resource_adapter'}),'public prepare fields differ')
    resource_override=E.pinned(c['resource_adapter']) if 'resource_adapter' in c else None
    if resource_override is not None:
        E.require(resource_override.name=='r3_resource_adapter.py','resource adapter filename differs')
    E.require(c['schema']=='nga-bev-public-test-prepare-v1','prepare schema differs')
    E.require(type(c['chip']) is int and 0<=c['chip']<8,'invalid chip')
    root=E.safe(c['root']);E.require(not root.exists(),'output already exists')
    E.require(c['run']=='r3_runs/'+root.name and re.fullmatch(r'r3_runs/[A-Za-z0-9_-]+',c['run']),'run identity differs')
    E.require(re.fullmatch(r'nga-[A-Za-z0-9_-]+',c['container']),'invalid container')
    contract_path=E.pinned(c['contract']);contract=E.read_json(contract_path)
    E.require(contract.get('schema')=='nga-public-test-panel-contract-draft-v1' and contract.get('panel')=='BEV/numeric_temporal/release-test','wrong source/split contract')
    source=E.safe(contract['source']['path'])
    E.require(source.name=='test.parquet' and source.parent.name=='numeric_temporal' and contract['source']['sha256']==SOURCE_SHA,'wrong public source/split/hash')
    E.require(E.digest(source)==SOURCE_SHA,'source bytes differ')
    E.require(contract['population']['rows']==3329 and contract['population']['questions']==6518 and contract['population']['by_type']==POP,'public population differs')
    identity_path=E.pinned({'path':contract['population']['ordered_identity_path'],'sha256':contract['population']['ordered_identity_sha256']})
    tp=E.pinned(c['template_plan']);plan=E.read_json(tp)
    E.require(plan['schema']=='bev-dev-plan-v1' and plan['source_split']=='train_derived_dev' and plan['test_read'] is False,'template scope differs')
    for group in ('code','inputs','model_files'):
        for v in plan[group].values():E.pinned(v)
    from pyarrow import parquet
    rows=parquet.read_table(source).to_pylist();requests,gold,identities=extract(rows,SOURCE_SHA)
    E.require(len(rows)==3329 and len(requests)==6518 and dict(Counter(g['type'] for g in gold))==POP,'full population differs')
    E.require(identities==E.read_json(identity_path),'release ordered identities differ')
    E.require(len({json.dumps(x['request'],sort_keys=True,ensure_ascii=False) for x in requests})==6494,'release duplicate population differs')
    E.require(E.digest(source)==SOURCE_SHA,'source changed during build')
    root.mkdir(parents=False)
    try:
        inf=root/'inference';cpu=root/'cpu';control=root/'control'
        for p in (inf,cpu,control,inf/'code',inf/'inputs',inf/'output'):p.mkdir()
        code={}
        for role in ('host','runner','bridge'):
            p=Path(__file__).with_name('bev_public_test_'+role+'.py');dst=inf/'code'/p.name;shutil.copyfile(p,dst);code[role]=pin(dst)
        for role in ('prompt','scorer','resource'):
            p=resource_override if role=='resource' and resource_override is not None else E.pinned(plan['code'][role])
            if role=='resource' and resource_override is not None:E.pinned(c['resource_adapter'])
            dst=inf/'code'/p.name;shutil.copyfile(p,dst);code[role]=pin(dst)
        req=inf/'inputs/requests.jsonl';ids=inf/'inputs/test-ids.json'
        jsonl(req,requests);write(ids,[r['id'] for r in requests]);jsonl(cpu/'gold.jsonl',gold)
        write(cpu/'source-contract.json',contract)
        manifest=inf/'inputs/source-manifest.json'
        write(manifest,{'schema':'bev-public-test-source-v1','scope':'public_release_test','dataset':'avbiswas/bev-decision','config':'numeric_temporal','split':'test','source_sha256':SOURCE_SHA,'recorded_revision':contract['source']['recorded_revision'],'rows':3329,'questions':6518,'by_type':POP,'ordered_ids_sha256':E.digest(ids),'requests_sha256':E.digest(req),'unique_gold_free_requests':6494,'duplicate_questions_preserved':24,'candidate_selection_allowed':False,'native_reproduction':False})
        plan.update(schema='bev-public-test-plan-v1',source_split='public_release_test',test_read=True,selection='all_release_test_ids',expected_questions=6518,expected_by_type=POP,candidate_selection_allowed=False,protocol=PROTOCOL,run=c['run'],container=c['container'],chip=c['chip'],out=str(inf/'output'),code=code,inputs={'requests':pin(req),'ids':pin(ids),'source_manifest':pin(manifest)},source_manifest=pin(manifest),purpose='Complete public numeric_temporal TEST, fixed local typed baseline; not trained-candidate TEST or model selection')
        plan['mounts']=[dict(source=str(inf),destination=str(inf),readonly=True),dict(source=str(inf/'output'),destination=str(inf/'output'),readonly=False),dict(source=plan['model'],destination=plan['model'],readonly=True)]
        prompt=module(code['prompt']['path'],'bev_public_prompt_audit')
        proof=tokenizer_proof(plan,requests,prompt);write(inf/'inputs/tokenizer-proof.json',proof);plan['inputs']['tokenizer_proof']=pin(inf/'inputs/tokenizer-proof.json')
        prereg=inf/'inputs/PREREGISTRATION.md'
        prereg.write_text(f"""# BEV public release TEST — prospective local baseline

Defect4 numerical/ordered interpretation and measurement integrity. Hypothesis: frozen base model admits valid readout on all release questions; actual accuracy may improve, deteriorate, or be at a degenerate baseline. No training-gain, consistency or source-family-generalization claim. Unconstrained optimum may memorize release labels; this is a descriptive public split baseline, not evidence of input-use. No invariance target. Input-use discrimination requires a separately registered control.

Population: numeric_temporal/test.parquet SHA {SOURCE_SHA}; all3329 rows/6518 questions, choice3002/noul2835/score681. Preserve24 duplicate requests as distinct source-row/question IDs. Native AnyJev default TEST is a different population and is not compared.

Protocol: {PROTOCOL}. Neutral r0-prompt-v2 L1..Ln, original criteria order, first maximum wins. Noul true,false; score zero-based order. fp32/rightpad/HF32off/batch8/token_budget16384/max4096. Gold only in CPU sibling, never NPU mounts. No truncation, sampling, retuning, TEST-label oracle, candidate selection or trained-candidate TEST access.

Accuracy correct/full release question denominator by type and optional pooled local question-weighted row. Missing/refused/failed/invalid/overlength remain incorrect. Score valid-only index MAE and valid-only normalized absolute index error report valid and full counts; normalized_error_with_failure_penalty uses full score denominator and penalty1 per failure. Failed/partial lifecycle cannot produce completed benchmark; no acceptance number from a partial run. All6518 valid finite outputs and identity/lifecycle checks required. Zero/one or repeated rates flagged for inspection, no scientific gate.

Detached retained Docker with per-item resume, heartbeat and explicit terminal/resource release. CPU analysis async, machine polling600s, no model polling. Exact model/code/input hashes frozen in plan. Activation requires a new independent exact review, prelaunch publication and current resource guard; preparation is not admission.
""")
        plan['inputs']['preregistration']=pin(prereg)
        pp=inf/'plan.json';write(pp,plan)
        consumer=cpu/'consume.py';shutil.copyfile(Path(__file__).with_name('bev_public_test_consumer.py'),consumer)
        prepcode=cpu/'preparation-code';prepcode.mkdir()
        provenance={}
        for origin in (Path(__file__),Path(A.__file__),Path(B.__file__)):
            target=prepcode/origin.name;shutil.copyfile(origin,target)
            provenance[origin.name]={'maintained_source':pin(origin),'frozen_copy':pin(target)}
        for role in ('prompt','scorer','resource'):
            provenance[role]={'template_source':E.read_json(tp)['code'][role],
                              'selected_source':c['resource_adapter'] if role=='resource' and resource_override is not None else E.read_json(tp)['code'][role],
                              'frozen_copy':plan['code'][role]}
        write(cpu/'CODE-ORIGINS.json',provenance)
        files={str(p):E.digest(p) for p in (consumer,pp,cpu/'gold.jsonl',cpu/'source-contract.json',cpu/'CODE-ORIGINS.json',*prepcode.iterdir())}
        for group in ('code','inputs','model_files'):files.update({x['path']:x['sha256'] for x in plan[group].values()})
        cc={'schema':'bev-public-test-cpu-config-v1','plan':str(pp),'plan_sha256':E.digest(pp),'gold':str(cpu/'gold.jsonl'),'files':files,'poll_interval_seconds':600,'scientific_acceptance':False,'test_read':True,'scope':'public_release_test','candidate_selection_allowed':False}
        cp=cpu/'config.json';write(cp,cc)
        R=module(code['runner']['path'],'bev_public_verify');R.verify(pp,E.digest(pp));R.requests(plan,B)
        C=module(consumer,'bev_public_consumer_verify');C.verify_config(cp,E.digest(cp));C.population(requests,gold,6518)
        receipt=dict(schema='nga-bev-public-test-prepared-v1',config=pin(config_path),template_plan=c['template_plan'],contract=c['contract'],plan=pin(pp),cpu=pin(cp),consumer=pin(consumer),entrypoint=pin(Path(E.__file__)),workflow=pin(Path(__file__).with_name('experiment_workflow.py')),approved=False,scientific_acceptance=False,test_read=True,scope='public_release_test')
        write(root/'PREPARED.json',receipt)
        write(control/'RELAUNCH.json',{'note':'New independent exact review required. No inherited DEV approval. Bind reviewed plan/CPU with experiment_workflow bind, then use activation dry-run/validate/start. No service was started.','prepared':pin(root/'PREPARED.json'),'runner_verify':[sys.executable,'-B','-P',code['runner']['path'],'verify','--plan',str(pp),'--sha256',E.digest(pp)]})
        return {'status':'prepared_requires_new_review','prepared':pin(root/'PREPARED.json'),'population':6518,'npu_started':False}
    except Exception as error:
        write(root/'PREPARE_FAILED.json',{'error':str(error),'exit_code':1});raise


def validate_prepared(path,expected,op='validate'):
    p=E.read_json(E.pinned({'path':str(path),'sha256':expected}))
    E.require(p.get('schema')=='nga-bev-public-test-prepared-v1' and p.get('approved') is False, 'prepared public scope differs')
    for key in ('plan','cpu','consumer','entrypoint','workflow'):E.pinned(p[key])
    E.require(p['entrypoint']==pin(Path(E.__file__)) and p['workflow']==pin(Path(__file__).with_name('experiment_workflow.py')),'workflow version differs')
    plan=E.read_json(E.pinned(p['plan']));R=module(plan['code']['runner']['path'],'bev_public_prepared_runner')
    R.verify(p['plan']['path'],p['plan']['sha256']);R.requests(plan,B)
    cpu=module(p['consumer']['path'],'bev_public_prepared_consumer');cpu.verify_config(p['cpu']['path'],p['cpu']['sha256'])
    E.require(E.read_json(E.pinned(p['cpu']))['plan_sha256']==p['plan']['sha256'],'prepared CPU plan binding differs')
    return {'status':'prepared_validated_requires_new_review' if op=='validate' else 'prepared_dry_run_requires_new_review',
            'writes_performed':False,'activation_authorized':False,'population':6518,
            'runner_verify':[sys.executable,'-B','-P',plan['code']['runner']['path'],'verify','--plan',p['plan']['path'],'--sha256',p['plan']['sha256']],
            'bind_command':[sys.executable,'-B','-P',p['workflow']['path'],'bind','--config',str(path),'--sha256',expected,'--review','<independent-review-path>','--review-sha256','<independent-review-sha256>','--attempt','1']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.config,a.sha256),indent=2))

if __name__=='__main__':main()
