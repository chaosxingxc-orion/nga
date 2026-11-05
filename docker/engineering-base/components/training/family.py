"""Versioned, bounded K1 family route. The v1 component is unchanged."""
from __future__ import annotations
import copy, importlib.util, json, os, random, re, sys, warnings
from pathlib import Path
import training

HERE = Path(__file__).parent
REGISTRY = json.loads((HERE / 'family-registry-v2.json').read_text())
RECIPES = {x['id']: x for x in REGISTRY['recipes'].values()}
TOTAL = 3116

def validate(config):
    import jsonschema
    schema = json.loads((HERE / 'family-schema-v2.json').read_text())
    jsonschema.Draft202012Validator(schema).validate(config)
    if config['seed'] > (2**64 - 1 - TOTAL) // 1000003:
        raise ValueError('seed exceeds derived torch RNG range')
    recipe = RECIPES[config['recipe_id']]
    if config['model']['id'] != recipe['model_id']:
        raise ValueError('model size does not match recipe')
    return recipe

def cli(config, output):
    recipe = validate(config)
    return ['--out', str(output), '--arm', 'k1', '--seed', str(int(config['seed'])),
            '--model-path', config['model']['path'], '--kernel', 'ref', '--grad-ckpt',
            '--micro-tokens', '12000', '--max-len', '4096', '--save-every', '200',
            '--no-merge', '--epochs', '2', '--total-steps', str(TOTAL),
            '--expect-pairs', str(recipe['pairs']), '--lr', '0.0001', '--lora-r', '16',
            '--lora-alpha', '32', '--lora-dropout', '0.05', '--stop-after', str(int(config['engineering_stop_after']))]

def seed_step(torch, seed, step, *, require_npu=True):
    s = seed * 1000003 + step
    random.seed(s); torch.manual_seed(s)
    npu = getattr(torch, 'npu', None)
    if npu is None or not callable(getattr(npu, 'manual_seed_all', None)):
        if require_npu: raise RuntimeError('NPU RNG seed API unavailable')
        return 'no NPU seed API (CPU diagnostic)'
    npu.manual_seed_all(s)
    return 'NPU seeded'

def topology(trainable):
    return [{'name': n, 'shape': list(p.shape), 'dtype': str(p.dtype)} for n,p in trainable]

def check_topology(trainable, recipe):
    ts = topology(trainable)
    expected = expected_topology(recipe)
    if not expected:
        raise ValueError('exact authenticated architecture topology unavailable; admission closed')
    if ts != expected:
        raise ValueError('unexpected ordered LoRA name/shape/dtype topology')
    if len(ts) != 2 * recipe['pairs'] or sum(p.numel() for _,p in trainable) != recipe['trainable_parameters']:
        raise ValueError('unexpected LoRA topology or trainable count')
    if len({x['name'] for x in ts}) != len(ts) or any('lora_' not in x['name'] or x['dtype'] != 'torch.float32' for x in ts):
        raise ValueError('unexpected trainable names or dtype')
    return ts

def expected_topology(recipe):
    name=recipe.get('topology_file'); digest=recipe.get('topology_sha256')
    if not isinstance(name,str) or not re.fullmatch(r'topologies/topology-(0\.8B|2B|4B|9B)\.json',name):
        return None
    path=HERE/name
    if path.is_symlink() or training.sha(path)!=digest: raise ValueError('topology manifest digest mismatch')
    data=json.loads(path.read_text())
    if data['model_id']!=recipe['model_id'] or data['revision']!=recipe['revision'] or data['config_sha256']!=recipe['files']['config.json'] or data['pairs']!=recipe['pairs'] or data['trainable_parameters']!=recipe['trainable_parameters']:
        raise ValueError('topology provenance mismatch')
    return data['topology']

def identity(config, recipe):
    return {'version':'family-checkpoint-v2', 'recipe_id':recipe['id'], 'registry_sha256':training.sha(HERE/'family-registry-v2.json'),
            'model_id':recipe['model_id'], 'model_revision':recipe['revision'],
            'model_inventory_sha256':training.canonical(recipe['files']), 'data_sha256':training.DATA_SHA,
            'source':training.PINS, 'family_sha256':training.sha(Path(__file__)),
            'training_sha256':training.sha(HERE/'training.py'), 'seed':config['seed']}

