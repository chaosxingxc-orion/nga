#!/usr/bin/env python3
"""Read-only RC1 same-TEST reconstruction. Never issues tickets or writes producer evidence."""
import argparse
import ast
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
from fractions import Fraction
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
PRODUCER_SHA = 'a24c27e80f6d5023a490f41ae51d0ea08c3f54b10cae183f0a7a7bd3302d88f6'
WRAPPER_SHA = '10534f805f2c2f9b259a27f7f23c3c03fb7b0fc6845eae525a47ed06ca6f8433'
SIZES = ('q0p8b', 'q2b', 'q4b', 'q9b')
SUITES = {'decision-v7':1200, 'transfer-v4':656}
ROLES = [f'{s}-s{n}' for s in SIZES for n in (2,3)] + [f'{s}-base' for s in SIZES]
PLAN = [('decision-v7','calibration'),('decision-v7','test'),('transfer-v4','test')]
GROUPS = [f'{s}/{p}/{k}' for s,p in PLAN for k in (('clean',) if p == 'calibration' else ('clean','variants','question_only','empty_input'))]
DATA = {'decision-v7/train/clean':(15576,'5ddc8e94f3e0af1c8abdb887ed77c1e8813879efcc428edc6d4ea0bed537daf6'),
        'decision-v7/calibration/clean':(1148,'c3eeeda72740fbde6fbcc28e1dff0928c98407242543d0bd8f0819497f502b69'),
        'decision-v7/test/clean':(1200,'55e21d63b93550ff2e1c98b32c2be558af02bde31c0633f8448d8f38d23fe1b2'),
        'decision-v7/test/variants':(240,'72a095a26d9ac0052bd7825b745475b551d343a78409202576570dbdd2f63d6e'),
        'transfer-v4/test/clean':(656,'43de4b7d6efb2d4b6b78b670ba82b98fefa324076fdda1b0462f5902ac02f7fc'),
        'transfer-v4/test/variants':(108,'228b9cfe82ded8495eac7aa1490b062b2ffedf4e0e737f4dacbec6b38aef5e8c')}

def require(ok, reason):
    if not ok: raise ValueError(reason)

def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def sha(path):
    with open(path,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'duplicate JSON key: '+k);out[k]=v
        return out
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def save(path, x):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as f:
        json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def pin(p):
    require(isinstance(p,dict) and set(p)=={'path','sha256'}, 'invalid file pin')
    require(Path(p['path']).is_absolute() and len(p['sha256'])==64 and all(c in '0123456789abcdef' for c in p['sha256']), 'invalid absolute pin')
    require(sha(p['path'])==p['sha256'],'changed bytes: '+p['path'])
    return p['path']

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def instrument(packet):
    # Execute only named frozen arithmetic modules, after checking their closure.
    sources=packet['source_files']
    require(isinstance(sources,dict) and sources, 'source closure absent')
    for path,h in sources.items(): pin({'path':path,'sha256':h})
    pin(packet['producer']);require(packet['producer']['sha256']==PRODUCER_SHA,'wrong producer revision')
    pin(packet['bootstrap_wrapper']);require(packet['bootstrap_wrapper']['sha256']==WRAPPER_SHA,'wrong bootstrap wrapper')
    require(sources.get(packet['producer']['path'])==PRODUCER_SHA,'producer outside source closure')
    dirs=packet['module_dirs']
    required={'core_r3','variants_r3','degenerate_r3','admissible_store_r3','selection_evidence_r3','provenance_r3',
              'thresholds','split','metrics','decision','common','prompt','scorer','r3_reference_metrics','r3_final_container'}
    for name in required:
        candidates=[str((Path(d)/(name+'.py')).resolve()) for d in dirs if (Path(d)/(name+'.py')).is_file()]
        require(len(candidates)==1 and candidates[0] in sources,'missing/ambiguous arithmetic source: '+name)
    # Do not import full evaluator, producer, model loader or historical outcome loaders.
    sys.path[:0]=dirs
    import core_r3 as C, variants_r3 as V, degenerate_r3 as D
    import admissible_store_r3 as AS, selection_evidence_r3 as SE, provenance_r3 as PV
    import r3_reference_metrics as RM
    for name in required:
        if name in sys.modules:
            p=str(Path(sys.modules[name].__file__).resolve())
            require(p in sources,'unbound imported module: '+name)
    return C,V,D,AS,SE,PV,RM

def bootstrap(packet):
    # original_bootstrap authenticates historical source and AST-extracts only
    # four constants + paired_bootstrap. Wrapper is independently pinned above.
    m=load_module('rc1_original_bootstrap',packet['bootstrap_wrapper']['path'])
    return m.original_bootstrap()

def no_fixture(x):
    if isinstance(x,dict):
        require(not x.get('fixture_only',False),'fixture evidence in production')
        for v in x.values(): no_fixture(v)
    elif isinstance(x,list):
        for v in x:no_fixture(v)
    elif isinstance(x,str): require('fixture' not in x.lower() and 'synthetic' not in x.lower(),'generated identity in production')

