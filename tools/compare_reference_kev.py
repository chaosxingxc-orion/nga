#!/usr/bin/env python3
"""Describe native Kev reproduction deltas; no inferred equivalence threshold."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def softmax(z):
    e = [math.exp(v-max(z)) for v in z]
    return [v/sum(e) for v in e]


def compare(root, upstream):
    terminal = load(root/'REFERENCE_COMPLETE.json')
    if type(terminal.get('rc')) is not int or terminal['rc'] != 0:
        raise ValueError('Complete successful reference run required')
    release = upstream/'runs/release/kev-08b-r15.json'
    published = load(release)['candidate']
    result = {'kind': 'descriptive_comparison_not_equivalence_gate',
              'sources': {str(release): sha(release)}, 'suites': {}}
    for name, panel in [('decision-v7', 'locked_decision'), ('transfer-v4', 'locked_transfer')]:
        report_path = root/name/'report.json'
        if sha(report_path) != terminal['suites'][name]['report_sha256']:
            raise ValueError('Report binding changed')
        report = load(report_path)
        local, original = report['native']['clean'], published[panel]
        if local['n'] != original['n'] or report['native_serving_temperature'] != published['temperature']:
            raise ValueError('Published/local denominator or temperature mismatch')
        entry = {'n': local['n'], 'temperature': published['temperature'],
                 'published': original,
                 'local': {k:local[k] for k in original},
                 'local_minus_published': {k:local[k]-original[k] for k in original if k!='n'}}
        native_rows = root/name/'rows.json'
        if sha(native_rows) != terminal['suites'][name]['rows_sha256']:
            raise ValueError('Rows binding changed')
        old_rows = upstream/'runs/locked/kev-08b-r15-ungated'/('decision' if name=='decision-v7' else 'transfer')/'rows.json'
        if not old_rows.exists():
            entry['paired_comparison'] = {'status': 'upstream_rows_missing', 'expected_path': str(old_rows)}
        else:
            old = load(old_rows)
            new = load(native_rows)
            def index(rows):
                d = {(r['id'],r['question']):r for r in rows}
                if len(d)!=len(rows): raise ValueError('Duplicate upstream/local keys')
                return d
            old, new = index(old), index(new)
            if set(old)!=set(new): raise ValueError('Upstream/local question IDs differ')
            max_dp, flips, bin_changes = 0., 0, 0
            clean_count = 0
            for key, a in old.items():
                b = new[key]
                if any(a[k]!=b[k] for k in ('keys','label','variant','source')):
                    raise ValueError('Upstream/local metadata differs')
                if a['variant']!='clean' or a['source']=='unknowable': continue
                clean_count += 1
                temp = a.get('inference_temperature') or 1.
                p = softmax([v*temp/published['temperature'] for v in a['logits']])
                q = b['p']
                max_dp = max(max_dp, max(abs(x-y) for x,y in zip(p,q)))
                flips += max(range(len(p)),key=p.__getitem__)!=max(range(len(q)),key=q.__getitem__)
                # Descriptive equal-width bin movement, not a correctness criterion.
                bin_changes += min(9,int(max(p)*10))!=min(9,int(max(q)*10))
            entry['paired_comparison'] = {'status': 'keys_and_metadata_aligned',
                'all_questions':len(old),'clean_questions':clean_count,
                'clean_max_abs_probability_delta':max_dp,'clean_argmax_disagreements':flips,
                'clean_confidence_bin_changes':bin_changes}
            result['sources'][str(old_rows)] = sha(old_rows)
        result['sources'][str(report_path)] = sha(report_path)
        result['suites'][name] = entry
    return result


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--upstream',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    result=compare(a.run,a.upstream)
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2,allow_nan=False))
