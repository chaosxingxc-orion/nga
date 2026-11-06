"""Metadata-only adapter for the existing accepted reference chain; no payload reads."""
import hashlib
import json
from pathlib import Path

ACCEPT = 'ACCEPT_SCOPED_REFERENCE_TO_CONVERTED_MAPPING'
METADATA_SHA = 'b4175ae1d3f750d49b415dc9891c1e1773dab016c7468df816ede9dabb076184'
NATIVE_T = 2.3510958125672174
SUITES = ('decision-v7', 'transfer-v4')
LIMITS = [
    'Native Kev-0.8B pointer head T=2.3510958125672174 and T1 are separate; continuation scores use T1.',
    'Pointer versus label-continuation interfaces; no prompt-byte, tokenization, architecture, mathematical or cross-runtime equivalence.',
    'Final prompt strips outer whitespace on 36 decision inputs, one transfer input and eight transfer definition options.',
    'Historical reference audit has no audit-SHA terminal binding; present hashes cannot create historical authentication.',
    'Historical accepted continuation panels are separate from the current four-size roster.',
    'No current paired reference correctness or probability-loss inference: matched item operands are not consumed here.',
    'Upstream release is aggregate-only context, not local prediction operands; no synthetic Kev-2B.',
]


def identity_hash(rows):
    normalized = []
    for row in rows:
        ids = [level['id'] for level in row['levels']]
        normalized.append({'record_id': row['kev']['id'], 'question': row['qname'],
                           'ids': ids, 'gold_index': ids.index(row['gold'])})
    raw = json.dumps(normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_chain(N, metadata):
    """Authenticate only the five registered metadata files, never their payload inventory."""
    pins = metadata['pins']
    N.require(len(pins) == 5 and len({p['path'] for p in pins}) == 5, 'reference metadata pin inventory')
    docs = {Path(p['path']).name: N.read(N.pin(p)) for p in pins}
    byname = {Path(p['path']).name: p for p in pins}
    N.require(set(docs) == {'REFERENCE-SEMANTIC-ACCEPTANCE.json', 'REVIEW.json', 'RESULT.json',
                            'SOURCE-PIN-RECEIPT.json', 'INPUT-PINS.json'}, 'reference metadata file names')
    parent, review, result, receipt, inputs = [docs[k] for k in (
        'REFERENCE-SEMANTIC-ACCEPTANCE.json', 'REVIEW.json', 'RESULT.json', 'SOURCE-PIN-RECEIPT.json', 'INPUT-PINS.json')]
    N.require(parent.get('verdict') == ACCEPT and parent.get('review_sha256') == byname['REVIEW.json']['sha256'],
              'reference parent acceptance/review binding')
    N.require(review.get('schema') == 'reference-semantic-independent-scientific-review-v1'
              and review.get('verdict') == ACCEPT and review.get('scientific_acceptance') is True
              and review.get('reference_semantic_mapping_gap_closed') is True
              and review.get('unqualified_raw_semantic_or_prompt_equivalence') is False
              and review.get('blocking_findings_for_scoped_mapping') == [], 'reference typed scoped acceptance')
    N.require({k: review['reviewed_result'][k] for k in ('path', 'sha256')} == byname['RESULT.json'],
              'reference reviewed_result binding')
    N.require(result.get('schema') == 'reference-semantic-result-v1'
              and result.get('status') == 'PASS_SCOPED_SOURCE_SEMANTIC_MAPPING'
              and result.get('mapping_checks_all_passed') is True
              and result.get('exact_reference_semantic_evidence_gap_closed_for_data_mapping') is True,
              'reference typed result')
    N.require(receipt.get('schema') == 'reference-semantic-source-receipt-v1'
              and receipt.get('hash_verification_preceded_pure_replay') is True
              and inputs.get('schema') == 'reference-semantic-pins-v1', 'reference receipt/input schema')
    for name in ('RESULT.json', 'SOURCE-PIN-RECEIPT.json', 'INPUT-PINS.json'):
        p = byname[name]
        N.require(review['input_pins'].get(p['path'], {}).get('sha256') == p['sha256'],
                  'reference review input_pins binding: ' + name)
    for name in ('SOURCE-PIN-RECEIPT.json', 'INPUT-PINS.json'):
        N.require(result['evidence_sha256'].get(name) == byname[name]['sha256'], 'reference RESULT evidence binding: ' + name)
    for doc in (review, result, receipt):
        N.require(doc.get('historical_reference_audit_sha_terminal_binding') is False, 'unjustified historical terminal equivalence')
    bindings = {}
    for suite in SUITES:
        s = result['suites'][suite]; clean = s['converted_clean']; count = clean['rows']
        N.require(s.get('all_passed') is True and s.get('full_converted_bytes_reconstructed_exactly') is True
                  and s['clean_mapping_checks'] == count == review['suites'][suite]['questions'], 'reference suite count/checks')
        matches = [p for p, v in inputs['files'].items()
                   if p.endswith('/' + clean['path']) and v['sha256'] == clean['sha256']]
        N.require(len(matches) == 1, 'reference converted input pin missing/ambiguous')
        for path in matches + [s['original_source']['path']]:
            v = inputs['files'][path]
            expected = clean['sha256'] if path in matches else s['original_source']['sha256']
            N.require(v.get('verified') is True and v.get('observed_sha256') == v.get('sha256') == expected
                      and review['input_pins'].get(path, {}).get('sha256') == expected, 'reference source inputpins binding')
        bindings[suite] = {'n': count, 'sha256': clean['sha256'], 'ordered_identity_sha256': s['ordered_identity_sha256']}
    N.require(result['mapping_count'] == sum(x['n'] for x in bindings.values()), 'reference total count')
    return {'pins': byname, 'review': review, 'result': result, 'inputs': inputs, 'population_bindings': bindings}


def match_populations(N, expected, actual):
    N.require(set(actual) == set(expected), 'reference population suite inventory differs')
    for suite in SUITES:
        for field in ('n', 'sha256', 'ordered_identity_sha256'):
            N.require(type(actual[suite][field]) is type(expected[suite][field])
                      and actual[suite][field] == expected[suite][field], 'reference population ' + field + ' differs: ' + suite)


def performance_context(N, chain, export_pin):
    """Read accepted metadata/report export, not raw TEST/rows/vectors it references."""
    review, inputs = chain['review'], chain['inputs']['files']
    prior_pin = {k: review['prior_review'][k] for k in ('path', 'sha256')}
    prior = N.read(N.pin(prior_pin))
    N.require(inputs.get(prior_pin['path'], {}).get('sha256') == prior_pin['sha256'], 'prior report input binding')
    N.require(prior.get('schema') == 'final-production-scientific-review-v1'
              and prior.get('verdict') == 'PASS_SCOPED_SAME_TEST_REPORT'
              and prior.get('scientific_acceptance') is True, 'prior report typed acceptance')
    for inventory in (inputs, review['input_pins'], prior['input_pins']):
        N.require(inventory.get(export_pin['path'], {}).get('sha256') == export_pin['sha256'], 'performance export not in accepted inputs')
    export = N.read(N.pin(export_pin))
    N.require(export.get('schema') == 'private-final-reference-alignment-v1', 'performance export schema')
    for suite in SUITES:
        N.require(export['alignment'][suite]['ordered_identity_sha256'] == chain['population_bindings'][suite]['ordered_identity_sha256'],
                  'performance export population order')
    rows = export['reference_operands']
    N.require(len(rows) == 4 and {(r['dataset'], r['protocol']) for r in rows} ==
              {(s + '/clean', p) for s in SUITES for p in ('native', 'raw_temperature_one')}, 'reference performance panels missing')
    panels = []
    for i, row in enumerate(rows):
        suite = row['dataset'].split('/')[0]
        N.require(row['model'] == 'Kev-0.8B' and row['temperature'] == (NATIVE_T if row['protocol'] == 'native' else 1.0)
                  and row['metrics']['n'] == chain['population_bindings'][suite]['n'], 'reference model/temperature/denominator')
        panels.append({k: row[k] for k in ('model', 'dataset', 'protocol', 'temperature', 'metrics', 'sources', 'audit_terminal_binding')}
                      | {'provenance': {'export': export_pin, 'json_pointer': '/reference_operands/' + str(i)}})
    continuation = []
    for member, suites in prior['accepted_probability_panels'].items():
        for suite in SUITES:
            item = suites[suite + '/test']; m = item['metrics']
            continuation.append({'member': member, 'suite': suite, 'interface': 'label-continuation', 'temperature': 1.0,
                                 'metrics': {k: m[k] for k in ('n', 'accuracy', 'nll', 'brier_sum', 'ece10')},
                                 'provenance': {'export': prior_pin, 'json_pointer': '/accepted_probability_panels/' + member + '/' + suite + '~1test'}})
    return {'status': 'attached accepted historical context', 'local_pointer_panels': panels,
            'accepted_historical_continuation_panels': continuation,
            'upstream_native_aggregate_only': export['nativeT_context']['upstream_release'],
            'native_temperature': NATIVE_T, 'provenance': {'alignment_export': export_pin, 'prior_scientific_review': prior_pin},
            'paired_reference_claim': False, 'paired_probability_loss_contrasts': None}


def context(N, packet, config, populations=None):
    result = {'status': 'pending', 'mapping_status': 'not attached', 'performance_status': 'not attached',
              'paired_reference_claim': False, 'paired_probability_loss_contrasts': None, 'limitations': LIMITS,
              'missing_evidence': ['accepted mapping attachment and actual count/hash/order match', 'accepted reference performance export']}
    metadata_pin = config.get('reference_metadata')
    if not metadata_pin:
        N.require('reference_context' not in packet, 'reference metadata trust anchor absent')
        return result
    N.require(metadata_pin['sha256'] == METADATA_SHA, 'reference metadata differs from existing registered acceptance')
    metadata = N.read(N.pin(metadata_pin)); chain = validate_chain(N, metadata)
    result.update(mapping_status='accepted metadata; current population alignment pending',
                  accepted_metadata=metadata_pin, population_bindings=chain['population_bindings'],
                  accepted_mapping_pins=chain['pins'])
    ref = packet.get('reference_context')
    if ref is not None:
        N.require(set(ref) == {'mapping_metadata'}, 'reference attachment fields/equivalence claims differ')
        N.require(ref['mapping_metadata'] == metadata_pin, 'reference mapping attachment binding')
        N.require(populations is not None, 'actual population metadata required')
        actual = {s: {'n': len(populations[s + '/test/clean']),
                      'sha256': packet['data_pins'][s + '/test/clean']['sha256'],
                      'ordered_identity_sha256': identity_hash(populations[s + '/test/clean'])} for s in SUITES}
        for s in SUITES:
            N.require(packet['data_pins'][s + '/test/clean']['n'] == actual[s]['n'], 'reference actual population count')
        match_populations(N, chain['population_bindings'], actual)
        N.require(packet['kind'] == 'production', 'generated populations cannot borrow real reference approval')
        result['mapping_status'] = 'complete'
        result['actual_population_bindings'] = actual
    if config.get('reference_performance_export'):
        result['performance'] = performance_context(N, chain, config['reference_performance_export'])
        result['performance_status'] = 'complete historical context'
    missing = []
    if result['mapping_status'] != 'complete': missing.append('current authorized production population count/hash/order alignment')
    if result['performance_status'] != 'complete historical context': missing.append('accepted reference performance export')
    result['missing_evidence'] = missing
    result['status'] = 'pending' if missing else 'complete'
    return result
