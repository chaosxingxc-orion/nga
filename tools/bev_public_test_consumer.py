"""Bound CPU-only BEV public TEST consumer. Never launches NPU or reads raw logs."""
import argparse, collections, datetime, fcntl, hashlib, json, math, os, shlex, subprocess, time, types
from pathlib import Path


def require(ok, message):
    if not ok: raise ValueError(message)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def module(path,name):
    m=types.ModuleType(name);m.__file__=str(path)
    exec(compile(Path(path).read_bytes(),str(path),'exec',dont_inherit=True),m.__dict__);return m
def atomic(p,v):
    p=Path(p);temp=p.with_name(p.name+'.pending')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o644);os.fchmod(fd,0o644)
    with os.fdopen(fd,'w') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,p)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def population(requests,gold,expected=None):
    ids=[r['id'] for r in requests];gids=[g['id'] for g in gold]
    require(len(ids)==len(set(ids)) and ids==gids,'gold/request ordered IDs differ or duplicate')
    if expected is not None:require(len(ids)==expected,'population count differs')
    for r,g in zip(requests,gold):
        q=r['request'];k=q['type'];keys=q['candidate_keys']
        require(set(r)=={'id','request'} and set(g)=={'id','type','gold_index'}
                and g['type']==k and k in ('choice','noul','score'),'type/envelope differs')
        require(isinstance(keys,list) and len(keys)>=2 and len(keys)==len(set(keys)),'invalid candidates')
        require(type(g['gold_index']) is int and 0<=g['gold_index']<len(keys),'invalid gold index')
        require(len(q['definitions'])==len(keys),'definition count differs')
        if k=='noul':require(keys==['true','false'],'Noul candidate order differs')
        if k=='score':require(keys==[str(i) for i in range(len(keys))],'score order differs')
    return ids

def score(requests,gold,predictions):
    ids=set(population(requests,gold));by={}
    for p in predictions:
        require(p.get('id') in ids and p['id'] not in by,'unknown/duplicate prediction')
        by[p['id']]=p
    cells={k:[] for k in ('all','choice','noul','score')}
    for r,g in zip(requests,gold):
        p=by.get(r['id']);n=len(r['request']['candidate_keys']);status='missing' if p is None else p.get('status')
        valid=(status=='ok' and type(p.get('index')) is int and 0<=p['index']<n)
        if status=='ok' and not valid:status='invalid_prediction'
        if status not in ('ok','missing','refused','failed','unsupported_length','invalid_prediction'):status='invalid_prediction'
        c={'correct':int(valid and p['index']==g['gold_index']),'status':status}
        if r['request']['type']=='score':
            c['error']=abs(p['index']-g['gold_index']) if valid else None
            c['normalized_error']=c['error']/(n-1) if valid else 1.
        cells['all'].append(c);cells[g['type']].append(c)
    result={}
    for kind,rows in cells.items():
        n=len(rows);correct=sum(r['correct'] for r in rows);valid=sum(r['status']=='ok' for r in rows)
        d={'n':n,'correct':correct,'accuracy':correct/n if n else None,'valid_predictions':valid,'outcomes':dict(collections.Counter(r['status'] for r in rows))}
        if kind=='score':
            e=[r['error'] for r in rows if r['error'] is not None]
            normalized=[r['normalized_error'] for r in rows if r['error'] is not None]
            d.update(valid_prediction_index_mae=sum(e)/len(e) if e else None,mae_denominator=len(e),
                     valid_prediction_normalized_error=sum(normalized)/len(normalized) if normalized else None,
                     full_denominator=n,failure_count=n-len(e),failure_penalty=1.,
                     normalized_error_with_failure_penalty=sum(r['normalized_error'] for r in rows)/n if n else None)
        result[kind]=d
    return result

