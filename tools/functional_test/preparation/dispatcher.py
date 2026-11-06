#!/usr/bin/env python3
"""Conditional dispatcher; callbacks return JSON {status: pending|ready|failed}.
Start only after independent bounded review of this dispatcher and its graph.
"""
import argparse, fcntl, json, os, shlex, signal, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from assembler import STAGE, C, H

def callback(command):
 r=subprocess.run(command,check=True,text=True,capture_output=True,timeout=90)
 doc=json.loads(r.stdout); H.need(doc.get('status') in ('ready','pending','failed'),'invalid callback status')
 return doc

def identity(pid):
 # Parentheses in /proc/<pid>/stat comm can contain spaces and parentheses.
 try:
  stat=Path('/proc')/str(pid)/'stat'
  fields=stat.read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'start_ticks':int(fields[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
 except (OSError,ValueError,IndexError):
  return None

def step(graph, callbacks, start=None):
 start=start or launch
 statuses={}
 for member,node in graph['members'].items():
  if node['status']!='available': statuses[member]='unavailable';continue
  draft=Path(node['draft']); review=Path(node['review']); config=Path(node['config'])
  H.need(H.sha(draft)==node['draft_sha256'],'draft changed')
  c=H.read(draft); H.need(C.campaign_digest(c)==graph['campaign_sha256'] and c['member']==member and c['container']['chip']==node['chip'],'graph differs')
  H.need(node['dependencies'] and ('27B' if node['chip']<4 else 'K0') in node['dependencies'],'resource dependency differs')
  state=Path(c['host']['state_dir'])/member;state.mkdir(parents=True,exist_ok=True)
  marker=state/'SUPERVISOR-EXIT.json'; intent=state/'DISPATCH-INTENT.json'; receipt=state/'DISPATCH-START.json'
  if marker.exists():
   H.need(config.exists() and H.read(marker).get('config_sha256')==H.digest(H.read(config)),'supervisor marker differs')
   H.need(H.read(marker).get('exit_code')==0,'supervisor failed');statuses[member]='complete';continue
  if intent.exists():
   H.need(receipt.exists(),'need_reconcile: ambiguous supervisor start')
   rec=H.read(receipt); pid=rec.get('pid'); recorded=rec.get('process_identity')
   H.need(type(pid) is int and isinstance(recorded,dict) and identity(pid)==recorded,'need_reconcile: missing or uncertain supervisor identity')
   statuses[member]='started';continue
  if not review.exists(): statuses[member]='waiting-review';continue
  rv=H.read(review); H.need(rv.get('schema')=='rc1-trackk-review-v1' and rv.get('reviewed') is True and rv.get('config_sha256')==H.digest(c),'contradictory review')
  c['review']={'path':str(review),'sha256':H.sha(review)}
  waiting=False
  for dep in node['dependencies']:
   H.need(dep in callbacks,'missing readiness callback');result=callback([*callbacks[dep], '--chip', str(node['chip'])]);H.need(result['status']!='failed',dep+' dependency failed');waiting |= result['status']=='pending'
  if waiting: statuses[member]='waiting-dependency';continue
  H.validate(c,str(config)); C.validate(c)
  if config.exists(): H.need(H.read(config)==c,'config differs')
  else: H.save(config,c)
  H.save(intent,{'config_sha256':H.digest(c),'config':str(config)})
  result=start(str(config)); H.need(type(result.get('pid')) is int and result['pid']>0 and result.get('state_dir')==str(state),'supervisor start receipt differs')
  result['process_identity']=identity(result['pid']); H.need(result['process_identity'] is not None,'need_reconcile: started process identity unavailable')
  H.save(receipt,result);statuses[member]='started'
 return statuses

def launch(config):
 r=subprocess.run([sys.executable,'-P',str(STAGE/'supervisor.py'),'start','--config',config],check=True,text=True,capture_output=True,timeout=90)
 return json.loads(r.stdout)

def main():
 p=argparse.ArgumentParser();p.add_argument('--graph',required=True);p.add_argument('--callbacks',required=True);a=p.parse_args()
 graph_path=Path(a.graph).resolve(); graph=H.read(graph_path); callbacks=H.read(a.callbacks); root=graph_path.parent; expected=H.sha(graph_path)
 H.need(graph.get('schema')=='rc1-dispatch-graph-v1','graph schema'); H.need(set(callbacks)=={'K0','27B'} and all(isinstance(v,list) and v and all(isinstance(s,str) for s in v) for v in callbacks.values()),'callback config')
 with (root/'dispatcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); marker=root/'DISPATCH-EXIT.json';H.need(not marker.exists(),'terminal exists; reconcile')
  (root/'DISPATCH-RELAUNCH.txt').write_text(shlex.join([sys.executable,'-P',str(Path(__file__).resolve()),'--graph',str(graph_path),'--callbacks',str(Path(a.callbacks).resolve())])+'\n')
  lg=root/'dispatcher.log'; wake=[False]
  def event(*_): wake[0]=True
  signal.signal(signal.SIGUSR1,event)
  try:
   while True:
    H.need(H.sha(graph_path)==expected,'graph changed');status=step(graph,callbacks);H.log(lg,'heartbeat progress='+json.dumps(status,sort_keys=True))
    if all(x in ('complete','unavailable') for x in status.values()): H.save(marker,{'exit_code':0,'graph_sha256':expected});break
    wake[0]=False
    for _ in range(600):
     if wake[0]: break
     time.sleep(1)
  except BaseException as exc:
   H.log(lg,'failed '+str(exc));H.save(marker,{'exit_code':1,'graph_sha256':expected,'error':str(exc)});raise
if __name__=='__main__':main()
