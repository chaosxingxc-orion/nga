"""CPU-only K1-QO input-removal contract; no model, test read or approval."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
TRAIN=Path('/mnt/cephfs/xingchao/experiments/jev/KEV/decision-v7/train.jsonl')
MODELS=Path('/mnt/cephfs/xingchao/models/jev')
SENTINEL='NGA_INPUT_ONLY_SENTINEL_7262'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def modules():
    code=ROOT/'experiments/r3_sft/r3_code'
    load('kev_aug',code/'kev_aug.py')
    return load('control_builder',code/'build_kev_sft.py'),load('control_prompt',ROOT/'experiments/r0_baseline/prompt.py')

def check(rows,builder,prompt):
    require(len(rows)==20,'exact twenty training records required')
    require(all(r['split']=='train' for r in rows),'training split required')
    tagged=copy.deepcopy(rows)
    for r in tagged:r['input']=SENTINEL
    counts=[]
    for epoch in (0,1):
        full=builder.epoch_units(tagged,2,epoch,'kev',prompt,False)
        drop=builder.epoch_units(tagged,2,epoch,'kev',prompt,True)
        require(drop==builder.epoch_units(tagged,2,epoch,'kev',prompt,True),'nondeterministic question-only epoch')
        require(len(full)==len(drop)==20,'base population changed')
        count=0
        for a,b in zip(full,drop):
            require(len(a)==len(b),'augmentation sibling population differs')
            for x,y in zip(a,b):
                require(SENTINEL in x['prompt'] and SENTINEL not in y['prompt'],'state not removed')
                expected=x['prompt'].replace('Input:\n'+SENTINEL+'\n\n','',1)
                require(y['prompt']==expected,'removal changed question, options or task')
                require({k:v for k,v in x.items() if k!='prompt'}=={k:v for k,v in y.items() if k!='prompt'},'candidate/gold/provenance changed')
                require('Question: ' in y['prompt'] and 'Options:' in y['prompt'],'question/options missing')
                require(y['response']==y['candidates'][y['gold_index']],'response/gold differs')
                count+=1
        counts.append({'epoch':epoch,'base_questions':20,'examples_checked':count})
    return counts

def architecture():
    paths=[MODELS/n/'config.json' for n in ('Qwen__Qwen3.5-0.8B-Base','Qwen__Qwen3.5-0.8B')]
    a,b=[json.loads(p.read_text()) for p in paths]
    keys=['hidden_size','intermediate_size','num_hidden_layers','num_attention_heads','num_key_value_heads','head_dim','layer_types','linear_conv_kernel_dim','linear_key_head_dim','linear_num_key_heads','linear_num_value_heads','linear_value_head_dim','vocab_size','tie_word_embeddings']
    require(a['architectures']==b['architectures'] and a['model_type']==b['model_type'],'model architecture differs')
    require(all(a['text_config'][k]==b['text_config'][k] for k in keys),'text architecture differs')
    return {'fields':keys,'equal':True,'config_sha256':{str(p):sha(p) for p in paths},'scope':'config structure only; does not verify weights or LoRA construction'}

def run():
    builder,prompt=modules();rows=builder.read_rows(str(TRAIN),20)
    code=ROOT/'experiments/r3_sft/r3_code'
    paths=[TRAIN,code/'train_r3.py',code/'build_kev_sft.py',code/'kev_aug.py',ROOT/'experiments/r0_baseline/prompt.py']
    return {'schema':'r3-control-data-contract-v1','status':'PASS','test_read':False,'scientific_acceptance':False,
            'seed':2,'epochs':check(rows,builder,prompt),'architecture':architecture(),
            'source_sha256':{str(p):sha(p) for p in paths},
            'scope':'twenty train records with input-only sentinel; original augmentation and renderer; CPU only'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args()
    result=run();p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'output':str(p),'status':result['status'],'epochs':result['epochs']}))
