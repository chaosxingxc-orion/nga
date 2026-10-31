"""Synthetic retained releases and restart handoff; no NPU access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('control_successor',HERE/'r3_control_resume_successor.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class Successor(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.previous=self.root/'previous'
        self.out=self.root/'restart';self.source.mkdir();self.previous.mkdir()
        self.plan={'schema':'r3-engineering-k1-plan-v1','chip':0,'out':str(self.source),
                   'seed':2,'control_arm':'K1-QO','review_sha256':'PENDING'}
        self.write(self.source/'plan.json',self.plan)
        self.prior={'chip':2,'out':str(self.previous),'run':'previous','container':'prior',
                    'launcher':'/frozen/previous.py','scientific_acceptance':False,'test_read':False,
                    'schema':'r3-engineering-posttrain-execution-v1'}
        self.write(self.previous/'execution.json',self.prior)
        self.job={'id':'qo','source_plan':str(self.source/'plan.json'),'source_pin':S.P.R.identity(self.plan),
                  'source_step':3000,'after_eval_out':str(self.previous),
                  'after_execution_sha256':S.P.R.sha(self.previous/'execution.json'),'chip':2,'out':str(self.out)}
        checkpoint=self.source/'ckpt/step_003000.pt';checkpoint.parent.mkdir();checkpoint.write_bytes(b'fixture')
    def write(self,p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d))
    def actual_prior(self,rc=0):
        marker={'attempt':1,'exit_code':rc};self.write(self.previous/'ENGINEERING_EVAL_EXIT.json',marker)
        attempt=self.previous/'attempts/1';self.write(attempt/'EXIT.json',marker)
        self.write(attempt/'RELEASE.json',{'container_id':'id','exit_code':rc,'chip':2,'run':'previous','scientific_acceptance':False})
        self.write(attempt/'LAUNCH_RECEIPT.json',{'id':'id'})
        command=[S.sys.executable,'-P',self.prior['launcher'],'supervise','--plan',str(self.previous/'execution.json'),
                 '--sha256',self.job['after_execution_sha256'],'--attempt','1']
        self.write(self.previous/'SUPERVISOR_RECEIPT.json',{'command':command,'pid':42})
        return {'Id':'id','State':{'Status':'exited','ExitCode':rc}}
    def test_source_must_exit_successfully_before_dependency_or_prepare(self):
        with patch.object(S.S,'predecessor',return_value=None),patch.object(S.Q,'predecessor') as previous,patch.object(S.P,'prepare') as prepare:
            self.assertEqual(S.tick(self.job)['status'],'waiting_source_release');previous.assert_not_called();prepare.assert_not_called()
        with patch.object(S.S,'predecessor',return_value={'exit_code':7}),patch.object(S.P,'prepare') as prepare:
            self.assertEqual(S.tick(self.job)['status'],'source_failed');prepare.assert_not_called()
    def test_actual_predecessor_must_be_released_and_successful(self):
        with patch.object(S.S,'predecessor',return_value={'exit_code':0}):
            self.assertEqual(S.ready(self.job)['status'],'waiting_predecessor_release')
            actual=self.actual_prior(7)
            with patch.object(S.RESOURCE,'docker_inspect',return_value=actual):
                self.assertEqual(S.ready(self.job)['status'],'predecessor_failed')
            actual=self.actual_prior();actual['State']['Status']='running'
            with patch.object(S.RESOURCE,'docker_inspect',return_value=actual):
                with self.assertRaisesRegex(RuntimeError,'still live'):S.ready(self.job)
    def test_newer_predecessor_retry_blocks_old_terminal(self):
        self.actual_prior();p=self.previous/'SUPERVISOR_RECEIPT.json';d=S.load(p);d['command'][-1]='2';self.write(p,d)
        with patch.object(S.S,'predecessor',return_value={'exit_code':0}),patch.object(S.RESOURCE,'docker_inspect') as observe:
            self.assertEqual(S.ready(self.job)['status'],'waiting_predecessor_release');observe.assert_not_called()
    def test_partial_prepare_never_retries(self):
        intent=self.out.with_name(self.out.name+'.PREPARE_INTENT.json');self.write(intent,{'job':self.job})
        with patch.object(S.P,'prepare') as prepare:
            self.assertEqual(S.tick(self.job)['status'],'needs_repair');prepare.assert_not_called()
    def prepare_fake(self,*args):
        self.out.mkdir()
        self.write(self.out/'PREPARATION.json',{'source_plan':self.job['source_plan'],'source_plan_pin':self.job['source_pin']})
        self.write(self.out/'SOURCE.json',{'step':3000,'checkpoint':str(self.source/'ckpt/step_003000.pt')})
    def finalize_fake(self,*args):
        plan={'schema':'r3-engineering-k1-plan-v1','out':str(self.out),'chip':2,'launcher':'/frozen/next.py','review_sha256':'PENDING'}
        self.write(self.out/'plan.json',plan)
        return {'plan':str(self.out/'plan.json'),'plan_sha256':S.P.R.identity(plan),'deployable':True,'test_read':False,'scientific_acceptance':False}
    def test_prepare_then_handoff_same_tick_and_reentry_does_not_reprepare(self):
        with patch.object(S,'ready',return_value={'status':'ready'}),patch.object(S.P,'prepare',side_effect=self.prepare_fake) as prepare,\
             patch.object(S.P,'finalize',side_effect=self.finalize_fake),patch.object(S.subprocess,'run') as run,\
             patch.object(S.S,'tick',return_value={'status':'launch_requested'}) as handoff:
            self.assertEqual(S.tick(self.job)['status'],'launch_requested')
            self.assertEqual(S.tick(self.job)['status'],'launch_requested')
            prepare.assert_called_once();self.assertEqual(handoff.call_count,2);run.assert_called_once()
    def test_interrupted_finalization_never_duplicates(self):
        with patch.object(S,'ready',return_value={'status':'ready'}),patch.object(S.P,'prepare',side_effect=self.prepare_fake) as prepare,\
             patch.object(S.P,'finalize',side_effect=RuntimeError('interrupted')):
            with self.assertRaisesRegex(RuntimeError,'interrupted'):S.tick(self.job)
            self.assertEqual(S.tick(self.job)['status'],'needs_repair');prepare.assert_called_once()
    def test_predecessor_pin_change_refused_even_if_exit_is_success(self):
        self.write(self.previous/'execution.json',dict(self.prior,chip=3))
        with patch.object(S.S,'predecessor',return_value={'exit_code':0}),patch.object(S.P,'prepare') as prepare:
            with self.assertRaisesRegex(RuntimeError,'execution changed'):S.tick(self.job)
            prepare.assert_not_called()
    def test_after_start_observation_does_not_wait_for_or_relaunch_predecessor(self):
        with patch.object(S,'ready',return_value={'status':'ready'}),patch.object(S.P,'prepare',side_effect=self.prepare_fake),\
             patch.object(S.P,'finalize',side_effect=self.finalize_fake),patch.object(S.subprocess,'run'),patch.object(S.S,'tick'):
            S.tick(self.job)
        self.write(self.out/'SUCCESSOR_START_INTENT.json',{'previous':{}})
        with patch.object(S,'ready') as ready,patch.object(S.S,'tick',return_value={'status':'supervisor_live'}) as tick:
            self.assertEqual(S.tick(self.job)['status'],'supervisor_live');ready.assert_not_called();tick.assert_called_once()

    def test_queue_pin_tool_inventory_and_step_are_enforced(self):
        manifest=self.root/'queue.json'
        doc={'schema':'r3-control-resume-successor-v1','interval_seconds':600,
             'scientific_acceptance':False,'test_read':False,'jobs':[self.job],
             'tools':{str(HERE.resolve()/name):S.P.R.sha(HERE/name) for name in S.TOOLS}}
        self.write(manifest,doc)
        self.assertEqual(S.verify(manifest,S.P.R.sha(manifest)),doc)
        with self.assertRaisesRegex(RuntimeError,'queue changed'):S.verify(manifest,'0'*64)
        doc['jobs'][0]['source_step']=400;self.write(manifest,doc)
        with self.assertRaisesRegex(RuntimeError,'source step'):S.verify(manifest,S.P.R.sha(manifest))


class DynamicPredecessor(Successor):
    def dynamic(self, create_execution=True):
        producer=self.root/'producer';producer.mkdir()
        tools={}
        for name in ('r3_posttrain_eval_queue.py','r3_posttrain_eval_plan.py',
                     'r3_posttrain_eval_launcher.py','r3_resource_adapter.py'):
            file=producer/name;file.write_text('# '+name);tools[str(file)]=S.P.R.sha(file)
        closure=self.root/'closure';closure.mkdir();code=closure/'scientific.py';code.write_text('# science')
        config={'code':{'science':{'snapshot':str(code),'sha256':S.P.R.sha(code)}},
                'data':{str(self.root/'train.jsonl'):'f'*64},'mounts':[{'source':str(closure),'destination':'/code','readonly':True}],
                'evaluation_profile':'track_t_pt_r0',
                'command_template':['python3','-P','/entry.py','--model','<FROZEN_BASE_MODEL>',
                    '--adapter','<COMPLETED_ADAPTER>','--arm','K1-PT','--out','<FRESH_EVAL_OUTPUT>',
                    '--cache','<FRESH_IDENTITY_CACHE>']}
        self.write(closure/'manifest.json',config)
        training=self.root/'pt-training';training.mkdir()
        trainplan={'control_arm':'K1-PT','seed':3,'chip':2,'model':'/models/instruct','image_sha256':'image'}
        self.write(training/'plan.json',trainplan)
        row={'id':'pt-r0-s3','out':str(self.previous),'chip':2,'container':'prior',
             'training':str(training),'training_plan_sha256':S.P.R.sha(training/'plan.json')}
        queue={'schema':'r3-posttrain-queue-v1','test_read':False,'scientific_acceptance':False,
               'tools':tools,'closure':str(closure),'closure_sha256':S.P.R.sha(closure/'manifest.json'),'jobs':[row]}
        self.qpath=producer/'queue.json';self.write(self.qpath,queue)
        self.job.pop('after_execution_sha256')
        self.job['after_queue']={'path':str(self.qpath),'sha256':S.P.R.sha(self.qpath),'job_id':'pt-r0-s3'}
        if not create_execution:
            (self.previous/'execution.json').unlink();return
        spec={'training':str(training),'training_variant':{'training_plan_sha256':row['training_plan_sha256'],'arm':'k1-pt','seed':3},
              'model':trainplan['model'],'adapter':str(training/'adapter'),'image_sha256':'image',
              'evaluation_profile':'track_t_pt_r0','test_read':False,'scientific_acceptance':False,
              'code_mounts':config['mounts'],'readonly_data_mounts':list(config['data']),
              'files':{**config['data'],str(code):S.P.R.sha(code)}}
        replacements={'<FROZEN_BASE_MODEL>':spec['model'],'<COMPLETED_ADAPTER>':spec['adapter'],
                      '<FRESH_EVAL_OUTPUT>':str(self.previous/'results'),'<FRESH_IDENTITY_CACHE>':str(self.previous/'identity')}
        spec['command']=[replacements.get(x,x) for x in config['command_template']]
        self.write(self.previous/'plan.json',spec)
        frozen=self.previous/'execution-tools';frozen.mkdir()
        for name in ('r3_posttrain_eval_launcher.py','r3_resource_adapter.py'):
            (frozen/name).write_bytes((producer/name).read_bytes())
        self.prior.update(spec=str(self.previous/'plan.json'),spec_sha256=S.P.R.sha(self.previous/'plan.json'),
            launcher=str(frozen/'r3_posttrain_eval_launcher.py'),resource_adapter=str(frozen/'r3_resource_adapter.py'),
            tools={str(p):S.P.R.sha(p) for p in frozen.iterdir()})
        self.write(self.previous/'execution.json',self.prior)
        self.write(self.previous/'QUEUE_EXECUTION_PIN.json',{'sha256':S.P.R.sha(self.previous/'execution.json')})
    def repin_execution(self):
        self.prior['spec_sha256']=S.P.R.sha(self.previous/'plan.json')
        self.write(self.previous/'execution.json',self.prior)
        self.write(self.previous/'QUEUE_EXECUTION_PIN.json',{'sha256':S.P.R.sha(self.previous/'execution.json')})
    def test_dynamic_queue_waits_without_execution_or_data_read(self):
        self.dynamic(False)
        self.assertIsNone(S.predecessor_pin(self.job))
        with patch.object(S.S,'predecessor',return_value={'exit_code':0}),patch.object(S.Q,'predecessor') as actual:
            self.assertEqual(S.ready(self.job)['status'],'waiting_predecessor_execution');actual.assert_not_called()
    def test_complete_dynamic_execution_is_bound_to_original_template(self):
        self.dynamic();self.assertEqual(S.predecessor_pin(self.job),S.P.R.sha(self.previous/'execution.json'))
        # Dataset intentionally does not exist: this check reads only configuration/code.
        self.assertFalse((self.root/'train.jsonl').exists())
    def test_repinned_wrong_template_training_or_tool_refused(self):
        self.dynamic();path=self.previous/'plan.json';original=path.read_bytes()
        for field,value in [('command',['wrong']),('model','/wrong'),('evaluation_profile','track_kt'),('code_mounts',[])]:
            spec=S.load(path);spec[field]=value;self.write(path,spec);self.repin_execution()
            with self.subTest(field=field),self.assertRaises(RuntimeError):S.predecessor_pin(self.job)
            path.write_bytes(original);self.repin_execution()
        tool=self.previous/'execution-tools/r3_resource_adapter.py';tool.write_text('# changed')
        self.prior['tools'][str(tool)]=S.P.R.sha(tool);self.repin_execution()
        with self.assertRaisesRegex(RuntimeError,'execution tool changed'):S.predecessor_pin(self.job)
    def test_dynamic_queue_pin_and_execution_pin_changes_refused(self):
        self.dynamic();self.write(self.previous/'QUEUE_EXECUTION_PIN.json',{'sha256':'0'*64})
        with self.assertRaisesRegex(RuntimeError,'execution changed'):S.predecessor_pin(self.job)
        self.qpath.write_text(self.qpath.read_text()+' ')
        with self.assertRaisesRegex(RuntimeError,'producer queue changed'):S.predecessor_pin(self.job)


if __name__=='__main__':unittest.main()