def flags(metrics):
    out=[];rates=[]
    for kind,cell in metrics.items():
        if cell['accuracy'] in (0.,1.):out.append({'type':kind,'flag':'exact_extreme_accuracy'})
        if cell['n']<30:out.append({'type':kind,'flag':'small_cell_descriptive_warning','n':cell['n'],'threshold':30})
        if cell['n']:rates.append(cell['accuracy'])
    if len(rates)>1 and len(set(rates))==1:out.append({'flag':'identical_accuracy_cells'})
    return out

def verify_config(path,pin):
    d,observed=snapshot(path);require(observed==pin,'config changed')
    require(d.get('schema')=='bev-public-test-cpu-config-v1' and d.get('scope')=='public_release_test'
            and d.get('candidate_selection_allowed') is False, 'consumer public TEST scope differs')
    require(d['scientific_acceptance'] is False and d['test_read'] is True and d['poll_interval_seconds']==600,'scope/poll differs')
    for p,h in d['files'].items():require(sha(p)==h,'dependency changed: '+p)
    require(d['files'][str(Path(__file__).resolve())]==sha(__file__),'consumer identity differs')
    require(d['files'].get(d['plan'])==d['plan_sha256'] and d['files'].get(d['gold'])==sha(d['gold']), 'CPU source pins missing')
    plan,observed=snapshot(d['plan']);require(observed==d['plan_sha256'],'plan differs')
    for group in ('code','inputs','model_files'):
        for item in plan[group].values():require(d['files'].get(item['path'])==item['sha256'],'CPU dependency coverage differs')
    R=module(plan['code']['runner']['path'],'public_test_cpu_runner')
    R.verify(d['plan'],d['plan_sha256'])
    if 'compatibility' in d:
        original=compatibility_inputs(d)
        require(d['gold']==original['gold'],'compatibility gold path differs')
    else:
        require(Path(d['gold']).parent==Path(path).parent,'gold placement differs')
    require(not Path(d['gold']).is_relative_to(Path(d['plan']).parent),'gold enters inference package')
    requests=[json.loads(x) for x in Path(plan['inputs']['requests']['path']).read_text().splitlines()]
    gold=[json.loads(x) for x in Path(d['gold']).read_text().splitlines()]
    population(requests,gold,6518)
    require(dict(collections.Counter(g['type'] for g in gold))==plan['expected_by_type'],'gold type population differs')
    d['_verified_config_sha256']=pin
    return d


def compatibility_inputs(d):
    c=d['compatibility']
    require(set(c)=={'kind','original_config','original_consumer','original_review'}
            and c['kind']=='docker_bind_order_only','unsupported CPU compatibility scope')
    values={}
    for key in ('original_config','original_consumer','original_review'):
        ref=c[key];require(set(ref)=={'path','sha256'} and d['files'].get(ref['path'])==ref['sha256'],'compatibility pin coverage differs')
        if key=='original_consumer':require(sha(ref['path'])==ref['sha256'],'compatibility dependency changed')
        else:
            values[key],observed=snapshot(ref['path'])
            require(observed==ref['sha256'],'compatibility dependency changed')
    original=values['original_config'];review=values['original_review']
    require('compatibility' not in original and original.get('schema')==d['schema'],'compatibility chain unsupported')
    for key in ('plan','plan_sha256','gold','scope','scientific_acceptance','test_read','candidate_selection_allowed','poll_interval_seconds'):
        require(original.get(key)==d.get(key),'original CPU contract differs: '+key)
    require(original['files'].get(c['original_consumer']['path'])==c['original_consumer']['sha256'],'original consumer binding differs')
    require(all(d['files'].get(p)==h for p,h in original['files'].items()),'original CPU files not preserved')
    require(review.get('activation_authorized') is True and review.get('scope')=='public_release_test'
            and review.get('scientific_acceptance') is False and review.get('candidate_selection_allowed') is False
            and review.get('approved_plan_sha256')==d['plan_sha256']
            and review.get('cpu_config_sha256')==c['original_config']['sha256']
            and review.get('consumer_sha256')==c['original_consumer']['sha256'],'original CPU admission differs')
    return original


