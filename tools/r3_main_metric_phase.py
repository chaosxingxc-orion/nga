"""Prospective DEV phase snapshots; diagnostics never grant full-run qualification."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

SCHEMA = 'r3-main-metric-contract-v1'
COUNTS = {'decision-v7/dev/clean': 1264, 'transfer-v4/dev/clean': 656}
FLAGS = dict(diagnostic_only=True, scientific_acceptance=False,
             candidate_selection_allowed=False, test_read=False, resources_released=False)


def require(ok, why):
    if not ok: raise ValueError(why)


def safe(path):
    p = Path(path).absolute()
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink evidence path')
    return p


def sha(path): return hashlib.sha256(safe(path).read_bytes()).hexdigest()
def read(path): return json.loads(safe(path).read_text())
def canonical(d): return (json.dumps(d, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
def digest(d): return hashlib.sha256(canonical(d)).hexdigest()
def pin(path): return {'path':str(safe(path)), 'sha256':sha(path)}
def pinned(ref):
    p=safe(ref['path']);require(sha(p)==ref['sha256'], 'evidence pin changed: '+str(p));return p

def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def exclusive(path, raw):
    path=safe(path)
    with path.open('xb') as f: f.write(raw);f.flush();os.fsync(f.fileno())
    fsync_dir(path.parent)

def publish(path, value):
    # Readers see either no marker or complete bytes; stale temp requires reconciliation.
    path=safe(path);tmp=path.with_name(path.name+'.pending')
    exclusive(tmp,canonical(value));os.link(tmp,path);fsync_dir(path.parent)
    tmp.unlink();fsync_dir(path.parent)

def contract(path, expected, C, AS, SE):
    require(sha(path)==expected,'contract pin differs');d=read(path)
    require(d['schema']==SCHEMA and d['flags']==FLAGS,'contract scope differs')
    require(set(d['populations'])==set(COUNTS),'only two clean DEV populations allowed')
    require(type(d['attempt']) is int and d['attempt']>0,'invalid attempt')
    for ref in d['files'].values():pinned(ref)
    require(pin(__file__)==d['phase_implementation'],'phase implementation differs')
    for name,m in [('core',C),('store',AS),('population',SE)]:
        require(pin(m.__file__)==d['libraries'][name],'loaded dependency differs')
    header=d['header_identity']
    require(header['arm'] in ('K0','K1','K1-QO','K1-PT','K2'),'unsupported arm')
    require(header['primary_input_mode']==('drop' if header['arm']=='K1-QO' else 'full'),'primary mode differs')
    require(header['model']['sha256'] and isinstance(header['scorer'],dict),'model/scorer absent')
    rows={}
    for label,n in COUNTS.items():
        spec=d['populations'][label];p=pinned(spec['input'])
        require(p.name=='dev.jsonl' and p.parent.name==label.split('/')[0],'foreign partition')
        rows[label]=C.read_jsonl(str(p));keys=[C.kev_key(x) for x in rows[label]]
        require(spec['n']==n==len(rows[label]) and len(set(keys))==n and digest(keys)==spec['ordered_keys_sha256'],'population differs')
    for name in ('evaluation_plan','execution'):pinned(d[name])
    safe(d['evaluation_out']);return d,rows

def check_header(d, header, producer, attempt, out):
    require(pin(producer)==d['producer'],'producer differs')
    require(type(attempt) is int and attempt==d['attempt'],'attempt differs')
    require(str(safe(out))==d['evaluation_out'],'evaluation root differs')
    require({k:header.get(k) for k in d['header_identity']}==d['header_identity'],'runtime model/scorer/mode differs')
    require(header.get('limit',0)==0 and set(header['partitions'])=={'dev','calibration'},'partial/foreign partitions')
    require(set(header['stages'].split(','))=={'k_score','t_score'},'full registered scorer stages required')

def payload(d, rows, label, C, AS, SE, path):
    path=safe(path);receipt=safe(str(path)+'.receipt.json')
    raw,rr=path.read_bytes(),receipt.read_bytes()
    stored=AS.read_verified(d['evaluation_out'],str(path),d['header_identity']['model']['sha256'],d['header_identity']['scorer'])
    ordered=SE.validate_population(stored,rows[label],C.kev_key)
    require(path.read_bytes()==raw and receipt.read_bytes()==rr,'readout mutated during validation')
    return raw,rr,ordered

class Collector:
    def __init__(self,path,expected,C,AS,SE,header,producer,attempt,out):
        self.path,self.expected,self.C,self.AS,self.SE=path,expected,C,AS,SE
        self.d,self.rows=contract(path,expected,C,AS,SE)
        check_header(self.d,header,producer,attempt,out)
        self.header=json.loads(json.dumps(header));self.seen=set();self.start=time.monotonic()

    def completed(self,label,path,input_mode):
        if label not in COUNTS:return None
        d=self.d;C=self.C
        require(input_mode==d['header_identity']['primary_input_mode'],'input mode differs')
        suite,split,kind=label.split('/')
        require(safe(path)==safe(C.k_readout_path(d['evaluation_out'],suite,split,kind)),'readout path differs')
        payload(d,self.rows,label,C,self.AS,self.SE,path);self.seen.add(label)
        if self.seen!=set(COUNTS):return None
        # No whole-run status/release is inspected or produced here.
        root=safe(d['evaluation_out']);phase=root/'main_metric_phase';marker=root/'MAIN_METRIC_COMPLETE.json'
        with (root/'main_metric_phase.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if marker.exists():
                result=consume(self.path,self.expected,C,self.AS,self.SE)
                for label,e in read(marker)['snapshots'].items():
                    require(sha(e['original_path'])==e['data']['sha256'] and sha(e['original_path']+'.receipt.json')==e['original_receipt']['sha256'],'resume evidence changed')
                return result
            require(not phase.exists(),'partial snapshot requires reconciliation')
            phase.mkdir();fsync_dir(root);snapshots={}
            for label in COUNTS:
                suite,split,kind=label.split('/');original=C.k_readout_path(str(root),suite,split,kind)
                raw,rr,_=payload(d,self.rows,label,C,self.AS,self.SE,original)
                dest=phase/(suite+'.jsonl');orig=phase/(suite+'.original-receipt.json');rec=Path(str(dest)+'.receipt.json')
                exclusive(dest,raw);exclusive(orig,rr)
                mapped=json.loads(rr);mapped['path']=str(dest);exclusive(rec,canonical(mapped))
                require(safe(original).read_bytes()==raw and safe(original+'.receipt.json').read_bytes()==rr,'readout mutated during snapshot')
                snapshots[label]=dict(original_path=original,data=pin(dest),original_receipt=pin(orig),snapshot_receipt=pin(rec))
            value=dict(schema='r3-main-metric-complete-v1',contract_sha256=self.expected,attempt=d['attempt'],header=self.header,
                       completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),phase_elapsed_seconds=time.monotonic()-self.start,
                       snapshots=snapshots,**FLAGS)
            for entry in snapshots.values():
                require(sha(entry['original_path'])==entry['data']['sha256'] and sha(entry['original_path']+'.receipt.json')==entry['original_receipt']['sha256'],'source changed before phase commit')
            # Revalidate exact contract/source/input before committing diagnostic marker.
            contract(self.path,self.expected,C,self.AS,self.SE)
            publish(marker,value)
        return consume(self.path,self.expected,C,self.AS,self.SE)

def consume(path,expected,C,AS,SE):
    d,rows=contract(path,expected,C,AS,SE);root=safe(d['evaluation_out']);marker=root/'MAIN_METRIC_COMPLETE.json';v=read(marker)
    require(v['schema']=='r3-main-metric-complete-v1' and v['contract_sha256']==expected and v['attempt']==d['attempt'],'phase identity differs')
    require({k:v.get(k) for k in FLAGS}==FLAGS and set(v['snapshots'])==set(COUNTS),'phase scope differs')
    check_header(d,v['header'],d['producer']['path'],d['attempt'],root)
    result={}
    for label,e in v['snapshots'].items():
        suite,split,kind=label.split('/');dest=root/'main_metric_phase'/(suite+'.jsonl')
        require(pinned(e['data'])==dest and pinned(e['snapshot_receipt'])==Path(str(dest)+'.receipt.json') and pinned(e['original_receipt'])==root/'main_metric_phase'/(suite+'.original-receipt.json'),'snapshot location differs')
        require(e['original_path']==C.k_readout_path(str(root),suite,split,kind),'original location differs')
        original=read(e['original_receipt']['path']);mapped=dict(original,path=str(dest))
        require(original['path']==e['original_path'] and read(e['snapshot_receipt']['path'])==mapped,'receipt relocation differs')
        _,_,ordered=payload(d,rows,label,C,AS,SE,dest)
        result[label]={'n':len(rows[label]),'headline':C.headline(rows[label],[x['s'] for x in ordered])}
    return dict(schema='r3-main-metric-diagnostic-v1',contract_sha256=expected,marker=pin(marker),primary_input_mode=d['header_identity']['primary_input_mode'],partitions=result,**FLAGS)

class OptionalCollector:
    """Isolate diagnostic failures; never catch errors from the actual scorer."""
    def __init__(self,path,expected,C,AS,SE,header,producer,attempt,out,log):
        self.out=safe(out);self.log=log;self.inner=None
        try:self.inner=Collector(path,expected,C,AS,SE,header,producer,attempt,out)
        except Exception as error:self.fail(error)
    def fail(self,error):
        self.inner=None
        marker=self.out/'MAIN_METRIC_DIAGNOSTIC_FAILED.json'
        value=dict(schema='r3-main-metric-diagnostic-failed-v1',error=str(error)[:500],**FLAGS)
        try:
            if not marker.exists():publish(marker,value)
        except Exception as write_error:
            self.log('main-metric diagnostic failure could not persist: '+str(write_error)[:200])
        self.log('main-metric diagnostic failed: '+str(error)[:500])
    def completed(self,*args):
        if self.inner is None:return None
        try:return self.inner.completed(*args)
        except Exception as error:self.fail(error);return None

def main():
    import importlib
    import sys
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--contract',required=True);ap.add_argument('--sha256',required=True)
    ap.add_argument('--output',required=True,help='New diagnostic JSON only; never selection_report.json')
    a=ap.parse_args();require(sha(a.contract)==a.sha256,'contract changed');d=read(a.contract)
    require(pin(__file__)==d['phase_implementation'],'consumer implementation differs')
    require(safe(a.output).name=='main_metric_diagnostic.json','diagnostic output name required')
    for ref in d['files'].values():pinned(ref)
    for ref in d['libraries'].values():pinned(ref)
    directory=pinned(d['libraries']['core']).parent
    sys.path.insert(0,str(directory))
    C=importlib.import_module('core_r3');AS=importlib.import_module('admissible_store_r3');SE=importlib.import_module('selection_evidence_r3')
    value=consume(a.contract,a.sha256,C,AS,SE)
    publish(a.output,value)
    print(json.dumps({'status':'diagnostic_complete','output':pin(a.output),**FLAGS}))

if __name__=='__main__':main()
