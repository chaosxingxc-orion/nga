"""CPU-only native-panel shard contracts; never grants execution or result acceptance.

The referenced single-card plan is an immutable *population source*, not a shard
execution plan. A new runner/host protocol and independently reviewed DEV gate
are required before these manifests may be used for model execution.
"""
import argparse
import hashlib
import json
from pathlib import Path


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def ref_read(ref):
    require(set(ref) == {'path', 'sha256'}, 'reference fields differ')
    path = Path(ref['path'])
    require(path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
            'reference must be absolute and nonsymlink')
    require(file_sha(path) == ref['sha256'], 'reference bytes changed')
    return json.loads(path.read_bytes())


def require_int(value, minimum=0):
    require(type(value) is int and value >= minimum, 'exact integer required')


def request_identity(request, ordinal, source_indices=None):
    source_i=ordinal if source_indices is None else source_indices[ordinal]
    require(type(request.get('i')) is int and request['i'] == source_i, 'global ordinal differs')
    require('y' not in request and 'gold' not in request, 'gold in inference request')
    require(type(request.get('qid')) is str and type(request.get('request_sha256')) is str,
            'request identity missing')
    return dict(i=source_i, qid=request['qid'], request_sha256=request['request_sha256'],
                input_sha256=digest(request))


def build(parent_ref):
    parent = ref_read(parent_ref)
    require(parent.get('schema') == 'bev-native-panel-host-v1'
            and parent.get('scope') == 'public_fixed_base_test', 'unsupported population source')
    require(type(parent.get('count')) is int and parent['count'] == 46320,
            'full public population required')
    require(parent.get('batch_size') == 1 and type(parent['batch_size']) is int
            and parent.get('max_length') == 8192 and parent.get('adapter') is None,
            'numerical population source differs')
    require(all(parent.get(k) is False for k in ('scientific_acceptance',
            'candidate_test_authority', 'candidate_selection_allowed')), 'scope differs')
    ref = parent['inputs']; path = Path(ref['path'])
    require(path.is_absolute() and not any(p.is_symlink() for p in [path, *path.parents]),
            'input path differs')
    require(file_sha(path) == ref['sha256'], 'input file changed')
    identities, lengths = [], []
    ordered = hashlib.sha256(); ordered.update(b'[')
    with path.open() as stream:
        for i, line in enumerate(stream):
            require(line.endswith('\n') and line.strip(), 'torn or empty input row')
            row = json.loads(line)
            if i: ordered.update(b',')
            ordered.update(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())
            identities.append(request_identity(row, i))
            tokens = row.get('input_ids')
            require(type(tokens) is list and 0 < len(tokens) <= 8192
                    and all(type(x) is int and x >= 0 for x in tokens), 'token input differs')
            lengths.append(len(tokens))
    ordered.update(b']')
    require(ordered.hexdigest() == parent['ordered_inputs_sha256'], 'ordered request hash differs')
    require(len(identities) == parent['count'], 'input count differs')
    common = dict(parent_population=parent_ref, inputs=ref,
                  model_sha256=parent['model_sha256'], contract_sha256=parent['contract_sha256'],
                  source_protocol_binding_sha256=parent['protocol_binding_sha256'],
                  global_count=len(identities), ordered_inputs_sha256=parent['ordered_inputs_sha256'],
                  global_request_identities_sha256=digest(identities),
                  shard_count=2, strategy='contiguous_equal_count', execution_authorized=False,
                  scientific_acceptance=False, candidate_test_authority=False)
    split = len(identities) // 2
    shards = []
    for sid, (lo, hi) in enumerate(((0, split), (split, len(identities)))):
        ordinals = list(range(lo, hi))
        shards.append(dict(common, schema='bev-native-shard-manifest-v1', shard_id=sid,
                           global_ordinals=ordinals, ordinals_sha256=digest(ordinals),
                           assigned_count=hi-lo, input_tokens=sum(lengths[lo:hi]),
                           assigned_request_identities_sha256=digest(identities[lo:hi])))
    result = dict(schema='bev-native-shard-population-v1', binding=common,
                  shards=shards, scientific_acceptance=False, execution_authorized=False,
                  numerical_equivalence_verified=False)
    validate(result)
    return result


