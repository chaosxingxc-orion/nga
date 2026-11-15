"""Crash-resumable stamped readouts with durable committed-prefix receipts.

A receipt is written after the data is fsynced. On recovery only the uncommitted
tail may be truncated; every committed byte is verified before a row is reused.
Existing completed files can migrate only through their producer manifest.
This detects accidents, not deliberate coordinated rewriting of all evidence.
"""
import hashlib
import json
import os

import core_r3 as C
import provenance_r3 as PV


def receipt_path(path):
    return path + ".receipt.json"


def digest_prefix(path, size):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        remaining = size
        while remaining:
            b = f.read(min(remaining, 1 << 22))
            if not b:
                raise PV.ProvenanceRefusal("committed readout prefix is truncated")
            h.update(b)
            remaining -= len(b)
    return h.hexdigest()


def publish_receipt(path, model_sha, scorer, digest=None, rows=None):
    size = os.path.getsize(path)
    doc = {"model_sha256": model_sha, "scorer": scorer, "path": os.path.realpath(path), "committed_bytes": size,
           "sha256": digest if digest is not None else digest_prefix(path, size),
           "rows": rows if rows is not None else PV.count_rows(path)}
    target = receipt_path(path)
    with open(target + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(target + ".tmp", target)
    return doc


def check_receipt(path, model_sha, scorer, recover=False):
    with open(receipt_path(path), encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("model_sha256") != model_sha or doc.get("scorer") != scorer or doc.get("path") != os.path.realpath(path):
        raise PV.ProvenanceRefusal("readout receipt model/scorer mismatch")
    size = doc.get("committed_bytes")
    if type(size) is not int or size < 0 or digest_prefix(path, size) != doc.get("sha256"):
        raise PV.ProvenanceRefusal("committed readout bytes differ from their receipt")
    if os.path.getsize(path) != size:
        if not recover:
            raise PV.ProvenanceRefusal("uncommitted readout tail: resume its producing unit first")
        with open(path, "r+b") as f:
            f.truncate(size)
            f.flush()
            os.fsync(f.fileno())
    if PV.count_rows(path) != doc.get("rows"):
        raise PV.ProvenanceRefusal("readout receipt row count mismatch")
    rows = C.read_jsonl(path)
    keys = [r.get("k") for r in rows]
    if len(keys) != len(set(keys)) or any(k is None for k in keys):
        raise PV.ProvenanceRefusal("duplicate or missing readout keys")
    if any(r.get("m") != model_sha[:PV.STAMP_LEN] for r in rows):
        raise PV.ProvenanceRefusal("readout receipt row stamp mismatch")
    return rows


def read_verified(run_dir, path, model_sha, scorer, require_record=True):
    if require_record and PV._scorer_problems(scorer):
        raise PV.ProvenanceRefusal("reader is not using the scorer of record")
    if os.path.exists(receipt_path(path)):
        return check_receipt(path, model_sha, scorer)
    PV.verify(run_dir, os.path.dirname(path), model_sha, require_scorer_of_record=require_record,
              selected_files=[path])
    return C.read_jsonl(path)


class VerifiedStore(C.ReadoutStore):
    def __init__(self, run_dir, path, model_sha, scorer, require_record=True):
        self.model_sha, self.scorer = model_sha, scorer
        if require_record and PV._scorer_problems(scorer):
            raise PV.ProvenanceRefusal("writer is not using the scorer of record")
        if os.path.exists(path):
            if os.path.exists(receipt_path(path)):
                check_receipt(path, model_sha, scorer, recover=True)
            elif os.path.getsize(path):
                read_verified(run_dir, path, model_sha, scorer, require_record)
            # An empty file carries no reused evidence; establish its empty prefix below.
        super().__init__(path)
        self._digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                self._digest.update(chunk)
        self._committed_size = os.path.getsize(path)
        self.commit()

    def commit(self):
        self._fh.flush()
        os.fsync(self._fh.fileno())
        with open(self.path, "rb") as f:
            f.seek(self._committed_size)
            for chunk in iter(lambda: f.read(1 << 22), b""):
                self._digest.update(chunk)
            self._committed_size = f.tell()
        publish_receipt(self.path, self.model_sha, self.scorer, self._digest.hexdigest(), len(self.done))

    def append(self, obj):
        if obj.get("m") != self.model_sha[:PV.STAMP_LEN] or obj.get("k") in self.done:
            raise PV.ProvenanceRefusal("writer supplied a wrong stamp or duplicate key")
        super().append(obj)
