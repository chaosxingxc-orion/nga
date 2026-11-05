"""Registered K1 training component. Lifecycle and accelerator ownership belong to caller."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid
from typing import Any, TypedDict

SOURCE = Path('/opt/nga/source/train')
PINS = {'train_r3.py':'044ad70d14a6511816066407986e075bb02be0cb86eb0e0a47225f33161d9e18', 'build_kev_sft.py':'356da5eb4667eb9c3349e26b088b2bd0fac5cd30acea548a3d92bed2adcf0b98','kev_aug.py':'696da28b06a7e902197806bfb4969586ee050877e93e49a744e7a1df4ebf4542','r0_code/prompt.py':'84c99aec2817de3365e650c7c6c846aeddc1ec675b3321cf80be267a7557f0fc'}
DATA_SHA = '5ddc8e94f3e0af1c8abdb887ed77c1e8813879efcc428edc6d4ea0bed537daf6'
class Config(TypedDict):
    adapter: str
    seed: int
    owner: str
    model: dict[str, str]
    dataset: dict[str, str]
    resume: dict[str, str] | None


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def canonical(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def verify_manifest(root: Path, manifest: Path, expected: str) -> dict:
    if not root.is_absolute() or not manifest.is_absolute() or sha(manifest) != expected: raise ValueError('manifest identity mismatch')
    obj = json.loads(manifest.read_text())
    files = obj['files']
    if not isinstance(files, dict) or not files: raise ValueError('empty manifest')
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if actual != set(files): raise ValueError('manifest file set mismatch')
    for name, digest in files.items():
        p = root / name
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or sha(p) != digest: raise ValueError('manifest content mismatch: '+name)
    return obj

def validate_state(st: dict, identity: dict, total: int) -> int:
    if not isinstance(st, dict): raise ValueError('invalid checkpoint state')
    if st.get('identity') != identity: raise ValueError('checkpoint identity mismatch')
    step = st.get('step')
    if type(step) is not int or not 0 < step <= total: raise ValueError('invalid checkpoint step')
    if not isinstance(st.get('lora'), dict) or not st['lora']: raise ValueError('missing LoRA')
    opt, sched = st.get('opt'), st.get('sched')
    if not isinstance(opt, dict) or not isinstance(sched, dict): raise ValueError('missing optimizer or scheduler')
    if sched.get('last_epoch') != step or sched.get('total_steps') != total: raise ValueError('scheduler step mismatch')
    states = opt.get('state', {})
    params = [x for g in opt.get('param_groups', []) for x in g['params']]
    if not params or set(states) != set(params): raise ValueError('optimizer state incomplete')
    if any(int(s['step'].item() if hasattr(s['step'], 'item') else s['step']) != step or 'exp_avg' not in s or 'exp_avg_sq' not in s for s in states.values()): raise ValueError('optimizer step mismatch')
    return step

def save_checkpoint(torch, out: str, step: int, trainable, opt, sched, identity: dict, total: int) -> None:
    d = Path(out)/'ckpt'; d.mkdir(exist_ok=True)
    st = {'step':step, 'lora':{n:p.detach().cpu() for n,p in trainable}, 'opt':opt.state_dict(), 'sched':sched.state_dict(), 'identity':identity}
    validate_state(st, identity, total)
    tmp = d / ('.partial-'+str(step)); dest = d / f'step_{step:06d}.pt'
    if dest.exists() or any(d.glob('.partial-*')): raise ValueError('checkpoint already exists or partial remains')
    with tmp.open('xb') as f:
        torch.save(st, f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,dest)
    fd=os.open(d,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def checked_checkpoint(torch, output: Path, resume: dict, identity: dict, total: int) -> Path:
    if not isinstance(resume, dict) or set(resume) != {'path', 'sha256'}: raise ValueError('invalid resume')
    path = Path(resume['path'])
    if any((output/'ckpt').glob('.partial-*')): raise ValueError('partial checkpoint remains')
    if path.parent != output/'ckpt' or not re.fullmatch(r'step_\d{6}\.pt', path.name) or path.is_symlink(): raise ValueError('checkpoint outside owned output')
    if sha(path) != resume['sha256']: raise ValueError('checkpoint digest mismatch')
    try: st = torch.load(path, map_location='cpu', weights_only=True)
    except Exception as e: raise ValueError('invalid checkpoint') from e
    if validate_state(st, identity, total) != int(path.stem[5:]): raise ValueError('checkpoint filename mismatch')
    return path

def claim_owner(out: Path, identity: dict, resume: bool) -> None:
    owner = out / 'OWNER.json'
    if resume:
        if owner.is_symlink() or json.loads(owner.read_text()) != identity: raise ValueError('output owner mismatch')
    else:
        if any(out.iterdir()): raise ValueError('fresh output must be empty')
        with owner.open('x') as f:
            json.dump(identity, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        fd = os.open(out, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

def verify_source(root: Path = SOURCE) -> None:
    for name, pin in PINS.items():
        if (root/name).is_symlink() or sha(root/name) != pin: raise ValueError('installed trainer source mismatch: '+name)

def run(config: Config, output: str) -> dict:
    import jsonschema
    schema = json.loads((Path(__file__).parent/'schema-fragment.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(config)
    out=Path(output)
    if not out.is_absolute() or out.is_symlink(): raise ValueError('output must be an absolute owned directory')
    # The caller owns the lifecycle and supplies a private output; never infer a resume.
    if not out.is_dir(): raise ValueError('caller must create output directory')
    model=config['model']; dataset=config['dataset']
    registered=json.loads((Path(__file__).parent/'full-model-manifest.json').read_text())
    obj=verify_manifest(Path(model['path']),Path(model['manifest']),model['manifest_sha256'])
    if obj != registered: raise ValueError('model is not registered full model')
    if sha(Path(dataset['manifest'])) != dataset['manifest_sha256']: raise ValueError('dataset manifest mismatch')
    dm=json.loads(Path(dataset['manifest']).read_text())
    if dm != {'id':'decision-v7-train','sha256':DATA_SHA} or sha(Path(dataset['path'])) != DATA_SHA: raise ValueError('dataset content mismatch')
    verify_source()
    identity={'owner':config['owner'],'output':str(out),'adapter':config['adapter'],'seed':config['seed'],'model_manifest_sha256':model['manifest_sha256'],'dataset_manifest_sha256':dataset['manifest_sha256'],'dataset_sha256':DATA_SHA,'recipe':'k1-08b-full-3116-v1','source':PINS,'config_sha256':canonical({k:v for k,v in config.items() if k != 'resume'}),'component_sha256':sha(Path(__file__))}
    import torch
    resume=config['resume']
    claim_owner(out, identity, resume is not None)
    ck=checked_checkpoint(torch,out,resume,identity,3116) if resume else None
    if ck and int(ck.stem[5:]) == 3116: raise ValueError('checkpoint already completed')
    # Only installed, pinned modules, never output/model/dataset paths on sys.path.
    sys.path.insert(0,str(SOURCE)); os.environ['NGA_R0_CODE']=str(SOURCE/'r0_code')
    os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','PYTORCH_NPU_ALLOC_CONF':'expandable_segments:True','TASK_QUEUE_ENABLE':'2'})
    for module in ('build_kev_sft', 'kev_aug', 'prompt'):
        sys.modules.pop(module, None)
    spec=importlib.util.spec_from_file_location('nga_registered_trainer',SOURCE/'train_r3.py'); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
    t.TRAIN_FILE=dataset['path']
    t.latest_ckpt=lambda _: str(ck) if ck else None
    t.save_ckpt=lambda torch_,out_,step,trainable,opt,sched,keep=2: save_checkpoint(torch_,out_,step,trainable,opt,sched,identity,3116)
    original_data=t.Data
    class CheckedData(original_data):
        def steps_per_epoch(self):
            value = super().steps_per_epoch()
            if value != 1558: raise ValueError('dataset epoch length does not match registered recipe')
            return value
    t.Data=CheckedData
    original_build=t.build_model
    def checked_build(args, torch_):
        result=original_build(args, torch_)
        if ck:
            state=torch_.load(ck, map_location='cpu', weights_only=True)['lora']
            trainable=dict(result[1])
            if set(state) != set(trainable) or any(state[n].shape != p.shape or state[n].dtype != p.dtype for n,p in trainable.items()): raise ValueError('checkpoint trainable tensors mismatch')
        return result
    t.build_model=checked_build
    args=['--out',str(out),'--arm','k1','--seed',str(config['seed']),'--model-path',model['path'],'--kernel','ref','--grad-ckpt','--micro-tokens','12000','--max-len','4096','--save-every','200','--no-merge','--epochs','2','--total-steps','3116','--expect-pairs','186']
    return lifecycle(out, identity, lambda: t.run(t.parse_args(args)))


def lifecycle(out: Path, identity: dict, invoke):
    """Record each invocation; the outer launcher owns lease, logs and relaunch command."""
    attempts = out / 'attempts'; attempts.mkdir(exist_ok=True)
    attempt = attempts / uuid.uuid4().hex; attempt.mkdir()
    def write(name, obj):
        tmp = attempt / (name + '.partial')
        with tmp.open('w') as f:
            json.dump(obj, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, attempt / name)
        fd = os.open(attempt, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    stop = threading.Event()
    def beat():
        while not stop.wait(20): write('heartbeat.json', {'unix_time': time.time(), 'state':'running'})
    write('start.json', {'unix_time':time.time(), 'identity_sha256':canonical(identity)})
    write('heartbeat.json', {'unix_time':time.time(), 'state':'running'})
    worker=threading.Thread(target=beat, daemon=True); worker.start()
    try:
        result=invoke()
    except BaseException as e:
        stop.set(); worker.join(); write('terminal.json', {'unix_time':time.time(), 'exit_code':1, 'error_type':type(e).__name__})
        raise
    stop.set(); worker.join(); write('terminal.json', {'unix_time':time.time(), 'exit_code':0})
    return result
