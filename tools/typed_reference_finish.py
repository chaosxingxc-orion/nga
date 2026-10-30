#!/usr/bin/env python3
"""Detached CPU waiter and independent Typed Decisions artifact audit; never restarts inference."""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()


def atomic(path,value):
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.')
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.chmod(temp,0o644);os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def container_info(name, socket_path='/var/run/docker.sock'):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',name):raise ValueError('Invalid container name')
    connection=http.client.HTTPConnection('localhost',timeout=15)
    connection.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    connection.sock.settimeout(15);connection.sock.connect(socket_path)
    try:
        connection.request('GET','/containers/'+name+'/json')
        response=connection.getresponse()
        if response.status!=200:raise RuntimeError('Docker inspect HTTP '+str(response.status))
        return json.loads(response.read())
    finally:connection.close()


def inspect_state(info,receipt,config):
    if info['Id']!=receipt['container_id'] or info['Image']!=receipt['image'] or info['Image']!=config['image']:
        raise ValueError('Inference container identity/image differs')
    if info['Config']['Cmd']!=receipt['command'] or info['Config'].get('Entrypoint')!=receipt['entrypoint']:
        raise ValueError('Inference container command/entrypoint differs')
    devices={d['PathOnHost'] for d in info['HostConfig'].get('Devices') or []
             if re.fullmatch(r'/dev/davinci\d+',d['PathOnHost'])}
    if devices!={'/dev/davinci'+str(config['physical_chip'])}:raise ValueError('Inference device binding differs')
    state=info['State']
    if state['Status'] in ('running','created','restarting','paused'):return 'pending'
    if state['Status']!='exited' or state['ExitCode']!=0:raise ValueError('Inference container terminal failure')
    return 'exited'


def completion_state(run,config_hash):
    if (run/'ERROR.json').exists() or (run/'FAILED').exists():raise ValueError('Recorded inference failure')
    path=run/'inference-COMPLETE.json';wrapper=run/'EXIT'
    if wrapper.exists() and not re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?',wrapper.read_text()):
        raise ValueError('Wrapper failed or malformed, including missing inference terminal')
    if not path.exists():return 'pending'
    terminal=json.loads(path.read_text())
    if type(terminal.get('rc')) is not int or terminal['rc']!=0:raise ValueError('Inference terminal failed')
    if terminal.get('config_sha256')!=config_hash or terminal.get('stage')!='completed':raise ValueError('Inference terminal binding differs')
    if not wrapper.exists():return 'pending'
    if not re.fullmatch(r'rc=0 utc=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\n?',wrapper.read_text()):raise ValueError('Wrapper failed')
    if wrapper.stat().st_mtime_ns<path.stat().st_mtime_ns:raise ValueError('Stale wrapper')
    for name in ('report.json','PREFLIGHT.json','PROBE.json'):
        if terminal.get('outputs',{}).get(name)!=sha(run/name):raise ValueError('Inference output binding differs: '+name)
    return 'ready'


def publish_digest(out,run,info,status):
    """Bounded structured observation, not an inference completion certificate."""
    source=run/'STATUS.json'
    try:
        upstream=json.loads(source.read_text())
        fields={key:upstream.get(key) for key in ('utc','stage','progress','total',
                'questions_per_second_per_chip','chips','reserved_gib')}
        error=None
    except (OSError,ValueError) as exc:
        fields={};error=type(exc).__name__
    value={'observed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
           'container_status':info['State']['Status'],'finisher_stage':status['stage'],
           'inference_status':fields,'source':str(source),'observation_error':error}
    atomic(out/'digest.json',value)
    # Whitelist scalar fields and cap each rendering; no raw log or traceback.
    safe=lambda x:str(x).replace('\n',' ')[:100]
    line=(f"{value['observed_utc']} container={safe(value['container_status'])} "
          f"stage={safe(fields.get('stage'))} progress={safe(fields.get('progress'))}/{safe(fields.get('total'))} "
          f"q/s/chip={safe(fields.get('questions_per_second_per_chip'))} chips={safe(fields.get('chips'))} "
          f"reserved_GiB={safe(fields.get('reserved_gib'))} heartbeat_utc={safe(fields.get('utc'))}\n")
    (out/'digest.md').write_text(line+'Source: '+str(source)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());out=Path(plan['out']);lock=(out/'driver.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'FINISH_COMPLETE.json').exists():raise ValueError('Existing finisher terminal; inspect before retry')
    status={'stage':'verify_plan','progress':0,'total':2,'chips':0};stop=threading.Event()
    def heartbeat():
        while not stop.wait(15):
            snapshot={'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status};atomic(out/'STATUS.json',snapshot)
            with (out/'heartbeat.log').open('a') as f:f.write(json.dumps(snapshot)+'\n')
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        for path,h in plan['files'].items():
            if sha(path)!=h:raise ValueError('Finisher input changed: '+path)
        config=json.loads(Path(plan['config']).read_text());run=Path(config['out']);config_hash=sha(plan['config'])
        receipt=json.loads((run/'LAUNCH_RECEIPT.json').read_text())
        if receipt['config_sha256']!=config_hash:raise ValueError('Launch receipt config differs')
        status['stage']='waiting_for_inference_terminal_and_container_exit'
        while True:
            # GET only. No container mutations or NPU allocation occur in this process.
            info=container_info(config['container'])
            c=inspect_state(info,receipt,config)
            publish_digest(out,run,info,status)
            t=completion_state(run,config_hash)
            if c=='exited':
                if t!='ready':raise ValueError('Exited container lacks successful terminal/wrapper')
                break
            time.sleep(5)
        atomic(out/'INFERENCE_CONTAINER_EXIT.json',{'container_id':receipt['container_id'],'status':'exited','exit_code':0,
              'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        status.update(stage='independent_audit',progress=1)
        with (out/'audit.log').open('ab') as log:
            subprocess.run([sys.executable,'-P',plan['auditor'],'--config',plan['config'],'--out',str(out/'INDEPENDENT_AUDIT.json')],
                           stdout=log,stderr=subprocess.STDOUT,check=True)
        if completion_state(run,config_hash)!='ready' or inspect_state(container_info(config['container']),receipt,config)!='exited':
            raise ValueError('Completion changed during audit')
        for path,h in plan['files'].items():
            if sha(path)!=h:raise ValueError('Finisher input changed during audit: '+path)
        audit=json.loads((out/'INDEPENDENT_AUDIT.json').read_text())
        report={'rc':0,'status':'COMPLETED_SCOPED_REVIEW_REQUIRED' if audit['review_flags'] else 'COMPLETED_SCOPED',
                'inference_run':str(run),'config_sha256':config_hash,'review_flag_count':len(audit['review_flags']),
                'outputs':{n:sha(out/n) for n in ('INDEPENDENT_AUDIT.json','INFERENCE_CONTAINER_EXIT.json')},
                'scope':'Independent artifact and metric checks; flags require review; not Astra approval.'}
        atomic(out/'FINISH_COMPLETE.json',report);status.update(stage=report['status'],progress=2)
    except BaseException as exc:
        atomic(out/'FINISH_COMPLETE.json',{'rc':1,'stage':status['stage'],'error':str(exc)});status['stage']='failed';raise
    finally:
        stop.set();thread.join();atomic(out/'STATUS.json',{'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status})


if __name__=='__main__':main()
