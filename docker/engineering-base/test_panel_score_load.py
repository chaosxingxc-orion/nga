"""Targeted saved-panel equivalence and corruption tests; temporary outputs only."""
import builtins, hashlib, json, sys, unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import panel_score as S
from test_panel_bridge import Bridge, sha, put

class ReadOnce(Bridge):
    def setUp(self):
        super().setUp()
        self.manifest_path = self.baseline()
        self.manifest = json.loads(self.manifest_path.read_bytes())
        self.dest = Path(self.manifest['records']) / '000000'
        self.generation = {'model_sha256': self.modelpin, 'contract_sha256': self.cpin}
        self.ref = S.R.VerifiedReference.create(S.N, {'path':str(S.ROOT/'bev_native_runtime.py'), 'sha256':sha(S.ROOT/'bev_native_runtime.py')}, {'root':str(S.ROOT), 'files':{k:{'path':str(S.ROOT/'anyjev'/k),'sha256':v} for k,v in S.N.PINS.items()}})

    def new(self, dest=None, req=None, generation=None, ref=None):
        return S.panel_score_load.load_item(dest or self.dest, req or self.reqs[0], generation or self.generation, S.N, ref or self.ref, S.R)

    def score_direct(self, name):
        out = self.root/name
        c = dict(manifest=str(self.manifest_path), manifest_sha256=sha(self.manifest_path), output=str(out), workers=2, chunk_size=1)
        cp=self.root/(name+'.json'); put(cp,c); S.run(c,str(cp))
        return (out/'summary.json').read_bytes(), json.loads((out/'report.json').read_bytes())['receipts_sha256']

    def test_full_field_order_and_score_parity(self):
        for i,req in enumerate(self.reqs):
            dest=Path(self.manifest['records'])/f'{i:06d}'
            old=S.R.load_item(dest,req,self.generation,S.N,self.ref)
            new,receipt,record=self.new(dest,req)
            self.assertEqual(json.dumps(old,allow_nan=False),json.dumps(new,allow_nan=False))
            self.assertEqual(receipt,sha(dest/'COMMITTED.json'));self.assertEqual(record,sha(dest/'record.json'))
        def old_load(dest,req,generation,native,ref,replay):
            return replay.load_item(dest,req,generation,native,ref),sha(dest/'COMMITTED.json'),sha(dest/'record.json')
        with mock.patch.object(S.panel_score_load,'load_item',side_effect=old_load): old=self.score_direct('old-score')
        new=self.score_direct('new-score')
        self.assertEqual(old,new)
        summary=json.loads(new[0]); self.assertEqual([(summary['by_type'][k]['n'],summary['by_type'][k]['correct']) for k in ('choice','yes_no','score')],[(1,1),(1,1),(1,1)])
        self.assertFalse(summary['scientific_acceptance']);self.assertFalse(summary['candidate_test_authority'])

    def test_open_counts(self):
        counts=[]; reads=[]
        original=Path.open
        builtin_open=builtins.open
        def counted(path,*args,**kwargs):
            if path.parent==self.dest and path.name in ('record.json','COMMITTED.json'): counts.append(path.name)
            return wrap(original(path,*args,**kwargs),path)
        class FileProxy:
            def __init__(self,f,p): self.f=f; self.p=p
            def __enter__(self): self.f.__enter__(); return self
            def __exit__(self,*a): return self.f.__exit__(*a)
            def __getattr__(self,k): return getattr(self.f,k)
            def read(self,*a):
                data=self.f.read(*a); reads.append((self.p,len(data))); return data
            def readinto(self,b):
                n=self.f.readinto(b); reads.append((self.p,n)); return n
        def wrap(f,p):
            p=Path(p)
            return FileProxy(f,p.name) if p.parent==self.dest and p.name in ('record.json','COMMITTED.json') else f
        def counted_builtin(path,*args,**kwargs):
            p=Path(path)
            if p.parent==self.dest and p.name in ('record.json','COMMITTED.json'): counts.append(p.name)
            return wrap(builtin_open(path,*args,**kwargs),p)
        with mock.patch.object(Path,'open',counted), mock.patch('builtins.open',counted_builtin):
            S.R.load_item(self.dest,self.reqs[0],self.generation,S.N,self.ref)
            S.sha(self.dest/'COMMITTED.json')
        self.assertEqual(counts.count('record.json'),2);self.assertEqual(counts.count('COMMITTED.json'),2)
        oldbytes=sum(n for _,n in reads); counts.clear(); reads.clear()
        with mock.patch.object(Path,'open',counted), mock.patch('builtins.open',counted_builtin): self.new()
        self.assertCountEqual(counts,['record.json','COMMITTED.json'])
        self.assertEqual(len(counts),2)
        self.assertEqual(len(reads),2);self.assertEqual(oldbytes,2*sum(n for _,n in reads))

    def test_corrupt_and_shape(self):
        rp=self.dest/'record.json';cp=self.dest/'COMMITTED.json'; original_r=rp.read_bytes();original_c=cp.read_bytes()
        for mode in ('missing_commit','partial_commit','partial_record','changed_byte','foreign_receipt','extra_commit','extra_record','missing_field','wrong_model','wrong_contract','bool_forwards','bool_operand','nan_operand','bad_prediction'):
            with self.subTest(mode=mode):
                rp.write_bytes(original_r);cp.write_bytes(original_c)
                r=json.loads(original_r); c=json.loads(original_c)
                if mode=='missing_commit': cp.unlink()
                elif mode=='partial_commit':cp.write_bytes(original_c[:10])
                elif mode=='partial_record':rp.write_bytes(original_r[:10]);put(cp,{'record.json':sha(rp)})
                elif mode=='changed_byte':rp.write_bytes(original_r+b' ')
                elif mode=='foreign_receipt':put(cp,{'record.json':'0'*64})
                elif mode=='extra_commit':put(cp,{**c,'other':'x'})
                else:
                    if mode=='extra_record':r['extra']=1
                    elif mode=='missing_field':del r['forwards']
                    elif mode=='wrong_model':r['model_sha256']='0'*64
                    elif mode=='wrong_contract':r['contract_sha256']='0'*64
                    elif mode=='bool_forwards':r['forwards']=True
                    elif mode=='bool_operand':r['prediction']['label_values'][0]=True
                    elif mode=='nan_operand':r['prediction']['label_values'][0]=float('nan')
                    elif mode=='bad_prediction':r['prediction']['first_index']+=1
                    put(rp,r);put(cp,{'record.json':sha(rp)})
                with self.assertRaises((ValueError, KeyError, TypeError, FileNotFoundError)):self.new()
        rp.write_bytes(original_r);cp.write_bytes(original_c)
        with self.assertRaises(ValueError):self.new(req=self.reqs[1])
        with self.assertRaises(ValueError):self.new(ref=object())

    def test_paths_and_mutation_binding(self):
        cp=self.dest/'COMMITTED.json'; original=cp.read_bytes()
        alias=self.root/'alias';alias.symlink_to(self.dest, target_is_directory=True)
        with self.assertRaises(ValueError):self.new(dest=alias)
        cp.unlink(); target=self.root/'receipt';target.write_bytes(original);cp.symlink_to(target)
        with self.assertRaises(ValueError):self.new()
        cp.unlink();cp.write_bytes(original)
        read=Path.read_bytes
        def mutate(path):
            data=read(path)
            if path==cp: path.write_bytes(data+b' ')
            return data
        with mock.patch.object(Path,'read_bytes',mutate): pred,commit_hash,_=self.new()
        self.assertEqual(commit_hash,hashlib.sha256(original).hexdigest())
        self.assertNotEqual(commit_hash,sha(cp))
        # A changed commit snapshot cannot pass the frozen ordered receipt binding.
        with self.assertRaisesRegex(ValueError,'record receipts provenance differs'):self.score_direct('changed-receipt')
        cp.write_bytes(original)
        rp=self.dest/'record.json'; rb=rp.read_bytes()
        def mutate_record(path):
            data=read(path)
            if path==rp: path.write_bytes(data+b' ')
            return data
        with mock.patch.object(Path,'read_bytes',mutate_record): self.new()
        with self.assertRaisesRegex(ValueError,'partial/changed record'):self.score_direct('changed-record')
        self.assertEqual(json.loads((self.root/'changed-record/EXIT.json').read_bytes())['exit_code'],1)
        rp.write_bytes(rb)
        rp.unlink(); target_record=self.root/'record';target_record.write_bytes(rb);rp.symlink_to(target_record)
        with self.assertRaises(ValueError):self.new()
        rp.unlink();rp.mkdir()
        with self.assertRaises(IsADirectoryError):self.new()
        rp.rmdir();rp.write_bytes(rb)
        ancestor=self.root/'ancestor';ancestor.symlink_to(self.dest.parent, target_is_directory=True)
        with self.assertRaises(ValueError):self.new(dest=ancestor/self.dest.name)

    def test_duplicate_population_rejected(self):
        records=Path(self.manifest['records']);(records/'duplicate').mkdir()
        with self.assertRaisesRegex(ValueError,'record population differs'):self.score_direct('duplicate')
        self.assertEqual(json.loads((self.root/'duplicate/EXIT.json').read_bytes())['exit_code'],1)
        (records/'duplicate').rmdir()
        a,b=records/'000000',records/'000001'; temp=records/'temp';a.rename(temp);b.rename(a);temp.rename(b)
        with self.assertRaises(ValueError):self.score_direct('wrong-order')
        self.assertEqual(json.loads((self.root/'wrong-order/EXIT.json').read_bytes())['exit_code'],1)

# Inherited integration tests exercise separate inference/export routes; only the
# explicitly named ReadOnce methods below are run by the reproducible command.
if __name__=='__main__':
    suite=unittest.TestSuite(ReadOnce(x) for x in ('test_full_field_order_and_score_parity','test_open_counts','test_corrupt_and_shape','test_paths_and_mutation_binding','test_duplicate_population_rejected'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
