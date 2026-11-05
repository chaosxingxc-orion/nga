#!/usr/bin/env python3
"""Recoverable composition of the existing CPU export and score consumers."""
import argparse
import hashlib
import json
import stat
from pathlib import Path
try:
    from . import unified_cpu_consumer_v1 as C
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import unified_cpu_consumer_v1 as C


def sha(path):
    return hashlib.sha256(C.safe(str(path)).read_bytes()).hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def persist(path, value):
    if path.exists(): C.need(C.read(path) == value, 'staged identity changed: '+str(path))
    else: C.write(path, value)
    return ref(path)


def mapped(inputs, path):
    p = C.safe(path)
    matches = [m for m in inputs if p == Path(m['target']) or p.is_relative_to(m['target'])]
    C.need(len(matches) == 1, 'dependency must have one declared mount: '+path)
    m = matches[0]
    result = C.safe(str(Path(m['source']) / p.relative_to(m['target'])))
    C.need(result.exists(), 'dependency missing: '+path)
    return result


def dependencies(inputs, export):
    source = C.pin({'path':str(mapped(inputs, export['source_config'])), 'sha256':export['source_config_sha256']})
    manifest = C.pin({'path':str(mapped(inputs, export['panel_manifest'])), 'sha256':export['panel_manifest_sha256']})
    model=source['model']; dataset=source['dataset']; panel=source['panel']
    inventory_model=C.pin({'path':str(mapped(inputs, model['manifest'])), 'sha256':model['manifest_sha256']})
    modelroot=mapped(inputs, model['path']); C.need(modelroot.is_dir(), 'model directory missing')
    files=inventory_model['files']; C.need(type(files) is dict and files, 'model inventory')
    entries=list(modelroot.rglob('*'))
    C.need(all(not p.is_symlink() and (p.is_dir() or (stat.S_ISREG(p.stat().st_mode) and not p.stat().st_mode & 0o111)) for p in entries), 'unsafe model inventory')
    C.need({str(p.relative_to(modelroot)) for p in entries if p.is_file()} == set(files), 'model inventory differs')
    for name, digest in files.items():
        C.need(type(name) is str and name and not Path(name).is_absolute() and '..' not in Path(name).parts and sha(modelroot/name)==digest, 'model file differs')
    for path, digest in ((dataset['path'],dataset['sha256']), (panel['contract'],panel['contract_file_sha256'])):
        C.need(sha(mapped(inputs,path)) == digest, 'export dependency hash')
    mounts=[]
    for key in ('contract','items','gold','requests'):
        item=manifest['population'][key]; path=item['path']; host=mapped(inputs,path)
        C.need(host.is_file() and sha(host)==item['sha256'], 'population dependency hash')
        mount={'source':str(host),'target':path}
        if mount not in mounts: mounts.append(mount)
    C.need(manifest['population']['contract']['path'] == panel['contract'] and manifest['population']['contract']['sha256'] == panel['contract_file_sha256'], 'contract mapping differs')
    allowed={C.OUTPUT,export['source_config'],export['panel_manifest'],model['path'],model['manifest'],dataset['path'],panel['contract'],*(manifest['population'][k]['path'] for k in ('contract','items','gold','requests'))}
    C.need(type(inputs) is list and all(type(m) is dict and set(m)=={'source','target'} and m['target'] in allowed for m in inputs), 'unexpected export mount')
    C.need(all(m['target'] in (C.OUTPUT,model['path']) or (stat.S_ISREG(C.safe(m['source']).stat().st_mode) and not C.safe(m['source']).stat().st_mode & 0o111) for m in inputs), 'non-regular or executable export input')
    return manifest, mounts


