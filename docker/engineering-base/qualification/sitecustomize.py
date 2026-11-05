"""Qualification image only: intercept exact production family/trainer module loads."""
import importlib.util, os
from pathlib import Path

_original_spec = importlib.util.spec_from_file_location

def _spec(name, location, *args, **kwargs):
    spec = _original_spec(name, location, *args, **kwargs)
    targets = {'nga_training_family_v2': '/opt/nga/components/training/family.py',
               'nga_family_trainer': '/opt/nga/source/train/train_r3.py'}
    if name in targets and str(location) == targets[name]:
        execute = spec.loader.exec_module
        def wrapped(module):
            execute(module)
            if name == 'nga_training_family_v2':
                from nga_qualification_fixture import patch_family
                patch_family(module)
            else:
                from nga_qualification_fixture import patch_trainer
                patch_trainer(module)
        spec.loader.exec_module = wrapped
    return spec
importlib.util.spec_from_file_location = _spec