def authenticate(packet, config, packet_pin):
    require(packet.get('schema')=='rc1-same-test-packet-v1','packet schema')
    require(packet.get('kind') in ('generated','production'),'packet kind')
    require(config.get('schema')=='rc1-same-test-consumer-v1','consumer config schema')
    require(type(config['workers']) is int and 1<=config['workers']<=8,'workers must be bounded 1..8')
    require(config['packet']==packet_pin,'packet/config binding')
    require(packet['kind']=='generated' or config.get('allow_production') is True,'production disabled')
    if packet['kind']=='generated':
        require(config.get('allow_generated') is True,'generated packet disabled')
        require(packet.get('fixture_only') is True,'generated marker absent')
    else:
        # This is an out-of-band trust anchor supplied by the release owner, NOT
        # self-authentication by hashes in an untrusted packet. No review is made here.
        review=read(pin(config['completed_access_review']))
        require(review.get('schema')=='rc1-numerical-completed-access-review-v1' and review.get('accepted') is True,'completed-access review absent')
        require(review.get('packet_sha256')==packet_pin['sha256'] and review.get('new_test_access') is False and review.get('scope')=='reconstruct-authorized-saved-vectors-only','completed-access scope differs')
        require(review.get('source_acceptance')==config['source_acceptance'],'source acceptance binding')
        acceptance=read(pin(config['source_acceptance']))
        require(acceptance.get('entry_sha256')==PRODUCER_SHA and acceptance.get('reviewed') is True and acceptance.get('production_ready') is True,'producer source not accepted')
        require(review.get('authorized_files')==packet['authorized_files'],'authorized saved evidence scope differs')
        require(review.get('model_bindings')=={r['id']:{'identity_sha256':r['identity_sha256'],'model':r['model'],'adapter':r['adapter'],'evidence':r['evidence']} for r in packet['roster'] if r['status']=='available'},'reviewed model/publication/runtime bindings differ')
        accepted_sources=dict(acceptance['source_files'])
        # The source-only acceptance explicitly names equivalent local/host entry
        # locations. No arbitrary file with a declared digest becomes trusted.
        local_entry=acceptance['entry_path'];host_entry=acceptance.get('host_entry_path')
        if packet['producer']['path']==local_entry and host_entry in accepted_sources:
            accepted_sources[local_entry]=accepted_sources.pop(host_entry)
        require(packet['source_files']==accepted_sources,'source closure differs from accepted source')
        require(packet['protocol']['sha256']=='7c464d587f746b18237ee14c7ab46dea8e950f0ed7406552ff6b62cb29a85739','frozen protocol differs')
        require(packet['manifest']['sha256']=='c2e8cbc6e0c686be2cc730890928d803e3f4de1b9b745abbea90adb6f3903afd','frozen manifest differs')
        no_fixture(packet)
    require([r['id'] for r in packet['roster']]==ROLES,'fixed roster/order differs')
    require(set(packet['members'])<=set(ROLES),'foreign member')
    require(isinstance(packet['image'],str) and packet['image'].startswith('sha256:') and len(packet['image'])==71,'image digest')
    require(set(packet['populations'])==set(DATA),'population metadata inventory differs')
    require(set(packet['data_pins'])==set(DATA),'dataset identity inventory differs')
    for group,(n,h) in DATA.items():
        require(packet['data_pins'][group]['n']==n,'wrong population denominator')
        if packet['kind']=='production': require(packet['data_pins'][group]['sha256']==h,'wrong frozen dataset identity')
    for role in packet['roster']:
        name=role['id'];require(role['status'] in ('available','failed','unavailable'),'roster status')
        if role['status']!='available': require(bool(role.get('reason')),'missing failure reason')
        if role['status']=='available':
            base=name.endswith('-base');require(role['arm']==('K0' if base else 'K1'),'wrong arm')
            require(role['size']==name.split('-')[0] and role.get('seed')==(None if base else int(name[-1])),'wrong size/seed')
            require(role.get('terminal_step')==(None if base else 3116),'wrong terminal')
            require((role.get('adapter') is None)==base,'wrong adapter mode')
            keys={'base_inventory','tokenizer','runtime'} | (set() if base else {'publication','training_terminal','smoke_resume','dev_review'})
            require(set(role['evidence'])>=keys,'missing lineage pins')
            for p in role['evidence'].values(): pin(p)
    available=[r for r in packet['roster'] if r['status']=='available']
    require(len({r['identity_sha256'] for r in available})==len(available),'duplicate model/adapter identity')
    for size in SIZES:
        require(len({r['model'] for r in available if r['size']==size})<=1,'same-size model base paths differ')
    for path,h in packet['authorized_files'].items(): pin({'path':path,'sha256':h})
    # Every byte opened later must appear in the authorized attachment inventory.
    for p in all_pins(packet):
        require(packet['authorized_files'].get(p['path'])==p['sha256'],'file outside completed-access scope: '+p['path'])

