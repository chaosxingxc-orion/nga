#!/usr/bin/env python3
"""Frozen native Open-Jev public-test preflight and resumable single-chip evaluation."""
import argparse
from collections import Counter, defaultdict
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys
import socket
import subprocess
import tempfile
import threading
import time


def stamp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def softmax(logits, temperature):
    require(math.isfinite(temperature) and temperature > 0, 'Invalid temperature')
    require(logits and all(type(x) in (int, float) and math.isfinite(x) for x in logits), 'Invalid logits')
    maximum = max(logits)
    weights = [math.exp((x - maximum) / temperature) for x in logits]
    return [x / sum(weights) for x in weights]


def validate_rows(rows, expected):
    require(len(rows) == expected, 'Test row count changed')
    require(len({r['id'] for r in rows}) == len(rows), 'Duplicate IDs')
    require(all(r['split'] == 'test' for r in rows), 'Non-test input')
    for r in rows:
        q = r['target']
        require(len(q) == len(r['options']) >= 2, 'Target/candidate mismatch')
        require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in q)
                and abs(sum(q) - 1) <= 1e-8, 'Invalid target')


def verify_files(config, config_path):
    files = config['files']
    required = {str(Path(__file__).resolve()), str(Path(config['data']).resolve()),
                config['export_manifest'], config['preregistration']}
    for key in ('code', 'base', 'checkpoint'):
        required.update(str(p.resolve()) for p in Path(config[key]).rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    required.update(config['execution_files'])
    require(required <= set(files), 'Missing frozen dependencies: ' + str(sorted(required - set(files))))
    for path, expected in files.items():
        require(digest(path) == expected, 'Frozen file changed: ' + path)
    return stamp(config)


def row_identity(row, index, identity):
    return {'index': index, 'id': row['id'], 'input_sha256': stamp(row),
            'identity': identity, 'options': row['options'], 'target': row['target'],
            'source': row['source'], 'kind': row['kind'], 'group_id': row['group_id']}


def validate_receipt(envelope, row, index, identity, temperature, expected_tokens=None):
    value = envelope['payload']
    require(stamp(value) == envelope['sha256'], 'Receipt checksum mismatch')
    require(all(value.get(k) == v for k, v in row_identity(row, index, identity).items()), 'Receipt input/order mismatch')
    logits = value['logits']
    require(len(logits) == len(row['target']), 'Wrong candidate count')
    expected = softmax(logits, temperature)
    require(len(value['probabilities']) == len(expected) and
            all(type(p) in (int, float) and math.isfinite(p) and abs(p - q) <= 1e-12
                for p, q in zip(value['probabilities'], expected)), 'Probability/temperature mismatch')
    require(type(value['input_tokens']) is int and value['input_tokens'] > 0, 'Invalid token count')
    require(expected_tokens is None or value['input_tokens'] == expected_tokens, 'Token count differs from preflight')
    return value


def receipts(directory, rows, identity, temperature, token_totals=None):
    paths = sorted(directory.glob('record-*.json'))
    require([p.name for p in paths] == [f'record-{i:06d}.json' for i in range(len(paths))], 'Noncontiguous receipt prefix')
    require(len(paths) <= len(rows), 'Extra receipts')
    return [validate_receipt(json.loads(p.read_text()), rows[i], i, identity, temperature,
                            token_totals[i] if token_totals is not None else None) for i, p in enumerate(paths)]


def require_no_error(out):
    require(not (out / 'ERROR.json').exists(), 'Recorded error requires review; automatic retry is forbidden')


def validate_protocol(config, rows):
    checkpoint = json.loads(Path(config['checkpoint'], 'model.json').read_text())
    require((checkpoint['model_id'], checkpoint['revision'], checkpoint['max_length']) ==
            (config['base_id'], config['base_revision'], config['max_length']), 'Checkpoint protocol mismatch')
    require(config['max_length'] == 4096, 'Released native length limit changed')
    manifest = json.loads(Path(config['export_manifest']).read_text())['configs']['release-v2-redistributable']['splits']['test']
    require(digest(config['data']) == manifest['raw_uncompressed_sha256'], 'Data differs from export manifest')
    require(len(rows) == manifest['count'] == config['expected_rows'], 'Manifest denominator mismatch')
    require(dict(Counter(r['source'] for r in rows)) == manifest['sources'], 'Manifest source counts mismatch')
    require(dict(Counter(r['kind'] for r in rows)) == manifest['kinds'], 'Manifest kind counts mismatch')


def token_lengths(tokenizer, candidate_prompts, row):
    prompts = [tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=False,
               add_generation_prompt=True, enable_thinking=False) for prompt in candidate_prompts(row)]
    encoded = tokenizer(prompts, padding=False, truncation=False)
    return [len(ids) for ids in encoded['input_ids']]


