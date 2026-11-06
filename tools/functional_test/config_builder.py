#!/usr/bin/env python3
"""Create a reviewable template from real bindings; never generate a review."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import supervisor as H

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--template',required=True); p.add_argument('--runtime',required=True)
    p.add_argument('--entry',required=True); p.add_argument('--config-path',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args(); c=H.read(a.template); rt=H.read(a.runtime)
    entry=Path(a.entry); H.need(entry.is_absolute() and str(entry.resolve())==str(entry),'entry path')
    H.need(str(entry) in c['source_files'] and c['source_files'][str(entry)]==H.sha(entry),'entry source pin')
    H.need(rt['image']==c['image'],'runtime image differs')
    c['host']['entry']=str(entry); c['host']['runtime_evidence']={'path':str(Path(a.runtime).resolve()),'sha256':H.sha(a.runtime)}
    c['container']['spec']['environment']={**rt['environment'],**H.K.ENV}
    c['container']['spec']['cmd']=['-B','-P',str(entry),'infer','--config',str(Path(a.config_path).resolve())]
    H.need(not Path(a.output).exists(),'output exists')
    # The operator supplies mounts, source pins and the real review after inspecting this template.
    c.pop('review',None)
    H.save(a.output,c)
if __name__=='__main__': main()
