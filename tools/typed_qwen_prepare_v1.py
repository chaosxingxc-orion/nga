"""CPU input package for Typed Decisions; no NPU launch or admission authority."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def module(ref):
    if sha(ref['path']) != ref['sha256']:
        raise ValueError('module changed')
    spec = importlib.util.spec_from_file_location(Path(ref['path']).stem, ref['path'])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def prepare(config):
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    c = json.loads(Path(config).read_text())
    P = module(c['adapter'])
    N = module(c['native_runtime'])
    B = module(c['native_protocol'])
    P.require(sha(c['source']['path']) == c['source']['sha256'], 'dataset changed')
    P.require(sha(c['scorer']['path']) == c['scorer']['sha256'] == P.SCORER_SHA, 'scorer changed')
    P.require(c['scope'] == 'public_fixed_base_test' and c['candidate_selection_allowed'] is False, 'scope differs')
    out = Path(c['output']); out.mkdir()
    rows = pq.read_table(c['source']['path']).to_pylist()
    items, gold = P.map_rows(rows)
    B.validate_items(items)
    P.require(len(rows) == c['expected_cases'] and len(items) == c['expected_decisions'], 'population differs')
    tok = AutoTokenizer.from_pretrained(c['model'], local_files_only=True, trust_remote_code=False)
    tok.padding_side = 'left'
    native = N.reference(Path(c['native_reference']))
    lengths, requests = [], []
    # CPU preparation only; inference is always subject to final source-bound runtime admission.
    for item in items:
        req = N.prepare_request({k: v for k, v in item.items() if k != 'y'}, tok, native)
        P.require(req['request_sha256'] == B.request_hash(item), 'request hash differs')
        P.require(len(req['input_ids']) <= c['max_length'], 'overlength; no truncation')
        lengths.append(len(req['input_ids'])); requests.append(req)
    outputs = {}
    for name, records in [('items', items), ('typed_gold', gold), ('requests', requests)]:
        path = out / (name + '.jsonl')
        with path.open('x') as f:
            for row in records:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        outputs[name] = dict(path=str(path), sha256=sha(path))
    result = dict(schema='typed-qwen-input-preparation-v1', protocol=P.PROTOCOL,
                  status='INPUTS_PREPARED_RUNTIME_INTEGRATION_PENDING', npu_launched=False,
                  model=c['model'], config=dict(path=str(Path(config).resolve()), sha256=sha(config)),
                  source=c['source'], scorer=c['scorer'], cases=len(rows), decisions=len(items),
                  outputs=outputs, max_tokens=max(lengths), min_tokens=min(lengths),
                  overlength=0, requested_workers=c['cpu_workers'], requested_chunk_size=c['cpu_chunk_size'],
                  tokenizer_files={name: sha(Path(c['model']) / name) for name in ('tokenizer.json', 'tokenizer_config.json')},
                  gold_free_requests_sha256=P.digest(requests),
                  boundary='New single-question native label protocol; not published five-question endpoint equivalence',
                  remaining=['generic execution source-mapper integration', 'source-bound model/runtime config and exact independent execution review', 'full-label saved-readout CPU consumer integration'])
    write(out / 'PREPARATION.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.config)), flush=True)
