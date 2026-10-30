#!/usr/bin/env python3
"""Native initial Nimble NPU compatibility probe; synthetic inputs only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading
import time


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def atomic(path, obj):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    with os.fdopen(fd, 'w') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, 0o644); os.replace(tmp, path)


def validate_contract_identity(config):
    adapter = Path(config['adapter'])
    contract = json.loads((adapter / 'schema_config.json').read_text())
    if contract['task'] != 'schema_candidate_classification_v1':
        raise ValueError('Initial checkpoint requires v1 schema; alias may point at v3')
    if sha(adapter / 'adapter_model.safetensors') != 'ba7e28acb97f973e80fa51f3aa6fc6f75ea4081b89632ed45d8e5f3a1d7bfa6b':
        raise ValueError('Not the original benchmark adapter')
    if contract['revision'] != config['base_revision'] or Path(config['base'], '.complete').read_text().splitlines()[0] != config['base_revision']:
        raise ValueError('Base revision mismatch')
    return contract


def validate_output(logits, probabilities, count):
    if len(logits) != count or len(probabilities) != count or not all(math.isfinite(x) for x in logits + probabilities):
        raise ValueError('Invalid candidate dimensions or nonfinite output')
    if any(p < 0 or p > 1 for p in probabilities) or abs(sum(probabilities) - 1) > 1e-6:
        raise ValueError('Invalid probability distribution')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True); ap.add_argument('--resume', action='store_true')
    args = ap.parse_args(); config_path = Path(args.config)
    config = json.loads(config_path.read_text()); out = Path(config['out'])
    config_sha = sha(config_path)
    import fcntl
    lock = (out / 'driver.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    terminal_path = out / 'PROBE_COMPLETE.json'
    if terminal_path.exists():
        old = json.loads(terminal_path.read_text())
        if not args.resume or old['rc'] == 0 or old['config_sha256'] != config_sha:
            raise ValueError('Terminal exists; preserve previous probe')
        terminal_path.rename(out / ('PROBE_COMPLETE.before_resume_%d.json' % time.time_ns()))
    status = {'stage': 'verify', 'progress': 0, 'total': 8, 'chips': 1}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(10):
            value = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **status}
            atomic(out / 'STATUS.json', value)
            with (out / 'heartbeat.log').open('a') as f: f.write(json.dumps(value) + '\n')
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    rc = 1; error = None; outputs = {}
    try:
        for path, expected in config['files'].items():
            if sha(path) != expected: raise ValueError('Frozen file changed: ' + path)
        contract = validate_contract_identity(config)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
        sys.dont_write_bytecode = True; sys.path.insert(0, config['code'])
        import torch
        import torch_npu
        from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
        from peft import PeftModel
        from nimble.scoring.release_contract import prompt_builder
        from nimble.scoring.cuda_scorer import candidate_projection
        torch.set_num_threads(8); torch.npu.set_device('npu:0')
        torch.npu.config.allow_internal_format = False
        torch.npu.conv.allow_hf32 = False; torch.npu.matmul.allow_hf32 = False
        tokenizer = AutoTokenizer.from_pretrained(config['adapter'], local_files_only=True)
        prepare = prompt_builder(config['adapter'], tokenizer)
        examples = json.loads(Path(config['fixtures']).read_text())
        prepared = [prepare(tokenizer, e['context'], e['schema'], 2048, system_role=True) for e in examples]
        if any(len(p.names) != 1 for p in prepared): raise ValueError('Probe fixture expects one field')
        status['stage'] = 'load_and_merge_cpu'; start = time.monotonic()
        base, loading = Qwen3_5ForConditionalGeneration.from_pretrained(config['base'], local_files_only=True,
            dtype=torch.bfloat16, device_map='cpu', attn_implementation='sdpa', output_loading_info=True)
        if any(loading.get(k) for k in ['missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs']):
            raise ValueError('Base checkpoint loading differs: ' + str(loading))
        model = PeftModel.from_pretrained(base, config['adapter'], local_files_only=True).merge_and_unload(safe_merge=True)
        model = model.eval().to('npu:0'); torch.npu.synchronize()
        load_seconds = time.monotonic() - start
        head = model.get_output_embeddings().weight; results = []
        start = time.monotonic()
        expected_names = ['item-%d-%d.json' % (r, i) for r in range(2) for i in range(4)]
        existing_names = [p.name for p in sorted(out.glob('item-*.json'))]
        if existing_names != expected_names[:len(existing_names)] or (existing_names and not args.resume):
            raise ValueError('Invalid receipt prefix or missing explicit resume')
        newly_computed = 0
        for repeat in range(2):
            for index, p in enumerate(prepared):
                path = out / ('item-%d-%d.json' % (repeat, index))
                if path.exists():
                    envelope = json.loads(path.read_text()); item = envelope['payload']
                    if hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest() != envelope['sha256']:
                        raise ValueError('Receipt checksum mismatch')
                    if item['config_sha256'] != config_sha or item['fixture_id'] != examples[index]['id'] or item['repeat'] != repeat or item['index'] != index or item['candidate_ids'] != p.candidate_ids[0] or item['choices'] != p.choices[0] or item['prompt_sha256'] != hashlib.sha256(json.dumps(p.full_ids[0]).encode()).hexdigest():
                        raise ValueError('Foreign receipt identity')
                    validate_output(item['logits'], item['probabilities_T1'], len(p.candidate_ids[0]))
                    results.append(item); continue
                status.update(stage='inference', current_index=index, repeat=repeat)
                begin = time.monotonic(); ids = p.full_ids[0]; candidates = p.candidate_ids[0]
                with torch.inference_mode():
                    hidden = model.model(input_ids=torch.tensor([ids], device='npu:0'), use_cache=False).last_hidden_state[:, -1, :]
                    z = candidate_projection(hidden, head, candidates)[0]
                    prob = torch.softmax(z, dim=-1)
                    torch.npu.synchronize()
                    # Same hidden state, independent CPU FP32 projection as a diagnostic.
                    cpu = hidden.float().cpu() @ head[candidates].float().cpu().T
                logits = z.cpu().tolist(); probabilities = prob.cpu().tolist()
                validate_output(logits, probabilities, len(candidates))
                item = {'repeat': repeat, 'index': index, 'fixture_id': examples[index]['id'],
                    'candidate_ids': candidates, 'choices': p.choices[0], 'logits': logits,
                    'probabilities_T1': probabilities, 'prompt_tokens': len(ids),
                    'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                    'projection_cpu_max_delta': max(abs(a-b) for a,b in zip(logits, cpu[0].tolist())),
                    'seconds': time.monotonic() - begin, 'config_sha256': config_sha}
                atomic(path, {'payload': item, 'sha256': hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()}); results.append(item); newly_computed += 1
                status.update(progress=len(results), questions_per_second_per_chip=newly_computed/(time.monotonic()-start),
                    reserved_memory_gib=torch.npu.memory_reserved()/2**30)
        inference_seconds = time.monotonic() - start
        repeat_delta = max(abs(a-b) for first, second in zip(results[:4], results[4:]) for a,b in zip(first['logits'], second['logits']))
        for path, expected in config['files'].items():
            if sha(path) != expected: raise ValueError('Frozen file changed after run: ' + path)
        if sha(config_path) != config_sha: raise ValueError('Config changed during run')
        report = {'scope': 'Synthetic native-interface compatibility, not test accuracy or CUDA equivalence',
            'examples': 4, 'passes': 2, 'load_merge_seconds': load_seconds, 'temperature': 1.0,
            'base_revision': config['base_revision'], 'adapter_revision': config['adapter_revision'],
            'precision': 'bf16 CPU safe merge and backbone, FP32 candidate-token projection',
            'max_input_tokens': 2048, 'repeat_max_logit_delta': repeat_delta,
            'projection_cpu_max_delta': max(r['projection_cpu_max_delta'] for r in results),
            'questions_per_second_per_chip': newly_computed/inference_seconds, 'chips': 1,
            'inference_seconds': inference_seconds,
            'reserved_memory_gib': torch.npu.memory_reserved()/2**30,
            'receipts': {p.name: sha(p) for p in sorted(out.glob('item-*.json'))}}
        atomic(out / 'report.json', report); outputs['report.json'] = sha(out / 'report.json')
        rc = 0; status['stage'] = 'completed'
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc); status['stage'] = 'failed'; raise
    finally:
        stop.set(); thread.join()
        terminal = {'rc': rc, 'error': error, 'config_sha256': config_sha, 'outputs': outputs,
            'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **status}
        atomic(out / 'STATUS.json', terminal); atomic(out / 'PROBE_COMPLETE.json', terminal)


if __name__ == '__main__': main()
