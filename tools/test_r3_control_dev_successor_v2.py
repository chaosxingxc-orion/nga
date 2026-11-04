import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
def load(path):
    spec=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class ControlDevContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for src,dst in [('r3_control_dev_successor_v2.py','r3_control_dev_successor_v2.py'),
                        ('r3_formal_dev_successor.py','core_formal_dev_successor.py'),
                        ('r3_control_dev_resource_v2.py','r3_control_dev_resource_v2.py'),
                        ('r3_resource_adapter.py','core_resource_adapter.py')]:shutil.copyfile(ROOT/src,self.root/dst)
        self.G=load(self.root/'r3_control_dev_successor_v2.py');self.R=load(self.root/'r3_control_dev_resource_v2.py')
        previous=self.root/'pt';(previous/'attempts/1').mkdir(parents=True)
        self.target={'out':str(self.root/'qo'),'model':'/base'}
        self.previous={'out':str(previous),'run':'r3_runs/pt','container':'pt'}
        self.jobs={'pt_seed2':{'chip':3,'id':'pt_seed2','arm':'K1-PT','seed':2,'previous':{'kind':'control','job':'qo_seed2'},'plan':str(previous/'plan.json'),'raw_sha256':'raw','canonical_sha256':'canonical'},
                   'qo_seed2':{'chip':3,'id':'qo_seed2','arm':'K1-QO','seed':2,'raw_sha256':'qo_raw'}}
        ref=lambda path,pin='h':{'path':str(path),'sha256':pin}
        generation={'attempt':1,'plan':ref(previous/'plan.json','raw'),'canonical_plan_sha256':'canonical','container_id':'id','started_at':'start','start_observation':ref('/start')}
        for key,p in {'claim':'attempts/1/CLAIM.json','launch_spec':'attempts/1/LAUNCH_SPEC.json','launch_receipt':'attempts/1/LAUNCH_RECEIPT.json','supervisor':'SUPERVISOR_RECEIPT.json'}.items():generation[key]=ref(previous/p)
        self.spec={'training':self.target['out'],'training_variant':{'arm':'k1-qo','seed':2,'training_plan_sha256':'qo_raw'},'model':'/base','adapter':self.target['out']+'/adapter','test_read':False,'scientific_acceptance':False,'execution_review':'PENDING','chip_assignment':'PENDING'}
        self.p={'chip':3,'out':str(self.root/'evaluation'),'adapter':'/adapter','resource_adapter':'/adapter','files':{},'tools':{},'spec':'/spec','spec_sha256':'h',
                'successor_guard':{'schema':'r3-control-dev-guard-v2','identity_mode':'sha256_raw','controller':str(self.root/'r3_control_dev_successor_v2.py'),'predecessor_kind':'control_physical_release','original_spec':ref('/original/plan.json'),'prepared':ref('/prepared'),'control_controller':ref('/control.py'),'control_config':ref('/config'),'training_role':'qo_s2','training_job':'qo_seed2','previous_job':'pt_seed2','previous_generation':generation}}
        self.docs={'/spec':self.spec,'/original/plan.json':copy.deepcopy(self.spec),'/prepared':{'status':'prepared','plan':'/original/plan.json','sha256':'h','role':'qo_s2','evaluation_authorized':False,'test_read':False,'scientific_acceptance':False},
                   '/config':{'controller':ref('/control.py')},str(previous/'attempts/1/LAUNCH_RECEIPT.json'):{'id':'id','plan_sha256':'canonical'},str(previous/'attempts/1/CLAIM.json'):{'chip':3,'run':'r3_runs/pt'},'/start':{'Status':'running','Running':True,'StartedAt':'start'}}
        self.ctl=types.SimpleNamespace(verify_controller=lambda *a:None,by_id=lambda c,k:self.jobs[k],checked_plan=lambda j:self.previous if j['id']=='pt_seed2' else self.target,helper=lambda c:types.SimpleNamespace(process_matches=lambda x:False),terminal_control=lambda *a:self.result)
        self.result={'status':'completed','container_id':'id','free_entry':{'chip':3,'previous_run':'r3_runs/pt'},'hashes':{}}
    @contextmanager
    def binding_io(self):
        with patch.multiple(self.G._core,sha=lambda x:'h',read=lambda x:self.docs[str(x)],pinned=lambda ref:Path(ref['path']),normalized_spec=lambda *a:None,module=lambda ref:self.ctl):yield
    def mark_terminal(self):
        root=Path(self.previous['out'])
        for p in ['TRAIN_EXIT.json','attempts/1/EXIT.json','attempts/1/RELEASE.json','attempts/1/SUPERVISOR_DONE.json']:(root/p).write_text('{}')
        self.docs[str(root/'attempts/1/RELEASE.json')]={'container_id':'id','container_started_at':'start','container_finished_at':'finish','claim_sha256':'h'}
    def test_exact_control_edge_binds_without_future_release(self):
        with self.binding_io():self.assertEqual(self.G.control_binding(self.p)[3],self.previous)
    def test_wrong_target_seed_arm_chip_rejected(self):
        for key,value in [('seed',3),('arm','k1-pt')]:
            with self.subTest(key=key):
                old=self.spec['training_variant'][key];self.spec['training_variant'][key]=value
                with self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
                self.spec['training_variant'][key]=old
        self.p['chip']=4
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
    def test_old_qo_cannot_replace_current_pt_predecessor(self):
        self.p['successor_guard']['previous_job']='qo_seed2'
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
    def test_generation_container_or_plan_swap_rejected(self):
        g=self.p['successor_guard']['previous_generation']
        for key,value in [('container_id','other'),('canonical_plan_sha256','other'),('attempt',2),('started_at','restart')]:
            old=g[key];g[key]=value
            with self.subTest(key=key),self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
            g[key]=old
    def test_extra_training_attempt_rejected(self):
        (Path(self.previous['out'])/'attempts/2').mkdir()
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
    def test_qo_artifact_cannot_be_replaced_by_pt_artifact(self):
        self.spec['adapter']=self.previous['out']+'/adapter'
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
    def test_scientific_test_authority_rejected(self):
        for key in ['test_read','scientific_acceptance']:
            self.spec[key]=True
            with self.subTest(key=key),self.binding_io(),self.assertRaises(RuntimeError):self.G.control_binding(self.p)
            self.spec[key]=False
    def test_core_watch_and_claim_are_reused(self):
        self.assertEqual(self.G.claim_precondition.__code__.co_filename,str(self.root/'core_formal_dev_successor.py'))
        self.assertEqual(self.G.watch.__code__.co_filename,str(self.root/'core_formal_dev_successor.py'))
        self.assertEqual(self.R.claim.__code__.co_filename,str(self.root/'core_resource_adapter.py'))
    def test_resource_entry_refuses_unbound_claim(self):
        with self.assertRaisesRegex(RuntimeError,'complete successor'):self.R.successor_guard(types.SimpleNamespace())
    def test_resource_entry_rejects_wrong_plan_pin_or_chip(self):
        (self.root/'allocation.json').write_text('{}')
        path=self.root/'execution.json';p={'chip':3,'run':'run','allocation':str(self.root/'allocation.json'),'adapter':str(self.root/'r3_control_dev_resource_v2.py'),'out':str(self.root/'out'),'files':{str(self.root/'r3_control_dev_resource_v2.py'):sha(self.root/'r3_control_dev_resource_v2.py')},'successor_guard':{'identity_mode':'sha256_raw','controller':str(self.root/'unexpected.py')}};path.write_text(json.dumps(p))
        args=types.SimpleNamespace(plan=str(path),plan_sha256='wrong',precondition_sha256='pre',chip=3,run='run',alloc=p['allocation'],proof=p['out']+'/attempts/1/CLAIM.json')
        with self.assertRaisesRegex(RuntimeError,'raw plan identity'):self.R.successor_guard(args)
        args.plan_sha256=sha(path);args.chip=4
        with self.assertRaisesRegex(RuntimeError,'resource scope'):self.R.successor_guard(args)
        args.chip=3
        with self.assertRaisesRegex(RuntimeError,'registered control'):self.R.successor_guard(args)



