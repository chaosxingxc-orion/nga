#!/usr/bin/env python3
"""Reuse native evaluator with exact original OOD admission."""
import importlib.util
from pathlib import Path
def sibling(n):
    s=importlib.util.spec_from_file_location(n,Path(__file__).with_name(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if __name__=='__main__':sibling('openjev_reference_eval').main(sibling('openjev_ood_protocol').validate_dataset)
