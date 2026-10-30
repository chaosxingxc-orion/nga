#!/usr/bin/env python3
"""Restore exact published Open-Jev original mixtures; no inference or training."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import threading
import time
import urllib.request

ARCHIVE_SHA = '97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5'
ARCHIVE_URL = 'https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4 << 20), b''): h.update(b)
    return h.hexdigest()


def atomic(path, value):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, 0o644); os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def verify(files):
    for path, expected in files.items():
        if sha(path) != expected: raise ValueError('Frozen file differs: ' + path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--config', required=True); args = ap.parse_args()
    cp = Path(args.config); c = json.loads(cp.read_text()); ch = sha(cp); out = Path(c['out'])
    lock = (out/'driver.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (out/'RESTORE_COMPLETE.json').exists(): raise ValueError('Use reviewed fresh directory after terminal')
    status = {'stage': 'verify', 'progress': 0, 'total': 3, 'chips': 0}; stop = threading.Event()
    def heartbeat():
        while not stop.wait(10):
            v = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **status}
            atomic(out/'STATUS.json', v)
            with (out/'heartbeat.log').open('a') as f: f.write(json.dumps(v)+'\n')
    th = threading.Thread(target=heartbeat, daemon=True); th.start(); rc = 1; error = None; outputs = {}
    try:
        verify(c['files']); root = Path(c['release']); export = json.loads((root/'export-manifest.json').read_text())
        for relative, expected in export['source_code_sha256'].items():
            if sha(Path(c['code'])/relative) != expected: raise ValueError('Published source snapshot differs: '+relative)
        status['stage'] = 'download_archive'; archive = out/'wikispeedia_paths-and-graph.tar.gz'
        if not archive.exists():
            context = ssl.create_default_context(cafile=c['ca_bundle'])
            temp = archive.with_suffix('.download')
            try:
                with urllib.request.urlopen(ARCHIVE_URL, context=context, timeout=120) as response, temp.open('wb') as f:
                    for block in iter(lambda: response.read(1 << 20), b''): f.write(block)
                if sha(temp) != ARCHIVE_SHA: raise ValueError('Archive checksum mismatch')
                os.replace(temp, archive)
            finally:
                if temp.exists(): temp.unlink()
        if sha(archive) != ARCHIVE_SHA: raise ValueError('Archive checksum mismatch')
        atomic(out/'ARCHIVE_VERIFIED.json', {'url': ARCHIVE_URL, 'sha256': ARCHIVE_SHA, 'bytes': archive.stat().st_size})
        status.update(stage='generate_wiki', progress=1)
        sys.dont_write_bytecode = True; sys.path.insert(0, c['code'])
        from jev.case_wikiracing import build_dataset
        wiki = out/'wiki'; expected = json.loads((root/'provenance/original-manifests/wikiracing.json').read_text())
        valid = wiki.exists() and all((wiki/n).exists() and sha(wiki/n)==h for n,h in expected['files_sha256'].items())
        if not valid: build_dataset(wiki, archive_path=archive, targets=300, pairs_per_target=12, max_candidates=12, seed=42)
        for name, h in expected['files_sha256'].items():
            if sha(wiki/name) != h: raise ValueError('Generated original Wiki hash mismatch: '+name)
        atomic(out/'WIKI_VERIFIED.json', {'files_sha256': expected['files_sha256']})
        status.update(stage='restore_mixture', progress=2)
        spec = importlib.util.spec_from_file_location('published_restore', c['restore_script'])
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        target = out/'release-v2'; details=export['configs']['release-v2-redistributable']
        # Exact successful stages are reusable; partial writes are never accepted.
        if target.exists():
            for split, info in details['splits'].items():
                f=target/(split+'.jsonl')
                if not f.exists() or sha(f)!=info['original_sha256']: raise ValueError('Partial restored mixture needs reviewed fresh output')
        else: module.restore(root, 'release-v2-redistributable', wiki, target)
        results = {}; missing = {}
        for split, info in details['splits'].items():
            f=target/(split+'.jsonl'); rows=[json.loads(line) for line in f.read_text().splitlines()]
            if sha(f)!=info['original_sha256'] or len(rows)!=info['original_count']: raise ValueError('Restored split differs')
            results[split]={'count':len(rows),'sha256':sha(f)}
            if split in ('test','ood'):
                positions=info['excluded_original_line_numbers']; selected=[rows[i-1] for i in positions]
                if any(r['source']!='wikispeedia-v1' for r in selected): raise ValueError('Wrong missing-row source')
                path=out/(split+'-missing-wiki.jsonl')
                path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
                missing[split]={'count':len(selected),'original_line_numbers':positions,'ids':[r['id'] for r in selected], 'sha256':sha(path)}
        verify(c['files'])
        if sha(cp)!=ch: raise ValueError('Config changed')
        report={'status':'RESTORED_EXACT_ORIGINAL','config_sha256':ch,'splits':results,'missing_public_rows':missing,
                'scope':'Exact data restoration only; no model inference, old-full benchmark score or training benefit.'}
        atomic(out/'report.json', report); outputs={'report.json':sha(out/'report.json')}; rc=0; status.update(stage='completed',progress=3)
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc); status['stage']='failed'; raise
    finally:
        stop.set(); th.join(); terminal={'rc':rc,'error':error,'config_sha256':ch,'outputs':outputs,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status}
        atomic(out/'STATUS.json',terminal); atomic(out/'RESTORE_COMPLETE.json',terminal)


if __name__ == '__main__': main()