def all_pins(x):
    if isinstance(x,dict):
        if set(x)=={'path','sha256'}: yield x
        else:
            for k,v in x.items():
                if k!='authorized_files':yield from all_pins(v)
    elif isinstance(x,list):
        for v in x:yield from all_pins(v)

def populations(packet,C):
    out={}
    for group,p in packet['populations'].items():
        rows=read(pin(p));n=DATA[group][0]
        require(isinstance(rows,list) and len(rows)==n,'metadata population count: '+group)
        keys=[C.kev_key(r) for r in rows]
        require(len(keys)==len(set(keys)),'duplicate ordered metadata keys')
        for r in rows:
            ids=C.level_ids(r)
            require(ids and len(ids)==len(set(ids)) and r['gold'] in ids,'invalid candidates/gold')
            require(r['level_type'] in ('boolean','nominal','ordinal'),'invalid level type')
        out[group]=rows
    for suite in SUITES:
        vs=out[f'{suite}/test/variants'];expected={'permuted':96,'none_present':72,'none_absent':72} if suite=='decision-v7' else dict.fromkeys(('permuted','none_present','none_absent'),36)
        require({k:sum(r['variant']==k for r in vs) for k in expected}==expected,'variant populations differ')
    return out

def identity_valid(role,identity):
    require(identity['base_revision']!='unknown','unknown model revision')
    base=role['arm']=='K0'
    require(identity['kind']==('checkpoint' if base else 'lora-adapter-unmerged'),'identity kind')
    require(identity['base_path']==str(Path(role['model']).resolve()),'base path')
    require(identity['path']==str(Path(role['model'] if base else role['adapter']).resolve()),'adapter/checkpoint path')
    files=identity['files'];require(isinstance(files,dict) and files,'empty model inventory')
    payload=({'kind':'checkpoint','weight_files':files,'revision':identity['base_revision']} if base else
             {'kind':'lora-adapter-unmerged','adapter_files':files,'base_revision':identity['base_revision'],'base_path':identity['base_path']})
    require(identity['sha256']==role['identity_sha256']==digest(payload),'model identity digest')

def base_identity_for(role, ident, inventory):
    if inventory.get('schema') == 'matched-current-dev-consumer-config-v1':
        matches = [entry for entry in inventory['models'] if entry['model']['path'] == role['model']]
        require(len(matches) == 1, 'base inventory model missing or ambiguous')
        identity = dict(matches[0]['model'], files=matches[0]['weight_shard_pins'])
    else:
        identity = inventory['identity']
    require(identity['kind']=='checkpoint' and identity['base_path']==ident['base_path'] and identity['base_revision']==ident['base_revision'], 'base inventory/revision differs')
    base_role = dict(role, arm='K0', adapter=None, identity_sha256=identity['sha256'])
    identity_valid(base_role, identity)
    return identity

def check_header(header,role,ident,desc,stage,C):
    require(header['model']=={k:ident[k] for k in ('path','sha256','kind','base_path','base_revision')},'report model identity differs')
    require(header['arm']==role['arm'] and header['checkpoint_revision']==ident['base_revision'],'header arm/revision differs')
    require(header['scorer']==desc and header['dtype']=='float32','report scorer differs')
    require(header['render']=='record_name' and header['primary_input_mode']=='full','wrong render/input mode')
    require(header['stages']==stage and header['limit']==0 and header['limit_groups']==0,'wrong phase/partial population')
    require(header['partitions']==['calibration','test'],'wrong report partitions')
    require(header['device']==('npu' if stage=='k_score' else 'cpu'),'wrong phase device')
    import prompt
    require(header['prompt_version']==prompt.PROMPT_VERSION and header['prompt_format']==prompt.PROMPT_FORMAT,'wrong frozen prompt')

