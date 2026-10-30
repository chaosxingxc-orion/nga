#!/usr/bin/env python3
"""E24 entrypoint: same native evaluator, exact supplementary dataset validator."""
import importlib.util
from pathlib import Path


def sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == '__main__':
    driver = sibling('openjev_reference_eval')
    protocol = sibling('openjev_original_protocol')
    driver.main(protocol.validate_dataset)
