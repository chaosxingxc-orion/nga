import copy,importlib.util,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import typed_nimble_inference as d
import verify_typed_nimble as v
import prepare_typed_nimble as launch
import test_typed_reference_nimble as fixtures

def fixture():
    raw=fixtures.row();raw['workflow']='fixture';raw['split']='test';qs=json.loads(raw['questions']);gold={};prob={};logits={};typed={};fields=[]
    for n,q in qs.items():
        ks=d.candidate_keys(q);vals=[.2,.8];prob[n]=dict(zip(ks,vals));logits[n]={k:math.log(p) for k,p in prob[n].items()};typed[n]=True if q['type']=='noul' else ks[-1]
        gold[n]={'type':q['type'],'probabilities':dict(zip(ks,[.333,.666]))}
        fields.append(dict(name=n,candidate_keys=ks,candidate_token_ids=[7,8],tokens=3,prompt_token_sha256=d.stamp([1,2,3],True)))
    raw['gold']=json.dumps(gold);pred=dict(probabilities=prob,logits=logits,typed_output=typed,inference_temperature=1.,prompt_fields=fields)
    payload=dict(index=0,id=raw['id'],identity='identity',input_sha256=d.stamp(raw),request_ordered_sha256=d.stamp(d.request(raw),True),prediction=pred,seconds=.1)
    return raw,pred,fields,dict(payload=payload,sha256=d.stamp(payload))

