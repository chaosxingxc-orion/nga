"""Registered resource adapter: queue and hardware checks inside allocation claim lock."""
import argparse,hashlib,json,types
from pathlib import Path

def load_module(ref):
    raw=Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('resource implementation changed')
    m=types.ModuleType('pinned_resource');m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m

def queue_guard(d,R):
    ref=d['queue'];q=R.load(ref['path'])
    if q.get('schema')!='native-ready-queue-v1' or q.get('allocation')!=d['allocation'] or q.get('writer_lock')!=d['allocation']+'.lock':raise ValueError('authoritative queue contract missing')
    if q.get('accepted_for_dispatch')is not True:raise ValueError('queue coverage not admitted')
    if q.get('coverage')=='chip_ready_tasks':
        if q.get('chips')!=[d['chip']] or any(type(x)is not int for x in q['chips']):raise ValueError('queue chip scope differs')
        # Trusted executable composition pins an independent admission; the
        # controller remains responsible for updating under the allocation lock.
        admission=d['queue'].get('admission');writer=q.get('writer')
        if not admission or not writer:raise ValueError('scoped queue admission/writer missing')
        if R.sha_bytes(R.read_bytes(admission['path']))!=admission['sha256'] or R.sha_bytes(R.read_bytes(writer['path']))!=writer['sha256']:raise ValueError('scoped queue authority changed')
        auth=R.load(admission['path'])
        if (auth.get('schema')!='native-chip-queue-admission-v1' or auth.get('accepted_for_dispatch')is not True
            or auth.get('scientific_acceptance')is not False or auth.get('allocation')!=d['allocation']
            or auth.get('writer_lock')!=q['writer_lock'] or auth.get('queue_path')!=ref['path']
            or auth.get('chips')!=q['chips'] or any(type(x)is not int for x in auth['chips'])
            or auth.get('writer')!=writer):raise ValueError('scoped queue admission differs')
    elif q.get('coverage')!='all_ready_tasks':raise ValueError('queue coverage not admitted')
    if type(q.get('generation'))is not int or q['generation']<1 or not isinstance(q.get('tasks'),list):raise ValueError('queue generation/tasks invalid')
    ids=[]
    for t in q['tasks']:
        if set(t)!={'id','state','chips'} or t['state'] not in ('preparing','ready','running','complete','blocked'):raise ValueError('queue task schema differs')
        if type(t['id'])is not str or not isinstance(t['chips'],list) or any(type(x)is not int for x in t['chips']):raise ValueError('queue task identity differs')
        ids.append(t['id'])
        if t['state']=='ready' and d['chip'] in t['chips'] and t['id']!=d['run']:raise ValueError('ready predecessor has priority')
    if len(ids)!=len(set(ids)):raise ValueError('queue duplicate task')
    if R.live_chip_conflict(d['chip'],None):raise ValueError('device not free')
    return {'queue_sha256':R.sha_bytes(R.read_bytes(ref['path'])),'queue_generation':q['generation'],'live_conflict':False}

def main():
    a=argparse.ArgumentParser();a.add_argument('op',choices=['claim','release']);a.add_argument('--plan',required=True);a.add_argument('--sha256',required=True);a.add_argument('--attempt',type=int,required=True);a.add_argument('--container-id');x=a.parse_args()
    raw=Path(x.plan).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=x.sha256 or x.attempt<1:raise ValueError('plan differs')
    d=json.loads(raw);R=load_module(d['modules']['resource_base']);root=Path(d['out'])/'host_attempts'/str(x.attempt)
    args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='registered native runtime',purpose='synthetic_long_dev',proof=str(root/('CLAIM.json' if x.op=='claim' else 'RELEASE.json')))
    if x.op=='claim':
        def guard_factory(_):
            def check(allocation):
                if Path(x.plan).read_bytes()!=raw:raise ValueError('plan changed in claim')
                return queue_guard(d,R)
            return check
        R.successor_guard=guard_factory;R.claim(args)
    else:
        args.container=d['container']+'-a'+str(x.attempt);args.container_id=x.container_id;args.claim=str(root/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
