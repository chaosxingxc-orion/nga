"""BEV public-release TEST runner. Gold-free requests; no label or resource reads."""
import argparse
from collections import Counter
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import types


def require(ok, message):
    if not ok: raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts, 'absolute path required')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path refused')
    return p


def atomic(path, value, exclusive=False):
    path = Path(path)
    temp = path.with_name(path.name + '.pending-' + str(os.getpid()) + '-' + str(threading.get_ident()))
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    os.fchmod(fd,0o644)
    with os.fdopen(fd, 'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    try:
        if exclusive: os.link(temp, path); temp.unlink()
        else: os.replace(temp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if temp.exists(): temp.unlink()


def verify(plan_path, pin):
    p = safe(plan_path); require(sha(p) == pin, 'plan changed')
    d = json.loads(p.read_text())
    require(d['schema'] == 'bev-public-test-plan-v1' and d['scientific_acceptance'] is False and
            d['test_read'] is True and d['source_split'] == 'public_release_test', 'scope differs')
    require(d['selection'] == 'all_release_test_ids' and d['expected_questions'] == 6518, 'public population differs')
    require(d.get('candidate_selection_allowed') is False and d.get('native_reproduction') is False
            and d.get('expected_by_type') == {'choice':3002,'noul':2835,'score':681}
            and d.get('protocol') == 'bev-local-typed-exact-release-test-v1', 'public TEST contract differs')
    require(re.fullmatch(r'Qwen__Qwen3\.5-(0\.8|2|4|9)B-Base', Path(d['model']).name), 'base-only public model scope differs')
    require(d['scoring'] == {'mode':'rightpad','dtype':'float32','head_fp32':False,'hf32':False,
                            'token_budget':16384,'max_sequence_tokens':4096,'chunk':8}, 'scoring differs')
    require(d['device'] == 'npu:0' and d['chips'] == 1, 'one-chip NPU required')
    require(d['image_sha256'] == 'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7', 'image differs')
    require(d['code']['runner']['path'] == str(Path(__file__).resolve()), 'wrong runner')
    for group in ('code', 'inputs', 'model_files'):
        require(isinstance(d[group], dict) and d[group], 'empty pin group')
        for item in d[group].values():
            require(sha(safe(item['path'])) == item['sha256'], 'dependency changed: ' + item['path'])
    require('gold' not in d['inputs'] and 'test' not in d['inputs'], 'label input prohibited')
    require(set(d['inputs']) == {'requests','ids','source_manifest','tokenizer_proof','preregistration'}, 'input inventory differs')
    require(d['source_manifest'] == d['inputs']['source_manifest'], 'source manifest pin differs')
    source = json.loads(safe(d['source_manifest']['path']).read_text())
    require(source.get('schema') == 'bev-public-test-source-v1' and source.get('scope') == 'public_release_test'
            and source.get('config') == 'numeric_temporal' and source.get('split') == 'test'
            and source.get('source_sha256') == 'd06e1948260e07f70435fab8435b687fbff3fcae4e7db871b02127aed60416b8'
            and source.get('rows') == 3329 and source.get('questions') == 6518
            and source.get('by_type') == d['expected_by_type']
            and source.get('ordered_ids_sha256') == d['inputs']['ids']['sha256']
            and source.get('requests_sha256') == d['inputs']['requests']['sha256'], 'source/split/population binding differs')
    package = p.parent
    require(safe(d['out']) == package/'output', 'output placement differs')
    for item in d['inputs'].values(): require(safe(item['path']).parent == package/'inputs', 'input placement differs')
    for item in d['code'].values(): require(safe(item['path']).parent == package/'code', 'code placement differs')
    require(d['mounts'] == [dict(source=str(package), destination=str(package), readonly=True),
            dict(source=str(package/'output'), destination=str(package/'output'), readonly=False),
            dict(source=d['model'], destination=d['model'], readonly=True)], 'gold-free mounts differ')
    require(type(d['chip']) is int and 0 <= d['chip'] < 8, 'physical chip differs')
    proof = json.loads(safe(d['inputs']['tokenizer_proof']['path']).read_text())
    require(proof.get('schema') == 'bev-public-test-tokenizer-proof-v1' and proof.get('questions') == 6518
            and proof.get('model') == d['model'] and proof.get('requests_sha256') == d['inputs']['requests']['sha256']
            and proof.get('prompt_sha256') == d['code']['prompt']['sha256']
            and proof.get('candidate_collisions') == 0 and proof.get('overlength') == 0, 'tokenizer proof differs')
    require(proof.get('tokenizer_files') == {n:v for n,v in d['model_files'].items()
            if n in ('config.json','tokenizer.json','tokenizer_config.json','vocab.json','merges.txt')}, 'tokenizer model pins differ')
    require(Path(d['model']) == Path(d['model_files']['config.json']['path']).parent, 'model directory mismatch')
    require({p.name for p in safe(d['model']).iterdir() if p.is_file()} == set(d['model_files']), 'model file inventory differs')
    require(all(Path(e['path']).parent == Path(d['model']) and Path(e['path']).name == name for name,e in d['model_files'].items()), 'model file placement differs')
    return d


def module(entry, name):
    raw = safe(entry['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'module changed')
    m = types.ModuleType(name); m.__file__ = entry['path']
    exec(compile(raw, entry['path'], 'exec', dont_inherit=True), m.__dict__)
    return m


def components(plan):
    prompt = module(plan['code']['prompt'], 'bev_frozen_prompt')
    previous = sys.modules.get('prompt')
    previous_path = list(sys.path)
    sys.modules['prompt'] = prompt
    try: scorer = module(plan['code']['scorer'], 'bev_frozen_scorer')
    finally:
        sys.path[:] = previous_path
        if previous is None: sys.modules.pop('prompt', None)
        else: sys.modules['prompt'] = previous
    require(scorer.prompt_mod is prompt and prompt.PROMPT_VERSION == 'r0-prompt-v2', 'frozen prompt binding failed')
    bridge = module(plan['code']['bridge'], 'bev_frozen_bridge')
    return prompt, scorer, bridge


def requests(plan, bridge):
    rows = [json.loads(line) for line in Path(plan['inputs']['requests']['path']).read_text().splitlines()]
    ids = json.loads(Path(plan['inputs']['ids']['path']).read_text())
    require(isinstance(ids, list) and len(ids) == len(set(ids)) == 6518, 'invalid release IDs')
    require(len(rows) == 6518 and [x.get('id') for x in rows] == ids, 'release request order differs')
    for row in rows:
        require(set(row) == {'id', 'request'}, 'gold-free envelope required')
        bridge.to_r3_row(row['request'])
    require(dict(Counter(r['request']['type'] for r in rows)) == plan['expected_by_type'], 'request type population differs')
    require(len({digest(r['request']) for r in rows}) == 6494, 'duplicate request population differs')
    return rows


def item_path(out, identifier):
    return out/'items'/(hashlib.sha256(identifier.encode()).hexdigest() + '.json')


def validate_item(value, row, pin, bridge):
    require(value.get('scientific_acceptance') is False and value.get('test_read') is True, 'item scope differs')
    require(value['schema'] == 'bev-public-test-item-v1' and value['plan_sha256'] == pin and
            value['request_sha256'] == digest(row) and value['id'] == row['id'], 'item binding differs')
    pred = value['prediction']; require(pred['id'] == row['id'], 'prediction ID differs')
    n = len(row['request']['candidate_keys'])
    if value['raw'] is not None:
        require(bridge.from_raw(row['id'], value['raw'], n) == pred, 'decoded item differs')
        require(pred['status'] == 'ok', 'nonfinite raw score cannot commit')
    else:
        require(pred['status'] == 'unsupported_length' and pred['sequence_tokens'] > 4096, 'unsupported item differs')
    return value


def existing(out, rows, pin, bridge):
    directory = safe(out/'items'); directory.mkdir(exist_ok=True)
    expected = {item_path(out, r['id']).name: r for r in rows}; found = {}
    for path in directory.iterdir():
        if '.pending-' in path.name: continue
        require(path.name in expected, 'unknown item output')
        safe(path); value = json.loads(path.read_text())
        found[value['id']] = validate_item(value, expected[path.name], pin, bridge)
    return found


def score_batch(batch, scorer, prompt, bridge, plan):
    eligible, results = [], []
    for row in batch:
        parsed = bridge.to_r3_row(row['request'])
        rendered = prompt.build_prompt(parsed, render='record_name', input_mode='full')
        prefix = scorer.tok(rendered.text, add_special_tokens=False)['input_ids']
        labels = [scorer.tok(x, add_special_tokens=False)['input_ids'] for x in rendered.candidates]
        require(prefix and all(labels), 'empty tokenizer sequence')
        require(len({tuple(x) for x in labels}) == len(labels), 'duplicate tokenized candidates')
        length = max(len(prefix)+len(x) for x in labels)
        if length > plan['scoring']['max_sequence_tokens']:
            results.append((row, None, {'id':row['id'],'status':'unsupported_length','sequence_tokens':length}))
        else: eligible.append((row, parsed))
    if eligible:
        raw = scorer.score_raw([parsed for _, parsed in eligible], mode=plan['scoring']['mode'])
        require(len(raw) == len(eligible), 'scorer population differs')
        for (row, _), scores in zip(eligible, raw):
            pred = bridge.from_raw(row['id'], scores, len(row['request']['candidate_keys']))
            require(pred['status'] == 'ok', 'nonfinite or malformed raw score')
            results.append((row, list(scores), pred))
    by_id = {row['id']:(row, raw, pred) for row,raw,pred in results}
    return [by_id[row['id']] for row in batch]


def process(rows, out, pin, bridge, score_fn, on_progress):
    committed = existing(out, rows, pin, bridge); on_progress(len(committed))
    missing = [row for row in rows if row['id'] not in committed]
    for start in range(0, len(missing), 8):
        batch = missing[start:start+8]
        result = score_fn(batch)
        require([row['id'] for row,_,_ in result] == [row['id'] for row in batch], 'batch order differs')
        for row, raw, prediction in result:
            value = {'schema':'bev-public-test-item-v1','id':row['id'],'plan_sha256':pin,
                     'request_sha256':digest(row),'raw':raw,'prediction':prediction,
                     'scientific_acceptance':False,'test_read':True}
            validate_item(value,row,pin,bridge)
            atomic(item_path(out,row['id']),value,exclusive=True);committed[row['id']]=value
            on_progress(len(committed))
    return [committed[row['id']] for row in rows]


def run(plan_path, pin, out, attempt):
    plan=verify(plan_path,pin);require(str(safe(out))==plan['out'],'output differs')
    out = safe(out); out.mkdir(parents=True, exist_ok=True)
    require(attempt >= 1, 'positive attempt required')
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (out/'COMPLETE.json').exists(), 'already complete; do not rerun')
        adir=out/'attempts'/str(attempt);adir.mkdir(parents=True,exist_ok=False)
        start=time.time(); state={'status':'validating','completed':0,'total':6518}; stop=threading.Event()
        def heartbeat():
            value=dict(state,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       elapsed_seconds=time.time()-start,attempt=attempt,scientific_acceptance=False)
            atomic(adir/'heartbeat.json',value); print(json.dumps(value),flush=True)
        def beat_loop():
            while not stop.wait(30):heartbeat()
        heartbeat(); thread=threading.Thread(target=beat_loop,daemon=True);thread.start()
        rc=1
        try:
            plan=verify(plan_path,pin);require(str(out)==plan['out'],'output differs')
            prompt,scorer_module,bridge=components(plan);rows=requests(plan,bridge)
            prior=existing(out,rows,pin,bridge);state.update(completed=len(prior),status='model_loading')
            import torch
            import torch_npu
            torch.npu.set_device(plan['device'])
            torch.npu.conv.allow_hf32=False;torch.npu.matmul.allow_hf32=False
            require(not torch.npu.conv.allow_hf32 and not torch.npu.matmul.allow_hf32,'HF32 not disabled')
            scorer=scorer_module.R3Scorer(plan['model'],device=plan['device'],dtype='float32',
                    token_budget=16384,head_fp32=False,render='record_name').load()
            state.update(status='scoring',chips=1,reserved_gib=torch.npu.memory_reserved()/2**30)
            def progress(count):
                state.update(completed=count,reserved_gib=torch.npu.memory_reserved()/2**30)
                stats=dict(scorer.stats);seconds=stats.get('rightpad_s',0)
                state['scorer_stats']=stats
                state['forwarded_tokens_per_second_per_chip']=stats.get('tokens',0)/seconds if seconds else None
            values=process(rows,out,pin,bridge,lambda batch:score_batch(batch,scorer,prompt,bridge,plan),progress)
            verify(plan_path,pin)
            outcomes=dict(Counter(v['prediction']['status'] for v in values))
            rc=0 if outcomes=={'ok':6518} else 2
            summary={'schema':'bev-public-test-completion-v1','plan_sha256':pin,'attempt':attempt,
                     'exit_code':rc,'rows':6518,'outcomes':outcomes,'scientific_acceptance':False,
                     'test_read':True,'native_reproduction':False,'scorer_stats':dict(scorer.stats),
                     'items':{item_path(out,r['id']).name:sha(item_path(out,r['id'])) for r in rows}}
            atomic(out/'COMPLETE.json',summary,exclusive=True)
            state['status']='complete' if rc==0 else 'completed_with_unsupported_items'
        except BaseException as error:
            state.update(status='failed',error_type=type(error).__name__,error=str(error)[:800]);raise
        finally:
            stop.set();thread.join(timeout=2);heartbeat()
            atomic(adir/'EXIT.json',{'exit_code':rc,'attempt':attempt,'plan_sha256':pin,
                                    'utc_seconds':time.time(),'scientific_acceptance':False})
    return rc


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('op',choices=['verify','run'])
    parser.add_argument('--plan',required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--attempt',type=int,default=1);args=parser.parse_args()
    if args.op=='verify':
        plan=verify(args.plan,args.sha256)
        p,s,b=components(plan);requests(plan,b);print('BEV_PUBLIC_TEST_VERIFIED');return 0
    require(sha(safe(args.plan))==args.sha256,'plan changed')
    plan=json.loads(Path(args.plan).read_text()); out=safe(plan['out']);out.mkdir(parents=True,exist_ok=True)
    (out/'logs').mkdir(exist_ok=True)
    import contextlib
    with (out/'logs'/('attempt-'+str(args.attempt)+'.log')).open('a',buffering=1) as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        return run(args.plan,args.sha256,plan['out'],args.attempt)


if __name__=='__main__':
    os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
    raise SystemExit(main())