def validate_v2(st, ident, names=None):
    if not isinstance(st,dict) or st.get('identity') != ident: raise ValueError('checkpoint identity mismatch or legacy import unsupported')
    step=training.validate_state(st,ident,TOTAL)
    if st.get('cursor') != {'next_step':step,'epoch':step//1558,'batch':step%1558,'step_seed':ident['seed']*1000003+step}: raise ValueError('cursor mismatch')
    parent=st.get('parent_sha256')
    if parent is not None and (not isinstance(parent,str) or not re.fullmatch('[0-9a-f]{64}',parent)): raise ValueError('invalid parent digest')
    top=st.get('topology')
    if not isinstance(top,list) or not top or [x['name'] for x in top] != list(st['lora']): raise ValueError('checkpoint topology mismatch')
    if names is not None and top != names: raise ValueError('checkpoint parameter order or topology mismatch')
    for x in top:
        p=st['lora'][x['name']]
        if list(p.shape)!=x['shape'] or str(p.dtype)!=x['dtype']: raise ValueError('checkpoint tensor mismatch')
    import torch
    if any(not torch.isfinite(v).all().item() for v in st['lora'].values()): raise ValueError('nonfinite adapter tensor')
    # Reconstruct the registered schedule using the current runtime, before restore.
    dummy=torch.nn.Parameter(torch.zeros(()))
    reference_opt=torch.optim.AdamW([dummy],lr=1e-4,weight_decay=.01)
    reference_sched=torch.optim.lr_scheduler.OneCycleLR(reference_opt,max_lr=1e-4,total_steps=TOTAL,pct_start=.1)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        for _ in range(step): reference_sched.step()
    if st['sched'] != reference_sched.state_dict(): raise ValueError('scheduler recipe state mismatch')
    groups=st['opt'].get('param_groups',[])
    ref=reference_opt.state_dict()['param_groups'][0]
    if len(groups)!=1 or {k:v for k,v in groups[0].items() if k!='params'} != {k:v for k,v in ref.items() if k!='params'}:
        raise ValueError('optimizer recipe group mismatch')
    params=[p for g in groups for p in g['params']]
    if params != list(range(len(top))): raise ValueError('optimizer parameter order mismatch')
    for i,x in zip(params,top):
        state=st['opt']['state'][i]
        value=state['step']
        if not isinstance(value, torch.Tensor) or value.numel()!=1 or not torch.isfinite(value).all().item() or value.item()!=step:
            raise ValueError('invalid Adam step')
        if any(not torch.isfinite(state[k]).all().item() for k in ('exp_avg','exp_avg_sq')) or (state['exp_avg_sq'] < 0).any().item():
            raise ValueError('invalid Adam moments')
        if any(list(state[k].shape)!=x['shape'] or str(state[k].dtype)!=x['dtype'] for k in ('exp_avg','exp_avg_sq')): raise ValueError('optimizer tensor mismatch')
    return step

def save_v2(torch, out, step, trainable, opt, sched, ident, parent):
    d=Path(out)/'ckpt'; d.mkdir(exist_ok=True)
    st={'step':step,'lora':{n:p.detach().cpu().clone() for n,p in trainable},'opt':opt.state_dict(),'sched':sched.state_dict(),
        'identity':ident,'topology':topology(trainable),'parent_sha256':parent,
        'cursor':{'next_step':step,'epoch':step//1558,'batch':step%1558,'step_seed':ident['seed']*1000003+step}}
    validate_v2(st,ident,topology(trainable))
    dest=d/f'step_{step:06d}.pt'; tmp=d/f'.partial-{step}'
    if dest.exists() or any(d.glob('.partial-*')): raise ValueError('checkpoint exists or partial remains')
    with tmp.open('xb') as f: torch.save(st,f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,dest)
    fd=os.open(d,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return training.sha(dest)

def load_v2(torch, output, resume, ident):
    if any((output/'ckpt').glob('.partial-*')): raise ValueError('partial checkpoint remains')
    path=Path(resume['path'])
    if path.parent != output/'ckpt' or path.is_symlink() or not re.fullmatch(r'step_\d{6}\.pt',path.name): raise ValueError('checkpoint outside owned output')
    checkpoints=sorted((output/'ckpt').glob('step_*.pt'))
    if not checkpoints or checkpoints[-1] != path: raise ValueError('resume must use latest committed checkpoint')
    if training.sha(path)!=resume['sha256']: raise ValueError('checkpoint digest mismatch')
    try: st=torch.load(path,map_location='cpu',weights_only=True)
    except Exception as e: raise ValueError('invalid checkpoint') from e
    if validate_v2(st,ident)!=int(path.stem[5:]): raise ValueError('checkpoint filename mismatch')
    return st

def publish_adapter(out, st, ident, owner, checkpoint_sha):
    """Publish the terminal checkpoint through a verified, retryable staging directory."""
    from peft import LoraConfig, TaskType
    from safetensors.torch import save_file, load_file
    import shutil, tempfile
    expected=expected_topology(RECIPES[ident['recipe_id']])
    if validate_v2(st,ident,expected)!=TOTAL: raise ValueError('publication requires terminal checkpoint')
    binding={'owner':owner,'identity_sha256':training.canonical(ident),'checkpoint_sha256':checkpoint_sha}
    dest=out/'adapter'; key=training.canonical(binding)
    stage=out/('.adapter-publish-'+key); intent=out/('.adapter-intent-'+key+'.json')
    targets=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj','in_proj_qkv','in_proj_z','in_proj_a','in_proj_b','out_proj']
    cfg=LoraConfig(task_type=TaskType.CAUSAL_LM,r=16,lora_alpha=32,lora_dropout=.05,target_modules=targets,bias='none')
    cfg.base_model_name_or_path=ident['model_id']; cfg.revision=ident['model_revision']
    # Compare the complete serialized runtime config, including defaults that affect behavior.
    with tempfile.TemporaryDirectory() as tmp:
        cfg.save_pretrained(tmp)
        expected_config=json.loads((Path(tmp)/'adapter_config.json').read_text())
    def normalize_config(value):
        value=copy.deepcopy(value)
        targets_=value.get('target_modules')
        if not isinstance(targets_,list) or len(targets_)!=len(set(targets_)): raise ValueError('invalid target modules')
        value['target_modules']=sorted(targets_)
        return value
    expected_config=normalize_config(expected_config)
    def syncdir(path):
        fd=os.open(path,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    def verify(directory):
        if directory.is_symlink() or not directory.is_dir(): raise ValueError('invalid adapter directory')
        if set(p.name for p in directory.iterdir()) != {'adapter_config.json','adapter_model.safetensors','PUBLICATION.json','BINDING.json'}: raise ValueError('foreign adapter contents')
        if (directory/'BINDING.json').is_symlink() or json.loads((directory/'BINDING.json').read_text())!=binding: raise ValueError('foreign adapter binding')
        if any(p.is_symlink() or not p.is_file() for p in directory.iterdir()): raise ValueError('invalid adapter file')
        receipt=json.loads((directory/'PUBLICATION.json').read_text())
        if receipt.get('binding')!=binding: raise ValueError('foreign adapter publication')
        files=receipt.get('files')
        if files!={n:training.sha(directory/n) for n in ('adapter_config.json','adapter_model.safetensors')}: raise ValueError('corrupt adapter publication')
        if normalize_config(json.loads((directory/'adapter_config.json').read_text()))!=expected_config: raise ValueError('adapter configuration mismatch')
        tensors=load_file(str(directory/'adapter_model.safetensors'),device='cpu')
        wanted={n.replace('.default.weight','.weight'):p for n,p in st['lora'].items()}
        import torch
        if tensors.keys()!=wanted.keys() or any(not torch.equal(tensors[n],p) for n,p in wanted.items()): raise ValueError('adapter tensors mismatch')
    if dest.exists() or dest.is_symlink():
        verify(dest)
        if stage.exists(): raise ValueError('unexpected staging directory')
        return {'step':TOTAL,'published':True,'adapter':str(dest)}
    # An atomically installed, durable parent intent predates creation of the stage.
    # Never claim an already present stage when that intent is absent.
    if not intent.exists() and not intent.is_symlink():
        if stage.exists() or stage.is_symlink(): raise ValueError('unbound staging directory')
        fd, name=tempfile.mkstemp(prefix='.adapter-intent-tmp-',dir=out)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(binding,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
            try: os.link(name,intent)
            except FileExistsError: pass
            syncdir(out)
        finally: os.unlink(name)
    if intent.is_symlink() or not intent.is_file() or json.loads(intent.read_text())!=binding: raise ValueError('foreign publication intent')
    if stage.exists() or stage.is_symlink():
        # Only our explicitly bound staging area can be discarded after interruption.
        marker=stage/'BINDING.json'
        if stage.is_symlink() or not stage.is_dir() or marker.is_symlink(): raise ValueError('foreign staging directory')
        if not marker.is_file() or json.loads(marker.read_text())!=binding: raise ValueError('foreign staging directory')
        if not {p.name for p in stage.iterdir()} <= {'BINDING.json','.BINDING.tmp','adapter_config.json','adapter_model.safetensors','PUBLICATION.json','README.md'} or any(p.is_symlink() or not p.is_file() for p in stage.iterdir()): raise ValueError('foreign staging contents')
        shutil.rmtree(stage)
    # Use a fresh private stage on every attempt. Interrupted private directories
    # are left intact: ownership cannot be inferred from a partial binding.
    private=Path(tempfile.mkdtemp(prefix='.adapter-stage-tmp-',dir=out))
    with (private/'.BINDING.tmp').open('x') as f:
        json.dump(binding,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
    os.replace(private/'.BINDING.tmp',private/'BINDING.json')
    syncdir(private)
    stage=private
    syncdir(out)
    cfg.save_pretrained(stage)
    save_file({n.replace('.default.weight','.weight'):p.contiguous() for n,p in st['lora'].items()},str(stage/'adapter_model.safetensors'),metadata={'format':'pt'})
    files={n:training.sha(stage/n) for n in ('adapter_config.json','adapter_model.safetensors')}
    (stage/'PUBLICATION.json').write_text(json.dumps({'binding':binding,'files':files},sort_keys=True)+'\n')
    for p in stage.iterdir():
        with p.open('rb') as f: os.fsync(f.fileno())
    fd=os.open(stage,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    verify(stage)
    os.rename(stage,dest)
    fd=os.open(out,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return {'step':TOTAL,'published':True,'adapter':str(dest)}

def run(config, output):
    recipe=validate(config); config=copy.deepcopy(config)
    config['seed']=int(config['seed']); config['engineering_stop_after']=int(config['engineering_stop_after'])
    out=Path(output)
    if not expected_topology(recipe):
        raise ValueError('exact authenticated architecture topology unavailable; admission closed')
    if not out.is_absolute() or out.is_symlink() or not out.is_dir(): raise ValueError('invalid output directory')
    m=config['model']; data=config['dataset']
    obj=training.verify_manifest(Path(m['path']),Path(m['manifest']),m['manifest_sha256'])
    if obj != {'model_id':recipe['model_id'],'files':recipe['files']}: raise ValueError('model inventory differs from registered recipe')
    if training.sha(Path(data['manifest']))!=data['manifest_sha256'] or json.loads(Path(data['manifest']).read_text()) != {'id':'decision-v7-train','sha256':training.DATA_SHA} or training.sha(Path(data['path']))!=training.DATA_SHA: raise ValueError('dataset mismatch')
    training.verify_source()
    import torch
    ident=identity(config,recipe); resume=config['resume']
    sys.path.insert(0,str(training.SOURCE)); os.environ['NGA_R0_CODE']=str(training.SOURCE/'r0_code')
    os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','PYTORCH_NPU_ALLOC_CONF':'expandable_segments:True','TASK_QUEUE_ENABLE':'2'})
    for module in ('build_kev_sft','kev_aug','prompt'): sys.modules.pop(module,None)
    spec=importlib.util.spec_from_file_location('nga_family_trainer',training.SOURCE/'train_r3.py'); t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
    args=t.parse_args(cli(config,out))
    training.claim_owner(out, {'owner':config['owner'],'identity':ident}, resume is not None)
    st=load_v2(torch,out,resume,ident) if resume else None
    if st and st['step']==TOTAL:
        return training.lifecycle(out,ident,lambda:publish_adapter(out,st,ident,config['owner'],resume['sha256']))
    if st and st['step']+config['engineering_stop_after']>TOTAL: raise ValueError('bounded stop exceeds schedule')
    t.TRAIN_FILE=data['path']; t.latest_ckpt=lambda _: resume['path'] if resume else None
    t.seed_step=lambda torch_,seed,step: seed_step(torch_,seed,step)
    original_data=t.Data
    class CheckedData(original_data):
        def steps_per_epoch(self):
            n=super().steps_per_epoch()
            if n!=1558 or len(self.rows)!=15576 or self.sym: raise ValueError('dataset population mismatch')
            return n
    t.Data=CheckedData
    original_build=t.build_model
    def checked_build(args,torch_):
        result=original_build(args,torch_); top=check_topology(result[1],recipe)
        if st: validate_v2(st,ident,top)
        # Publication is driven solely by the durable terminal checkpoint.
        result[0].save_pretrained=lambda *a,**kw: None
        return result
    t.build_model=checked_build
    parent=[resume['sha256'] if resume else None]; last=[None]
    def save(torch_,out_,step,trainable,opt,sched,keep=2):
        if last[0]==step: return # trainer invokes save twice when stop coincides with periodic save
        parent[0]=save_v2(torch_,out_,step,trainable,opt,sched,ident,parent[0]); last[0]=step
    t.save_ckpt=save
    def invoke():
        result=t.run(args)
        terminal=out/'ckpt'/f'step_{TOTAL:06d}.pt'
        if terminal.exists():
            digest=training.sha(terminal)
            state=load_v2(torch,out,{'path':str(terminal),'sha256':digest},ident)
            return publish_adapter(out,state,ident,config['owner'],digest)
        return result
    return training.lifecycle(out,ident,invoke)
