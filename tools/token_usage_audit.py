#!/usr/bin/env python3
"""Read-only project-scoped Codex/Claude token audit. Never exports message text.

Uses individual response usage, not cumulative token_count snapshots. Cache is a
subset of Codex input; Claude cache read/write are additive input categories.
Purpose/action labels are transparent lexical proxies, not judgments of value.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3

FIELDS=('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')

def instant(value):
    """Compare instants, not ISO spellings with different offsets/precision."""
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required for audit timestamp')
    return parsed.astimezone(dt.timezone.utc)

def add(a,b):
    for k in FIELDS:a[k]+=int(b.get(k,0) or 0)
    a['uncached_input_tokens']+=int(b.get('input_tokens',0) or 0)-int(b.get('cached_input_tokens',0) or 0)-int(b.get('cache_write_input_tokens',0) or 0)
    a['noncached_input_plus_output']+=int(b.get('input_tokens',0) or 0)-int(b.get('cached_input_tokens',0) or 0)+int(b.get('output_tokens',0) or 0)
    a['responses']+=1

def counter():return collections.Counter()
def clean(c):return dict(sorted(c.items()))
def purpose(path,title):
    s=(path or title or '').lower()
    for label,pat in [
        ('review_validation',r'review|audit|admission|acceptance|astra|verify|verification|qualif|reconstruct|confirmation'),
        ('monitoring_coordination',r'monitor|watchdog|poll|cadence|status|observer'),
        ('reporting_knowledge',r'report|wiki|archive|memory|documentation|publication|consolidation'),
        ('research_analysis',r'survey|literature|architecture|diagnos|analysis|coverage|benchmark.*align|results'),
        ('engineering_implementation',r'fix|repair|impl|prepare|ready|package|builder|config|guard|queue|handoff|successor|runtime|closure|adapter|consumer|source|protocol|contract|efficiency|profile|performance|execute|launch|train|scor|eval|baseline|experiment'),
    ]:
        if re.search(pat,s):return label
    return 'other_or_mixed'

def action(calls):
    if not calls:return 'text_reasoning_no_tool'
    names=' '.join(x[0] for x in calls).lower();code=' '.join(x[1] for x in calls).lower()
    if re.search(r'spawn_agent|followup_task|send_message|interrupt_agent',names):return 'agent_coordination'
    if re.search(r'wait_agent|list_agents|sleep|write_stdin|^wait$',names):return 'wait_status_control'
    if re.search(r'git (commit|push)|wiki|current-conclusions|reference-baseline-latest|report.*\.md',code):return 'publication_or_report_io'
    if re.search(r'unittest|pytest|test_[a-z]|verify|sha256|reconstruct|rebuild|assert ',code):return 'test_verification_io'
    if re.search(r'apply_patch|write_text|write_bytes|cat >|open\([^\n]*[\"\x27][wax]',code+names):return 'code_or_artifact_mutation'
    if re.search(r'docker.*run|[\"\x27 ]start[\"\x27 ]|\blaunch\b|--op run',code):return 'execution_start_or_prepare'
    if re.search(r'docker ps|digest\.(json|md)|heartbeat|npu-smi|/proc/|git status|curr_time',code+names):return 'status_or_digest_read'
    if re.search(r'cat |sed |rg |read_text|read_bytes|select |ls |find ',code):return 'source_or_evidence_read'
    if re.search(r'search|browse|fetch|web',names):return 'external_retrieval'
    return 'other_tool'

def connect(path):
    c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c

def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    project=str(Path(args.project).resolve());cutoff=args.cutoff;cutoff_time=instant(cutoff)
    state=connect(Path(args.codex)/'state_5.sqlite')
    rows=[dict(r) for r in state.execute('select id,rollout_path,cwd,tokens_used,agent_path,title,thread_source,created_at from threads where cwd=?',(project,))]
    goal=connect(Path(args.codex)/'goals_1.sqlite')
    goals=[dict(r) for r in goal.execute('select thread_id,tokens_used,time_used_seconds,status,created_at_ms,updated_at_ms from thread_goals') if r['thread_id'] in {x['id'] for x in rows}]
    totals=counter();by_day=collections.defaultdict(counter);by_purpose=collections.defaultdict(counter);by_action=collections.defaultdict(counter);by_agent=collections.defaultdict(counter)
    threads=[];seen={};dedup=collections.Counter();events=collections.Counter();models=collections.Counter();tools=collections.Counter();records=[]
    for row in rows:
        p=Path(row['rollout_path']);stats=counter();toolcounts=collections.Counter();calls=[];meta=None;boundary=0;finals=[];tool_chars=0;tool_truncated=0;compactions=0;first=None;last=None;own_count=0;pending_model=None;failure_signatures=collections.Counter();usage_snapshots=0;latest_snapshot=None;first_own_usage=None
        if not p.exists():dedup['missing_rollout']+=1;continue
        if dt.datetime.fromtimestamp(row['created_at'],dt.timezone.utc)>cutoff_time:
            continue
        with p.open() as stream:
            for lineno,line in enumerate(stream,1):
                try:d=json.loads(line)
                except (ValueError,UnicodeError):dedup['malformed_line']+=1;continue
                stamp=d.get('timestamp','');typ=d.get('type');v=d.get('payload',{});ordinal=d.get('ordinal',0)
                if stamp and instant(stamp)>cutoff_time:continue
                if typ=='session_meta' and meta is None:
                    meta=v;boundary=v.get('subagent_history_start_ordinal') or 0
                if ordinal<boundary:continue
                if typ=='turn_context':pending_model=v.get('model',pending_model)
                if typ=='compacted':compactions+=1
                if typ=='event_msg' and v.get('type')=='token_count':
                    usage_snapshots+=1;latest_snapshot=(v.get('info') or {}).get('total_token_usage',latest_snapshot)
                if typ=='response_item':
                    vt=v.get('type')
                    if vt in ('function_call','custom_tool_call'):
                        name=v.get('name','unknown');code=v.get('arguments',v.get('input',''));code=code if isinstance(code,str) else json.dumps(code)
                        calls.append((name,code));toolcounts[name]+=1;tools[name]+=1
                    elif vt in ('function_call_output','custom_tool_call_output'):
                        output=v.get('output','');output=output if isinstance(output,str) else json.dumps(output)
                        tool_chars+=len(output);tool_truncated+=int('truncated' in output.lower())
                        for k,pat in [('403_balance',r'403.{0,100}(prepayment|balance)|prepayment.{0,100}(balance|insufficient)'),('observation_timeout',r'timed out|timeout'),('missing_artifact',r'no such file|file.?not.?found')]:
                            if re.search(pat,output,re.I):failure_signatures[k]+=1
                    elif vt=='message' and v.get('role')=='assistant' and v.get('phase') in ('final','final_answer'):
                        finals.append(' '.join(x.get('text','') for x in v.get('content',[]) if isinstance(x,dict)))
                if typ!='token_usage_record':continue
                if v.get('thread_id')!=row['id']:
                    dedup['inherited_usage_excluded']+=1;continue
                rid=v.get('response_id');u=v.get('usage',{})
                key=(v.get('thread_id'),rid)
                if not rid:dedup['missing_response_id']+=1;continue
                if key in seen:
                    dedup['duplicate_response_id']+=1
                    if seen[key]!=u:dedup['conflicting_duplicate_usage']+=1
                    calls=[];continue
                seen[key]=u;own_count+=1
                if int(u.get('input_tokens',0))+int(u.get('output_tokens',0))!=int(u.get('total_tokens',0)):dedup['usage_arithmetic_mismatch']+=1
                if int(u.get('cached_input_tokens',0))+int(u.get('cache_write_input_tokens',0))>int(u.get('input_tokens',0)):dedup['cache_exceeds_input']+=1
                cat=purpose(row['agent_path'],row['title']) if row['agent_path'] else 'root_orchestration_mixed'
                act=action(calls);agent='child' if row['agent_path'] else 'root';date=stamp[:10]
                for counter_ in [stats,totals,by_day[date],by_purpose[cat],by_action[act],by_agent[agent]]:add(counter_,u)
                events['responses_input_ge_128k']+=int(u.get('input_tokens',0)>=128000)
                events['responses_input_ge_200k']+=int(u.get('input_tokens',0)>=200000)
                models[pending_model or 'unrecorded']+=1
                record={'provider':'codex','thread_id':row['id'],'response_id':rid,'timestamp':stamp,'source':str(p),'line':lineno,'agent_path':row['agent_path'],'purpose_proxy':cat,'action_proxy':act,'usage':u,'model_recorded':pending_model,'tool_call_count':len(calls),'tool_names':[x[0] for x in calls]}
                records.append(record);calls=[]
                first=first or stamp;last=stamp;first_own_usage=first_own_usage or u
        ack_only=bool(own_count and not toolcounts and any(re.search(r'follow these|follow the.*guidelines|guidelines.*follow|遵循|遵守|确认.*指令',x,re.I) for x in finals))
        thread={'id':row['id'],'agent_path':row['agent_path'],'purpose_proxy':purpose(row['agent_path'],row['title']) if row['agent_path'] else 'root_orchestration_mixed','usage':clean(stats),'first':first,'last':last,'tool_calls':dict(toolcounts),'tool_output_characters':tool_chars,'truncated_outputs':tool_truncated,'compactions':compactions,'failure_signature_outputs':dict(failure_signatures),'ack_only_heuristic':ack_only,'first_own_usage':first_own_usage,'history_boundary':boundary,'parent_thread_id':(meta or {}).get('parent_thread_id'),'usage_snapshots_ignored':usage_snapshots,'latest_snapshot':latest_snapshot,'state_tokens_used_at_read':row['tokens_used'],'source':str(p)}
        threads.append(thread)
    claude_seen={};claude_rows=0;claude_conflicts=0;claude_outside=0;claude_files=0;claude_bytes=0
    croot=Path(args.claude)/'projects'/project.replace('/','-')
    for p in croot.rglob('*.jsonl') if croot.exists() else []:
        claude_files+=1;claude_bytes+=p.stat().st_size
        with p.open() as stream:
            for lineno,line in enumerate(stream,1):
                try:d=json.loads(line)
                except (ValueError,UnicodeError):continue
                if d.get('type')!='assistant':continue
                if d.get('timestamp') and instant(d['timestamp'])>cutoff_time:continue
                if d.get('cwd',project)!=project:claude_outside+=1;continue
                m=d.get('message',{});u=m.get('usage');mid=m.get('id')
                if not u or not mid:continue
                claude_rows+=1;k=mid
                # Block-stream rows repeat request usage. Retain the largest total usage;
                # preserve conflict count for visibility, do not sum repeated blocks.
                cooked={'input_tokens':int(u.get('input_tokens',0))+int(u.get('cache_read_input_tokens',0))+int(u.get('cache_creation_input_tokens',0)), 'cached_input_tokens':int(u.get('cache_read_input_tokens',0)), 'cache_write_input_tokens':int(u.get('cache_creation_input_tokens',0)), 'output_tokens':int(u.get('output_tokens',0)), 'reasoning_output_tokens':int((u.get('output_tokens_details') or {}).get('thinking_tokens',0))}
                cooked['total_tokens']=cooked['input_tokens']+cooked['output_tokens']
                if k in claude_seen:
                    old=claude_seen[k]
                    if old['usage']!=cooked:claude_conflicts+=1
                    if cooked['total_tokens']<=old['usage']['total_tokens']:continue
                claude_seen[k]={'provider':'claude','response_id':mid,'timestamp':d.get('timestamp'),'source':str(p),'line':lineno,'model_recorded':m.get('model'),'session_id':d.get('sessionId',d.get('session_id')),'is_sidechain':d.get('isSidechain',False),'usage':cooked}
    ct=counter();cd=collections.defaultdict(counter);cm=collections.defaultdict(counter)
    for rec in claude_seen.values():
        add(ct,rec['usage']);add(cd[rec['timestamp'][:10]],rec['usage']);add(cm[rec['model_recorded']],rec['usage'])
    allrecs=records+list(claude_seen.values())
    with (out/'responses.jsonl').open('w') as f:
        for rec in allrecs:f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    summary={'schema':'nga-token-audit-v1','generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'cutoff_utc':cutoff,'project':project,'method':{'codex':'Own-thread individual token_usage_record deduplicated by (thread_id,response_id), excludes inherited ordinals; never sums event_msg cumulative snapshots','claude':'Project-scoped assistant usage deduplicated by message.id; retain maximum total usage across block-stream copies, not iterations sum','cached':'Codex cached input is subset of input; Claude read/create fields added into total input. Reasoning is subset of output, never added again.','classification':'Purpose from agent path; action from tool names/code. Lexical proxies, not semantic or business-value measurements.','cost':'No prices or invoices; raw/cache-adjusted accounting are not money or exact compute.'},'codex':{'threads_discovered':len(rows),'threads_scanned':len(threads),'totals':clean(totals),'by_day':{k:clean(v) for k,v in sorted(by_day.items())},'by_purpose_proxy':{k:clean(v) for k,v in by_purpose.items()},'by_action_proxy':{k:clean(v) for k,v in by_action.items()},'by_agent':{k:clean(v) for k,v in by_agent.items()},'dedup_diagnostics':dict(dedup),'events':dict(events),'tool_calls':dict(tools),'models_responses':dict(models),'goal_snapshot':goals,'thread_state_tokens_sum_at_read':sum(r['tokens_used'] for r in rows)},'claude':{'files_scanned':claude_files,'bytes_scanned':claude_bytes,'usage_rows':claude_rows,'deduplicated_messages':len(claude_seen),'stream_rows_dropped':claude_rows-len(claude_seen),'different_stream_usage_rows':claude_conflicts,'out_of_project_rows_excluded':claude_outside,'totals':clean(ct),'by_day':{k:clean(v) for k,v in sorted(cd.items())},'by_model':{k:clean(v) for k,v in cm.items()}},'threads':threads,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'codex':clean(totals),'claude':clean(ct),'threads':len(threads),'dedup':dict(dedup),'output':str(out)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True);p.add_argument('--codex',default='/home/xingchao/.codex');p.add_argument('--claude',default='/home/xingchao/.claude');p.add_argument('--cutoff',required=True);p.add_argument('--output',required=True);run(p.parse_args())
