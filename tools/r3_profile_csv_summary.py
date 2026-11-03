#!/usr/bin/env python3
"""Bounded-memory CPU summary of profiler CSVs; no model or NPU imports."""
import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path


def publish(path, data):
    tmp=path.with_suffix(path.suffix+'.pending')
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n');tmp.replace(path)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    root=Path(a.input);out=Path(a.output);out.mkdir(exist_ok=True,parents=True)
    result={'scope':'Trace phase only; device task durations can overlap; no production speed claim','files':{},'tables':{}}
    rc=1
    try:
        configs=[('kernel_details.csv','Name',['Duration(us)']),('operator_details.csv','Name',['Host Self Duration(us)','Device Self Duration(us)']),('task_time.csv','kernel_type',['task_time(us)'])]
        for name,key,fields in configs:
            p=root/name;h=hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(1<<20),b''):h.update(b)
            result['files'][name]={'sha256':h.hexdigest(),'bytes':p.stat().st_size}
            groups=defaultdict(lambda:[0]+[0.]*len(fields));count=0
            with p.open(newline='') as f:
                for row in csv.DictReader(f):
                    values=groups[row[key]];values[0]+=1
                    for i,field in enumerate(fields,1): values[i]+=float(row[field])
                    count+=1
                    if count%100000==0:publish(out/'heartbeat.json',{'utc_seconds':time.time(),'file':name,'rows':count})
            totals=[sum(v[i] for v in groups.values()) for i in range(len(fields)+1)]
            top={field:[{'key':k,'rows':v[0],'seconds':v[i]/1e6} for k,v in sorted(groups.items(),key=lambda kv:-kv[1][i])[:20]] for i,field in enumerate(fields,1)}
            result['tables'][name]={'rows':count,'groups':len(groups),'totals_seconds':dict(zip(fields,[x/1e6 for x in totals[1:]])),'top20':top}
        p=root/'step_trace_time.csv';result['step_trace']=list(csv.DictReader(p.open(newline='')))
        result['files'][p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
        publish(out/'report.json',result);rc=0
    finally:publish(out/'EXIT.json',{'exit_code':rc,'utc_seconds':time.time()})


if __name__=='__main__':main()
