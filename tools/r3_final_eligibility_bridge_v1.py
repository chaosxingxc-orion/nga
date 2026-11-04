"""First-K1 DEV-to-final artifact bridge, with explicit external selection.

Never infer selection from ELIGIBLE, open TEST, or start inference. Production use
requires reviewed config/source and authenticated selection-review authorship.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
NINE = ('primary_s2','primary_s3','samechip_s2','diffchip_s2','qo_s2','pt_s2','pt_s3','k0_base','k0_instruct')
SEVEN = ('primary_s2','primary_s3','k0_base','k0_instruct','qo_s2','pt_s2','pt_s3')
EVIDENCE = ('development_comparison','r0_gating','resume_reconstruction','training_eligibility','selection_decision')

def require(ok, why):
    if not ok: raise ValueError(why)

def canonical(d): return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(d): return hashlib.sha256(canonical(d).encode()).hexdigest()
def safe(p):
    p=Path(p)
    require(p.is_absolute() and str(p)==str(p.resolve()) and not any(x.is_symlink() for x in (p,*p.parents)), 'unsafe path')
    return p

def sha(p):
    with safe(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pin(p):return {'path':str(p),'sha256':sha(p)}
def read(ref):
    require(set(ref)=={'path','sha256'} and sha(ref['path'])==ref['sha256'],'artifact changed')
    return json.loads(safe(ref['path']).read_text())
def module(ref):
    require(sha(ref['path'])==ref['sha256'],'implementation changed')
    spec=importlib.util.spec_from_file_location(Path(ref['path']).stem,ref['path'])
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def write(p,d):
    with safe(p).open('x') as f:
        json.dump(d,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    fd=os.open(Path(p).parent,os.O_RDONLY);os.fsync(fd);os.close(fd)

def validate_semantics(c,bundle,adjudication,result,campaign,decision):
    """Validate already re-executed qualification, not a caller's status assertion."""
    require(bundle.get('schema')=='r3-production-dev-bundle-v1' and bundle.get('branch')=='firstK1'
            and bundle.get('test_read') is False,'only registered firstK1 supported')
    require(set(bundle['entries'])==set(NINE),'complete nine-member bundle required')
    require(adjudication.get('schema')=='r3-independent-dev-adjudication-v1'
            and adjudication.get('bundle_sha256')==c['bundle']['sha256'],'adjudication binding differs')
    require(result.get('schema')=='r3-production-dev-qualification-v1' and result.get('status')=='ELIGIBLE'
            and result.get('completed') is True and result.get('candidate_eligibility_granted') is True
            and result.get('test_read') is False and result.get('scientific_acceptance') is False
            and result.get('final_test_logger_authority') is False,'DEV not eligible')
    require(result.get('bundle_sha256')==c['bundle']['sha256'] and result.get('adjudication_sha256')==c['adjudication']['sha256'],'qualification origin differs')
    checks=result['checks']; expected={'inventory','membership','adjudication','r0','role_bindings','chronology','numeric','final_inventory'}|{'member:'+x for x in NINE}
    require(set(checks)==expected and all(x.get('status')=='VALIDATED' for x in checks.values()),'incomplete/failed qualification checks')
    numeric=checks['numeric']['value']
    require(numeric.get('numeric_predicates_pass') is True and numeric.get('floor_qualification_indeterminate') is False,'numeric qualification not affirmative')
    require('development_comparison' in numeric,'development comparison missing')
    require(campaign.get('selected_arm')=='K1' and campaign.get('size')=='0.8B','firstK1 campaign differs')
    members=campaign['members'];require(len(members)==7,'seven final members required')
    used=set()
    for m in members:
        matches=[name for name in SEVEN if bundle['entries'][name]['model']['path']==m['model']['path']]
        require(len(matches)==1 and matches[0] not in used,'campaign member not in qualified roster')
        name=matches[0];used.add(name);entry=bundle['entries'][name]
        require(m['arm']==entry['arm'] and all(m['model'].get(k)==v for k,v in entry['model'].items()),'campaign model identity differs')
        require(m['verified_evidence_sha256']==digest(checks['member:'+name]['value']),'campaign member evidence differs')
        if entry['arm']!='K0':
            training=m['training']
            require(training['arm']==entry['arm'] and training['seed']==entry['seed']
                    and training['adapter_path']==entry['model']['path']
                    and training['training_variant']==entry['training_variant'],'campaign training differs')
    require(used==set(SEVEN),'final roster incomplete')
    require(decision.get('schema')=='r3-independent-first-k1-final-selection-v1'
            and decision.get('origin')=='independent-parent-adjudication'
            and bool(decision.get('authenticator_identity')) and bool(decision.get('reviewer_identity'))
            and decision.get('verdict')=='SELECT_FIRST_K1' and decision.get('selected_arm')=='K1'
            and decision.get('candidate_test_read') is False and decision.get('blocking_findings')==[],
            'external independent final selection absent')
    expected_refs={k:c[k] for k in ('bundle','adjudication','qualification','campaign','qualifier')}
    require(decision.get('inputs')==expected_refs,'selection input bindings differ')
    require(decision.get('selected_members')==list(SEVEN),'selection roster differs')
    require(decision.get('basis')=={'branch':'firstK1','numeric_check_sha256':digest(numeric),
             'r0_check_sha256':digest(checks['r0']['value']),
             'no_added_replacement_thresholds':True},'selection basis differs')
    require(decision.get('evidence_checks') and isinstance(decision['evidence_checks'],list),'selection review checks absent')
    return checks

