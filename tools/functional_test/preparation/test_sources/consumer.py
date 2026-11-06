#!/usr/bin/env python3
"""Receipt-bound matched-current DEV reconstruction. No model imports or weight reads.
Exit 0 complete, 2 pending, 1 refused. Fixtures require --allow-fixture and stay labelled.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from fractions import Fraction

HERE = Path(__file__).resolve().parent

def sha(path):
    return L.digest(read(path))

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value

# Immutable accepted consumer, imported without constructing its historical catalog.
L = module('matched_legacy', HERE/'legacy_consumer.py')
require, obj, read, canonical = L.require, L.obj, L.read, L.canonical
Pending, Contradiction = L.Pending, L.Contradiction
_original_read = read
_accesses = {}

def stat_signature(path):
    value=Path(path).stat()
    return (value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns)

def read(path, expected=None):
    try:before=stat_signature(path)
    except (FileNotFoundError,PermissionError) as e:raise Pending(str(e)) from e
    data=_original_read(path,expected)
    signature=stat_signature(path)
    require(signature==before,'input changed while reading: '+str(path))
    key=str(Path(path).resolve())
    require(key not in _accesses or _accesses[key]==signature,'input changed during reconstruction: '+key)
    _accesses[key]=signature
    return data

L.read=read
CLEAN = ('decision-v7/calibration/clean','decision-v7/dev/clean','transfer-v4/dev/clean')
ALL = tuple(g for label in ('decision-v7/calibration','decision-v7/dev','transfer-v4/dev')
            for g in [label+'/'+k for k in (('clean',) if label.endswith('calibration') else
                                           ('clean','variants','question_only','empty_input'))])
SIZES = ('0.8B','2B','4B','9B')
COUNTS = {'decision-v7/calibration':1148,'decision-v7/dev':1264,'transfer-v4/dev':656}
SETUP = 'source /usr/local/Ascend/ascend-toolkit/set_env.sh; source /usr/local/Ascend/cann-9.2.0/share/info/ascendnpu-ir/bin/set_env.sh; source /usr/local/Ascend/nnal/atb/set_env.sh --cxx_abi=1; export PYTHONPATH=/usr/local/Ascend/cann-9.2.0/python/site-packages:/usr/local/Ascend/cann-9.2.0/opp/built-in/op_impl/ai_core/tbe; exec python3 -B -P '

def expected_tail(base, phase, rid, model, adapter, out):
    return ['-c',SETUP+('/run/packet/producer.py' if base else '/run/phase_wrapper.py')+' "$@"','--',
            *(['--phase',phase,'--model-id',rid,'--out',out] if base else
              ['--model',model,'--adapter',adapter,'--out',out,'--phase',phase])]


def numerics(config):
    require(sha(HERE/'legacy_consumer.py') == config['legacy_consumer_sha256'], 'accepted consumer source changed')
    root = HERE/'numeric_sources'
    for name, pin in config['numeric_sources'].items():
        require(sha(root/(name+'.py')) == pin, 'numerical source changed: '+name)
    # Preload dependencies from these exact preserved sources. Never import an evaluator.
    previous = list(sys.path)
    try:
        for name in ('common','split','decision','thresholds','metrics','core_r3','variants_r3','degenerate_r3','provenance_r3'):
            module(name, root/(name+'.py'))
    finally:
        sys.path[:] = previous
    return sys.modules['core_r3'], sys.modules['variants_r3'], sys.modules['provenance_r3']


def probability(rows, raw):
    """Supplement binary64 T=1; ECE correctness is the raw-score first argmax."""
    require(len(rows) == len(raw) > 0, 'probability population')
    bins = [[] for _ in range(10)]
    edges = [i*0.1 for i in range(10)] + [1.0]
    losses, briers, mismatch, ties = [], [], 0, 0
    for row, saved in zip(rows, raw):
        s = saved['s']; ids = [x['id'] for x in row['levels']]
        require(len(s) == len(ids) > 0 and len(set(ids)) == len(ids), 'probability options')
        require(all(type(x) in (int,float) and math.isfinite(x) for x in s), 'probability scores')
        s=[float(x) for x in s]
        y = ids.index(row['gold']); maximum = max(s)
        exps = [math.exp(x-maximum) for x in s]; z = math.fsum(exps)
        p = [x/z for x in exps]
        loss = math.log(z)+(maximum-s[y]); require(math.isfinite(loss), 'nonfinite stable NLL')
        a = max(range(len(s)), key=s.__getitem__)
        mismatch += int(max(range(len(p)), key=p.__getitem__) != a)
        ties += int(s.count(maximum)>1)
        losses.append(loss); briers.append(math.fsum((x-int(i==y))**2 for i,x in enumerate(p)))
        confidence = max(p)
        b = next(i for i in range(10) if confidence >= edges[i] and
                 (confidence < edges[i+1] or i == 9 and confidence <= 1.0))
        bins[b].append((confidence,int(a==y)))
    n = len(rows); details=[]
    for i, values in enumerate(bins):
        count = len(values)
        contribution = abs(math.fsum(correct-conf for conf,correct in values))/n
        details.append({'lower':edges[i],'upper':edges[i+1],'n':count,
                        'mean_confidence':math.fsum(x for x,_ in values)/count if count else None,
                        'mean_correctness':sum(y for _,y in values)/count if count else None,
                        'contribution':contribution})
    try: nll=math.fsum(x/n for x in losses)
    except OverflowError: nll=float(sum((Fraction.from_float(x) for x in losses),Fraction())/n)
    require(math.isfinite(nll),'unrepresentable mean NLL')
    return {'scope':'registered supplement; binary64 T=1 clean panel; separate from old diagnostics',
            'n':n,'brier_sum':math.fsum(briers)/n,'nll':nll,
            'ece10':math.fsum(x['contribution'] for x in details),'bins':details,
            'probability_argmax_mismatches':mismatch,'exact_score_top_ties':ties}


def docker_inspect(cid):
    try:
        result = subprocess.run(['docker','inspect',cid],capture_output=True,text=True,timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Pending('container inspection unavailable: '+str(e)) from e
    require(result.returncode == 0, 'retained container absent/uninspectable: '+cid)
    result = L.decode(result.stdout)
    require(len(result)==1,'ambiguous container inspection')
    return result[0]


class Consumer:
    # Reuse identity and phase checks, never historical catalog construction or vectors.
    phase_receipts = L.Consumer.phase_receipts
    publication = L.Consumer.publication
    inference_handoff = L.Consumer.inference_handoff

    def __init__(self, config, inspector=docker_inspect, allow_fixture=False):
        _accesses.clear()
        self.config = config
        self.fixture = config.get('mode') == 'synthetic-fixture'
        require(config.get('mode') == 'production' or self.fixture and allow_fixture, 'fixture mode requires explicit opt-in')
        if not self.fixture:
            frozen=obj(HERE/'producer-config.json',config['producer_config_sha256'])
            require(config['image']==frozen['image'] and config['closure']==frozen['closure'],'accepted runtime config changed')
            require(config['new_contract']['data_pins']==frozen['data_pins'],'accepted data pins changed')
            require([{k:m[k] for k in ('id','size','model','weight_shard_pins')} for m in config['models']]==frozen['models'],'accepted Base roster/identity changed')
        require(config.get('cpu_workers') == 1, 'CPU numerical worker bound must be one')
        self.inspect = inspector
        self.C, self.V, self.pv = numerics(config)
        self.catalog = {'new_contract':config['new_contract'],'new_rc1_lanes':config['lanes']}
        self.refs = {m['id']:m for m in config['models']}
        require(len(self.refs)==4 and {m['size'] for m in self.refs.values()}==set(SIZES), 'four distinct Base sizes required')
        require(len(config['lanes'])==8 and len({x['lane'] for x in config['lanes']})==8,'eight adapters required')
        for size in SIZES:
            lanes = [x for x in config['lanes'] if x['size']==size]
            require(len(lanes)==2 and {x['seed'] for x in lanes}=={2,3},'fixed seed roster')
            for lane in lanes:
                require(type(lane['seed']) is int and self.refs[lane['baseline_id']]['size']==size,'wrong size/seed mapping')
        expected = config['new_contract']['expected_populations']
        require(self.fixture or expected==COUNTS,'frozen counts changed')
        self.pop={}
        for path,pin in config['new_contract']['data_pins'].items():
            p=Path(path)
            require(p.parent.name in L.SUITES and p.name in ('dev.jsonl','dev.variants.jsonl','calibration.jsonl'), 'non-DEV/calibration path')
            label=p.parent.name+'/'+('calibration' if p.name=='calibration.jsonl' else 'dev')
            self.pop[label,'variants' if '.variants.' in p.name else 'clean']=L.jsonl(path,pin)
        for label,n in expected.items():
            require(len(self.pop[label,'clean'])==n,'frozen population count '+label)
        if not self.fixture:
            require(len(self.pop['decision-v7/dev','variants'])==204 and len(self.pop['transfer-v4/dev','variants'])==108,'variant counts')
        self.keys=[[s,L.qkey(r)] for s in L.SUITES for r in self.pop[s+'/dev','clean']]
        self.checked_assets=set()

    def source_assets(self, model):
        if model['id'] in self.checked_assets:return
        c=self.config
        read(Path(c['closure'])/'manifest.json',c['closure_manifest_sha256'])
        for path,pin in c['source_pins'].items():read(path,pin)
        for path,pin in model['asset_pins'].items():
            require(Path(path).name in ('.complete','config.json','tokenizer.json','tokenizer_config.json','merges.txt','vocab.json'),'unexpected asset/weight payload')
            read(path,pin)
        require(read(Path(model['model']['base_path'])/'.complete').decode().splitlines()[0]==model['model']['base_revision'],'Base revision file')
        self.checked_assets.add(model['id'])

    def phases(self, role, directory, lane=None):
        """Inspect every existing exit before any missing sibling can mask failure."""
        packets={};missing=[]
        for phase in ('infer','score'):
            packet={};packets[phase]=packet
            for kind in ('EXIT','LAUNCH','COMMAND'):
                try:packet[kind]=obj(directory/(phase+'-'+kind+'.json'))
                except Pending as e:missing.append(str(e))
            if 'EXIT' in packet:
                e=packet['EXIT']
                require(all(type(e.get(k)) is int and e[k]==0 for k in ('exit_code','container_exit_code')),phase+' failed/invalid phase exit')
        # All exits were examined before an absent container/sibling can defer us.
        for phase,packet in packets.items():
            if 'LAUNCH' in packet and 'EXIT' in packet:
                require(packet['LAUNCH']['container_id']==packet['EXIT']['container_id'],'phase container ID mismatch')
            if 'LAUNCH' in packet and 'COMMAND' in packet:
                require(packet['LAUNCH']['command_sha256']==sha(directory/(phase+'-COMMAND.json')),'command digest')
                cmd=packet['COMMAND'];require(isinstance(cmd,list) and all(isinstance(x,str) for x in cmd),'command shape')
                require('--smoke' not in cmd and '--rm' not in cmd,'smoke/ephemeral command')
                def flag(key):
                    require(cmd.count(key)==1 and cmd.index(key)+1<len(cmd),'command flag '+key)
                    return cmd[cmd.index(key)+1]
                expected=role['id'] if lane is None else lane['lane']
                name='nga-rc1-matched-k0-'+expected+'-'+phase if lane is None else 'nga-rc1-cpu-full-'+expected+'-'+phase
                require(flag('--name')==name and flag('--phase')==phase,'phase name/role')
                require(cmd.count(self.config['image'])==1 and flag('--entrypoint')=='/bin/bash','command image')
                require(flag('--model-id')==expected if lane is None else
                        flag('--model')==role['model']['path'] and flag('--adapter')==lane['new_adapter'],'command model/seed')
                out=str(directory/'result') if lane is None else '/run/output/result'
                require(flag('--out')==out,'command output')
                cid=packet['LAUNCH']['container_id'];require(isinstance(cid,str) and re.fullmatch('[0-9a-f]{64}',cid),'container ID format')
                info=self.inspect(cid)
                require(info['Id']==cid and info['Name']=='/'+name and info['Image']==self.config['image'],'actual container image/identity')
                require(info['HostConfig'].get('AutoRemove') is False,'retained container required')
                label='nga.rc1.matched-k0' if lane is None else 'nga.rc1.record-grade'
                value=expected if lane is None else self.config['adapter_deployment_id']
                require(info['Config']['Labels'].get(label)==value,'container role label')
                image_index=cmd.index(self.config['image'])
                require(cmd[image_index+1:]==expected_tail(lane is None,phase,expected,role['model']['path'],None if lane is None else lane['new_adapter'],out),'frozen phase executable/arguments')
                require(info['Config']['Entrypoint']==['/bin/bash'] and info['Config']['Cmd']==cmd[image_index+1:],'actual container executable/arguments')
                if 'EXIT' in packet:
                    require(info['State']['Status']=='exited' and type(info['State']['ExitCode']) is int and info['State']['ExitCode']==0,'actual container phase failed')
                mounts={x['Destination']:x for x in info['Mounts']}
                closure=self.config['closure']
                required={closure:closure, '/mnt/cephfs/xingchao/experiments/jev/r0_code':closure+'/r0_code'} if lane is None else {closure+'/r3_code':closure+'/r3_code','/mnt/cephfs/xingchao/experiments/jev/r0_code':closure+'/r0_code'}
                required[role['model']['path']]=role['model']['path']
                if lane is not None:required[lane['new_adapter']]=lane['new_adapter']
                for dest,src in required.items():
                    require(dest in mounts and mounts[dest]['Source']==src and mounts[dest]['RW'] is False,'source/model mount '+dest)
                wrapper='/run/packet' if lane is None else '/run/phase_wrapper.py'
                require(wrapper in mounts and mounts[wrapper]['RW'] is False,'wrapper mount')
                src=Path(mounts[wrapper]['Source'])
                if lane is None:
                    read(src/'producer.py',self.config['producer_py_sha256']);read(src/'config.json',self.config['producer_config_sha256'])
                else:read(src,self.config['adapter_wrapper_sha256'])
                if phase=='infer':
                    chip=packet['LAUNCH']['chip']
                    expected_chip = list(self.refs).index(role['id'])+4 if lane is None else self.config['lanes'].index(lane)
                    require(chip==expected_chip,'phase assigned chip')
                    require(type(chip) is int and any(x['PathOnHost']=='/dev/davinci'+str(chip) for x in info['HostConfig']['Devices']),'inference device binding')
        if missing:raise Pending('; '.join(missing))
        return packets

    def header(self,h,model,adapter=None):
        c=self.config
        for k,v in {'arm':'K0' if adapter is None else 'K1','limit':0,'limit_groups':0,'dry_run_warnings':[],
                    'primary_input_mode':'full','prompt_version':'r0-prompt-v2','prompt_format':'raw-completion (no chat template)',
                    'render':'record_name','dtype':'float32'}.items():require(h[k]==v,'header '+k)
        require(h['partitions']==['dev','calibration'],'header partition order')
        require(h['checkpoint_revision']==model['model']['base_revision'],'header revision')
        expected={**c['new_contract']['scorer'],'scorer':'scorer_r3.R3Scorer',
                  'layout':'one row per candidate, right-padded with an explicit mask, LM head at the scored positions only; rows sorted by descending length and packed to token_budget per forward, per call of 32 questions',
                  'model_path':model['model']['path'],'adapter':adapter}
        require(h['scorer']==expected,'scorer descriptor mismatch')
        for path,pin in c['new_contract']['data_pins'].items():require(h['data_files'].get(path)==pin,'data header pin')

    def stores(self,run,h,model_sha,groups):
        require(h['groups']==list(groups) and set(h['stores'])==set(groups),'exact group scope/order')
        raw={};metrics={};ev={}
        for group in groups:
            suite,part,kind=group.split('/');label=suite+'/'+part
            rows=self.pop[label,'variants' if kind=='variants' else 'clean']
            path=run/'trackk'/(suite+'__'+part)/(kind+'.jsonl')
            data=read(path);receipt=obj(str(path)+'.receipt.json');e=h['stores'][group]
            require(e=={'store_sha256':L.digest(data),'receipt_sha256':sha(str(path)+'.receipt.json'),'rows':len(rows)},'store evidence '+group)
            allowed_paths={str(path.resolve())}
            if h.get('adapter') is not None:allowed_paths.add('/run/output/result/'+str(path.relative_to(run)))
            require(receipt['path'] in allowed_paths and receipt['model_sha256']==model_sha and receipt['scorer']==h['descriptor'],'receipt identity/path/scorer')
            require(type(receipt['committed_bytes']) is int and receipt['committed_bytes']==len(data) and receipt['sha256']==L.digest(data) and receipt['rows']==len(rows),'score receipt bytes/rows')
            values=[L.decode(line) for line in data.splitlines() if line.strip()]
            vals=L.score_rows(rows,values,model_sha)
            metrics[group]=L.summarize(rows,vals);raw[group]=values;ev[group]=e
        return raw,metrics,ev

    def reconstruct(self,run,h,report,model_sha,groups,k0):
        raw,metrics,ev=self.stores(run,h,model_sha,groups)
        parts=report['partitions'];require(set(parts)==set(COUNTS),'report partitions')
        cal=CLEAN[0];calrows=self.pop['decision-v7/calibration','clean']
        fitted=self.V.fit_operator(calrows,[x['s'] for x in raw[cal]])
        fit=report['operator_fit']
        require(fit['n']==len(calrows) and fit['partition']==('decision-v7/calibration/clean' if k0 else 'decision-v7/calibration') and fit['fitted']==fitted.summary(),
                'calibration fit summary: saved='+json.dumps(fit,sort_keys=True)+' reconstructed='+json.dumps(fitted.summary(),sort_keys=True)+' n='+str(len(calrows)))
        probability_panels={};vectors={};diagnostics={}
        for group in CLEAN:
            suite,part,_=group.split('/');label=suite+'/'+part;rows=self.pop[label,'clean'];saved=raw[group];scores=[x['s'] for x in saved];block=parts[label]
            require(block['n']==len(rows),'report n')
            L.compare_headline(metrics[group],block['headline'],label)
            for key,value in {'near_tie_census':self.C.near_tie_census(scores,gold=[self.C.gold_index(r) for r in rows],keys=[L.qkey(r) for r in rows],option_ids=[self.C.level_ids(r) for r in rows]),
                              'duplicate_option_audit':self.C.duplicate_option_audit(rows),'gold_position_distribution':self.C.gold_position_distribution(rows)}.items():
                require(block[key]==value,'diagnostic mismatch '+label+'/'+key)
            probability_panels[label]=probability(rows,saved)
            vectors[label]={rule:[v[rule] for v in L.score_rows(rows,saved,model_sha)] for rule in ('correct','r0')}
            if k0:
                exact=[{**{k:x[k] for k in ('k','ids','gold','s')},'p':self.C.softmax(x['s'])} for x in saved]
                require(block['vectors']==exact,'saved per-item vector/probability mismatch')
            if part=='dev':
                operator=self.V.operator_column(rows,scores,fitted,label)
                if k0:require(block['operator']==operator,'K0 operator mismatch')
                else:
                    require(all(k in block['arms'] for k in ('constant','uniform','question_only','empty_input')),'adapter controls missing')
                    for kind in ('question_only','empty_input'):
                        L.compare_headline(metrics[label+'/'+kind],block['arms'][kind],label+'/'+kind)
                    L.compare_headline(self.C.headline(rows,[[0.]*len(r['levels']) for r in rows]),block['arms']['uniform'],label+'/uniform')
                    variants=self.pop[label,'variants'];merged={x['k']:x['s'] for g in (group,label+'/variants') for x in raw[g]}
                    sec=block['secondary']
                    require(sec['operator']==operator,'adapter operator mismatch')
                    require(sec['permutation']==self.V.permutation_metrics(self.V.build_permutation_pairs(rows,variants),merged,lambda r,s:self.V.operator_decision(fitted,r,s)[0],'K1'),'adapter permutation mismatch')
                    require(sec['nota']==self.V.nota_metrics(self.V.build_nota_units(rows,variants),merged),'adapter NOTA mismatch')
                diagnostics[label]=block
        # Preserve the actual fitted table, not only its key-count summary.
        table=[{'tier':tier,'key':list(key),'tau':tau,'n_fit':n} for (tier,key),(tau,n) in sorted(fitted._table.items())]
        return {'metrics':metrics,'probability_panels':probability_panels,'operator_fit':fit,
                'reconstructed_tau_table':table,'full_report_diagnostics':diagnostics,
                'constant_control_validation':'retained producer diagnostic; not independently refitted (train population outside this consumer)',
                '_vectors':vectors,'_stores':ev}

    def consume(self,model,lane=None):
        c=self.config;rid=model['id'] if lane is None else lane['lane']
        d=Path(c['k0_root'])/rid if lane is None else Path(c['adapter_root'])/('full-'+rid)
        phases=self.phases(model,d,lane);self.source_assets(model);run=d/'result';handoff=obj(run/'INFERENCE-READY.json')
        h=handoff['inference_header'];adapter=None if lane is None else lane['new_adapter'];self.header(h,model,adapter)
        require(h['stages']=='k_score' and h['device']=='npu','inference stage')
        require(handoff['version']==1 and handoff['descriptor']==h['scorer'],'handoff descriptor')
        if lane is None:
            require(handoff['model_id']==rid and handoff['out']==str(run) and handoff['config_sha256']==c['producer_config_sha256'],'K0 handoff binding')
            actual=handoff['identity'];require(actual=={**model['model'],'files':model['weight_shard_pins']},'Base identity/inventory')
            require(h['model']==model['model'],'Base header identity')
            require(obj(run/'RUN_IDENTITY.json')['model_sha256']==actual['sha256'],'Base RUN_IDENTITY')
            require(set(handoff['import_bindings'])=={'full_eval_r3','eval_r3','core_r3','prompt','scorer_r3'},'source import inventory')
            for name,binding in handoff['import_bindings'].items():
                path=c['closure']+('/r0_code/' if name=='prompt' else '/r3_code/')+name+'.py'
                allowed={path}
                if name=='prompt':allowed.add('/mnt/cephfs/xingchao/experiments/jev/r0_code/prompt.py')
                require(binding['path'] in allowed and binding['sha256']==c['source_pins'][path],'source import binding '+name)
            report=obj(run/'clean-report.json')
            require(report['schema']=='matched-k0-clean-dev-v1' and report['scope']=='clean calibration and DEV only; no DEV variants/drop/blank','K0 report schema/scope')
            require(report['model_id']==rid and report['identity']==actual and report['inference_receipt_sha256']==sha(run/'INFERENCE-READY.json') and report['inference_header']==h and report['stores']==handoff['stores'],'K0 report binding')
            data=self.reconstruct(run,handoff,report,actual['sha256'],CLEAN,True)
            evidence={'inference_sha256':sha(run/'INFERENCE-READY.json'),'stores':data['_stores']}
            require(phases['infer']['EXIT']['artifact_evidence']==evidence,'inference terminal artifacts')
            require(phases['score']['EXIT']['artifact_evidence']=={**evidence,'report_sha256':sha(run/'clean-report.json')},'score terminal artifacts')
        else:
            report,top=L.selective(run/'report.json',{'header','track_k','selection_evidence'})
            require('track_t' not in top,'forbidden Track T payload')
            header=report['header'];self.header(header,model,adapter)
            require(header['stages']=='k' and header['device']=='cpu','adapter score stage')
            model_sha,pub=self.publication(lane,run,'phased');self.inference_handoff(run,header)
            require(header['model']=={'path':adapter,'sha256':model_sha,'kind':'lora-adapter-unmerged','base_path':model['model']['path'],'base_revision':model['model']['base_revision']},'adapter model identity')
            require(obj(run/'RUN_IDENTITY.json')['model_sha256']==model_sha,'adapter RUN_IDENTITY')
            data=self.reconstruct(run,handoff,report['track_k'],model_sha,ALL,False);data['publication']=pub
            if report.get('selection_evidence') is not None:
                v=report['selection_evidence'];require(v['keys']==self.keys and v['correct']==sum([data['_vectors'][s+'/dev']['correct'] for s in L.SUITES],[]),'saved selection vector mismatch')
            selected=[str(run/'trackk'/(g.split('/')[0]+'__'+g.split('/')[1])/(g.split('/')[2]+'.jsonl')) for g in ALL]
            try:self.pv.verify(str(run),[],model_sha,selected_files=selected,role_of=lambda p:p)
            except self.pv.ProvenanceRefusal as e:raise Contradiction(str(e)) from e
        data.update(role=rid,size=model['size'],seed=None if lane is None else lane['seed'],baseline_id=model['id'],status='VALIDATED_OPERAND',groups=list(CLEAN if lane is None else ALL),
                    runtime={'image':c['image'],'status':'ALIGNED_INSTRUMENT','note':'Retained container/image/mounts and pinned sources; K0 actual import bindings. No mathematical or cross-image equivalence proof.'})
        data['evidence']={'report':str(run/('clean-report.json' if lane is None else 'report.json')),
                          'report_sha256':sha(run/('clean-report.json' if lane is None else 'report.json')),
                          'inference_receipt_sha256':sha(run/'INFERENCE-READY.json'),
                          'stores':data.pop('_stores'),
                          'phase_receipts_sha256':{phase:{kind:sha(d/(phase+'-'+kind+'.json')) for kind in ('LAUNCH','COMMAND','EXIT')} for phase in ('infer','score')},
                          'ordered_keys':{label:[L.qkey(r) for r in self.pop[label,'clean']] for label in COUNTS}}
        return data


def recovery_disposition(c, path, operand):
    """Accept only a recorded retry of this exact pre-inference publication failure."""
    root = Path(c.config['adapter_root']); lane = path.name[:-len('-ERROR.json')]
    matches = [x for x in c.config['lanes'] if x['lane'] == lane]
    require(len(matches) == 1 and path.parent == root, 'unknown recovery lane')
    lane_config = matches[0]
    rec = root.parent/'dev-publication-recovery'
    disposition = obj(rec/(lane+'-disposition.json'))
    error = obj(path)
    expected = "[Errno 13] Permission denied: '"+str(Path(lane_config['new_adapter'])/'PUBLICATION.json')+"'"
    trace = error.get('traceback','')
    require(error.get('error') == expected and 'binding=ready(j)' in trace and
            "pub=json.loads((adapter/'PUBLICATION.json').read_text())" in trace and
            ('PermissionError: '+expected) in trace, 'not the eligible pre-infer permission failure')
    require(disposition.get('schema') == 'rc1-dev-publication-recovery-v1' and
            disposition.get('lane') == lane and disposition.get('error_path') == str(path) and
            disposition.get('error_sha256') == sha(path) and disposition.get('original_error') == expected,
            'recovery error binding mismatch')
    package = root.parent/'cpu-separated'; approved = obj(root/'REVIEW-APPROVED.json')
    for field, name in (('queue_sha256','queue_proposal.py'),('wrapper_sha256','phase_wrapper.py'),('config_sha256','config.json')):
        require(disposition.get(field) == approved.get(field) == sha(package/name), 'recovery recipe mismatch '+field)
    require(disposition['wrapper_sha256'] == c.config['adapter_wrapper_sha256'], 'recovery wrapper differs from consumer')
    queue_config = obj(package/'config.json')
    jobs = [j for j in queue_config['jobs'] if j['id'] == lane]
    model = c.refs[lane_config['baseline_id']]
    require(len(jobs)==1 and jobs[0]['model']==model['model']['path'] and
            jobs[0]['seed']==lane_config['seed'] and jobs[0]['size']==lane_config['size'], 'recovery model/seed mismatch')
    require(disposition.get('phase_directory_full') == str(root/('full-'+lane)) and
            disposition.get('phase_directory_smoke') == str(root/('smoke-'+lane)), 'recovery directory mismatch')
    require(not (rec/(lane+'-ERROR.json')).exists(), 'recovery attempt failed')
    state = disposition.get('state')
    require(state in ('pending_retry','complete'), 'recovery failed/unknown')
    if state == 'pending_retry':
        require(operand['status'] != 'REFUSED_CONTRADICTION', 'retry phase contradiction')
        return {'path':str(path),'lane':lane,'status':'PENDING_RETRY','disposition':str(rec/(lane+'-disposition.json'))}
    require(operand['status'] == 'VALIDATED_OPERAND', 'recovery has no validated phase artifacts')
    receipts=disposition.get('phase_receipts',{})
    for phase in ('infer','score'):
        for kind in ('LAUNCH','COMMAND','BINDING','EXIT'):
            p=root/('full-'+lane)/(phase+'-'+kind+'.json')
            require(receipts.get(str(p)) == sha(p), 'retry phase receipt binding mismatch')
    return {'path':str(path),'lane':lane,'status':'RECOVERED_VALIDATED','disposition':str(rec/(lane+'-disposition.json'))}


def assemble(c):
    queue_failures=[]; historical_errors=[]; recovery=[]
    for root,name in ((c.config['k0_root'],'QUEUE-EXIT.json'),(c.config['adapter_root'],'EXIT.json')):
        p=Path(root)/name
        if p.is_file():
            terminal=obj(p)
            if type(terminal.get('exit_code')) is not int or terminal['exit_code']!=0 or any(v!='complete' for v in terminal.get('results',{}).values()):
                queue_failures.append({'path':str(p),'detail':'queue terminal failure/invalid results'})
        for p in Path(root).glob('*-ERROR.json'):
            historical_errors.append(p)
    operands=[]
    for model in c.refs.values():
        jobs=[None]+[x for x in c.config['lanes'] if x['baseline_id']==model['id']]
        for lane in jobs:
            rid=model['id'] if lane is None else lane['lane']
            try:value=c.consume(model,lane)
            except Pending as e:value={'role':rid,'size':model['size'],'seed':None if lane is None else lane['seed'],'status':'PENDING_MISSING_INPUT','detail':str(e)}
            except (ValueError,KeyError,TypeError,IndexError,UnicodeError,OSError,ArithmeticError) as e:
                value={'role':rid,'size':model['size'],'seed':None if lane is None else lane['seed'],'status':'REFUSED_CONTRADICTION','detail':str(e)}
            operands.append(value)
    index={x['role']:x for x in operands}
    for path in historical_errors:
        try:
            lane=path.name[:-len('-ERROR.json')]
            recovery.append(recovery_disposition(c,path,index[lane]))
        except Pending:
            queue_failures.append({'path':str(path),'detail':'missing recovery disposition'})
        except (ValueError,KeyError,TypeError,IndexError,UnicodeError,OSError,ArithmeticError) as e:
            queue_failures.append({'path':str(path),'detail':'invalid recovery disposition: '+str(e)})
    comparisons=[];means=[]
    for model in c.refs.values():
        base=index[model['id']];lanes=[x for x in c.config['lanes'] if x['baseline_id']==model['id']];ready=[]
        for lane in lanes:
            v=index[lane['lane']];pair={'lane':lane['lane'],'size':lane['size'],'seed':lane['seed'],'baseline_id':model['id'],'status':'PENDING_OPERANDS','suites':None}
            if '_vectors' in base and '_vectors' in v:
                pair.update(status='MATCHED_CURRENT_DESCRIPTIVE_DEV',suites={})
                for suite in L.SUITES:
                    label=suite+'/dev';pair['suites'][label]={rule:L.paired(v['_vectors'][label][key],base['_vectors'][label][key]) for rule,key in [('first_argmax','correct'),('r0_tie_incorrect','r0')]}
                ready.append(v)
            elif any(x['status']=='REFUSED_CONTRADICTION' for x in (base,v)):pair['status']='REFUSED_CONTRADICTION'
            comparisons.append(pair)
        mean={'size':model['size'],'required_seeds':[2,3],'finished_seeds':[v['seed'] for v in ready],'suites':None,'status':'INCOMPLETE_NO_TWO_SEED_MEAN'}
        if len(ready)==2 and {x['seed'] for x in ready}=={2,3}:
            mean.update(status='MATCHED_CURRENT_DESCRIPTIVE_DEV',suites={})
            for suite in L.SUITES:
                label=suite+'/dev';mean['suites'][label]={}
                for rule,key in [('first_argmax','correct'),('r0_tie_incorrect','r0')]:
                    a,b=[x['_vectors'][label][key] for x in ready];z=base['_vectors'][label][key]
                    require(len(a)==len(b)==len(z)>0,'mean paired lengths')
                    mean['suites'][label][rule]={'n_questions':len(z),'seed_count':2,'dev_same_question_two_seed_mean_difference':sum((x+y)/2-v for x,y,v in zip(a,b,z))/len(z)}
        means.append(mean)
    for value in operands:
        if '_vectors' in value:
            value['ordered_correctness']=value.pop('_vectors')
            value['correctness_sha256']=canonical(value['ordered_correctness'])
    bad=bool(queue_failures) or any(x['status']=='REFUSED_CONTRADICTION' for x in operands);pending=any(x['status']=='PENDING_MISSING_INPUT' for x in operands) or any(x['status']=='PENDING_RETRY' for x in recovery)
    status='REFUSED_CONTRADICTION' if bad else 'INCOMPLETE_PENDING' if pending else 'MATCHED_CURRENT_DESCRIPTIVE_DEV'
    for path,signature in _accesses.items():
        require(stat_signature(path)==signature,'input changed during reconstruction: '+path)
    return {'schema':'matched-current-dev-comparison-v1','status':status,'synthetic_fixture':c.fixture,
            'scope':'defect12 instrument prerequisite; DEV descriptive per size/suite/seed; no pooling, CI, success gate, TEST reads, or cross-image equivalence',
            'k0_diagnostic_scope':'three clean DEV/calibration groups only; variants/drop/blank unavailable',
            'uncertainty':'No DEV bootstrap interval registered here; two fixed seeds do not isolate training randomness. Adverse controls remain reportable.',
            'queue_failures':queue_failures,'recovery_dispositions':recovery,'operands':operands,'comparisons':comparisons,'within_size_two_seed_means':means},1 if bad else 2 if pending else 0


def persist(out,result):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    text=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    (out/'comparison.json.tmp').write_text(text);os.replace(out/'comparison.json.tmp',out/'comparison.json')
    lines=['Matched-current DEV: '+result['status'],'',result.get('scope',''),'', 'Synthetic fixture: '+str(result.get('synthetic_fixture',False)),'']
    for v in result.get('operands',[]):lines.append(v['role']+': '+v['status']+(' — '+v['detail'] if 'detail' in v else ''))
    (out/'comparison.md').write_text('\n'.join(lines)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(HERE/'config.json'));p.add_argument('--output',required=True);p.add_argument('--allow-fixture',action='store_true');a=p.parse_args()
    try:result,code=assemble(Consumer(obj(a.config),allow_fixture=a.allow_fixture))
    except Pending as e:result,code={'status':'INCOMPLETE_PENDING','detail':str(e)},2
    except (ValueError,KeyError,TypeError,IndexError,UnicodeError,OSError,ArithmeticError) as e:result,code={'status':'REFUSED_CONTRADICTION','detail':str(e)},1
    persist(a.output,result);print(json.dumps({'status':result['status'],'exit_code':code}));return code

if __name__=='__main__':sys.exit(main())
