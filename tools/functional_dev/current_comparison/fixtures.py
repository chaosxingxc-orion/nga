"""Explicit synthetic receipt-shaped packet. No production evidence or model loading.
All payloads and inspections generated below are labelled by config.mode and path.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('matched_fixture_consumer',HERE/'consumer.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')

def jsonl(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True,allow_nan=False)+'\n' for x in rows))

def row(i,suite):
    return {'kev':{'id':suite+'/q'+str(i),'qindex':0},'source':'fixture-decision' if suite=='decision-v7' else 'fixture-transfer',
            'qname':'fixture','level_type':'nominal','candidate_set':'exclusive','task_definition':'Choose.',
            'question':'Which?','input':'fixture '+str(i),'levels':[{'id':'a','name':'A','definition':'alpha'}, {'id':'b','name':'B','definition':'beta'}],
            'gold':'a' if i%2==0 else 'b'}

def variants(rows):
    out=[]
    for kind in ('permuted','none_present','none_absent'):
        r=copy.deepcopy(rows[0]);r['variant']=kind;r['kev']={'id':r['kev']['id']+'-'+kind,'parent_id':r['kev']['id'],'qindex':0}
        if kind=='permuted':r['levels'].reverse()
        else:
            r['levels'].append({'id':'none','name':'NONE','definition':'none of these'})
            r['kev']['none_key']='none'
        if kind=='none_absent':r['gold']='none'
        if kind!='permuted':r['input']+=' '+kind
        out.append(r)
    return out


def build(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    c=copy.deepcopy(M.obj(HERE/'config.json'));c.update(mode='synthetic-fixture',k0_root=str(root/'k0'),adapter_root=str(root/'adapters'),output=str(root/'comparison'),review=str(root/'REVIEW-NOT-CREATED.json'))
    # Frozen numerical source copies, with explicit synthetic paths/identities.
    C,V,PV=M.numerics(c);c['closure']=str(root/'fixture-closure');closure=Path(c['closure'])
    put(closure/'manifest.json',{'synthetic_fixture':True})
    c['closure_manifest_sha256']=M.sha(closure/'manifest.json');c['source_pins']={}
    for name in ('full_eval_r3','eval_r3','core_r3','scorer_r3','prompt'):
        p=closure/('r0_code' if name=='prompt' else 'r3_code')/(name+'.py');p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('# synthetic import binding, never executed\n');c['source_pins'][str(p)]=M.sha(p)
    packet=root/'fixture-producer-source';packet.mkdir(exist_ok=True)
    (packet/'producer.py').write_text('# synthetic mounted producer, never executed\n');put(packet/'config.json',{'synthetic_fixture':True})
    c['producer_py_sha256']=M.sha(packet/'producer.py');c['producer_config_sha256']=M.sha(packet/'config.json')
    wrapper=root/'fixture-phase-wrapper.py';wrapper.write_text('# synthetic adapter wrapper, never executed\n');c['adapter_wrapper_sha256']=M.sha(wrapper)
    populations={};pins={}
    for suite,split,n in [('decision-v7','calibration',24),('decision-v7','dev',4),('transfer-v4','dev',4)]:
        clean=[row(i,suite) for i in range(n)];populations[suite+'/'+split,'clean']=clean
        p=root/'populations'/suite/(split+'.jsonl');jsonl(p,clean);pins[str(p)]=M.sha(p)
        if split=='dev':
            var=variants(clean);populations[suite+'/'+split,'variants']=var
            p=p.with_name('dev.variants.jsonl');jsonl(p,var);pins[str(p)]=M.sha(p)
    c['new_contract']['data_pins']=pins;c['new_contract']['expected_populations']={label:len(rows) for (label,kind),rows in populations.items() if kind=='clean'}
    inspections={}
    for model in c['models']:
        base=root/'fixture-models'/model['id'];base.mkdir(parents=True,exist_ok=True)
        revision='fixture-revision-'+model['id'];weights={'fixture.safetensors':M.canonical(model['id'])}
        identity={'kind':'checkpoint','weight_files':weights,'revision':revision}
        model['model']={'path':str(base),'base_path':str(base),'kind':'checkpoint','base_revision':revision,'sha256':M.canonical(identity)}
        model['weight_shard_pins']=weights;model['asset_pins']={}
        for n in ('.complete','config.json','tokenizer.json','tokenizer_config.json','merges.txt','vocab.json'):
            p=base/n;p.write_text(revision+'\n' if n=='.complete' else 'synthetic asset '+n+'\n');model['asset_pins'][str(p)]=M.sha(p)
        for lane in c['lanes']:
            if lane['baseline_id']==model['id']:lane['new_adapter']=str(root/'train'/lane['lane']/'result/adapter')
        for lane in [None]+[x for x in c['lanes'] if x['baseline_id']==model['id']]:
            rid=model['id'] if lane is None else lane['lane'];isbase=lane is None
            d=Path(c['k0_root'])/rid if isbase else Path(c['adapter_root'])/('full-'+rid);run=d/'result';run.mkdir(parents=True,exist_ok=True)
            publication=None
            if not isbase:
                adapter=Path(lane['new_adapter']);ident={'seed':lane['seed'],'model_id':'Qwen3.5-'+model['size']+'-Base','model_revision':revision}
                binding={'owner':'rc1-functional-'+rid,'identity_sha256':M.canonical(ident,ascii=True),'checkpoint_sha256':'c'*64}
                put(adapter/'adapter_config.json',{'base_model_name_or_path':ident['model_id'],'revision':revision})
                pub={'binding':binding,'files':{'adapter_config.json':M.sha(adapter/'adapter_config.json'),'adapter_model.safetensors':M.canonical(rid)}}
                put(adapter/'PUBLICATION.json',pub);put(adapter/'BINDING.json',binding);put(adapter.parent/'OWNER.json',{'owner':binding['owner'],'identity':ident})
                put(adapter.parents[1]/'COMPLETE.json',{'exit_code':0,'steps':3116,'scientific_acceptance':False})
                files={**pub['files'],**{n:M.sha(adapter/n) for n in ('PUBLICATION.json','BINDING.json')}}
                modelsha=M.canonical({'kind':'lora-adapter-unmerged','adapter_files':files,'base_revision':revision,'base_path':str(base)})
                publication={'binding':binding,'publication_sha256':M.sha(adapter/'PUBLICATION.json')}
                expected_model={'path':str(adapter),'sha256':modelsha,'kind':'lora-adapter-unmerged','base_path':str(base),'base_revision':revision}
            else:modelsha=model['model']['sha256'];expected_model=model['model']
            desc={**c['new_contract']['scorer'],'scorer':'scorer_r3.R3Scorer','layout':'one row per candidate, right-padded with an explicit mask, LM head at the scored positions only; rows sorted by descending length and packed to token_budget per forward, per call of 32 questions',
                  'model_path':str(base),'adapter':None if isbase else lane['new_adapter']}
            h={'arm':'K0' if isbase else 'K1','partitions':['dev','calibration'],'limit':0,'limit_groups':0,'dry_run_warnings':[],
               'primary_input_mode':'full','prompt_version':'r0-prompt-v2','prompt_format':'raw-completion (no chat template)','render':'record_name','dtype':'float32',
               'stages':'k_score','device':'npu','model':expected_model,'checkpoint_revision':revision,'scorer':desc,'data_files':pins}
            groups=M.CLEAN if isbase else M.ALL;stores={};raw={};paths=[]
            for group in groups:
                suite,split,kind=group.split('/');label=suite+'/'+split;rows=populations[label,'variants' if kind=='variants' else 'clean'];rr=[]
                for i,r in enumerate(rows):
                    # Includes exact ties and adverse controls; size/seed vectors stay distinct.
                    s=([0.,0.] if i%4==0 else [2.,0.] if (isbase or lane['seed']==2) else [0.,2.])[:]
                    if len(r['levels'])==3:s.append(-1.)
                    if kind in ('question_only','empty_input'):s=[0.]*len(r['levels'])
                    arg=C.argmax_first(s);rr.append({'k':M.L.qkey(r),'ids':C.level_ids(r),'gold':r['gold'],'gold_index':C.gold_index(r),
                        'argmax':arg,'tie':C.is_tie(s),'s':s,'m':modelsha[:16],'source':r['source'],'level_type':r['level_type'],'qname':r['qname'],'variant':r.get('variant','original')})
                path=run/'trackk'/(suite+'__'+split)/(kind+'.jsonl');jsonl(path,rr);paths.append(str(path))
                receipt={'path':str(path) if isbase else '/run/output/result/'+str(path.relative_to(run)),'model_sha256':modelsha,'scorer':desc,'rows':len(rr),'committed_bytes':path.stat().st_size,'sha256':M.sha(path)}
                put(str(path)+'.receipt.json',receipt)
                stores[group]={'store_sha256':M.sha(path),'receipt_sha256':M.sha(str(path)+'.receipt.json'),'rows':len(rr)};raw[group]=rr
            handoff={'version':1,'out':str(run) if isbase else '/run/output/result','groups':list(groups),'descriptor':desc,'stores':stores,'inference_header':h}
            if isbase:
                handoff.update(model_id=rid,identity={**model['model'],'files':model['weight_shard_pins']},config_sha256=c['producer_config_sha256'],
                               import_bindings={name:{'path':p,'sha256':pin} for p,pin in c['source_pins'].items() for name in [Path(p).stem]})
            else:handoff.update(model=str(base),adapter=lane['new_adapter'],limit=0)
            put(run/'INFERENCE-READY.json',handoff);put(run/'RUN_IDENTITY.json',{'model_sha256':modelsha})
            cal=populations['decision-v7/calibration','clean'];fitted=V.fit_operator(cal,[x['s'] for x in raw[M.CLEAN[0]]]);parts={}
            for group in M.CLEAN:
                suite,split,_=group.split('/');label=suite+'/'+split;rows=populations[label,'clean'];rr=raw[group];scores=[x['s'] for x in rr]
                b={'n':len(rows),'headline':C.headline(rows,scores),'near_tie_census':C.near_tie_census(scores,gold=[C.gold_index(r) for r in rows],keys=[C.kev_key(r) for r in rows],option_ids=[C.level_ids(r) for r in rows]),
                   'duplicate_option_audit':C.duplicate_option_audit(rows),'gold_position_distribution':C.gold_position_distribution(rows)}
                if isbase:
                    b['vectors']=[{**{k:x[k] for k in ('k','ids','gold','s')},'p':C.softmax(x['s'])} for x in rr]
                    if split=='dev':b['operator']=V.operator_column(rows,scores,fitted,label)
                else:
                    b['arms']={}
                    if split=='dev':
                        for kind in ('question_only','empty_input'):b['arms'][kind]=C.headline(rows,[x['s'] for x in raw[label+'/'+kind]])
                        b['arms']['uniform']=C.headline(rows,[[0.]*len(r['levels']) for r in rows]);b['arms']['constant']=copy.deepcopy(b['arms']['uniform'])
                        var=populations[label,'variants'];merged={x['k']:x['s'] for g in (group,label+'/variants') for x in raw[g]}
                        b['secondary']={'operator':V.operator_column(rows,scores,fitted,label),'permutation':V.permutation_metrics(V.build_permutation_pairs(rows,var),merged,lambda r,s:V.operator_decision(fitted,r,s)[0],'K1'),
                                        'nota':V.nota_metrics(V.build_nota_units(rows,var),merged)}
                parts[label]=b
            track={'operator_fit':{'partition':'decision-v7/calibration/clean' if isbase else 'decision-v7/calibration','n':len(cal),'fitted':fitted.summary()},'partitions':parts}
            if isbase:
                put(run/'clean-report.json',{'schema':'matched-k0-clean-dev-v1','scope':'clean calibration and DEV only; no DEV variants/drop/blank','model_id':rid,'identity':handoff['identity'],
                                            'inference_receipt_sha256':M.sha(run/'INFERENCE-READY.json'),'inference_header':h,'stores':stores,**track})
            else:
                manifest=PV.write_unit_manifest(str(run),'',modelsha,desc,paths)
                scoreh={**h,'device':'cpu','stages':'k','provenance_manifest':'/run/output/result/manifests/main.json',
                        'phase_separation':{'inference_receipt_sha256':M.sha(run/'INFERENCE-READY.json'),'inference_header':h}}
                put(run/'report.json',{'header':scoreh,'track_k':track})
            for phase in ('infer','score'):
                name='nga-rc1-matched-k0-'+rid+'-'+phase if isbase else 'nga-rc1-cpu-full-'+rid+'-'+phase
                cid=M.canonical(['fixture-container',rid,phase]);chip=c['models'].index(model)+4 if isbase else c['lanes'].index(lane)
                mounts=[{'Source':str(base),'Destination':str(base),'RW':False},
                        {'Source':c['closure']+'/r0_code','Destination':'/mnt/cephfs/xingchao/experiments/jev/r0_code','RW':False}]
                if isbase:mounts += [{'Source':c['closure'],'Destination':c['closure'],'RW':False},{'Source':str(packet),'Destination':'/run/packet','RW':False}]
                else:mounts += [{'Source':c['closure']+'/r3_code','Destination':c['closure']+'/r3_code','RW':False},{'Source':str(wrapper),'Destination':'/run/phase_wrapper.py','RW':False},{'Source':lane['new_adapter'],'Destination':lane['new_adapter'],'RW':False}]
                cmd=['docker','run','-d','--name',name,'--entrypoint','/bin/bash',c['image'],
                     *M.expected_tail(isbase,phase,rid,str(base),None if isbase else lane['new_adapter'],handoff['out'])]
                put(d/(phase+'-COMMAND.json'),cmd);put(d/(phase+'-LAUNCH.json'),{'container_id':cid,'command_sha256':M.sha(d/(phase+'-COMMAND.json')),'chip':chip if phase=='infer' or not isbase else None})
                exit_={'container_id':cid,'exit_code':0,'container_exit_code':0,'finished_at':'synthetic-fixture'}
                if isbase:
                    ev={'inference_sha256':M.sha(run/'INFERENCE-READY.json'),'stores':stores}
                    if phase=='score':ev['report_sha256']=M.sha(run/'clean-report.json')
                    exit_['artifact_evidence']=ev
                else:put(d/(phase+'-BINDING.json'),publication)
                put(d/(phase+'-EXIT.json'),exit_)
                inspections[cid]={'Id':cid,'Name':'/'+name,'Image':c['image'],'Config':{'Entrypoint':['/bin/bash'],'Cmd':cmd[cmd.index(c['image'])+1:],'Labels':{'nga.rc1.matched-k0':rid} if isbase else {'nga.rc1.record-grade':c['adapter_deployment_id']}},
                    'State':{'Status':'exited','ExitCode':0},'HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci'+str(chip)}] if phase=='infer' else []},'Mounts':mounts}
    put(root/'fixture-config.json',c);put(root/'fixture-inspections.json',inspections)
    return c,inspections

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    config,inspections=build(a.output)
    result,code=M.assemble(M.Consumer(config,inspector=inspections.__getitem__,allow_fixture=True));M.persist(Path(a.output)/'comparison',result)
    print(json.dumps({'synthetic_fixture':True,'roles':len(result['operands']),'status':result['status'],'exit_code':code}));sys.exit(code)
