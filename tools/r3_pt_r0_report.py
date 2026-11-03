"""Rebuild PT's R0-configuration B-4 diagnostics from complete source readouts.

This CPU library performs source/metric checks, not execution admission. Callers
must verify the pinned scorer closure, guarded execution/release, contract and
R0 report provenance before use. A hash binds a baseline report; it cannot prove
that the baseline was source-verified. No test, FINAL, approval or marker writes.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

PT_MODEL = '/mnt/cephfs/xingchao/models/jev/Qwen__Qwen3.5-0.8B'
ROLES = ('primary', 'empty_input', 'question_only')
EXPECTED_COUNT = 102654


def require(ok, why):
    if not ok:
        raise ValueError(why)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   allow_nan=False).encode()).hexdigest()


def verify_task_manifest(path, entry):
    """Match build_tasks.py's serialized-line hash (LF excluded) and count.

    This lives in the pinned CPU consumer because the original frozen R0
    selection module predates this helper. No metric implementation is changed.
    """
    digest, count = hashlib.sha256(), 0
    with Path(path).open('rb') as stream:
        for line in stream:
            require(line.endswith(b'\n') and line != b'\n',
                    'Track T task has malformed line framing')
            digest.update(line[:-1]); count += 1
    require(digest.hexdigest() == entry['sha256'] and count == entry['records'],
            'Track T input differs from the builder manifest')
    return {'records': count, 'builder_sha256': digest.hexdigest()}


def pinned_json(entry):
    require(set(entry) == {'path', 'sha256'}, 'artifact descriptor differs')
    path = Path(entry['path'])
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe evidence path')
    require(sha(path) == entry['sha256'], 'bound artifact changed')
    return load(path)


def verify_base_bytes(run, contract, header):
    """Rehash every base file and bind both producers to that exact inventory.

    Producer spec pins must themselves be bound to verified executions by the
    caller; this does not establish execution history from JSON declarations.
    """
    source = Path(__file__).with_name('r3_model_inventory.py')
    loader = importlib.util.spec_from_file_location('pt_base_inventory', source)
    M = importlib.util.module_from_spec(loader); loader.loader.exec_module(M)
    doc = pinned_json(contract['base_inventory'])
    proof = M.verify(PT_MODEL, doc['inventory'], doc['inventory_sha256'])
    expected = {str(Path(PT_MODEL) / rel): value['sha256']
                for rel, value in doc['inventory']['files'].items()}
    for key, profile, schema in (
            ('pt_scoring_spec', 'track_t_pt_r0', 'r3-posttrain-dev-spec-v1'),
            ('r0_scoring_spec', 'track_t_r0', 'r3-baseline-dev-spec-v1')):
        spec = pinned_json(contract[key])
        require(spec.get('schema') == schema and spec.get('evaluation_profile') == profile
                and spec.get('model') == PT_MODEL, 'base scoring specification differs')
        if key == 'pt_scoring_spec':
            require(Path(contract[key]['path']) == Path(run) / 'plan.json'
                    and spec.get('adapter') == header['model']['path'], 'PT scoring owner differs')
        actual = {name: digest for name, digest in spec['files'].items()
                  if Path(name).is_relative_to(PT_MODEL)}
        require(actual == expected, 'producer base file inventory differs: ' + key)
    return {**proof, 'artifact_sha256': contract['base_inventory']['sha256'],
            'producer_spec_sha256': {key: contract[key]['sha256']
                                    for key in ('pt_scoring_spec', 'r0_scoring_spec')}}


def header_checks(receipt, contract, deps):
    require(receipt.get('schema') == 'r3-scoring-receipt-v1'
            and receipt.get('scientific_acceptance') is False, 'receipt scope differs')
    h = receipt['header']
    require(h.get('arm') == 'K1-PT' and h.get('stages') == 't_score'
            and h.get('track_t_config') == 'r0', 'PT R0 scoring required')
    require(h.get('partitions') in (['dev', 'calibration'], ['calibration', 'dev']),
            'candidate test forbidden')
    require(h.get('limit') == 0 and h.get('limit_groups') == 0
            and not h.get('dry_run_warnings'), 'partial or diagnostic producer refused')
    require(h.get('primary_input_mode') == 'full' and h.get('render') == 'record_name',
            'input/render differs')
    require(h.get('dtype') == 'float32' and not deps['provenance_r3']._scorer_problems(h.get('scorer')),
            'scorer not of record')
    scorer = h['scorer']
    require(scorer.get('mode') == 'rightpad' and scorer.get('dtype') == 'float32'
            and scorer.get('token_budget') == 16384 and scorer.get('hf32', {}).get('hf32') is False,
            'frozen scorer differs')
    p = deps['prompt']
    require(h.get('prompt_version') == p.PROMPT_VERSION and h.get('prompt_format') == p.PROMPT_FORMAT,
            'prompt differs')
    require(h.get('track_t_sources', '').split(',') == ['typed-decisions', 'openjev-synth', 'akhilaaa3'],
            'sources differ')
    require(h.get('model') == contract['model'] and h['model'].get('base_path') == PT_MODEL
            and h['model'].get('kind') == 'lora-adapter-unmerged', 'PT model differs')
    expected_data = {k: v for k, v in contract['data'].items() if Path(k).name != 'manifest.json'}
    require(h.get('data_files') == expected_data, 'producer data differs')
    return h


def control_objective(plan):
    """Read the recorded canonical argv; formal plans need no duplicate arm key."""
    command = plan.get('command')
    require(isinstance(command, list) and all(type(x) is str for x in command)
            and command[:3] == ['python3', '-P', '/workspace/train_r3.py'],
            'control training command differs')
    valued = {'--out', '--arm', '--seed', '--model-path', '--epochs', '--total-steps',
              '--stop-after', '--lr', '--lora-r', '--lora-alpha', '--lora-dropout',
              '--expect-pairs', '--kernel', '--micro-tokens', '--max-len',
              '--save-every', '--symbol-file', '--symbol-n', '--limit-rows', '--device'}
    switches = {'--grad-ckpt', '--full-logits', '--drop-state', '--no-merge'}
    parsed = {}; i = 3
    while i < len(command):
        flag = command[i]
        require(flag in valued or flag in switches, 'unknown or noncanonical training flag')
        require(flag not in parsed, 'duplicate training flag')
        if flag in switches:
            parsed[flag] = True; i += 1
        else:
            require(i + 1 < len(command) and not command[i + 1].startswith('-'), 'missing training value')
            parsed[flag] = command[i + 1]; i += 2
    require(parsed.get('--arm') == 'k1' and plan.get('arm', 'k1') == 'k1', 'training objective differs')
    require(type(plan.get('seed')) is int and parsed.get('--seed') == str(plan['seed'])
            and parsed.get('--model-path') == plan.get('model'), 'training argv identity differs')
    return 'k1'


def training_checks(receipt, contract, E):
    identity = E.train_identity(receipt)
    require(identity.get('arm') == 'K1-PT' and type(identity.get('seed')) is int
            and identity['seed'] in (2, 3), 'PT seed/arm differs')
    descriptor = contract['training_plan']
    path = Path(descriptor['path'])
    require(path == Path(identity['training_manifest']).parent / 'plan.json'
            and sha(path) == descriptor['sha256'], 'control training plan unbound')
    plan = load(path)
    require(plan.get('control_arm') == 'K1-PT' and control_objective(plan) == 'k1'
            and plan.get('model') == PT_MODEL and type(plan.get('seed')) is int
            and plan['seed'] == identity['seed'] and '--drop-state' not in plan.get('command', []),
            'control training plan differs')
    manifest = load(identity['training_manifest'])
    require(manifest.get('arm') == manifest.get('args', {}).get('arm') == 'k1'
            and manifest.get('args', {}).get('drop_state') is False
            and manifest.get('total_steps') == 3116
            and manifest.get('summary', {}).get('final_step') == 3116,
            'full PT training required')
    return identity


def scorer_protocol(header):
    """Validate each producer identity, then retain every nonidentity field."""
    scorer, model = header.get('scorer'), header.get('model', {})
    require(isinstance(scorer, dict) and 'model_path' in scorer and 'adapter' in scorer,
            'scorer protocol differs: missing producer identity')
    require(model.get('kind') in ('checkpoint', 'lora-adapter-unmerged'),
            'scorer protocol differs: unsupported model kind')
    require(scorer['model_path'] == model.get('base_path'),
            'scorer protocol differs: model identity')
    expected_adapter = model.get('path') if model['kind'] == 'lora-adapter-unmerged' else None
    require(scorer['adapter'] == expected_adapter,
            'scorer protocol differs: adapter identity')
    return {key: value for key, value in scorer.items() if key not in ('model_path', 'adapter')}


def compare_baseline(header, block, baseline, baseline_pin, T):
    """Caller must source-verify baseline separately; SHA alone is not proof."""
    require(canonical_sha(baseline) == baseline_pin, 'baseline report binding differs')
    b = baseline['header']
    require(b.get('arm') == 'K0' and b.get('model', {}).get('kind') == 'checkpoint'
            and b['model'].get('path') == PT_MODEL and b['model'].get('base_path') == PT_MODEL,
            'same instruct K0 baseline required')
    require(b['model'].get('base_revision') == header['model'].get('base_revision'),
            'base revision differs')
    for field in ('track_t_config', 'prompt_version', 'prompt_format', 'data_files',
                  'primary_input_mode', 'render', 'dtype'):
        require(b.get(field) == header.get(field), 'baseline protocol differs: ' + field)
    require(scorer_protocol(header) == scorer_protocol(b), 'baseline protocol differs: scorer')
    base = baseline['track_t']
    require(base.get('config') == 'r0' and not base.get('missing_roles')
            and base.get('tie_rule') == block.get('tie_rule')
            and base.get('tau_splitter') == block.get('tau_splitter'), 'baseline R0 configuration differs')
    # Metadata is restored from source-bound headers, not optional cached blocks.
    trained, untuned = copy.deepcopy(block), copy.deepcopy(base)
    for value, h in ((trained, header), (untuned, b)):
        value['meta'] = {**value.get('meta', {}), 'prompt_version': h['prompt_version']}
    lines = T.b4_lines(trained, untuned, half='all')
    require(bool(lines), 'B-4 population absent')
    for line in lines:
        # Preserve the frozen metric's own valid denominators. Equality is not
        # an additional pre-registered gate; retain both counts for comparison.
        if not line.get('admissible'):
            require(line.get('verdict') == 'not admissible', 'B-1 refusal lost')
    return lines


def rebuild(run, contract, deps, baseline, baseline_pin):
    """Return a per-seed diagnostic; no file is published and no gate is granted.

    deps supplies caller-pinned scientific modules. contract contains the exact
    model and freshly verified base_model identities, task file hashes, and pinned
    training_plan path/SHA, base_inventory descriptor ({inventory, inventory_sha256}),
    and pinned pt_scoring_spec / r0_scoring_spec descriptors. baseline
    is a separately source-verified R0 report and baseline_pin its canonical SHA.
    """
    run = Path(run); out = run / 'results'
    C, T, E, PV, RC = (deps[x] for x in ('core_r3', 'track_t_r3', 'selection_evidence_r3', 'provenance_r3', 'common'))
    receipt_path = out / 'SCORING_RECEIPT.track_t_pt_r0.json'
    receipt = load(receipt_path); h = header_checks(receipt, contract, deps)
    require(baseline.get('header', {}).get('model') == contract['base_model'],
            'baseline differs from caller-verified base identity')
    require(contract['base_model'].get('kind') == 'checkpoint'
            and contract['base_model'].get('path') == PT_MODEL
            and isinstance(contract['base_model'].get('sha256'), str)
            and len(contract['base_model']['sha256']) == 64, 'base identity absent')
    require(load(out / 'EVAL_COMPLETE.track_t_pt_r0.json').get('exit_code') == 0,
            'producer terminal failed')
    base_proof = verify_base_bytes(run, contract, h)
    identity = training_checks(receipt, contract, E)
    evidence = E.verify_run(str(out), receipt)
    require(evidence.get('manifests') and all(m['scorer'] == h['scorer'] for m in evidence['manifests'].values()),
            'producer scorer descriptors differ')
    manifests = [p for p in contract['data'] if Path(p).name == 'manifest.json']
    require(len(manifests) == 1, 'one task manifest required')
    for filename, digest in contract['data'].items():
        require(sha(filename) == digest, 'task dependency changed: ' + filename)
    root = Path(manifests[0]).parent; manifest = load(manifests[0]); records = []; paths = []
    for task in ('T1', 'T2', 'T3'):
        for source in RC.SOURCE_FILES:
            if task == 'T3' and source != 'typed-decisions':
                continue
            filename = RC.task_path(str(root), task, source); paths.append(filename)
            require(filename in contract['data'], 'required task input absent')
            verify_task_manifest(filename, manifest['tasks'][RC.TASK_DIRS[task]][source])
            records.extend(RC.load_records(filename))
    require(set(contract['data']) == set(paths + manifests), 'extra task input')
    needed = T.records_needed(records, T.CONFIG_R0)
    require(len(needed) == EXPECTED_COUNT and len({r['key'] for r in needed}) == EXPECTED_COUNT,
            'full R0 population differs')
    by_role = {role: [] for role in ROLES}; counts = {}
    for path in sorted((out / 'trackt/readouts').glob('*.jsonl')):
        role = path.name.split('__')[0]
        require(role in by_role, 'unexpected readout role')
        by_role[role].extend(C.read_jsonl(str(path)))
    for role in ROLES:
        ordered = E.validate_population(by_role[role], needed, lambda r: r['key'])
        counts[role] = len(ordered)
        by_role[role] = [T.make_readout(row, stored['s']) for row, stored in zip(needed, ordered)]
    by_role.update(T.constant_and_uniform_rows(records, needed))
    block = T.build_track_t(by_role, records, T.CONFIG_R0)
    require(block.get('config') == 'r0' and not block.get('missing_roles'), 'incomplete R0 block')
    lines = compare_baseline(h, block, baseline, baseline_pin, T)
    return {'schema': 'r3-pt-r0-diagnostics-v1', 'header': copy.deepcopy(h), 'training': identity,
            'track_t': block, 'B-4': {'half': 'all', 'lines': lines, 'baseline_canonical_sha256': baseline_pin,
                'denominator_policy': 'Report each model denominator separately; no added equality gate.'},
            'cpu_rebuild': {'producer_receipt_sha256': sha(receipt_path), 'per_role': counts, 'provenance': evidence, 'base_bytes': base_proof},
            'scientific_acceptance': False, 'publication_authorized': False, 'candidate_test_read': False,
            'limitations': ['Caller must verify frozen module origins and guarded execution/release.',
                            'Baseline report source verification is an external prerequisite; its hash is only a binding.',
                            'Per-seed B-4 diagnostics; both seeds must pass before any arm-level pass.']}