class ReleaseOnlyContracts(ControlDevContracts):
    def setUp(self):
        super().setUp();self.mark_terminal();root=Path(self.previous['out']);g=self.p['successor_guard'];refs={k:{'path':str(root/v),'sha256':'h'} for k,v in {'release':'attempts/1/RELEASE.json','terminal':'TRAIN_EXIT.json','attempt_terminal':'attempts/1/EXIT.json','supervisor_done':'attempts/1/SUPERVISOR_DONE.json'}.items()};g['physical_release']=refs
        self.end={'exit_code':1,'source':'retained-container-exit','runtime_terminal_present':False,'container_id':'id','release_sha256':'h','scientific_acceptance':False,'test_read':False}
        self.docs[refs['terminal']['path']]=self.end;self.docs[refs['attempt_terminal']['path']]=self.end.copy();self.docs[refs['supervisor_done']['path']]={'exit_code':1,'source':'retained-container-reconciliation','container_id':'id','scientific_acceptance':False}
        self.release=self.docs[refs['release']['path']];self.release['exit_code']=1
        self.data={'status':'completed','container_id':'qo_id','hashes':{'q':'pin'}};self.physical={'status':'failed','hashes':{'p':'pin'}}
        self.ctl.terminal_control=lambda c,j,p,r:self.data if j['id']=='qo_seed2' else self.physical
        self.ctl.helper=lambda c:types.SimpleNamespace(ownership=lambda *a:{'chip':3,'previous_run':'r3_runs/pt'})
        self.actual={'Id':'id','RestartCount':0,'State':{'Status':'exited','Running':False,'ExitCode':1,'StartedAt':'start','FinishedAt':'finish'}}
        self.resource=types.SimpleNamespace(docker_inspect=lambda n:self.actual)
    def test_failed_released_pt_allows_successful_qo(self):
        with self.binding_io():v=self.G.predecessor(self.p,self.resource)
        self.assertEqual(v['status'],'physical_release_authenticated');self.assertEqual(v['exit_code'],1);self.assertEqual(v['data_dependency']['container_id'],'qo_id')
    def test_failed_qo_data_never_accepted(self):
        for status in ['failed','training','needs_repair']:
            self.data['status']=status
            with self.subTest(status=status),self.binding_io(),self.assertRaisesRegex(RuntimeError,'QO own'):self.G.predecessor(self.p,self.resource)
    def test_unreleased_or_uncertain_pt_never_accepted(self):
        for status in ['training','waiting_release','needs_repair','supervisor_live','completed']:
            self.physical['status']=status
            with self.subTest(status=status),self.binding_io(),self.assertRaisesRegex(RuntimeError,'failed released'):self.G.predecessor(self.p,self.resource)
    def test_restart_or_live_container_rejected(self):
        for key,value in [('Status','running'),('Running',True),('ExitCode',0)]:
            old=self.actual['State'][key];self.actual['State'][key]=value
            with self.subTest(key=key),self.binding_io(),self.assertRaises(RuntimeError):self.G.predecessor(self.p,self.resource)
            self.actual['State'][key]=old
        self.actual['RestartCount']=1
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.predecessor(self.p,self.resource)
    def test_stale_release_and_fake_terminal_rejected(self):
        for key,value in [('container_id','other'),('container_started_at','other'),('claim_sha256','other')]:
            old=self.release[key];self.release[key]=value
            with self.subTest(key=key),self.binding_io(),self.assertRaises(RuntimeError):self.G.predecessor(self.p,self.resource)
            self.release[key]=old
        self.end['source']='runtime'
        with self.binding_io(),self.assertRaises(RuntimeError):self.G.predecessor(self.p,self.resource)

if __name__=='__main__':unittest.main()
