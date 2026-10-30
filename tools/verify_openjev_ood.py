#!/usr/bin/env python3
"""Original OOD independent artifact and metric audit."""
import argparse,importlib.util
from pathlib import Path
def sibling(n):
    s=importlib.util.spec_from_file_location(n,Path(__file__).with_name(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify(path):
    v=sibling('verify_reference_openjev');c=v.load(path)
    required={str(Path(__file__).with_name(n).resolve()) for n in ['verify_openjev_ood.py','verify_reference_openjev.py','openjev_ood_protocol.py','openjev_ood_eval.py']}
    v.require(required<=set(c['files']),'OOD executable dependency omitted')
    r=v.verify(path,sibling('openjev_ood_protocol').validate_dataset);r['scope']='Original complete OOD 15920 rows; native methods and artifact audit, not training benefit or Astra approval.';return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();sibling('verify_reference_openjev').atomic(a.out,verify(a.config))