def preflight(config, rows, identity, out, status):
    from transformers import AutoTokenizer
    from jev.api import candidate_prompts
    tokenizer = AutoTokenizer.from_pretrained(config['base'], local_files_only=True)
    tokenizer.padding_side = 'right'
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    directory = out / 'lengths'
    directory.mkdir(exist_ok=True)
    paths = sorted(directory.glob('record-*.json'))
    require([p.name for p in paths] == [f'record-{i:06d}.json' for i in range(len(paths))], 'Noncontiguous length prefix')
    require(len(paths) <= len(rows), 'Extra length receipts')
    results = []
    start = time.monotonic()
    reused = len(paths)
    for i, row in enumerate(rows):
        path = directory / f'record-{i:06d}.json'
        if path.exists():
            envelope = json.loads(path.read_text())
            value = envelope['payload']
            require(stamp(value) == envelope['sha256'] and value['identity'] == identity
                    and value['input_sha256'] == stamp(row) and value['index'] == i, 'Invalid length receipt')
        else:
            value = {'index': i, 'id': row['id'], 'identity': identity, 'input_sha256': stamp(row),
                     'lengths': token_lengths(tokenizer, candidate_prompts, row)}
            atomic(path, {'payload': value, 'sha256': stamp(value)})
        require(len(value['lengths']) == (1 if row['kind'] == 'noul' else len(row['options']))
                and all(type(n) is int and n > 0 for n in value['lengths']), 'Invalid lengths')
        results.append(value)
        status.update(progress=i + 1, rows_per_second=(i + 1 - reused) / max(time.monotonic() - start, 1e-9))
    excess = [{'index': r['index'], 'id': r['id'], 'lengths': r['lengths']} for r in results
              if max(r['lengths']) > config['max_length']]
    report = {'identity': identity, 'rows': len(rows), 'max_length': config['max_length'],
              'maximum_candidate_tokens': max(max(r['lengths']) for r in results),
              'candidate_prompts': sum(len(r['lengths']) for r in results), 'overlength_rows': len(excess),
              'overlength_candidates': sum(n > config['max_length'] for r in results for n in r['lengths']),
              'overlength': excess, 'ordered_ids_sha256': stamp([r['id'] for r in rows]),
              'status': 'ready' if not excess else 'blocked_overlength', 'test_inference_performed': False}
    atomic(out / 'PREFLIGHT.json', report)
    return report


