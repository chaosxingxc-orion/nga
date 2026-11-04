"""Real native operand/receipt consumer integration; synthetic logits only."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import typed_qwen_execution_v1 as C
from tools import typed_qwen_execution_consume_v1 as V

class TypedExecution(unittest.TestCase):
    def test_configuration_bounds_and_gold_mount_exclusion(self):
        source=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/typed_qwen_execution_08b_20261104_v1/PLAN.json')
        d=C.read(source);c=C.read(d['config']['path']);C.config_validate(c)
        for key,value in [('workers',0),('workers',True),('chunk_size',0),('protocol','bev')]:
            changed=copy.deepcopy(c);changed['typed'][key]=value
            with self.assertRaises(ValueError):C.config_validate(changed)
        mounts=C.mounts(d,source)
        for key in ('rich_gold','scorer'):
            self.assertFalse(any(Path(d['typed'][key]['path']).is_relative_to(m['source']) for m in mounts))
        changed=copy.deepcopy(d);changed['files'][str(source.parent)]= '0'*64
        with self.assertRaisesRegex(ValueError,'CPU-only'):C.mounts(changed,source)

    def test_cpu_lifecycle_and_native_operand_scoring(self):
        import numpy as np
        source=Path('/mnt/cephfs/xingchao/experiments/jev/r3_runs/typed_qwen_execution_08b_20261104_v1/PLAN.json')
        d=C.read(source);N=C.module(d['modules']['native']);X=C.module(d['modules']['panel']);P=C.module(d['modules']['protocol']);T=C.module(d['modules']['typed']);H=C.module(d['modules']['host'])
        all_items=X.rows(d['population']['items']['path']);all_reqs=X.rows(d['population']['requests']['path']);all_gold=X.rows(d['typed']['rich_gold']['path'])
        # One entire published workflow includes all three question types.
        count=5;items=all_items[:count];requests=all_reqs[:count];rich=all_gold[:count]
        reference=N.reference(Path(d['upstream']['root']));N.reference=lambda *a,**kw:reference
        with tempfile.TemporaryDirectory(prefix='typed-e2e-') as td:
            root=Path(td);out=root/'output';h=out/'host_attempts/1';a=out/'attempts/1';h.mkdir(parents=True);a.mkdir(parents=True)
            def write(p,v):X.write(p,v)
            def lines(name,rows):
                p=root/name;p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows));return {'path':str(p),'sha256':C.sha(p)}
            d=copy.deepcopy(d);d['out']=str(out);d['run']='fixture-only';d['typed']['rich_gold']=lines('rich.jsonl',rich)
            pop=d['population'];pop['count']=count;pop['items']=lines('items.jsonl',items);pop['requests']=lines('requests.jsonl',requests);pop['gold']=lines('gold.jsonl',[dict(i=i,qid=x['qid'],y=x['y'],request_sha256=P.request_hash(x)) for i,x in enumerate(items)])
            contract=P.make_contract(items,source_sha256=pop['source']['sha256'],model_sha256=d['model_sha256'],runtime_protocol_sha256=pop['protocol_binding_sha256']);write(root/'CONTRACT.json',contract);pop['contract']={'path':str(root/'CONTRACT.json'),'sha256':C.sha(root/'CONTRACT.json')};pop['contract_sha256']=P.sha256_value(contract);pop['ordered_inputs_sha256']=N.digest(requests)
            view=copy.deepcopy(d);view.update(contract_sha256=pop['contract_sha256'],protocol_binding_sha256=pop['protocol_binding_sha256'],ordered_inputs_sha256=pop['ordered_inputs_sha256'])
            predictions=[];receipts=[]
            for req in requests:
                logits=np.zeros(248320,dtype=np.float32);logits[req['label_ids']]=np.linspace(-2,2,len(req['label_ids']),dtype=np.float32)
                pred=N.read_logits(req,logits,mode='transformers_full_labels',contract_sha256=pop['contract_sha256'],prepared_sha256=N.digest(req),ref=reference);predictions.append(pred)
                dest=out/'items'/f'{req["i"]:06d}';dest.mkdir(parents=True)
                write(dest/'record.json',dict(schema='bev-native-compact-v1',model_sha256=d['model_sha256'],contract_sha256=pop['contract_sha256'],prediction=pred,forwards=1));write(dest/'COMMITTED.json',{'record.json':C.sha(dest/'record.json')});receipts.append(C.sha(dest/'COMMITTED.json'))
            pin='a'*64;path=root/'PLAN.json';container='f'*64;cmd=H.command({**d,'runtime':d['modules']['runtime'],'image_sha256':d['image']},str(path),pin,1)
            write(h/'CLAIM.json',dict(schema='r3-resource-claim-v1',run=d['run'],chip=d['chip']))
            write(h/'RELEASE.json',dict(schema='r3-resource-release-v1',run=d['run'],chip=d['chip'],claim_sha256=C.sha(h/'CLAIM.json'),container_id=container,exit_code=0,scientific_acceptance=False,container=d['container']+'-a1'))
            write(h/'EXIT.json',dict(exit_code=0,container_exit_code=0,runner_terminal_matches=True,plan_sha256=pin,attempt=1,scientific_acceptance=False,container_id=container))
            write(a/'EXIT.json',dict(exit_code=0,attempt=1,plan_sha256=pin,test_read=True,scientific_acceptance=False))
            write(h/'LAUNCH_SPEC.json',dict(plan_sha256=pin,command=cmd));write(h/'LAUNCH_RECEIPT.json',dict(plan_sha256=pin,attempt=1,container_id=container,command=cmd[cmd.index(d['image'])+1:]))
            write(a/'report.json',dict(schema='bev-native-panel-completion-v1',attempt=1,plan_sha256=pin,scientific_acceptance=False,model_sha256=d['model_sha256'],contract_sha256=pop['contract_sha256'],ordered_inputs_sha256=pop['ordered_inputs_sha256'],adaptive='NOT_EVALUATED',forwards_per_new_item=1,completed=count,computed=count,reused=0,receipts_sha256=N.digest(receipts)))
            # Entry pin validation is separately exercised on actual plans; all downstream joins,
            # lifecycle files, saved operands and native metric arithmetic execute here.
            d['modules']['consumer']={'path':str(Path(V.__file__).resolve()),'sha256':C.sha(V.__file__)}
            def modules(ref):
                if ref==d['modules']['native']:return N
                return C.module(ref)
            with patch.object(V.C,'verify',return_value=d),patch.object(V.C,'plan_legacy_view',return_value=(view,None,N)),patch.object(V.C,'module',side_effect=modules):
                result=V.consume(str(path),pin,1)
                expected=T.score(rich,predictions,scorer=d['typed']['scorer']['path'],contract_sha256=pop['contract_sha256'],workers=1,chunk_size=1)
                self.assertEqual(result['strict'],expected['strict']);self.assertEqual(result['strict']['n'],count)
                bad=copy.deepcopy(rich);bad[0]['request_sha256']='0'*64;lines('rich.jsonl',bad)
                with self.assertRaisesRegex(ValueError,'rich gold join'):V.consume(str(path),pin,1)
                lines('rich.jsonl',rich)
                corrupt=copy.deepcopy(predictions[0]);corrupt['first_index']=999
                dest=out/'items/000000';write(dest/'record.json',dict(schema='bev-native-compact-v1',model_sha256=d['model_sha256'],contract_sha256=pop['contract_sha256'],prediction=corrupt,forwards=1));write(dest/'COMMITTED.json',{'record.json':C.sha(dest/'record.json')})
                with self.assertRaises(ValueError):V.consume(str(path),pin,1)
                write(dest/'record.json',dict(schema='bev-native-compact-v1',model_sha256=d['model_sha256'],contract_sha256=pop['contract_sha256'],prediction=predictions[0],forwards=1));write(dest/'COMMITTED.json',{'record.json':C.sha(dest/'record.json')})
                write(h/'EXIT.json',dict(exit_code=1))
                with self.assertRaises(ValueError):V.consume(str(path),pin,1)

if __name__=='__main__':unittest.main()
