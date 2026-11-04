"""Read-only imported-DEV provenance check before unchanged qualification member().

This verifies external, caller-authenticated result evidence. It never writes a
member decision or grants campaign/TEST authority. The caller must separately
run the frozen full-member consumer and independently accept its result.
"""
import hashlib
import json
from pathlib import Path


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def bound(path, files):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), 'unsafe recovery path')
    require(files.get(str(path)) == digest(path), 'recovery artifact missing or changed: '+str(path))
    return json.loads(path.read_bytes())


def verify_recovery(entry, files, review_ref):
    require(set(review_ref) == {'path', 'sha256'}
            and files.get(review_ref['path']) == review_ref['sha256'], 'external result review unbound')
    review = bound(review_ref['path'], files)
    require(review.get('schema') == 'independent-recovered-dev-result-acceptance-v1'
            and review.get('verdict') == 'PASS' and review.get('result_acceptance') is True
            and review.get('test_read') is False and review.get('scientific_acceptance') is False,
            'recovery result review scope differs')
    require(review.get('execution_sha256') == files.get(entry['execution'])
            and review.get('report_sha256') == files.get(entry['report']), 'review generation differs')
    require(isinstance(review.get('files'), dict) and review['files'], 'empty review evidence')
    for path, pin in review['files'].items():
        require(files.get(path) == pin and digest(path) == pin, 'review evidence changed: '+path)
    execution = bound(entry['execution'], files)
    require(execution.get('test_read') is False and execution.get('scientific_acceptance') is False,
            'execution authority differs')
    root = Path(execution['out'])
    require(Path(entry['report']) == root/'results/selection_report.json', 'report location differs')
    ref = execution['resume_import']
    require(ref['path'] == str(root/'IMPORTS.json') and files.get(ref['path']) == ref['sha256'], 'import ref differs')
    imports = bound(ref['path'], files)
    source_ref = execution['successor_guard']['source_execution']
    require(imports['schema'] == 'r3-dev-imported-prefixes-v1'
            and imports['source_execution'] == source_ref
            and imports['test_read'] is False and imports['scientific_acceptance'] is False,
            'import source/scope differs')
    require(files.get(source_ref['path']) == source_ref['sha256'], 'original execution unbound')
    source = bound(source_ref['path'], files)
    snapshot = imports['source_snapshot']
    require(files.get(snapshot['path']) == snapshot['sha256'] == source_ref['sha256']
            and Path(snapshot['path']).is_relative_to(root), 'source snapshot differs')
    require(bound(snapshot['path'], files) == source, 'source snapshot content differs')
    require(imports['target_out'] == str(root) and imports['source_out'] == source['out'], 'import output differs')
    population_ref = imports['population']
    require(files.get(population_ref['path']) == population_ref['sha256'], 'population unbound')
    population = bound(population_ref['path'], files)
    require(population['schema'] == 'r3-dev-resume-population-v1' and population['test_read'] is False,
            'population scope differs')
    seen = set(); imported = 0
    for item in imports['entries']:
        relative = Path(item['relative'])
        require(not relative.is_absolute() and '..' not in relative.parts and str(relative) not in seen
                and relative.parts[0] in ('trackk', 'trackt') and relative.suffix == '.jsonl', 'invalid imported relative path')
        seen.add(str(relative)); data_ref = item['data']; receipt_ref = item['receipt']
        for value in (data_ref, receipt_ref):
            require(Path(value['path']).is_relative_to(root/'imported')
                    and files.get(value['path']) == value['sha256'] == digest(value['path']), 'import payload changed')
        receipt = bound(receipt_ref['path'], files); payload = Path(data_ref['path']).read_bytes()
        require(receipt['path'] == str(Path(source['out'])/'results'/relative)
                and receipt['committed_bytes'] == len(payload) and receipt['sha256'] == data_ref['sha256'], 'original receipt differs')
        destination = root/'results'/relative
        require(files.get(str(destination)) == digest(destination), 'final readout unbound')
        with destination.open('rb') as stream:
            require(stream.read(len(payload)) == payload, 'imported prefix differs from final output')
        rows = [json.loads(line) for line in payload.splitlines()]
        require(len(rows) == receipt['rows'] and len({row['k'] for row in rows}) == len(rows), 'import rows duplicated')
        require(receipt['model_sha256'] == imports['model_sha256'] and receipt['scorer'] == imports['scorer'], 'import model/scorer differs')
        imported += len(rows)
    require(len(seen) == imports['file_count'] and imported == imports['rows'] == review['imported_rows'], 'import count differs')
    actual_files = {str(p.relative_to(root/'results')) for group in ('trackk', 'trackt')
                    for p in (root/'results'/group).rglob('*.jsonl')}
    require(actual_files == set(population['files']), 'complete readout population files differ')
    total = 0
    for relative, expected in population['files'].items():
        path = root/'results'/relative
        require(files.get(str(path)) == digest(path), 'population readout unbound')
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        require(len(rows) == len(expected) and {row['k'] for row in rows} == set(expected), 'population keys/count differ')
        for row in rows:
            require({k:v for k,v in row.items() if k not in ('s','p','argmax','tie','m')} == expected[row['k']], 'population metadata differs')
            require(row['m'] == imports['model_sha256'][:16], 'population model stamp differs')
        total += len(rows)
    require(total == review['rows'] and total-imported == review['new_rows'], 'new/total counts differ')
    report = bound(entry['report'], files)
    require(report['scientific_acceptance'] is False and report['header']['model'] == entry['model'], 'report model differs')
    return {'rows': total, 'imported_rows': imported, 'new_rows': total-imported,
            'result_review_sha256': review_ref['sha256'], 'scientific_acceptance': False,
            'qualification_member_bound': False, 'test_read': False}
