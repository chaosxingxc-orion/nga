#!/usr/bin/env python3
"""Build the exact provider-v3 asset from a reviewed source and pin manifest."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('configured_resource', Path(__file__).with_name('unified_configured_resource_v1.py'))
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
PINS = wrapper.CLOSURE
README = '''# provider-v3 runtime\n\nExact six-file runtime from engineering-resource-strict-json-astra-20261105-v3/verification.\nThe review handoff is ACCEPT_SCOPED_SIMULATION_ONLY; it does not qualify physical deployment\nor compatibility with newer trained hosts. inventory.json records SHA-256 for every runtime file.\nThe wrapper independently pins the same bytes; inventory is not an authority for executable code.\nRebuild with tools/build_resource_provider_v3.py and the review's PINS.json and verification root.\n'''


def build(manifest, source, destination):
    doc = json.loads(Path(manifest).read_text())
    entries = doc['verification_copy']
    by_suffix = {}
    for rel in PINS:
        matches = [x for x in entries if x['path'].endswith('/verification/' + rel)]
        if len(matches) != 1 or matches[0]['sha256'] != PINS[rel]:
            raise ValueError('manifest does not identify exact reviewed closure: ' + rel)
        by_suffix[rel] = matches[0]
    source = Path(source).absolute()
    dest = Path(destination).absolute()
    if dest.exists() or dest.is_symlink():
        raise ValueError('destination already exists')
    if not dest.parent.is_dir() or any(p.is_symlink() for p in (source, *source.parents, dest.parent, *dest.parent.parents)):
        raise ValueError('invalid source or destination')
    payload = {}
    for rel, digest in PINS.items():
        path = source / rel
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError('source file invalid: ' + rel)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest or len(raw) != by_suffix[rel]['bytes']:
            raise ValueError('source file changed: ' + rel)
        payload[rel] = raw
    with tempfile.TemporaryDirectory(prefix='.provider-v3-build-', dir=dest.parent) as temp:
        stage = Path(temp)/'asset'
        stage.mkdir()
        for rel, raw in payload.items():
            path = stage/rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (stage/'inventory.json').write_text(json.dumps({'schema':'resource-provider-v3-inventory-v1', 'files':PINS}, indent=2, sort_keys=True)+'\n')
        (stage/'README.md').write_text(README)
        stage.rename(dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pin-manifest', required=True)
    p.add_argument('--source-root', required=True)
    p.add_argument('--output', required=True, help='new directory; never overwrites')
    a = p.parse_args()
    build(a.pin_manifest, a.source_root, a.output)


if __name__ == '__main__':
    main()
