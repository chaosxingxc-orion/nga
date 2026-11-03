#!/usr/bin/env python3
"""Freeze current K0 control inputs and exact independent-review package; no launch."""
import argparse,hashlib,importlib,json,shutil,sys,subprocess,shlex
from pathlib import Path
from r3_k0_current_identity import *
DATA=Path('/mnt/cephfs/xingchao/experiments/jev');RUNS=DATA/'r3_runs';REPO=Path('/home/xingchao/workspace/nga')

def qualification_sources(config,files):
    """Close the qualifier's verified historical source dependencies explicitly."""
    from r3_k0_current_identity_consume import load
    Q=load(read(config)['qualifier']);legacy=Q.legacy();root=Q.LEGACY
    def add(path,expected):
        path=str(path);require(sha(path)==expected,'qualification source differs: '+path)
        require(path not in files or files[path]==expected,'conflicting qualification pin: '+path)
        files[path]=expected
    add(root/'consumer.py',Q.LEGACY_SHA)
    add(root/'SOURCE_PINS.json',legacy.SOURCE_PINS_SHA256)
    inventory=read(root/'SOURCE_PINS.json')
    add(root/'closure/manifest.json',inventory['closure_manifest_sha256'])
    add(root/'R0_COMPATIBLE_SOURCES.json',legacy.R0_SOURCES_SHA256)
    for entry in inventory['files']:
        require(Path(entry['snapshot']).is_relative_to(root),'historical source escaped closure')
        add(entry['snapshot'],entry['sha256'])
    add(Q.BRIDGE,Q.BRIDGE_SHA)
    add(Q.BRIDGE.parent/'role_validator.py',Q.ROLE_SHA)

