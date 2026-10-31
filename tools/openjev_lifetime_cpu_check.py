#!/usr/bin/env python3
"""Fixed-image CPU tensor comparisons; no weights, data labels, or NPU use."""
import argparse
import ast
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def publish(path, value):
    raw=(json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    tmp=path.with_name(path.name+'.pending')
    with tmp.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.link(tmp,path);tmp.unlink()
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def run(root):
    plan=json.loads((root/'PLAN.json').read_bytes())
    ph=sha((root/'PLAN.json').read_bytes())
    for name,digest in plan['files'].items():
        if sha((root/name).read_bytes())!=digest:raise ValueError('Frozen source changed: '+name)
    spec=importlib.util.spec_from_file_location('lifetime_candidate',root/'openjev_lifetime_candidate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import torch
    import torch.nn.functional as F
    # Full transformers import probes NPU integrations even for CPU-only work.
    # Authenticate the installed source, then compile only these two functions.
    installed=importlib.util.find_spec('transformers')
    native_path=Path(installed.origin).parent/'models/qwen3_5/modeling_qwen3_5.py'
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    source=native_path.read_bytes()
    if sha(source)!=module.SOURCE_SHA256:raise ValueError('Installed native source differs')
    tree=ast.parse(source)
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['l2norm',module.FUNCTION]]
    if len(selected)!=2:raise ValueError('Original function extraction differs')
    namespace={'torch':torch,'F':F}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(native_path),'exec'),namespace)
    original=namespace[module.FUNCTION]
    functions={'original':original,**{v:module.build_candidate(source,original,v) for v in module.VARIANTS}}
    items=root/'items';items.mkdir(exist_ok=True)
    def tensor_sha(t):return sha(t.contiguous().view(torch.uint8).numpy().tobytes())
    results=[]
    for i,(dtype_name,heads,length,norm) in enumerate(itertools.product(['float32','bfloat16'],[16,32],[1,63,64,65],[False,True])):
        target=items/(str(i).zfill(3)+'.json')
        if target.exists():
            record=json.loads(target.read_bytes())
            if record['plan_sha256']!=ph or record['index']!=i:raise ValueError('Resume identity differs')
            results.append(record);continue
        torch.manual_seed(plan['seed']+i);dtype=getattr(torch,dtype_name)
        shape=(1,length,heads,128)
        q,k,v=[torch.randn(shape,dtype=dtype)*0.1 for _ in range(3)]
        g=-torch.rand((1,length,heads),dtype=torch.float32)*0.1
        beta=torch.rand((1,length,heads),dtype=dtype)
        inputs=[q,k,v,g,beta];before=[tensor_sha(t) for t in inputs]
        values={};started=time.monotonic()
        with torch.inference_mode():
            for name,fn in functions.items():
                outputs=[]
                for repeat in range(2):
                    output,state=fn(*inputs,chunk_size=64,initial_state=None,output_final_state=False,use_qk_l2norm_in_kernel=norm)
                    if state is not None or not torch.isfinite(output).all() or output.shape!=q.shape or output.dtype!=dtype:
                        raise ValueError('Invalid tensor output')
                    outputs.append(tensor_sha(output))
                values[name]=outputs
        if before!=[tensor_sha(t) for t in inputs]:raise ValueError('Input tensors mutated')
        exact=all(h==values['original'][0] for pair in values.values() for h in pair)
        record=dict(index=i,plan_sha256=ph,dtype=dtype_name,heads=heads,length=length,qk_norm=norm,
                    input_sha256=before,output_sha256=values,exact=exact,seconds=time.monotonic()-started)
        publish(target,record);results.append(record)
        print(json.dumps(dict(utc=time.time(),progress=i+1,total=32,exact=exact)),flush=True)
    expected={str(i).zfill(3)+'.json' for i in range(32)}
    if {p.name for p in items.iterdir()}!=expected:raise ValueError('Item population differs')
    report=dict(plan_sha256=ph,cells=len(results),forwards=len(results)*8,all_exact=all(r['exact'] for r in results),
                torch_version=torch.__version__,native_source_sha256=sha(source),device='cpu',chips=0,
                items={p.name:sha(p.read_bytes()) for p in sorted(items.iterdir())},
                scope='CPU tensor exactness only; no NPU memory, throughput or JEVal admission')
    publish(root/'report.json',report)
    rc=0 if report['all_exact'] else 1
    publish(root/'COMPLETE.json',dict(rc=rc,progress=32,total=32,plan_sha256=ph,report_sha256=sha((root/'report.json').read_bytes())))
    return rc


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:result=run(args.out)
    except BaseException as exc:
        publish(args.out/'FAILED.json',dict(rc=1,error=type(exc).__name__+': '+str(exc)));raise
    raise SystemExit(result)
