"""Pinned physical release policy for matched DEV; original locked transaction."""
import argparse,hashlib,json,types
from pathlib import Path

def need(v,s):
 if not v:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(ref):
 raw=Path(ref['path']).read_bytes();need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'source changed');m=types.ModuleType('resource');m.__file__=ref['path'];exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def guard(d,R,allocation):
 def pinned(ref):
  need(d['files'].get(ref['path'])==ref['sha256']==sha(ref['path']),'policy source');return json.loads(Path(ref['path']).read_bytes())
 q=pinned(d['queue']);need(q['schema']=='native-matched-resource-policy-v1' and q['scientific_acceptance']is False,'policy')
 need(q['chip']==d['chip']==6 and q['run']==d['run'] and q['allocation']==d['allocation'],'identity')
 R.validate_doc(allocation);free=[x for x in allocation['free'] if x['chip']==6];need(free==[q['free_entry']] and not any(x['chip']==6 for x in allocation['allocation']),'free lineage changed');need(allocation.get('pending_claims')==q['pending_claims'],'priority changed')
 p=q['predecessor'];v={k:pinned(ref) for k,ref in p.items()};old=v['plan'];cl=v['claim'];rel=v['release'];rec=v['receipt'];spec=v['launch_spec']
 need(old['schema']=='native-dev72-dual-shard-execution-v1' and old['chip']==6,'predecessor schema/chip')
 root=Path(old['out'])/'host_attempts/1'
 for k,n in [('claim','CLAIM.json'),('release','RELEASE.json'),('receipt','LAUNCH_RECEIPT.json'),('launch_spec','LAUNCH_SPEC.json')]:need(p[k]['path']==str(root/n),'predecessor path')
 need(rel['claim_sha256']==p['claim']['sha256'] and cl['run']==rel['run']==old['run'] and cl['chip']==rel['chip']==6,'release binding')
 need(free[0]['previous_run']==old['run'] and free[0]['release_evidence']==p['release']['path'],'free origin')
 a=R.docker_inspect(old['container']+'-a1');need(a and a['Id']==rec['container_id']==rel['container_id'] and a['Image']==old['image'],'container identity')
 need(a['State']['Status']=='exited' and a['State']['Running']is False and a['State']['ExitCode']==rel['exit_code'],'physical exit')
 need(a['State']['StartedAt']==rel['container_started_at'] and a['State']['FinishedAt']==rel['container_finished_at'],'generation')
 need(rec['plan_sha256']==spec['plan_sha256']==p['plan']['sha256'] and a['Config']['Cmd']==rec['command']==spec['command'][spec['command'].index(old['image'])+1:],'command')
 need(a['HostConfig']['AutoRemove']is False and a['RestartCount']==0,'retained generation')
 expected=sorted('/dev/'+x for x in ('davinci_manager','devmm_svm','hisi_hdc','davinci6'))
 need(sorted(x.get('PathOnHost') for x in a['HostConfig']['Devices'])==expected and all(x.get('PathInContainer')==x.get('PathOnHost') for x in a['HostConfig']['Devices']) and a['HostConfig'].get('Privileged')is False and a['HostConfig'].get('NetworkMode')=='none','retained device/isolation')
 for ref in q['priority_refs']:pinned(ref)
 need(q['selection'] and not R.live_chip_conflict(6,None),'selection/conflict')
 return {'schema':q['schema'],'physical_release_verified':True,'global_empty_queue_asserted':False,'free_entry':free[0]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('op',choices=['claim','release']);ap.add_argument('--plan',required=True);ap.add_argument('--sha256',required=True);ap.add_argument('--attempt',type=int,required=True);ap.add_argument('--container-id');a=ap.parse_args();raw=Path(a.plan).read_bytes();need(hashlib.sha256(raw).hexdigest()==a.sha256 and a.attempt==1,'plan/attempt');d=json.loads(raw);R=load(d['modules']['resource_base']);h=Path(d['out'])/'host_attempts/1'
 args=types.SimpleNamespace(alloc=d['allocation'],run=d['run'],chip=d['chip'],owner='native matched performance',purpose='matched DEV6516 native collect paths',proof=str(h/('CLAIM.json' if a.op=='claim' else 'RELEASE.json')))
 if a.op=='claim':
  def factory(_):
   def check(allocation):need(Path(a.plan).read_bytes()==raw,'plan changed in lock');return guard(d,R,allocation)
   return check
  R.successor_guard=factory;R.claim(args)
 else:args.container=d['container']+'-a1';args.container_id=a.container_id;args.claim=str(h/'CLAIM.json');R.release(args)
if __name__=='__main__':main()
