"""All twelve synthetic roles emitted by actual frozen evaluator and accepted wrappers.
No model backend imports or actual DEV/TEST reads; only temporary synthetic populations.
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('integration_fixture',HERE/'fixtures.py');FX=importlib.util.module_from_spec(spec);spec.loader.exec_module(FX);M=FX.M
REPO=HERE.parents[7] # overwritten by explicit origin below
REPO=Path(M.obj(HERE/'SOURCE-ORIGINS.json')['legacy_consumer']['path']).parents[3]
PRODUCER=REPO/'.local/releases/engineering-base-rc1/tasks/execution/matched-k0-fix/producer.py'
WRAPPER=REPO/'tools/functional_dev/phased/phase_wrapper.py'
CLOSURE=Path(M.obj(HERE/'config.json')['closure'])
M.sha=lambda p:M.L.digest(Path(p).read_bytes())
M.obj=lambda p:json.loads(Path(p).read_bytes())

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value

class Tests(unittest.TestCase):
    def test_actual_frozen_all_twelve_roles(self):
        with tempfile.TemporaryDirectory(dir=HERE/'scratch') as tmp:
            root=Path(tmp);c,inspections=FX.build(root)
            sys.path[:0]=[str(CLOSURE/'r3_code'),str(CLOSURE/'r0_code')]
            for name in ('common','split','decision','thresholds','metrics'):
                load(name,CLOSURE/'r0_code'/(name+'.py'))
            for name in ('core_r3','variants_r3','degenerate_r3','provenance_r3'):
                load(name,CLOSURE/'r3_code'/(name+'.py'))
            import core_r3 as C, full_eval_r3 as F, testlock_r3 as TL, prechecks_r3 as PC, eval_r3 as E
            P=load('frozen_integration_producer',PRODUCER);W=load('frozen_integration_adapter',WRAPPER)
            real_load=C.load_partition;real_path=C.partition_path;real_manifest=PC.check_kev_manifest
            data=root/'populations';manifest={'suites':{}}
            for label,n in M.COUNTS.items():
                suite,part=label.split('/');path=data/suite/(part+'.jsonl')
                FX.jsonl(path,[FX.row(i,suite) for i in range(n)])
                c['new_contract']['data_pins'][str(path)]=M.sha(path)
            c['new_contract']['expected_populations']=dict(M.COUNTS)
            train=[FX.row(i,'decision-v7') for i in range(24)];FX.jsonl(data/'decision-v7/train.jsonl',train)
            for path in data.glob('*/*.jsonl'):
                suite=path.parent.name;split=path.name.split('.')[0];kind='variants' if '.variants.' in path.name else 'clean'
                manifest['suites'].setdefault(suite,{'partitions':{}})['partitions'].setdefault(split,{'outputs':{}})['outputs'][kind]={'path':str(path.relative_to(data)),'sha256':M.sha(path)}
            FX.put(data/'manifest.json',manifest)
            loads=[]
            def partition_path(suite,split,variants=False,kev_dir=None):
                self.assertIn(split,('train','dev','calibration'));return real_path(suite,split,variants,str(data))
            def partition_load(suite,split,*args,**kwargs):
                self.assertIn(split,('train','dev','calibration'));loads.append((suite,split));kwargs['kev_dir']=str(data);return real_load(suite,split,*args,**kwargs)
            c['closure']=str(CLOSURE);c['source_pins']={str(path):M.sha(path) for sub in ('r0_code','r3_code') for path in (CLOSURE/sub).glob('*.py')};c['closure_manifest_sha256']=M.sha(CLOSURE/'manifest.json')
            c['producer_py_sha256']=M.sha(PRODUCER);c['producer_config_sha256']=M.sha(PRODUCER.with_name('config.json'));c['adapter_wrapper_sha256']=M.sha(WRAPPER)
            for info in inspections.values():
                base='nga.rc1.matched-k0' in info['Config']['Labels']
                info['Mounts']=[m for m in info['Mounts'] if not (m['Destination'].endswith('fixture-closure') or m['Destination'].endswith('fixture-closure/r3_code') or m['Destination'] in ('/run/packet','/run/phase_wrapper.py','/mnt/cephfs/xingchao/experiments/jev/r0_code'))]
                info['Mounts'] += [{'Source':str(CLOSURE/'r0_code'),'Destination':'/mnt/cephfs/xingchao/experiments/jev/r0_code','RW':False}]
                info['Mounts'] += ([{'Source':str(CLOSURE),'Destination':str(CLOSURE),'RW':False},{'Source':str(PRODUCER.parent),'Destination':'/run/packet','RW':False}] if base else
                    [{'Source':str(CLOSURE/'r3_code'),'Destination':str(CLOSURE/'r3_code'),'RW':False},{'Source':str(WRAPPER),'Destination':'/run/phase_wrapper.py','RW':False}])
            with contextlib.ExitStack() as stack:
                # Synthetic test payloads only: skip durability latency, retain actual store bytes/receipts.
                stack.enter_context(patch.object(os,'fsync',return_value=None))
                for target,key,value in [(C,'partition_path',partition_path),(C,'load_partition',partition_load),
                    (PC,'check_kev_manifest',lambda paths,run_dir=None,hashes=None:real_manifest(paths,run_dir,hashes,str(data))),
                    (F.TimedScorer,'reserved_gib',lambda self:None)]:stack.enter_context(patch.object(target,key,value))
                stack.enter_context(patch.dict(sys.modules,{'torch':None,'torch_npu':None,'transformers':None}))
                for model in c['models']:
                    for lane in [None]+[x for x in c['lanes'] if x['baseline_id']==model['id']]:
                        base=lane is None;rid=model['id'] if base else lane['lane'];d=Path(c['k0_root'])/rid if base else Path(c['adapter_root'])/('full-'+rid);out=d/'result'
                        old=M.obj(out/'INFERENCE-READY.json');desc=old['descriptor'];desc['model_path']=model['model']['path']
                        identity=old['identity'] if base else {**old['inference_header']['model'],'files':{}}
                        shutil.rmtree(out);out.mkdir()
                        def scorer(rows,mode='full'):
                            result=[]
                            for i,r in enumerate(rows):
                                s=[0.]*len(r['levels']) if i%4==0 or mode!='full' else [float(j) for j in range(len(r['levels']))]
                                result.append(s)
                            return result
                        scorer.describe=lambda:desc
                        with patch.object(TL,'model_identity',return_value=identity),patch.object(E,'make_score_fn',return_value=scorer),contextlib.redirect_stdout(io.StringIO()):
                            if base:
                                pc=copy.deepcopy(P.CONFIG);pc['models']=c['models'];pc['data_pins']=c['new_contract']['data_pins']
                                with patch.object(P,'CONFIG',pc):
                                    P.run('infer',rid,str(out));P.run('score',rid,str(out))
                            else:
                                a=type('Args',(),{'out':str(out),'model':model['model']['path'],'adapter':lane['new_adapter'],'limit':0,'phase':'infer'})()
                                W.run(a,F,E)
                                hand=M.obj(out/'INFERENCE-READY.json');hand['out']='/run/output/result';FX.put(out/'INFERENCE-READY.json',hand)
                                a.phase='score'
                                # Wrapper validates its own output path, so use actual host path for its CPU call;
                                # then normalize ONLY the container namespace path and bind that exact final receipt.
                                hand['out']=str(out);FX.put(out/'INFERENCE-READY.json',hand)
                                W.run(a,F,E)
                                hand['out']='/run/output/result';FX.put(out/'INFERENCE-READY.json',hand)
                                report=M.obj(out/'report.json');report['header']['phase_separation']['inference_receipt_sha256']=M.sha(out/'INFERENCE-READY.json');FX.put(out/'report.json',report)
                        if base:
                            h=M.obj(out/'INFERENCE-READY.json');ev={'inference_sha256':M.sha(out/'INFERENCE-READY.json'),'stores':h['stores']}
                            for phase in ('infer','score'):
                                e=M.obj(d/(phase+'-EXIT.json'));e['artifact_evidence']=dict(ev)
                                if phase=='score':e['artifact_evidence']['report_sha256']=M.sha(out/'clean-report.json')
                                FX.put(d/(phase+'-EXIT.json'),e)
            M._accesses.clear()
            result,code=M.assemble(M.Consumer(c,inspector=inspections.__getitem__,allow_fixture=True))
            FX.put(HERE/'FROZEN-INTEGRATION-RESULT.json',result)
            self.assertEqual(code,0,[(x['role'],x.get('detail')) for x in result['operands']])
            self.assertEqual(len(result['operands']),12)
            self.assertFalse(any(split=='test' for _,split in loads))

if __name__=='__main__':unittest.main(verbosity=2)
