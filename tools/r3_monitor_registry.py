#!/usr/bin/env python3
"""Script-only logical task monitoring; never grants experimental qualification."""
import argparse, collections, fcntl, hashlib, importlib.util, json, math, os, signal, subprocess, sys, time
from pathlib import Path

LIMIT=2**20

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate JSON key')
        result[k]=v
    return result

def read(path):
    with Path(path).open('rb') as f: data=f.read(LIMIT+1)
    if len(data)>LIMIT: raise ValueError('JSON exceeds bounded size')
    d=json.loads(data,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    if not isinstance(d,dict): raise ValueError('object required')
    return d

def put(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.pending')
    with tmp.open('w') as f:json.dump(data,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def verify(path,pin):
    if sha(path)!=pin:raise ValueError('configuration changed')
    c=read(path)
    if c['schema']!='r3-monitor-registry-v1' or c['interval_seconds']!=600 or c['scientific_acceptance'] is not False:raise ValueError('monitor scope differs')
    for ref in (c['watchdog'],c['runner']):
        if sha(ref['path'])!=ref['sha256']:raise ValueError('source changed')
    if not Path(c['output']).is_absolute() or '..' in Path(c['output']).parts:raise ValueError('absolute output required')
    if not 0<len(c['tasks'])<=128:raise ValueError('task count outside bound')
    ids=[t['id'] for t in c['tasks']]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate logical task')
    if Path(c['runner']['path']).resolve()!=Path(__file__).resolve():raise ValueError('runner path differs')
    for g in c['groups'].values():
        if not g['markers'] or any('/' in n or '\\' in n for n in g['markers']):raise ValueError('bare marker names required')
    for t in c['tasks']:
        if type(t['chip'])is not int or not 0<=t['chip']<8:raise ValueError('chip differs')
        if not t['required_phases']:raise ValueError('required phases missing')
        for role,p in t['phases'].items():
            if role not in c['groups'] or not Path(p).is_absolute():raise ValueError('phase binding differs')
        if not set(t['required_phases'])<=set(t['phases']):raise ValueError('required phase unregistered')
    return c

def group_command(c,name,out):
    g=c['groups'][name];roots=sorted({t['phases'][name] for t in c['tasks'] if name in t['phases']})
    cmd=[sys.executable,'-B','-P',c['watchdog']['path']]
    for p in roots:cmd+=['--root',p]
    return cmd+['--out-dir',str(out),'--max-depth','0','--marker-names',','.join(g['markers']),'--log-globs',','.join(g['logs']),'--no-npu','--max-md-bytes','12000']

def phase_observation(digest,path,error=None):
    if error:return {'state':'unknown','reason':error,'path':path}
    rows=[r for r in digest.get('runs',[]) if r.get('path')==path]
    if len(rows)!=1:return {'state':'not_observed_or_queued','path':path,'reason':'registered root absent from digest'}
    r=rows[0]
    return {'state':r['state'],'path':path,'reason':r.get('state_reason'),
            'progress':r.get('progress'),'perf':r.get('perf'),'errors':r.get('errors'),
            'pointers':r.get('pointers',[]),'escalation':r.get('escalation'),
            'logs':r.get('logs',[]),'log_evidence':r.get('log_evidence',[]),
            'progress_flat':r.get('progress_flat'),'json_progress_history':r.get('json_progress_history')}

def release_observation(task):
    ref=task['release'];p=Path(ref['path']);claimp=Path(ref['claim'])
    if not p.exists():return {'state':'not_observed','path':str(p)}
    try:
        r=read(p);cl=read(claimp)
        if r.get('schema')!='r3-resource-release-v1' or cl.get('schema')!='r3-resource-claim-v1':raise ValueError('release/claim schema differs')
        if any(type(o.get('chip'))is not int or o['chip']!=task['chip'] or o.get('run')!=task['run'] for o in (r,cl)):raise ValueError('release/claim task differs')
        if type(r.get('exit_code'))is not int or r.get('scientific_acceptance')is not False:raise ValueError('release scope/code differs')
        if r.get('container')!=task['container'] or type(r.get('container_id'))is not str or len(r['container_id'])!=64 or any(x not in '0123456789abcdef' for x in r['container_id']):raise ValueError('release container differs')
        if 'claim_sha256' in r:
            if r['claim_sha256']!=sha(claimp):raise ValueError('release claim hash differs')
            state='released_bound'
        elif ref.get('legacy_release_sha256')==sha(p) and ref.get('legacy_claim_sha256')==sha(claimp):state='released_legacy_observed'
        else:raise ValueError('release claim binding missing')
        # Tie release to actual recorded host/runtime terminal, not arbitrary claim.
        terminal=read(ref['terminal'])
        receipt=read(ref['receipt'])
        if receipt.get(ref.get('receipt_id_field','container_id'))!=r['container_id']:raise ValueError('launch receipt container differs')
        if 'container_id' in terminal and terminal['container_id']!=r['container_id']:raise ValueError('terminal container differs')
        if type(terminal.get('exit_code'))is not int or terminal['exit_code']!=r['exit_code']:raise ValueError('terminal release code differs')
        for obj in (r,terminal):
            for key in ('rc','returncode','return_code','exit_status'):
                if key in obj and (type(obj[key]) is not int or obj[key]!=obj['exit_code']):raise ValueError('conflicting exit aliases')
        return {'state':state,'path':str(p),'exit_code':r['exit_code'],'container_id':r['container_id'],'released_utc':r.get('released_utc'),'modern_binding':state=='released_bound'}
    except (OSError,ValueError,TypeError,KeyError) as e:return {'state':'unknown','path':str(p),'reason':str(e)[:160]}

def aggregate(task,phases,release):
    required=[phases[k]['state'] for k in task['required_phases']]
    cpu=phases.get('cpu',{'state':task.get('cpu_scope','not_registered')})
    success=all(s=='done' for s in required)
    release_ok=release['state'] in ('released_bound','released_legacy_observed') and release.get('exit_code')==0
    if any(s=='failed' for s in required):state='failed'
    elif success and release_ok:
        state=('complete_observed' if cpu['state'] in ('done','not_required') else
               'inference_complete_cpu_untracked' if cpu['state']=='not_registered' else
               'cpu_failed' if cpu['state']=='failed' else
               'cpu_unknown' if cpu['state'] in ('unknown','stalled') else 'awaiting_cpu')
    elif success:state='awaiting_release' if release['state']=='not_observed' else 'release_unknown'
    elif release['state']=='unknown':state='release_unknown'
    elif any(s=='unknown' for s in required):state='unknown'
    elif any(s=='stalled' for s in required):state='stalled'
    elif all(s=='not_observed_or_queued' for s in required):state='not_observed_or_queued'
    else:state='running'
    # Completed inference overrides its old progress timestamp, not its log errors.
    progress=phases.get('progress',phases.get('scoring',{}))
    if state=='running' and progress.get('state')=='stalled':state='stalled'
    issues=[];physical={}
    for role,p in phases.items():
        errors=p.get('errors') or {}
        if errors.get('error_lines',0) or errors.get('warning_lines',0):issues.append({'phase':role,'error_lines':errors.get('error_lines',0),'warning_lines':errors.get('warning_lines',0),'pointers':p.get('pointers',[])[:8]})
        for e in p.get('log_evidence',[]):
            key=(e['device'],e['inode']);old=physical.get(key)
            if old is None:physical[key]=dict(e)
            else:
                for field in ('error_lines','warning_lines','untracked_lines'):old[field]=max(old[field],e[field])
    counts={k:sum(e[k] for e in physical.values()) for k in ('error_lines','warning_lines','untracked_lines')}
    if not physical:counts={k:sum(i.get(k,0) for i in issues) for k in ('error_lines','warning_lines','untracked_lines')}
    return {'id':task['id'],'chip':task['chip'],'state':state,'inference_complete_observed':success,
            'release':release,'cpu_state':cpu['state'],'progress':progress.get('progress'),
            'perf':progress.get('perf'),'phases':phases,'log_issues':issues,'log_counts':counts,
            'log_availability':list(physical.values()),'progress_flat':progress.get('progress_flat'),
            'warnings_trigger_agent':False,
            'scientific_acceptance':False,'resource_reuse_authorized':False}

def load_watchdog(ref):
    if sha(ref['path']) != ref['sha256']:raise ValueError('watchdog source changed')
    spec=importlib.util.spec_from_file_location('registry_watchdog',ref['path'])
    w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
    original=w.read_json_heartbeat
    def heartbeat(path):
        try:
            d=read(path)
            if type(d.get('utc_seconds')) not in (int,float) or not math.isfinite(d['utc_seconds']) or d['utc_seconds']<=0 or d['utc_seconds']>time.time()+120:raise ValueError('invalid/future heartbeat timestamp')
            legacy={'pid','progress_unit','readout_bytes','readout_files','utc_seconds'}
            if set(d)==legacy:
                if d['progress_unit']!='files and bytes, not scored questions':raise ValueError('legacy progress unit differs')
                if type(d['pid']) is not int or d['pid']<=0 or any(type(d[k]) is not int or d[k]<0 for k in ('readout_files','readout_bytes')):raise ValueError('invalid legacy counters')
                return dict(ts=d['utc_seconds'],done=None,total=None,counters={k:d[k] for k in ('readout_files','readout_bytes')},fields={'progress_unit':d['progress_unit']},perf=None,source=w.JSON_HEARTBEAT,snapshot=True,phase=None),None
            return original(path)
        except (OSError,ValueError,TypeError) as e:return None,'JSON heartbeat invalid: '+str(e)[:100]
    w.read_json_heartbeat=heartbeat
    original_logs=w.run_logs
    def canonical_logs(root,cfg):
        found={}
        for p in original_logs(root,cfg):
            try:
                st=os.stat(p);found.setdefault((st.st_dev,st.st_ino),str(Path(p).resolve()))
            except OSError:pass
        return sorted(found.values())
    w.run_logs=canonical_logs
    return w


def load_state(path,w,binding):
    if not Path(path).exists():return {},{},None
    try:
        with Path(path).open('rb') as f:raw=f.read(32*2**20+1)
        if len(raw)>32*2**20:raise ValueError('state exceeds bound')
        d=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite state')))
        if d['binding']!=binding:raise ValueError('state binding differs')
        states={}
        for p,v in d['logs'].items():
            st=w.LogState()
            for k in ('inode','offset','lineno','dropped'):
                if type(v[k]) is not int or v[k]<0:raise ValueError('invalid state integer')
                setattr(st,k,v[k])
            st.registry_dev=v['dev'];st.registry_prefix=v['prefix'];st.registry_prefix_size=v['prefix_size']
            if len(v['sigs'])>500:raise ValueError('state signature bound')
            for key,values in v['sigs'].items():
                if set(values)!=set(w.Sig.__slots__):raise ValueError('state signature fields')
                e=w.Sig()
                for k,value in values.items():setattr(e,k,value)
                if e.sev not in ('warning','error') or type(e.count)is not int or e.count<0:raise ValueError('state severity/count')
                st.sigs[key]=e
            states[p]=st
        return states,d['history'],None
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as e:return {},{},'scan state reset: '+str(e)[:120]


def persist_state(path,states,history,binding):
    logs={}
    for p,st in states.items():
        if st.inode is None:continue
        logs[p]={**{k:getattr(st,k) for k in ('inode','offset','lineno','dropped')},'dev':st.registry_dev,'prefix':st.registry_prefix,'prefix_size':st.registry_prefix_size,
                 'sigs':{k:{a:getattr(e,a) for a in e.__slots__} for k,e in st.sigs.items()}}
    put(path,{'binding':binding,'logs':logs,'history':history})


def prepare_log_state(path,st):
    stat=os.stat(path)
    # Detect rename/replacement, truncation, and same-inode truncate+regrowth.
    prefix_size=min(stat.st_size,4096)
    with open(path,'rb') as f:
        old=f.read(getattr(st,'registry_prefix_size',0))
        f.seek(0);prefix=f.read(prefix_size)
    if (getattr(st,'registry_dev',stat.st_dev)!=stat.st_dev or
        (getattr(st,'registry_prefix_size',0) and hashlib.sha256(old).hexdigest()!=getattr(st,'registry_prefix',''))):
        st.reset(stat.st_ino)
    st.registry_dev=stat.st_dev;st.registry_prefix=hashlib.sha256(prefix).hexdigest();st.registry_prefix_size=prefix_size


def json_progress_history(w,path,row,history,now):
    jp=Path(path)/'heartbeat.json'
    if not jp.exists():return
    sample,err=w.read_json_heartbeat(str(jp))
    if err or sample['done'] is None:return
    obj=read(jp);identity=[obj.get('phase'),obj.get('attempt'),sample['total']]
    previous=history.get(path)
    if (not previous or previous.get('identity')!=identity or sample['done']<previous['done'] or sample['ts']<previous['last_ts']):
        previous={'identity':identity,'done':sample['done'],'since':sample['ts'],'last_ts':sample['ts'],'samples':1}
    elif sample['ts']>previous['last_ts']:
        if sample['done']!=previous['done']:previous.update(done=sample['done'],since=sample['ts'],samples=0)
        previous['samples']+=1;previous['last_ts']=sample['ts']
    history[path]=previous
    row['json_progress_history']={**previous,'source':str(jp),'rate_derived':False}
    flat=previous['last_ts']-previous['since']
    if row['state']=='running' and previous['samples']>=3 and flat>=2*row['tier']['stall_s']:
        row['progress_flat']={'flat_s':flat,'done':previous['done'],'samples':previous['samples'],'confirmed':True,'source':str(jp)}
        row['escalation']='read';row['escalation_reason']='JSON progress unchanged across observed heartbeats'


def observe_group(c,name,out,w,now):
    dest=Path(out)/'phases'/name;dest.mkdir(parents=True,exist_ok=True)
    roots=sorted({t['phases'][name] for t in c['tasks'] if name in t['phases']})
    group=c['groups'][name]
    cfg=w.make_cfg(root=roots,out_dir=str(dest),max_depth=0,perf_depth=0,marker_names=','.join(group['markers']),log_globs=','.join(group['logs']),no_npu=True,max_md_bytes=12000)
    binding=hashlib.sha256(json.dumps({'watchdog':c['watchdog'],'runner':c['runner'],'group':group,'roots':roots},sort_keys=True).encode()).hexdigest()
    states,history,state_note=load_state(dest/'scan-state.json',w,binding)
    rows=[];used=set();scanned=0
    for path in roots:
        if not Path(path).is_dir():continue
        logs=w.run_logs(path,cfg)
        before={}
        for p in logs:
            used.add(p);st=states.setdefault(p,w.LogState());prepare_log_state(p,st)
            stat=os.stat(p);before[p]=st.offset if st.inode==stat.st_ino and stat.st_size>=st.offset else 0
        row=w.evaluate_run({'id':path,'path':path,'root':path,'id_prefix':''},cfg,states,now)
        row['log_evidence']=[]
        for p in logs:
            st=states[p];scanned+=max(0,st.offset-before[p]);stat=os.stat(p)
            row['log_evidence'].append({'path':p,'device':stat.st_dev,'inode':stat.st_ino,'error_lines':sum(e.count for e in st.sigs.values() if e.sev=='error'),'warning_lines':sum(e.count for e in st.sigs.values() if e.sev=='warning'),'untracked_lines':st.dropped,'size_bytes':stat.st_size})
        if not row['marker'] and not (Path(path)/'heartbeat.json').exists() and not (Path(path)/cfg.heartbeat_name).exists():
            row.update(state='unknown',state_reason='registered directory exists without heartbeat or terminal',escalation='read')
        json_progress_history(w,path,row,history,now)
        # Warn-only evidence gets pointers, without forcing agent escalation.
        for sig in row['errors']['signatures']:
            ex=sig['exemplar']
            if len(row['pointers'])<8:row['pointers'].append({'path':ex['log'],'line_start':ex['line_start'],'line_end':ex['line_end'],'why':sig['severity']+' signature'})
            ex.pop('text',None)
        rows.append(row)
    states={p:st for p,st in states.items() if p in used}
    history={p:h for p,h in history.items() if p in roots}
    persist_state(dest/'scan-state.json',states,history,binding)
    digest={'generated_utc':w.iso(now),'runs':rows,'scan_bytes':scanned,'state_note':state_note}
    put(dest/'digest.json',digest)
    (dest/'digest.md').write_text('# Phase observations\n\n'+ '\n'.join('| '+r['path']+' | '+r['state']+' | errors '+str(r['errors']['error_lines'])+' warnings '+str(r['errors']['warning_lines'])+' |' for r in rows)+'\n')
    return digest


def compact_flags(task):
    flags=[]
    for role,phase in task['phases'].items():
        if phase.get('progress_flat'):flags.append(role+':progress_flat')
        if phase.get('escalation') not in (None,'none'):flags.append(role+':'+str(phase['escalation']))
    return ', '.join(flags) or '-'

def once(c,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);digests={};errors={};started=time.monotonic();w=load_watchdog(c['watchdog'])
    for name in c['groups']:
        try:digests[name]=observe_group(c,name,out,w,time.time())
        except (OSError,ValueError,TypeError,KeyError) as e:errors[name]=str(e)[:160];digests[name]={}
    tasks=[]
    for t in c['tasks']:
        ph={role:phase_observation(digests[role],path,errors.get(role)) for role,path in t['phases'].items()}
        tasks.append(aggregate(t,ph,release_observation(t)))
    result={'schema':'r3-monitor-logical-digest-v2','utc_seconds':time.time(),'interval_seconds':600,
            'logical_task_count':len(tasks),'counts':dict(collections.Counter(t['state'] for t in tasks)),
            'tasks':tasks,'group_errors':errors,'scan_bytes':sum(d.get('scan_bytes',0) for d in digests.values()),
            'state_notes':{k:d['state_note'] for k,d in digests.items() if d.get('state_note')},
            'pass_seconds':time.monotonic()-started,'scientific_acceptance':False,'resource_reuse_authorized':False,
            'hardware_sampling':'None; global hardware monitor remains separate; this registry never claims cards.'}
    put(out/'digest.json',result)
    lines=['# Logical experiment monitor','One row per registered task; observations do not grant qualification.','', '| Task | Chip | State | CPU | Release | Errors | Warnings | Flags |','| --- | ---: | --- | --- | --- | ---: | ---: | --- |']
    lines += ['| '+t['id']+' | '+str(t['chip'])+' | '+t['state']+' | '+t['cpu_state']+' | '+t['release']['state']+' | '+str(t['log_counts']['error_lines'])+' | '+str(t['log_counts']['warning_lines'])+' | '+compact_flags(t)+' |' for t in tasks]
    lines += ['', 'Bounded evidence pointers: digest.json. Empty logs do not prove absence of faults.', 'Physical logs are deduplicated within each task. No resource reuse or scientific acceptance authority.']
    (out/'digest.md').write_text('\n'.join(lines)+'\n')
    put(out/'heartbeat.json',{'utc_seconds':time.time(),'state':'monitor_pass_complete','logical_tasks':len(tasks)})
    print(json.dumps({'utc_seconds':time.time(),'counts':result['counts'],'group_errors':errors,'scan_bytes':result['scan_bytes']}),flush=True)
    return result

def process_identity(pid):
    # PID alone can be reused; bind the kernel boot and process start tick.
    stat=Path('/proc')/str(pid)/'stat'
    fields=stat.read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(fields[19])}

def command(path,pin,op):return [sys.executable,'-B','-P',str(Path(__file__).resolve()),op,'--config',str(Path(path).resolve()),'--sha256',pin]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('op',choices=('once','watch','start'));ap.add_argument('--config',required=True);ap.add_argument('--sha256',required=True);a=ap.parse_args();c=verify(a.config,a.sha256);out=Path(c['output']);out.mkdir(parents=True,exist_ok=True)
    inherited=os.environ.pop('NGA_MONITOR_LOCK_FD',None) if a.op=='watch' else None
    lockfile=os.fdopen(int(inherited),'a') if inherited else (out/'service.lock').open('a')
    with lockfile as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.op=='once':once(c,out);return
        if a.op=='start':
            # Child inherits locked fd, eliminating duplicate start race.
            (out/'EXIT.json').unlink(missing_ok=True)
            cmd=command(a.config,a.sha256,'watch');env=dict(os.environ,NGA_MONITOR_LOCK_FD=str(lock.fileno()))
            put(out/'RELAUNCH.json',{'command':command(a.config,a.sha256,'start'),'automatic_restart':False})
            with (out/'service.log').open('ab') as log:proc=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(lock.fileno(),),env=env)
            put(out/'SERVICE.json',{**process_identity(proc.pid),'command':cmd,'config_sha256':a.sha256,'started_utc_seconds':time.time()});print(json.dumps({'pid':proc.pid}));return
        rc=1
        def stop(signum,frame): raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        try:
            while True:
                tick=time.monotonic();c=verify(a.config,a.sha256);once(c,out)
                time.sleep(max(0.0,600-(time.monotonic()-tick)))
        except KeyboardInterrupt:rc=0
        finally:put(out/'EXIT.json',{'exit_code':rc,'scientific_acceptance':False,'utc_seconds':time.time()})

if __name__=='__main__':main()