def admit_compatibility(d,path,pin):
    require('compatibility' in d,'compatibility admission without compatibility config')
    compatibility_inputs(d);review,observed=snapshot(path);require(observed==pin,'compatibility review hash differs')
    require(review.get('schema')=='bev-public-cpu-compatibility-review-v1' and review.get('verdict')=='PASS'
            and review.get('consumption_authorized') is True and review.get('scientific_acceptance') is False
            and review.get('candidate_selection_allowed') is False and review.get('scope')=='public_release_test'
            and review.get('compatibility_kind')=='docker_bind_order_only','CPU compatibility admission differs')
    require(review.get('plan_sha256')==d['plan_sha256'] and review.get('cpu_config_sha256')==d['_verified_config_sha256']
            and review.get('consumer_sha256')==d['files'][str(Path(__file__).resolve())]
            and review.get('original')==d['compatibility'],'CPU compatibility identity differs')
    require(all(review.get('hashes',{}).get(p)==h for p,h in d['files'].items()),'CPU compatibility review coverage differs')
    d['_compatibility_review']={'path':str(path),'sha256':pin}
    return d

def snapshot(path):
    """One stable byte snapshot supplies both semantics and evidence hash."""
    path=Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)), 'unsafe evidence path')
    with path.open('rb') as f:
        before=os.fstat(f.fileno());raw=f.read();after=os.fstat(f.fileno())
    identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
    require(identity(before)==identity(after),'evidence changed during read')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def remote_json(command):
    return json.loads(subprocess.check_output(['ssh','npu',shlex.join(command)],text=True,timeout=45))


def review_lineage(d,plan,attempt,start,service):
    command=start.get('command')
    require(isinstance(command,list) and len(command)==15 and
            Path(command[0]).is_absolute() and Path(command[0]).name in ('python3','python3.12'),
            'supervisor interpreter/command differs')
    require(command[1:7]==['-B','-P',plan['code']['host']['path'],'supervise','--plan',d['plan']]
            and command[7:10]==['--sha256',d['plan_sha256'],'--review']
            and command[11]=='--review-sha256' and command[13:]==['--attempt',str(attempt)],
            'supervisor plan/review/attempt command differs')
    require(service.get('command')==command and type(service.get('pid')) is int and service['pid']>0,
            'supervisor service binding differs')
    path=Path(command[10]);review,pin=snapshot(path)
    require(pin==command[12] and review.get('activation_authorized') is True
            and review.get('scientific_acceptance') is False and review.get('scope')=='public_release_test'
            and review.get('candidate_selection_allowed') is False
            and review.get('approved_plan_sha256')==d['plan_sha256'] and attempt in review.get('attempts',[]),
            'original activation review differs')
    expected_config=d.get('_verified_config_sha256');expected_consumer=d['files'][str(Path(__file__).resolve())]
    if 'compatibility' in d:
        c=d['compatibility'];compatibility_inputs(d)
        require(str(path)==c['original_review']['path'] and pin==c['original_review']['sha256'],'original launch review differs')
        expected_config=c['original_config']['sha256'];expected_consumer=c['original_consumer']['sha256']
    require(review.get('deployment_suitable') is True and review.get('cpu_config_sha256')==expected_config
            and review.get('consumer_sha256')==expected_consumer,
            'original CPU review differs')
    require(review.get('hashes',{}).get(d['plan'])==d['plan_sha256'],'original review plan coverage differs')
    for group in ('code','inputs','model_files'):
        for item in plan[group].values():
            require(review.get('hashes',{}).get(item['path'])==item['sha256'],'original review dependency coverage differs')
    # A reused PID does not represent this supervisor; unknown observations fail.
    script="import json,pathlib; p=pathlib.Path('/proc')/"+repr(str(service['pid']))+"; c=(p/'cmdline').read_bytes().split(b'\\0')[:-1] if (p/'cmdline').exists() else []; print(json.dumps({'same_supervisor':c=="+repr([x.encode() for x in command])+"}))"
    observed=remote_json([command[0],'-B','-P','-c',script])
    require(observed=={'same_supervisor':False},'supervisor still running or observation unknown')
    return {str(path):pin}


