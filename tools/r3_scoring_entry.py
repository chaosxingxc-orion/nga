#!/usr/bin/env python3
"""Run frozen readout stages and retain the evaluator's own header for CPU selection.

No report-stage metric computation and no test partitions. Installed beside the
frozen evaluator; it does not fabricate readout identities or acceptance.
"""
import json
import os
from pathlib import Path
import re
import sys


def validate(args):
    stages = set(args.stages.split(','))
    partitions = set(args.partitions.split(',')) if isinstance(args.partitions, str) else set(args.partitions)
    if not stages or not stages <= {'k_score', 't_score'}:
        raise ValueError('only scoring stages are admitted')
    if not partitions or not partitions <= {'dev', 'calibration'}:
        raise ValueError('only dev/calibration partitions are admitted')
    tag = getattr(args, 'unit_tag', '') or 'main'
    if not re.fullmatch(r'[A-Za-z0-9_-]+', tag):
        raise ValueError('invalid receipt tag')
    return tag


def receipt_runner(original):
    def run(args, scorer):
        tag = validate(args)
        report = original(args, scorer)
        if not isinstance(report, dict) or not isinstance(report.get('header'), dict):
            raise RuntimeError('successful evaluator did not return its header')
        receipt = {'schema': 'r3-scoring-receipt-v1', 'header': report['header'],
                   'track_k': {'partitions': {}}, 'scientific_acceptance': False,
                   'scope': 'producer header only; CPU must verify and rebuild metrics from readouts'}
        out = Path(args.out)
        target = out / f'SCORING_RECEIPT.{tag}.json'
        temp = target.with_suffix('.pending')
        temp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        os.replace(temp, target)
        return report
    return run


def main():
    # The entry is copied into the frozen r3_code directory and mounted at its
    # original absolute path, like eval_r3.py. Import paths never include data.
    root = Path(__file__).resolve().parent
    if not (root / 'eval_r3.py').is_file():
        raise RuntimeError('entry must be installed beside the frozen evaluator')
    sys.path.insert(0, str(root))
    sys.path.insert(0, '/mnt/cephfs/xingchao/experiments/jev/r0_code')
    import full_eval_r3
    import eval_r3
    full_eval_r3.run_full_marked = receipt_runner(full_eval_r3.run_full_marked)
    eval_r3.main()


if __name__ == '__main__':
    main()
