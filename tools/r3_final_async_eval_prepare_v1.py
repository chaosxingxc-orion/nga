"""Append verification-only scored-result recovery to a new generated testlock.

The original verified-stage recovery stays unchanged. This source builder never
opens TEST or produces authority. A future CPU entry authenticates release before
calling the new verification-only entry. No scoring ticket escapes that entry.
"""
import ast
import hashlib
import importlib.util
from pathlib import Path
_spec=importlib.util.spec_from_file_location('original_prepare',Path(__file__).with_name('r3_final_eval_prepare.py'))
P=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(P)

def extension():
    text=P.RECOVERY
    for before,after in (
        ('def verify_reserved_test_result(', 'def verify_scored_test_result('),
        ("'TEST-STAGED-RESULTS.json'", "'TEST-SCORED-UNVERIFIED.json'"),
        ("'r3-test-staged-results-v1'", "'r3-test-scored-unverified-v1'")):
        if text.count(before)!=1:raise ValueError('recovery transformation anchor differs')
        text=text.replace(before,after,1)
    ast.parse(text);return text

def prepare(source,output,expected_sha256):
    source=Path(source);output=Path(output);raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('prepared testlock source changed')
    if raw.decode().count('def verify_reserved_test_result(')!=1 or 'def verify_scored_test_result(' in raw.decode():raise ValueError('wrong generated testlock')
    result=raw.decode()+'\n'+extension();ast.parse(result)
    with output.open('x') as f:f.write(result)
    return hashlib.sha256(output.read_bytes()).hexdigest()