def validate(contract):
    require(contract.get('schema') == 'bev-native-shard-population-v1', 'population schema differs')
    require(contract.get('scientific_acceptance') is False
            and contract.get('execution_authorized') is False
            and contract.get('numerical_equivalence_verified') is False, 'authority forbidden')
    b = contract['binding']; n = b['global_count']; require_int(n, 2)
    if b.get('source_kind')=='native_dev72':
        require(n==72 and type(b.get('source_indices')) is list and len(b['source_indices'])==72 and len(set(b['source_indices']))==72 and all(type(x) is int and x>=0 for x in b['source_indices']),'DEV72 source identities differ')
        require(b.get('test_read') is False,'DEV72 TEST scope forbidden')
    else:require('source_kind' not in b and 'source_indices' not in b,'unknown source kind')
    require(type(b['shard_count']) is int and b['shard_count'] == 2
            and b['strategy'] == 'contiguous_equal_count', 'sharding policy differs')
    require(all(b.get(k) is False for k in ('execution_authorized', 'scientific_acceptance',
                                           'candidate_test_authority')), 'binding authority forbidden')
    require(len(contract['shards']) == 2, 'missing shard manifest')
    union = set()
    for sid, shard in enumerate(contract['shards']):
        require(shard.get('schema') == 'bev-native-shard-manifest-v1'
                and type(shard['shard_id']) is int and shard['shard_id'] == sid,
                'shard identity differs')
        require(all(shard.get(k) == v and type(shard.get(k)) is type(v) for k,v in b.items()),
                'foreign parent/model/contract binding')
        lo, hi = (0, n//2) if sid == 0 else (n//2, n)
        ids = shard['global_ordinals']
        require(type(ids) is list and all(type(x) is int and 0 <= x < n for x in ids),
                'invalid global ordinal')
        require(ids == list(range(lo, hi)), 'fixed assignment changed')
        require(shard['ordinals_sha256'] == digest(ids), 'ordinal hash differs')
        require_int(shard['assigned_count'], 1)
        require_int(shard['input_tokens'], 1)
        require(shard['assigned_count'] == len(ids), 'assignment count differs')
        require(not union.intersection(ids), 'overlapping shards')
        union.update(ids)
    require(union == set(range(n)), 'incomplete union')
    return b


def merge_population(contract, request_rows, shard_results):
    """Validate data population only. Caller still owes real lifecycle/operand review.

    A success status or this return value is never a COMPLETE marker. No metrics
    are averaged here: callers must pass the restored global sequence to the
    existing whole-population join only after lifecycle/numerical acceptance.
    """
    b = validate(contract); n = b['global_count']
    require(len(request_rows) == n and len(shard_results) == 2, 'partial population')
    identities = [request_identity(row, i, b.get('source_indices')) for i, row in enumerate(request_rows)]
    require(digest(identities) == b['global_request_identities_sha256'], 'request bytes changed')
    merged = {}
    for sid, (manifest, result) in enumerate(zip(contract['shards'], shard_results)):
        require(type(result.get('shard_id')) is int and result['shard_id'] == sid,
                'result shard differs')
        require(result.get('manifest_sha256') == digest(manifest), 'result manifest differs')
        require(type(result.get('exit_code')) is int and result['exit_code'] == 0,
                'failed or unfinished shard')
        require(result.get('scientific_acceptance') is False, 'result scope differs')
        require(result.get('model_sha256') == b['model_sha256']
                and result.get('contract_sha256') == b['contract_sha256'], 'foreign result binding')
        predictions = result.get('predictions')
        ids = manifest['global_ordinals']
        require(type(predictions) is list and len(predictions) == len(ids), 'missing shard predictions')
        require(digest([identities[i] for i in ids]) == manifest['assigned_request_identities_sha256'],
                'shard request identity differs')
        for ordinal, pred in zip(ids, predictions):
            require(all(pred.get(k) == v and type(pred.get(k)) is type(v)
                        for k,v in identities[ordinal].items()), 'prediction identity differs')
            require('y' not in pred and 'gold' not in pred, 'gold in prediction')
            require(ordinal not in merged, 'duplicate prediction ordinal')
            merged[ordinal] = pred
    require(set(merged) == set(range(n)), 'incomplete result union')
    return dict(status='POPULATION_VALIDATED_LIFECYCLE_AND_NUMERICS_PENDING',
                predictions=[merged[i] for i in range(n)], count=n,
                scientific_acceptance=False, execution_authorized=False,
                complete=False, lifecycle_verified=False, numerical_equivalence_verified=False)


def build_dev72(parent_ref, requests_ref, model_sha256, execution_ref):
    """Keep original selected input identities; shard position never rewrites i."""
    parent=ref_read(parent_ref);execution=ref_read(execution_ref)
    require(execution.get('schema')=='bev-native-dev-host-v1' and execution.get('probe_plan')==parent_ref and execution.get('test_read') is False and execution.get('scientific_acceptance') is False,'DEV execution source differs')
    require(parent.get('schema')=='bev-native-dev-probe-v1' and parent.get('test_read') is False and parent.get('scientific_acceptance') is False and parent.get('activation_authorized') is False,'DEV source scope differs')
    require(parent.get('source_split')=='train_derived_dev' and parent.get('tolerance')==0 and type(parent['tolerance']) is int,'DEV source protocol differs')
    doc=ref_read(parent['inputs']);items=doc['items']
    require(doc.get('test_read') is False and doc.get('selection')=='first24 per native kind in TRAIN order; no model outputs','DEV selection differs')
    require(len(items)==72 and [digest(x) for x in items]==parent['ordered_input_sha256'],'DEV population differs')
    path=Path(requests_ref['path']);require(path.is_absolute() and not any(x.is_symlink() for x in [path,*path.parents]) and '..' not in path.parts,'unsafe DEV requests');require(file_sha(path)==requests_ref['sha256'],'DEV requests changed')
    rows=[json.loads(line) for line in path.read_text().splitlines()];require(rows==items and digest(rows)==digest(items),'DEV requests transformed')
    require(all(set(x)=={'schema','i','qid','request_sha256','input_ids','rendered_prompt','labels','label_ids','options','kind'} and x['schema']=='bev-native-input-v1' for x in items),'DEV input fields differ')
    indices=[x['i'] for x in items];identities=[request_identity(x,i,indices) for i,x in enumerate(items)]
    model_files={v['path']:v['sha256'] for v in parent['model_files'].values()}
    require(digest(model_files)==model_sha256,'DEV model differs')
    b=dict(parent_population=parent_ref,inputs=requests_ref,model_sha256=model_sha256,contract_sha256=execution_ref['sha256'],source_protocol_binding_sha256=parent_ref['sha256'],source_execution=execution_ref,global_count=72,ordered_inputs_sha256=digest(items),global_request_identities_sha256=digest(identities),shard_count=2,strategy='contiguous_equal_count',execution_authorized=False,scientific_acceptance=False,candidate_test_authority=False,source_kind='native_dev72',source_indices=indices,test_read=False)
    shards=[]
    for sid in (0,1):
        ids=list(range(sid*36,(sid+1)*36));shards.append(dict(b,schema='bev-native-shard-manifest-v1',shard_id=sid,global_ordinals=ids,ordinals_sha256=digest(ids),assigned_count=36,input_tokens=sum(len(items[i]['input_ids']) for i in ids),assigned_request_identities_sha256=digest([identities[i] for i in ids])))
    out=dict(schema='bev-native-shard-population-v1',binding=b,shards=shards,scientific_acceptance=False,execution_authorized=False,numerical_equivalence_verified=False);validate(out);return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = build(dict(path=str(Path(args.parent).resolve()), sha256=args.sha256))
    with open(args.output, 'x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status='CPU_MANIFEST_ONLY', count=result['binding']['global_count'],
                          shards=[dict(id=s['shard_id'], count=s['assigned_count'],
                                       input_tokens=s['input_tokens']) for s in result['shards']],
                          execution_authorized=False)))


if __name__ == '__main__':
    main()
