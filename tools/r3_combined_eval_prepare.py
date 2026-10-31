#!/usr/bin/env python3
"""Freeze combined Track K/T readout generation with no report-half metrics."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

BASE = Path('/mnt/cephfs/xingchao/experiments/jev')
REPO = Path(__file__).resolve().parent.parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(out):
    K, T = module('r3_eval_prepare'), module('r3_track_t_prepare')
    normative = json.loads((BASE / 'manifest.json').read_text())
    task_files = [BASE / directory / (source + '.jsonl')
                  for task, directory in T.TASKS.items()
                  for source in (T.SOURCES if task != 'T3' else ('typed-decisions',))]
    for path in task_files:
        entry = normative['tasks'][path.parent.name][path.stem]
        if T.builder_identity(path) != {k: entry[k] for k in ('sha256', 'records')}:
            raise ValueError('Track T builder identity differs: ' + str(path))
    K.prepare(out)
    manifest = out / 'manifest.json'
    doc = json.loads(manifest.read_text())
    for name, source in [('selection_evidence_r3.py', REPO / 'experiments/r3_sft/r3_code/selection_evidence_r3.py'),
                         ('r3_scoring_entry.py', REPO / 'tools/r3_scoring_entry.py')]:
        target = out / 'r3_code' / name
        shutil.copy2(source, target)
        doc['code'][str(BASE / 'r3_code' / name)] = {'snapshot': str(target), 'sha256': sha(target)}
    doc['data'].update({str(p): sha(p) for p in [BASE / 'manifest.json'] + task_files})
    command = doc['command_template']
    command[2] = str(BASE / 'r3_code/r3_scoring_entry.py')
    command[command.index('--stages') + 1] = 'k_score,t_score'
    command += ['--unit-tag', 'track_kt', '--track-t-config', 'r3', '--data-root', str(BASE),
                '--track-t-sources', ','.join(T.SOURCES), '--shard', '0', '--num-shards', '1']
    doc.update(evaluation_profile='track_kt',
               scope='Full Track K dev/calibration and Track T raw scoring; only selection-half CPU metrics may inform choices',
               pending=['completed adapter or K0 identity', 'guarded execution', 'verified selection-only CPU report', 'independent review'],
               split_policy={'report_half_raw_scored': True, 'report_half_metrics_computed': False,
                             'selection_only': True, 'raw_readouts_not_for_candidate_decisions': True})
    manifest.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    return {'out': str(out), 'sha256': sha(manifest), 'data_files': len(doc['data']),
            'modules': len(doc['code']), 'ready_to_score': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    print(json.dumps(prepare(Path(parser.parse_args().out))))
