#!/usr/bin/env python3
"""Metadata-only member DEV publication and verification.

publish_member(c, comparison_path, source_review_path, dev_config_path) snapshots
one completed operand into c['host']['dev_evidence_dir']; Pending means retry.
validate_member(c, review) verifies the exact member review and local snapshot and
returns its authorized metadata pins. No report, store or model payload is read.
The caller supplies the genuine reviewed config and runs this before data access.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

class Pending(RuntimeError): pass
class Contradiction(ValueError): pass

def need(ok, msg):
    if not ok: raise Contradiction(msg)
def sha(b): return hashlib.sha256(b).hexdigest()
def digest(obj, ascii=False):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=ascii, allow_nan=False).encode())
def decode(data):
    def pairs(xs):
        out = {}
        for k, v in xs:
            need(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    try: return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(Contradiction('nonfinite JSON')))
    except (ValueError, UnicodeError) as e: raise Contradiction('invalid JSON') from e

def read(path):
    try:
        p=Path(path)
        with p.open('rb') as f:
            before=os.fstat(f.fileno()); data=f.read(); after=os.fstat(f.fileno())
        now=p.stat()
        key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if key(before)!=key(after) or key(after)!=key(now): raise Pending('metadata changed: '+str(p))
        return data
    except (FileNotFoundError, PermissionError) as e: raise Pending('missing metadata: '+str(path)) from e

def row_and_root(c):
    member=c['member']; need(isinstance(member,str) and re.fullmatch(r'q(?:0p8b|2b|4b|9b)-(?:base|s2|s3)',member), 'member role')
    rows=[r for r in c['roster'] if r['id']==member]; need(len(rows)==1,'roster member')
    row=rows[0]; base=member.endswith('-base')
    need(row['status']=='available' and row['arm']==('K0' if base else 'K1'), 'roster arm')
    need(row['size']==member.split('-')[0] and (row['adapter'] is None)==base,'roster size/adapter')
    need(row['seed'] is None if base else type(row['seed']) is int and row['seed']==int(member[-1]) and row['terminal_step']==3116,'roster seed/step')
    root=Path(c['round_dir']).parent/'dev'/member
    need(root.is_absolute() and str(root.resolve())==c['host']['dev_evidence_dir'], 'reserved directory')
    return row,root,base

def campaign(c): return digest({k:c[k] for k in ('schema','protocol','manifest','source_files','image','roster','round_dir')}, True)
def role_for(member):
    return {'q0p8b-base':'08b-k0','q2b-base':'2b-k0','q4b-base':'4b-k0','q9b-base':'9b-k0'}.get(member,member)
def counts(base):
    d={'decision-v7/calibration/clean':1148}
    for suite,n,v in [('decision-v7',1264,204),('transfer-v4',656,108)]:
        d[suite+'/dev/clean']=n
        if not base: d.update({suite+'/dev/variants':v,suite+'/dev/question_only':n,suite+'/dev/empty_input':n})
    return d

# Fixed deployment accepted by the existing source review; never derive these from requests.
DEPLOY = Path('/mnt/cephfs/xingchao/experiments/jev/engineering-base-rc1/functional-20261106/matched-current-dev-consumer-source')
CONFIG_ORIGIN = DEPLOY/'config.json'
REVIEW_ORIGIN = DEPLOY/'REVIEW.json'

def source_names(config):
    return ['consumer.py','watcher.py','legacy_consumer.py','config.json','producer-config.json'] + ['numeric_sources/'+n+'.py' for n in config['numeric_sources']]

def source_check(review,config,config_bytes):
    need(review.get('verdict')=='PASS_FOR_MATCHED_CURRENT_DEV_CONSUMPTION','source review verdict')
    pins=review['files_sha256']
    need(pins.get('consumer.py')=='671b2c3cbe42d9f3b29b83baabade49732bcb4ba24a95c877c7086fea1ca04d0' and pins.get('watcher.py')=='fdbf3aa9a5218bb8c8a7e6898577a79ce582e58be3fcc0efbb9a356dedd6f75b','source acceptance pins')
    need(pins.get('config.json')==sha(config_bytes),'source config not reviewed')
    need(config.get('schema')=='matched-current-dev-consumer-config-v1' and config.get('mode')=='production','DEV config mode')
    need(config['new_contract']['expected_populations']=={'decision-v7/dev':1264,'transfer-v4/dev':656,'decision-v7/calibration':1148},'population config')

def global_check(comparison):
    need(comparison.get('schema')=='matched-current-dev-comparison-v1' and comparison.get('synthetic_fixture') is False,'comparison schema/fixture')
    need(comparison.get('status') in ('INCOMPLETE_PENDING','MATCHED_CURRENT_DESCRIPTIVE_DEV'),'comparison global status')
    need(comparison.get('queue_failures')==[] and all(x.get('status')!='REFUSED_CONTRADICTION' for x in comparison['operands']),'global contradiction')

def roster_review_check(row, accepted, local=False):
    pin=row['evidence']['dev_consumer_review']; path=Path(pin['path'])
    need(path.is_absolute() and str(path.resolve())==pin['path'], 'roster source review path')
    need(pin['sha256']==sha(accepted), 'roster source review pin')
    # The original is already checked as the source snapshot on local replay.
    if not local or path != REVIEW_ORIGIN:
        need(read(path)==accepted, 'roster source review bytes')
    return str(path),pin['sha256']

def selected(c,row,base,config,comparison):
    global_check(comparison)
    role=role_for(c['member']); matches=[o for o in comparison['operands'] if o.get('role')==role]
    need(len(matches)==1,'operand role'); o=matches[0]
    if o.get('status')=='PENDING_MISSING_INPUT': raise Pending('selected operand pending')
    need(o.get('status')=='VALIDATED_OPERAND','operand status')
    refs=[m for m in config['models'] if m['id']==(role if base else o['baseline_id'])]; need(len(refs)==1,'baseline id'); ref=refs[0]
    size={'q0p8b':'0.8B','q2b':'2B','q4b':'4B','q9b':'9B'}[row['size']]
    need(ref['size']==size==o['size'] and ref['model']['path']==row['model'] and o['seed']==row['seed'],'operand model size seed')
    if base:
        need(o['baseline_id']==role and row['identity_sha256']==ref['model']['sha256'],'base identity')
        directory=Path(config['k0_root'])/role
    else:
        lanes=[x for x in config['lanes'] if x['lane']==role]; need(len(lanes)==1,'lane config'); lane=lanes[0]
        need(lane['seed']==row['seed'] and lane['size']==size and lane['baseline_id']==ref['id'] and lane['new_adapter']==row['adapter'],'lane identity')
        directory=Path(config['adapter_root'])/('full-'+role)
    need(o['runtime']['status']=='ALIGNED_INSTRUMENT' and o['runtime']['image']==config['image']==c['image'],'runtime image')
    expected=counts(base); need(o['groups']==list(expected) and set(o['evidence']['stores'])==set(expected),'group scope')
    for group,n in expected.items():
        e=o['evidence']['stores'][group]; need(type(e['rows']) is int and e['rows']==n,'group count '+group)
        need(all(re.fullmatch('[0-9a-f]{64}',e[k]) for k in ('store_sha256','receipt_sha256')),'store pins')
        need(o['metrics'][group]['n']==n,'metric count')
    need(o['operator_fit']['n']==1148,'calibration count')
    need(o['evidence']['report']==str(directory/'result'/('clean-report.json' if base else 'report.json')),'report path')
    need(bool(re.fullmatch('[0-9a-f]{64}',o['evidence']['report_sha256'])),'report pin')
    return o,ref,directory

def deployment_paths(config):
    return {'deployment_'+str(i): DEPLOY/name for i,name in enumerate(source_names(config)) if name != 'config.json'}

def deployment_check(config, review, raw):
    for i,name in enumerate(source_names(config)):
        key = 'dev_config' if name == 'config.json' else 'deployment_'+str(i)
        need(sha(raw[key]) == review['files_sha256'][name], 'deployment source pin '+name)

def exists(path):
    try: return Path(path).exists()
    except PermissionError as e: raise Pending('inaccessible metadata: '+str(path)) from e

def semantics(c,row,base,config,comparison,docs):
    o,ref,directory=selected(c,row,base,config,comparison); ev=o['evidence']; role=role_for(c['member']); run=directory/'result'
    ready=docs['inference']; ident=docs['identity']; need(ident['model_sha256']==row['identity_sha256'],'RUN_IDENTITY mismatch')
    need(sha(docs['_bytes']['inference'])==ev['inference_receipt_sha256'],'inference digest')
    need(ready['version']==1 and ready['groups']==o['groups'] and ready['stores']==ev['stores'],'inference scope/stores')
    h=ready['inference_header']; need(h['arm']==('K0' if base else 'K1') and h['stages']=='k_score' and h['device']=='npu' and h['checkpoint_revision']==ref['model']['base_revision'],'inference header')
    need(h['scorer']['model_path']==row['model'] and h['scorer']['adapter']==row['adapter'],'inference scorer identity')
    if base:
        need(ready['model_id']==role and ready['out']==str(run) and ready['config_sha256']==config['producer_config_sha256'] and ready['identity']=={**ref['model'],'files':ref['weight_shard_pins']},'base inference identity')
    else:
        p=docs['publication']; b=docs['binding']; owner=docs['owner']; ident0=owner['identity']; pub=o['publication']
        need(pub['publication']==str(Path(row['adapter'])/'PUBLICATION.json') and pub['publication_sha256']==sha(docs['_bytes']['publication']),'publication digest/path')
        need(p['binding']==b==pub['binding'] and owner['owner']==b['owner']=='rc1-functional-'+role and digest(ident0,True)==b['identity_sha256'],'publication binding')
        need(ident0['seed']==row['seed']==pub['seed'] and ident0['model_id']=='Qwen3.5-'+ref['size']+'-Base' and ident0['model_revision']==ref['model']['base_revision'] and pub['terminal_step']==3116,'publication identity/step')
        need(docs['complete']=={'exit_code':0,'steps':3116,'scientific_acceptance':False},'training completion')
        need(set(p['files'])=={'adapter_config.json','adapter_model.safetensors'} and sha(docs['_bytes']['adapter_config'])==p['files']['adapter_config.json'],'publication files')
        ac=docs['adapter_config']; need(ac['base_model_name_or_path']==ident0['model_id'] and ac['revision']==ident0['model_revision'],'adapter config')
        files={**p['files'],'PUBLICATION.json':sha(docs['_bytes']['publication']),'BINDING.json':sha(docs['_bytes']['binding'])}
        need(digest({'kind':'lora-adapter-unmerged','adapter_files':files,'base_revision':ref['model']['base_revision'],'base_path':ref['model']['base_path']})==row['identity_sha256'],'adapter identity')
        need(ready['model']==row['model'] and ready['adapter']==row['adapter'] and ready['out']=='/run/output/result' and ready['limit']==0,'adapter inference identity')
    for phase in ('infer','score'):
        launch=docs[phase+'_LAUNCH']; cmd=docs[phase+'_COMMAND']; ex=docs[phase+'_EXIT']
        for kind in ('LAUNCH','COMMAND','EXIT'):
            need(sha(docs['_bytes'][phase+'_'+kind])==ev['phase_receipts_sha256'][phase][kind],'phase receipt digest')
        need(all(type(ex.get(k)) is int and ex[k]==0 for k in ('exit_code','container_exit_code')),'phase failure')
        need(re.fullmatch('[0-9a-f]{64}',launch['container_id']) and launch['container_id']==ex['container_id'] and launch['command_sha256']==sha(docs['_bytes'][phase+'_COMMAND']),'phase binding')
        need(isinstance(cmd,list) and all(isinstance(x,str) for x in cmd) and '--smoke' not in cmd and '--rm' not in cmd,'phase command')
        def flag(k):
            need(cmd.count(k)==1 and cmd.index(k)+1<len(cmd),'command flag '+k); return cmd[cmd.index(k)+1]
        name=('nga-rc1-matched-k0-' if base else 'nga-rc1-cpu-full-')+role+'-'+phase
        need(flag('--name')==name and flag('--phase')==phase and flag('--entrypoint')=='/bin/bash' and cmd.count(config['image'])==1,'command role/image')
        need(flag('--model-id')==role if base else flag('--model')==row['model'] and flag('--adapter')==row['adapter'],'command model')
        need(flag('--out')==(str(run) if base else '/run/output/result'),'command output')
        setup='source /usr/local/Ascend/ascend-toolkit/set_env.sh; source /usr/local/Ascend/cann-9.2.0/share/info/ascendnpu-ir/bin/set_env.sh; source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi=1; export PYTHONPATH=/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe; exec python3 -B -P '
        tail=['-c',setup+('/run/packet/producer.py' if base else '/run/phase_wrapper.py')+' "$@"','--'] + (['--phase',phase,'--model-id',role,'--out',str(run)] if base else ['--model',row['model'],'--adapter',row['adapter'],'--out','/run/output/result','--phase',phase])
        need(cmd[cmd.index(config['image'])+1:]==tail,'phase executable binding')
        if base:
            artifacts={'inference_sha256':ev['inference_receipt_sha256'],'stores':ev['stores']}
            if phase=='score': artifacts['report_sha256']=ev['report_sha256']
            need(ex['artifact_evidence']==artifacts,'terminal artifact binding')
        else:
            binding=docs[phase+'_BINDING']; need(binding['binding']==docs['binding'] and binding['publication_sha256']==pub['publication_sha256'],'phase publication')
    for i,rec in enumerate(comparison.get('recovery_dispositions',[])):
        if rec.get('lane')!=role: continue
        need(rec.get('status')=='RECOVERED_VALIDATED','unresolved own recovery')
        d=docs['recovery_'+str(i)]; error=docs['recovery_error_'+str(i)]
        root=Path(config['adapter_root']); lane=next(x for x in config['lanes'] if x['lane']==role)
        expected="[Errno 13] Permission denied: '"+str(Path(lane['new_adapter'])/'PUBLICATION.json')+"'"
        trace=error.get('traceback','')
        need(rec['path']==str(root/(role+'-ERROR.json')) and rec['disposition']==str(root.parent/'dev-publication-recovery'/(role+'-disposition.json')), 'recovery origins')
        need(error.get('error')==expected and 'binding=ready(j)' in trace and "pub=json.loads((adapter/'PUBLICATION.json').read_text())" in trace and 'PermissionError: '+expected in trace,'recovery original failure')
        need(d['schema']=='rc1-dev-publication-recovery-v1' and d['lane']==role and d['state']=='complete' and d['error_path']==rec['path'] and d['error_sha256']==sha(docs['_bytes']['recovery_error_'+str(i)]) and d['original_error']==expected,'recovery disposition')
        approved=docs['recovery_approved']; queue=docs['recovery_config']
        for field,key in (('queue_sha256','recovery_queue'),('wrapper_sha256','recovery_wrapper'),('config_sha256','recovery_config')):
            need(d.get(field)==approved.get(field)==sha(docs['_bytes'][key]),'recovery recipe '+field)
        need(d['wrapper_sha256']==config['adapter_wrapper_sha256'],'recovery wrapper consumer pin')
        jobs=[j for j in queue['jobs'] if j['id']==role]
        need(len(jobs)==1 and jobs[0]['model']==ref['model']['path'] and jobs[0]['seed']==lane['seed'] and jobs[0]['size']==lane['size'],'recovery job')
        need(d.get('phase_directory_full')==str(directory) and d.get('phase_directory_smoke')==str(root/('smoke-'+role)),'recovery directories')
        for phase in ('infer','score'):
            for kind in ('LAUNCH','COMMAND','BINDING','EXIT'):
                need(d['phase_receipts'].get(str(directory/(phase+'-'+kind+'.json')))==sha(docs['_bytes'][phase+'_'+kind]),'recovery receipt')

def source_paths(c,row,base,config,comparison):
    o,ref,directory=selected(c,row,base,config,comparison); run=directory/'result'
    paths={'inference':run/'INFERENCE-READY.json','identity':run/'RUN_IDENTITY.json'}
    for phase in ('infer','score'):
        for kind in (('LAUNCH','COMMAND','EXIT') if base else ('LAUNCH','COMMAND','EXIT','BINDING')): paths[phase+'_'+kind]=directory/(phase+'-'+kind+'.json')
    if not base:
        a=Path(row['adapter']); paths.update(publication=a/'PUBLICATION.json',binding=a/'BINDING.json',adapter_config=a/'adapter_config.json',owner=a.parent/'OWNER.json',complete=a.parents[1]/'COMPLETE.json')
    for i,r in enumerate(comparison.get('recovery_dispositions',[])):
        if r.get('lane')==role_for(c['member']): paths.update({f'recovery_{i}':Path(r['disposition']),f'recovery_error_{i}':Path(r['path'])})
    if any(r.get('lane')==role_for(c['member']) for r in comparison.get('recovery_dispositions',[])):
        root=Path(config['adapter_root']); package=root.parent/'cpu-separated'
        paths.update(recovery_approved=root/'REVIEW-APPROVED.json', recovery_queue=package/'queue_proposal.py', recovery_wrapper=package/'phase_wrapper.py', recovery_config=package/'config.json')
    return paths

def publish_member(c, comparison_path, source_review_path, dev_config_path):
    row,root,base=row_and_root(c); root.mkdir(parents=True,exist_ok=True)
    with (root/'.publish.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        source={'comparison':Path(comparison_path),'source_review':Path(source_review_path),'dev_config':Path(dev_config_path)}
        need(source['dev_config']==CONFIG_ORIGIN and source['source_review']==REVIEW_ORIGIN,'deployment origin')
        # Read every available terminal before treating missing siblings as pending.
        raw={k:read(p) for k,p in source.items()}; config=decode(raw['dev_config']); comparison=decode(raw['comparison']); source_check(decode(raw['source_review']),config,raw['dev_config'])
        need(config['review']==str(REVIEW_ORIGIN) and source['comparison']==Path(config['output'])/'comparison.json','comparison/review origin')
        roster_review_check(row,raw['source_review'])
        deployment=deployment_paths(config)
        for k,p in deployment.items(): raw[k]=read(p)
        source.update(deployment); deployment_check(config,decode(raw['source_review']),raw)
        role=role_for(c['member']); early_dir=(Path(config['k0_root'])/role if base else Path(config['adapter_root'])/('full-'+role))
        for phase in ('infer','score'):
            try: terminal=decode(read(early_dir/(phase+'-EXIT.json')))
            except Pending: continue
            need(all(type(terminal.get(t)) is int and terminal[t]==0 for t in ('exit_code','container_exit_code')),'phase failure')
        global_check(comparison)
        role=role_for(c['member'])
        for rec in comparison.get('recovery_dispositions',[]):
            if rec.get('lane')==role:
                root0=Path(config['adapter_root'])
                need(rec.get('path')==str(root0/(role+'-ERROR.json')) and rec.get('disposition')==str(root0.parent/'dev-publication-recovery'/(role+'-disposition.json')), 'recovery origins')
                if rec.get('status')=='PENDING_RETRY': raise Pending('recovery pending retry')
        paths=source_paths(c,row,base,config,comparison)
        if any(r.get('lane')==role for r in comparison.get('recovery_dispositions',[])):
            need(not exists(Path(config['adapter_root']).parent/'dev-publication-recovery'/(role+'-ERROR.json')), 'recovery attempt failed')
        missing=[]
        for k,p in paths.items():
            try: raw[k]=read(p)
            except Pending as e: missing.append(str(e)); continue
            if k.endswith('_EXIT'):
                x=decode(raw[k]); need(all(type(x.get(t)) is int and x[t]==0 for t in ('exit_code','container_exit_code')),'phase failure')
        if missing: raise Pending('; '.join(missing))
        source.update(paths); docs={k:decode(raw[k]) for k in paths if k not in ('recovery_queue','recovery_wrapper')}; docs['_bytes']=raw
        semantics(c,row,base,config,comparison,docs)
        for k,p in source.items():
            if read(p)!=raw[k]: raise Pending('snapshot raced: '+str(p))
        roster_review_check(row,raw['source_review'])
        if any(r.get('lane')==role for r in comparison.get('recovery_dispositions',[])):
            need(not exists(Path(config['adapter_root']).parent/'dev-publication-recovery'/(role+'-ERROR.json')), 'recovery attempt failed')
        refs={k:{'path':str(root/(k+'.json')),'sha256':sha(v),'original_path':str(source[k])} for k,v in raw.items()}
        bundle={'schema':'rc1-member-dev-binding-v1','member':c['member'],**{k:row[k] for k in ('identity_sha256','model','adapter','seed','terminal_step')},'campaign_sha256':campaign(c),'evidence_status':'ACTUAL_DEV_COMPLETE','operand_role':role_for(c['member']),'source_review':refs.pop('source_review'),'dev_config':refs.pop('dev_config'),'comparison':refs.pop('comparison'),'artifact_pins':refs}
        data=(json.dumps(bundle,sort_keys=True,indent=2)+'\n').encode(); bp=root/'bundle.json'
        if bp.exists():
            need(read(bp)==data,'accepted bundle changed'); _local(c,bundle); return {'path':str(bp),'sha256':sha(data)}
        for k,b in raw.items():
            p=root/(k+'.json')
            with tempfile.NamedTemporaryFile(dir=root,delete=False) as f: f.write(b); f.flush(); os.fsync(f.fileno()); tmp=f.name
            os.replace(tmp,p)
        with tempfile.NamedTemporaryFile(dir=root,delete=False) as f: f.write(data); f.flush(); os.fsync(f.fileno()); tmp=f.name
        os.replace(tmp,bp)
        return {'path':str(bp),'sha256':sha(data)}

def _local(c,bundle):
    row,root,base=row_and_root(c)
    need(bundle['schema']=='rc1-member-dev-binding-v1' and bundle['evidence_status']=='ACTUAL_DEV_COMPLETE' and bundle['member']==c['member'] and bundle['operand_role']==role_for(c['member']) and bundle['campaign_sha256']==campaign(c),'bundle scope')
    need(all(bundle[k]==row[k] for k in ('identity_sha256','model','adapter','seed','terminal_step')),'bundle identity')
    refs={k:bundle[k] for k in ('source_review','dev_config','comparison')}; refs.update(bundle['artifact_pins']); raw={}; result={}
    for k,ref in refs.items():
        p=Path(ref['path']); need(p==root/(k+'.json') and p.resolve()==p and p.is_file(),'snapshot path escape')
        b=read(p); need(sha(b)==ref['sha256'],'snapshot mutation'); raw[k]=b; result[str(p)]=ref['sha256']
    config=decode(raw['dev_config']); comparison=decode(raw['comparison']); source_check(decode(raw['source_review']),config,raw['dev_config'])
    need(refs['dev_config']['original_path']==str(CONFIG_ORIGIN) and refs['source_review']['original_path']==str(REVIEW_ORIGIN) and config['review']==str(REVIEW_ORIGIN) and refs['comparison']['original_path']==str(Path(config['output'])/'comparison.json'),'source origins')
    path,pin=roster_review_check(row,raw['source_review'],local=True); result[path]=pin
    deployment=deployment_paths(config); deployment_check(config,decode(raw['source_review']),raw)
    need(all(refs[k]['original_path']==str(p) for k,p in deployment.items()),'deployment provenance')
    paths=source_paths(c,row,base,config,comparison); need(set(paths)|set(deployment)==set(bundle['artifact_pins']),'snapshot inventory')
    need(all(refs[k]['original_path']==str(p) for k,p in paths.items()),'source provenance')
    docs={k:decode(raw[k]) for k in paths if k not in ('recovery_queue','recovery_wrapper')}; docs['_bytes']=raw; semantics(c,row,base,config,comparison,docs)
    return result

def validate_member(c, review):
    row,root,base=row_and_root(c); bp=root/'bundle.json'; own=review['own_dev']
    need(review.get('schema')=='rc1-trackk-review-v1' and review.get('reviewed') is True and review.get('config_sha256')==digest({k:v for k,v in c.items() if k!='review'},True),'config review')
    review_bytes=read(c['review']['path']); need(sha(review_bytes)==c['review']['sha256'] and decode(review_bytes)==review,'exact review pin')
    need(set(own)=={'path','sha256'} and own['path']==str(bp),'review bundle path')
    raw=read(bp); need(sha(raw)==own['sha256'],'review bundle digest')
    result=_local(c,decode(raw)); result[str(bp)]=own['sha256']; return result
