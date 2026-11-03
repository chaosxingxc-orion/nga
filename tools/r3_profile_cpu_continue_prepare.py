#!/usr/bin/env python3
"""Freeze a reviewed-input CPU continuation without starting a container."""
import importlib.util,json,shutil
from pathlib import Path

def main():
    source=Path(__file__).with_name('r3_profile_cpu_continue.py').resolve();spec=importlib.util.spec_from_file_location('continuation',source);R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
    root=R.BASE/'profile_cpu_continuation_20261103_v4';root.mkdir(exist_ok=False);(root/'code').mkdir();(root/'output').mkdir()
    target=root/'code'/source.name;shutil.copyfile(source,target);old=R.read(R.CAPTURE/'HOST-PLAN.json')
    d={'schema':'r3-profile-cpu-continuation-v1','package':root.name,'capture_plan':str(R.CAPTURE/'HOST-PLAN.json'),'capture_plan_sha256':R.CAPTURE_PIN,'runtime':{'path':str(target),'sha256':R.sha(target)},'out':str(root/'output'),'container':'nga-'+root.name,'image':old['image_sha256'],'environment':old['environment'],'max_process_number':4,'poll_seconds':600,'scientific_acceptance':False,'test_read':False,'coverage_adjudicated':False,'capture_evidence':{p:R.sha(R.CAPTURE/'output'/p) for p in R.EVIDENCE}}
    d['files']=dict(old['files']);d['files'].update({d['capture_plan']:R.CAPTURE_PIN,str(target):R.sha(target)});d['files'].update({str(R.CAPTURE/'output'/p):h for p,h in d['capture_evidence'].items()})
    plan=root/'PLAN.json';R.put(plan,d);pin=R.sha(plan)
    diagnosis=Path('/home/xingchao/workspace/nga/.local/reports/profile-cann-diagnosis-current.json')
    previous=R.BASE/'profile_cpu_continuation_20261103_v3'
    support=[diagnosis,previous/'PLAN.json',previous/'output/host/EXIT.json',previous/'output/parse/EXIT.json']
    support_pins={str(p):R.sha(p) for p in support};support_pins.update(R.read(diagnosis)['evidence'])
    for p,h in support_pins.items():R.require(R.sha(p)==h,'diagnostic evidence changed')
    R.put(root/'REVIEW-INPUT.json',{'status':'UNREVIEWED_NOT_LAUNCHED','plan':str(plan),'plan_sha256':pin,'expected_command':R.command(d,plan,pin),'files':d['files'],'supporting_evidence':support_pins,'mount_change':'Exclude host driver/sbin/install.info as a group; use image toolkit. Prior v3 and capture unchanged.','scientific_acceptance':False,'coverage_acceptance':'Independent raw-to-trace coverage review required after actual parse. CSV nonempty alone insufficient.'})
    R.put(root/'OPERATIONS.json',{'verify':['python3','-B','-P',str(target),'verify','--plan',str(plan),'--sha256',pin],'start':['/usr/bin/python3.12','-B','-P',str(target),'start','--plan',str(plan),'--sha256',pin,'--review',str(root/'INDEPENDENT-REVIEW.json'),'--review-sha256','REPLACE_WITH_ACTUAL_REVIEW_SHA256'],'consume':['python3','-B','-P',str(target),'consume','--plan',str(plan),'--sha256',pin]})
    print(json.dumps({'root':str(root),'plan_sha256':pin}))
if __name__=='__main__':main()