def inventory(manifest, output):
    root=C.safe(str(Path(output)/'result/records')); count=manifest['population']['count']
    C.need(type(count) is int and count > 0 and {p.name for p in root.iterdir()} == {f'{i:06d}' for i in range(count)}, 'record inventory')
    receipts=[]
    for i in range(count):
        d=C.safe(str(root/f'{i:06d}')); marker=C.read(d/'COMMITTED.json')
        C.need(set(marker)=={'record.json'} and marker['record.json']==sha(d/'record.json'), 'record changed')
        receipts.append(sha(d/'COMMITTED.json'))
    C.need(hashlib.sha256(json.dumps(receipts,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()==manifest['receipts_sha256'], 'record receipts changed')


def run(config_ref, consumer=None, hook=None):
    """Run a pinned composition. hook is an in-process test seam, never configured."""
    cfg = C.pin(config_ref)
    C.need(type(cfg) is dict and set(cfg) == {'schema','authorization','event','host_config','image','image_env','template','inputs','export_output','score_output','controller','slots','state_dir'}, 'pipeline fields')
    C.need(cfg['schema'] == 'unified-cpu-pipeline-v1' and cfg['authorization'] == 'existing-completed-host-event-cpu-processing', 'CPU processing authorization')
    template = C.pin(cfg['template'])
    C.need(type(template) is dict and set(template) == {'schema','export','score'}, 'template fields')
    C.need(template['schema'] == 'unified-cpu-pipeline-template-v1', 'template schema')
    export = template['export']; score = template['score']
    C.need(type(export) is dict and set(export) == {'schema','adapter','runtime','source','owner_sha256','source_config','source_config_sha256','panel_manifest','panel_manifest_sha256','output'}, 'export template fields')
    C.need(export['schema'] == 'nga-unified-config-v1' and export['adapter'] == 'native-panel-export-v2' and export['runtime'] == 'cpu' and export['source'] == C.OUTPUT+'/result' and export['output'] == C.EXPORT+'/result', 'export template action')
    C.need(type(score) is dict and set(score) == {'workers','chunk_size'} and type(score['workers']) is int and type(score['chunk_size']) is int and 1 <= score['workers'] <= 32 and 1 <= score['chunk_size'] <= 1024, 'score settings')
    C.need(type(cfg['image']) is str and C.HEX.fullmatch(cfg['image'].removeprefix('sha256:')) and cfg['image'].startswith('sha256:'), 'image ID')
    C.need(type(cfg['slots']) is int and 1 <= cfg['slots'] <= 1024, 'slot count')
    env=cfg['image_env']; C.need(type(env) is list and all(type(x) is str and '=' in x and x.split('=',1)[0] for x in env) and len({x.split('=',1)[0] for x in env})==len(env), 'image environment')
    state = C.safe(cfg['state_dir']); controller = C.safe(cfg['controller'])
    for p in (cfg['export_output'],cfg['score_output']):
        out=C.safe(p); C.need(out.is_dir() and not (state == out or state.is_relative_to(out) or out.is_relative_to(state)), 'state/output overlap')
        C.need(not (controller == out or controller.is_relative_to(out) or out.is_relative_to(controller)), 'controller/output overlap')
    C.need(state != controller and not state.is_relative_to(controller) and not controller.is_relative_to(state), 'state/controller overlap')
    C.need(cfg['export_output'] != cfg['score_output'] and not C.safe(cfg['export_output']).is_relative_to(cfg['score_output']) and not C.safe(cfg['score_output']).is_relative_to(cfg['export_output']), 'output overlap')
    event, host = C.evidence(cfg)
    original_manifest, score_inputs = dependencies(cfg['inputs'], export)
    for m in [{'source':cfg['export_output'],'target':C.EXPORT}, *score_inputs]:
        p=C.safe(m['source']); out=C.safe(cfg['score_output'])
        C.need(not (p == out or p.is_relative_to(out) or out.is_relative_to(p)), 'score input/output overlap')
        C.need(any(Path(m['target']).is_relative_to(x) for x in ('/data','/model',C.EXPORT)), 'score input target')
    sourcepins = {str(Path(__file__).resolve()):sha(Path(__file__).resolve()), str(Path(C.__file__).resolve()):sha(Path(C.__file__).resolve()), str(Path(C.__file__).resolve().parent/'unified_resource_lease_v1.py'):sha(Path(C.__file__).resolve().parent/'unified_resource_lease_v1.py'), str(Path(C.__file__).resolve().parents[1]/'docker/engineering-base/schema.json'):sha(Path(C.__file__).resolve().parents[1]/'docker/engineering-base/schema.json')}
    identity={'schema':'unified-cpu-pipeline-owner-v1','config':config_ref,'template':cfg['template'],'event_id':event['event_id'],'sources':sourcepins}
    state.mkdir(parents=True,exist_ok=True)
    with C.lock(state/'pipeline.lock',True):
        # Recheck all trust roots after acquiring the lifetime lock.
        C.need(C.pin(config_ref)==cfg and C.pin(cfg['template'])==template and C.evidence(cfg)==(event,host), 'pipeline roots changed')
        persist(state/'OWNER.json', identity)
        exp_ref=persist(state/'export-task.json',export)
        base={'schema':'unified-cpu-consumer-v1','event':cfg['event'],'host_config':cfg['host_config'],'image':cfg['image'],'image_env':cfg['image_env'],'controller':cfg['controller'],'slots':cfg['slots']}
        exp={**base,'config':exp_ref,'inputs':cfg['inputs'],'output':cfg['export_output'],'export_receipt':None}
        exp_consumer_ref=persist(state/'export-consumer.json',exp)
        persist(state/'EXPORT-STAGE.json',{'task':exp_ref,'consumer':exp_consumer_ref})
        C.validate(exp)
        worker=consumer or C.Consumer()
        ack=worker.run(exp); C.need(ack['exit_code']==0, 'export failed')
        jid=C.digest({'event_id':event['event_id'],'stage':export['adapter'],'config_sha256':exp_ref['sha256']})
        root=controller/'jobs'/jid; receipt_path=root/'EXPORT.json'
        receipt=C.read(receipt_path); receipt_ref=ref(receipt_path)
        C.need(receipt.get('event_id')==event['event_id'] and receipt.get('job_id')==jid and receipt.get('output')==cfg['export_output'] and receipt.get('ack_sha256')==sha(root/'ACK.json') and C.read(root/'ACK.json')==ack, 'export receipt binding')
        C.need(C.read(root/'OWNER.json')['config']==exp and C.read(root/'OWNER.json')['task']==export, 'export owner binding')
        manifest=Path(cfg['export_output'])/'result/manifest.json'
        C.need(receipt.get('manifest_sha256')==sha(manifest) and C.read(manifest).get('records')==C.EXPORT+'/result/records', 'export manifest binding')
        exported=C.read(manifest)
        C.need(all(exported.get(k)==v for k,v in original_manifest.items() if k not in ('records','receipts_sha256')) and set(exported)==set(original_manifest), 'exported manifest differs from pinned population')
        for item in score_inputs:
            C.need(mapped(cfg['inputs'],item['target']) == Path(item['source']), 'population mapping changed')
        inventory(exported,cfg['export_output'])
        if hook: hook('after_export')
        score_task={'schema':'nga-unified-config-v1','adapter':'native-panel-score-v1','runtime':'cpu','manifest':C.EXPORT+'/result/manifest.json','manifest_sha256':receipt['manifest_sha256'],'output':C.SCORE+'/result',**score}
        score_ref=persist(state/'score-task.json',score_task)
        sc={**base,'config':score_ref,'inputs':[{'source':cfg['export_output'],'target':C.EXPORT},*score_inputs],'output':cfg['score_output'],'export_receipt':receipt_ref}
        score_consumer_ref=persist(state/'score-consumer.json',sc)
        persist(state/'SCORE-STAGE.json',{'task':score_ref,'consumer':score_consumer_ref,'export_receipt':receipt_ref})
        C.validate(sc)
        if hook: hook('after_score_config')
        result=worker.run(sc); C.need(result['exit_code']==0, 'score failed')
        summary=Path(cfg['score_output'])/'result/summary.json'
        C.read(summary)
        sjid=C.digest({'event_id':event['event_id'],'stage':score_task['adapter'],'config_sha256':score_ref['sha256']})
        sr=controller/'jobs'/sjid; so=C.read(sr/'OWNER.json'); st=C.read(sr/'TERMINAL.json'); sa=C.read(sr/'ACK.json')
        C.need(so.get('event_id')==event['event_id'] and so.get('job_id')==sjid and so.get('task')==score_task and so.get('config')==sc and sa==result and sa.get('terminal_sha256')==sha(sr/'TERMINAL.json') and sa.get('launch_sha256')==C.digest(so)==st.get('launch_sha256') and sa.get('container_id')==st.get('container_id') and st.get('event_id')==event['event_id'] and st.get('exit_code')==sa.get('exit_code')==0, 'score ACK ancestry')
        resultdir=summary.parent; owner=C.read(resultdir/'OWNER.json'); report=C.read(resultdir/'report.json'); exitinfo=C.read(resultdir/'EXIT.json'); summary_hash=sha(summary)
        C.need(owner=={'schema':'native-panel-score-owner-v1','config_sha256':score_ref['sha256'],'manifest_sha256':receipt['manifest_sha256'],'output':C.SCORE+'/result'}, 'score owner')
        C.need(report.get('schema')=='native-panel-score-report-v1' and report.get('records')==exported['population']['count'] and report.get('receipts_sha256')==exported['receipts_sha256'] and report.get('config_sha256')==score_ref['sha256'] and report.get('manifest_sha256')==receipt['manifest_sha256'] and report.get('summary_sha256')==summary_hash and report.get('cpu_only') is True and report.get('test_inference_rerun') is False, 'score report')
        C.need(exitinfo.get('exit_code')==0 and exitinfo.get('config_sha256')==score_ref['sha256'] and exitinfo.get('manifest_sha256')==receipt['manifest_sha256'] and exitinfo.get('summary_sha256')==summary_hash, 'score EXIT')
        inventory(exported,cfg['export_output'])
        terminal={'schema':'unified-cpu-pipeline-terminal-v1','event_id':event['event_id'],'owner':ref(state/'OWNER.json'),'export_consumer':ref(state/'export-consumer.json'),'export_task':exp_ref,'export_receipt':receipt_ref,'manifest':ref(manifest),'score_consumer':ref(state/'score-consumer.json'),'score_task':score_ref,'score_ack':ref(sr/'ACK.json'),'score_consumer_owner':ref(sr/'OWNER.json'),'score_consumer_terminal':ref(sr/'TERMINAL.json'),'score_owner':ref(resultdir/'OWNER.json'),'score_report':ref(resultdir/'report.json'),'score_exit':ref(resultdir/'EXIT.json'),'summary':ref(summary),'sources':sourcepins,'scientific_acceptance':False}
        persist(state/'TERMINAL.json',terminal)
        return terminal


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--sha256',required=True); a=p.parse_args()
    print(json.dumps(run({'path':a.config,'sha256':a.sha256}),sort_keys=True))


if __name__=='__main__': main()
