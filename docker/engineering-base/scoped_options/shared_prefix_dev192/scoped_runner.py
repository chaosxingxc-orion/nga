#!/usr/bin/env python3
"""Scoped DEV single-path scorer. Run with python3 -B -P; see HANDOFF."""
import argparse, hashlib, json, os, sys, time, traceback, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_SHA256 = 'b27854722f65b9960d2e3a96054073c628ffd47054843041b52acd00a41a8c47'
OPTION_ID = 'rc1-shared-prefix-q35-9b-base-s2-t3116-dev192-fp32-hf32off-cap8-v1'

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p, obj):
    tmp = p.with_name(p.name + '.tmp')
    with tmp.open('w') as f:
        json.dump(obj, f, allow_nan=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    fd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

class ConfigRefusal(Exception): pass

class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        raise ConfigRefusal(message)

def parse():
    p = ArgumentParser(allow_abbrev=False)
    p.add_argument('--config', required=True); p.add_argument('--output', required=True)
    p.add_argument('--descriptor-sha256', required=True)
    p.add_argument('--scorer-layout', choices=['rightpad','shared_prefix'], default='rightpad')
    p.add_argument('--scorer-option'); p.add_argument('--resume', action='store_true')
    for name in ('budget-bytes','allowance-bytes','per-row-extra','max-rows'): p.add_argument('--'+name,type=int,required=True)
    return p.parse_args()

def load_scope(a):
    cfg = json.loads(Path(a.config).read_text())
    expected = json.loads((ROOT/'config.json').read_text())
    if cfg != expected or hashlib.sha256(canonical(cfg)).hexdigest() != CONFIG_SHA256: raise ValueError('configuration differs from approved scope')
    descriptor = cfg['descriptor']
    if any(getattr(a,k) != descriptor[k] for k in ('budget_bytes','allowance_bytes','per_row_extra','max_rows')): raise ValueError('explicit memory parameters differ from approved scope')
    dh = hashlib.sha256(canonical(descriptor)).hexdigest()
    if dh != cfg['descriptor_sha256'] or dh != a.descriptor_sha256: raise ValueError('descriptor hash mismatch')
    if a.scorer_layout == 'shared_prefix':
        if not a.scorer_option or json.loads(Path(a.scorer_option).read_text()) != descriptor: raise ValueError('shared option descriptor required and must match')
    elif a.scorer_option: raise ValueError('rightpad must not specify shared option')
    for rel, pin in cfg['package_pins'].items():
        if sha(ROOT/rel) != pin: raise ValueError('package source or receipt mismatch: '+rel)
    return cfg, dh

def run(a, cfg, dh, fixture=None):
    # Imports are bound by package hashes before the source directory enters sys.path.
    sys.path.insert(0,str(ROOT/'source'))
    import runner
    from compare import compare
    from diagnostic import score_encoded
    out = Path(a.output)
    identity = {'layout':a.scorer_layout,'option_id':OPTION_ID if a.scorer_layout == 'shared_prefix' else None,
                'descriptor_sha256':dh,'implementation_pins':cfg['package_pins']}
    binding = {'identity':identity, 'config_sha256':hashlib.sha256(canonical(cfg)).hexdigest(), 'output':str(out.resolve())}
    bh = hashlib.sha256(canonical(binding)).hexdigest()
    existed = out.exists()
    if existed:
        if not a.resume or not (out/'binding.json').is_file(): raise ValueError('output exists; explicit same-binding resume required')
        if json.loads((out/'binding.json').read_text()) != {'sha256':bh,'binding':binding}: raise ValueError('resume binding changed')
    else:
        if a.resume: raise ValueError('cannot resume missing output')
        out.mkdir(parents=True, exist_ok=False)
        put(out/'binding.json',{'sha256':bh,'binding':binding})
    # Archive the old full pass first, preserving its bytes before recovery starts.
    if existed:
        history=out/'history'; history.mkdir(exist_ok=True)
        stamp=str(time.time_ns())
        for name in ('pass.json','report.json','EXIT.json','terminal.marker'):
            if (out/name).exists(): os.replace(out/name,history/(stamp+'-'+name))
    # A rejected resume never modifies the old attempt. Once binding is checked this is a new process of the same attempt.
    status = dict(identity, binding_sha256=bh, status='rejected', numerical_pass=False, numerical_status='incomplete', timing_valid=False, lower_all_pairs=None)
    code = 1
    progress = {'completed': 0}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(10): print(json.dumps({'heartbeat_utc':time.time(),'completed':progress['completed'],'total':192}),flush=True)
    thread = threading.Thread(target=heartbeat,daemon=True); thread.start()
    try:
        put(out/'report.json',dict(status,reason='attempt in progress'))
        (out/'terminal.marker').unlink(missing_ok=True); (out/'EXIT.json').unlink(missing_ok=True)
        manifest=json.loads((ROOT/'receipts/DEV-MANIFEST.json').read_text())
        d=cfg['descriptor']
        if (manifest['dataset'],manifest['model'],manifest['adapter']) != (d['population']['dataset'],d['model'],d['adapter']): raise ValueError('manifest asset mismatch')
        if not fixture and os.environ.get('ASCEND_RT_VISIBLE_DEVICES') != '4': raise ValueError('physical device 4 must be explicitly mapped to logical 0')
        rows = None if fixture else runner.read_rows(d['population']['dataset'],manifest)
        flags = {'device':'cpu','matmul':None,'conv':None} if fixture else runner.hf32('npu:0')
        if fixture:
            scorer=fixture.scorer().load(); items=fixture.prepare()
        else:
            import torch
            scorer=runner.R3Scorer(d['model'],adapter=d['adapter'],device='npu:0',dtype='float32',token_budget=16384).load()
            free,total=torch.npu.mem_get_info()
            if d['budget_bytes'] > free: raise MemoryError('configured post-model budget exceeds free device memory')
            put(out/'memory-at-load.json',dict(identity,free_bytes=int(free),total_bytes=int(total),reserved_bytes=int(torch.npu.memory_reserved())))
            items=runner.prepare(rows,manifest,scorer.tok)
        if len(items)!=192 or len({i['key'] for i,_ in items})!=192: raise ValueError('population identity mismatch')
        records=[]; wall=time.perf_counter()
        for offset in range(0,192,32):
            subset=items[offset:offset+32]; enc=[e for _,e in subset]; path=out/f'chunk-{offset:03d}.json'
            if path.exists():
                if not a.resume: raise ValueError('unexpected chunk')
                chunk=json.loads(path.read_text())
                if chunk['binding_sha256']!=bh or chunk['identity']!=identity or [{k:r[k] for k in ('key','candidate_ids','token_ids','gold')} for r in chunk['records']] != [i for i,_ in subset]: raise ValueError('resume chunk identity mismatch')
                rec=chunk['records']
            else:
                scorer.stats.clear(); scorer._sync()
                if a.scorer_layout == 'rightpad': scores=scorer.score_enc(enc,mode='rightpad')
                else:
                    fn = fixture.score_encoded if fixture else score_encoded
                    scores=fn(scorer,enc,budget_bytes=d['budget_bytes'],allowance_bytes=d['allowance_bytes'],per_row_extra=d['per_row_extra'],max_rows=d['max_rows'])
                scorer._sync()
                if len(scores)!=len(subset): raise ValueError('scorer row count mismatch')
                rec=[dict(i,scores=s) for (i,_),s in zip(subset,scores)]
                result=compare(rec,rec)
                if not result['pass']: raise NumericalReject('duplicate expansion rejected')
                put(path,dict(identity=identity,binding_sha256=bh,records=rec))
            if not compare(rec,rec)['pass']: raise NumericalReject('duplicate expansion rejected')
            records.extend(rec)
            progress['completed']=len(records)
            print(json.dumps({'heartbeat_utc':time.time(),'completed':len(records),'total':192}),flush=True)
        if not compare(records,records)['pass']: raise NumericalReject('invalid records')
        elapsed=time.perf_counter()-wall
        summary=dict(identity=identity,binding_sha256=bh,records=records,hf32=flags,wall_seconds=elapsed,resumed=existed,timing_valid=not existed)
        put(out/'pass.json',summary)
        put(out/'report.json',dict(status, status='complete',numerical_pass=None,numerical_status='single_path_unpaired',timing_valid=not existed,lower_all_pairs=None,conditions=len(records),record_grade=False,claim_scope='NOT_OF_RECORD_DEV192_ONLY',historical_evidence=cfg['historical_evidence']))
        code=0
    except Exception as exc:
        traceback.print_exc()
        code=2 if isinstance(exc,NumericalReject) else 1
        put(out/'report.json',dict(status,reason='numerical rejection' if code==2 else 'execution exception',error_category=type(exc).__name__))
    finally:
        stop.set(); thread.join()
        put(out/'EXIT.json',dict(exit_code=code,utc=time.time(),identity=identity,binding_sha256=bh))
        put(out/'terminal.marker',dict(exit_code=code,utc=time.time(),binding_sha256=bh))
    return code

class NumericalReject(Exception): pass

def output_from_argv(argv):
    # Only a single unambiguous, explicitly spelled output is safe to acquire.
    values=[]
    for i, token in enumerate(argv):
        if token == '--': break
        if token == '--output':
            if i+1 >= len(argv) or argv[i+1].startswith('-'): return None
            values.append(argv[i+1])
        elif token.startswith('--output='):
            values.append(token[len('--output='):])
    return values[0] if len(values)==1 and values[0] else None

def cli(fixture=None):
    try:
        a=parse()
    except ConfigRefusal as exc:
        print('configuration refusal:', exc, file=sys.stderr)
        output=output_from_argv(sys.argv[1:])
        if output:
            out=Path(output)
            try:
                out.mkdir(parents=True,exist_ok=False)
            except FileExistsError:
                pass
            else:
                put(out/'report.json',{'status':'rejected','reason':'configuration refusal','numerical_pass':None,'numerical_status':'not_run','timing_valid':False,'lower_all_pairs':None,'error_category':'ConfigRefusal'})
                put(out/'EXIT.json',{'exit_code':1,'utc':time.time(),'reason':'configuration refusal'})
                put(out/'terminal.marker',{'exit_code':1,'utc':time.time(),'reason':'configuration refusal'})
        return 1
    try:
        cfg,dh=load_scope(a)
        return run(a,cfg,dh,fixture)
    except Exception as exc:
        # Refusals before namespace acquisition cannot safely write into an existing attempt.
        traceback.print_exc()
        out=Path(a.output)
        if not out.exists():
            out.mkdir(parents=True,exist_ok=False)
            put(out/'report.json',{'status':'rejected','numerical_pass':False,'numerical_status':'incomplete','timing_valid':False,'lower_all_pairs':None,'error_category':type(exc).__name__})
            put(out/'EXIT.json',{'exit_code':1,'utc':time.time()}); put(out/'terminal.marker',{'exit_code':1,'utc':time.time()})
        return 1
if __name__=='__main__': sys.exit(cli())
