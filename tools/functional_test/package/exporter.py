#!/usr/bin/env python3
"""Capture frozen population rows during the existing first host CPU verification."""
import argparse, importlib.util, json, os, sys
from pathlib import Path


def load(path):
 spec=importlib.util.spec_from_file_location('rc1_export_core',path); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def capture(core,c,identity,desc,expected,export):
    """The original verifier obtains tickets; interception adds no TEST load."""
    seen={}; original=core.C.load_partition
    def intercept(s,p,*args,**kwargs):
        result=original(s,p,*args,**kwargs)
        kind='variants' if kwargs.get('variants',False) else 'clean'
        key=f'{s}/{p}/{kind}'
        if key in seen: raise ValueError('duplicate population load')
        seen[key]=result[0]
        return result
    core.C.load_partition=intercept
    try: evidence,clean=core.verify(c,identity,desc,expected)
    finally: core.C.load_partition=original
    train,_=original('decision-v7','train')
    seen['decision-v7/train/clean']=train
    groups={f'{s}/{p}/{k}' for s,p,k in core.DATA}
    core.require(set(seen)==groups,'export population inventory differs')
    for key,rows in seen.items():
        s,p,k=key.split('/');core.require(len(rows)==core.DATA[(s,p,k)][0],'export count differs')
        keys=[core.C.kev_key(r) for r in rows]
        core.require(len(keys)==len(set(keys)),'duplicate metadata identity')
        for r in rows:
            ids=core.C.level_ids(r);core.require(ids and len(ids)==len(set(ids)) and r['gold'] in ids and r['level_type'] in ('boolean','nominal','ordinal'),'invalid metadata')
    root=Path(export);root.mkdir(parents=True,exist_ok=True)
    for key,rows in seen.items():
        path=root/(key.replace('/','__')+'.json')
        if path.exists():core.require(core.read(path)==rows,'existing export differs')
        else:core.save(path,rows)
    core.save(root/'CAPTURE.json',{'campaign_sha256':core.campaign_digest(c),'config_sha256':core.digest(c),'identity_sha256':identity['sha256'],'populations':{key:{'path':str((root/(key.replace('/','__')+'.json')).resolve()),'sha256':core.sha(root/(key.replace('/','__')+'.json'))} for key in sorted(seen)}})
    return evidence,clean

def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['host-cpu']);ap.add_argument('--config',required=True);a=ap.parse_args()
 c=json.loads(Path(a.config).read_text());e=c['population_export'];core=load(e['producer']['path'])
 core.pinfile(e['producer']);core.pinfile(e['exporter']);core.require(Path(e['exporter']['path']).resolve()==Path(__file__).resolve(),'exporter path differs')
 core.require(e['scope']=='existing-host-cpu-verify-raw-frozen-train-calibration-test-population-export' and e['member']==c['member'],'export scope/member differs')
 core.require(Path(e['directory']).is_absolute(),'export path must be absolute')
 ident=core.admitted(c);core.require(not any(core.previous(c,ident).values()),'capture requires first CPU verification')
 evidence=core.host_release(c,a.config);core.save(Path(c['out'])/'HOST-RELEASE-VERIFIED.json',evidence)
 result=core.cpu(c,verify_fn=lambda c,i,d,x:capture(core,c,i,d,x,e['directory']))
 core.save(Path(e['directory'])/'COMPLETE.json',{'capture_sha256':core.sha(Path(e['directory'])/'CAPTURE.json'),'report_sha256':core.sha(Path(c['out'])/'K-REPORT.json'),'config_sha256':core.digest(c)})
 print(json.dumps({'phase':a.phase,'state':'ok','result_sha256':core.digest(result)}))
if __name__=='__main__':main()
