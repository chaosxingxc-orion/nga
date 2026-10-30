#!/usr/bin/env python3
"""E24 CPU controller: audit public dependency, claim chip, launch supplement and join."""
import argparse
import fcntl
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


def sibling(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

v=sibling('verify_reference_openjev');f=sibling('openjev_reference_finish')


def docker(method,path,value=None):
    c=http.client.HTTPConnection('localhost',timeout=30)
    c.sock=socket.socket(socket.AF_UNIX);c.sock.settimeout(30);c.sock.connect('/var/run/docker.sock')
    try:
        c.request(method,path,body=json.dumps(value).encode() if value is not None else None,
                  headers={'Content-Type':'application/json'})
        r=c.getresponse();data=r.read()
        v.require(r.status<300,'Docker operation failed: '+str(r.status)+' '+path)
        return json.loads(data) if data else None
    finally:c.close()


def dependency(entry,out):
    config=v.load(entry['public_config']);run=Path(config['out']);receipt=v.load(run/'LAUNCH_RECEIPT.json')
    info=docker('GET','/containers/'+config['container']+'/json')
    state=f.inspect_state(info,receipt,config);complete=f.completion_state(run,v.sha(entry['public_config']))
    if state!='exited':return None
    v.require(complete=='ready','Exited public inference has no successful terminal')
    audit=v.verify(entry['public_config'])
    v.atomic(out/(entry['name']+'-PUBLIC_AUDIT.json'),audit)
    v.require(f.inspect_state(docker('GET','/containers/'+config['container']+'/json'),receipt,config)=='exited',
              'Public container changed during audit')
    return info


def claim_launch(entry,previous,out):
    config_path=Path(entry['supplement_config']);c=v.load(config_path);run=Path(c['out'])
    old=v.load(entry['public_config']);chip=c['physical_chip'];device='/dev/davinci'+str(chip)
    v.require(chip==old['physical_chip'] and c['image']==previous['Image'],'Wrong inherited chip/image')
    v.require(not (run/'LAUNCH_RECEIPT.json').exists(),'Existing supplementary launch requires reconciliation')
    for path,expected in c['files'].items():v.require(v.sha(path)==expected,'Frozen supplement file changed')
    allocation=Path('/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json')
    with Path(str(allocation)+'.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);a=v.load(allocation)
        for obj in docker('GET','/containers/json'):
            live=docker('GET','/containers/'+obj['Id']+'/json')
            v.require(not any(d['PathOnHost']==device for d in live['HostConfig'].get('Devices') or []),'Live device conflict')
        owners=[x for x in a['allocation'] if x['chip']==chip];free=[x for x in a['free'] if x['chip']==chip]
        v.require((len(owners)==1 and owners[0]['run']=='reference_inference/'+Path(old['out']).name)
                  or (not owners and len(free)==1),'Chip ownership changed')
        now=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        a['allocation']=[x for x in a['allocation'] if x['chip']!=chip]
        a['free']=[x for x in a['free'] if x['chip']!=chip]
        a['allocation'].append({'chip':chip,'owner':'E24 OpenJev original test supplement',
            'run':'reference_inference/'+run.name,'claimed_utc':now,
            'release_when':'supplement exited and independent join checked'})
        a.update(updated_utc=now,updated_by='E24 dependency controller');v.atomic(allocation,a)
        host={k:previous['HostConfig'][k] for k in ('Binds','NetworkMode','ShmSize','Ulimits','Devices') if k in previous['HostConfig']}
        spec={'Image':c['image'],'Cmd':['bash',str(run/'evaluate.sh')],
              'Entrypoint':previous['Config']['Entrypoint'],'Env':previous['Config']['Env'],
              'WorkingDir':'/tmp','HostConfig':host}
        created=docker('POST','/containers/create?name='+c['container'],spec)
        info=docker('GET','/containers/'+created['Id']+'/json')
        v.atomic(run/'LAUNCH_RECEIPT.json',{'container_id':info['Id'],'image':info['Image'],
            'command':info['Config']['Cmd'],'entrypoint':info['Config']['Entrypoint'],
            'config_sha256':v.sha(config_path),'wrapper_sha256':v.sha(run/'evaluate.sh'),'utc':now})
        v.atomic(run/'TRANSFER_EVIDENCE.json',{'previous_container':previous['Id'],'previous_exit':0,
            'public_audit_sha256':v.sha(out/(entry['name']+'-PUBLIC_AUDIT.json')),'chip':chip,'utc':now})
        docker('POST','/containers/'+created['Id']+'/start')
        return info['Id']


def finish(entry,out):
    c=v.load(entry['supplement_config']);run=Path(c['out']);receipt=v.load(run/'LAUNCH_RECEIPT.json')
    info=docker('GET','/containers/'+c['container']+'/json')
    state=f.inspect_state(info,receipt,c);complete=f.completion_state(run,v.sha(entry['supplement_config']))
    if state!='exited':return False
    v.require(complete=='ready','Exited supplement lacks successful terminal')
    with (out/'audit.log').open('ab') as stream:
        subprocess.run([sys.executable,'-P',str(Path(__file__).with_name('join_openjev_original_test.py')),
                        '--plan',entry['join_plan']],stdout=stream,stderr=subprocess.STDOUT,check=True)
    result=v.load(Path(v.load(entry['join_plan'])['out'])/'JOIN_COMPLETE.json')
    v.require(result['rc']==0,'Join failed')
    return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    plan=v.load(args.plan);out=Path(plan['out']);lock=(out/'driver.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'QUEUE_COMPLETE.json').exists() or (out/'STATUS.json').exists():
        lock.close();raise ValueError('Queue restart needs reviewed continuation')
    for path,expected in plan['files'].items():v.require(v.sha(path)==expected,'Queue frozen file changed')
    states={e['name']:{'stage':'waiting_public'} for e in plan['entries']};rc=1
    try:
        while any(s['stage'] not in ('complete','failed') for s in states.values()):
            for path,expected in plan['files'].items():v.require(v.sha(path)==expected,'Queue frozen file changed during execution')
            for entry in plan['entries']:
                state=states[entry['name']]
                try:
                    if state['stage']=='waiting_public':
                        previous=dependency(entry,out)
                        if previous is not None:
                            state.update(stage='supplement',container_id=claim_launch(entry,previous,out))
                    elif state['stage']=='supplement' and finish(entry,out):state['stage']='complete'
                except Exception as exc:
                    state.update(stage='failed',error_type=type(exc).__name__)
                    v.atomic(out/(entry['name']+'-FAILED.json'),{'error':str(exc),'type':type(exc).__name__,
                        'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
            snapshot={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'entries':states,
                      'progress':sum(s['stage']=='complete' for s in states.values()),'total':len(states),'chips':0}
            v.atomic(out/'STATUS.json',snapshot)
            (out/'digest.md').write_text(snapshot['utc']+'\n'+'\n'.join(name+': '+state['stage'] for name,state in states.items())+'\n')
            with (out/'heartbeat.log').open('a') as stream:stream.write(json.dumps(snapshot)+'\n')
            if any(s['stage'] not in ('complete','failed') for s in states.values()):time.sleep(15)
        rc=0 if all(s['stage']=='complete' for s in states.values()) else 1
    finally:
        v.atomic(out/'QUEUE_COMPLETE.json',{'rc':rc,'entries':states,'scope':'Original-test supplement and verified join; flags require review'})
        lock.close()
    if rc:raise SystemExit(rc)


if __name__=='__main__':main()