def summarize(rows, values, evaluate_probabilities, temperature):
    require(len(values) == len(rows), 'Incomplete evaluation cannot produce final metrics')
    def metric(indices, temp):
        return evaluate_probabilities([rows[i]['target'] for i in indices],
                                      [softmax(values[i]['logits'], temp) for i in indices], n_bins=15)
    groups = defaultdict(list)
    kinds = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row['source']].append(i)
        kinds[row['kind']].append(i)
    source_metrics = {source: metric(indices, temperature) for source, indices in sorted(groups.items())}
    flags = [{'source': source, 'reason': 'sample_count_below_30', 'count': value['count']}
             for source, value in source_metrics.items() if value['count'] < 30]
    flags += [{'source': source, 'reason': 'exact_zero_or_one', 'metric': key, 'value': value[key]}
              for source, value in source_metrics.items() for key in ('accuracy', 'expected_accuracy', 'multiclass_ece')
              if value[key] in (0.0, 1.0)]
    for key in ('accuracy', 'expected_accuracy', 'nll', 'brier', 'multiclass_ece'):
        if len(source_metrics) > 1 and len({v[key] for v in source_metrics.values()}) == 1:
            flags.append({'reason': 'identical_across_sources', 'metric': key})
    return {'total_count': len(rows), 'hard_count': sum(max(r['target']) == 1 for r in rows),
            'soft_count': sum(max(r['target']) != 1 for r in rows), 'failed_count': 0,
            'serving_temperature': temperature, 'serving': metric(range(len(rows)), temperature),
            'raw_T1': metric(range(len(rows)), 1.0),
            'tie_count': sum(v['logits'].count(max(v['logits'])) > 1 for v in values),
            'by_source_serving': source_metrics,
            'by_kind_serving': {kind: metric(indices, temperature) for kind, indices in sorted(kinds.items())},
            'review_flags': flags}


def validate_preflight(config, rows, identity, out):
    terminal_path = out / 'preflight-COMPLETE.json'
    terminal = json.loads(terminal_path.read_text())
    require(type(terminal.get('rc')) is int and terminal['rc'] == 0 and
            terminal.get('identity') == identity and terminal.get('stage') == 'ready',
            'Preflight terminal not successful or foreign')
    exit_path = out / 'preflight-EXIT'
    require(re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?', exit_path.read_text())
            and exit_path.stat().st_mtime_ns >= terminal_path.stat().st_mtime_ns,
            'Preflight wrapper unsuccessful or stale')
    require(terminal.get('outputs', {}).get('PREFLIGHT.json') == digest(out / 'PREFLIGHT.json'),
            'Preflight report hash mismatch')
    pre = json.loads((out / 'PREFLIGHT.json').read_text())
    require(pre['identity'] == identity and pre['rows'] == len(rows) and pre['status'] == 'ready'
            and pre['overlength_rows'] == 0, 'Whole-test length preflight not passed')
    require(pre['max_length'] == config['max_length'] and
            pre['ordered_ids_sha256'] == stamp([r['id'] for r in rows]), 'Preflight data identity differs')
    paths = sorted((out / 'lengths').glob('record-*.json'))
    require([p.name for p in paths] == [f'record-{i:06d}.json' for i in range(len(rows))],
            'Length evidence incomplete')
    maximum = count = 0
    token_totals = []
    for i, (path, row) in enumerate(zip(paths, rows)):
        envelope = json.loads(path.read_text())
        value = envelope['payload']
        require(stamp(value) == envelope['sha256'] and value['identity'] == identity
                and value['input_sha256'] == stamp(row) and value['index'] == i and value['id'] == row['id'],
                'Invalid length receipt')
        lengths = value['lengths']
        require(len(lengths) == (1 if row['kind'] == 'noul' else len(row['options'])) and
                all(type(n) is int and 0 < n <= config['max_length'] for n in lengths), 'Invalid length bound')
        maximum = max(maximum, max(lengths))
        count += len(lengths)
        token_totals.append(sum(lengths))
    require(pre['maximum_candidate_tokens'] == maximum and pre['candidate_prompts'] == count
            and pre['overlength_candidates'] == 0, 'Length summary differs from evidence')
    return token_totals


