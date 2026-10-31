"""Exact-plan artifact verification for final evaluation; does not launch.

This validates bindings, not scientific eligibility by itself. An independently
reviewed eligibility decision and exact-plan review are required inputs. No
approval/FINAL is generated and no test partition is opened by this module.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

IMAGE='sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7'
SUITES=['decision-v7','transfer-v4']


def helper(name):
    path=Path(__file__).with_name(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

C=helper('r3_final_closure');M=helper('r3_model_inventory')


def require(ok,reason):
    if not ok:raise ValueError(reason)


def pin(value):
    require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value),'invalid SHA256')
    return value


def identity(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def artifact(entry):
    require(set(entry)=={'path','sha256'},'artifact descriptor differs')
    path=C.safe(entry['path']);pin(entry['sha256'])
    require(path.suffix=='.json','only JSON evidence may enter admission')
    require(C.sha(path)==entry['sha256'],'bound artifact changed: '+str(path))
    return json.loads(path.read_text())


def verify(plan, expected_pin, review_entry):
    """CPU-only preflight; caller must also enforce reviewed container execution.

    Review is externally pinned, outside plan to avoid a circular plan hash.
    The reviewer's identity/provenance must be established by the orchestrator;
    a JSON claim or a passing verifier does not establish independent authorship.
    """
    require(identity(plan)==pin(expected_pin),'final plan identity differs')
    require(plan.get('schema')=='r3-final-test-plan-v1','final plan schema differs')
    require(plan.get('image')==IMAGE and plan.get('host')=='k8s-node1','image/host differs')
    require(type(plan.get('chip')) is int and plan['chip'] in range(8),'invalid chip')
    require(plan.get('suites')==SUITES and plan.get('partitions')==['calibration','test'],'final partitions differ')
    require(plan.get('arm') in ('K0','K1','K2'),'unregistered arm')
    require(plan.get('scoring')=={'mode':'rightpad','dtype':'float32','hf32':False,'token_budget':16384,
                                'stages':'k','shards':1},'frozen scorer settings differ')
    out=C.safe(plan['out']);round_dir=C.safe(plan['round_dir'])
    require(out!=round_dir and not round_dir.is_relative_to(out),'output/round overlap')
    pin(plan['model_sha256'])
    review=artifact(review_entry)
    require(review.get('schema')=='r3-final-test-review-v1'
            and review.get('review_kind')=='independent_astra' and review.get('reviewer_model')=='gpt-6-astra'
            and review.get('verdict')=='PASS' and review.get('approved_plan_sha256')==expected_pin,
            'actual independent exact-plan review required')
    require(review.get('blocking_findings')==[] and bool(review.get('evidence_checks')),
            'review has blockers or lacks checks')
    eligibility=artifact(plan['eligibility'])
    require(review.get('eligibility_sha256')==plan['eligibility']['sha256'],'review eligibility differs')
    require(eligibility.get('schema')=='r3-final-eligibility-v1' and eligibility.get('status')=='ELIGIBLE',
            'formal eligibility required')
    require(eligibility.get('candidate_test_read') is False,'selection used candidate test')
    require(eligibility.get('seed_set')==[2,3] and eligibility.get('suites')==SUITES,'eligibility scope differs')
    require(eligibility.get('evidence')==plan['evidence'],'eligibility evidence binding differs')
    required={'development_comparison','r0_gating','resume_reconstruction','training_eligibility','selection_decision'}
    require(set(plan['evidence'])==required,'eligibility evidence inventory differs')
    require(review.get('evidence')==plan['evidence'],'review evidence binding differs')
    for entry in plan['evidence'].values():artifact(entry)
    models=eligibility.get('selected_models',[])
    require(isinstance(models,list) and models,'no eligible models')
    model_path=str(C.safe(plan['adapter'] or plan['model']))
    require(any(m.get('path')==model_path and m.get('sha256')==plan['model_sha256']
                and m.get('arm')==plan['arm'] for m in models),'model not eligible')
    final=artifact(plan['final'])
    require(Path(plan['final']['path'])==round_dir/'FINAL.json','FINAL outside round')
    require(final.get('eligibility_sha256')==plan['eligibility']['sha256'],'FINAL eligibility differs')
    require(isinstance(final.get('models'),list) and any(m.get('path')==model_path and m.get('sha256')==plan['model_sha256']
                for m in final['models']),'model not named in FINAL')
    # Only manifest bytes are read here. Dataset bytes are checked after ticket
    # authorization by the source/metric verifier, before completion publication.
    data=artifact(plan['dataset_manifest'])
    require(all(s in data.get('suites',{}) for s in SUITES),'task manifest suites absent')
    closure=plan['closure'];root=C.safe(closure['root'])
    require(set(closure)=={'root','sha256'},'closure descriptor differs')
    C.verify(root,pin(closure['sha256']))
    manifest=json.loads((root/'manifest.json').read_text())
    # Bind the actual admission implementation, not just a sibling manifest.
    require(C.safe(Path(__file__).absolute()).is_relative_to(root), 'admission must execute from frozen closure')
    require('r3_code/r3_final_admission.py' in manifest['files'],'admission implementation unbound')
    require(out!=root and not out.is_relative_to(root) and not root.is_relative_to(out),'output/closure overlap')
    inventory=artifact(plan['base_inventory'])
    base=M.verify(plan['model'],inventory['inventory'],inventory['inventory_sha256'])
    require(Path(plan['model']).name in {'Qwen__Qwen3.5-0.8B-Base','Qwen__Qwen3.5-2B-Base',
                                      'Qwen__Qwen3.5-4B-Base','Qwen__Qwen3.5-9B-Base'},'base outside scope')
    adapter=None
    if plan['adapter'] is not None:
        training=artifact(plan['training_manifest'])
        require(Path(plan['training_manifest']['path'])==Path(plan['adapter']).parent/'manifest.json',
                'training manifest does not own adapter')
        require(training.get('args',{}).get('seed') in (2,3)
                and training.get('summary',{}).get('final_step')==training.get('total_steps')
                and training.get('total_steps',0)>0,'completed training seed required')
        inv=artifact(plan['adapter_inventory']);adapter=M.verify(plan['adapter'],inv['inventory'],inv['inventory_sha256'])
    else:
        require(plan.get('adapter_inventory') is None and plan['arm']=='K0','trained arm needs adapter binding')
        require(plan.get('training_manifest') is None,'K0 must not carry a training manifest')
    return {'plan_sha256':expected_pin,'base':base,'adapter':adapter,
            'artifact_bindings_verified':True,'scientific_acceptance':False,
            'scope':'binding preflight only; review authorship, eligibility semantics and container execution remain external'}
