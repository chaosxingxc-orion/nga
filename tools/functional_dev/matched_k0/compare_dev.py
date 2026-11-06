#!/usr/bin/env python3
"""CPU-only RC1 DEV consumer. Standard library; never imports a model or reads weights.
Exit 0: all lanes validated; 2: pending/incomplete; 1: contradiction.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
DEFAULT_CATALOG = HERE.parent / 'rc1-base-reuse/BASE-REUSE.json'
SUITES = ('decision-v7', 'transfer-v4')

class Contradiction(ValueError):
    pass

class Pending(RuntimeError):
    pass

def require(ok, message):
    if not ok:
        raise Contradiction(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(obj, ascii=False):
    return digest(json.dumps(obj, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=ascii, allow_nan=False).encode())

def pairs(items):
    out = {}
    for key, value in items:
        require(key not in out, 'duplicate JSON field: ' + key)
        out[key] = value
    return out

def decode(text):
    value = json.loads(text, object_pairs_hook=pairs,
                       parse_constant=lambda s: (_ for _ in ()).throw(Contradiction('nonfinite JSON: ' + s)))
    finite_tree(value)
    return value

def finite_tree(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'nonfinite numeric value')
    elif isinstance(value, dict):
        for v in value.values(): finite_tree(v)
    elif isinstance(value, list):
        for v in value: finite_tree(v)

def read(path, expected=None):
    path = Path(path)
    try:
        data = path.read_bytes()
    except (FileNotFoundError, PermissionError) as e:
        raise Pending(f'{type(e).__name__}: {path}') from e
    if expected:
        require(digest(data) == expected, 'SHA256 mismatch: ' + str(path))
    return data

def obj(path, expected=None):
    return decode(read(path, expected))

def selective(path, allowed):
    """Skip non-allowlisted top-level values lexically, without decoding Track T.
    Adapted from the validated K0 selective reader; strict duplicate/top-level checks added.
    """
    text = read(path).decode('utf-8')
    dec = json.JSONDecoder(object_pairs_hook=pairs)
    i = 0
    while text[i].isspace(): i += 1
    require(text[i] == '{', 'report must be an object')
    i += 1
    out, seen = {}, set()
    while True:
        while text[i].isspace(): i += 1
        if text[i] == '}':
            require(not text[i+1:].strip(), 'trailing report bytes')
            return out, seen
        key, i = dec.raw_decode(text, i)
        require(isinstance(key, str) and key not in seen, 'duplicate/invalid report key')
        seen.add(key)
        while text[i].isspace(): i += 1
        require(text[i] == ':', 'missing report colon')
        i += 1
        while text[i].isspace(): i += 1
        start = i
        if text[i] in '[{':
            stack, quoted, escaped = [], False, False
            while i < len(text):
                c = text[i]
                if quoted:
                    if escaped: escaped = False
                    elif c == '\\': escaped = True
                    elif c == '"': quoted = False
                elif c == '"': quoted = True
                elif c in '[{': stack.append(c)
                elif c in ']}':
                    require(stack and (stack.pop(), c) in (('[', ']'), ('{', '}')), 'unbalanced report')
                    if not stack:
                        i += 1
                        break
                i += 1
            require(not stack and not quoted, 'truncated report')
        elif text[i] == '"':
            _, i = dec.raw_decode(text, i)
        else:
            while i < len(text) and text[i] not in ',}': i += 1
        if key in allowed:
            out[key] = decode(text[start:i])
        while text[i].isspace(): i += 1
        require(text[i] in ',}', 'invalid report separator')
        if text[i] == ',':
            i += 1
            require(text[i:].lstrip()[:1] != '}', 'trailing report comma')

def jsonl(path, expected=None):
    return [decode(line) for line in read(path, expected).splitlines() if line.strip()]

def qkey(row):
    return str(row['kev']['id']) + '/' + str(row['kev']['qindex'])

def summarize(rows, values):
    def metric(indices):
        n = len(indices)
        correct = sum(values[i]['correct'] for i in indices)
        r0 = sum(values[i]['r0'] for i in indices)
        return {'n': n, 'correct': correct, 'kev_rule_accuracy': correct/n,
                'r0_correct': r0, 'r0_rule_accuracy': r0/n,
                'tie_count': sum(values[i]['tie'] for i in indices)}
    out = metric(list(range(len(rows))))
    for field, dest in [('source', 'by_source'), ('level_type', 'by_level_type')]:
        groups = {}
        for i, r in enumerate(rows): groups.setdefault(r[field], []).append(i)
        out[dest] = {k: metric(v) for k, v in sorted(groups.items())}
    return out

def score_rows(rows, saved, model_sha):
    require(len(rows) == len(saved) > 0, 'wrong population count')
    keys = [qkey(r) for r in rows]
    require(len(set(keys)) == len(keys), 'duplicate frozen population keys')
    require([r['k'] for r in saved] == keys, 'wrong question population/order or duplicate readout')
    values = []
    for row, raw in zip(rows, saved):
        ids = [x['id'] for x in row['levels']]
        require(raw['ids'] == ids and raw['gold'] == row['gold'], 'candidate order/gold mismatch')
        for field in ('source', 'level_type', 'qname'):
            require(raw[field] == row[field], field + ' mismatch')
        require(raw.get('variant', 'original') == row.get('variant', 'original'), 'variant mismatch')
        s = raw['s']
        require(isinstance(s, list) and len(s) == len(ids) > 0 and
                all(type(x) in (int, float) and math.isfinite(x) for x in s), 'malformed/nonfinite score vector')
        gold, arg = ids.index(row['gold']), max(range(len(s)), key=s.__getitem__)
        tie = s.count(max(s)) > 1
        require(raw['gold_index'] == gold and raw['argmax'] == arg and raw['tie'] == tie,
                'saved raw decision contradicts scores')
        require(raw.get('m') == model_sha[:16], 'wrong row model stamp')
        values.append({'correct': int(arg == gold), 'r0': int(arg == gold and not tie), 'tie': int(tie)})
    return values

def compare_headline(actual, saved, label):
    # Check all pre-existing headline numbers, including source/type strata.
    for key in ('n', 'kev_rule_accuracy', 'r0_rule_accuracy', 'tie_count'):
        require(saved[key] == actual[key], 'headline mismatch: ' + label + '/' + key)
    for key in ('by_source', 'by_level_type'):
        require(set(saved[key]) == set(actual[key]), 'headline strata mismatch: ' + label)
        for name in actual[key]: compare_headline_leaf(actual[key][name], saved[key][name], label+'/'+name)

def compare_headline_leaf(a, b, label):
    for key in ('n', 'kev_rule_accuracy', 'r0_rule_accuracy', 'tie_count'):
        require(a[key] == b[key], 'headline mismatch: '+label+'/'+key)

def paired(new, base):
    require(len(new) == len(base) > 0, 'paired count mismatch')
    n = len(new)
    return {'n': n, 'new_correct': sum(new), 'k0_correct': sum(base),
            'dev_delta': (sum(new)-sum(base))/n,
            'k0_wrong_new_right': sum(a == 1 and b == 0 for a,b in zip(new,base)),
            'k0_right_new_wrong': sum(a == 0 and b == 1 for a,b in zip(new,base)),
            'both_right': sum(a == b == 1 for a,b in zip(new,base)),
            'both_wrong': sum(a == b == 0 for a,b in zip(new,base))}

class Consumer:
    def __init__(self, catalog_path, vectors_path=None, source_pins=None):
        self.catalog_path = Path(catalog_path)
        self.catalog = obj(catalog_path)
        self.vectors_path = Path(vectors_path or self.catalog_path.with_name('DEV-VECTORS.json'))
        self.vectors = obj(self.vectors_path)
        self.source_pins = obj(source_pins or self.catalog_path.with_name('SOURCE-PINS.json'))
        c = self.catalog
        require(c['status'] == 'READY_FOR_COMPARISON_INPUT' and not c['checks_summary']['failed'], 'unvalidated K0 catalog')
        self.refs = {r['id']: r for r in c['references']}
        require(len(self.refs) == len(c['references']) == 4, 'duplicate/missing K0 size')
        lanes = c['new_rc1_lanes']
        require(len(lanes) == 8 and len({x['lane'] for x in lanes}) == 8, 'wrong fixed lane roster')
        require({r['size'] for r in self.refs.values()} == {'0.8B','2B','4B','9B'}, 'wrong sizes')
        for size in ('0.8B','2B','4B','9B'):
            group = [x for x in lanes if x['size'] == size]
            require(len(group) == 2 and {x['seed'] for x in group} == {2,3}, 'wrong fixed seeds')
            for lane in group:
                require(self.refs[lane['baseline_id']]['size'] == size, 'wrong same-size K0')
        self.pop = {}
        for path, pin in c['new_contract']['data_pins'].items():
            p = Path(path)
            require(p.name in ('dev.jsonl','dev.variants.jsonl','calibration.jsonl') and p.parent.name in SUITES,
                    'non-DEV/calibration population refused')
            label = p.parent.name + '/' + ('calibration' if p.name == 'calibration.jsonl' else 'dev')
            self.pop[(label, 'variants' if '.variants.' in p.name else 'clean')] = jsonl(p, pin)
        expected = {'decision-v7/dev':1264,'transfer-v4/dev':656,'decision-v7/calibration':1148}
        require(c['new_contract']['expected_populations'] == expected, 'wrong frozen population counts')
        for label, n in expected.items(): require(len(self.pop[(label,'clean')]) == n, 'wrong frozen population: '+label)
        require(len(self.pop[('decision-v7/dev','variants')]) == 204 and
                len(self.pop[('transfer-v4/dev','variants')]) == 108, 'wrong variant counts')
        self.keys = [[s,qkey(r)] for s in SUITES for r in self.pop[(s+'/dev','clean')]]
        self.base = {}
        for rid, ref in self.refs.items():
            require(ref['status'] == 'READY_FOR_COMPARISON_INPUT', 'K0 reference not ready')
            vec = self.vectors[rid]
            require(vec['keys'] == self.keys and canonical(vec['keys']) == vec['keys_sha256'] and
                    canonical(vec['correct']) == vec['correct_sha256'], 'K0 vector pin/keys mismatch')
            require(len(vec['correct']) == len(self.keys) and all(type(x) is int and x in (0,1) for x in vec['correct']), 'bad K0 correctness')
            self.base[rid] = {}
            observed = []
            for suite in SUITES:
                label = suite+'/dev'
                pins = [p for p in ref['readout_pins'] if p['path'].endswith('/'+suite+'__dev/clean.jsonl')]
                require(len(pins) == 1, 'missing/duplicate K0 DEV readout pin')
                raw = jsonl(pins[0]['path'], pins[0]['sha256'])
                rows = self.pop[(label,'clean')]
                values = score_rows(rows, raw, ref['model']['sha256'])
                corr = [v['correct'] for v in values]
                observed.extend(corr)
                m = summarize(rows, values)
                compare_headline_leaf(m, ref['metrics'][label+'/clean'], rid+'/'+label)
                require(m['correct'] == ref['metrics'][label+'/clean']['correct'], 'K0 correct count mismatch')
                self.base[rid][label] = corr
            require(observed == vec['correct'], 'K0 saved vector contradicts actual DEV scores')
        # Reuse frozen pure-Python provenance checks; never import evaluator/scorer/model.
        path = next(p for p in c['new_contract']['source_pins'] if Path(p).name == 'provenance_r3.py')
        read(path, self.source_pins[path]['sha256'])
        spec = importlib.util.spec_from_file_location('rc1_dev_provenance', path)
        self.pv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pv)

    def phase_receipts(self, run):
        bindings, missing = {}, []
        for phase in ('infer', 'score'):
            packet = {}
            for kind in ('EXIT', 'LAUNCH', 'BINDING'):
                try: packet[kind] = obj(run.parent/(phase+'-'+kind+'.json'))
                except Pending as e: missing.append(str(e))
            if 'EXIT' in packet:
                for key in ('exit_code', 'container_exit_code'):
                    require(type(packet['EXIT'][key]) is int and packet['EXIT'][key] == 0,
                            phase+' phase exit nonzero/invalid: '+key)
            for kind in ('LAUNCH', 'EXIT'):
                if kind in packet:
                    cid = packet[kind]['container_id']
                    require(isinstance(cid, str) and bool(cid), phase+' invalid container ID')
            if 'LAUNCH' in packet and 'EXIT' in packet:
                require(packet['LAUNCH']['container_id'] == packet['EXIT']['container_id'],
                        phase+' container ID mismatch')
            if 'BINDING' in packet: bindings[phase] = packet['BINDING']
        if len(bindings) == 2:
            require(bindings['infer'] == bindings['score'], 'phase publication binding mismatch')
        if missing: raise Pending('; '.join(missing))
        return bindings

    def publication(self, lane, run, receipt_layout='legacy'):
        adapter = Path(lane['new_adapter'])
        pub = obj(adapter/'PUBLICATION.json')
        binding = obj(adapter/'BINDING.json')
        owner = obj(adapter.parent/'OWNER.json')
        ident = owner['identity']
        require(owner['owner'] == binding['owner'] == 'rc1-functional-'+lane['lane'], 'wrong publication owner/lane')
        require(type(ident['seed']) is int and ident['seed'] == lane['seed'], 'wrong publication seed')
        ref = self.refs[lane['baseline_id']]
        require(ident['model_id'] == 'Qwen3.5-'+lane['size']+'-Base' and
                ident['model_revision'] == ref['model']['base_revision'], 'wrong publication Base')
        require(canonical(ident, ascii=True) == binding['identity_sha256'] and pub['binding'] == binding,
                'publication identity binding mismatch')
        complete = obj(adapter.parents[1]/'COMPLETE.json')
        require(complete == {'exit_code':0,'steps':3116,'scientific_acceptance':False}, 'wrong/missing terminal3116 completion')
        require(set(pub['files']) == {'adapter_config.json','adapter_model.safetensors'}, 'wrong publication files')
        # No weight payload is opened. Producer already validated these hashes; inherit that acceptance.
        require(all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h)
                    for h in pub['files'].values()), 'malformed publication digest')
        config = obj(adapter/'adapter_config.json', pub['files']['adapter_config.json'])
        require(config['base_model_name_or_path'] == ident['model_id'] and config['revision'] == ident['model_revision'], 'adapter Base metadata mismatch')
        eval_bindings = (self.phase_receipts(run).values() if receipt_layout == 'phased'
                         else [obj(run.parent/'BINDING.json')])
        for eval_binding in eval_bindings:
            require(eval_binding['binding'] == binding and eval_binding['publication_sha256'] == digest(read(adapter/'PUBLICATION.json')),
                    'DEV launch publication mismatch')
        # Frozen model_identity includes all four nonhidden JSON/safetensors files.
        files = dict(pub['files'])
        files.update({n:digest(read(adapter/n)) for n in ('PUBLICATION.json','BINDING.json')})
        payload = {'kind':'lora-adapter-unmerged','adapter_files':files,
                   'base_revision':ref['model']['base_revision'],'base_path':ref['model']['base_path']}
        return canonical(payload), {'publication':str(adapter/'PUBLICATION.json'),
                'publication_sha256':digest(read(adapter/'PUBLICATION.json')),
                'binding':binding, 'seed':ident['seed'], 'terminal_step':3116,
                'weight_payload_validation':'inherited producer publication; consumer opens no weights'}

    def inference_handoff(self, run, h):
        handoff_path = run/'INFERENCE-READY.json'
        handoff = obj(handoff_path)
        phase = h['phase_separation']
        require(phase['inference_receipt_sha256'] == digest(read(handoff_path)),
                'inference handoff SHA256 mismatch')
        ih = handoff['inference_header']
        require(phase['inference_header'] == ih, 'inference handoff header mismatch')
        require(handoff['version'] == 1 and handoff['model'] == h['model']['base_path'] and
                handoff['adapter'] == h['model']['path'] and handoff['limit'] == 0 and
                handoff['out'] == '/run/output/result', 'inference handoff identity mismatch')
        require(handoff['descriptor'] == h['scorer'], 'inference handoff descriptor mismatch')
        require(ih['stages'] == 'k_score' and ih['device'] == 'npu' and h['device'] == 'cpu',
                'inference handoff stage/device mismatch')
        for key in ('arm', 'model', 'checkpoint_revision', 'prompt_version', 'render',
                    'prompt_format', 'scorer', 'limit', 'primary_input_mode', 'limit_groups',
                    'partitions', 'dtype', 'dry_run_warnings', 'data_files'):
            require(ih[key] == h[key], 'inference handoff header mismatch: '+key)
        # Throughput, UTC, argv, dedup counters and manifests belong to each process.
        groups = [s+'/'+p+'/'+k for s,p in (('decision-v7','calibration'),
                  ('decision-v7','dev'),('transfer-v4','dev'))
                  for k in (('clean',) if p == 'calibration' else
                            ('clean','variants','question_only','empty_input'))]
        require(handoff['groups'] == groups and set(handoff['stores']) == set(groups),
                'inference handoff groups mismatch')
        for group in groups:
            suite, split, kind = group.split('/')
            path = run/'trackk'/(suite+'__'+split)/(kind+'.jsonl')
            evidence = handoff['stores'][group]
            read(path, evidence['store_sha256'])
            read(str(path)+'.receipt.json', evidence['receipt_sha256'])
            rows = self.pop[(suite+'/'+split, 'variants' if kind == 'variants' else 'clean')]
            require(evidence['rows'] == len(rows), 'inference handoff row count mismatch')

    def consume(self, lane, run, runtime_receipt=None, receipt_layout='legacy'):
        run = Path(run)
        require(run.name == 'result', 'expected producer result directory')
        require(receipt_layout in ('legacy', 'phased'), 'unknown receipt layout')
        if receipt_layout == 'phased': self.phase_receipts(run)
        else:
            terminal = obj(run.parent/'EXIT.json')
            require(terminal['exit_code'] == 0, 'producer terminal exit nonzero')
        report, top = selective(run/'report.json', {'header','track_k','selection_evidence'})
        require('track_t' not in top, 'new DEV report contains forbidden Track T payload')
        h, track = report['header'], report['track_k']
        for k,v in {'arm':'K1','partitions':['dev','calibration'],'limit':0,'limit_groups':0,
                    'dry_run_warnings':[],'stages':'k','primary_input_mode':'full',
                    'prompt_version':'r0-prompt-v2','prompt_format':'raw-completion (no chat template)',
                    'render':'record_name','dtype':'float32'}.items():
            require(h[k] == v, 'header mismatch: '+k)
        expected_sc = self.catalog['new_contract']['scorer']
        for k,v in expected_sc.items(): require(h['scorer'].get(k) == v, 'numeric descriptor mismatch: '+k)
        for p,pin in self.catalog['new_contract']['data_pins'].items():
            require(h['data_files'].get(p) == pin, 'population header pin mismatch: '+p)
        model_sha, publication = self.publication(lane, run, receipt_layout)
        if receipt_layout == 'phased': self.inference_handoff(run, h)
        ref = self.refs[lane['baseline_id']]
        expected_model = {'path':lane['new_adapter'],'sha256':model_sha,'kind':'lora-adapter-unmerged',
                          'base_path':ref['model']['base_path'],'base_revision':ref['model']['base_revision']}
        require(h['model'] == expected_model and h['checkpoint_revision'] == expected_model['base_revision'], 'model/Base identity mismatch')
        require(h['scorer']['adapter'] == lane['new_adapter'] and h['scorer']['model_path'] == expected_model['base_path'], 'scorer model path mismatch')
        manifest_path = Path(h['provenance_manifest'])
        if not manifest_path.is_absolute(): manifest_path = run/manifest_path
        elif str(manifest_path).startswith('/run/output/result/'):
            manifest_path = run/manifest_path.relative_to('/run/output/result')
        require(manifest_path.resolve().is_relative_to((run/'manifests').resolve()), 'foreign header provenance path')
        manifest = obj(manifest_path)
        require(manifest['model_sha256'] == model_sha and manifest['scorer'] == h['scorer'], 'provenance descriptor mismatch')
        require(set(track['partitions']) == set(self.catalog['new_contract']['expected_populations']), 'wrong report partitions')
        selected, all_raw, diagnostics, stats, vectors = [], {}, {}, {}, {}
        for label in track['partitions']:
            suite, split = label.split('/')
            kinds = ('clean',) if split == 'calibration' else ('clean','question_only','empty_input','variants')
            for kind in kinds:
                rel = 'trackk/'+suite+'__'+split+'/'+kind+'.jsonl'
                require(rel in manifest['files'], 'header manifest lacks required readout: '+rel)
                pin = manifest['files'][rel]
                raw = jsonl(run/rel, pin['sha256'])
                require(len(raw) == pin['rows'], 'manifest row count mismatch: '+rel)
                rows = self.pop[(label,'variants' if kind == 'variants' else 'clean')]
                values = score_rows(rows, raw, model_sha)
                selected.append(run/rel)
                all_raw[(label,kind)] = [r['s'] for r in raw]
                m = summarize(rows, values)
                stats[label+'/'+kind] = m
                part = track['partitions'][label]
                require(part['n'] == len(self.pop[(label,'clean')]), 'wrong report population count')
                if kind != 'variants':
                    saved = part['headline'] if kind == 'clean' else part['arms'][kind]
                    compare_headline(m, saved, label+'/'+kind)
                if split == 'dev' and kind == 'clean': vectors[label] = [v['correct'] for v in values]
            if split == 'dev':
                part = track['partitions'][label]
                require(all(k in part['arms'] for k in ('constant','uniform','question_only','empty_input')), 'missing full controls')
                require(all(k in part['secondary'] for k in ('permutation','nota','operator')), 'missing full secondary diagnostics')
                require('near_tie_census' in part and 'duplicate_option_audit' in part, 'missing tie/duplicate diagnostics')
                diagnostics[label] = part  # retain existing full diagnostics; no semantic-transfer interpretation
        fit = track['operator_fit']
        require(fit['partition'] == 'decision-v7/calibration' and fit['n'] == 1148, 'wrong operator calibration population')
        evidence = report.get('selection_evidence')
        if evidence is not None:
            require(evidence['keys'] == self.keys and evidence['correct'] == sum([vectors[s+'/dev'] for s in SUITES], []),
                    'saved selection vector mismatch')
        try:
            prov = self.pv.verify(str(run), [], model_sha, selected_files=[str(p) for p in selected], role_of=lambda rel:rel)
        except self.pv.ProvenanceRefusal as e: raise Contradiction(str(e)) from e
        # Its stock summary says recomputed weights; replace with our actual, narrower identity source.
        prov.pop('checked', None)
        prov['identity_source'] = 'current publication hashes + Base revision/path; no weights opened'
        runtime = {'status':'CONDITIONAL_PENDING_ACTUAL_RUNTIME_VALIDATION',
                   'historical_image':'sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7',
                   'new_image':self.catalog['new_contract']['current_train_image'],
                   'note':'Descriptor equality does not establish numerical runtime equivalence.'}
        if runtime_receipt:
            receipt = obj(runtime_receipt)
            require(isinstance(receipt, dict) and bool(receipt), 'empty/malformed named runtime receipt')
            runtime['named_receipt'] = {'path':str(runtime_receipt),'sha256':digest(read(runtime_receipt))}
            runtime['review_required'] = True
            runtime['note'] = 'Named runtime receipt retained for independent review; consumer does not adjudicate runtime equivalence.'
        comparisons = {label:paired(v, self.base[lane['baseline_id']][label]) for label,v in vectors.items()}
        return {'lane':lane['lane'],'size':lane['size'],'seed':lane['seed'],'status':'VALIDATED_DEV_CONDITIONAL_RUNTIME',
                'baseline_id':lane['baseline_id'],'report':{'path':str(run/'report.json'),'sha256':digest(read(run/'report.json'))},
                'publication':publication,'provenance':prov,'runtime':runtime,'metrics':stats,
                'dev_comparisons':comparisons,'full_report_diagnostics':diagnostics,
                'operator_fit':fit,'_vectors':vectors}

def assemble(consumer, run_root, overrides=None, receipts=None, receipt_layout='legacy'):
    lanes = []
    overrides, receipts = overrides or {}, receipts or {}
    for lane in consumer.catalog['new_rc1_lanes']:
        run = Path(overrides.get(lane['lane'], Path(run_root)/('full-'+lane['lane'])/'result'))
        try: row = consumer.consume(lane, run, receipts.get(lane['lane']), receipt_layout)
        except Pending as e:
            row = {**{k:lane[k] for k in ('lane','size','seed')},'status':'PENDING_MISSING_INPUT','detail':str(e)}
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as e:
            row = {**{k:lane[k] for k in ('lane','size','seed')},'status':'REFUSED_CONTRADICTION','detail':str(e)}
        lanes.append(row)
    means = []
    for size in ('0.8B','2B','4B','9B'):
        rows = [r for r in lanes if r['size'] == size]
        ready = [r for r in rows if '_vectors' in r]
        mean = {'size':size,'required_seeds':[2,3],'finished_seeds':[r['seed'] for r in ready],
                'status':'INCOMPLETE_NO_TWO_SEED_MEAN','suites':None}
        if len(ready) == 2 and {r['seed'] for r in ready} == {2,3}:
            mean.update(status='DESCRIPTIVE_DEV_CONDITIONAL_RUNTIME', suites={})
            for s in SUITES:
                label = s+'/dev'
                a,b = [r['_vectors'][label] for r in ready]
                base = consumer.base[ready[0]['baseline_id']][label]
                diffs = [(x+y)/2-z for x,y,z in zip(a,b,base)]
                mean['suites'][label] = {'n_questions':len(base),'seed_count':2,
                    'new_correct_mean':(sum(a)+sum(b))/2,'new_accuracy_mean':(sum(a)+sum(b))/(2*len(base)),
                    'k0_correct':sum(base),'k0_accuracy':sum(base)/len(base),
                    'dev_same_question_two_seed_mean_difference':sum(diffs)/len(diffs)}
        means.append(mean)
    for row in lanes: row.pop('_vectors', None)
    bad = any(r['status'] == 'REFUSED_CONTRADICTION' for r in lanes)
    pending = any(r['status'] == 'PENDING_MISSING_INPUT' for r in lanes)
    return {'schema':'nga-rc1-dev-comparison-v1','status':'REFUSED_CONTRADICTION' if bad else 'INCOMPLETE_PENDING' if pending else 'VALIDATED_DEV_CONDITIONAL_RUNTIME',
            'scope':'DEV only; per-size descriptive comparison, no size pooling, CI, TEST selection or eligibility thresholds',
            'lanes':lanes,'within_size_two_seed_means':means}, 1 if bad else 2 if pending else 0

def markdown(result):
    lines = ['# RC1 DEV comparison', '', result['status'], '',
             'All differences are DEV. Historical image8190 differs from new image4726; runtime equivalence remains conditional.', '',
             '| Model/lane | Suite | n | Correct | Accuracy | R0 accuracy | Ties | DEV delta vs K0 | K0 wrong→right | K0 right→wrong |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in result.get('lanes',[]):
        if 'metrics' not in row:
            lines.append('| '+row['lane']+' | '+row['status']+' | — | — | — | — | — | — | — | — |')
            continue
        for suite,c in row['dev_comparisons'].items():
            m = row['metrics'][suite+'/clean']
            lines.append(f"| {row['lane']} | {suite} | {m['n']} | {m['correct']} | {m['kev_rule_accuracy']:.6f} | {m['r0_rule_accuracy']:.6f} | {m['tie_count']} | {c['dev_delta']:+.6f} | {c['k0_wrong_new_right']} | {c['k0_right_new_wrong']} |")
    lines += ['', '| Size | Seeds finished | Suite | Questions | DEV descriptive two-seed mean difference |', '|---|---|---|---:|---:|']
    for row in result.get('within_size_two_seed_means',[]):
        if row['suites'] is None:
            lines.append(f"| {row['size']} | {row['finished_seeds']} | Incomplete: no two-seed mean | — | — |")
        else:
            for suite,m in row['suites'].items():
                lines.append(f"| {row['size']} | 2, 3 | {suite} | {m['n_questions']} | {m['dev_same_question_two_seed_mean_difference']:+.6f} |")
    lines += ['', 'Full constant/uniform, input-drop/blank, source/type, near-tie, duplicate, permutation, NOTA and operator diagnostics remain in JSON. Input-drop is not evidence of trained semantic transfer.', '']
    return '\n'.join(lines)

def mappings(values):
    out = {}
    for value in values:
        lane, path = value.split('=',1)
        require(lane not in out, 'duplicate CLI lane: '+lane)
        out[lane] = path
    return out

def persist(out, result):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in [('comparison.json',json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n'),
                       ('comparison.md',markdown(result))]:
        temp = out/(name+'.tmp')
        temp.write_text(data)
        os.replace(temp,out/name)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-catalog',default=str(DEFAULT_CATALOG))
    p.add_argument('--vectors')
    p.add_argument('--source-pins')
    p.add_argument('--run-root',default='/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/followup-record-grade')
    p.add_argument('--receipt-layout', choices=('legacy', 'phased'), default='legacy')
    p.add_argument('--run',action='append',default=[],metavar='LANE=RESULT_DIR')
    p.add_argument('--runtime-receipt',action='append',default=[],metavar='LANE=RECEIPT_JSON')
    p.add_argument('--output',required=True)
    p.add_argument('--validate-inputs-only',action='store_true')
    a = p.parse_args()
    try:
        c = Consumer(a.reference_catalog,a.vectors,a.source_pins)
        overrides, receipts = mappings(a.run), mappings(a.runtime_receipt)
        known = {x['lane'] for x in c.catalog['new_rc1_lanes']}
        require(set(overrides) <= known and set(receipts) <= known, 'unknown CLI lane/seed')
        if a.validate_inputs_only:
            result, code = {'schema':'nga-rc1-dev-input-readiness-v1','status':'READY',
                'scope':'Validated saved K0 DEV inputs only; no actual producer report consumed and no gain computed',
                'catalog':{'path':str(c.catalog_path),'sha256':digest(read(c.catalog_path))},
                'vectors':{'path':str(c.vectors_path),'sha256':digest(read(c.vectors_path))},
                'k0_sizes':list(r['size'] for r in c.refs.values()),'paired_DEV_questions_per_size':len(c.keys),
                'fixed_lanes':c.catalog['new_rc1_lanes'],'runtime':'CONDITIONAL: historical8190 vs current4726'}, 0
        else: result, code = assemble(c,a.run_root,overrides,receipts,a.receipt_layout)
    except Pending as e: result, code = {'status':'PENDING_MISSING_INPUT','detail':str(e)}, 2
    except (ValueError,KeyError,TypeError,IndexError,UnicodeError) as e:
        result, code = {'status':'REFUSED_CONTRADICTION','detail':str(e)}, 1
    persist(a.output,result)
    print(json.dumps({'status':result['status'],'output':a.output,'exit_code':code}))
    return code

if __name__ == '__main__':
    sys.exit(main())
