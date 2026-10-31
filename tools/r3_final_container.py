"""Exact retained-container contract and terminal reconciliation.

Pure command/observation checks; no launch, claim, release or approval. The host
supervisor must apply this contract before launch and before resource release.
"""
import json
from pathlib import Path
import re


ENV={'ASCEND_RT_VISIBLE_DEVICES':'0','TASK_QUEUE_ENABLE':'2',
     'PYTORCH_NPU_ALLOC_CONF':'expandable_segments:True','PYTHONDONTWRITEBYTECODE':'1',
     'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
ALLOCATION='/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json'


def require(ok,reason):
    if not ok:raise ValueError(reason)


def path(value):
    p=Path(value)
    require(p.is_absolute() and '..' not in p.parts and not any(c in str(p) for c in ',\n\r'), 'unsafe mount path')
    require(not any(q.is_symlink() for q in (p,*p.parents)),'symlink mount path')
    return str(p)


def contract(plan,plan_path,pin,review,attempt):
    require(type(attempt) is int and attempt>0,'invalid attempt')
    require(re.fullmatch('[0-9a-f]{64}',pin) is not None,'invalid plan SHA')
    require(type(plan['chip']) is int and plan['chip'] in range(8),'invalid chip')
    name='nga-final-'+pin[:20]+'-a'+str(attempt)
    root=path(plan['closure']['root']);out=path(plan['out']);rd=path(plan['round_dir'])
    require(out!=rd,'output and round must differ')
    # Round directory only exposes the frozen FINAL as a read-only file; its
    # test-log/reservation directories must remain writable for transactions.
    mounts={out:True,rd:True,root:False,path(plan['model']):False}
    if plan['adapter']:mounts[path(plan['adapter'])]=False
    entries=[plan['final'],plan['dataset_manifest'],plan['base_inventory'],plan['eligibility'],review,
             *plan['evidence'].values()]
    if plan['adapter_inventory']:entries.append(plan['adapter_inventory'])
    for entry in entries:mounts[path(entry['path'])]=False
    mounts[path(plan_path)]=False
    data=Path(plan['dataset_manifest']['path']).parent
    for suite,split,variant in [('decision-v7','train',False),('decision-v7','calibration',False),
            ('decision-v7','test',False),('decision-v7','test',True),
            ('transfer-v4','test',False),('transfer-v4','test',True)]:
        mounts[path(data/suite/(split+('.variants' if variant else '')+'.jsonl'))]=False
    # Writable outputs may never overlay a frozen model/code root. File mounts
    # beneath the writable round directory intentionally protect input evidence.
    for writable in (out,rd):
        for frozen in (root,plan['model'],plan['adapter']):
            if frozen is None:continue
            a,b=Path(writable),Path(frozen)
            require(a!=b and not a.is_relative_to(b) and not b.is_relative_to(a),'writable/frozen mount overlap')
    cmd=['-B','-P',root+'/r3_code/r3_final_driver.py','--plan',path(plan_path),'--sha256',pin,
         '--review',path(review['path']),'--review-sha256',review['sha256'],'--attempt',str(attempt)]
    devices=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci'+str(plan['chip'])]
    return {'name':name,'image':plan['image'],'cmd':cmd,'mounts':mounts,'devices':devices,'environment':ENV.copy()}


def command(spec):
    argv=['docker','run','-d','--pull=never','--name',spec['name'],'--network=none','--shm-size','64g',
          '--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
    # Parents first; nested read-only input files override writable parents.
    for source,rw in sorted(spec['mounts'].items(),key=lambda x:(len(Path(x[0]).parts),x[0])):
        argv+=['--mount','type=bind,src='+source+',dst='+source+('' if rw else ',readonly')]
    argv+=['--mount','type=bind,src=/usr/local/Ascend/driver,dst=/usr/local/Ascend/driver,readonly']
    for dev in spec['devices']:argv+=['--device',dev]
    for key,value in sorted(spec['environment'].items()):argv+=['-e',key+'='+value]
    return argv+['--entrypoint','python3',spec['image'],*spec['cmd']]


def verify_observation(spec,observed,container_id=None):
    require(observed is not None,'retained container observation missing')
    if container_id is not None:require(observed['Id']==container_id,'container generation changed')
    require(observed['Name'].lstrip('/')==spec['name'] and observed['Image']==spec['image'],'container identity differs')
    host=observed['HostConfig'];config=observed['Config']
    require(host.get('AutoRemove') is False and host.get('NetworkMode')=='none','container lifecycle/network differs')
    require(not host.get('Privileged',False),'privileged container refused')
    require(config.get('Entrypoint')==['python3'] and config.get('Cmd')==spec['cmd'],'container command differs')
    require({x['PathOnHost'] for x in host.get('Devices',[])}==set(spec['devices']),'container devices differ')
    expected={**spec['mounts'],'/usr/local/Ascend/driver':False}
    mounts=observed.get('Mounts',[])
    require(len(mounts)==len(expected),'container mount count differs')
    require(all(x.get('Type')=='bind' and x.get('Source')==x.get('Destination')
                and x['Source'] in expected and x.get('RW') is expected[x['Source']] for x in mounts),
            'container mounts differ')
    require(len({x['Destination'] for x in mounts})==len(expected),'duplicate mount destination')
    env=dict(item.split('=',1) for item in config.get('Env',[]))
    require(all(env.get(k)==v for k,v in spec['environment'].items()),'container environment differs')
    return observed


def reconcile_exit(observed,marker,*,plan_sha256,attempt):
    """Only actual retained exit permits creating missing terminal evidence.

    An exit zero without a driver marker is NOT success. The supervisor must
    preserve container exit code separately and retain the run for diagnosis.
    """
    state=observed['State']
    require(state.get('Status') in ('exited','dead'),'container has not exited')
    require(observed['HostConfig'].get('AutoRemove') is False,'container must be retained')
    code=state['ExitCode'];require(type(code) is int,'invalid container exit code')
    if marker is not None:
        require(marker.get('plan_sha256')==plan_sha256 and marker.get('attempt')==attempt,'terminal identity differs')
        if marker.get('source')=='retained-container-exit-missing-driver-marker':
            require(marker.get('container_id')==observed['Id'] and marker.get('container_exit_code')==code
                    and marker.get('exit_code')==(code if code else 125)
                    and marker.get('publication_complete') is False,'reconciled terminal differs')
            return marker
        require(marker.get('exit_code')==code,'driver/container exit disagreement')
        require(marker.get('publication_complete') is (code==0),'terminal publication state differs')
        return marker
    return {'exit_code':code if code else 125,'container_exit_code':code,'attempt':attempt,
            'plan_sha256':plan_sha256,'source':'retained-container-exit-missing-driver-marker',
            'container_id':observed['Id'],'finished_utc':state.get('FinishedAt'),
            'publication_complete':False,'scientific_acceptance':False}