def prepare(root,chip):
    import numpy as np
    root=Path(root);require(root.parent==RUNS and not root.exists(),'fresh run root required');root.mkdir();(root/'code').mkdir();(root/'output').mkdir();(root/'output/cpu').mkdir();(root/'inputs').mkdir()
    files={};refs={}
    for k,n in [('runtime','r3_k0_current_identity.py'),('host','r3_k0_current_identity_host.py'),('consumer','r3_k0_current_identity_consume.py')]:
        dest=root/'code'/n;shutil.copyfile(REPO/'tools'/n,dest);refs[k]=pin(dest);files[str(dest)]=sha(dest)
    for directory in [DATA/'r3_code',DATA/'r0_code']:
        for f in directory.glob('*.py'):files[str(f)]=sha(f)
    sys.path.insert(0,str(DATA/'r0_code'));sys.path.insert(0,str(DATA/'r3_code'));import common;import track_t_r3 as TrackT
    sources={};source_refs={}
    km=read(DATA/'KEV/manifest.json');tm=read(DATA/'manifest.json')
    for p in [DATA/'KEV/manifest.json',DATA/'manifest.json']:files[str(p)]=sha(p)
    for suite in SUITES:
        if suite.startswith('T1/'):
            name=suite.split('/')[1];p=DATA/'T1_level_names'/(name+'.jsonl');require(p.exists(),'task source missing')
            rows=common.load_records(str(p));src={r['key']:r for r in rows};require(len(src)==len(rows),'source duplicate key')
            require(len(rows)==tm['tasks']['T1_level_names'][name]['records'],'task manifest record count differs')
        else:
            p=DATA/'KEV'/suite/'dev.jsonl';src=rows_jsonl(p,lambda r:r['kev']['id']+'/'+str(r['kev']['qindex']))
            declared=km['suites'][suite]['partitions']['dev']['outputs'];require(any(v.get('sha256')==sha(p) for v in declared.values()),'DEV manifest differs')
        files[str(p)]=sha(p);sources[suite]=src;source_refs[suite]=pin(p)
    targets={};cells=[];rng=np.random.default_rng(20261030)
    for model in MODELS:
        bp=REPO/'.local/preparations/k0-member-evidence-20261103-v1'/('k0_'+model+'-BUNDLE.json');b=read(bp);e=b['entry'];res=Path(e['report']).parent;exe=read(e['execution'])
        files.update(b['files']);files[str(bp)]=sha(bp)
        identity=read(res/'RUN_IDENTITY.json');require(identity['model_sha256']==e['model']['sha256'],'target weight identity differs')
        terms=[Path(exe['out'])/'ENGINEERING_EVAL_EXIT.json',Path(exe['out'])/'attempts/1/EXIT.json']
        for t in terms:require(type(read(t)['exit_code'])is int and read(t)['exit_code']==0,'target terminal failed')
        targets[model]={'bundle':pin(bp),'execution':pin(e['execution']),'identity':pin(res/'RUN_IDENTITY.json'),'report':pin(e['report']),'model':e['model'],'terminals':[pin(p) for p in terms]}
        for suite in SUITES:
            raw=res/('trackt/readouts/primary__'+suite.replace('/','__')+'__shard0of1.jsonl' if suite.startswith('T1/') else 'trackk/'+suite+'__dev/clean.jsonl')
            population={r['key']:r for r in TrackT.records_needed(list(sources[suite].values()),TrackT.CONFIG_R3)} if suite.startswith('T1/') else sources[suite]
            rr=current_raw(raw,population,e['model']['sha256']);require(set(rr)==set(population),'current raw population differs from registered plan');keys=sorted(rr);require(len(keys)>=64,'insufficient population')
            picked=[keys[i] for i in sorted(rng.choice(len(keys),size=64,replace=False).tolist())]
            cells.append({'checkpoint':model,'suite':suite,'n_finished_keys':len(keys),'keys':picked,'rows':[sources[suite][k] for k in picked],'stored':[rr[k]['s'] for k in picked],'source':source_refs[suite],'raw':pin(raw),'receipt':pin(str(raw)+'.receipt.json'),'execution':targets[model]['execution']})
    sample={'seed':20261030,'n_per_cell':64,'sampling':'single numpy default_rng; base then instruct; fixed suites; sorted keys and sampled indices','cells':cells}
    sample['sample_sha1']=hashlib.sha1(json.dumps(sample,sort_keys=True).encode()).hexdigest();sp=root/'inputs/sample.json';put(sp,sample);sh=root/'inputs/sample.sha1';sh.write_text(sample['sample_sha1']+'\n');files[str(sp)]=sha(sp);files[str(sh)]=sha(sh)
    controls=[];base=targets['base']['model']['path'];instruct=targets['instruct']['model']['path'];adapter=str(root/'adapter')
    Path(adapter).mkdir()
    image=read(RUNS/'native_dev_execution_20261103_v4/HOST-PLAN.json')['image_sha256']
    cp=['docker','run','--name','nga-'+root.name+'-adapter-copy','--network=none','--mount','type=bind,src='+str(RUNS/'smoke100/adapter')+',dst=/old,readonly','--mount','type=bind,src='+adapter+',dst=/new',image,'python3','-B','-P','-c',"import shutil,os;[shutil.copyfile('/old/'+n,'/new/'+n) for n in ['adapter_config.json','adapter_model.safetensors']];[os.chmod('/new/'+n,0o644) for n in ['adapter_config.json','adapter_model.safetensors']]"]
    subprocess.run(['ssh','npu',shlex.join(cp)],check=True,capture_output=True,timeout=55)
    require(sha(Path(adapter)/'adapter_model.safetensors')=='9ff31658692a1fd67bf2175afe6a9782ae6c06593373636edae17df2c13d0856','adapter snapshot differs')
    matrix=[('decision-v7','adapter'),('decision-v7','base'),('transfer-v4','adapter'),('transfer-v4','base'),('T1/typed-decisions','adapter'),('T1/openjev-synth','adapter'),('T1/akhilaaa3','adapter'),('T1/typed-decisions','r0model'),('T1/openjev-synth','r0model'),('T1/akhilaaa3','r0model')]
    for suite,tag in matrix:
        old=RUNS/'scorer_r3/c32/data'/suite.replace('/','__')/tag;side=read(old/'sample.json');keys=[m['key'] for m in side['meta']];require(len(set(keys))==len(keys),'historical sample duplicate')
        require(all(k in sources[suite] for k in keys),'historical control outside actual source population')
        p=root/'inputs'/(suite.replace('/','__')+'_'+tag+'.json');put(p,{'keys':keys,'rows':[sources[suite][k] for k in keys]})
        controls.append({'id':suite.replace('/','__')+'_'+tag,'suite':suite,'tag':tag,'model':instruct if tag=='r0model' else base,'adapter':adapter if tag=='adapter' else None,'historical_sample':pin(old/'sample.json'),'historical_exact':pin(old/'exact.json'),'data':pin(p)})
        for f in [old/'sample.json',old/'exact.json',p]:files[str(f)]=sha(f)
    # Pin actual model/tokenizer/adapter files, not merely a directory label.
    # Protected adapter weights are hashed in the exact image by a device-free CPU check.
    files[adapter+'/adapter_model.safetensors']='9ff31658692a1fd67bf2175afe6a9782ae6c06593373636edae17df2c13d0856'
    files[adapter+'/adapter_config.json']='edd39f6e3b3528c04a0a7402fcd926ff0d8e2ebc93de370084f1da1d7babe702'
    native=read(RUNS/'native_dev_execution_20261103_v4/HOST-PLAN.json');resource=native['resource'];files[resource['path']]=resource['sha256']
    hist=RUNS/'harness_identity/IDENTITY_VERDICT.json';files[str(hist)]=sha(hist)
    qcfg=REPO/'.local/preparations/production-dev-qualification-20261103-v6/CONFIG.json';files[str(qcfg)]=sha(qcfg)
    files.update(read(qcfg)['immutable_files'])
    qualification_sources(qcfg,files)
    d={'consumer':refs['consumer'],'qualification_config':pin(qcfg),'schema':'r3-k0-current-identity-v1','runtime':refs['runtime'],'host':refs['host'],'resource':resource,'allocation':native['allocation'],'image_sha256':native['image_sha256'],'environment':native['environment'],'chip':chip,'poll_seconds':600,'container':'nga-'+root.name.replace('_','-'),'run':'r3_runs/'+root.name,'out':str(root/'output'),'code_dir':str(DATA/'r3_code'),'r0_dir':str(DATA/'r0_code'),'files':files,'targets':targets,'sample':pin(sp),'sample_sha1_file':str(sh),'controls':controls,'historical_identity':pin(hist),'seed':20261030,'n_per_cell':64,'call':32,'tau':TAU,'modes':list(MODES),'scientific_acceptance':False,'test_read':False,'final_acceptance':'NPU terminal is control-only; complete strict CPU report reconstruction and independent scoped adjudication required'}
    hp=root/'HOST-PLAN.json'
    # Existing evidence has broad read-boundary dependencies; mount those immutable roots read-only.
    mounts=[{'source':str(DATA),'destination':str(DATA),'readonly':True},{'source':str(REPO/'.local'),'destination':str(REPO/'.local'),'readonly':True}]
    mounts += [{'source':x,'destination':x,'readonly':True} for x in [base,instruct,'/usr/local/Ascend/driver','/usr/local/sbin','/etc/ascend_install.info']]
    mounts += [{'source':d['out'],'destination':d['out'],'readonly':False}]
    roots=[Path(x['source']) for x in mounts]
    for f in sorted(files):
        if not any(Path(f).is_relative_to(x) for x in roots):mounts.append({'source':f,'destination':f,'readonly':True})
    d['mounts']=mounts;put(hp,d)
    # Verify copied runtime, not the repository source path.
    import types
    module=types.ModuleType('k0_frozen');module.__file__=refs['runtime']['path'];exec(compile(Path(module.__file__).read_bytes(),module.__file__,'exec'),module.__dict__);module.verify(hp,sha(hp))
    host=types.ModuleType('k0_host');host.__file__=refs['host']['path'];exec(compile(Path(host.__file__).read_bytes(),host.__file__,'exec'),host.__dict__)
    review={'status':'PENDING_INDEPENDENT_REVIEW','plan':pin(hp),'hashes':dict(files,**{str(hp):sha(hp)}),'expected_commands':{str(a):host.command(d,hp,sha(hp),a) for a in (1,2)},'scientific_acceptance':False,'test_read':False,'npu_started':False,'cpu_consumer':d['consumer'],'cpu_after_successful_release':True,'cpu_commands':{str(a):host.cpu_command(d,hp,sha(hp),a) for a in (1,2)}}
    put(root/'REVIEW-INPUT.json',review)
    local=sorted(f for f in files if f.startswith(str(REPO/'.local')+'/'));listing=root/'LOCAL-FILES.txt';listing.write_text(''.join(str(Path(f).relative_to(REPO/'.local'))+'\n' for f in local))
    archive=subprocess.run(['tar','-C',str(REPO/'.local'),'-cf','-','-T',str(listing)],stdout=subprocess.PIPE,check=True).stdout
    subprocess.run(['ssh','npu','mkdir -p /home/xingchao/workspace/nga/.local && tar -C /home/xingchao/workspace/nga/.local -xf -'],input=archive,check=True,capture_output=True)
    launch=['/usr/bin/python3.12','-B','-P',refs['host']['path'],'start','--plan',str(hp),'--sha256',sha(hp),'--review','<independent exact receipt>','--review-sha256','<receipt sha>','--attempt','1']
    cpu=list(launch);cpu[4]='cpu-supervise'
    put(root/'OPERATIONS.json',{'launch_template':launch,'cpu_completion_pending':True,'cpu_supervisor_template':cpu,'cpu_uses_device_free_container':True})
    return pin(hp)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--chip',type=int,choices=[0,6,7],required=True);a=ap.parse_args();print(json.dumps(prepare(a.root,a.chip)))
