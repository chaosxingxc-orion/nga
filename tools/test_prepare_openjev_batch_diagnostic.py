"""CPU tests for E37 preparation contracts; no Docker/NPU or resource mutation."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


p = module('prepare_e37', 'prepare_openjev_batch_diagnostic.py')
q = module('queue_helpers_e37', 'jeval_reference_queue.py')
diag = module('diagnostic_e37', 'openjev_batch_diagnostic.py')


def spec(out):
    return dict(Image=q.IMAGE, Cmd=['bash', 'historical.sh'], Entrypoint=['native-entrypoint'],
        Env=['ASCEND_RT_VISIBLE_DEVICES=0'], HostConfig=dict(
            Binds=['/mnt/cephfs:/mnt/cephfs'], Devices=[dict(PathOnHost='/dev/davinci1',
            PathInContainer='/dev/davinci1', CgroupPermissions='rwm')], NetworkMode='host', ShmSize=4096))


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.out = self.root / 'run'; self.out.mkdir()
        self.allocation = self.root / 'ALLOCATION.json'
        self.config = self.root / 'source' / 'config.json'; self.config.parent.mkdir()
        q.atomic(self.config, {'physical_chip': 1})
        q.atomic(self.config.parent / 'NPU_SPEC.json', spec(self.out))
        self.s = p.spec_for(spec(self.out), 0, self.out, 'nga-e37-test')
        q.atomic(self.out / 'NPU_SPEC.json', self.s)
        (self.out / 'run.sh').write_text('wrapper')
        shutil.copy2(Path(__file__).with_name('openjev_batch_diagnostic.py'), self.out)
        self.plan = dict(out=str(self.out), image=q.IMAGE, physical_chip=0, logical_device='npu:0',
            allocation=str(self.allocation), candidate_batch_admission=False, files={},
            container='nga-e37-test', container_spec=str(self.out / 'NPU_SPEC.json'),
            source_config=str(self.config), wrapper=str(self.out / 'run.sh'),
            selection={'selected':[{'index':9027,'role':'boundary'}]})
        self.path = self.out / 'plan.json'; q.atomic(self.path,self.plan)
        q.atomic(self.out/'PARENT_REVIEW.json',{'approved_plan_sha256':q.sha(self.path)})
        q.atomic(self.allocation,{'allocation':[],'free':[{'chip':0}]})
        self.d=None; self.calls=[]
        self.stack=[]
        for name,value in [('ROOT',self.root),('ALLOCATION',self.allocation)]:
            patcher=patch.object(p,name,value);patcher.start();self.addCleanup(patcher.stop)
        for name,value in [('helper',lambda _:q),('host',lambda _:None),('docker_host',lambda _:None),('preparation_binding',lambda *a:None),('free_now',lambda *a,**k:None)]:
            patcher=patch.object(p,name,value);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(q,'inspect',lambda _:self.d);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(q,'docker',self.docker);patcher.start();self.addCleanup(patcher.stop)

    def docker(self, method, path, value=None):
        self.calls.append((method,path))
        if '/create?' in path:
            self.d=dict(Id='container1',Image=q.IMAGE,Config={k:value[k] for k in ['Cmd','Entrypoint','Env','Labels']},
                HostConfig=copy.deepcopy(value['HostConfig']),State=dict(Status='created',ExitCode=0,FinishedAt='time0'))
        elif path.endswith('/start'):self.d['State']['Status']='running'

    def start(self):return p.launch(self.path)

    def interrupted(self, rc=137):
        self.start();self.d['State']=dict(Status='exited',ExitCode=rc,FinishedAt='time1')
        (self.out/'EXIT').write_text(f'rc={rc} utc=2026-10-31T00:00:00Z\n')
        q.atomic(self.out/'RESUME_REVIEW.json',dict(approved_plan_sha256=q.sha(self.path),container_id=self.d['Id'],
            finished_at='time1',exit_sha256=q.sha(self.out/'EXIT')))

    def item(self, name='9027_original_0.json'):
        folder=self.out/'items';folder.mkdir(exist_ok=True)
        value=dict(plan_sha256=q.sha(self.path),index=9027,mode='original',rep=0,profiled=False,
            request_sha256='request',prediction={'saved':True})
        q.atomic(folder/name,dict(payload=value,sha256=diag.stamp(value)))
        return folder/name

    def test_device_mapping_does_not_mutate_source(self):
        original=spec(self.out); result=p.spec_for(original,0,self.out,'nga-e37-test')
        self.assertEqual(original['HostConfig']['Devices'][0]['PathOnHost'],'/dev/davinci1')
        self.assertEqual(result['HostConfig']['Devices'][0]['PathOnHost'],'/dev/davinci0')
        self.assertIn('ASCEND_RT_VISIBLE_DEVICES=0',result['Env'])
        with self.assertRaises(ValueError):p.spec_for(original,6,self.out,'x')

    def test_visibility_or_privilege_rejected(self):
        for change in ['visible','privileged']:
            s=spec(self.out)
            if change=='visible':s['Env']=['ASCEND_RT_VISIBLE_DEVICES=1']
            else:s['HostConfig']['Privileged']=True
            with self.assertRaises(ValueError):p.spec_for(s,0,self.out,'x')

    def test_exact_empty_process_grammar(self):
        p.process_query('NPU ID : 0\nChip Count : 1\nNo process in device.\nChip ID : 0\n',0)
        for output in ['', 'No process in device.', 'NPU ID : 0\nChip Count : 1\nProcess id:123 Process name:python Process memory(MB):10\nChip ID : 0']:
            with self.assertRaises(ValueError):p.process_query(output,0)

    def test_zero_exit_with_process_query_stderr_rejected(self):
        # Exercise the real guard, restored underneath setUp's no-op patch.
        real = module('e37_real_guard', 'prepare_openjev_batch_diagnostic.py')
        result=subprocess.CompletedProcess([],0,
            stdout='NPU ID : 0\nChip Count : 1\nNo process in device.\nChip ID : 0\n',
            stderr='driver query returned incomplete data\n')
        with patch.object(q,'docker',return_value=[]),patch.object(real.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(ValueError,'stderr'):real.free_now(q,0)
        result.stderr=''
        with patch.object(q,'docker',return_value=[]),patch.object(real.subprocess,'run',return_value=result):
            real.free_now(q,0)

    def test_launch_claims_once_and_running_noop(self):
        self.assertEqual(self.start()['status'],'STARTED')
        self.assertEqual(self.start()['status'],'ALREADY_RUNNING')
        self.assertEqual(len(q.load(self.allocation)['allocation']),1)
        self.assertEqual(sum(path.endswith('/start') for _,path in self.calls),1)

    def test_terminal_failure_and_report_never_restarted(self):
        for name in ['COMPLETE.json','FAILURE.json','report.json']:
            (self.out/name).write_text('{}')
            with self.assertRaisesRegex(ValueError,'Terminal'):self.start()
            self.assertFalse(self.calls);(self.out/name).unlink()

    def test_unknown_container_without_intent_rejected(self):
        self.docker('POST','/create?',self.s)
        with self.assertRaisesRegex(ValueError,'Foreign'):self.start()

    def test_known_created_gap_recovers(self):
        q.atomic(self.out/'LAUNCH_INTENT.json',dict(plan_sha256=q.sha(self.path),spec_sha256=q.sha(self.out/'NPU_SPEC.json')))
        self.docker('POST','/create?',self.s)
        self.assertEqual(self.start()['status'],'STARTED')
        self.assertTrue((self.out/'LAUNCH_RECEIPT.json').exists())

    def test_changed_receipt_rejected(self):
        self.start();r=q.load(self.out/'LAUNCH_RECEIPT.json');r['container_id']='foreign';q.atomic(self.out/'LAUNCH_RECEIPT.json',r)
        with self.assertRaises(ValueError):self.start()

    def test_resource_conflict_rejected(self):
        q.atomic(self.allocation,{'allocation':[{'chip':0,'run':'foreign'}],'free':[]})
        with self.assertRaises(ValueError):self.start()
        self.assertFalse(self.calls)

    def test_exit137_requires_exact_review(self):
        self.interrupted();r=q.load(self.out/'RESUME_REVIEW.json');r['finished_at']='old';q.atomic(self.out/'RESUME_REVIEW.json',r)
        with self.assertRaisesRegex(ValueError,'generation'):p.launch(self.path,True)
        self.assertTrue((self.out/'EXIT').exists())

    def test_resume_preserves_items_and_archives_partial(self):
        self.interrupted();item=self.item();before=q.sha(item)
        partial=item.with_name('9027_chunk8_0.json.tmp');partial.write_text('{partial')
        result=p.launch(self.path,True)
        self.assertEqual(result['status'],'STARTED');self.assertEqual(q.sha(item),before)
        self.assertFalse((self.out/'EXIT').exists());self.assertFalse(partial.exists())
        self.assertEqual(len(list((self.out/'resume_history').glob('*/EXIT'))),1)
        self.assertEqual(len(list((self.out/'resume_history').glob('*/9027_chunk8_0.json.tmp'))),1)

    def test_business_failure_not_signal_resume(self):
        self.interrupted(1)
        with self.assertRaisesRegex(ValueError,'signal'):p.launch(self.path,True)

    def test_modified_receipt_fails_before_start(self):
        self.interrupted();item=self.item();value=q.load(item);value['payload']['prediction']={};q.atomic(item,value)
        with self.assertRaisesRegex(ValueError,'Receipt hash'):p.launch(self.path,True)
        self.assertEqual(self.d['State']['Status'],'exited')

    def test_unknown_item_and_symlink_rejected(self):
        item=self.item('foreign.json')
        with self.assertRaisesRegex(ValueError,'Unknown receipt'):self.start()
        item.unlink();target=self.root/'other';target.write_text('{}');item.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'Unknown receipt'):self.start()

    def test_wrapper_preserves_literal_paths(self):
        path=self.root/"quote ' and $literal";path.mkdir();script=path/'run.sh';script.write_text(p.wrapper(path))
        subprocess.run(['bash','-n',str(script)],check=True)
        self.assertIn('python3 -P',script.read_text());self.assertIn('2>&1',script.read_text())

    def complete(self):
        self.start();self.d['State']=dict(Status='exited',ExitCode=0,FinishedAt='completed')
        (self.out/'EXIT').write_text('rc=0 utc=2026-10-31T00:00:00Z\n')
        folder=self.out/'items';folder.mkdir()
        prediction=dict(answer={'type':'choice','choice':'a','probabilities':{'a':.75,'b':.25}},
                        native_probabilities={'a':.75,'b':.25},logits=[1.,0.],consumed_token_sha256=['a','b'])
        for mode,rep,profiled in [(m,r,False) for m in ['original','noop','chunk8'] for r in range(2)]+[('original',0,True),('chunk8',0,True)]:
            name=f'9027_{mode}_{rep}'+('_profiled' if profiled else '')+'.json'
            value=dict(plan_sha256=q.sha(self.path),index=9027,mode=mode,rep=rep,profiled=profiled,
                       request_sha256='request',prediction=prediction)
            q.atomic(folder/name,dict(payload=value,sha256=diag.stamp(value)))
        same=diag.comparison(prediction,prediction)
        report=dict(plan_sha256=q.sha(self.path),selection=self.plan['selection'],candidate_batch_admission=False,
            existing_e36_admission='failed; unchanged',diagnostic_valid=True,paired_denominator=1,paired_decision_flips=0,
            comparisons={'9027':{k:same for k in ['original_repeat','chunk_repeat','original_vs_chunk',
                'noop_repeat','original_vs_noop','original_hook_effect','chunk_hook_effect']}})
        q.atomic(self.out/'SELECTION.json',self.plan['selection']);q.atomic(self.out/'report.json',report)
        q.atomic(self.out/'COMPLETE.json',dict(rc=0,stage='completed',progress=8,total=8,plan_sha256=q.sha(self.path),
            outputs={name:q.sha(self.out/name) for name in ['SELECTION.json','report.json']}))

    def test_complete_checks_receipts_and_preserves_admission_false(self):
        self.complete();result=p.verify_complete(self.path)
        self.assertEqual(len(result['receipt_manifest']),8);self.assertTrue(result['diagnostic_valid'])
        self.assertFalse(result['candidate_batch_admission'])
        self.assertEqual(q.load(self.allocation)['allocation'][0]['run'],'reference_inference/run')

    def test_complete_rejects_missing_item(self):
        self.complete();(self.out/'items/9027_noop_0.json').unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):p.verify_complete(self.path)

    def test_complete_rejects_changed_arithmetic_even_rehashed_report(self):
        self.complete();report=q.load(self.out/'report.json');report['paired_decision_flips']=1
        q.atomic(self.out/'report.json',report)
        term=q.load(self.out/'COMPLETE.json');term['outputs']['report.json']=q.sha(self.out/'report.json')
        q.atomic(self.out/'COMPLETE.json',term)
        with self.assertRaisesRegex(ValueError,'arithmetic'):p.verify_complete(self.path)

    def test_complete_rejects_success_marker_before_actual_exit(self):
        self.complete();self.d['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'not successful'):p.verify_complete(self.path)

    def test_prepare_generated_closure_and_compile(self):
        target=self.root/'prepared';source=Path(__file__).parent
        eligibility={'items':[dict(index=9027,id='b',status='eligible',lengths=[4096]*30,max_tokens=4096)]}
        c=dict(physical_chip=1,files={},eligibility_report=str(self.config))
        prereg=source.parent/'experiments/OPENJEV-BATCH-DIAGNOSTIC-2026-10-30.md'
        request=self.root/'request.json';q.atomic(request,{'files':{}})
        with patch.object(p,'source_evidence',return_value=(c,eligibility,[self.config],{})):
            plan_path=p._prepare(source,prereg,self.config,self.root/'e36.json',target,'nga-e37-prepared',0,request)
        result=q.load(plan_path)
        self.assertFalse(result['candidate_batch_admission']);self.assertEqual(result['physical_chip'],0)
        self.assertEqual(result['source_physical_chip'],1);self.assertFalse(self.calls)
        for name in p.NAMES:self.assertIn(str(target/name),result['files'])
        for field in ['wrapper','launch','resume','container_spec','preregistration']:
            self.assertEqual(q.sha(result[field]),result['files'][result[field]])
        self.assertFalse(q.load(target/'PREPARATION_AUDIT.json')['resource_claimed'])
        self.assertEqual(q.load(self.allocation)['allocation'],[])


class CPUWorkflow(unittest.TestCase):
    docker = Guards.docker

    def setUp(self):
        Guards.setUp(self)
        self.real=module('e37_cpu_workflow','prepare_openjev_batch_diagnostic.py')
        for name,value in [('ROOT',self.root),('ALLOCATION',self.allocation),('helper',lambda _:q),
                           ('host',lambda _:None),('docker_host',lambda _:None),('free_now',lambda *a,**k:None)]:
            patcher=patch.object(self.real,name,value);patcher.start();self.addCleanup(patcher.stop)
        self.source=Path(__file__).parent
        self.prereg=self.source.parent/'experiments/OPENJEV-BATCH-DIAGNOSTIC-2026-10-30.md'
        self.weight=self.root/'weights.bin';self.weight.write_bytes(b'weight')
        self.c=dict(physical_chip=1,files={str(self.weight):q.sha(self.weight)},eligibility_report=str(self.config))
        q.atomic(self.config,self.c)
        self.e36=self.root/'e36.json';q.atomic(self.e36,dict(files=self.c['files']))
        self.target=self.root/'target';self.cpu=self.root/'cpu'
        self.selection={'items':[dict(index=9027,id='b',status='eligible',lengths=[4096]*30,max_tokens=4096)]}
        patcher=patch.object(q,'image_environment',return_value=['TORCH_DEVICE_BACKEND_AUTOLOAD=0'])
        patcher.start();self.addCleanup(patcher.stop)

    def request(self,verify=None):
        path=self.real.make_request(self.source,self.prereg,self.config,self.e36,self.target,'nga-e37-target',0,self.cpu,verify)
        q.atomic(self.cpu/'PARENT_REVIEW.json',{'approved_request_sha256':q.sha(path)})
        return path

    def completed_preparation(self):
        request=self.request();self.real.cpu_launch(request)
        self.d['State']=dict(Status='exited',ExitCode=0,FinishedAt='cpu-completed')
        with patch.object(q,'inspect',return_value=None),patch.object(self.real,'source_evidence',
            return_value=(self.c,self.selection,[self.config,self.e36,self.config.parent/'NPU_SPEC.json'],self.c['files'])):
            plan=self.real._prepare(self.cpu,self.cpu/'PREREGISTRATION.md',self.config,self.e36,
                self.target,'nga-e37-target',0,request)
        result=dict(plan=str(plan),plan_sha256=q.sha(plan),source_config_sha256=q.sha(self.config),
            e36_plan_sha256=q.sha(self.e36),full_closure_verified=True,launched=False,resource_claimed=False)
        q.atomic(self.cpu/'report.json',result)
        q.atomic(self.cpu/'COMPLETE.json',dict(rc=0,stage='completed',progress=1,total=1,request_sha256=q.sha(request),
            outputs={'report.json':q.sha(self.cpu/'report.json')}))
        (self.cpu/'EXIT').write_text('rc=0 utc=2026-10-31T00:00:00Z\n')
        return request,plan

    def test_request_does_not_read_weight_or_claim_chip(self):
        original=q.sha
        def short_only(path):
            if Path(path)==self.weight:raise AssertionError('host read model weights')
            return original(path)
        with patch.object(q,'sha',side_effect=short_only):request=self.request()
        self.assertEqual(q.load(request)['task'],'prepare')
        self.assertEqual(q.load(self.allocation)['allocation'],[])
        self.assertFalse(self.calls)
        for script in self.cpu.glob('*.sh'):subprocess.run(['bash','-n',str(script)],check=True)

    def test_cpu_launch_has_no_devices_and_no_allocation(self):
        request=self.request();result=self.real.cpu_launch(request)
        self.assertEqual(result['status'],'STARTED');self.assertEqual(q.devices(self.d),[])
        self.assertEqual(q.load(self.allocation)['allocation'],[])
        self.assertEqual(self.real.cpu_launch(request)['status'],'ALREADY_RUNNING')

    def test_cpu_spec_device_bypass_rejected(self):
        request=self.request();r=q.load(request);spec=q.load(r['container_spec'])
        spec['HostConfig']['Devices']=[dict(PathOnHost='/dev/davinci0',PathInContainer='/dev/davinci0',CgroupPermissions='rwm')]
        q.atomic(Path(r['container_spec']),spec);r['files'][r['container_spec']]=q.sha(r['container_spec'])
        q.atomic(request,r);q.atomic(self.cpu/'PARENT_REVIEW.json',{'approved_request_sha256':q.sha(request)})
        with self.assertRaisesRegex(ValueError,'no NPU'):self.real.cpu_launch(request)
        self.assertIsNone(self.d)

    def test_host_binding_never_reads_weights_and_requires_cpu_exit(self):
        _,plan=self.completed_preparation();original=q.sha
        def no_weights(path):
            if Path(path)==self.weight:raise AssertionError('host bulk read')
            return original(path)
        with patch.object(q,'sha',side_effect=no_weights):self.real.preparation_binding(q,plan,q.load(plan))
        self.d['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'actual state'):self.real.preparation_binding(q,plan,q.load(plan))

    def test_runtime_dependency_omission_cannot_be_exempted(self):
        _,plan=self.completed_preparation();value=q.load(plan);del value['files'][str(self.weight)]
        value['skip_files']=[str(self.weight)]
        with self.assertRaisesRegex(ValueError,'full dependency'):self.real.control_files(q,value)

    def test_preparation_report_plan_and_source_binding(self):
        _,plan=self.completed_preparation();report=q.load(self.cpu/'report.json');report['plan_sha256']='foreign'
        q.atomic(self.cpu/'report.json',report)
        terminal=q.load(self.cpu/'COMPLETE.json');terminal['outputs']['report.json']=q.sha(self.cpu/'report.json')
        q.atomic(self.cpu/'COMPLETE.json',terminal)
        with self.assertRaisesRegex(ValueError,'report differs'):self.real.preparation_binding(q,plan,q.load(plan))

    def test_changed_control_rejected_after_successful_cpu_task(self):
        _,plan=self.completed_preparation();(self.target/'openjev_batch_diagnostic.py').write_text('# changed')
        with self.assertRaisesRegex(ValueError,'Frozen file'):self.real.preparation_binding(q,plan,q.load(plan))

    def test_large_control_is_not_silently_hashed_on_host(self):
        control=self.root/'largecontrol';control.write_bytes(b'0'*(8*2**20+1))
        with self.assertRaisesRegex(ValueError,'too large'):self.real.small_frozen(q,{str(control):'digest'})

    def test_verify_request_needs_no_chip_or_host_probe(self):
        with patch.object(self.real,'host',side_effect=AssertionError('host check')),patch.object(self.real,'free_now',side_effect=AssertionError('NPU query')):
            request=self.request(verify=self.path)
        self.assertEqual(q.load(request)['task'],'verify')
        self.assertIsNone(q.load(request)['resource_check_utc'])

    def task_process(self,request):
        import socket
        self.d['Config']['Hostname']=socket.gethostname()
        patcher=patch.object(self.real,'in_cpu_container',return_value=True);patcher.start();self.addCleanup(patcher.stop)
        evidence=(self.c,self.selection,[self.config,self.e36,self.config.parent/'NPU_SPEC.json'],self.c['files'])
        old_inspect=q.inspect
        def inspect(name): return None if name == 'nga-e37-target' else self.d
        with patch.object(q,'inspect',side_effect=inspect),patch.object(self.real,'source_evidence',return_value=evidence),patch.object(self.real,'_prepare',wraps=self.real._prepare):
            # Test process runs in this isolated container; actual production task
            # additionally binds the real retained container's hostname.
            self.real.cpu_task(request)

    def test_cpu_task_prepares_and_publishes_terminal(self):
        request=self.request();self.real.cpu_launch(request)
        self.task_process(request)
        terminal=q.load(self.cpu/'COMPLETE.json');report=q.load(self.cpu/'report.json')
        self.assertEqual(terminal['rc'],0);self.assertTrue(report['full_closure_verified'])
        self.assertFalse(report['resource_claimed'])
        self.assertEqual(terminal['outputs']['report.json'],q.sha(self.cpu/'report.json'))
        self.assertEqual(q.load(self.target/'plan.json')['files'][str(self.weight)],q.sha(self.weight))

    def test_cpu_task_resumes_published_report_without_repreparing(self):
        request,plan=self.completed_preparation()
        report_before=q.sha(self.cpu/'report.json');plan_before=q.sha(plan)
        (self.cpu/'COMPLETE.json').unlink();(self.cpu/'EXIT').unlink()
        q.atomic(self.cpu/'TARGET_INTENT.json',dict(request=str(request),request_sha256=q.sha(request)))
        self.d['State']['Status']='running'
        with patch.object(self.real,'_prepare',side_effect=AssertionError('duplicate preparation')):
            self.task_process(request)
        self.assertEqual(q.sha(self.cpu/'report.json'),report_before);self.assertEqual(q.sha(plan),plan_before)
        self.assertEqual(q.load(self.cpu/'COMPLETE.json')['rc'],0)

    def test_cpu_task_preserves_partial_preparation_directory(self):
        request=self.request();self.real.cpu_launch(request)
        identity=dict(request=str(request),request_sha256=q.sha(request))
        q.atomic(self.cpu/'TARGET_INTENT.json',identity);self.target.mkdir()
        q.atomic(self.target/'PREPARATION_IDENTITY.json',identity)
        (self.target/'partial.txt').write_text('interrupted evidence')
        self.task_process(request)
        saved=list((self.cpu/'partial_preparations').glob('*/partial.txt'))
        self.assertEqual(len(saved),1);self.assertEqual(saved[0].read_text(),'interrupted evidence')
        self.assertEqual(q.load(self.cpu/'COMPLETE.json')['rc'],0)

    def test_cpu_task_refuses_foreign_partial_preparation(self):
        request=self.request();self.real.cpu_launch(request);self.target.mkdir()
        (self.target/'foreign').write_text('keep')
        with self.assertRaisesRegex(ValueError,'Unowned'):self.task_process(request)
        self.assertTrue((self.target/'foreign').exists());self.assertEqual(q.load(self.cpu/'COMPLETE.json')['rc'],1)

    def test_cpu_resume_publication_gap_preserves_report(self):
        request=self.request();self.real.cpu_launch(request)
        self.d['State']=dict(Status='exited',ExitCode=137,FinishedAt='interrupted')
        (self.cpu/'EXIT').write_text('rc=137 utc=2026-10-31T00:00:00Z\n')
        q.atomic(self.cpu/'report.json',{'published':'preserve'})
        before=q.sha(self.cpu/'report.json')
        q.atomic(self.cpu/'RESUME_REVIEW.json',dict(approved_plan_sha256=q.sha(request),container_id=self.d['Id'],
            finished_at='interrupted',exit_sha256=q.sha(self.cpu/'EXIT')))
        self.assertEqual(self.real.cpu_launch(request,True)['status'],'STARTED')
        self.assertEqual(q.sha(self.cpu/'report.json'),before)


if __name__=='__main__':unittest.main()
