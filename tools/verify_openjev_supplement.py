#!/usr/bin/env python3
"""Independent supplementary artifact audit; no inference/metric imports."""
import argparse
import importlib.util
from pathlib import Path


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(config):
    v = sibling('verify_reference_openjev')
    p = sibling('openjev_original_protocol')
    c = v.load(config)
    needed = {str(Path(__file__).resolve()), str(Path(__file__).with_name('verify_reference_openjev.py').resolve()),
              str(Path(__file__).with_name('openjev_original_protocol.py').resolve()),
              str(Path(c['out'], 'openjev_supplement_eval.py').resolve())}
    v.require(needed <= set(c['files']), 'Supplement executable dependencies omitted')
    result = v.verify(config, p.validate_dataset)
    result['scope'] = '176-row exact original-test supplement only; full-test result requires separately verified join.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    sibling('verify_reference_openjev').atomic(args.out, verify(args.config))