def replay(c,directory):
    """Use exact pinned executable; never accept fabricated status-only input."""
    require(sha(c['qualifier']['path'])==c['qualifier']['sha256'],'qualifier source changed')
    target=directory/'REPLAY.json'
    cmd=[str(safe(c['python'])),'-B','-P',c['qualifier']['path'],'--bundle',c['bundle']['path'],
         '--bundle-sha256',c['bundle']['sha256'],'--adjudication',c['adjudication']['path'],
         '--adjudication-sha256',c['adjudication']['sha256'],'--output',str(target)]
    env=c['environment'];require(isinstance(env,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in env.items()),'environment differs')
    require(env.get('TORCH_DEVICE_BACKEND_AUTOLOAD')=='0' and env.get('PYTHONDONTWRITEBYTECODE')=='1','CPU-only environment required')
    with (directory/'replay.log').open('xb') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,**env))
    require(result.returncode==0 and target.is_file(),'qualification replay did not qualify')
    require(sha(c['qualifier']['path'])==c['qualifier']['sha256'],'qualifier changed during replay')
    actual=json.loads(target.read_text());require(actual==read(c['qualification']),'qualification replay differs')
    return actual

def build(path,config_sha):
    require(sha(path)==config_sha,'config changed');c=json.loads(safe(path).read_text())
    require(c.get('schema')=='r3-first-k1-final-bridge-config-v1','config schema differs')
    required={'schema','bundle','adjudication','qualification','campaign','selection_decision','qualifier','campaign_verifier','inventory_verifier','inventories','python','environment','output'}
    require(set(c)==required,'config fields differ')
    docs={k:read(c[k]) for k in ('bundle','adjudication','qualification','campaign','selection_decision')}
    bundle=docs['bundle'];out=safe(c['output']);require(not out.exists(),'fresh output required')
    # All bound source artifacts pre-exist and must remain outside the new output.
    refs=[c[k] for k in ('bundle','adjudication','qualification','campaign','selection_decision','qualifier','campaign_verifier','inventory_verifier')]
    for ref in refs:require(not safe(ref['path']).is_relative_to(out),'output overlaps inputs')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='final-bridge-check-',dir=out.parent) as scratch:
        actual=replay(c,Path(scratch))
        checks=validate_semantics(c,bundle,docs['adjudication'],actual,docs['campaign'],docs['selection_decision'])
        K=module(c['campaign_verifier']);K.verify(docs['campaign']);M=module(c['inventory_verifier'])
        require(set(c['inventories'])==set(SEVEN),'inventory roster differs')
        for name in SEVEN:
            entry=bundle['entries'][name];model=entry['model'];m=next(m for m in docs['campaign']['members'] if m['model']['path']==model['path']);inv=c['inventories'][name]
            require(set(inv)==({'base'} if entry['arm']=='K0' else {'base','adapter'}),'inventory fields differ')
            base=read(inv['base']);M.verify(model['base_path'],base['inventory'],base['inventory_sha256'])
            require(m['model']['base_inventory_sha256']==base['inventory_sha256'],'base inventory binding differs')
            if entry['arm']!='K0':
                adapter=read(inv['adapter']);M.verify(model['path'],adapter['inventory'],adapter['inventory_sha256'])
                t=m['training'];mp=str(Path(model['path']).parent/'manifest.json')
                require(t['training_manifest']==mp and bundle['files'].get(mp)==t['training_manifest_sha256']==sha(mp),'training manifest differs')
            refs.extend(inv.values())
        for ref in refs:require(sha(ref['path'])==ref['sha256'],'source changed during construction')
        for p,h in bundle['files'].items():require(sha(p)==h,'bundle evidence changed after replay')
        require(sha(path)==config_sha,'config changed during construction')
        out.mkdir()
        # Durable evidence documents explicitly identify source checks; no invented gates.
        origins={k:c[k] for k in ('bundle','adjudication','qualification','qualifier')}
        values={'development_comparison':checks['numeric']['value']['development_comparison'],
                'r0_gating':checks['r0']['value'],
                'resume_reconstruction':{n:checks['member:'+n]['value'] for n in NINE},
                'training_eligibility':{'chronology':checks['chronology']['value'],'role_bindings':checks['role_bindings']['value'],'numeric':checks['numeric']['value']}}
        evidence={}
        for key,value in values.items():
            p=out/(key+'.json');write(p,{'schema':'r3-final-derived-evidence-v1','kind':key,'source':origins,'value':value,'test_read':False,'scientific_acceptance':False});evidence[key]=pin(p)
        evidence['selection_decision']=c['selection_decision']
        views=[]
        for m in docs['campaign']['members']:
            v={'path':m['model']['path'],'sha256':m['model']['sha256'],'base_path':m['model']['base_path'],'arm':m['arm'],'role':m['role']}
            if m['arm']!='K0':v['seed']=m['training']['seed']
            views.append(v)
        eligible={'schema':'r3-final-eligibility-v1','status':'ELIGIBLE','candidate_test_read':False,'seed_set':[2,3],
                  'suites':['decision-v7','transfer-v4'],'evidence':evidence,'selected_models':views,'campaign_sha256':c['campaign']['sha256']}
        write(out/'ELIGIBILITY.json',eligible)
        write(out/'FINAL.json',{'eligibility_sha256':sha(out/'ELIGIBILITY.json'),'campaign_sha256':c['campaign']['sha256'],'models':views})
        write(out/'BUILD.json',{'configuration':pin(path),'selection':c['selection_decision'],'eligibility':pin(out/'ELIGIBILITY.json'),
              'final':pin(out/'FINAL.json'),'campaign':c['campaign'],'test_read':False,'npu_started':False,
              'remaining':['externally authenticate review authorship','exact per-member plans and named Astra reviews','resource admission and actual evaluation'],
              'scientific_acceptance':False})
    return pin(out/'BUILD.json')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    print(json.dumps(build(a.config,a.sha256),indent=2))
