#!/usr/bin/env python3
"""Assemble pinned completed-member inputs; never create adjudication."""
import argparse
import hashlib
import json
from pathlib import Path
import types

QUALIFIER_SHA='89fa709d4f830f38ebbc7bd449d89a8e3c527ed3e986dc71ff6faa64f755df4f'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):h.update(block)
    return h.hexdigest()


def prepare(config_path, config_pin, output):
    files={}
    def pin(path, expected=None):
        p=Path(path)
        if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p,*p.parents)):
            raise ValueError('unsafe member input')
        value=sha(p)
        if expected is not None and value!=expected:raise ValueError('member input changed: '+str(p))
        if str(p) in files and files[str(p)]!=value:raise ValueError('conflicting file identity')
        files[str(p)]=value
        return p
    def readref(ref):return json.loads(pin(ref['path'],ref['sha256']).read_text())
    def inventory(group):
        for p,h in group.items():pin(p,h)
    config=readref({'path':str(Path(config_path).absolute()),'sha256':config_pin})
    if set(config)!={'schema','qualification','member','capture','collection','postrun_review','producer_manifest','review_lineage'} or config['schema']!='r3-member-evidence-prepare-v1':
        raise ValueError('preparation schema differs')
    qualification=readref(config['qualification']);name=config['member'];member=qualification['members'][name]
    producer_ref=config['producer_manifest']
    if qualification['immutable_files'].get(producer_ref['path'])!=producer_ref['sha256']:
        raise ValueError('complete producer manifest not previously pinned by qualification')
    if name not in ('primary_s2','primary_s3','samechip_s2','diffchip_s2'):
        raise ValueError('formal four-role member required; controls use a different prelaunch review protocol')
    capture=readref(config['capture']);collection=readref(config['collection']);review=readref(config['postrun_review'])
    lineage=readref(config['review_lineage']);producer=readref(config['producer_manifest'])
    if capture['member']!=name or capture['execution']!=member['execution']:
        raise ValueError('capture member differs')
    if collection['training']!=member['training'] or review['training']!=member['training']:
        raise ValueError('postrun member differs')
    if review.get('verdict')!='PASS' or review.get('independent') is not True:
        raise ValueError('actual independent postrun review missing')
    if review['evidence_files'].get(config['collection']['path'])!=config['collection']['sha256']:
        raise ValueError('postrun review does not bind collection')
    for doc,groups in [(capture,['files']), (collection,['files','verified_training_files','external_observation_pins','static_pins']),
                       (review,['files','evidence_files'])]:
        for group in groups:inventory(doc[group])
    line=lineage['members'][name]
    if line['status']!='PASS_FROZEN_REVIEW_LINEAGE_AND_CHRONOLOGY':raise ValueError('review lineage not replayed')
    inventory(line['files'])
    plan=readref(member['plan']);execution=json.loads(pin(member['execution'],capture['execution_sha256']).read_text())
    spec=json.loads(pin(execution['spec'],execution['spec_sha256']).read_text())
    inventory(execution['tools']);inventory(spec['files'])
    if (producer.get('evaluation_profile')!='track_kt' or producer.get('test_read') is not False
            or not producer.get('code') or not producer.get('data')):
        raise ValueError('producer closure scope differs')
    for item in producer['code'].values():
        if spec['files'].get(item['snapshot'])!=item['sha256'] or not any(
                Path(item['snapshot']).is_relative_to(mount['source']) for mount in spec['code_mounts']):
            raise ValueError('producer source not bound/mounted by spec')
        pin(item['snapshot'],item['sha256'])
    for path,h in producer['data'].items():
        if spec['files'].get(path)!=h:raise ValueError('producer data not bound by spec')
    inventory(producer['data'])
    def observations(refs, bound, root, container_name):
        if set(refs)!= {'container','image','daemon'}:raise ValueError('observation roles differ')
        docs={}
        for key,ref in refs.items():
            if set(ref)!= {'path','sha256'} or bound.get(ref['path'])!=ref['sha256']:
                raise ValueError('observation not bound to original collection')
            docs[key]=readref(ref)
        actual=docs['container']
        if len(actual)!=1:raise ValueError('single observed container required')
        actual=actual[0];state=actual['State']
        launch=json.loads(pin(Path(root)/'attempts/1/LAUNCH_RECEIPT.json').read_text())
        if (actual['Id']!=launch['id'] or actual['Name']!='/'+container_name+'-a1'
                or state.get('Status')!='exited' or state.get('Running') is not False
                or type(state.get('ExitCode')) is not int or state['ExitCode']!=0
                or state.get('OOMKilled') or state.get('Error') or actual['HostConfig'].get('AutoRemove')
                or len(docs['image'])!=1 or docs['image'][0]['Id']!=actual['Image']):
            raise ValueError('observation generation/success differs')
    observations(capture['evaluation_observations'],capture['files'],execution['out'],execution['container'])
    observations(review['training_observations'],collection['external_observation_pins'],plan['out'],plan['container'])
    qref=qualification['qualifier']
    if qref['sha256']!=QUALIFIER_SHA:raise ValueError('unsupported frozen qualifier')
    source=pin(qref['path'],qref['sha256']).read_bytes();Q=types.ModuleType('frozen_member_qualifier');Q.__file__=qref['path']
    exec(compile(source,qref['path'],'exec'),Q.__dict__)
    historical=json.loads(pin(plan['review_path'],plan['review_sha256']).read_text())
    canonical=hashlib.sha256((json.dumps(dict(plan,review_sha256='PENDING'),indent=2,sort_keys=True)+'\n').encode()).hexdigest()
    ended,_=Q.verify_collaboration_review(plan,canonical,historical,files,Q.legacy())
    terminal=json.loads(pin(Path(plan['out'])/'TRAIN_EXIT.json').read_text())
    if ended>=Q.moment(terminal['started_utc']):raise ValueError('review does not precede training')
    report_path=pin(member['report']);report=json.loads(report_path.read_text());header=report['header']
    if report['scientific_acceptance'] is not False or header['arm']!=member['arm']:
        raise ValueError('report scope/arm differs')
    if header['model']['path']!=str(Path(plan['out'])/'adapter') or header['model']['base_path']!=member['checkpoint']:
        raise ValueError('report model differs')
    if report['selection_evidence']['seed']!=member['seed']:raise ValueError('report seed differs')
    inventory(header['data_files'])
    for n in ['EVAL_COMPLETE.track_kt.json','SCORING_RECEIPT.track_kt.json']:pin(report_path.parent/n)
    entry={'arm':member['arm'],'seed':member['seed'],'plan':member['plan']['path'],
           'execution':member['execution'],'report':member['report'],'model':header['model'],
           'training_variant':report['selection_evidence']['training_variant'],
           'producer_manifest':config['producer_manifest']['path'],
           'postrun_collection':config['collection']['path'],
           'postrun_review':config['postrun_review']['path']}
    result={'schema':'r3-member-evidence-candidate-v1','member':name,'entry':entry,
            'files':files,'training_observations':review['training_observations'],
            'evaluation_observations':capture['evaluation_observations'],
            'independent_decision':None,'scientific_acceptance':False,'test_read':False,
            'status':'CANDIDATE_INPUTS_ASSEMBLED_NOT_ADJUDICATED',
            'missing':['independent complete member adjudication','full frozen member() replay with its read boundary'],
            'scope':'References original evidence. Does not create the reserved independent member descriptor.'}
    with Path(output).open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    return {'member':name,'files':len(files),'status':result['status']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ['config','sha256','output']:p.add_argument('--'+k,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.config,a.sha256,a.output)))
