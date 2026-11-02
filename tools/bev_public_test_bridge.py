"""Pure BEV typed schema and raw-score bridge; no device imports.

The caller supplies the already loaded raw-score callable and exact tokenizer.
This does not invoke suite-bound full_eval_r3 or grant dataset admission.
"""
import math
from collections import Counter

BRIDGE_PROTOCOL = 'bev-r3-neutral-identifiers-draft-v1'
TASK_DEFINITION = 'Answer the question about the input using only the options given.'
_TYPES = {'choice': 'nominal', 'noul': 'boolean', 'score': 'ordinal'}
REQUEST_KEYS = {'input', 'type', 'level_type', 'candidate_set', 'question', 'candidate_keys', 'definitions'}


def to_r3_row(request):
    """Accept ONLY a gold-free request. Stable source keys are hidden level IDs."""
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise ValueError('exact_gold_free_request_required')
    kind = request['type']
    if kind not in _TYPES or request['level_type'] != _TYPES[kind] or request['candidate_set'] != 'exclusive':
        raise ValueError('unsupported_typed_request')
    keys, definitions = request['candidate_keys'], request['definitions']
    if not isinstance(keys, list) or not isinstance(definitions, list) or len(keys) != len(definitions) or len(keys) < 2:
        raise ValueError('invalid_candidate_arrays')
    if not all(isinstance(x, str) and x.strip() for x in keys + definitions):
        raise ValueError('invalid_candidate_text')
    if len(set(keys)) != len(keys) or len(set(definitions)) != len(definitions):
        raise ValueError('duplicate_candidates')
    if kind == 'noul' and (keys != ['true', 'false'] or definitions != ['True', 'False']):
        raise ValueError('boolean_order_differs')
    if kind == 'score' and keys != [str(i) for i in range(len(keys))]:
        raise ValueError('ordinal_index_order_differs')
    if not all(isinstance(request[k], str) and request[k].strip() for k in ('input', 'question')):
        raise ValueError('invalid_input_or_instruction')
    return {'input': request['input'], 'question': request['question'],
            'task_definition': TASK_DEFINITION, 'candidate_set': 'exclusive',
            'level_type': request['level_type'],
            'levels': [{'id': key, 'name': f'L{i+1}', 'definition': definition}
                       for i, (key, definition) in enumerate(zip(keys, definitions))]}


def from_raw(identifier, raw, n_options):
    if not isinstance(raw, (list, tuple)) or len(raw) != n_options or not all(
            type(x) in (int, float) and math.isfinite(x) for x in raw):
        return {'id': identifier, 'status': 'invalid_prediction', 'reason': 'invalid_raw_scores'}
    # Same rule as core_r3.argmax_first: first maximum in frozen candidate order.
    winner = max(range(n_options), key=lambda i: raw[i])
    ordered = sorted(raw, reverse=True)
    return {'id': identifier, 'status': 'ok', 'index': winner,
            'exact_tie': sum(x == raw[winner] for x in raw) > 1,
            'top2_gap_nats': ordered[0] - ordered[1]}