def member(packet,role,pop,mods):
    C,V,D,AS,SE,PV,RM=mods;name=role['id'];ev=packet['members'][name]
    required={'config','identity','ready','infer_exit','report','fit','final','access','owner','run_identity','producer_manifest','host_release_verified'}
    if packet['kind']=='production':required|={'launch_receipt','release','claim','container_observation'}
    require(set(ev)==required,'completed evidence inventory differs')
    docs={k:read(pin(p)) for k,p in ev.items() if k!='access'}
    c=docs['config'];ident=docs['identity'];identity_valid(role,ident)
    require(c['schema']=='rc1-trackk-v1' and c['member']==name and c['roster']==packet['roster'],'config role/roster differs')
    for key in ('source_files','image','protocol','manifest'):
        require(c[key]==packet[key],'config scientific binding differs: '+key)
    pin(c['review']);require(packet['authorized_files'].get(c['review']['path'])==c['review']['sha256'],'review outside scope')
    rv=read(c['review']['path'])
    require(rv.get('schema')=='rc1-trackk-review-v1' and rv.get('reviewed') is True and rv.get('config_sha256')==digest({k:v for k,v in c.items() if k!='review'}),'actual config review binding')
    if packet['kind']=='production': no_fixture(rv)
    owner={'config_sha256':digest(c),'model_sha256':ident['sha256'],'out':c['out']}
    require(docs['owner']==owner and docs['ready']['owner']==owner and docs['report']['rc1_owner']==owner,'owner binding differs')
    out=Path(c['out'])
    expected_paths={'ready':out/'INFERENCE-READY.json','infer_exit':out/'INFER-EXIT.json','report':out/'K-REPORT.json','fit':out/'CPU/OPERATOR-FIT.json',
                    'run_identity':out/'RUN_IDENTITY.json','producer_manifest':out/'manifests/main.json','final':Path(c['round_dir'])/'FINAL.json','access':Path(c['round_dir'])/'TEST-READS.log',
                    'owner':Path(c['round_dir'])/('owner-'+ident['sha256']+'.json'),'host_release_verified':out/'HOST-RELEASE-VERIFIED.json'}
    for k,path in expected_paths.items():require(ev[k]['path']==str(path),'artifact path/phase differs: '+k)
    campaign=digest({k:c[k] for k in ('schema','protocol','manifest','source_files','image','roster','round_dir')})
    final=docs['final']
    require(final.get('campaign_sha256')==campaign and final.get('protocol_sha256')==packet['protocol']['sha256'],'FINAL campaign differs')
    require(final['roster_status']==[{'id':r['id'],'status':r['status'],'reason':r.get('reason')} for r in packet['roster']],'FINAL roster statuses differ')
    require(any(x['label']==name and x['sha256']==ident['sha256'] and x['path']==ident['path'] for x in final['models']),'FINAL model not named')
    ready=docs['ready'];report=docs['report'];desc=ready['descriptor']
    require(ready['schema']=='rc1-inference-ready-v1' and ready['groups']==GROUPS and set(ready['stores'])==set(GROUPS),'ready groups')
    require(not PV._scorer_problems(desc),'non-record scorer')
    if packet['kind']=='production':
        no_fixture(desc)
        require(desc.get('model_path')==role['model'] and desc.get('adapter')==role['adapter'],'scorer model/adapter differs')
        require(desc.get('scorer')=='scorer_r3.R3Scorer' and desc.get('render')=='record_name' and desc.get('dedup') is True,'scorer implementation/render/dedup differs')
    require(docs['infer_exit']=={'schema':'rc1-infer-exit-v1','config_sha256':digest(c),'exit_code':0,'ready_sha256':ev['ready']['sha256']},'failed/mismatched infer phase')
    require(report['inference_ready_sha256']==ev['ready']['sha256'] and report['operator_fit_artifact']==ev['fit'],'report handoff/fit pin differs')
    host=docs['host_release_verified']
    require(host['ready_sha256']==ev['ready']['sha256'] and isinstance(host['container_id'],str) and host['container_id'],'missing completed host release')
    if packet['kind']=='production':
        container=c['container'];spec=container['spec']
        require(spec['image']==packet['image'],'actual container image differs')
        require(spec['cmd']==['-B','-P',packet['producer']['path'],'infer','--config',ev['config']['path']],'actual container command differs')
        for key,field in (('launch_receipt','launch_receipt'),('release','release'),('claim','claim')):
            require(ev[key]['path']==container[field],'container evidence path differs: '+key)
        observed=docs['container_observation'];launch=docs['launch_receipt'];release=docs['release'];claim=docs['claim']
        # Frozen pure validator, not Docker/API access or a new observation claim.
        import r3_final_container as K
        K.verify_observation(spec,observed,launch['id'])
        state=observed['State']
        require(state['Status']=='exited' and type(state['ExitCode']) is int and state['ExitCode']==0 and not state.get('OOMKilled',False),'actual inference container failed')
        require(host=={'container_id':observed['Id'],'ready_sha256':ev['ready']['sha256'],'release_sha256':ev['release']['sha256']},'host release verification differs')
        require(release['schema']=='r3-resource-release-v1' and release['container_id']==observed['Id'] and release['container']==spec['name'] and release['exit_code']==0,'actual release differs')
        require(release['container_started_at']==state['StartedAt'] and release['container_finished_at']==state['FinishedAt'],'release/container phase times differ')
        require(release['claim_sha256']==ev['claim']['sha256'] and claim['run']==release['run']==container['run'] and claim['chip']==release['chip']==container['chip'],'actual claim/release identity differs')
        before=release['allocation_before'];after=release['allocation_after'];chip=container['chip'];run_name=container['run']
        for value,key in ((before,'allocation_before_sha256'),(after,'allocation_after_sha256')):
            require(hashlib.sha256((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()==release[key],'allocation transition digest')
        require(any(x.get('chip')==chip and x.get('run')==run_name for x in before['allocation']) and not any(x.get('chip')==chip for x in after['allocation']) and any(x.get('chip')==chip and x.get('previous_run')==run_name for x in after['free']),'actual allocation transition differs')
    check_header(ready['header'],role,ident,desc,'k_score',C)
    check_header(report['header'],role,ident,desc,'k',C)
    require(docs['run_identity']=={'model_sha256':ident['sha256'],'model_path':ident['path'],'prompt_version':report['header']['prompt_version'],'track_t_config':report['header']['track_t_config'],'arm':role['arm']},'run identity differs')
    # Strict completion parsing; legacy read_log silently ignores malformed lines.
    lines=Path(pin(ev['access'])).read_text().splitlines();records=[]
    for line in lines:
        fields=line.split('\t');require(len(fields)==7,'malformed access record')
        if fields[2]==ident['sha256']:
            require(fields[1]==ident['path'] and fields[4]=='test' and fields[3] in SUITES,'wrong completed access identity/scope')
            records.append((fields,line))
    require(len(records)==2 and {r[0][3] for r in records}==set(SUITES),'missing/duplicate completed access')
    require(report['test_reads']==[next(line for fields,line in records if fields[3]==s) for s in SUITES],'report completed-access mismatch')
    stored={}
    # All populations/identity/scores are checked before accepting any metric.
    for group in GROUPS:
        s,p,k=group.split('/');path=C.k_readout_path(c['out'],s,p,k);e=ready['stores'][group]
        require(packet['authorized_files'].get(path)==e['store_sha256'] and packet['authorized_files'].get(AS.receipt_path(path))==e['receipt_sha256'],'store outside authorized scope')
        require(sha(path)==e['store_sha256'] and sha(AS.receipt_path(path))==e['receipt_sha256'],'changed store/receipt bytes')
        raw=AS.check_receipt(path,ident['sha256'],desc,recover=False)
        rows=pop[f'{s}/{p}/'+('variants' if k=='variants' else 'clean')]
        require([r['k'] for r in raw]==[C.kev_key(r) for r in rows],'readout order differs')
        stored[group]=SE.validate_population(raw,rows,C.kev_key)
        require(len(raw)==e['rows'],'ready row count differs')
        for r,src in zip(raw,rows):
            require(all(r[key]==src[key] for key in ('source','qname','level_type')),'readout metadata differs')
    expected_stores={C.k_readout_path(c['out'],*g.split('/')) for g in GROUPS}
    actual_stores={str(p) for p in (out/'trackk').rglob('*.jsonl')}
    require(actual_stores==expected_stores,'unexpected/missing readout file scope')
    require({str(p) for p in (out/'manifests').glob('*.json')}=={ev['producer_manifest']['path']},'unexpected producer manifest scope')
    PV.verify(c['out'],[str(d) for d in (out/'trackk').iterdir() if d.is_dir()],ident['sha256'],role_of=SE.role_for_path)
    cal='decision-v7/calibration/clean';fitted=V.fit_operator(pop[cal],[r['s'] for r in stored[cal]])
    fit=docs['fit'];import thresholds as TH
    entries=[{'tier':t,'key':list(k),'tau':v[0],'n_fit':v[1]} for (t,k),v in fitted._table.items()]
    entries.sort(key=lambda e:canonical([e['tier'],e['key']]))
    expected_fit={'schema':'rc1-operator-fit-v1','partition':'decision-v7/calibration','population_n':1148,
                  'calibration_data_sha256':packet['data_pins'][cal]['sha256'],'calibration_store':ready['stores'][cal],
                  'descriptor':desc,'model_sha256':ident['sha256'],'splitter':fitted.splitter_name,'summary':fitted.summary(),
                  'default_tau':TH.DEFAULT_TAU,'min_fit_items':TH.MIN_FIT_ITEMS,'tau_grid':list(TH.TAU_GRID),'entries':entries}
    require(fit==expected_fit,'fitted tau table differs from calibration reconstruction')
    fit_const=D.fit_constant(pop['decision-v7/train/clean']);parts={};prob={};vectors={}
    for s,p in PLAN:
        group=f'{s}/{p}/clean';rows=pop[group];scores=[r['s'] for r in stored[group]]
        arms={};var=[] if p=='calibration' else pop[f'{s}/{p}/variants']
        if p=='test':
            cs,tiers=D.score_constant(fit_const,rows);arms['constant']={**C.headline(rows,cs),'tier_usage':tiers}
            arms['uniform']=C.headline(rows,D.score_uniform(rows))
            for kind in ('question_only','empty_input'):arms[kind]=C.headline(rows,[r['s'] for r in stored[f'{s}/{p}/{kind}']])
        part={'n':len(rows),'headline':C.headline(rows,scores),
              'near_tie_census':C.near_tie_census(scores,gold=[C.gold_index(r) for r in rows],keys=[C.kev_key(r) for r in rows],option_ids=[C.level_ids(r) for r in rows]),
              'duplicate_option_audit':C.duplicate_option_audit(rows),'gold_position_distribution':C.gold_position_distribution(rows),'arms':arms,
              'n_variants':{k:sum(v['variant']==k for v in var) for k in C.KEV_VARIANTS}}
        if p=='test':
            bykey={C.kev_key(r):v for r,v in zip(rows,scores)};bykey.update({r['k']:r['s'] for r in stored[f'{s}/{p}/variants']})
            op=lambda row,score:V.operator_decision(fitted,row,score)[0]
            part['secondary']={'permutation':V.permutation_metrics(V.build_permutation_pairs(rows,var),bykey,op,role['arm']),
                               'nota':V.nota_metrics(V.build_nota_units(rows,var),bykey),
                               'operator':V.operator_column(rows,scores,fitted,f'{s}/{p}')}
            part['secondary_note']='secondary metrics gate nothing in this round (sec 4.7)'
            vectors[s]={'keys':[C.kev_key(r) for r in rows],'ids':[C.level_ids(r) for r in rows],'gold':[r['gold'] for r in rows],
                        'raw':[int(C.argmax_first(v)==C.gold_index(r)) for r,v in zip(rows,scores)],
                        'r0':[int(C.argmax_first(v)==C.gold_index(r) and not C.is_tie(v)) for r,v in zip(rows,scores)]}
            line=next(fields for fields,line in records if fields[3]==s)
            require(line[5]==str(len(rows)) and line[6]=='%.6f'%part['headline']['kev_rule_accuracy'],'access metrics differ from reconstructed scores')
        parts[f'{s}/{p}']=part;prob[group]=RM.summarize(scores,[C.gold_index(r) for r in rows])
    require(report['track_k']['partitions']==parts,'persisted Track K metrics differ from reconstruction')
    require(report['probability_panels']==prob,'persisted binary64 probability panels differ from reconstruction')
    expected_op={'partition':'decision-v7/calibration','n':1148,'fitted':fitted.summary(),'note':"tau fitted per model on decision-v7 calibration (sec 4.4); not the Track T carve-out (sec 2.6, F1)"}
    require(report['track_k']['operator_fit']==expected_op,'persisted operator summary differs')
    token_audit=ready['header']['duplicate_candidate_safeguard']
    require(token_audit.get('scorer_counts_this_process') is not None,'missing inference token duplicate audit')
    base_inventory=read(role['evidence']['base_inventory']['path'])
    base_identity=base_identity_for(role,ident,base_inventory)
    return {'status':'reconstructed','identity':ident,'base_identity':base_identity,
            'runtime':role['evidence']['runtime'],'tokenizer':role['evidence']['tokenizer'],
            'descriptor':{k:v for k,v in desc.items() if k not in ('model_path','adapter')},'vectors':vectors,
            'panels':{'partitions':parts,'operator_fit':expected_op,'probability_panels':prob,'token_duplicate_audit':token_audit,
                      'clean_correct_counts':{s:{r:sum(vectors[s][r]) for r in ('raw','r0')} for s in SUITES}},
            'input_receipts':ev,'member':name,'campaign_sha256':campaign,'config_sha256':digest(c)}

def effect(a,b,fn):
    n=len(b);delta=Fraction(sum(a),n)-Fraction(sum(b),n) if all(type(x) is int for x in a) else Fraction(sum(Fraction(x) for x in a),n)-Fraction(sum(b),n)
    interval=fn(a,b)
    return {'n':n,'difference_percentage_points':float(delta*100),'exact_difference':{'numerator':delta.numerator,'denominator':delta.denominator},
            'interval_percentage_points':[100*interval['ci_lower'],100*interval['ci_upper']], 'historical_bootstrap':interval,
            'interval_interpretation':'inconclusive for positive difference' if interval['ci_lower']<=0<=interval['ci_upper'] else ('positive descriptive interval' if interval['ci_lower']>0 else 'negative descriptive interval')}

def comparison_job(job):
    packet,size,suite,lanes=job;fn=bootstrap(packet);start=time.monotonic()
    base,s2,s3=lanes;out={}
    for lane in lanes[1:]:
        require(lane['base_identity']==base['base_identity']==base['identity'],'same-size base bytes differ')
        for key in ('runtime','tokenizer','descriptor','campaign_sha256'):
            require(lane[key]==base[key],'runtime-confounded: '+key)
        for key in ('keys','ids','gold'):require(lane['vectors'][suite][key]==base['vectors'][suite][key],'paired population differs: '+key)
    for rule in ('raw','r0'):
        b=base['vectors'][suite][rule];a=s2['vectors'][suite][rule];c=s3['vectors'][suite][rule]
        require(len(a)==len(c)==len(b)==SUITES[suite],'wrong suite denominator')
        seeds={}
        for seed,v in ((2,a),(3,c)):
            seeds[str(seed)]={**effect(v,b,fn),'correct':sum(v),'base_correct':sum(b),'paired_discordants':{
                'candidate_only':sum(x==1 and y==0 for x,y in zip(v,b)), 'base_only':sum(x==0 and y==1 for x,y in zip(v,b)),
                'both_correct':sum(x==y==1 for x,y in zip(v,b)),'both_incorrect':sum(x==y==0 for x,y in zip(v,b))}}
        means=[(x+y)/2 for x,y in zip(a,c)];d=[x-y for x,y in zip(means,b)]
        out[rule]={'per_seed_descriptive':seeds,'two_seed_mean':{**effect(means,b,fn),'positive':sum(x>0 for x in d),'negative':sum(x<0 for x in d),'zero':sum(x==0 for x in d)}}
    probability_deltas={}
    for seed,lane in ((2,s2),(3,s3)):
        candidate=lane['panels']['probability_panels'][f'{suite}/test/clean']
        reference=base['panels']['probability_panels'][f'{suite}/test/clean']
        probability_deltas[str(seed)]={metric:{'candidate':candidate[metric],'base':reference[metric],
                                              'difference':candidate[metric]-reference[metric],
                                              'direction':'worsened' if candidate[metric]>reference[metric] else ('improved' if candidate[metric]<reference[metric] else 'unchanged')}
                                       for metric in ('nll','brier_sum','ece10')}
    return {'status':'complete','size':size,'suite':suite,'rules':out,'probability_differences_vs_own_base':probability_deltas,'seconds':time.monotonic()-start,'worker_pid':os.getpid()}

def historical_indicator(cells):
    out={}
    for size in SIZES:
        out[size]={}
        for rule in ('raw','r0'):
            valid=[cells[f'{size}/{s}'] for s in SUITES]
            if any(c['status']!='complete' for c in valid):out[size][rule]={'status':'unavailable','value':None};continue
            ds=[Fraction(**{'numerator':c['rules'][rule]['two_seed_mean']['exact_difference']['numerator'],'denominator':c['rules'][rule]['two_seed_mean']['exact_difference']['denominator']}) for c in valid]
            out[size][rule]={'status':'descriptive only','value':any(d>=Fraction(1,100) for d in ds) and all(d>=-Fraction(1,100) for d in ds),'intervals_percentage_points':{s:c['rules'][rule]['two_seed_mean']['interval_percentage_points'] for s,c in zip(SUITES,valid)}}
    return out

def run(config_path,out):
    started=time.monotonic();config=read(config_path);packet_pin=config['packet'];packet=read(pin(packet_pin))
    authenticate(packet,config,packet_pin);mods=instrument(packet);pop=populations(packet,mods[0]);references=reference_context(packet,config,pop)
    # Fingerprint includes actual complete authorized files (stores too), consumer
    # and bootstrap source. No weight files are opened or rehashed on polls.
    historical=load_module('rc1_bootstrap_identity',packet['bootstrap_wrapper']['path'])
    require(sha(historical.SELECTOR)==historical.SELECTOR_SHA256,'historical bootstrap source changed')
    # Cache reuse must also notice additions/deletions outside the declared
    # inventory; a changed directory cannot hide behind unchanged listed hashes.
    scope={}
    for name,evidence in packet['members'].items():
        c=read(evidence['config']['path']);base=Path(c['out'])
        scope[name]={'stores':sorted(str(p) for p in (base/'trackk').rglob('*.jsonl')),
                     'manifests':sorted(str(p) for p in (base/'manifests').glob('*.json'))}
    fingerprint=digest({'filesystem_scope':scope,'packet':packet_pin,'authorized':packet['authorized_files'],'consumer':sha(__file__),
                        'bootstrap':historical.SELECTOR_SHA256,'config':sha(config_path),'reference_adapter':sha(HERE/'reference.py'),'references':references})
    result_path=Path(out)/'comparison.json'
    if result_path.exists():
        old=read(result_path)
        if old.get('input_fingerprint')==fingerprint and old.get('own_base_status')=='complete':
            save(Path(out)/'poll.json',{'status':'identical input receipts; skipped','input_fingerprint':fingerprint});return old
    lanes={}
    for role in packet['roster']:
        name=role['id']
        if name in packet['members']:
            try:
                require(role['status']=='available','evidence supplied for failed/unavailable roster role')
                lanes[name]=member(packet,role,pop,mods)
            except Exception as exc:lanes[name]={'status':'invalid','reason':str(exc),'exception':type(exc).__name__}
        else:lanes[name]={'status':role['status'] if role['status']!='available' else 'missing','reason':role.get('reason','completed evidence absent')}
        save(Path(out)/'heartbeat.json',{'utc_epoch':time.time(),'phase':'validation','completed':len(lanes),'total':12})
    cells={};jobs=[]
    for size in SIZES:
        names=[size+'-base',size+'-s2',size+'-s3']
        for suite in SUITES:
            key=f'{size}/{suite}'
            if any(lanes[x]['status']!='reconstructed' for x in names):
                cells[key]={'status':'unavailable','roles':{x:lanes[x]['status'] for x in names},'reason':'complete authenticated own-Base and both seeds required'}
            else:jobs.append((packet,size,suite,[lanes[x] for x in names]))
    # One independent process per size/suite, sequential historical RNG inside it.
    if jobs:
        with concurrent.futures.ProcessPoolExecutor(max_workers=config['workers'],mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as pool:
            pending={pool.submit(comparison_job,j):f'{j[1]}/{j[2]}' for j in jobs}
            for future in concurrent.futures.as_completed(pending):
                key=pending[future]
                try:cells[key]=future.result()
                except Exception as exc:cells[key]={'status':'runtime-confounded/invalid','reason':str(exc)}
                save(Path(out)/'heartbeat.json',{'utc_epoch':time.time(),'phase':'bootstrap','completed':len(cells),'total':8})
    # Preserve standalone reconstructed panels when a comparison is unavailable.
    public_lanes={k:{a:b for a,b in v.items() if a!='vectors'} for k,v in lanes.items()}
    result={'schema':'rc1-same-test-comparison-v1','kind':packet['kind'],'fixture_only':packet['kind']=='generated',
            'status':'complete' if all(x['status']=='complete' for x in cells.values()) and references['status']=='complete' else 'partial',
            'own_base_status':'complete' if all(x['status']=='complete' for x in cells.values()) else 'partial',
            'reference_alignment_status':references['status'],
            'publication_authorized':False,'scientific_acceptance':False,'input_fingerprint':fingerprint,
            'roster':public_lanes,'comparisons':cells,'descriptive_historical_criterion_indicator':historical_indicator(cells),
            'limitations':['Conditional question-level descriptive intervals; not training-seed, cluster, multiplicity or universal-success inference.',
                          'Aggregate accuracy is not consistency. No G1/G2/G3, adoption or selection claim.',
                          'T=1 continuation panels differ from native/reference interfaces and their historical temperatures.',
                          'No actual results may be published before independent numerical and final evidence review.'],
            'reference_context':references,
            'runtime':{'seconds':time.monotonic()-started,'max_cpu_workers':config['workers'],'bootstrap_jobs':len(jobs),'npu_used':False},
            'source':{'producer_sha256':PRODUCER_SHA,'wrapper_sha256':WRAPPER_SHA,'selector_sha256':historical.SELECTOR_SHA256}}
    # Never cache invalid/partial results across evidence mutation repairs; complete
    # immutable packets alone can skip arithmetic on subsequent polls.
    save(result_path,result)
    lines=[f"RC1 same-TEST numerical consumer: {result['status']} ({packet['kind']}). Publication authorized: false."]
    lines += [f"Own-Base: {result['own_base_status']}; required reference alignment: {result['reference_alignment_status']}; performance: {references['performance_status']}."]
    lines += [f'{k}: {v["status"]}'+(' — '+v['reason'].split(';')[0][:180] if 'reason' in v else '') for k,v in public_lanes.items()]
    lines += [f"Own-Base: {result['own_base_status']}; required reference alignment: {result['reference_alignment_status']}; performance: {references['performance_status']}."]
    lines += [f'{k}: {v["status"]}' for k,v in sorted(cells.items())]
    lines += ['All panels and intervals: comparison.json. Accuracy is not consistency. Final independent evidence review remains required.']
    Path(out,'digest.md').write_text('\n'.join(lines)+'\n')
    return result

def reference_context(packet,config,pop=None):
    # Explicit local module loading also works under python -P (no cwd imports).
    adapter=load_module('rc1_reference_metadata',HERE/'reference.py')
    return adapter.context(sys.modules[__name__],packet,config,pop)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args()
    try:
        r=run(a.config,a.out);print(canonical({'status':r['status'],'fixture_only':r['fixture_only'],'publication_authorized':False}))
        return 0 if r['status']=='complete' else 2
    except Exception as exc:
        save(Path(a.out)/'failure.json',{'status':'rejected','reason':str(exc),'exception':type(exc).__name__,'publication_authorized':False,
             'roster':{r:{'status':'unaccepted','reason':'packet rejected before acceptance'} for r in ROLES},
             'comparisons':{f'{s}/{u}':{'status':'unavailable','reason':'packet rejected before acceptance'} for s in SIZES for u in SUITES}})
        print(canonical({'status':'rejected','reason':str(exc)}));return 1
if __name__=='__main__':raise SystemExit(main())
