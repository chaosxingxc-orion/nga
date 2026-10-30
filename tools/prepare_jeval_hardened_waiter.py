#!/usr/bin/env python3
"""Prepare a new, unapproved CPU waiter generation without launching containers.

The previous plan supplies unchanged model and finisher identities. Output must
be a new directory; existing generations and production sources are never edited.
The generated launch.py is an exact copy of the repository launcher, whose
location beside plan.json is part of its frozen deployment contract.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def prepare(previous_plan, output, container, tools_directory, amendment):
    previous_plan = Path(previous_plan).resolve()
    output = Path(output).resolve()
    tools_directory = Path(tools_directory).resolve()
    amendment = Path(amendment).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', container):
        raise ValueError('Invalid container name')
    plan = json.loads(previous_plan.read_text())
    if plan['readonly_sources'] is not True:
        raise ValueError('Previous plan is not read-only')
    if sha(plan['config']) != plan['config_sha256']:
        raise ValueError('Previous source config changed')
    output.mkdir()  # Intentionally rejects every existing output generation.
    for name in ['jeval_hardened_waiter.py', 'test_jeval_hardened_waiter.py',
                 'audit_jeval_inference_hardened.py', 'test_launch_jeval_hardened_waiter.py',
                 'prepare_jeval_hardened_waiter.py', 'launch_jeval_hardened_waiter.py',
                 'test_jeval_inference_hardened.py']:
        shutil.copy2(tools_directory / name, output / name)
    shutil.copy2(tools_directory / 'launch_jeval_hardened_waiter.py', output / 'launch.py')
    shutil.copy2(amendment, output / amendment.name)
    preregistration = Path(plan['preregistration'])
    shutil.copy2(preregistration, output / preregistration.name)
    spec = json.loads(Path(plan['container_spec']).read_text())
    spec['Config']['Cmd'] = [str(output / 'run.sh')]
    spec['HostConfig']['Binds'] = ['/mnt/cephfs:/mnt/cephfs:ro',
                                  str(output) + ':' + str(output) + ':rw',
                                  '/var/run/docker.sock:/var/run/docker.sock:ro']
    write_json(output / 'CONTAINER_SPEC.json', spec)
    plan.update(out=str(output), container=container,
                auditor=str(output / 'audit_jeval_inference_hardened.py'),
                wrapper=str(output / 'run.sh'),
                container_spec=str(output / 'CONTAINER_SPEC.json'),
                preregistration=str(output / preregistration.name))
    command = shlex.join(['python3', '-P', str(output / 'jeval_hardened_waiter.py'),
                          '--plan', str(output / 'plan.json')])
    (output / 'run.sh').write_text(
        '#!/bin/bash\nset -uo pipefail\n' + command + ' >> '
        + shlex.quote(str(output / 'run.log')) + ' 2>&1\nrc=$?\n'
        + 'printf \'rc=%s utc=%s\\n\' "$rc" "$(date -u +%FT%TZ)" > '
        + shlex.quote(str(output / 'EXIT')) + '\nexit "$rc"\n')
    for name, extra in [('LAUNCH_EXACT.sh', []), ('RESUME_EXACT.sh', ['--resume'])]:
        (output / name).write_text('#!/bin/bash\nset -e\n' + shlex.join(
            ['python3', '-I', str(output / 'launch.py')] + extra) + '\n')
    for source in output.glob('*.py'):
        compile(source.read_bytes(), str(source), 'exec')
    for script in output.glob('*.sh'):
        subprocess.run(['bash', '-n', str(script)], check=True)
    source_run = Path(plan['config']).parent
    frozen = [p for p in output.iterdir() if p.is_file()] + [
        Path(plan['config']), source_run / 'run.sh',
        Path(str(source_run) + '_finish') / 'run.sh']
    plan['files'] = {str(path): sha(path) for path in frozen}
    write_json(output / 'plan.json', plan)
    return dict(plan=str(output / 'plan.json'), sha256=sha(output / 'plan.json'),
                files=len(frozen), sources={k: v['container_id']
                                           for k, v in plan['sources'].items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--tools-directory', type=Path, default=Path(__file__).parent)
    parser.add_argument('--amendment', type=Path, default=Path(__file__).parents[1]
                        / 'experiments/JEVAL-AUDIT-AMENDMENT-2026-10-30.md')
    args = parser.parse_args()
    print(json.dumps(prepare(args.previous_plan, args.out, args.container,
                             args.tools_directory, args.amendment)))


if __name__ == '__main__':
    main()
