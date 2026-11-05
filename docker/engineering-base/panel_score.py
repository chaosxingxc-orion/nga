"""Image-local bounded replay of pinned saved native panels; no model execution."""
import fcntl, hashlib, json, os, threading, time, traceback
from pathlib import Path
from collections import Counter
import importlib.util, sys

ROOT=Path(__file__).resolve().parent/'source/native'
_spec=importlib.util.spec_from_file_location('nga_panel_score_load',Path(__file__).resolve().parent/'panel_score_load.py');panel_score_load=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(panel_score_load)
def module(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/(name+'.py')); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
N=module('bev_native_runtime'); P=module('bev_native_protocol'); X=module('bev_native_panel_runner'); R=module('bev_native_cpu_replay_v1'); Q=module('bev_native_cpu_parallel_v1')
def require(v,msg):
    if not v: raise ValueError(msg)
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):
    with open(p) as f:return json.load(f)
def put(p,obj):
    p=Path(p);t=p.with_name(p.name+'.pending')
    with t.open('w') as f: json.dump(obj,f,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
    fd=os.open(p.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def path(s):
    p=Path(s);require(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'unsafe path');return p

def run(c,config_path):
    config_path=path(config_path); config_hash=sha(config_path); manifest_path=path(c['manifest']);require(sha(manifest_path)==c['manifest_sha256'],'manifest hash differs');m=read(manifest_path)
    require(set(m)=={'schema','population','records','receipts_sha256','model_sha256','plan_sha256','scope','model','engine'},'manifest fields differ')
    require(m['schema']=='native-panel-input-manifest-v1','manifest schema differs');pop=m['population'];out=path(c['output']);recordroot=path(m['records']);
    require(not out.is_relative_to(recordroot) and not recordroot.is_relative_to(out),'output overlaps records')
    for k in ('contract','items','gold','requests'):
        p=path(pop[k]['path']);require(not out.is_relative_to(p.parent) and not p.is_relative_to(out),'output overlaps input');require(sha(p)==pop[k]['sha256'],'input hash differs: '+k)
    options=Q.parallel_options({'workers':c['workers'],'chunk_size':c['chunk_size']})
    out.parent.mkdir(parents=True,exist_ok=True);lock=(out.parent/(out.name+'.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    owner={'schema':'native-panel-score-owner-v1','config_sha256':config_hash,'manifest_sha256':c['manifest_sha256'],'output':str(out)}
    if out.exists(): require(out.is_dir() and (out/'OWNER.json').is_file() and read(out/'OWNER.json')==owner,'output provenance differs')
    else: out.mkdir();put(out/'OWNER.json',owner)
    require(not (out/'EXIT.json').exists() or read(out/'EXIT.json')['exit_code']!=0,'output already completed')
    (out/'chunks').mkdir(exist_ok=True); started=time.monotonic();state={'phase':'admission','completed':0,'total':pop['count']};stop=threading.Event()
    heartbeat_lock=threading.Lock()
    def heartbeat():
        with heartbeat_lock: put(out/'heartbeat.json',{**state,'utc_seconds':time.time()})
    def beat():
        while not stop.wait(20): heartbeat()
    thread=threading.Thread(target=beat,daemon=True);thread.start();rc=1
    try:
        put(out/'RELAUNCH.json',{'config':str(config_path),'config_sha256':config_hash,'instruction':'Relaunch the same image and config with the same mounts.'});heartbeat()
        items=X.rows(pop['items']['path']);gold=X.rows(pop['gold']['path']);requests=X.rows(pop['requests']['path']);contract=read(pop['contract']['path']);P.validate_items(items)
        require(len(items)==len(gold)==len(requests)==pop['count'],'population incomplete');require(dict(Counter(x['kind'] for x in items))==pop['kinds'],'kind population differs')
        require(P.sha256_value(contract)==pop['contract_sha256'] and contract==P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=m['model_sha256'],runtime_protocol_sha256=pop['protocol_binding_sha256'],tau=contract['tau']),'contract differs')
        require(N.digest(requests)==pop['ordered_inputs_sha256'],'ordered requests differ')
        require({p.name for p in recordroot.iterdir()}=={f'{i:06d}' for i in range(len(items))},'record population differs')
        ref=R.VerifiedReference.create(N,{'path':str(ROOT/'bev_native_runtime.py'),'sha256':sha(ROOT/'bev_native_runtime.py')},{'root':str(ROOT),'files':{k:{'path':str(ROOT/'anyjev'/k),'sha256':v} for k,v in N.PINS.items()}})
        state['phase']='records';heartbeat()
        def chunk(start,end):
            result=[]
            for i in range(start,end):
                item,req,g=items[i],requests[i],gold[i];X.item_check(req,i,8192)
                require(req['request_sha256']==P.request_hash(item) and g==dict(i=i,qid=item['qid'],y=item['y'],request_sha256=P.request_hash(item)),'population join differs')
                dest=recordroot/f'{i:06d}';p,receipt_hash,_=panel_score_load.load_item(dest,req,{'model_sha256':m['model_sha256'],'contract_sha256':pop['contract_sha256']},N,ref,R)
                require(p['i']==i and p['qid']==item['qid'] and p['request_sha256']==req['request_sha256'] and p['input_sha256']==N.digest(req) and 'gold' not in p and 'y' not in p,'prediction join differs')
                result.append([dict(p,y=item['y']),receipt_hash])
            return start,result
        # Chunks are recomputed on resume: saved output is never trusted as input.
        preds=[];receipts=[]
        for start,batch in Q.ordered_chunks(chunk,len(items),**options):
            preds.extend(x[0] for x in batch);receipts.extend(x[1] for x in batch);state['completed']=len(preds);heartbeat()
        require(N.digest(receipts)==m['receipts_sha256'],'record receipts provenance differs');ref.check_sources()
        for k in ('contract','items','gold','requests'):require(sha(pop[k]['path'])==pop[k]['sha256'],'input changed: '+k)
        require(sha(manifest_path)==c['manifest_sha256'] and sha(config_path)==config_hash,'manifest or config changed')
        raw=P.summarise(items,preds,contract=contract,contract_sha256=pop['contract_sha256']);kinds={}
        for kind in ('choice','yes_no','score'):
            selected=[(i,p) for i,p in zip(items,preds) if i['kind']==kind];correct=sum(i['y']==p['first_index'] for i,p in selected);kinds[kind]=dict(n=len(selected),correct=correct,accuracy=correct/len(selected) if selected else None,metric_origin='NGA additive stratification')
        summary=dict(schema='native-config-panel-summary-v2',n=len(items),one_forward=dict(**raw['one_forward'],accuracy=raw['one_forward']['correct']/len(items)),by_type=kinds,adaptive='NOT_EVALUATED',scientific_acceptance=False,candidate_test_authority=False,plan_sha256=m['plan_sha256'],attempt=1,scope=m['scope'],model=m['model'],engine=m['engine'])
        put(out/'summary.json',summary);state['phase']='complete';heartbeat();put(out/'report.json',{'schema':'native-panel-score-report-v1','records':len(items),'receipts_sha256':N.digest(receipts),'summary_sha256':sha(out/'summary.json'),'config_sha256':config_hash,'manifest_sha256':c['manifest_sha256'],'cpu_only':True,'test_inference_rerun':False,'elapsed_seconds':time.monotonic()-started});rc=0
    except BaseException as e:
        put(out/'ERROR.json',{'error':str(e),'phase':state['phase'],'completed':state['completed'],'traceback':traceback.format_exc()});raise
    finally:
        stop.set();thread.join();put(out/'EXIT.json',{'exit_code':rc,'config_sha256':config_hash,'manifest_sha256':c['manifest_sha256'],'summary_sha256':sha(out/'summary.json') if rc==0 else None,'utc_seconds':time.time()});lock.close()
