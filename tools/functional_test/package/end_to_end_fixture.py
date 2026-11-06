#!/usr/bin/env python3
"""Generated-only full-population producer integration; never opens real TEST."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import exporter, collector, integration
REF=HERE.parent/"comparison"
sys.path.insert(0,str(REF))
import consumer as N
REPO=HERE.parents[6]
ENTRY=REPO/'.local/releases/engineering-base-rc1/tasks/execution/rc1-test-host-stage/staged/rc1_trackk.py'
OLD_FIXTURE=REPO/'.local/releases/engineering-base-rc1/tasks/execution/rc1-test-reuse-fix/test_adversarial.py'

def helpers():
    # Reuse only generated fixture builders, not outcomes or old producer code.
    raw=OLD_FIXTURE.read_text();tree=ast.parse(raw)
    keep=[]
    for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)):keep.append(node)
        elif isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in ('row','FakeHardware','FrozenFixture'):keep.append(node)
    m=N.load_module('fixed_rc1_producer',ENTRY)
    namespace={'__file__':str(HERE/'fixture.py'),'m':m,'F':m.FULL,'C':m.C,'TL':m.TL,'HERE':HERE,'ENTRY':ENTRY}
    exec(compile(ast.Module(body=keep,type_ignores=[]),str(OLD_FIXTURE),'exec'),namespace)
    return namespace,m

def filepin(path):return {'path':str(Path(path).resolve()),'sha256':N.sha(path)}

def build(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    ns,m=helpers();fixture=ns['FrozenFixture']('test_real_two_phase_persistence_and_roles');fixture.setUp()
    # Retain generated data/evidence in this task instead of its temporary root.
    import shutil
    try:
        shutil.copytree(fixture.data,root/'data',dirs_exist_ok=True)
        fixture.data=root/'data';fixture.rd=root/'round';fixture.rd.mkdir(exist_ok=True)
        fixture.stack.enter_context(patch.object(m,'admitted',lambda c:identities[c['member']]))
        ids={};identities={};roster=[]
        for size in N.SIZES:
            base=root/'models'/size;base.mkdir(parents=True,exist_ok=True)
            (base/'.complete').write_text('fixture-'+size+'-revision\n');(base/'model.safetensors').write_text('GENERATED ONLY '+size)
            bid=m.TL.model_identity(str(base),None,str(fixture.rd));ids[size]=bid
        for name in N.ROLES:
            size=name.split('-')[0];base=root/'models'/size;k0=name.endswith('-base');adapter=None
            if not k0:
                adapter=root/'models'/name;adapter.mkdir(exist_ok=True);(adapter/'adapter_model.safetensors').write_text('GENERATED ONLY '+name)
            ident=m.TL.model_identity(str(base),str(adapter) if adapter else None,str(fixture.rd));identities[name]=ident
            evidence={}
            for key in (['base_inventory','tokenizer','runtime'] + ([] if k0 else ['publication','training_terminal','smoke_resume','dev_review'])):
                # Shared actual bytes for runtime and tokenizer per size, model
                # specific training/publication evidence. Every file says fixture.
                path=root/'lineage'/(size if key in ('base_inventory','tokenizer','runtime') else name)/(key+'.json')
                doc={'fixture_only':True,'kind':key,'size':size}
                if key=='base_inventory':doc['identity']=ids[size]
                if key in ('publication','training_terminal'):doc.update(identity_sha256=ident['sha256'],seed=int(name[-1]),step=3116)
                m.save(path,doc);evidence[key]=filepin(path)
            roster.append({'id':name,'status':'available','arm':'K0' if k0 else 'K1','size':size,'seed':None if k0 else int(name[-1]),'terminal_step':None if k0 else 3116,
                           'model':str(base),'adapter':str(adapter) if adapter else None,'identity_sha256':ident['sha256'],'evidence':evidence})
        source={p:m.sha(p) for p in m.required_sources()}
        # Arithmetic imports use exact pinned local metadata-only closure.
        dirs=[str(m.CLOSURE),str(m.R0_DIR),str(m.REPO/'tools')]
        configs=[]
        for row in roster:
            name=row['id'];c={'schema':'rc1-trackk-v1','fixture_only':True,'protocol':filepin(REPO/'experiments/RC1-FUNCTIONAL-TEST.md'),
                 'manifest':filepin(root/'data/manifest.json'),'source_files':source,'image':'sha256:'+'1'*64,
                 'roster':roster,'round_dir':str(fixture.rd),'member':name,'out':str(root/'runs'/name)}
            if name==N.ROLES[0]:
                c['population_export']={'producer':filepin(ENTRY),'exporter':filepin(HERE/'exporter.py'),'member':name,'directory':str(root/'population-export'),'scope':'existing-host-cpu-verify-raw-frozen-train-calibration-test-population-export'}
            review=root/'configs'/(name+'.fixture-review.json');m.save(review,{'schema':'rc1-trackk-review-v1','fixture_only':True,'reviewed':True,'config_sha256':m.digest(c)})
            c['review']=filepin(review);cp=root/'configs'/(name+'.json');m.save(cp,c);configs.append((c,cp))
        # Actual producer campaign projection/prepare (model metadata stubbed only
        # because synthetic DATA replaces the frozen real payload identities).
        with patch.object(m,'validate',return_value=identities):
            for c,_ in configs:m.prepare(c)
        members={}; export=root/'population-export'
        # Each lane invokes the assigned producer's main infer branch (real
        # terminal writer), and real cpu()/fitter/record_test_read verifier.
        for index,(c,cp) in enumerate(configs):
            fixture.c=c;fixture.out=Path(c['out']);fixture.ident=identities[c['member']]
            class Hardware(ns['FakeHardware']):
                def dedup_stats(self):return {'dup_questions':0,'dup_candidates_removed':0}
                def __call__(self,rows,mode='full'):
                    self.calls.append(mode);self.rows+=len(rows)
                    result=[]
                    for i,row in enumerate(rows):
                        scores=[-3.]*len(row['levels'])
                        # Mixed signed effects, exact ties, near ties; stable across
                        # repeated calls and distinct seeds. No constant metric.
                        offset=0 if c['member'].endswith('-base') else int(c['member'][-1])
                        chosen=(i+offset+len(c['member']))%len(scores)
                        scores[chosen]=0.
                        if i%29==0:scores=[0.]*len(scores)
                        elif i%31==0:scores[(chosen+1)%len(scores)]=-0.0001
                        if mode=='blank':scores=list(reversed(scores))
                        result.append(scores)
                    return result
            hardware=Hardware()
            with contextlib.nullcontext():
                # Main creates INFER-EXIT through the actual producer code.
                # Inject generated fake hardware at the factory boundary.
                import eval_r3
                with patch.object(eval_r3,'make_score_fn',lambda a:hardware),patch.object(sys,'argv',[str(ENTRY),'infer','--config',str(cp)]):m.main()
            if index==0:
                # Execute the real exporter CLI body, including first-verification
                # check and COMPLETE writer. Only synthetic host observation and
                # already-fixtured producer module injection are substituted.
                host_evidence={'fixture_only':True,'container_id':'fixture-'+c['member'],'ready_sha256':m.sha(Path(c['out'])/'INFERENCE-READY.json'),'release_sha256':'2'*64}
                with patch.object(exporter,'load',return_value=m),patch.object(m,'host_release',return_value=host_evidence),patch.object(sys,'argv',[str(HERE/'exporter.py'),'host-cpu','--config',str(cp)]):
                    exporter.main()
                report=m.read(Path(c['out'])/'K-REPORT.json')
                assert m.read(export/'COMPLETE.json')['capture_sha256']==m.sha(export/'CAPTURE.json')
                # Re-entry must refuse without another TEST load.
                with patch.object(exporter,'load',return_value=m),patch.object(sys,'argv',[str(HERE/'exporter.py'),'host-cpu','--config',str(cp)]):
                    try: exporter.main()
                    except (RuntimeError,ValueError) as e: assert 'first CPU verification' in str(e)
                    else: raise AssertionError('exporter accepted repeated verification')
            else:
                report=m.cpu(c)
            require=m.require;require(hardware.rows==7064,'fixture scored incorrect population')
            ready=m.read(Path(c['out'])/'INFERENCE-READY.json')
            # Generated host observation; never represented as actual Docker.
            host=Path(c['out'])/'HOST-RELEASE-VERIFIED.json'
            m.save(host,{'fixture_only':True,'container_id':'fixture-'+c['member'],'ready_sha256':m.sha(Path(c['out'])/'INFERENCE-READY.json'),'release_sha256':'2'*64})
            identity_path=root/'identities'/(c['member']+'.json');m.save(identity_path,fixture.ident)
            ev={'config':filepin(cp),'identity':filepin(identity_path),'ready':filepin(Path(c['out'])/'INFERENCE-READY.json'),
                'infer_exit':filepin(Path(c['out'])/'INFER-EXIT.json'),'report':filepin(Path(c['out'])/'K-REPORT.json'),
                'fit':report['operator_fit_artifact'],'final':filepin(fixture.rd/'FINAL.json'),
                'access':filepin(fixture.rd/'TEST-READS.log'),'owner':filepin(fixture.rd/('owner-'+fixture.ident['sha256']+'.json')),
                'run_identity':filepin(Path(c['out'])/'RUN_IDENTITY.json'),'producer_manifest':filepin(Path(c['out'])/'manifests/main.json'),
                'host_release_verified':filepin(host)}
            members[c['member']]=ev
            N.save(root/'progress.json',{'phase':'generated producer completion','completed':index+1,'total':12})
        # All lanes share log and FINAL; pin their final completed bytes.
        for ev in members.values():ev['access']=filepin(fixture.rd/'TEST-READS.log')
        populations=integration.capture_populations({'export_dir':str(export),'configs':{c['member']:str(cp) for c,cp in configs},'export_member':configs[0][0]['member']})
        settings={'kind':'generated','configs':{c['member']:str(cp) for c,cp in configs},
                  'identities':{name:ev['identity']['path'] for name,ev in members.items()},
                  'producer':str(ENTRY),'bootstrap_wrapper':str(REPO/'tools/r3_final_gain_compare.py'),
                  'module_dirs':dirs,'populations':populations,
                  'data_pins':{f'{s}/{p}/{k}':{'n':n,'sha256':h} for (s,p,k),(n,h) in fixture.synthetic_data.items()},
                  'workers':2}
        collector.save(root/'collector-config.json',settings)
        result=collector.build(settings,root/'collected')
        assert result['status']=='ready_for_consumer',result
        cfg=root/'collected/consumer-config.json'
        return cfg
    finally:fixture.tearDown()

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args()
    cfg=build(a.out);print(json.dumps({'fixture_only':True,'config':str(cfg)}))
