import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('successor',Path(__file__).with_name('bev_batch_successor.py'))
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)

class Successor(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.out=self.root/'service';self.out.mkdir()
        self.p={'out':str(self.root/'previous'),'run':'previous','chip':7,'container':'previous','image_sha256':'image','allocation':str(self.root/'allocation.json'),'expected_questions':2,'code':{'runner':{'path':'/runner.py'}}}
        self.n=dict(self.p,out=str(self.root/'next'),run='next',container='next',code={'host':{'path':'/host.py'},'runner':{'path':'/runner.py'}})
        self.h=Path(self.p['out'])/'host_attempts/1';self.h.mkdir(parents=True)
        (Path(self.p['out'])/'attempts/1').mkdir(parents=True)
        self.claim={'schema':'r3-resource-claim-v1','run':'previous','chip':7};S.write(self.h/'CLAIM.json',self.claim)
        self.receipt={'plan_sha256':'previous-pin','container_id':'cid','command':['python3','-B','-P','/runner.py','run','--plan','/previous-plan.json','--sha256','previous-pin','--attempt','1']};S.write(self.h/'LAUNCH_RECEIPT.json',self.receipt)
        self.c={'output':str(self.out),'python':'/usr/bin/python3.12','previous':{'claim':S.pin(self.h/'CLAIM.json'),'launch':S.pin(self.h/'LAUNCH_RECEIPT.json'),'plan':{'path':'/previous-plan.json','sha256':'previous-pin'}},'next':{'plan':{'path':'/next-plan.json','sha256':'next-pin'},'review':{'path':'/review.json','sha256':'review-pin'}}}
        review=self.root/'review.json';S.write(review,{'fixture':True});self.c['next']['review']=S.pin(review)
        self.actual={'Id':'cid','Name':'/previous-a1','Image':'image','HostConfig':{'AutoRemove':False,'Devices':[{'PathOnHost':'/dev/davinci7'}]},'Config':{'Cmd':self.receipt['command']},'State':{'Status':'exited','ExitCode':0,'StartedAt':'start','FinishedAt':'finish'}}
        pp=self.root/'previous-plan.json';S.write(pp,self.p);self.c['previous']['plan']=S.pin(pp)
        self.receipt['plan_sha256']=S.sha(pp);self.receipt['command']=S.runner_command(self.p,self.c['previous']['plan']);S.write(self.h/'LAUNCH_RECEIPT.json',self.receipt);self.c['previous']['launch']=S.pin(self.h/'LAUNCH_RECEIPT.json');self.actual['Config']['Cmd']=self.receipt['command']
    def complete(self):
        S.write(self.h/'EXIT.json',{'exit_code':0,'runner_terminal_matches':True,'container_exit_code':0,'container_id':'cid'})
        S.write(self.h/'RELEASE.json',{'schema':'r3-resource-release-v1','exit_code':0,'run':'previous','chip':7,'container_id':'cid','claim_sha256':S.sha(self.h/'CLAIM.json'),'container':'previous-a1','container_started_at':'start','container_finished_at':'finish','allocation_after':{'allocation':[],'free':[{'chip':7,'previous_run':'previous','release_evidence':str(self.h/'RELEASE.json')}]}})
        S.write(Path(self.p['out'])/'attempts/1/EXIT.json',{'attempt':1,'exit_code':0,'plan_sha256':self.c['previous']['plan']['sha256']})
        S.write(Path(self.p['out'])/'COMPLETE.json',{'attempt':1,'exit_code':0,'schema':'bev-public-test-completion-v1','plan_sha256':self.c['previous']['plan']['sha256'],'rows':2,'items':{'a':'a','b':'b'}})
        S.write(Path(self.p['allocation']),{'allocation':[],'free':[{'chip':7,'previous_run':'previous','release_evidence':str(self.h/'RELEASE.json')}]})
    def next_claim(self):
        before=S.read(self.p['allocation']);entry={'run':'next','chip':7};after={'allocation':[entry],'free':[]}
        digest=lambda d:S.hashlib.sha256((json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest()
        pre=Path(self.n['out'])/'SUCCESSOR_PRECONDITION.json'
        return dict(schema='r3-resource-claim-v1',run='next',chip=7,allocation=self.n['allocation'],allocation_before=before,allocation_after=after,allocation_before_sha256=digest(before),allocation_after_sha256=digest(after),entry=entry,successor_precondition=dict(plan_sha256='next-pin',precondition_sha256=S.sha(pre),previous=S.read(pre)['previous']))
    def test_matching_wrong_runtime_and_receipt_rejected(self):
        self.complete();S.tick(self.c,self.p,self.n,lambda _:self.actual,lambda cmd:dict(status='supervisor_started',pid=1,attempt=1))
        h=Path(self.n['out'])/'host_attempts/1';h.mkdir(parents=True)
        S.write(h/'LAUNCH_RECEIPT.json',dict(plan_sha256='next-pin',container_id='next-cid',command=['wrong']))
        actual=copy.deepcopy(self.actual);actual.update(Id='next-cid',Name='/next-a1');actual['Config']['Cmd']=['wrong'];actual['State']['Status']='running'
        with self.assertRaisesRegex(ValueError,'command'):S.tick(self.c,self.p,self.n,lambda _:actual)
    def guarded_fixture(self):
        self.complete();proof=S.previous_ready(self.c,self.p,lambda _:self.actual)
        out=Path(self.n['out']);out.mkdir();pre=out/'SUCCESSOR_PRECONDITION.json';S.write(pre,dict(plan_sha256='next-pin',previous=proof))
        pp=self.root/'previous-plan.json';S.write(pp,self.p)
        # Fixture receipt plan identifier remains fixed; pin is checked by claim hook.
        self.c['previous']['plan']=S.pin(pp);self.receipt['plan_sha256']=S.sha(pp);self.receipt['command']=S.runner_command(self.p,self.c['previous']['plan']);S.write(self.h/'LAUNCH_RECEIPT.json',self.receipt);self.c['previous']['launch']=S.pin(self.h/'LAUNCH_RECEIPT.json');self.actual['Config']['Cmd']=self.receipt['command']
        for path in [Path(self.p['out'])/'attempts/1/EXIT.json',Path(self.p['out'])/'COMPLETE.json']:
            d=S.read(path);d['plan_sha256']=S.sha(pp);S.write(path,d)
        proof=S.previous_ready(self.c,self.p,lambda _:self.actual);S.write(pre,dict(plan_sha256='next-pin',previous=proof));self.n['successor_guard']={'previous':self.c['previous']}
        resource=types.SimpleNamespace(docker_inspect=lambda name:self.actual if name=='cid' else None,live_chip_conflict=lambda *x:False)
        allocation=S.read(self.p['allocation'])
        return pre,resource,allocation
    def test_guard_checks_changed_free_and_changed_terminal(self):
        pre,resource,allocation=self.guarded_fixture();S.claim_precondition(self.n,'next-pin',S.sha(pre),allocation,resource)
        bad=copy.deepcopy(allocation);bad['free'][0]['previous_run']='intervening-owner'
        with self.assertRaisesRegex(ValueError,'generation'):S.claim_precondition(self.n,'next-pin',S.sha(pre),bad,resource)
        d=S.read(self.h/'EXIT.json');d['extra']='changed';S.write(self.h/'EXIT.json',d)
        with self.assertRaisesRegex(ValueError,'changed'):S.claim_precondition(self.n,'next-pin',S.sha(pre),allocation,resource)
    def adapter_fixture(self):
        pre,resource,allocation=self.guarded_fixture()
        wspec=importlib.util.spec_from_file_location('wrapper',Path(__file__).with_name('bev_batch_resource.py'));W=importlib.util.module_from_spec(wspec);wspec.loader.exec_module(W);R=W.build()
        R.docker_inspect=resource.docker_inspect;R.live_chip_conflict=resource.live_chip_conflict
        self.n['code']['resource']=S.pin(Path(W.__file__).resolve());self.n['successor_guard']['controller']=S.pin(Path(S.__file__).resolve())
        plan=self.root/'next-plan.json';S.write(plan,self.n)
        value=S.read(pre);value['plan_sha256']=S.sha(plan);S.write(pre,value)
        args=types.SimpleNamespace(plan=str(plan),plan_sha256=S.sha(plan),precondition_sha256=S.sha(pre),run='next',chip=7,alloc=self.p['allocation'],proof=str(Path(self.n['out'])/'host_attempts/1/CLAIM.json'),owner='test',purpose='test')
        return R,args,pre,allocation
    def test_actual_locked_transaction_rejects_intervening_generation(self):
        R,args,pre,allocation=self.adapter_fixture();changed=copy.deepcopy(allocation);changed['free'][0]['released_utc']='different-generation';S.write(Path(args.alloc),changed)
        before=Path(args.alloc).read_bytes()
        with self.assertRaisesRegex(ValueError,'changed|free entry'):R.claim(args)
        self.assertEqual(Path(args.alloc).read_bytes(),before);self.assertFalse(Path(args.proof).exists())
    def test_actual_transaction_second_guard_rejects_changed_evidence(self):
        R,args,pre,allocation=self.adapter_fixture();before=Path(args.alloc).read_bytes();original=R.write_atomic;calls=[]
        def mutate(path,value):
            result=original(path,value)
            if str(path).endswith('.intent'):
                calls.append('intent');v=S.read(self.h/'EXIT.json');v['changed_after_first_guard']=True;S.write(self.h/'EXIT.json',v)
            return result
        with patch.object(R,'write_atomic',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'changed|free entry'):R.claim(args)
        self.assertEqual(calls,['intent']);self.assertEqual(Path(args.alloc).read_bytes(),before);self.assertFalse(Path(args.proof).exists())
    def test_actual_transaction_produces_bound_claim_and_refuses_replay(self):
        R,args,pre,allocation=self.adapter_fixture();R.claim(args)
        S.validate_claim(S.read(args.proof),self.n,args.plan_sha256)
        with self.assertRaisesRegex(RuntimeError,'already attempted'):R.claim(args)
    def test_wait_and_failure_no_launch(self):
        calls=[]
        self.assertEqual(S.tick(self.c,self.p,self.n,launch=lambda x:calls.append(x))['status'],'waiting_predecessor_release')
        S.write(self.h/'EXIT.json',{'exit_code':1})
        with self.assertRaisesRegex(ValueError,'failed'):S.tick(self.c,self.p,self.n)
        self.assertEqual(calls,[])
    def test_real_schema_ready_and_changed_evidence(self):
        self.complete();self.assertEqual(S.previous_ready(self.c,self.p,lambda _:self.actual)['container_id'],'cid')
        for filename,key,bad in [('RELEASE.json','claim_sha256','bad'),('RELEASE.json','container_id','wrong'),('EXIT.json','runner_terminal_matches',False)]:
            p=self.h/filename;original=S.read(p);changed=dict(original);changed[key]=bad;S.write(p,changed)
            with self.assertRaises(ValueError):S.previous_ready(self.c,self.p,lambda _:self.actual)
            S.write(p,original)
    def test_wrong_retained_container_and_free_generation(self):
        self.complete()
        for section,key,bad in [('State','Status','running'),('State','ExitCode',1),('HostConfig','AutoRemove',True),('Config','Cmd',['wrong'])]:
            a=copy.deepcopy(self.actual);a[section][key]=bad
            with self.assertRaises(ValueError):S.previous_ready(self.c,self.p,lambda _:a)
        d=S.read(self.p['allocation']);d['free'][0]['previous_run']='wrong';S.write(Path(self.p['allocation']),d)
        with self.assertRaisesRegex(ValueError,'generation'):S.previous_ready(self.c,self.p,lambda _:self.actual)
    def test_uncertain_intent_never_replayed(self):
        self.complete();calls=[]
        def fail(cmd):calls.append(cmd);raise TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):S.tick(self.c,self.p,self.n,lambda _:self.actual,fail)
        with self.assertRaisesRegex(ValueError,'never replay'):S.tick(self.c,self.p,self.n,lambda _:self.actual,fail)
        self.assertEqual(len(calls),1)
    def test_exactly_one_launch_and_handoff(self):
        self.complete();calls=[]
        def launch(cmd):calls.append(cmd);return {'status':'supervisor_started','pid':123,'attempt':1}
        self.assertEqual(S.tick(self.c,self.p,self.n,lambda _:self.actual,launch)['status'],'waiting_successor_receipt')
        self.assertEqual(S.tick(self.c,self.p,self.n,lambda _:self.actual,launch)['status'],'waiting_successor_receipt');self.assertEqual(len(calls),1)
        h=Path(self.n['out'])/'host_attempts/1';h.mkdir(parents=True)
        S.write(h/'LAUNCH_RECEIPT.json',{'plan_sha256':'next-pin','container_id':'next-cid','command':S.runner_command(self.n,self.c['next']['plan'])});S.write(h/'CLAIM.json',self.next_claim())
        actual=copy.deepcopy(self.actual);actual.update(Id='next-cid',Name='/next-a1');actual['State']['Status']='running';actual['Config']['Cmd']=S.runner_command(self.n,self.c['next']['plan'])
        self.assertEqual(S.tick(self.c,self.p,self.n,lambda _:actual,launch)['status'],'handed_off');self.assertEqual(len(calls),1)
    def test_exclusive_intents_and_existing_external_attempt(self):
        p=self.out/'intent.json';S.write(p,{'x':1},True)
        with self.assertRaises(FileExistsError):S.write(p,{'x':2},True)
        self.complete();(Path(self.n['out'])/'host_attempts/1').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'already exists'):S.tick(self.c,self.p,self.n,lambda _:self.actual)
    def test_concurrent_service_start_lock_refuses_launch(self):
        args=types.SimpleNamespace(config="/config",sha256="pin",activation="/activation",activation_sha256="ap")
        with (self.out/"start.lock").open("a") as held:
            S.fcntl.flock(held,S.fcntl.LOCK_EX|S.fcntl.LOCK_NB)
            with patch.object(S.subprocess,"Popen") as launch:
                with self.assertRaises(BlockingIOError):S.start(args,self.c)
                launch.assert_not_called()

    def test_activation_requires_exact_external_review_and_publication(self):
        pr=self.root/'PREREG.md';pr.write_text('fixed');plan=self.root/'plan.json';S.write(plan,{'inputs':{'preregistration':S.pin(pr)}});self.c['next']['plan']['path']=str(plan)
        rev=self.root/'review.json';S.write(rev,{'verdict':'PASS','config_sha256':'cp','activation_authorized':True,'scientific_acceptance':False})
        a={'schema':'bev-batch-successor-activation-v1','config_sha256':'cp','activation_authorized':True,'scientific_acceptance':False,'review':S.pin(rev),'preregistration':S.pin(pr),'wiki_commit':'a'*40,'probe_review':S.pin(rev)};ap=self.root/'activation.json';S.write(ap,a)
        S.activation(str(ap),S.sha(ap),self.c,'cp')
        a['wiki_commit']='PENDING';S.write(ap,a)
        with self.assertRaisesRegex(ValueError,'wiki'):S.activation(str(ap),S.sha(ap),self.c,'cp')
    def test_detached_start_and_duplicate_refusal(self):
        self.c.update(controller={'path':S.__file__},host='k8s-node1')
        args=types.SimpleNamespace(config='/config',sha256='pin',activation='/activation',activation_sha256='ap')
        with patch.object(S.subprocess,'Popen',return_value=types.SimpleNamespace(pid=77)) as popen:
            self.assertEqual(S.start(args,self.c)['pid'],77)
            self.assertTrue(popen.call_args.kwargs['start_new_session']);self.assertEqual(popen.call_args.kwargs['stdin'],S.subprocess.DEVNULL)
            with self.assertRaisesRegex(ValueError,'reconciliation'):S.start(args,self.c)
            self.assertEqual(popen.call_count,1)
        self.assertTrue((self.out/'RELAUNCH.json').is_file());self.assertTrue((self.out/'service.log').is_file())

if __name__=='__main__':unittest.main()
