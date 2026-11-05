"""Read and bind the two compact saved-record files to their parsed bytes."""
import hashlib
import json
from pathlib import Path


def load_item(dest, item, generation, native, ref, replay):
    dest = Path(dest)
    replay.require(dest.is_dir() and not dest.is_symlink(), 'item missing')

    def snapshot(path):
        replay.require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe path')
        raw = path.read_bytes()
        return json.loads(raw), hashlib.sha256(raw).hexdigest()

    receipt, receipt_hash = snapshot(dest / 'COMMITTED.json')
    record, record_hash = snapshot(dest / 'record.json')
    replay.require(set(receipt) == {'record.json'} and receipt['record.json'] == record_hash, 'partial/changed record')
    replay.require(set(record) == {'schema', 'model_sha256', 'contract_sha256', 'prediction', 'forwards'} and record['schema'] == 'bev-native-compact-v1' and type(record['forwards']) is int and record['forwards'] == 1, 'record shape differs')
    replay.require(record['model_sha256'] == generation['model_sha256'] and record['contract_sha256'] == generation['contract_sha256'], 'record generation differs')
    return replay.validate_prediction(record['prediction'], item, generation, native, ref), receipt_hash, record_hash
