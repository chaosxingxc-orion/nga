"""DEV-only native readout equivalence operand collector; no host launch authority.

Public helpers are used by a future reviewed detached host runner. The CLI only
verifies a frozen diagnostic plan; it cannot claim an NPU or launch a container.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import types
from typing import List


def require(ok, why):
    if not ok: raise ValueError(why)


def sha(path):
    p=Path(path)
    require(p.is_absolute() and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe source path')
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()


def pinned(ref):
    require(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'], 'source pin changed')
    return Path(ref['path'])


def module(ref):
    p=pinned(ref); spec=importlib.util.spec_from_file_location('native_probe_runtime',p)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def upstream_engine(source, expected, ref):
    """Only execute the pinned __init__/read AST, never downloaded imports."""
    require(sha(source)==expected,'upstream source changed')
    tree=ast.parse(Path(source).read_bytes())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TransformersEngine')
    selected=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('__init__','read')]
    require(len(selected)==2,'upstream engine interface changed')
    ns={'List':List,'np':__import__('numpy'),'restricted_logprobs':ref.restricted_logprobs}
    code=ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name=cls.name,bases=[],keywords=[],body=selected,decorator_list=[])],type_ignores=[]))
    exec(compile(code,str(source),'exec'),ns)
    return ns['TransformersEngine']


def validate_items(items, runtime, expected):
    require(len(items)==72 and len(expected)==72,'DEV72 population required')
    require([runtime.digest(x) for x in items]==expected,'input population/order changed')
    require(len({(x['i'],x['qid']) for x in items})==72,'duplicate diagnostic identity')
    from collections import Counter
    require(Counter(x['kind'] for x in items)=={'choice':24,'noul':24,'score':24},'native type population changed')
    allowed={'schema','i','qid','request_sha256','input_ids','rendered_prompt','labels','label_ids','options','kind'}
    for row in items:
        require(set(row)==allowed and row['schema']=='bev-native-input-v1','gold/foreign input fields')
        require(type(row['i']) is int and row['i']>=0 and isinstance(row['qid'],str),'input identity differs')
        require(0<len(row['input_ids'])<=4096 and all(type(x) is int and x>=0 for x in row['input_ids']),'input length/token differs')
        require(len(row['label_ids'])==len(set(row['label_ids']))==len(row['options'])>=2,'label identity differs')


def verify(path, pin):
    require(sha(path)==pin,'plan changed');d=json.loads(Path(path).read_text())
    require(d['schema']=='bev-native-dev-probe-v1' and d['activation_authorized'] is False
            and d['test_read'] is False and d['scientific_acceptance'] is False,'scope differs')
    require(d['source_split']=='train_derived_dev' and d['batch_size']==1 and d['max_length']==4096
            and d['dtype']=='float32' and d['hf32'] is False and d['padding_side']=='left'
            and d['mode']=='transformers_full_labels' and d['tolerance']==0,'numerical protocol differs')
    require(d['passes']==['reference','reference_repeat','adapter'],'operand passes differ')
    for ref in d['files'].values():pinned(ref)
    R=module(d['runtime']);p=pinned(d['inputs']);doc=json.loads(p.read_text());items=doc['items']
    require(doc['selection']=='first24 per native kind in TRAIN order; no model outputs'
            and doc['test_read'] is False,'DEV provenance differs')
    validate_items(items,R,d['ordered_input_sha256'])
    require(Path(d['model']).name=='Qwen__Qwen3.5-0.8B-Base','model family differs')
    require({p.name for p in Path(d['model']).iterdir() if p.is_file()}==set(d['model_files']),'model inventory changed')
    for name,ref in d['model_files'].items():require(pinned(ref)==Path(d['model'])/name,'model path differs')
    return d,items,R


class CaptureModel:
    """Capture actual model operands; transparent forwarding, no alternate forward."""
    def __init__(self, model):self.model=model;self.calls=[]
    @property
    def device(self):return self.model.device
    def __call__(self, **kw):
        require(set(kw)=={'input_ids','attention_mask','logits_to_keep'} and kw['logits_to_keep']==1,'unregistered forward inputs')
        out=self.model(**kw)
        self.calls.append(dict(input_ids=kw['input_ids'].detach().cpu().numpy().copy(),
                               attention_mask=kw['attention_mask'].detach().cpu().numpy().copy(),
                               logits=out.logits[:,-1,:].detach().float().cpu().numpy().copy()))
        return out


def collect_one(model,tokenizer,item,R,ref,engine,contract_pin,variant):
    """One real forward per diagnostic row; strict exact equality is external."""
    import numpy as np
    require(variant in ('reference','reference_repeat','adapter'),'unknown variant')
    require(tokenizer.padding_side=='left' and tokenizer.encode(item['rendered_prompt'],add_special_tokens=False)==item['input_ids'],'tokenizer input differs')
    capture=CaptureModel(model)
    if variant=='adapter':
        prediction=R.read_model_batch(capture,[item],tokenizer,mode='transformers_full_labels',contract_sha256=contract_pin,prepared_pins=[R.digest(item)],max_length=4096,ref=ref)[0]
        lp=np.asarray(prediction['restricted_logprobs'])
    else:
        lp=engine(capture,tokenizer).read([item['rendered_prompt']],[item['label_ids']])[0]
        require(len(capture.calls)==1,'reference did not perform one forward')
        prediction=R.read_logits(item,capture.calls[0]['logits'][0],mode='transformers_full_labels',contract_sha256=contract_pin,prepared_sha256=R.digest(item),ref=ref)
        require(np.array_equal(lp,np.asarray(prediction['restricted_logprobs'])),'upstream label read differs')
    require(len(capture.calls)==1,'readout did not perform one forward')
    value=capture.calls[0]
    require(value['input_ids'].tolist()==[item['input_ids']] and value['attention_mask'].tolist()==[[1]*len(item['input_ids'])],'actual input differs')
    require(np.isfinite(value['logits']).all(),'nonfinite vocabulary')
    return value,dict(prediction=prediction,restricted_logprobs=lp.tolist(),variant=variant,forwards=1)


def compare_operands(left,right,left_result,right_result):
    import numpy as np
    require(set(left)==set(right)=={'input_ids','attention_mask','logits'},'operand set differs')
    for key in left:require(left[key].dtype==right[key].dtype and np.array_equal(left[key],right[key]),key+' differs')
    require(left_result['prediction']==right_result['prediction'] and left_result['restricted_logprobs']==right_result['restricted_logprobs'],'native output differs')


def persist_operand(directory,arrays,result):
    """Publish complete operands before comparing; immutable partials are not success."""
    import numpy as np
    root=Path(directory);root.mkdir(parents=True,exist_ok=False)
    with (root/'operands.npz').open('xb') as f:np.savez(f,**arrays);f.flush();os.fsync(f.fileno())
    with (root/'result.json').open('x') as f:json.dump(result,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    value={name:sha(root/name) for name in ('operands.npz','result.json')}
    with (root/'COMMITTED.json').open('x') as f:json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return value


if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('op',choices=['verify']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args()
    d,items,R=verify(a.plan,a.sha256)
    print(json.dumps(dict(status='NATIVE_DEV_CPU_PLAN_VERIFIED',items=len(items),npu_started=False,activation_authorized=False)))
