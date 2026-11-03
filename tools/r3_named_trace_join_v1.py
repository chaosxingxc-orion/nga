"""Version 1 independent CPU join: named host ranges -> explicit flows -> tasks.

Host nesting identifies range membership. Device association requires the exact
async_npu flow identity and exact destination pid/tid/start, never clock overlap.
Unassigned/non-forward device work stays visible; no all-device-time claim.
"""
import collections
import hashlib
import json
from decimal import Decimal

ADAPTER_ID = 'named_forward_trace_join_v1'
def require(ok, reason):
    if not ok:
        raise ValueError(reason)
def stamp(v):
    require(type(v) in (int,float,str,Decimal), 'invalid numeric type')
    try:number=Decimal(str(v))
    except Exception as exc:raise ValueError('invalid numeric value') from exc
    require(number.is_finite() and number>=0, 'nonfinite or negative numeric value')
    return number

def strict_object(pairs):
    value={}
    for key,item in pairs:
        require(key not in value, 'duplicate JSON key')
        value[key]=item
    return value

def invalid_constant(value):
    raise ValueError('nonfinite JSON constant '+value)

def iter_events(path):
    """Stream events and validate the entire strict JSON envelope to EOF."""
    decoder=json.JSONDecoder(object_pairs_hook=strict_object,parse_constant=invalid_constant,parse_float=Decimal)
    class Reader:
        def __init__(self,source):self.source=source;self.buf='';self.pos=0;self.eof=False
        def more(self):
            chunk=self.source.read(65536);self.buf=self.buf[self.pos:]+chunk;self.pos=0
            if not chunk:self.eof=True
        def peek(self):
            while True:
                while self.pos<len(self.buf) and self.buf[self.pos].isspace():self.pos+=1
                if self.pos<len(self.buf):return self.buf[self.pos]
                if self.eof:return ''
                self.more()
        def take(self,character):
            require(self.peek()==character, 'invalid JSON delimiter, expected '+character)
            self.pos+=1
        def value(self):
            require(bool(self.peek()), 'missing JSON value')
            while True:
                try:value,end=decoder.raw_decode(self.buf,self.pos)
                except json.JSONDecodeError as exc:
                    require(not self.eof,'incomplete JSON value')
                    self.more();continue
                # A numeric token can be incomplete exactly at the chunk edge.
                if end==len(self.buf) and not self.eof:self.more();continue
                self.pos=end;return value
        def events(self):
            self.take('[')
            if self.peek()==']':self.pos+=1;return
            while True:
                event=self.value();require(isinstance(event,dict), 'invalid trace event')
                yield event
                char=self.peek()
                if char==']':self.pos+=1;return
                self.take(',');require(self.peek()!=']', 'trailing array comma')
    with open(path) as source:
        reader=Reader(source)
        if reader.peek()=='[':yield from reader.events()
        else:
            reader.take('{');keys=set();found=False
            require(reader.peek()!='}', 'traceEvents missing')
            while True:
                key=reader.value();require(type(key) is str and key not in keys,'invalid or duplicate envelope key');keys.add(key);reader.take(':')
                if key=='traceEvents':found=True;yield from reader.events()
                else:reader.value()
                if reader.peek()=='}':reader.pos+=1;break
                reader.take(',');require(reader.peek()!='}', 'trailing object comma')
            require(found,'traceEvents missing')
        require(reader.peek()=='','trailing JSON data')