class ExecutionTests(unittest.TestCase):
    def test_config_change_after_read_keeps_original_terminal_hash(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t);path=out/'config.json'
            original=json.dumps(dict(out=str(out),mode='probe',files={})).encode();path.write_bytes(original)
            changed=json.dumps(dict(out=str(out),mode='probe',files={},changed=True)).encode()
            read_bytes=Path.read_bytes
            def read_then_change(p):
                value=read_bytes(p)
                if p==path:p.write_bytes(changed)
                return value
            with patch.object(Path,'read_bytes',read_then_change),self.assertRaisesRegex(ValueError,'Config changed before execution'):
                d.run(path)
            terminal=json.loads((out/'probe-COMPLETE.json').read_text())
            self.assertEqual(terminal['rc'],1)
            self.assertEqual(terminal['config_sha256'],d.hashlib.sha256(original).hexdigest())
            self.assertNotEqual(terminal['config_sha256'],d.sha(path))
            self.assertEqual(terminal['outputs'],{})
    def test_valid_receipt_and_independent_output(self):
        raw,pred,fields,e=fixture();d.receipt(e,raw,0,'identity',fields);v.prediction(raw,pred,fields)
    def test_foreign_rehashed_receipt(self):
        raw,pred,fields,e=fixture();e['payload']['index']=1;e['sha256']=d.stamp(e['payload'])
        with self.assertRaisesRegex(ValueError,'Foreign'):d.receipt(e,raw,0,'identity',fields)
    def test_resume_wrong_prompt(self):
        raw,pred,fields,e=fixture();fields=copy.deepcopy(fields);fields[0]['prompt_token_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Prompt'):d.receipt(e,raw,0,'identity',fields)
    def test_wrong_typed_boolean_rejected(self):
        raw,pred,fields,e=fixture();pred['typed_output']['b']='true'
        with self.assertRaisesRegex(ValueError,'Typed'):v.prediction(raw,pred,fields)
    def test_invalid_probabilities_rejected(self):
        raw,pred,fields,e=fixture();pred['probabilities']['a']['one']=float('nan')
        with self.assertRaisesRegex(ValueError,'probability'):v.prediction(raw,pred,fields)
    def test_independent_input_matches_native_adapter(self):
        raw,_,_,_=fixture();self.assertEqual(v.independent_input(raw),d.model_input(raw))
    def test_gold_rounding_original_formula(self):
        import ast
        raw,pred,_,_=fixture();path=Path('/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py');self.assertEqual(d.sha(path),d.SCORER_SHA)
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='score_one');ns={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        actual=d.score([raw],[pred],ns['score_one']);expected=v.metric_panels([raw],[pred]);v.same(actual,expected)
        self.assertNotEqual(expected['original_arithmetic_raw_readout']['brier'],(.2-1/3)**2+(.8-2/3)**2)
    def test_candidate_order_rejected(self):
        raw,pred,fields,_=fixture();pred['probabilities']['a']=dict(reversed(list(pred['probabilities']['a'].items())))
        with self.assertRaisesRegex(ValueError,'candidates'):v.prediction(raw,pred,fields)
    def test_loader_omission(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);c={k:str(p/k) for k in ['base','adapter','code','out','data','scorer','preregistration']}
            for k in ['base','adapter','code']:(p/k).mkdir()
            with self.assertRaisesRegex(ValueError,'loader'):v.dependencies(c)
    def test_live_chip_guard(self):
        info={'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci3'}]}}
        with patch.object(launch.subprocess,'check_output',return_value='id\n'),patch.object(launch,'inspect',return_value=info),self.assertRaisesRegex(ValueError,'Live device'):launch.live_conflict(3)
    def test_successful_resume_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);c={'out':str(p),'container':'same','image':'image','files':{},'mode':'inference'};cfg=p/'config.json';cfg.write_text(json.dumps(c));(p/'run.sh').write_text('script')
            lc={'container_id':'id','image':'image','command':['bash','script'],'entrypoint':None,'config_sha256':launch.sha(cfg),'wrapper_sha256':launch.sha(p/'run.sh')};(p/'LAUNCH_RECEIPT.json').write_text(json.dumps(lc))
            info={'Id':'id','Image':'image','Config':{'Cmd':lc['command'],'Entrypoint':None},'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci3'}]},'State':{'Status':'exited','ExitCode':0}}
            with patch.object(launch,'inspect',return_value=info),self.assertRaisesRegex(ValueError,'Successful or live'):launch.resume(cfg)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.runs=self.root/'runs';self.runs.mkdir();self.run=self.runs/'inference';self.run.mkdir();self.config=self.run/'config.json'
        self.c=dict(out=str(self.run),container='same',image='image',files={},mode='inference');self.config.write_text(json.dumps(self.c));(self.run/'run.sh').write_text('script')
        self.lc=dict(container_id='id',image='image',command=['bash','script'],entrypoint=None,config_sha256=launch.sha(self.config),wrapper_sha256=launch.sha(self.run/'run.sh'));(self.run/'LAUNCH_RECEIPT.json').write_text(json.dumps(self.lc))
        self.info=dict(Id='id',Image='image',Config=dict(Cmd=self.lc['command'],Entrypoint=None),HostConfig=dict(Devices=[dict(PathOnHost='/dev/davinci3')]),State=dict(Status='exited',ExitCode=137))
        (self.root/'CHIP-ALLOCATION.json').write_text(json.dumps(dict(allocation=[dict(chip=3,run='reference_inference/inference')],free=[])))
        (self.run/'inference-COMPLETE.json').write_text(json.dumps(dict(rc=1)));(self.run/'EXIT').write_text('rc=137 old');(self.run/'records').mkdir();(self.run/'records/000000.json').write_text('existing item')
    def call(self):
        with patch.object(launch,'ROOT',self.runs),patch.object(launch,'inspect',return_value=self.info),patch.object(launch.subprocess,'check_output',return_value=''),patch.object(launch.subprocess,'check_call') as start:
            launch.resume(self.config);return start
    def test_failed_resume_preserves_item_and_old_terminal(self):
        start=self.call();start.assert_called_once_with(['docker','start','id']);self.assertEqual((self.run/'records/000000.json').read_text(),'existing item');self.assertFalse((self.run/'EXIT').exists());archive=list(self.run.glob('resume-before-*'));self.assertEqual(len(archive),1);self.assertEqual((archive[0]/'EXIT').read_text(),'rc=137 old')
    def test_created_container_can_resume(self):
        self.info['State']=dict(Status='created',ExitCode=0);self.call().assert_called_once_with(['docker','start','id'])
    def test_wrong_device_cannot_resume(self):
        self.info['HostConfig']['Devices']=[dict(PathOnHost='/dev/davinci4')]
        with self.assertRaisesRegex(ValueError,'Resume container'):self.call()
    def test_successful_marker_cannot_resume_even_failed_exit(self):
        (self.run/'inference-COMPLETE.json').write_text(json.dumps(dict(rc=0)))
        with self.assertRaisesRegex(ValueError,'Successful terminal'):self.call()
    def test_wrong_owner_cannot_resume(self):
        (self.root/'CHIP-ALLOCATION.json').write_text(json.dumps(dict(allocation=[dict(chip=3,run='foreign')],free=[])))
        with self.assertRaisesRegex(ValueError,'allocation'):self.call()

if __name__=='__main__':unittest.main()
