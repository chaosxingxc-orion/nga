import ast,copy,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import typed_openjev_inference as d
import verify_typed_openjev as v
import prepare_typed_openjev as launch
import test_typed_openjev_preflight as f
compile_request=f.compile_request;candidate_prompts=f.candidate_prompts
from jev.api import format_response

def fixture():
    raw=d.synthetic();raw.update(id='fixture',workflow='fixture',split='test');fields=d.encode(raw,f.Tokenizer(),compile_request,candidate_prompts);prob={};z={};gold={}
    for n,q in d.request(raw)['questions'].items():
        ks=d.keys(q);vals=list(range(len(ks)));z[n]=dict(zip(ks,vals));prob[n]=dict(zip(ks,d.probabilities(vals,2.)))
        gold[n]=dict(type=q['type'],probabilities=dict(zip(ks,[round(1/len(ks),3)]*len(ks))))
    raw['gold']=json.dumps(gold);records=compile_request(d.request(raw)['state'],d.request(raw)['questions'])
    pred=dict(probabilities=prob,logits=z,inference_temperature=2.,prompt_fields=fields,input_tokens=sum(sum(x['lengths']) for x in fields),wire_response=format_response(records,[list(prob[r['id']].values()) for r in records]))
    payload=dict(identity='identity',index=0,id=raw['id'],input_sha256=d.stamp(raw),request_sha256=d.stamp(d.request(raw)),seconds=.1,prediction=pred)
    return raw,pred,fields,dict(payload=payload,sha256=d.stamp(payload))
class ExecutionTests(unittest.TestCase):
    def test_driver_verifier_prediction(self):
        raw,pred,fields,env=fixture();d.receipt(env,raw,0,'identity',fields,2.);v.prediction(raw,pred,fields,2.,compile_request,format_response)
    def test_original_formula_both_temperatures(self):
        raw,pred,_,_=fixture();p=Path('/mnt/cephfs/xingchao/omni/datasets/jev/LocalLLaMA__typed-decisions/bench/score_with_jobs.py');self.assertEqual(d.sha(p),d.SCORER_SHA);node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='score_one');ns={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns)
        for temp in [1.,2.]:v.same(d.summarize([raw],[pred],temp,ns['score_one']),v.metric_panels([raw],[pred],temp))
    def test_independent_prompt_hashes(self):
        raw,_,fields,_=fixture();self.assertEqual(fields,v.prompt_fields(raw,f.Tokenizer(),compile_request,candidate_prompts))
    def test_forged_receipt_index(self):
        raw,_,fields,env=fixture();env['payload']['index']=1;env['sha256']=d.stamp(env['payload'])
        with self.assertRaisesRegex(ValueError,'Foreign'):d.receipt(env,raw,0,'identity',fields,2.)
    def test_wrong_temperature(self):
        raw,pred,fields,_=fixture()
        with self.assertRaisesRegex(ValueError,'temperature'):d.prediction(raw,pred,fields,1.)
    def test_nonfinite_logits(self):
        raw,pred,fields,_=fixture();pred['logits']['route']['a']=float('nan')
        with self.assertRaisesRegex(ValueError,'logits'):d.prediction(raw,pred,fields,2.)
    def test_wrong_wire(self):
        raw,pred,fields,_=fixture();pred['wire_response']['answers']['allow']['noul']=.123
        with self.assertRaisesRegex(ValueError,'native wire'):v.prediction(raw,pred,fields,2.,compile_request,format_response)
    def test_wrong_token_total(self):
        raw,pred,fields,_=fixture();pred['input_tokens']+=1
        with self.assertRaisesRegex(ValueError,'token count'):d.prediction(raw,pred,fields,2.)
    def test_config_change_after_read_terminal_original_hash(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t);p=out/'config.json';blob=json.dumps(dict(out=str(out),mode='probe')).encode();p.write_bytes(blob);original=Path.read_bytes
            def changed(path):
                b=original(path)
                if path==p:path.write_text('{}')
                return b
            with patch.object(Path,'read_bytes',changed),self.assertRaisesRegex(ValueError,'before execution'):d.run(p)
            term=json.loads((out/'probe-COMPLETE.json').read_text());self.assertEqual(term['rc'],1);self.assertEqual(term['config_sha256'],d.hashlib.sha256(blob).hexdigest())
    def test_actual_token_recorder(self):
        class Tensor:
            def __init__(self,rows):self.rows=rows
            def tolist(self):return self.rows
        class Tok:
            def __call__(self,*a,**kw):return dict(input_ids=Tensor([[1,2,0],[3,0,0]]),attention_mask=Tensor([[1,1,0],[1,0,0]]))
        rec=d.TokenRecorder(Tok());rec(['a','b'],padding=True,truncation=False,return_tensors='pt');self.assertEqual(rec.calls,[[[1,2],[3]]])
        with self.assertRaisesRegex(ValueError,'changed'):rec([],padding=True,truncation=True,return_tensors='pt')
    def test_live_chip_conflict(self):
        with patch.object(launch.subprocess,'check_output',return_value='id'),patch.object(launch,'inspect',return_value={'HostConfig':{'Devices':[{'PathOnHost':'/dev/davinci0'}]}}),self.assertRaisesRegex(ValueError,'conflict'):launch.live_conflict(0)
class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.runs=self.root/'runs';self.runs.mkdir();self.run=self.runs/'inference';self.run.mkdir();self.config=self.run/'config.json'
        self.c=dict(out=str(self.run),container='same',image='image',files={},mode='inference',physical_chip=0);self.config.write_text(json.dumps(self.c));(self.run/'run.sh').write_text('script')
        self.lc=dict(container_id='id',image='image',command=['bash','script'],entrypoint=None,config_sha256=launch.sha(self.config),wrapper_sha256=launch.sha(self.run/'run.sh'));(self.run/'LAUNCH_RECEIPT.json').write_text(json.dumps(self.lc))
        self.info=dict(Id='id',Image='image',Config=dict(Cmd=self.lc['command'],Entrypoint=None),HostConfig=dict(Devices=[dict(PathOnHost='/dev/davinci0')]),State=dict(Status='exited',ExitCode=137))
        (self.root/'CHIP-ALLOCATION.json').write_text(json.dumps(dict(allocation=[dict(chip=0,run='reference_inference/inference')],free=[])))
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
        (self.root/'CHIP-ALLOCATION.json').write_text(json.dumps(dict(allocation=[dict(chip=0,run='foreign')],free=[])))
        with self.assertRaisesRegex(ValueError,'allocation'):self.call()

if __name__=='__main__':unittest.main()