def join(trace, manifest, plan_sha256, attempt=1):
    require(type(attempt) is int and attempt==1 and type(plan_sha256) is str and len(plan_sha256)==64,'invalid expected generation')
    require(manifest['schema'] == 'named-forward-manifest-v1' and manifest['plan_sha256'] == plan_sha256 and type(manifest['attempt']) is int and manifest['attempt'] == attempt, 'foreign manifest generation')
    records = manifest['records']
    require(len(records) == 21 and type(manifest['total_forwards']) is int and manifest['total_forwards'] == 21, 'missing true forwards')
    phases=('cold_reference','split_gate','warmup','wall_0','wall_1','wall_2','trace')
    require(len({r['name'] for r in records})==21, 'duplicate manifest identity')
    for phase in phases:
        subset=[r for r in records if r['phase']==phase]
        require(len(subset)==3 and [r['ordinal'] for r in subset]==[1,2,3], 'phase count/order differs')
        for r in subset:
            require(type(r['ordinal']) is int and type(r['cell']) is str, 'invalid manifest identity types')
            require(r['name']==f"nga.forward/{plan_sha256}/{attempt}/{phase}/{hashlib.sha256(r['cell'].encode()).hexdigest()}/{r['ordinal']}", 'foreign manifest identity')
    expected = {r['name']:r for r in records if r['phase'] == 'trace'}
    require(len(expected) == 3 and all(r['status'] == 'returned' for r in records), 'missing/duplicate manifest forwards')
    events = trace['traceEvents'] if isinstance(trace, dict) else trace
    named=[];tasks=[];flow_events=[]
    for e in events:
        if str(e.get('name','')).startswith('nga.forward/'):named.append(e)
        if e.get('ph')=='X' and 'Task Type' in e.get('args',{}):tasks.append(e)
        if e.get('cat')=='async_npu' and e.get('ph') in ('s','f'):flow_events.append(e)
    for event in named+tasks+flow_events:
        require(type(event.get('pid')) is int and type(event.get('tid')) is int and event['pid']>=0 and event['tid']>=0,'invalid event pid/tid')
        stamp(event.get('ts'))
        if event.get('ph')=='X':stamp(event.get('dur'))
    for event in tasks:require(type(event['args']['Task Type']) is str and bool(event['args']['Task Type']),'invalid task type')
    require(len(named) == 3 and len({e['name'] for e in named}) == 3, 'missing/duplicate named forwards')
    require({e['name'] for e in named} == set(expected), 'foreign named forward')
    require(all(e.get('ph') == 'X' and stamp(e.get('dur',0)) > 0 for e in named), 'invalid forward range')
    for a in named:
        for b in named:
            if a is b or (a['pid'],a['tid']) != (b['pid'],b['tid']):
                continue
            require(stamp(a['ts'])+stamp(a['dur']) <= stamp(b['ts']) or stamp(b['ts'])+stamp(b['dur']) <= stamp(a['ts']), 'ambiguous overlapping forward ranges')
    require(tasks, 'no device tasks')
    targets = collections.defaultdict(list)
    for i,e in enumerate(tasks):
        targets[(e['pid'],e['tid'],stamp(e['ts']))].append(i)
    flows = collections.defaultdict(lambda:collections.defaultdict(list))
    for e in flow_events:
        if e.get('cat') == 'async_npu' and e.get('ph') in ('s','f'):
            require(type(e.get('id')) in (int,str) and (e['id']>=0 if type(e['id']) is int else bool(e['id'])),'flow identity missing or invalid')
            require(e.get('name')=='torch_to_npu','foreign flow namespace')
            flows[(e['name'],type(e['id']).__name__,e['id'])][e['ph']].append(e)
    require(flows, 'no correlation flows')
    assigned = collections.defaultdict(list); outside = []; used = {}
    for identity, ends in flows.items():
        require(len(ends['s']) == len(ends['f']) == 1, 'missing/duplicate/ambiguous flow endpoints')
        start, finish = ends['s'][0], ends['f'][0]
        matches = targets[(finish['pid'],finish['tid'],stamp(finish['ts']))]
        require(len(matches) == 1, 'missing/ambiguous device join target')
        idx = matches[0]
        require(idx not in used, 'duplicate correlation target')
        used[idx] = identity
        owners = [e['name'] for e in named if (e['pid'],e['tid']) == (start['pid'],start['tid']) and stamp(e['ts']) <= stamp(start['ts']) < stamp(e['ts'])+stamp(e['dur'])]
        require(len(owners) <= 1, 'ambiguous forward owner')
        (assigned[owners[0]] if owners else outside).append(idx)
    require(set(assigned) == set(expected) and all(assigned.values()), 'forward has no correlated device work')
    unassigned = sorted(set(range(len(tasks)))-set(used))
    def finite_sum(indices):
        import math
        total=float(sum((stamp(tasks[i]['dur']) for i in indices),Decimal(0)))
        require(math.isfinite(total),'nonfinite duration aggregate')
        return total
    def metrics(indices):
        return dict(tasks=len(indices), duration_sum_us=finite_sum(indices), task_types=dict(collections.Counter(tasks[i]['args']['Task Type'] for i in indices)))
    return dict(schema='named-forward-coverage-v1', adapter=ADAPTER_ID, plan_sha256=plan_sha256, attempt=attempt, status='PASS_NAMED_FORWARD_CORRELATION', forward_ranges=3, unique_flow_ids=len(flows), per_forward={k:metrics(v) for k,v in assigned.items()}, correlated_outside_forward=metrics(outside), unattributed_tasks=metrics(unassigned), total_device_work=metrics(range(len(tasks))), partition_complete=sum(map(len,assigned.values()))+len(outside)+len(unassigned)==len(tasks), device_duration_additive_wall_time=False, all_device_time_claim=False, scientific_acceptance=False, test_read=False)
