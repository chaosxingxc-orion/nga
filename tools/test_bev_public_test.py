import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE=Path(__file__).parent

def mod(name):
    s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

R=mod('bev_public_test_runner');B=mod('bev_public_test_bridge');C=mod('bev_public_test_consumer')
A=mod('bev_public_test_builder');H=mod('bev_public_test_host');E=mod('experiment_entrypoint');W=mod('experiment_workflow')


def request(kind='choice',n=2,text='context'):
    keys=['true','false'] if kind=='noul' else ([str(i) for i in range(n)] if kind=='score' else ['a','b'])
    definitions=['True','False'] if kind=='noul' else ['level '+str(i) for i in range(n)]
    return dict(input=text,type=kind,level_type={'choice':'nominal','noul':'boolean','score':'ordinal'}[kind],candidate_set='exclusive',question='Choose one',candidate_keys=keys,definitions=definitions)

class PublicSchemaTests(unittest.TestCase):
    def row(self):
        specs={'c':{'type':'choice','instructions':'Choose','criteria':{'a':'A','b':'B'},'label':'b'},
               'n':{'type':'noul','instructions':'True?','label':True},
               's':{'type':'score','instructions':'Rank','criteria':['low','high','top'],'label':2}}
        return {'state':'input','questions_json':json.dumps(specs),'question_count':3,'question_types':['choice','noul','score'],'domain':'test'}
    def test_real_release_shape_gold_separation_and_duplicates(self):
        req,gold,ids=A.extract([self.row(),self.row()],A.SOURCE_SHA)
        self.assertEqual(len(req),6);self.assertEqual(len({x['id'] for x in req}),6)
        self.assertEqual(req[0]['request'],req[3]['request']);self.assertNotEqual(req[0]['id'],req[3]['id'])
        self.assertEqual([x['gold_index'] for x in gold],[1,0,2,1,0,2])
        for r in req:self.assertEqual(set(r),{'id','request'});self.assertNotIn('label',r['request'])
    def test_builder_rejects_source_split_hash_and_6516_before_writes(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);src=base/'numeric_temporal';src.mkdir();test=src/'test.parquet';test.write_bytes(b'fixture')
            contract={'schema':'nga-public-test-panel-contract-draft-v1','panel':'BEV/numeric_temporal/release-test','source':{'path':str(test),'sha256':A.SOURCE_SHA},'population':{'rows':3329,'questions':6518,'by_type':A.POP}}
            for failure in ('split','hash','population'):
                d=copy.deepcopy(contract)
                if failure=='split':d['source']['path']=str(src/'train.parquet')
                elif failure=='hash':d['source']['sha256']='0'*64
                else:d['population']['questions']=6516
                cp=base/('contract-'+failure+'.json');cp.write_text(json.dumps(d))
                cfg=base/('prepare-'+failure+'.json');root=base/('out-'+failure)
                c=dict(schema='nga-bev-public-test-prepare-v1',contract={'path':str(cp),'sha256':E.digest(cp)},template_plan={},root=str(root),run='r3_runs/'+root.name,container='nga-fixture',chip=0)
                cfg.write_text(json.dumps(c));real_digest=A.E.digest
                def fixture_digest(path):
                    return A.SOURCE_SHA if Path(path)==test else real_digest(path)
                with mock.patch.object(A.E,'digest',side_effect=fixture_digest):
                    with self.assertRaises(ValueError):A.prepare(cfg,real_digest(cfg))
                self.assertFalse(root.exists())
    def test_resource_override_is_explicit_pinned_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);adapter=root/'r3_resource_adapter.py';adapter.write_text('# fixture')
            cfg=root/'prepare.json';out=root/'output'
            c=dict(schema='nga-bev-public-test-prepare-v1',template_plan={},contract={},root=str(out),run='r3_runs/output',container='nga-public-fixture',chip=7,resource_adapter={'path':str(adapter),'sha256':'0'*64})
            cfg.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'pinned content changed'):A.prepare(cfg,E.digest(cfg))
            self.assertFalse(out.exists())
    def test_bad_schema_count_candidates_and_score_rejected(self):
        variants=[]
        r=self.row();r['question_count']=2;variants.append(r)
        r=self.row();r['questions_json']='{"x":{},"x":{}}';variants.append(r)
        for mutate in ('label','criteria'):
            r=self.row();qs=json.loads(r['questions_json']);qs['s'][mutate]=True if mutate=='label' else ['same','same'];r['questions_json']=json.dumps(qs);variants.append(r)
        for r in variants:
            with self.assertRaises((ValueError,KeyError)):A.extract([r],A.SOURCE_SHA)
    def test_metrics_missing_invalid_and_failure_denominators(self):
        req=[{'id':str(i),'request':request('score',3)} for i in range(4)]
        gold=[{'id':str(i),'type':'score','gold_index':2} for i in range(4)]
        metrics=C.score(req,gold,[{'id':'0','status':'ok','index':1},{'id':'1','status':'ok','index':True},{'id':'2','status':'refused'}])['score']
        self.assertEqual(metrics['n'],4);self.assertEqual(metrics['valid_predictions'],1);self.assertEqual(metrics['accuracy'],0)
        self.assertEqual(metrics['valid_prediction_index_mae'],1);self.assertEqual(metrics['valid_prediction_normalized_error'],.5)
        self.assertEqual(metrics['normalized_error_with_failure_penalty'],.875);self.assertEqual(metrics['failure_count'],3)
        self.assertEqual(metrics['outcomes'],{'ok':1,'invalid_prediction':1,'refused':1,'missing':1})
    def test_unknown_duplicate_predictions_and_gold_ids_reject(self):
        req=[{'id':'a','request':request()}];gold=[{'id':'a','type':'choice','gold_index':0}]
        for preds in [[{'id':'other'}],[{'id':'a'},{'id':'a'}]]:
            with self.assertRaises(ValueError):C.score(req,gold,preds)
        with self.assertRaises(ValueError):C.population(req,[dict(gold[0],id='bad')],1)
    def test_resume_commits_only_missing_then_rejects_changed_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);rows=[{'id':str(i),'request':request()} for i in range(12)]
            seen=[]
            def score(batch):
                seen.extend(x['id'] for x in batch)
                return [(r,[1.,0.],B.from_raw(r['id'],[1.,0.],2)) for r in batch]
            def interrupt(n):
                if n==5:raise RuntimeError('simulate disconnect')
            with self.assertRaises(RuntimeError):R.process(rows,root,'a'*64,B,score,interrupt)
            seen.clear();values=R.process(rows,root,'a'*64,B,score,lambda n:None)
            self.assertEqual(seen,[str(i) for i in range(5,12)]);self.assertEqual(len(values),12)
            R.process(rows,root,'a'*64,B,lambda _:self.fail('resume rescored'),lambda _:None)
            with self.assertRaisesRegex(ValueError,'binding'):R.process(rows,root,'b'*64,B,score,lambda _:None)
            (root/'items'/'foreign.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'unknown item'):R.existing(root,rows,'a'*64,B)

class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.inf=self.root/'inference';self.cpu=self.root/'cpu'
        for p in (self.inf,self.cpu,self.root/'control',self.inf/'code',self.inf/'inputs',self.inf/'output'):p.mkdir()
        self.pin=lambda p:{'path':str(p),'sha256':E.digest(p)}
        self.write=lambda p,x:p.write_text(json.dumps(x))
        self.rows=[]
        for kind,n in A.POP.items():
            for i in range(n):self.rows.append({'id':str(len(self.rows)),'request':request(kind,2,str(len(self.rows)))})
        for i in range(24):self.rows[-1-i]['request']=copy.deepcopy(self.rows[-25-i]['request'])
        req=self.inf/'inputs/requests.jsonl';req.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
        ids=self.inf/'inputs/test-ids.json';self.write(ids,[r['id'] for r in self.rows])
        manifest=self.inf/'inputs/source-manifest.json'
        self.write(manifest,dict(schema='bev-public-test-source-v1',scope='public_release_test',config='numeric_temporal',split='test',source_sha256=A.SOURCE_SHA,rows=3329,questions=6518,by_type=A.POP,ordered_ids_sha256=E.digest(ids),requests_sha256=E.digest(req)))
        code={}
        for key,name in [('runner','bev_public_test_runner.py'),('host','bev_public_test_host.py'),('bridge','bev_public_test_bridge.py')]:
            target=self.inf/'code'/name;target.write_bytes((HERE/name).read_bytes());code[key]=self.pin(target)
        for key in ('prompt','scorer'):
            target=self.inf/'code'/(key+'.py');target.write_text('# fixture');code[key]=self.pin(target)
        resource=self.inf/'code/r3_resource_adapter.py';resource.write_bytes((HERE/'r3_resource_adapter.py').read_bytes());code['resource']=self.pin(resource)
        model=self.root/'Qwen__Qwen3.5-0.8B-Base';model.mkdir();self.write(model/'config.json',{})
        proof=self.inf/'inputs/tokenizer-proof.json';self.write(proof,dict(schema='bev-public-test-tokenizer-proof-v1',questions=6518,model=str(model),requests_sha256=E.digest(req),prompt_sha256=code['prompt']['sha256'],candidate_collisions=0,overlength=0,tokenizer_files={'config.json':self.pin(model/'config.json')}))
        prereg=self.inf/'inputs/PREREGISTRATION.md';prereg.write_text('TEST protocol')
        self.plan=dict(schema='bev-public-test-plan-v1',scientific_acceptance=False,test_read=True,source_split='public_release_test',selection='all_release_test_ids',expected_questions=6518,expected_by_type=A.POP,candidate_selection_allowed=False,native_reproduction=False,protocol=A.PROTOCOL,device='npu:0',chips=1,chip=0,image_sha256='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7',model=str(model),model_files={'config.json':self.pin(model/'config.json')},code=code,inputs={'requests':self.pin(req),'ids':self.pin(ids),'source_manifest':self.pin(manifest),'tokenizer_proof':self.pin(proof),'preregistration':self.pin(prereg)},source_manifest=self.pin(manifest),scoring={'mode':'rightpad','dtype':'float32','head_fp32':False,'hf32':False,'token_budget':16384,'max_sequence_tokens':4096,'chunk':8},out=str(self.inf/'output'))
        self.plan['mounts']=[dict(source=str(self.inf),destination=str(self.inf),readonly=True),dict(source=str(self.inf/'output'),destination=str(self.inf/'output'),readonly=False),dict(source=str(model),destination=str(model),readonly=True)]
        self.pp=self.inf/'plan.json';self.write(self.pp,self.plan)
        self.runner=A.module(code['runner']['path'],'fixture_public_runner');self.host=A.module(code['host']['path'],'fixture_public_host')
        gold=[{'id':r['id'],'type':r['request']['type'],'gold_index':0} for r in self.rows]
        (self.cpu/'gold.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in gold))
        self.consumer=self.cpu/'consume.py';self.consumer.write_bytes((HERE/'bev_public_test_consumer.py').read_bytes());self.C=A.module(self.consumer,'fixture_public_cpu')
        self.cpuconfig=dict(schema='bev-public-test-cpu-config-v1',scope='public_release_test',candidate_selection_allowed=False,test_read=True,scientific_acceptance=False,poll_interval_seconds=600,plan=str(self.pp),plan_sha256=E.digest(self.pp),gold=str(self.cpu/'gold.jsonl'),files={str(p):E.digest(p) for p in (self.pp,self.consumer,self.cpu/'gold.jsonl')})
        for group in ('code','inputs','model_files'):self.cpuconfig['files'].update({v['path']:v['sha256'] for v in self.plan[group].values()})
        self.cp=self.cpu/'config.json';self.write(self.cp,self.cpuconfig)
        self.review=dict(activation_authorized=True,scientific_acceptance=False,scope='public_release_test',candidate_selection_allowed=False,approved_plan_sha256=E.digest(self.pp),attempts=[1],hashes=dict(self.cpuconfig['files']),deployment_suitable=True,cpu_config_sha256=E.digest(self.cp),consumer_sha256=E.digest(self.consumer))
        self.rp=self.root/'review.json';self.write(self.rp,self.review)
    def test_full_public_verify_cpu_scope_and_no_oracle(self):
        p=self.runner.verify(self.pp,E.digest(self.pp));self.assertEqual(len(self.runner.requests(p,B)),6518)
        self.C.verify_config(self.cp,E.digest(self.cp));self.assertFalse(hasattr(self.C,'references'))
    def test_6516_scope_and_source_misbinding_rejected(self):
        for key,value in [('expected_questions',6516),('source_split','train_derived_dev'),('test_read',False),('candidate_selection_allowed',True)]:
            p=dict(self.plan);p[key]=value;self.write(self.pp,p)
            with self.assertRaises(ValueError):self.runner.verify(self.pp,E.digest(self.pp))
        self.write(self.pp,self.plan)
        source=Path(self.plan['source_manifest']['path']);d=json.loads(source.read_text());d['split']='train';self.write(source,d)
        self.plan['inputs']['source_manifest']=self.plan['source_manifest']=self.pin(source);self.write(self.pp,self.plan)
        with self.assertRaisesRegex(ValueError,'source/split'):self.runner.verify(self.pp,E.digest(self.pp))
    def test_duplicate_foreign_missing_ids_rejected(self):
        for mode in ('duplicate','foreign','missing'):
            rows=copy.deepcopy(self.rows)
            if mode=='duplicate':rows[-1]['id']=rows[0]['id']
            elif mode=='foreign':rows[-1]['id']='foreign'
            else:rows.pop()
            Path(self.plan['inputs']['requests']['path']).write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaises(ValueError):self.runner.requests(self.plan,B)
    def test_gold_mount_and_invalid_candidate_rejected(self):
        self.plan['mounts'].append(dict(source=str(self.cpu),destination=str(self.cpu),readonly=True));self.write(self.pp,self.plan)
        with self.assertRaisesRegex(ValueError,'gold-free'):self.runner.verify(self.pp,E.digest(self.pp))
        q=request('score',2);q['candidate_keys']=['1','0']
        with self.assertRaises(ValueError):B.to_r3_row(q)
    def test_direct_host_requires_review_scope_pins_and_attempt(self):
        self.host.review(self.pp,E.digest(self.pp),self.rp,E.digest(self.rp))
        bad=dict(self.review);bad['scope']='train_derived_dev';self.write(self.rp,bad)
        with self.assertRaisesRegex(ValueError,'scope'):self.host.review(self.pp,E.digest(self.pp),self.rp,E.digest(self.rp))
        self.write(self.rp,self.review)
        args=type('Args',(),dict(plan=str(self.pp),sha256=E.digest(self.pp),review=str(self.rp),review_sha256=E.digest(self.rp),attempt=2))()
        with self.assertRaisesRegex(ValueError,'attempt not reviewed'):self.host.start(args)
        del self.review['hashes'][self.plan['code']['bridge']['path']];self.write(self.rp,self.review)
        with self.assertRaisesRegex(ValueError,'outside exact review'):self.host.review(self.pp,E.digest(self.pp),self.rp,E.digest(self.rp))
    def test_fixed_workflow_bind_dryrun_without_launch_and_old_review_rejected(self):
        pp=self.root/'PREPARED.json';self.write(pp,dict(schema='nga-bev-public-test-prepared-v1',approved=False,plan=self.pin(self.pp),cpu=self.pin(self.cp),consumer=self.pin(self.consumer),entrypoint=self.pin(HERE/'experiment_entrypoint.py'),workflow=self.pin(HERE/'experiment_workflow.py')))
        bad=dict(self.review);bad.pop('scope');self.write(self.rp,bad)
        with self.assertRaises(ValueError):W.bind(pp,E.digest(pp),self.rp,E.digest(self.rp),1)
        self.assertFalse((self.root/'control/attempt-1').exists())
        self.write(self.rp,self.review)
        result=W.bind(pp,E.digest(pp),self.rp,E.digest(self.rp),1);a=result['activation']
        output=W.operate('dry-run',a['path'],a['sha256']);self.assertEqual(output['status'],'validated_dry_run')
        self.assertFalse((self.cpu/'START_INTENT.json').exists());self.assertFalse((self.inf/'output/host_attempts').exists())
    def test_failed_partial_lifecycle_no_report(self):
        out=Path(self.plan['out']);(out/'host_attempts/1').mkdir(parents=True)
        self.write(out/'host_attempts/1/EXIT.json',{'exit_code':1})
        with self.assertRaisesRegex(ValueError,'producer failure'):self.C.lifecycle(self.cpuconfig,self.plan)
    def test_prepared_validation_and_no_unreviewed_activation(self):
        pp=self.root/'PREPARED.json';self.write(pp,dict(schema='nga-bev-public-test-prepared-v1',approved=False,plan=self.pin(self.pp),cpu=self.pin(self.cp),consumer=self.pin(self.consumer),entrypoint=self.pin(HERE/'experiment_entrypoint.py'),workflow=self.pin(HERE/'experiment_workflow.py')))
        for op in ('validate','dry-run'):
            result=W.operate(op,pp,E.digest(pp));self.assertFalse(result['activation_authorized']);self.assertFalse(result['writes_performed'])
        with self.assertRaisesRegex(ValueError,'independent review'):W.operate('start',pp,E.digest(pp))
    def lifecycle_fixture(self):
        adapter=A.module(self.plan['code']['resource']['path'],'fixture_real_resource')
        alloc=self.root/'allocation.json'
        adapter.write_atomic(alloc,{'allocation':[],'free':[{'chip':0},{'chip':7}]})
        self.plan.update(container='nga-test-public',run='r3_runs/test_public',allocation=str(alloc),environment={'HF_HUB_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'})
        self.write(self.pp,self.plan);planpin=E.digest(self.pp)
        self.cpuconfig['plan_sha256']=planpin;self.cpuconfig['files'][str(self.pp)]=planpin
        out=Path(self.plan['out']);(out/'items').mkdir();run=out/'attempts/1';host=out/'host_attempts/1'
        run.mkdir(parents=True);host.mkdir(parents=True)
        inventory={}
        for row in self.rows:
            raw=[1.,0.];v={'schema':'bev-public-test-item-v1','id':row['id'],'plan_sha256':planpin,'request_sha256':R.digest(row),'raw':raw,'prediction':B.from_raw(row['id'],raw,2),'scientific_acceptance':False,'test_read':True}
            item=R.item_path(out,row['id']);self.write(item,v);inventory[item.name]=E.digest(item)
        command=['python3','-B','-P',self.plan['code']['runner']['path'],'run','--plan',str(self.pp),'--sha256',planpin,'--attempt','1']
        devices=['/dev/davinci_manager','/dev/devmm_svm','/dev/hisi_hdc','/dev/davinci0']
        binds=['/usr/local/Ascend/driver:/usr/local/Ascend/driver:ro']+[m['source']+':'+m['destination']+(':ro' if m['readonly'] else '') for m in self.plan['mounts']]
        cli=['docker','run','-d','--name','nga-test-public-a1','--network','none','--shm-size','16g','--ulimit','memlock=-1:-1','--ulimit','stack=67108864:67108864']
        for device in devices:cli+=['--device',device]
        cli+=['-v',binds[0]]
        for k,v in self.plan['environment'].items():cli+=['-e',k+'='+v]
        for bind in binds[1:]:cli+=['-v',bind]
        cli +=[self.plan['image_sha256'],*command]
        image={'Id':self.plan['image_sha256'],'Config':{'Env':['PATH=/usr/bin'],'Entrypoint':None}}
        env=['PATH=/usr/bin']+[k+'='+v for k,v in self.plan['environment'].items()]
        mounts=[{'Type':'bind','Destination':b.split(':')[1],'Source':b.split(':')[0],'RW':len(b.split(':'))==2,'Mode':'' if len(b.split(':'))==2 else 'ro','Propagation':'rprivate'} for b in binds]
        actual=dict(Id='cid',Name='/nga-test-public-a1',Image=self.plan['image_sha256'],Path='python3',Args=command[1:],State={'Status':'exited','ExitCode':0,'StartedAt':'2026-11-02T11:00:01Z','FinishedAt':'2026-11-02T11:01:00Z'},HostConfig={'AutoRemove':False,'NetworkMode':'none','Runtime':'runc','IpcMode':'private','CgroupnsMode':'private','Devices':[{'PathOnHost':x,'PathInContainer':x,'CgroupPermissions':'rwm'} for x in devices],'Binds':binds,'ShmSize':16*1024**3,'Ulimits':[{'Name':'memlock','Soft':-1,'Hard':-1},{'Name':'stack','Soft':67108864,'Hard':67108864}]},Config={'Cmd':command,'Entrypoint':None,'Env':env},Mounts=mounts)
        args=type('Args',(),dict(alloc=str(alloc),run=self.plan['run'],chip=0,owner='BEV public TEST direct baseline',purpose='fixture',proof=str(host/'CLAIM.json')))()
        with mock.patch.object(adapter,'utc',return_value='2026-11-02T11:00:00Z'):adapter.claim(args)
        args.claim=str(host/'CLAIM.json');args.proof=str(host/'RELEASE.json');args.container='nga-test-public-a1';args.container_id='cid'
        with mock.patch.object(adapter,'docker_inspect',return_value=actual),mock.patch.object(adapter,'live_chip_conflict',return_value=False),mock.patch.object(adapter,'utc',return_value='2026-11-02T11:01:01Z'):adapter.release(args)
        self.write(out/'COMPLETE.json',dict(schema='bev-public-test-completion-v1',attempt=1,exit_code=0,rows=6518,outcomes={'ok':6518},items=inventory,plan_sha256=planpin,scientific_acceptance=False,test_read=True))
        self.write(run/'EXIT.json',dict(exit_code=0,attempt=1,plan_sha256=planpin))
        self.write(host/'EXIT.json',dict(exit_code=0,container_id='cid',runner_terminal_matches=True,container_exit_code=0,utc_seconds=C.timestamp('2026-11-02T11:01:02Z')))
        self.write(host/'LAUNCH_RECEIPT.json',dict(container_id='cid',plan_sha256=planpin,command=command))
        self.write(host/'LAUNCH_SPEC.json',dict(plan_sha256=planpin,command=cli))
        self.write(self.cp,self.cpuconfig)
        self.review.update(approved_plan_sha256=planpin,cpu_config_sha256=E.digest(self.cp))
        self.review['hashes'][str(self.pp)]=planpin;self.write(self.rp,self.review)
        supervisor=['/usr/bin/python3.12','-B','-P',self.plan['code']['host']['path'],'supervise','--plan',str(self.pp),'--sha256',planpin,'--review',str(self.rp),'--review-sha256',E.digest(self.rp),'--attempt','1']
        self.write(host/'START_INTENT.json',{'command':supervisor,'utc_seconds':C.timestamp('2026-11-02T10:59:59Z')})
        self.write(host/'SERVICE.json',{'command':supervisor,'pid':777})
        self.cpuconfig['_verified_config_sha256']=E.digest(self.cp)
        def remote(cmd):
            if cmd[0]=='/usr/bin/python3.12':return {'same_supervisor':False}
            if cmd[:3]==['docker','image','inspect']:return [image]
            if cmd[:2]==['docker','info']:return {'DefaultRuntime':'runc','CgroupVersion':'2'}
            return [actual]
        return host,actual,remote
    def test_full_success_lifecycle_consumption_then_tamper_rejection(self):
        host,actual,remote=self.lifecycle_fixture()
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            result=self.C.consume(self.cpuconfig)
            self.assertEqual(result['metrics']['all']['n'],6518);self.assertNotIn('references',result)
            item=R.item_path(Path(self.plan['out']),self.rows[0]['id']);item.write_text('{}')
            with self.assertRaisesRegex(ValueError,'item changed'):self.C.consume(self.cpuconfig)
    def test_effective_policy_mount_device_command_and_environment_mutations_rejected(self):
        host,actual,remote=self.lifecycle_fixture();original=copy.deepcopy(actual)
        mutations=[lambda x:x['Mounts'].append(dict(Type='bind',Source=str(self.cpu),Destination='/gold',RW=False,Mode='ro',Propagation='rprivate')),
                   lambda x:x['HostConfig']['Devices'].append(dict(PathOnHost='/dev/davinci7',PathInContainer='/dev/davinci7',CgroupPermissions='rwm')),
                   lambda x:x['Config']['Cmd'].extend(['--unreviewed','flag']),
                   lambda x:x['Config']['Env'].append('UNREVIEWED=1'),
                   lambda x:x['HostConfig'].update(Privileged=True),
                   lambda x:x['Config'].update(Entrypoint=['bash','-c']),
                   lambda x:x['HostConfig'].update(NetworkMode='host')]
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            for mutate in mutations:
                actual.clear();actual.update(copy.deepcopy(original));mutate(actual)
                with self.assertRaises((ValueError,RuntimeError)):self.C.lifecycle(self.cpuconfig,self.plan)
    def test_release_hash_generation_transition_schema_and_missing_claim_rejected(self):
        host,actual,remote=self.lifecycle_fixture();original=json.loads((host/'RELEASE.json').read_text())
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            for field,value in [('claim_sha256','0'*64),('schema','untrusted'),('run','another')]:
                d=copy.deepcopy(original);d[field]=value;self.write(host/'RELEASE.json',d)
                with self.assertRaises(ValueError):self.C.lifecycle(self.cpuconfig,self.plan)
            d=copy.deepcopy(original);d['allocation_before']['allocation'][0]['claimed_utc']='replacement'
            d['allocation_before_sha256']=hashlib.sha256((json.dumps(d['allocation_before'],indent=2,sort_keys=True)+'\n').encode()).hexdigest()
            self.write(host/'RELEASE.json',d)
            with self.assertRaisesRegex(ValueError,'generation'):self.C.lifecycle(self.cpuconfig,self.plan)
            self.write(host/'RELEASE.json',original);(host/'CLAIM.json').unlink()
            self.assertIsNone(self.C.lifecycle(self.cpuconfig,self.plan))
    def test_original_review_supervisor_and_generation_times_rejected(self):
        host,actual,remote=self.lifecycle_fixture()
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            actual['State']['StartedAt']='2026-11-02T10:00:00Z'
            with self.assertRaisesRegex(ValueError,'generation times'):self.C.lifecycle(self.cpuconfig,self.plan)
            actual['State']['StartedAt']='2026-11-02T11:00:01Z'
            original=(self.rp).read_bytes();self.rp.write_text('{}')
            with self.assertRaisesRegex(ValueError,'activation review'):self.C.lifecycle(self.cpuconfig,self.plan)
            self.rp.write_bytes(original)
            service=json.loads((host/'SERVICE.json').read_text());service['command'][-1]='2';self.write(host/'SERVICE.json',service)
            with self.assertRaisesRegex(ValueError,'service binding'):self.C.lifecycle(self.cpuconfig,self.plan)
    def test_consumer_missing_dependency_pin_and_gold_mismatch(self):
        del self.cpuconfig['files'][self.plan['inputs']['requests']['path']];self.write(self.cp,self.cpuconfig)
        with self.assertRaisesRegex(ValueError,'coverage'):self.C.verify_config(self.cp,E.digest(self.cp))

    def compatibility_fixture(self):
        # Temporary test evidence only; never an actual independent approval.
        host,actual,remote=self.lifecycle_fixture()
        newroot=self.root/'compatibility';newroot.mkdir()
        newconsumer=newroot/'consume.py';newconsumer.write_bytes(self.consumer.read_bytes())
        new=C.module(newconsumer,'fixture_compatibility_cpu')
        config=copy.deepcopy(self.cpuconfig);config.pop('_verified_config_sha256')
        config['compatibility']=dict(kind='docker_bind_order_only',original_config=self.pin(self.cp),
                                    original_consumer=self.pin(self.consumer),original_review=self.pin(self.rp))
        for p in (self.cp,self.rp,newconsumer):config['files'][str(p)]=E.digest(p)
        cp=newroot/'config.json';self.write(cp,config)
        verified=new.verify_config(cp,E.digest(cp))
        review=dict(schema='bev-public-cpu-compatibility-review-v1',verdict='PASS',consumption_authorized=True,
                    scientific_acceptance=False,candidate_selection_allowed=False,scope='public_release_test',
                    compatibility_kind='docker_bind_order_only',plan_sha256=config['plan_sha256'],
                    cpu_config_sha256=E.digest(cp),consumer_sha256=E.digest(newconsumer),
                    original=config['compatibility'],hashes=dict(config['files']),test_fixture_only=True)
        rp=newroot/'TEST_ONLY_REVIEW.json';self.write(rp,review)
        return new,verified,rp,review,host,actual,remote

    def test_bind_reordering_passes_but_cli_order_is_fixed(self):
        host,actual,remote=self.lifecycle_fixture()
        actual['HostConfig']['Binds'].reverse()
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            self.assertIsNotNone(self.C.lifecycle(self.cpuconfig,self.plan))
            spec=C.load(host/'LAUNCH_SPEC.json');positions=[i+1 for i,x in enumerate(spec['command']) if x=='-v']
            a,b=positions[:2];spec['command'][a],spec['command'][b]=spec['command'][b],spec['command'][a]
            self.write(host/'LAUNCH_SPEC.json',spec)
            with self.assertRaisesRegex(ValueError,'launch prefix'):self.C.lifecycle(self.cpuconfig,self.plan)

    def test_bind_extra_duplicate_missing_different_and_mount_mutations_reject(self):
        host,actual,remote=self.lifecycle_fixture();original=copy.deepcopy(actual)
        mutations=[lambda x:x['HostConfig']['Binds'].append('/gold:/gold:ro'),
                   lambda x:x['HostConfig']['Binds'].append(x['HostConfig']['Binds'][0]),
                   lambda x:x['HostConfig']['Binds'].__setitem__(1,x['HostConfig']['Binds'][0]),
                   lambda x:x['HostConfig']['Binds'].pop(),
                   lambda x:x['HostConfig']['Binds'].__setitem__(0,'/different:/different:ro'),
                   lambda x:x['HostConfig'].update(Binds=None),
                   lambda x:x['HostConfig'].update(Mounts=[{'Target':'/extra'}]),
                   lambda x:x['Mounts'][0].update(Mode='rw'),
                   lambda x:x['Mounts'][0].update(RW=True),
                   lambda x:x['Mounts'][0].update(Propagation='shared')]
        with mock.patch.object(self.C,'remote_json',side_effect=remote):
            for i,mutate in enumerate(mutations):
                with self.subTest(mutation=i):
                    actual.clear();actual.update(copy.deepcopy(original));mutate(actual)
                    with self.assertRaises((ValueError,RuntimeError)):self.C.lifecycle(self.cpuconfig,self.plan)

    def test_compatibility_requires_separate_admission_and_preserves_both_reviews(self):
        new,d,rp,review,host,actual,remote=self.compatibility_fixture()
        with self.assertRaisesRegex(ValueError,'compatibility review required'):new.consume(d)
        new.admit_compatibility(d,rp,E.digest(rp));actual['HostConfig']['Binds'].reverse()
        with mock.patch.object(new,'remote_json',side_effect=remote):
            result=new.consume(d)
            self.assertEqual(result['metrics']['all']['n'],6518)
            self.assertEqual(result['inputs'][str(rp)],E.digest(rp))
            self.assertEqual(result['inputs'][str(self.rp)],E.digest(self.rp))
            self.assertEqual(result['inputs'][str(self.cp)],E.digest(self.cp))
            self.assertEqual(result['plan_sha256'],self.cpuconfig['plan_sha256'])
            self.assertFalse(result['scientific_acceptance'])
            rp.write_text('{}')
            with self.assertRaisesRegex(ValueError,'review hash'):new.consume(d)

    def test_compatibility_rejects_wrong_admission_identity_scope_and_coverage(self):
        new,d,rp,review,*_=self.compatibility_fixture()
        for field,value in [('schema','unknown'),('verdict','FAIL'),('consumption_authorized',False),
                            ('scientific_acceptance',True),('candidate_selection_allowed',True),
                            ('scope','train_derived_dev'),('compatibility_kind','anything'),
                            ('cpu_config_sha256','0'*64),('consumer_sha256','0'*64),
                            ('plan_sha256','0'*64),('original',{}),('hashes',{})]:
            with self.subTest(field=field):
                changed=copy.deepcopy(review);changed[field]=value;self.write(rp,changed)
                with self.assertRaises(ValueError):new.admit_compatibility(d,rp,E.digest(rp))

    def test_compatibility_preserves_original_contract_and_launch_review(self):
        new,d,rp,review,host,actual,remote=self.compatibility_fixture()
        for field,value in [('plan_sha256','0'*64),('gold',str(self.root/'other.jsonl')),
                            ('poll_interval_seconds',1),('scope','train_derived_dev')]:
            with self.subTest(field=field):
                changed=copy.deepcopy(d);changed[field]=value
                with self.assertRaisesRegex(ValueError,'original CPU contract'):new.compatibility_inputs(changed)
        changed=copy.deepcopy(d);del changed['files'][str(self.consumer)]
        with self.assertRaisesRegex(ValueError,'pin coverage'):new.compatibility_inputs(changed)
        new.admit_compatibility(d,rp,E.digest(rp))
        # Even byte-identical launch review moved to another path is not the original receipt.
        other=self.root/'other-review.json';other.write_bytes(self.rp.read_bytes())
        for name in ('START_INTENT.json','SERVICE.json'):
            value=C.load(host/name);value['command'][10]=str(other);self.write(host/name,value)
        with mock.patch.object(new,'remote_json',side_effect=remote):
            with self.assertRaisesRegex(ValueError,'original launch review'):new.consume(d)

if __name__=='__main__':unittest.main()
