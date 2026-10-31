"""Exact-plan artifact verification for final evaluation; does not launch.

This validates bindings, not scientific eligibility by itself. An independently
reviewed eligibility decision and exact-plan review are required inputs. No
approval/FINAL is generated and no test partition is opened by this module.
"""
import ast
import hashlib
import os
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

C=helper('r3_final_closure');M=helper('r3_model_inventory');K=helper('r3_final_campaign')


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


def member_view(member):
    value={'path':member['model']['path'],'sha256':member['model']['sha256'],
           'base_path':member['model']['base_path'],'arm':member['arm'],'role':member['role']}
    if member['arm']!='K0':value['seed']=member['training']['seed']
    return value


def campaign_member(plan,eligibility,final,review):
    campaign=artifact(plan['campaign']);structure=K.verify(campaign)
    digest=plan['campaign']['sha256']
    require(all(d.get('campaign_sha256')==digest for d in (eligibility,final,review)),
            'campaign binding differs')
    views=[member_view(m) for m in campaign['members']]
    expected={identity(v) for v in views}
    for label,rows in [('eligibility',eligibility.get('selected_models')),('FINAL',final.get('models'))]:
        require(isinstance(rows,list) and len(rows)==len(expected)
                and all(isinstance(v,dict) for v in rows)
                and {identity(v) for v in rows}==expected, label+' campaign membership differs')
    matches=[m for m in campaign['members'] if m['model']['path']==plan['adapter'] or
             (plan['adapter'] is None and m['model']['path']==plan['model'])]
    require(len(matches)==1,'execution requires one unique campaign member')
    member=matches[0];view=member_view(member)
    require(view['arm']==plan['arm'] and view['sha256']==plan['model_sha256']
            and view['base_path']==plan['model'] and view['role']==plan.get('role'),
            'execution campaign identity differs')
    if member['arm']=='K0':require('seed' not in plan,'K0 must not carry a seed')
    else:require(type(plan.get('seed')) is int and plan['seed']==view['seed'],'execution campaign seed differs')
    return member,structure


def training_recipe(manifest,root):
    # Use the exact seed-independent recipe function from the verified closure
    # without importing historical runtime modules or opening any dataset.
    source=root/'r3_code/selection_evidence_r3.py'
    tree=ast.parse(source.read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='training_variant']
    require(len(nodes)==1,'frozen training recipe function missing')
    namespace={'os':os}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
    return namespace['training_variant'](manifest)


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
    require(plan.get('arm') in ('K0','K1','K2','K1-QO','K1-PT'),'unregistered arm')
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
    final=artifact(plan['final'])
    require(Path(plan['final']['path'])==round_dir/'FINAL.json','FINAL outside round')
    require(final.get('eligibility_sha256')==plan['eligibility']['sha256'],'FINAL eligibility differs')
    member,campaign_structure=campaign_member(plan,eligibility,final,review)
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
    require(plan['model'] in (K.BASE,K.INSTRUCT),'only complete 0.8B campaign supported')
    require(inventory['inventory_sha256']==member['model']['base_inventory_sha256'],
            'campaign base bytes differ')
    adapter=None
    if plan['adapter'] is not None:
        training=artifact(plan['training_manifest'])
        require(Path(plan['training_manifest']['path'])==Path(plan['adapter']).parent/'manifest.json',
                'training manifest does not own adapter')
        recorded=member['training'];args=training.get('args',{})
        require(recorded['training_manifest']==plan['training_manifest']['path']
                and recorded['training_manifest_sha256']==plan['training_manifest']['sha256'],
                'campaign training manifest differs')
        require(type(args.get('seed')) is int and args['seed']==plan['seed']
                and training.get('summary',{}).get('final_step')==training.get('total_steps')
                and training.get('total_steps')==3116,'completed training seed required')
        objective='k2' if plan['arm']=='K2' else 'k1'
        require(training.get('arm')==args.get('arm')==objective
                and training.get('model_path')==args.get('model_path')==plan['model']
                and args.get('out')==str(Path(plan['adapter']).parent)
                and args.get('drop_state') is (plan['arm']=='K1-QO'),
                'training objective/base/input identity differs')
        require(training_recipe(training,root)==recorded['training_variant'],'campaign training recipe differs')
        require(plan['arm']!='K1-QO' or plan['seed']==2,'QO seed differs')
        require((plan['model']==K.INSTRUCT)==(plan['arm']=='K1-PT'), 'control base differs')
        inv=artifact(plan['adapter_inventory']);adapter=M.verify(plan['adapter'],inv['inventory'],inv['inventory_sha256'])
    else:
        require(plan.get('adapter_inventory') is None and plan['arm']=='K0','trained arm needs adapter binding')
        require(plan.get('training_manifest') is None,'K0 must not carry a training manifest')
    return {'plan_sha256':expected_pin,'base':base,'adapter':adapter,
            'artifact_bindings_verified':True,'campaign_structure':campaign_structure,'scientific_acceptance':False,
            'scope':'binding preflight only; whole-campaign source verification, review authorship, eligibility semantics and container execution remain external'}
