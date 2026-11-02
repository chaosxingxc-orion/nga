#!/usr/bin/env python3
"""Read-only, hash-pinned control-receipt latency diagnostics. No scheduler actions."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

SCHEMA = 'nga-nfr-feedback-latency-v1'
MAX_CONFIG_BYTES = 65536
MAX_RECEIPT_BYTES = 1048576
MAX_OUTPUT_BYTES = 131072
MAX_RECEIPTS = 64
MAX_EVENTS = 64
MAX_INTERVALS = 32
RECEIPT_NAMES = {'START_INTENT.json', 'EXIT.json', 'TRAIN_EXIT.json',
                 'ENGINEERING_EVAL_EXIT.json'}
TIME_FIELDS = {'utc_seconds', 'started_utc', 'finished_utc'}
ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def keys(doc, required, optional=()):
    require(type(doc) is dict and set(required) <= set(doc)
            and set(doc) <= set(required) | set(optional), 'invalid object fields')


def identifier(value):
    require(type(value) is str and ID.fullmatch(value), 'invalid identifier')


def pin(value):
    require(type(value) is str and SHA.fullmatch(value), 'invalid SHA256')


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid('nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Invalid('invalid JSON') from exc


def read_snapshot(path, limit, counters):
    """Bounded single snapshot: parsed data and hash always share the same bytes."""
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts, 'absolute normalized path required')
    require(p.resolve(strict=True) == p, 'symlink or noncanonical path refused')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'regular file required')
        require(os.fstat(fd).st_size <= limit, 'input file too large')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            raw = handle.read(limit + 1)
        require(len(raw) <= limit, 'input file too large')
    finally:
        os.close(fd)
    counters['files_read'] += 1
    counters['bytes_read'] += len(raw)
    return raw


def validate(doc):
    keys(doc, ('schema', 'receipts', 'events', 'intervals'))
    require(doc['schema'] == SCHEMA, 'unsupported schema')
    for name, limit in [('receipts', MAX_RECEIPTS), ('events', MAX_EVENTS),
                        ('intervals', MAX_INTERVALS)]:
        require(type(doc[name]) is list and 1 <= len(doc[name]) <= limit, 'invalid collection size')
    receipts, events, intervals, paths, event_sources = {}, {}, set(), set(), set()
    for r in doc['receipts']:
        keys(r, ('id', 'path', 'sha256', 'clock_domain', 'clock_basis'))
        identifier(r['id']); pin(r['sha256'])
        require(r['id'] not in receipts, 'duplicate receipt identity')
        require(type(r['path']) is str and len(r['path']) <= 1024, 'invalid receipt path')
        p = Path(r['path'])
        require(p.is_absolute() and '..' not in p.parts and str(p) == r['path']
                and p.name in RECEIPT_NAMES, 'not a permitted control receipt')
        require(str(p) not in paths, 'duplicate receipt path')
        paths.add(str(p))
        require(r['clock_domain'] is None or (type(r['clock_domain']) is str
                and ID.fullmatch(r['clock_domain'])), 'invalid clock domain')
        require(type(r['clock_basis']) is str and len(r['clock_basis']) <= 256, 'invalid clock basis')
        require(r['clock_domain'] is None or r['clock_basis'].strip(), 'declared clock needs basis')
        receipts[r['id']] = r
    for e in doc['events']:
        keys(e, ('id', 'receipt', 'timestamp_field', 'kind'))
        identifier(e['id'])
        require(e['id'] not in events, 'duplicate event identity')
        require(e['receipt'] in receipts, 'unknown receipt reference')
        require(e['timestamp_field'] in TIME_FIELDS, 'unsupported timestamp field')
        require(e['kind'] in ('start', 'terminal'), 'invalid event kind')
        source = (e['receipt'], e['timestamp_field'])
        require(source not in event_sources, 'duplicate event source')
        event_sources.add(source)
        name = Path(receipts[e['receipt']]['path']).name
        require((name == 'START_INTENT.json') == (e['kind'] == 'start'), 'receipt kind mismatch')
        events[e['id']] = e
    for interval in doc['intervals']:
        keys(interval, ('id', 'start_events', 'end_event', 'required_terminals'))
        identifier(interval['id'])
        require(interval['id'] not in intervals, 'duplicate interval identity')
        intervals.add(interval['id'])
        for field in ('start_events', 'required_terminals'):
            refs = interval[field]
            require(type(refs) is list and 1 <= len(refs) <= MAX_EVENTS
                    and all(type(x) is str for x in refs)
                    and len(set(refs)) == len(refs), 'invalid interval references')
            require(all(x in events for x in refs), 'unknown event reference')
        require(interval['end_event'] in events, 'unknown end event')
        require(interval['end_event'] not in interval['start_events'], 'identical endpoints')
        require(all(events[x]['kind'] == 'terminal' for x in interval['required_terminals']),
                'required completion must reference terminal events')
        endpoints = interval['start_events'] + [interval['end_event']]
        require(all(events[x]['kind'] != 'terminal' or x in interval['required_terminals']
                    for x in endpoints), 'terminal endpoint must be required')
    require(set(receipts) == {e['receipt'] for e in events.values()}, 'unused receipt')
    return receipts, events


def timestamp(value):
    if type(value) in (int, float):
        require(math.isfinite(value) and 0 <= value <= 253402300799, 'invalid epoch timestamp')
        return float(value)
    require(type(value) is str and len(value) <= 64, 'invalid timestamp type')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'timezone required')
        result = parsed.timestamp()
        require(math.isfinite(result) and 0 <= result <= 253402300799, 'invalid ISO timestamp')
        return result
    except (ValueError, OverflowError) as exc:
        raise Invalid('invalid ISO timestamp') from exc


def analyze(config_path, config_sha256):
    started = time.perf_counter()
    cpu_started = time.process_time()
    counters = {'files_read': 0, 'bytes_read': 0}
    pin(config_sha256)
    raw = read_snapshot(config_path, MAX_CONFIG_BYTES, counters)
    require(hashlib.sha256(raw).hexdigest() == config_sha256, 'config hash mismatch')
    doc = strict_json(raw)
    receipts, event_specs = validate(doc)
    loaded, evidence = {}, []
    for rid, ref in receipts.items():
        try:
            data = read_snapshot(ref['path'], MAX_RECEIPT_BYTES, counters)
        except FileNotFoundError:
            loaded[rid] = None
            evidence.append(dict(ref, status='missing_receipt', observed_sha256=None))
            continue
        actual = hashlib.sha256(data).hexdigest()
        require(actual == ref['sha256'], 'receipt hash mismatch: ' + rid)
        content = strict_json(data)
        require(type(content) is dict, 'receipt must be a JSON object')
        loaded[rid] = content
        evidence.append(dict(ref, status='verified', observed_sha256=actual))
    events = {}
    for eid, spec in event_specs.items():
        ref, data = receipts[spec['receipt']], loaded[spec['receipt']]
        event = dict(spec, clock_domain=ref['clock_domain'], status='valid', timestamp_seconds=None)
        if data is None:
            event['status'] = 'missing_receipt'
        elif spec['kind'] == 'terminal' and type(data.get('exit_code')) is not int:
            event['status'] = 'missing_or_invalid_terminal'
        elif spec['kind'] == 'terminal' and data['exit_code'] != 0:
            event['status'] = 'failed_terminal'
        elif spec['timestamp_field'] not in data:
            event['status'] = 'missing_timestamp'
        else:
            try:
                event['timestamp_seconds'] = timestamp(data[spec['timestamp_field']])
            except Invalid:
                event['status'] = 'invalid_timestamp'
        events[eid] = event
    measured = []
    for spec in doc['intervals']:
        item = dict(spec, status='measured_same_clock_domain', elapsed_seconds=None,
                    basis='wall-clock snapshot; not monotonic duration or NPU idle time')
        endpoint_ids = spec['start_events'] + [spec['end_event']]
        all_ids = list(dict.fromkeys(endpoint_ids + spec['required_terminals']))
        errors = [{'event': e, 'status': events[e]['status']} for e in all_ids
                  if events[e]['status'] != 'valid']
        if errors:
            item.update(status='unavailable_event', reasons=errors)
        elif any(events[e]['clock_domain'] is None for e in endpoint_ids):
            item['status'] = 'unknown_clock_domain'
        elif len({events[e]['clock_domain'] for e in endpoint_ids}) != 1:
            item['status'] = 'incomparable_clock_domains'
        else:
            elapsed = events[spec['end_event']]['timestamp_seconds'] - max(
                events[e]['timestamp_seconds'] for e in spec['start_events'])
            if elapsed < 0:
                item['status'] = 'clock_or_order_anomaly'
            else:
                item['elapsed_seconds'] = elapsed
        measured.append(item)
    result = {'schema': SCHEMA + '-report', 'config': {'path': str(config_path), 'sha256': config_sha256},
              'receipts': evidence, 'events': list(events.values()), 'intervals': measured,
              'status_counts': dict(Counter(i['status'] for i in measured)),
              'measurement': dict(counters, runtime_seconds=time.perf_counter() - started,
                                  cpu_seconds=time.process_time() - cpu_started),
              'scope': 'readonly CPU control receipts; declared clocks are operator provenance, not verified synchronization',
              'production_speedup_claim': False, 'scientific_acceptance': False}
    require(len(json.dumps(result, ensure_ascii=True, allow_nan=False).encode()) <= MAX_OUTPUT_BYTES,
            'output exceeds bounded report size')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.config, args.sha256)
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        # Never dump receipt contents or a traceback into the orchestrator digest.
        message = str(exc)[:200] if isinstance(exc, Invalid) else type(exc).__name__
        print(json.dumps({'status': 'rejected', 'error': message, 'elapsed_seconds': None}))
        return 2
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
