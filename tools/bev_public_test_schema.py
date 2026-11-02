"""Pure audited BEV question mapping. No scope admission."""
import hashlib,json

def strict_json(text):
    def pairs(xs):
        d = {}
        for k, v in xs:
            if k in d:
                raise ValueError('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(text, object_pairs_hook=pairs)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def question(spec):
    if not isinstance(spec, dict):
        raise ValueError('question_not_object')
    kind = spec.get('type')
    instruction = spec.get('instructions')
    if not isinstance(instruction, str) or not instruction.strip():
        raise ValueError('missing_instruction')
    criteria, label = spec.get('criteria'), spec.get('label')
    if kind == 'choice':
        if not isinstance(criteria, dict) or len(criteria) < 2:
            raise ValueError('invalid_choice_candidates')
        keys, definitions = list(criteria), list(criteria.values())
        if not all(isinstance(k, str) and k for k in keys):
            raise ValueError('invalid_choice_keys')
        if type(label) is not str or label not in criteria:
            raise ValueError('invalid_choice_label')
        gold = keys.index(label)
        level_type = 'nominal'
    elif kind == 'noul':
        if type(label) is not bool:
            raise ValueError('invalid_boolean_label')
        # Explicit local order; inference bridge must preserve it.
        keys, definitions = ['true', 'false'], ['True', 'False']
        gold = 0 if label else 1
        level_type = 'boolean'
    elif kind == 'score':
        if not isinstance(criteria, list) or len(criteria) < 2:
            raise ValueError('invalid_ordinal_levels')
        if type(label) is not int or not 0 <= label < len(criteria):
            raise ValueError('invalid_ordinal_label')
        keys, definitions = [str(i) for i in range(len(criteria))], criteria
        gold, level_type = label, 'ordinal'
    else:
        raise ValueError('unsupported_type')
    if not all(isinstance(v, str) and v.strip() for v in definitions):
        raise ValueError('invalid_level_definition')
    if len(set(definitions)) != len(definitions):
        raise ValueError('duplicate_level_definition')
    return {'type': kind, 'level_type': level_type, 'candidate_set': 'exclusive',
            'question': instruction, 'candidate_keys': keys, 'definitions': definitions}, gold