def evaluate(config, rows, identity, out, status):
    require_no_error(out)
    token_totals = validate_preflight(config, rows, identity, out)
    for key in ('JEV_LOAD_8BIT', 'JEV_LOAD_4BIT', 'JEV_DEVICE_MAP', 'JEV_MAX_MEMORY'):
        os.environ.pop(key, None)
    os.environ['JEV_TORCH_DTYPE'] = 'bfloat16'
    import torch
    import torch_npu
    from jev.model import DecisionModel
    from jev.metrics import evaluate_probabilities
    torch.npu.set_device('npu:0')
    torch.npu.config.allow_internal_format = False
    torch.npu.conv.allow_hf32 = False
    torch.npu.matmul.allow_hf32 = False
    torch.set_num_threads(8)
    temperature = json.loads(Path(config['checkpoint'], 'temperature.json').read_text())['temperature']
    require(temperature == config['temperature'], 'Serving temperature changed')
    values = receipts(out, rows, identity, temperature, token_totals)
    reused = len(values)
    class LocalDecisionModel(DecisionModel):
        def __init__(self, model_id, revision, **kwargs):
            require((model_id, revision) == (config['base_id'], config['base_revision']), 'Checkpoint base mismatch')
            require(Path(config['base'], '.complete').read_text().splitlines()[0] == revision, 'Local base mismatch')
            super().__init__(config['base'], None, **kwargs)
    status.update(stage='loading', progress=reused)
    model = LocalDecisionModel.load(config['checkpoint'], device='npu:0')
    require(model.max_length == config['max_length'], 'Native max_length mismatch')
    start = time.monotonic()
    for i in range(reused, len(rows)):
        status.update(stage='inference', current_index=i)
        torch.npu.synchronize()
        begin = time.monotonic()
        with torch.inference_mode():
            output = model([rows[i]])
        torch.npu.synchronize()
        require(len(output) == 1, 'Unexpected output count')
        logits = output[0].float().cpu().tolist()
        value = {**row_identity(rows[i], i, identity), 'logits': logits,
                 'probabilities': softmax(logits, temperature), 'input_tokens': model.last_input_tokens,
                 'seconds': time.monotonic() - begin}
        envelope = {'payload': value, 'sha256': stamp(value)}
        validate_receipt(envelope, rows[i], i, identity, temperature, token_totals[i])
        atomic(out / f'record-{i:06d}.json', envelope)
        values.append(value)
        status.update(progress=i + 1, questions_per_second_per_chip=(i + 1 - reused) / (time.monotonic() - start),
                      chips=1, reserved_memory_gib=torch.npu.memory_reserved() / 2**30)
    report = summarize(rows, values, evaluate_probabilities, temperature)
    report.update(identity=identity, ordered_ids_sha256=stamp([r['id'] for r in rows]), reused_rows=reused,
                  inference_runtime={'torch': torch.__version__, 'torch_npu': torch_npu.__version__},
                  scope='10,356-row redistributable public test, not the 10,532-row original test')
    return report


def check_restart(config, allocation, container, running, receipt):
    require(container['State']['Status'] == 'exited', 'Container must be exited')
    chip = config['physical_chip']
    owner = [v for v in allocation['allocation'] if v['chip'] == chip]
    require(len(owner) == 1 and config['out'].endswith('/' + owner[0]['run']), 'Chip ownership changed')
    device = '/dev/davinci' + str(chip)
    mapped = {v['PathOnHost'] for v in container['HostConfig'].get('Devices') or []
              if v['PathOnHost'].startswith('/dev/davinci') and v['PathOnHost'][12:].isdigit()}
    require(mapped == {device}, 'Physical chip mismatch')
    command = ['bash', str(Path(config['out']) / 'evaluate.sh')]
    require(container['Id'] == receipt['container_id'] and container['Image'] == config['image'] == receipt['image'],
            'Container identity/image mismatch')
    require(container['Config']['Cmd'] == command == receipt['command'] and
            container['Config'].get('Entrypoint') == receipt['entrypoint'], 'Command/entrypoint mismatch')
    require(not any(device in [d['PathOnHost'] for d in c['HostConfig'].get('Devices') or []] for c in running),
            'Owned chip is mapped by running container')


