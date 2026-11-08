import importlib.util,sys,os,json,types,pathlib
p=pathlib.Path(sys.argv[1]); spec=importlib.util.spec_from_file_location('scoped',p); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);sys.argv=[str(p)]+sys.argv[2:]
sys.path.insert(0,str(p.parent/'source'))
import runner,diagnostic
mode=os.environ.get('PROBE','ok'); calls=[]
manifest=json.loads((p.parent/'receipts/DEV-MANIFEST.json').read_text())
metas={(x['mode'],x['row']):x for x in manifest['metadata']}
items=[]
for transform in ('clean','question_only','empty_input'):
 for row in range(33,97):
  x=metas[transform,row]; tokens=[[i+1] for i in range(x['candidate_count'])]
  if mode=='duplicate':tokens[1]=tokens[0]
  identity=dict(key=f"{transform}:{row}:{x['key_sha256']}",candidate_ids=[f'candidate-{i}' for i in range(len(tokens))],token_ids=tokens,gold=0)
  items.append((identity,runner.R3Scorer.__module__ and types.SimpleNamespace(prefix=[row],cands=tokens)))
class S:
 def __init__(self,*args,**kwargs):
  if kwargs: assert args==(manifest['model'],) and kwargs==dict(adapter=manifest['adapter'],device='npu:0',dtype='float32',token_budget=16384)
  self.stats={};self.tok=object()
 def load(self):
  if mode=='load_fail':raise RuntimeError('injected load failure')
  return self
 def _sync(self):pass
 def score_enc(self,enc,mode):
  assert mode=='rightpad';return score(enc,'rightpad')
def score(enc,layout):
 offset=(len(calls)+int(os.environ.get("SKIP_CHUNKS","0")))*32
 assert len(enc)==32 and all(a is b for a,(_,b) in zip(enc,items[offset:offset+32]))
 calls.append(layout)
 pathlib.Path(os.environ['CALLS']).write_text(json.dumps(calls))
 if mode=='exception' or mode=='partial_exception' and len(calls)==2:raise RuntimeError('injected scoring exception')
 if mode=='oom':raise MemoryError('injected OOM')
 if mode=='unsupported':raise TypeError('unsupported cache')
 if mode=='mutation':raise RuntimeError('parent cache mutated')
 ans=[[-float(j+1)-(10 if layout=='shared_prefix' else 0) for j in range(len(e.cands))] for e in enc]
 if mode=='nan':ans[0][0]=float('nan')
 if mode=='short_vector':ans[0].pop()
 if mode=='short_rows':ans.pop()
 return ans
def shared(s,enc,**kw):
 assert kw==dict(budget_bytes=8589934592,allowance_bytes=2147483648,per_row_extra=16777216,max_rows=8)
 return score(enc,'shared_prefix')
class F:
 def scorer(self):return S()
 def prepare(self):return items
 def score_encoded(self,s,enc,**kw):return shared(s,enc,**kw)
if os.environ.get('PRODUCTION'):
 runner.read_rows=lambda data,meta: []
 def hf32(device):
  assert device=='npu:0'
  if mode=='hf32_fail':raise RuntimeError('HF32 readback failed')
  return dict(device=device,matmul=False,conv=False)
 runner.hf32=hf32;runner.R3Scorer=S;runner.prepare=lambda rows,meta,tok:items;diagnostic.score_encoded=shared
 sys.modules['torch']=types.SimpleNamespace(npu=types.SimpleNamespace(mem_get_info=lambda:(1 if mode=='budget_fail' else 2**36,2**37),memory_reserved=lambda:1234))
 sys.exit(m.cli())
sys.exit(m.cli(F()))
