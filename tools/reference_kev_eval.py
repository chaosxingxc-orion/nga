#!/usr/bin/env python3
"""Frozen native Kev reference inference: preflight -> suites -> verified reports.

Run with python3 -P in the existing Ascend image. No training or calibration.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import tempfile
import time


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''):
            h.update(b)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def objhash(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def atomic(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(canonical(obj) + b'\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def verify_files(config):
    for filename, expected in config['files'].items():
        if sha(filename) != expected:
            raise ValueError(f'Frozen input changed: {filename}')


def validate_prediction(record, prediction):
    questions = record['questions']
    probs, logits = prediction['probabilities'], prediction['logits']
    if set(probs) != set(questions) or set(logits) != set(questions):
        raise ValueError('Wrong question set')
    temperature = prediction['inference_temperature']
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError('Invalid temperature')
    for q, p in probs.items():
        z = logits[q]
        if not p or set(p) != set(z):
            raise ValueError('Wrong logit option set')
        if any(not math.isfinite(v) or v < 0 or v > 1 for v in p.values()):
            raise ValueError('Invalid probability')
        if any(not math.isfinite(v) for v in z.values()):
            raise ValueError('Invalid logit')
        if abs(sum(p.values()) - 1) > 1e-5:
            raise ValueError('Probability sum outside native fp32 check')
        e = {k: math.exp(v - max(z.values())) for k, v in z.items()}
        total = sum(e.values())
        # Arithmetic consistency only, not a cross-device/model equivalence gate.
        if max(abs(p[k] - e[k] / total) for k in p) > 1e-5:
            raise ValueError('Probabilities disagree with returned logits')


def read_record(path, record, stamp):
    obj = json.loads(Path(path).read_text())
    payload = obj['payload']
    if objhash(payload) != obj['sha256']:
        raise ValueError('Changed record payload')
    if payload['stamp'] != stamp or payload['input_sha256'] != objhash(record):
        raise ValueError('Foreign record provenance')
    validate_prediction(record, payload['prediction'])
    return payload


def record_keys(records):
    keys = [r['_meta']['id'] for r in records]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError('Empty or duplicate record IDs')
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    a = ap.parse_args()
    config = json.loads(Path(a.config).read_text())
    out = Path(config['out'])
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / 'driver.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stamp = objhash(config)
    status = {'stage': 'verifying_inputs', 'progress': 0, 'total': 0, 'chips': 1}
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(15):
            atomic(out / 'STATUS.json', {'utc': utc(), **status})
            with (out / 'heartbeat.log').open('a') as f:
                f.write(utc() + ' ' + ' '.join(f'{k}={v}' for k, v in status.items()) + '\n')

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    terminal = out / 'REFERENCE_COMPLETE.json'
    try:
        verify_files(config)
        previous = out / 'CONFIG_RECEIPT.json'
        if previous.exists() and json.loads(previous.read_text()) != {'stamp': stamp}:
            raise ValueError('Changed run configuration')
        atomic(previous, {'stamp': stamp})
        if terminal.exists():
            os.replace(terminal, out / f'previous_terminal_{time.time_ns()}.json')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        import torch
        import torch_npu
        torch.npu.set_device('npu:0')
        torch.npu.config.allow_internal_format = False
        torch.npu.conv.allow_hf32 = False
        torch.npu.matmul.allow_hf32 = False
        torch.set_num_threads(8)
        sys.path.insert(0, config['kev_code'])
        import kev.predictors as predictors
        from kev.checkpoint import Checkpoint, LoadOptions
        from kev.suite import load_split, read_manifest
        from kev.benchmark import prediction_rows, summarize
        import transformers
        import peft
        runtime = {'torch': torch.__version__, 'torch_npu': torch_npu.__version__,
                   'transformers': transformers.__version__, 'peft': peft.__version__}
        if runtime != config['runtime']:
            raise ValueError(f'Unexpected runtime versions: {runtime}')
        ck = Checkpoint(config['checkpoint'])
        if ck.meta.base != config['base_id'] or ck.meta.base_revision != config['base_revision']:
            raise ValueError('Wrong native checkpoint base identity')
        if Path(config['base'], '.complete').read_text().splitlines()[0] != ck.meta.base_revision:
            raise ValueError('Local base revision differs from checkpoint')
        ck.meta.base, ck.meta.base_revision = config['base'], None
        predictors.Checkpoint = lambda _: ck
        predictors.sync = lambda _: torch.npu.synchronize()
        status['stage'] = 'loading_model'
        predictor = predictors.LocalPredictor(config['checkpoint'], 'npu:0',
            LoadOptions(dtype=torch.float32, attn='eager', merge=True),
            context=read_manifest(config['suites'][0]['path'])['context'])
        atomic(out / 'ENVIRONMENT.json', {'runtime': runtime, 'model': predictor.environment,
                                        'temperature': predictor.temperature})
        reports = {}
        for suite in config['suites']:
            directory = out / suite['name']
            directory.mkdir(exist_ok=True)
            predictor.context = read_manifest(suite['path'])['context']
            # Development preflight is rerun on resume: validates the actual current runtime.
            status.update(stage=suite['name'] + ':preflight', progress=0, total=2)
            controls = []
            for record in load_split(suite['path'], 'development')[:2]:
                first, second = predictor(record), predictor(record)
                validate_prediction(record, first)
                validate_prediction(record, second)
                prediction_rows(record, first)
                delta = max(abs(v - second['probabilities'][q][k])
                            for q, p in first['probabilities'].items() for k, v in p.items())
                controls.append({'id': record['_meta']['id'], 'repeat_delta': delta,
                                 'prediction': first})
                status['progress'] += 1
            atomic(directory / 'PREFLIGHT.json', {'stamp': stamp, 'controls': controls,
                'interpretation': 'Runtime arithmetic/coverage check; repeat delta diagnostic, no parity or benefit claim'})
            records = load_split(suite['path'], 'test', allow_test=True)
            ids = record_keys(records)
            if len(records) != suite['records'] or sum(len(r['questions']) for r in records) != suite['questions']:
                raise ValueError('Unexpected official test counts')
            atomic(directory / 'EXPECTED.json', {'stamp': stamp, 'ids': ids,
                'input_hashes': [objhash(r) for r in records]})
            items = directory / 'records'
            items.mkdir(exist_ok=True)
            expected = {f'{i:06d}.json' for i in range(len(records))}
            if any(p.name not in expected for p in items.glob('*.json')):
                raise ValueError('Unexpected persisted record')
            rows, elapsed, evaluated = [], 0.0, 0
            status.update(stage=suite['name'] + ':test', progress=0, total=len(records))
            for i, record in enumerate(records):
                path = items / f'{i:06d}.json'
                if path.exists():
                    payload = read_record(path, record, stamp)
                else:
                    started = time.monotonic()
                    prediction = predictor(record)
                    validate_prediction(record, prediction)
                    prediction_rows(record, prediction)
                    duration = time.monotonic() - started
                    payload = {'stamp': stamp, 'input_sha256': objhash(record),
                               'prediction': prediction, 'seconds': duration}
                    atomic(path, {'payload': payload, 'sha256': objhash(payload)})
                    elapsed += duration
                    evaluated += len(record['questions'])
                rows.extend(prediction_rows(record, payload['prediction']))
                status.update(progress=i+1, reserved_gib=round(torch.npu.memory_reserved()/2**30, 4),
                    questions_per_second_per_chip=round(evaluated/elapsed, 4) if elapsed else None)
            if len(list(items.glob('*.json'))) != len(records):
                raise ValueError('Incomplete record store')
            pairs = [(r['id'], r['question']) for r in rows]
            if len(set(pairs)) != len(pairs) or len(rows) != suite['questions']:
                raise ValueError('Missing or duplicate question rows')
            report = summarize(rows, heldout_sources=ck.meta.holdout)
            if report['clean']['n'] != suite['clean_questions']:
                raise ValueError('Unexpected headline denominator')
            # Returned logits already carry checkpoint temperature. Undo it once for raw T=1.
            raw = copy.deepcopy(rows)
            for row in raw:
                z = [v * predictor.temperature for v in row['logits']]
                e = [math.exp(v-max(z)) for v in z]
                row.update(logits=z, p=[v/sum(e) for v in e], inference_temperature=1.0)
            report = {'stamp': stamp, 'split': 'test', 'reference_model': config['checkpoint'],
                'native_serving_temperature': predictor.temperature, 'native': report,
                'raw_temperature_one': summarize(raw, heldout_sources=ck.meta.holdout),
                'records': len(records), 'questions': len(rows), 'chips': 1,
                'new_questions_per_second_per_chip': evaluated/elapsed if elapsed else None,
                'reserved_memory_gib': torch.npu.memory_reserved()/2**30,
                'limitations': ['Local Ascend fp32 reproduction; no cross-hardware bit-equivalence claim.',
                    'Reference test disclosed to training design; no NGA candidate selection.']}
            atomic(directory / 'rows.json', rows)
            atomic(directory / 'report.json', report)
            reports[suite['name']] = {'report_sha256': sha(directory/'report.json'),
                                     'rows_sha256': sha(directory/'rows.json')}
        verify_files(config)
        atomic(out / 'report.json', {'stamp': stamp, 'suite_reports': reports, 'run_of_record': True})
        atomic(terminal, {'rc': 0, 'utc': utc(), 'stamp': stamp, 'suites': reports})
        status['stage'] = 'completed'
    except BaseException as exc:
        atomic(terminal, {'rc': 1, 'utc': utc(), 'stamp': stamp, 'error': str(exc), 'stage': status['stage']})
        status['stage'] = 'failed'
        raise
    finally:
        stop.set()
        heartbeat_thread.join()
        atomic(out / 'STATUS.json', {'utc': utc(), **status})


if __name__ == '__main__':
    main()