def guarded_resume(config, config_path):
    require(socket.gethostname() == 'k8s-node1', 'Resume only on authorized npu/175 host')
    out = Path(config['out'])
    require_no_error(out)
    receipt = json.loads((out / 'LAUNCH_RECEIPT.json').read_text())
    require(digest(config_path) == receipt['config_sha256'], 'Config differs from launch receipt')
    verify_files(config, config_path)
    require(digest(out / 'evaluate.sh') == receipt['wrapper_sha256'], 'Wrapper differs from launch receipt')
    allocation_path = Path('/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json')
    with Path(str(allocation_path) + '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        allocation = json.loads(allocation_path.read_text())
        container = json.loads(subprocess.check_output(['docker', 'inspect', config['container']], text=True))[0]
        ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
        running = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)) if ids else []
        check_restart(config, allocation, container, running, receipt)
        terminal = out / 'evaluate-COMPLETE.json'
        if terminal.exists():
            marker = json.loads(terminal.read_text())
            require(marker['identity'] == stamp(config), 'Foreign terminal identity')
            require(type(marker['rc']) is int and marker['rc'] != 0, 'Successful evaluation must not restart')
        require(not (out / 'report.json').exists(), 'Existing final report requires review, not automatic restart')
        for name in ('evaluate-COMPLETE.json', 'evaluate-EXIT', 'evaluate-STATUS.json'):
            path = out / name
            if path.exists():
                path.rename(out / (name + '.before_restart_' + str(time.time_ns())))
        subprocess.run(['docker', 'start', config['container']], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--mode', choices=['preflight', 'evaluate', 'resume'], required=True)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    if args.mode == 'resume':
        guarded_resume(config, config_path)
        return
    config_hash = digest(config_path)
    out = Path(config['out'])
    lock = (out / (args.mode + '.lock')).open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Refuse before starting a heartbeat or overwriting terminal evidence.
    require(not (out / (args.mode + '-COMPLETE.json')).exists(),
            'Existing terminal requires guarded resume or a fresh run directory')
    require(not (out / (args.mode + '-EXIT')).exists(), 'Existing wrapper marker requires guarded resume')
    if args.mode == 'evaluate':
        require(not (out / 'report.json').exists(), 'Existing report forbids direct restart')
    status = {'stage': 'verify', 'progress': 0, 'total': config['expected_rows'], 'mode': args.mode}
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(15):
            snapshot = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **status}
            atomic(out / (args.mode + '-STATUS.json'), snapshot)
            with (out / (args.mode + '-heartbeat.log')).open('a') as stream:
                stream.write(json.dumps(snapshot) + '\n')
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    identity = stamp(config)
    rc = 1
    error = None
    outputs = {}
    try:
        verify_files(config, config_path)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
        sys.dont_write_bytecode = True
        sys.path.insert(0, config['code'])
        from jev.data import validate_records
        rows = [json.loads(line) for line in Path(config['data']).read_text().splitlines()]
        validate_rows(rows, config['expected_rows'])
        validate_records(rows)
        validate_protocol(config, rows)
        require(Counter(max(r['target']) == 1.0 for r in rows)[True] == config['hard_count'], 'Hard denominator changed')
        status['stage'] = args.mode
        report = preflight(config, rows, identity, out, status) if args.mode == 'preflight' else evaluate(config, rows, identity, out, status)
        verify_files(config, config_path)
        require(digest(config_path) == config_hash, 'Configuration changed during run')
        if args.mode == 'evaluate':
            atomic(out / 'report.json', report)
        output_name = 'report.json' if args.mode == 'evaluate' else 'PREFLIGHT.json'
        outputs[output_name] = digest(out / output_name)
        status['stage'] = report.get('status', 'complete')
        rc = 0
    except BaseException as exc:
        status['stage'] = 'failed'
        error = type(exc).__name__ + ': ' + str(exc)
        if args.mode == 'evaluate' and 'current_index' in status and not (out / 'ERROR.json').exists():
            index = status['current_index']
            atomic(out / 'ERROR.json', {'identity': identity, 'index': index,
                   'input_sha256': stamp(rows[index]), 'error': error})
        raise
    finally:
        stop.set()
        thread.join()
        terminal = {'rc': rc, 'identity': identity, 'config_sha256': config_hash, 'error': error, 'outputs': outputs,
                    'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **status}
        atomic(out / (args.mode + '-STATUS.json'), terminal)
        atomic(out / (args.mode + '-COMPLETE.json'), terminal)


if __name__ == '__main__':
    main()