def timestamp(value):
    require(isinstance(value,str) and not value.startswith('0001-'),'invalid lifecycle time')
    parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    require(parsed.tzinfo is not None,'timezone required')
    return parsed.timestamp()


def expected_launch(plan,d,attempt,spec):
    name=plan['container']+'-a'+str(attempt)
    devices=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(plan['chip'])]
    prefix=['docker','run','-d','--name',name,'--network','none','--shm-size','16g',
            '--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
    for device in devices:prefix+=['--device',device]
    binds=['/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro']
    prefix+=['-v',binds[0]]
    for key,value in plan['environment'].items():prefix+=['-e',key+'='+value]
    for m in plan['mounts']:
        bind=m['source']+':'+m['destination']+(':ro' if m['readonly'] else '')
        binds.append(bind);prefix+=['-v',bind]
    command=spec.get('command')
    require(isinstance(command,list) and command[:len(prefix)]==prefix,'exact launch prefix differs')
    tail=command[len(prefix):]
    for platform in ('/usr/local/sbin','/etc/ascend_install.info'):
        option=['-v',platform+':'+platform+':ro']
        if tail[:2]==option:
            binds.append(option[1]);tail=tail[2:]
    runner=['python3','-B','-P',plan['code']['runner']['path'],'run','--plan',d['plan'],
            '--sha256',d['plan_sha256'],'--attempt',str(attempt)]
    require(tail==[plan['image_sha256'],*runner],'exact launch suffix differs')
    return runner,devices,binds


def effective_container(plan,d,attempt,spec,launch,actual,image,daemon):
    runner,devices,binds=expected_launch(plan,d,attempt,spec)
    cfg=actual.get('Config',{});host=actual.get('HostConfig',{})
    require(cfg.get('Cmd')==launch.get('command')==runner,'exact runner command differs')
    require(cfg.get('Entrypoint')==image.get('Config',{}).get('Entrypoint'),'image entrypoint differs')
    require(actual.get('Path')==((cfg.get('Entrypoint') or runner)[0]),'effective process path differs')
    effective=(cfg.get('Entrypoint') or [])+runner
    require(actual.get('Args')==effective[1:],'effective process arguments differ')
    expected_devices=[{'PathOnHost':x,'PathInContainer':x,'CgroupPermissions':'rwm'} for x in devices]
    require(host.get('Devices')==expected_devices,'exact device map differs')
    observed_binds=host.get('Binds')
    require(isinstance(observed_binds,list) and all(isinstance(x,str) for x in observed_binds)
            and len(observed_binds)==len(set(observed_binds))
            and len(binds)==len(set(binds)) and collections.Counter(observed_binds)==collections.Counter(binds)
            and not host.get('Mounts'),'exact host bind configuration differs')
    mounts=actual.get('Mounts')
    require(isinstance(mounts,list) and len(mounts)==len(binds),'mount inventory differs')
    expected={}
    for bind in binds:
        parts=bind.split(':');expected[parts[1]]=(parts[0],len(parts)==2)
    require(len(expected)==len(binds),'duplicate expected mount')
    found={}
    for mount in mounts:
        dest=mount.get('Destination');require(dest not in found,'duplicate actual mount')
        require(mount.get('Type')=='bind' and mount.get('Propagation')=='rprivate','mount kind/propagation differs')
        require(mount.get('Mode')==('' if mount.get('RW') else 'ro'),'mount mode differs')
        found[dest]=(mount.get('Source'),mount.get('RW'))
    require(found==expected,'exact mount set differs')
    require(host.get('ShmSize')==16*1024**3,'shared memory differs')
    limits=host.get('Ulimits') or []
    require(len(limits)==2 and {x.get('Name'):(x.get('Soft'),x.get('Hard')) for x in limits}
            =={'memlock':(-1,-1),'stack':(67108864,67108864)},'ulimits differ')
    resource=plan['code']['resource'];raw=Path(resource['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==resource['sha256'],'resource policy changed')
    adapter=types.ModuleType('bev_public_resource_policy');adapter.__file__=resource['path']
    exec(compile(raw,resource['path'],'exec',dont_inherit=True),adapter.__dict__)
    # All bind bytes were checked above; shared policy rejects unhandled binds.
    normalized=dict(actual,HostConfig=dict(host,Binds=None))
    adapter.verify_effective_policy(normalized,image,plan['environment'],daemon=daemon)


def claim_lineage(claim,claim_pin,release,plan,claim_path,adapter):
    require(claim.get('schema')=='r3-resource-claim-v1' and release.get('schema')=='r3-resource-release-v1','resource schema differs')
    require(claim.get('run')==release.get('run')==plan['run'] and
            claim.get('chip')==release.get('chip')==plan['chip'],'claim/release role differs')
    require(claim.get('allocation')==plan['allocation'] and release.get('claim_sha256')==claim_pin,'claim hash/ledger lineage differs')
    entry=claim.get('entry');require(isinstance(entry,dict) and entry.get('chip')==plan['chip']
            and entry.get('run')==plan['run'] and entry.get('claimed_utc')==claim.get('claimed_utc'),'claim generation differs')
    for receipt in (claim,release):
        for side in ('before','after'):
            value=receipt['allocation_'+side];adapter.validate_doc(value)
            raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
            require(hashlib.sha256(raw).hexdigest()==receipt.get('allocation_'+side+'_sha256'),'allocation snapshot hash differs')
    before=claim['allocation_before'];after=claim['allocation_after'];chip=plan['chip']
    require(not any(x['chip']==chip for x in before['allocation']) and
            len([x for x in before['free'] if x['chip']==chip])==1,'claim prior ownership differs')
    require(after['allocation']==sorted(before['allocation']+[entry],key=lambda x:x['chip'])
            and after['free']==[x for x in before['free'] if x['chip']!=chip],'claim transition differs')
    rb=release['allocation_before'];ra=release['allocation_after']
    require([x for x in rb['allocation'] if x['chip']==chip]==[entry]
            and not any(x['chip']==chip for x in rb['free']),'release claim generation differs')
    free=[x for x in ra['free'] if x['chip']==chip]
    expected_release=str(claim_path.with_name('RELEASE.json'))
    require(len(free)==1 and free[0].get('previous_run')==plan['run']
            and free[0].get('release_evidence')==expected_release,'release free evidence differs')
    require(ra['allocation']==[x for x in rb['allocation'] if x['chip']!=chip]
            and [x for x in ra['free'] if x['chip']!=chip]==rb['free'],'release transition differs')


def lifecycle(d,plan):
    out=Path(plan['out']);complete=out/'COMPLETE.json'
    if not complete.exists():
        for failed in (out/'host_attempts').glob('*/EXIT.json'):
            require(load(failed).get('exit_code')==0,'producer failure requires review')
        return None
    c,complete_pin=snapshot(complete);a=c['attempt'];require(type(a) is int and a>0,'invalid attempt')
    run=out/'attempts'/str(a);host=out/'host_attempts'/str(a)
    paths=[run/'EXIT.json',host/'EXIT.json',host/'RELEASE.json',host/'LAUNCH_RECEIPT.json',host/'LAUNCH_SPEC.json',host/'CLAIM.json',host/'START_INTENT.json',host/'SERVICE.json']
    if not all(p.exists() for p in paths):return None
    snaps=[snapshot(p) for p in paths];end,hend,release,launch,spec,claim,start,service=[x[0] for x in snaps]
    pins={str(complete):complete_pin,**{str(p):value[1] for p,value in zip(paths,snaps)}}
    require(c.get('scientific_acceptance') is False and c.get('test_read') is True,'completion scope differs')
    require(c['schema']=='bev-public-test-completion-v1' and c['exit_code']==end['exit_code']==hend['exit_code']==release['exit_code']==0,'producer not successful')
    require(c['plan_sha256']==end['plan_sha256']==launch['plan_sha256']==spec['plan_sha256']==d['plan_sha256'],'terminal plan mismatch')
    require(end['attempt']==a and c['rows']==6518 and c['outcomes']=={'ok':6518},'terminal population differs')
    cid=launch['container_id'];name=plan['container']+'-a'+str(a)
    require(hend['container_id']==release['container_id']==cid and hend['runner_terminal_matches'] is True and hend['container_exit_code']==0,'host identity differs')
    require(release['chip']==plan['chip'] and release['run']==plan['run'] and release['container']==name,'release identity differs')
    actuals=remote_json(['docker','inspect',cid]);images=remote_json(['docker','image','inspect',plan['image_sha256']])
    info=remote_json(['docker','info','--format','{{json .}}'])
    require(isinstance(actuals,list) and len(actuals)==1 and isinstance(images,list) and len(images)==1,'ambiguous Docker observation')
    actual,image=actuals[0],images[0]
    require(info.get('DefaultRuntime') and info.get('CgroupVersion') in ('1','2'),'unknown daemon policy')
    daemon={'runtime':info['DefaultRuntime'],'cgroupns':'private' if info['CgroupVersion']=='2' else 'host'}
    require(actual['Id']==cid and actual['Name']=='/'+name and actual['Image']==plan['image_sha256'],'retained identity differs')
    require(actual['State']['Status']=='exited' and actual['State']['ExitCode']==0 and not actual['HostConfig']['AutoRemove'],'retained terminal differs')
    require(release.get('container_started_at')==actual['State'].get('StartedAt') and
            release.get('container_finished_at')==actual['State'].get('FinishedAt'),'retained generation times differ')
    claimed=timestamp(claim.get('claimed_utc'));began=timestamp(actual['State'].get('StartedAt'))
    finished=timestamp(actual['State'].get('FinishedAt'));released=timestamp(release.get('released_utc'))
    require(claimed<=began<=finished<=released,'claim/container/release chronology differs')
    require(type(start.get('utc_seconds')) in (int,float) and start['utc_seconds']<=claimed
            and type(hend.get('utc_seconds')) in (int,float) and released<=hend['utc_seconds'],
            'supervisor chronology differs')
    pins.update(review_lineage(d,plan,a,start,service))
    effective_container(plan,d,a,spec,launch,actual,image,daemon)
    resource=plan['code']['resource'];require(sha(resource['path'])==resource['sha256'],'resource changed')
    adapter=module(resource['path'],'bev_public_lineage')
    claim_lineage(claim,pins[str(host/'CLAIM.json')],release,plan,host/'CLAIM.json',adapter)
    require(all(sha(p)==h for p,h in pins.items()),'lifecycle changed during validation')
    return c,pins

def consume(d):
    compatibility_pins={}
    if 'compatibility' in d:
        admission=d.get('_compatibility_review');require(isinstance(admission,dict),'CPU compatibility review required')
        admit_compatibility(d,admission['path'],admission['sha256'])
        compatibility_pins[admission['path']]=admission['sha256']
    plan,observed=snapshot(d['plan']);require(observed==d['plan_sha256'],'plan mismatch')
    require(plan['schema']=='bev-public-test-plan-v1' and plan['test_read'] is True and plan['scientific_acceptance'] is False,'plan scope differs')
    ready=lifecycle(d,plan)
    if ready is None:return None
    complete,pins=ready;pins.update(compatibility_pins)
    requests=[json.loads(x) for x in Path(plan['inputs']['requests']['path']).read_text().splitlines()]
    gold=[json.loads(x) for x in Path(d['gold']).read_text().splitlines()]
    ids=population(requests,gold,6518);require(ids==load(plan['inputs']['ids']['path']),'ordered population differs')
    require(dict(collections.Counter(g['type'] for g in gold))=={'choice':3002,'noul':2835,'score':681},'type denominators differ')
    by={hashlib.sha256(r['id'].encode()).hexdigest()+'.json':r for r in requests};out=Path(plan['out'])/'items'
    require(set(complete['items'])==set(by)=={p.name for p in out.iterdir() if '.pending-' not in p.name},'item inventory differs')
    preds=[]
    for name,row in by.items():
        p=out/name;v,h=snapshot(p);require(h==complete['items'][name],'item changed');pins[str(p)]=h
        require(v.get('scientific_acceptance') is False and v.get('test_read') is True,'item scope differs')
        require(v['schema']=='bev-public-test-item-v1' and v['id']==row['id'] and v['plan_sha256']==d['plan_sha256'] and v['request_sha256']==digest(row),'item binding differs')
        raw=v['raw'];n=len(row['request']['candidate_keys'])
        require(isinstance(raw,list) and len(raw)==n and all(type(x) in (int,float) and math.isfinite(x) for x in raw),'invalid raw scores')
        i=max(range(n),key=lambda j:raw[j]);ordered=sorted(raw,reverse=True)
        expected={'id':row['id'],'status':'ok','index':i,'exact_tie':sum(x==raw[i] for x in raw)>1,'top2_gap_nats':ordered[0]-ordered[1]}
        require(v['prediction']==expected,'decoded prediction differs');preds.append(expected)
    metrics=score(requests,gold,preds)
    require(all(sha(p)==h for p,h in pins.items()),'producer changed during consumption')
    require(all(sha(p)==h for p,h in d['files'].items()),'dependency changed during consumption')
    return {'schema':'bev-public-test-cpu-result-v1','protocol':'bev-local-typed-exact-release-test-v1','scope':'public_release_test','metrics':metrics,'flags':flags(metrics),'plan_sha256':d['plan_sha256'],'inputs':{**d['files'],**pins},'scientific_acceptance':False,'test_read':True,'native_reproduction':False,'limitations':['No TEST-label-fitted oracle or model selection.','Public release TEST under local protocol; no native-reproduction, consistency or training-gain claim.','Full inference requires all6518 successful outputs; pure scoring preserves failed predictions in denominator but failed lifecycle yields no accepted result.','Small-cell warning30 is descriptive monitoring only, not a scientific threshold.']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--once',action='store_true')
    ap.add_argument('--compatibility-review');ap.add_argument('--compatibility-review-sha256')
    a=ap.parse_args();path=Path(a.config);root=path.parent
    with (root/'consumer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'EXIT.json').exists():
            e=load(root/'EXIT.json');require(e['exit_code']==0 and e.get('config_sha256')==a.sha256
                and sha(root/'report.json')==e['report_sha256'],'prior terminal requires review');return
        try:
            while True:
                d=verify_config(path,a.sha256)
                if 'compatibility' in d:
                    require(a.compatibility_review and a.compatibility_review_sha256,'independent CPU compatibility review required')
                    admit_compatibility(d,a.compatibility_review,a.compatibility_review_sha256)
                else:require(not a.compatibility_review and not a.compatibility_review_sha256,'unexpected compatibility review')
                value=consume(d)
                atomic(root/'digest.json',{'utc_seconds':time.time(),'status':'done' if value else 'waiting_inference','scientific_acceptance':False})
                if value is not None:
                    atomic(root/'report.json',value);atomic(root/'EXIT.json',{'exit_code':0,'report_sha256':sha(root/'report.json'),'config_sha256':a.sha256,'scientific_acceptance':False});return
                if a.once:return
                time.sleep(600)
        except Exception as e:
            atomic(root/'EXIT.json',{'exit_code':1,'status':'needs_review','error':str(e)[:1000],'config_sha256':a.sha256,'scientific_acceptance':False});raise
if __name__=='__main__':main()
