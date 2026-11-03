import copy
import json
import tempfile
import unittest
from pathlib import Path
from tools import bev_native_shard_runner as R
from tools import bev_native_shard_contract as S


class Runner(unittest.TestCase):
    def fixture(self, root):
        from tools.test_bev_native_shard_contract import Shards
        population, rows, _ = Shards().fixture()
        inputs = root / 'requests.jsonl'
        inputs.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        binding = population['binding']
        binding['inputs'] = {'path': str(inputs), 'sha256': R.file_sha(inputs)}
        binding['ordered_inputs_sha256'] = R.digest(rows)
        binding['model_sha256'] = R.digest({'/model': 'a'*64})
        parent = dict(schema='bev-native-panel-host-v1', scope='public_fixed_base_test',
                      scientific_acceptance=False, candidate_test_authority=False,
                      candidate_selection_allowed=False, batch_size=1,max_length=8192,adapter=None,
                      count=4,inputs=binding['inputs'],model_files={'/model':'a'*64},
                      model_sha256=binding['model_sha256'],contract_sha256=binding['contract_sha256'],
                      protocol_binding_sha256=binding['source_protocol_binding_sha256'],
                      ordered_inputs_sha256=binding['ordered_inputs_sha256'])
        parent_path=root/'parent.json';R.write_json(parent_path,parent)
        binding['parent_population']={'path':str(parent_path),'sha256':R.file_sha(parent_path)}
        for shard in population['shards']:shard.update(binding)
        path=root/'population.json';R.write_json(path,population)
        ref={'path':str(path),'sha256':R.file_sha(path)}
        def predictor(row):
            return dict(i=row['i'],qid=row['qid'],request_sha256=row['request_sha256'],
                        input_sha256=R.digest(row),contract_sha256='contract',value=row['i']*2)
        def validator(pred,row,binding):
            if pred['value']!=row['i']*2:raise ValueError('arithmetic differs')
        return ref,rows,population,predictor,validator

    def test_nonzero_global_ordinals_and_logs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root)
            out=root/'out';result=R.run_shard(ref,1,out,predict,validate,metadata=lambda:{'reserved_gib':2})
            self.assertEqual(result['computed'],2)
            self.assertEqual(sorted(x.name for x in (out/'items').iterdir()),['000002','000003'])
            events=[json.loads(x) for x in (out/'attempts/1/runtime.log').read_text().splitlines()]
            self.assertEqual(events[0]['stage'],'startup');self.assertEqual(events[-1]['stage'],'complete')
            self.assertNotIn('input_ids',str(events));self.assertEqual(next(e for e in events if e['stage']=='progress')['chips'],1)
            self.assertFalse(result['scientific_acceptance']);self.assertFalse(result['execution_authorized'])

    def test_failure_resume_reuses_committed_item(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root);out=root/'out'
            def fail(row):
                if row['i']==3:raise RuntimeError('secret-input-must-not-be-logged')
                return predict(row)
            with self.assertRaises(RuntimeError):R.run_shard(ref,1,out,fail,validate)
            self.assertEqual(R.read_json(out/'attempts/1/EXIT.json')['exit_code'],1)
            self.assertNotIn('secret-input',(out/'attempts/1/runtime.log').read_text())
            called=[]
            def track(row):called.append(row['i']);return predict(row)
            result=R.run_shard(ref,1,out,track,validate,attempt=2)
            self.assertEqual(called,[3]);self.assertEqual((result['computed'],result['reused']),(1,1))
            with self.assertRaises(ValueError):R.run_shard(ref,1,out,predict,validate,attempt=3)

    def test_partial_corrupt_extra_and_arithmetic(self):
        for attack in ('partial','modified','resigned','foreign_dir'):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as td:
                root=Path(td);ref,rows,p,predict,validate=self.fixture(root);out=root/'out'
                def fail(row):
                    if row['i']==3:raise RuntimeError('stop')
                    return predict(row)
                with self.assertRaises(RuntimeError):R.run_shard(ref,1,out,fail,validate)
                item=out/'items/000002'
                if attack=='partial':(item/'COMMITTED.json').unlink()
                elif attack=='foreign_dir':(out/'items/000000').mkdir()
                else:
                    r=R.read_json(item/'record.json');r['prediction']['value']=99;R.write_json(item/'record.json',r)
                    if attack=='resigned':
                        c=R.read_json(item/'COMMITTED.json');c['record_sha256']=R.file_sha(item/'record.json');R.write_json(item/'COMMITTED.json',c)
                with self.assertRaises(ValueError):R.run_shard(ref,1,out,predict,validate,attempt=2)

    def test_immutable_population_parent_and_tokens(self):
        for attack in ('population','parent','tokens','parent_model'):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as td:
                root=Path(td);ref,rows,p,predict,validate=self.fixture(root)
                if attack=='population':Path(ref['path']).write_text('{}')
                elif attack=='parent':Path(p['binding']['parent_population']['path']).write_text('{}')
                elif attack=='tokens':
                    p['shards'][1]['input_tokens']=1;R.write_json(ref['path'],p);ref['sha256']=R.file_sha(ref['path'])
                else:
                    p['binding']['model_sha256']='foreign'
                    for s in p['shards']:s['model_sha256']='foreign'
                    R.write_json(ref['path'],p);ref['sha256']=R.file_sha(ref['path'])
                with self.assertRaises(ValueError):R.run_shard(ref,1,root/'out',predict,validate)

    def test_strict_json_duplicate_nonfinite(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','{"x":1e999}','{"x":-1e999}','{"x":[{"y":1e999}]}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):R.strict_loads(raw)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root)
            f=Path(p['binding']['inputs']['path']);f.write_text('{"i":0,"i":1}\n')
            # Supply hash of malicious file: strict decoder must reject independent of hash.
            b=copy.deepcopy(p['binding']);b['inputs']['sha256']=R.file_sha(f)
            with self.assertRaises(ValueError):R.load_requests(b)

    def test_bool_identity_and_generation_reuse_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root)
            for sid in (True,2,-1):
                with self.assertRaises(ValueError):R.load_population(ref,sid)
            out=root/'out';R.run_shard(ref,1,out,predict,validate)
            with self.assertRaises(ValueError):R.run_shard(ref,0,out,predict,validate)

    def test_prior_terminal_exact_identity_scope_and_generation(self):
        attacks = [('attempt', True), ('shard_id', True), ('scientific_acceptance', True),
                   ('execution_authorized', True), ('generation_sha256', 'foreign')]
        for field, value in attacks:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root=Path(td);ref,rows,p,predict,validate=self.fixture(root);out=root/'out'
                def fail(row):
                    if row['i']==3:raise RuntimeError('stop')
                    return predict(row)
                with self.assertRaises(RuntimeError):R.run_shard(ref,1,out,fail,validate)
                terminal=out/'attempts/1/EXIT.json';old=R.read_json(terminal)
                R.write_json(terminal,{**old,field:value})
                called=[]
                with self.assertRaises(ValueError):R.run_shard(ref,1,out,lambda r:called.append(r),validate,attempt=2)
                self.assertEqual(called,[])
                self.assertEqual(R.read_json(out/'attempts/2/EXIT.json')['exit_code'],1)
                self.assertIn('startup_failure',(out/'attempts/2/runtime.log').read_text())

    def test_startup_validation_failure_record_and_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root);out=root/'out'
            population=Path(ref['path']);original=population.read_bytes();population.write_text('{}')
            called=[]
            with self.assertRaises(ValueError):R.run_shard(ref,1,out,lambda r:called.append(r),validate)
            self.assertEqual(called,[])
            terminal=R.read_json(out/'attempts/1/EXIT.json')
            self.assertEqual(terminal['exit_code'],1);self.assertFalse(terminal['scientific_acceptance'])
            self.assertEqual(terminal['generation_sha256'],R.digest({'population':ref,'shard_id':1}))
            self.assertIn('startup_failure',(out/'attempts/1/runtime.log').read_text())
            population.write_bytes(original)
            result=R.run_shard(ref,1,out,predict,validate,attempt=2)
            self.assertEqual((result['computed'],result['reused']),(2,0))

    def test_lock_excludes_concurrent_runner(self):
        import fcntl
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ref,rows,p,predict,validate=self.fixture(root);out=root/'out';out.mkdir()
            with (out/'runner.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):R.run_shard(ref,1,out,predict,validate)

if __name__=='__main__':unittest.main()
