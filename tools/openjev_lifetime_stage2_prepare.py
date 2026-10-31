#!/usr/bin/env python3
"""E41 finite source derivation and freezing; never allocates or launches NPU.

Derived executable bytes are explicit review artifacts. E40 source snapshots remain
immutable; no runtime monkeypatching or free-form shape parameters are provided.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil

ROOT=Path('/mnt/cephfs/xingchao/experiments/jev/reference_inference')
E40=ROOT/'e40_lifetime_npu_openjev2_20261031_v3'
E40_PIN='90721d6509df030a71ed012848f7a0b11ce31b7fd11d63c306fbaf90b223c3d9'
PINS={
 'openjev_lifetime_protocol.py':'15d1f093eb877fa4bf61eca9b04f2e98be2e2aee72a29aaada0bf06211b4a783',
 'openjev_lifetime_npu.py':'3287f8aed2150cd6c3f088609154e8605efd9adc224a91c98f0bfcd25eb3878d',
 'openjev_lifetime_verify.py':'27238178f3459f949f442fdbe1ed3dfdc6a5f4f032ff225e99a44ede000a67c9',
 'openjev_lifetime_launch.py':'3ced0f52f5dbc6fdcc394d75916f3c2e602896b22f3875b0d8d381b0035e685f',
 'openjev_path_trace_run.py':'7aa81798b4de38b598e1de30a7d124939ea9c85aab26a444964c307c3685727c'}
CASES={
 'openjev9_short':dict(model=9,index=4200,batch=15,length=186,heads=32,cores=24,chip=4,
    historical_reserved_gib=17.572265625),
 'openjev2_long':dict(model=2,index=8409,batch=24,length=3480,heads=16,cores=18,chip=1,
    historical_reserved_gib=14.142578125)}
STARTUP=('cd /\nunset PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP\nexport PYTHONNOUSERSITE=1\n'
 'export PYTHONPATH=/usr/local/python3.12.13/lib/python3.12/site-packages:/usr/local/Ascend/ascend-toolkit/latest/python/site-packages:/usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe:/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe\n')
PYTHON='/usr/local/python3.12.13/bin/python3 -B -S -s -P '
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def module(p,name):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def replace(s,a,b,count=None):
 actual=s.count(a)
 if not actual or count is not None and actual!=count:raise ValueError('Derivation anchor differs: '+a)
 return s.replace(a,b)

def derive(filename,raw,case):
 if hashlib.sha256(raw).hexdigest()!=PINS[filename]:raise ValueError('Unreviewed E40 source')
 c=CASES[case];s=raw.decode();idx=str(c['index']);b=c['batch'];l=c['length'];chip=c['chip']
 if filename=='openjev_lifetime_protocol.py':
  s=replace(s,"SCHEMA = 'e40-full-shape-lifetime-v1'",f"SCHEMA = 'e41-full-shape-lifetime-{case}-v1'",1)
  s=replace(s,'4200',idx);s=replace(s,'[15, 186]',f'[{b}, {l}]')
  s=replace(s,"== 15",f"== {b}");s=replace(s,"p['physical_chip'] == 1",f"p['physical_chip'] == {chip}",1)
  s=replace(s,'== 18',f'== {c["cores"]}',1)
  # Bind model/case and exact static shape, beyond the inherited source-config hash.
  s=replace(s,"def validate_plan(p):\n",f"def validate_plan(p):\n    require(p['case'] == {case!r} and p['base_id'] == 'Qwen/Qwen3.5-{c['model']}B' and p['core_shape'] == {[b,l,c['heads'],128]!r}, 'E41 finite case differs')\n",1)
 elif filename=='openjev_lifetime_npu.py':
  s=replace(s,'[15, 186, 16, 128]',str([b,l,c['heads'],128]),1)
  s=replace(s,"'Qwen/Qwen3.5-2B'",f"'Qwen/Qwen3.5-{c['model']}B'",1)
  s=replace(s,'First stage is 2B only',f'E41 {case} model differs',1)
 elif filename=='openjev_lifetime_verify.py':
  s=replace(s,'4200',idx);s=replace(s,'2B fixed input',f'{c["model"]}B fixed input',1)
 elif filename=='openjev_lifetime_launch.py':
  for a,z in [('physical chip 1',f'physical chip {chip}'),('/dev/davinci1',f'/dev/davinci{chip}'),
    ('current,1,run',f'current,{chip},run'),('chip=1',f'chip={chip}'),("x['chip']!=1",f"x['chip']!={chip}"),
    ("x.get('chip')!=1",f"x.get('chip')!={chip}"),("x.get('chip')==1",f"x.get('chip')=={chip}"),
    ('free_now(q,1',f'free_now(q,{chip}'),("]),1)",f"]),{chip})")]:
   s=replace(s,a,z)
  s=replace(s,'E40 full-shape lifetime diagnostic',f'E41 {case} full-shape lifetime diagnostic',1)
 elif filename=='openjev_path_trace_run.py':
  # Only the three input functions are called by E41. Keep trace code byte-identical.
  tree=ast.parse(s);lines=s.splitlines(keepends=True)
  for node in reversed([n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ('select','prepare_input','input_guard')]):
   first=node.lineno-1
   if node.decorator_list:first=min(x.lineno for x in node.decorator_list)-1
   block=''.join(lines[first:node.end_lineno])
   block=block.replace('4200',idx).replace('== 15',f'== {b}').replace('batch=15',f'batch={b}').replace('[15, 186]',f'[{b}, {l}]').replace('186',str(l))
   block=block.replace('fixed E37 short-tail input; exploratory localization after E37',f'fixed E37 metadata input; E41 {case}')
   lines[first:node.end_lineno]=[block]
  s=''.join(lines)
 ast.parse(s)
 return s.encode()

def source_tree(case,out):
 c=CASES[case]
 if out.exists():raise ValueError('New derivation directory required')
 if sha(E40/'plan.json')!=E40_PIN:raise ValueError('E40 v3 changed')
 p=load(E40/'plan.json');out.mkdir()
 for f in E40.glob('*.py'):
  if sha(f)!=p['files'][str(f)]:raise ValueError('E40 local executable changed')
  (out/f.name).write_bytes(derive(f.name,f.read_bytes(),case) if f.name in PINS else f.read_bytes())
 provenance={n:dict(source=str(E40/n),source_sha256=PINS[n],derived_sha256=sha(out/n)) for n in PINS}
 dump(out/'DERIVATION.json',dict(case=case,parameters=c,generator_sha256=sha(__file__),sources=provenance))
 return out

def input_snapshot(case,source,out):
 """Fixed-image CPU action, derives only request/token identity; no weights."""
 c=CASES[case];old=load(ROOT/f'openjev_path_trace_openjev{c["model"]}_20261031_v7/plan.json')
 cfg=load(old['source_config'])
 # Authenticate original inference/input implementation closure before imports.
 e=module(source/'e38_evidence.py','e41_input_evidence').Evidence();e.frozen(old['files'])
 helper=module(source/'openjev_path_trace_run.py','e41_input_native')
 native=module(Path(cfg['out'])/'jeval_reference_inference.py','e41_native_config')
 eligible=native.verify_files(cfg)
 value=helper.prepare_input(cfg,eligible);e.verify();dump(out,value)
 return value

def freeze(case,source,input_file,prereg,out):
 c=CASES[case];model=c['model'];oldpath=ROOT/f'openjev_path_trace_openjev{model}_20261031_v7/plan.json';old=load(oldpath)
 if out.exists():raise ValueError('New plan directory required')
 inp=load(input_file)
 if inp['index']!=c['index'] or inp['shape']!=[c['batch'],c['length']]:raise ValueError('Prepared input differs')
 proto=module(source/'openjev_lifetime_protocol.py','e41_protocol');candidate=module(source/'openjev_lifetime_candidate.py','e41_candidate')
 out.mkdir()
 for f in source.glob('*.py'):shutil.copy2(f,out/f.name)
 shutil.copy2(source/'DERIVATION.json',out/'DERIVATION.json');shutil.copy2(prereg,out/'PREREGISTRATION.md')
 shutil.copy2(Path(__file__),out/'openjev_lifetime_stage2_prepare.py')
 container='nga-e41-'+case.replace('_','-')+'-'+out.name.rsplit('_',1)[-1]
 wrapper='#!/usr/bin/env bash\nset -uo pipefail\n'+STARTUP+'pin=$(cat '+shlex.quote(str(out/'PLAN.sha256'))+')\n'+PYTHON+shlex.quote(str(out/'openjev_lifetime_npu.py'))+' --plan '+shlex.quote(str(out/'plan.json'))+' --plan-sha256 "$pin" >> '+shlex.quote(str(out/'run.log'))+' 2>&1\nrc=$?\nset -o noclobber\nprintf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '+shlex.quote(str(out/'EXIT'))+'\nexit "$rc"\n'
 (out/'run.sh').write_text(wrapper)
 spec=copy.deepcopy(load(old['container_spec']));spec['Cmd']=['bash',str(out/'run.sh')];spec['Labels']={'nga.e41.name':container}
 for d in spec['HostConfig']['Devices']:
  if d['PathOnHost'].startswith('/dev/davinci') and d['PathOnHost'][12:].isdigit():d['PathOnHost']=d['PathInContainer']='/dev/davinci'+str(c['chip'])
 if '/var/run/docker.sock:/var/run/docker.sock' not in spec['HostConfig']['Binds']:spec['HostConfig']['Binds'].append('/var/run/docker.sock:/var/run/docker.sock')
 dump(out/'NPU_SPEC.json',spec)
 src=(out/'modeling_qwen3_5.py').read_bytes()
 p=dict(schema=proto.SCHEMA,case=case,base_id=f'Qwen/Qwen3.5-{model}B',core_shape=[c['batch'],c['length'],c['heads'],128],image=proto.IMAGE,
  out=str(out),container=container,physical_chip=c['chip'],logical_device='npu:0',schedule=proto.schedule(),input=inp,
  source_config=old['source_config'],source_config_sha256=old['source_config_sha256'],numeric_contract=old['numeric_contract'],
  expected_core_names=[n.rsplit('.core:output',1)[0] for n in old['trace_contract']['order'] if n.endswith('.core:output')],
  native_source=str(out/'modeling_qwen3_5.py'),native_source_sha256=candidate.SOURCE_SHA256,
  candidate_sources={'original':candidate.SOURCE_SHA256,**{v:hashlib.sha256(candidate.generated_source(src,v).encode()).hexdigest() for v in candidate.VARIANTS}},
  wrapper=str(out/'run.sh'),container_spec=str(out/'NPU_SPEC.json'),preregistration=str(out/'PREREGISTRATION.md'),
  e38_plan=str(oldpath),e38_plan_sha256=sha(oldpath),candidate_batch_admission=False,
  safety=dict(max_reserved_gib=48,min_free_gib=8,chips=1,on_error='stop_and_preserve_generation',larger_inputs_authorized=False),
  performance_scope='full forward including identical passive token guard; no internal instrumentation',
  resume_policy='verified fixed prefix, same Docker start generation only; unmatched intent fails closed',
  files={**old['files'],str(oldpath):sha(oldpath),str(input_file):sha(input_file)})
 p['files'].update({str(f):sha(f) for f in out.iterdir() if f.is_file()});proto.validate_plan(p)
 dump(out/'plan.json',p);pin=sha(out/'plan.json');(out/'PLAN.sha256').write_text(pin+'\n')
 (out/'LAUNCH_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\n'+shlex.join(['python3','-B','-I',str(out/'openjev_lifetime_launch.py'),'--plan',str(out/'plan.json'),'--plan-sha256',pin])+'\n')
 (out/'RESUME_EXACT.sh').write_text('#!/usr/bin/env bash\nset -e\nbash '+shlex.quote(str(out/'LAUNCH_EXACT.sh'))+'\n')
 return dict(case=case,plan=str(out/'plan.json'),plan_sha256=pin,launched=False,approved=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['derive','input','freeze']);p.add_argument('--case',choices=CASES,required=True)
 for n in ('source','out','input-file','prereg'):p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.action=='derive':print(source_tree(a.case,a.out.absolute()))
 elif a.action=='input':input_snapshot(a.case,a.source.absolute(),a.out.absolute())
 else:print(json.dumps(freeze(a.case,a.source.absolute(),a.input_file.absolute(),a.prereg.absolute(),a.out.absolute())))
