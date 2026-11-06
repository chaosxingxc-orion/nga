"""Strict pre-filter loader accounting for the pinned Qwen runtime."""
import copy, hashlib, json, math, struct
from pathlib import Path

FIELDS=('missing_keys','unexpected_keys','mismatched_keys','error_msgs','conversion_errors')
PUBLIC=FIELDS[:-1]
SOURCES={'modeling_utils.py':'d8bf1879d6f582888b6cf47b4d63070260285a3bd1dc94ce7e1373304f74168a','utils/loading_report.py':'5e201aa79b46d7831e760984cf178bacaf33d6cedfe507972d2491537eb01fde','models/qwen3_5/modeling_qwen3_5.py':'0e2cd8dc50885b2701d26b116c585eedcdc62a24080ec34345af55b963126ded','models/qwen3_5/configuration_qwen3_5.py':'3c01b3cdcff8d77cbafac9841bc48c41e5a5b38637231f1bde3d843cd198dbaf','__init__.py':'67b01cb68df95d42da0661ea120535f33bb618225622e9523bd32e3b7741f9e1','core_model_loading.py':'bdba8ed71e303c626f91972b4787922f5f23d17060c37145adbbee1ae36599c6'}
class CaptureBeforeFilter:
 def _adjust_missing_and_unexpected_keys(self, info):
  self._raw_capture_count=getattr(self,'_raw_capture_count',0)+1
  try: self._raw_loading_info={k:copy.deepcopy(getattr(info,k)) for k in FIELDS}
  except Exception as e: self._raw_capture_error=repr(e)
  return super()._adjust_missing_and_unexpected_keys(info)

def normalize(x):
 if isinstance(x,dict): return {str(k):normalize(v) for k,v in x.items()}
 if isinstance(x,(set,frozenset)): return sorted((normalize(v) for v in x),key=repr)
 if isinstance(x,(list,tuple)): return [normalize(v) for v in x]
 if x is None or isinstance(x,(str,int,float,bool)): return x
 return repr(x)

def source_check(transformers, base):
 root=Path(transformers.__file__).resolve().parent
 actual={k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in SOURCES}
 if actual!=SOURCES: raise RuntimeError('Transformers source pin mismatch')
 from transformers.modeling_utils import PreTrainedModel
 if base._adjust_missing_and_unexpected_keys is not PreTrainedModel._adjust_missing_and_unexpected_keys: raise RuntimeError('unexpected hook resolution')
 if list(base._keys_to_ignore_on_load_unexpected)!=['^mtp.*']: raise RuntimeError('unexpected filter pattern')
 return actual

def inventory(root):
 root=Path(root); index=json.loads((root/'model.safetensors.index.json').read_text())['weight_map']; headers={}; hashes={}
 shards=sorted(root.glob('*.safetensors'))
 if len(shards)!=18 or {p.name for p in shards}!=set(index.values()): raise RuntimeError('shard inventory mismatch')
 for p in shards:
  with p.open('rb') as f:
   b=f.read(8)
   if len(b)!=8: raise RuntimeError('short header')
   n=struct.unpack('<Q',b)[0]
   if not 0<n<16*1024**2: raise RuntimeError('invalid header length')
   data=f.read(n)
   if len(data)!=n: raise RuntimeError('short header')
  hashes[p.name]=hashlib.sha256(data).hexdigest()
  def unique(pairs):
   d={}
   for k,v in pairs:
    if k in d: raise RuntimeError('duplicate header key')
    d[k]=v
   return d
  for k,v in json.loads(data,object_pairs_hook=unique).items():
   if k=='__metadata__': continue
   if k in headers or index.get(k)!=p.name: raise RuntimeError('index/header mismatch')
   headers[k]={'shape':v['shape'],'numel':math.prod(v['shape']),'dtype':v['dtype']}
 if set(headers)!=set(index) or len(headers)!=1199: raise RuntimeError('index inventory mismatch')
 return headers,hashes

def account(checkpoint,state,allow,raw,reported,capture_count,pattern):
 errors=[]
 if capture_count!=1: errors.append('capture count differs from one')
 if pattern!=['^mtp.*']: errors.append('filter pattern drift')
 if not isinstance(raw,dict) or set(raw)!=set(FIELDS): errors.append('raw schema mismatch')
 if not isinstance(reported,dict) or set(reported)!=set(PUBLIC): errors.append('returned schema mismatch')
 extra=set(checkpoint)-set(state); missing=set(state)-set(checkpoint)
 mismatch=sorted(k for k in state.keys() & checkpoint.keys() if state[k]['shape']!=checkpoint[k]['shape'])
 if len(state)!=1184 or len(checkpoint)!=1199: errors.append('inventory count mismatch')
 if missing: errors.append('state keys missing from checkpoint')
 if mismatch: errors.append('core shape mismatch')
 if any(checkpoint[k]['dtype']!='BF16' for k in checkpoint.keys() & state.keys()): errors.append('core checkpoint dtype mismatch')
 if any(v.get('dtype','float32')!='float32' for v in state.values()): errors.append('class dtype mismatch')
 if extra!=set(allow) or any(checkpoint[k]!=allow[k] for k in extra if k in allow): errors.append('exact extra metadata mismatch')
 if isinstance(raw,dict) and set(raw)==set(FIELDS):
  if set(raw['unexpected_keys'])!=extra: errors.append('raw unexpected mismatch')
  if any(raw[k] for k in FIELDS if k!='unexpected_keys'): errors.append('raw loader defects')
 if isinstance(reported,dict) and set(reported)==set(PUBLIC) and any(reported[k] for k in PUBLIC): errors.append('filtered report nonempty')
 return {'errors':errors,'checkpoint_count':len(checkpoint),'state_count':len(state),'checkpoint_only':{k:checkpoint[k] for k in sorted(extra)},'state_only':sorted(missing),'shape_mismatch':{k:{'checkpoint':checkpoint[k]['shape'],'state':state[k]['shape']} for k in mismatch}}
