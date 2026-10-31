#!/usr/bin/env python3
"""Detached actual-Astra release review. No Docker, SSH, NPU or allocation writes.

Prepare with --prepare, inspect brief and expected bundle, then explicitly --launch.
The runner records the actual child wait status; rc=0 is NOT a PASS verdict.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

REVIEW_TIMEOUT_SECONDS = 3600
TERMINATE_GRACE_SECONDS = 15


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def durable(path, value, replace=False):
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    tmp=path.with_name(path.name+'.pending')
    with tmp.open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    if replace: os.replace(tmp,path)
    else: os.link(tmp,path);tmp.unlink()
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def verify(bundle, expected):
    if bundle.is_symlink() or sha(bundle/'MANIFEST.json')!=expected:
        raise ValueError('Bundle manifest differs')
    entries=json.loads((bundle/'MANIFEST.json').read_bytes())['files']; names=[]
    for e in entries:
        rel=Path(e['path'])
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe member path')
        p=bundle/rel
        if any((bundle/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts)+1)):
            raise ValueError('Symlink member')
        if not p.is_file() or p.stat().st_size!=e['size'] or sha(p)!=e['sha256']:
            raise ValueError('Bundle member differs: '+e['path'])
        names.append(e['path'])
    actual={str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file()}
    if len(names)!=len(set(names)) or actual!=set(names)|{'MANIFEST.json'}:
        raise ValueError('Bundle membership differs')


def prepare(out,bundle,manifest):
    verify(bundle,manifest);out.mkdir(parents=False,exist_ok=False)
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    brief=('Review only the frozen release-tool candidate at '+str(bundle)+'.\n'
           'Expected MANIFEST SHA256: '+manifest+'.\n'
           'Read prior_review_v2/review.md and current release/evidence/test sources. Verify bundle membership and hashes. '
           'Check NPU EXIT/receipt/FinishedAt binding, post-exit CPU attestation, externally anchored review and allocation '
           'before-state, coordinated review/journal rewrite, real release() imports, publication crash windows, '
           'idempotence and negative scientific flags. Inspect cpu_tests/report.json and per-test text. '
           'Distinguish fixture checks from actual Docker/host evidence and explain trust boundaries. '
           'Do not require impossible self-attestation of CPU FinishedAt before its process exits. '
           'Do not run production release, launcher or preparer. No Docker, SSH, network, NPU, allocation mutation, '
           'approval file creation or external weights. Short isolated CPU fixture checks only if sandbox permits; '
           'otherwise state they were not rerun. Return substantive PASS or BLOCK for exact bundle, '
           'with file/line findings and exact evidence scope. CLI success alone is not scientific or operational approval.\n')
    (out/'brief.txt').write_text(brief)
    durable(out/'EXPECTED.json',dict(bundle=str(bundle),manifest_sha256=manifest,
                                   runner_sha256=sha(out/'runner.py'),brief_sha256=sha(out/'brief.txt')))


def launch(out):
    if any((out/n).exists() for n in ('PROCESS.json','LAUNCH.json','COMPLETE.json','runner.txt')):
        raise ValueError('Existing generation; never relaunch an uncertain review')
    with (out/'runner.txt').open('xb') as stream:
        cmd=[sys.executable,'-B','-P',str(out/'runner.py'),'--run',str(out)]
        proc=subprocess.Popen(cmd,cwd='/tmp',stdin=subprocess.DEVNULL,stdout=stream,
                              stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    durable(out/'LAUNCH.json',dict(runner_pid=proc.pid,command=cmd,utc=time.time()))
    return dict(pid=proc.pid,out=str(out))


def run(out):
    fd=os.open(out/'runner.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o644)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    expected=json.loads((out/'EXPECTED.json').read_bytes()); bundle=Path(expected['bundle'])
    if sha(out/'runner.py')!=expected['runner_sha256'] or sha(out/'brief.txt')!=expected['brief_sha256']:
        raise ValueError('Runner or brief identity differs')
    if any((out/n).exists() for n in ('PROCESS.json','COMPLETE.json','EXIT.json')):
        raise ValueError('Preserve prior generation')
    stop=threading.Event(); heartbeat_errors=[]; child=None; thread=None; rc=1; reason=None
    def beat():
        while not stop.is_set():
            try:
                durable(out/'digest.json',dict(stage='reviewing',runner_pid=os.getpid(),
                        child_pid=child.pid if child else None,progress=0,total=1,utc=time.time()),replace=True)
            except Exception as exc:
                heartbeat_errors.append(repr(exc));return
            stop.wait(10)
    try:
        verify(bundle,expected['manifest_sha256'])
        with (out/'events.jsonl').open('xb') as events,(out/'stderr.txt').open('xb') as err,(out/'brief.txt').open('rb') as prompt:
            cmd=['/home/xingchao/.npm-global/bin/codex','exec','--model','gpt-6-astra','--sandbox','read-only',
                 '--skip-git-repo-check','--ephemeral','--json','-C',str(out),'-o',str(out/'review.md'),'-']
            child=subprocess.Popen(cmd,stdin=prompt,stdout=events,stderr=err,start_new_session=True)
            durable(out/'PROCESS.json',dict(command=cmd,pid=child.pid,runner_pid=os.getpid(),utc=time.time()))
            thread=threading.Thread(target=beat,daemon=True);thread.start()
            try: result=child.wait(timeout=REVIEW_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try: result=child.wait(timeout=TERMINATE_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL);result=child.wait()
                reason='Review timeout; actual child termination recorded'
            durable(out/'CHILD_EXIT.json',dict(pid=child.pid,wait_returncode=result,utc=time.time(),source='Popen.wait'))
        verify(bundle,expected['manifest_sha256'])
        if result!=0 or reason: raise ValueError(reason or 'CLI failed: '+str(result))
        if not (out/'review.md').is_file() or (out/'review.md').stat().st_size<300:
            raise ValueError('No substantive review output')
        if heartbeat_errors: raise ValueError('Heartbeat failed: '+repr(heartbeat_errors))
        rc=0
    except BaseException as exc:
        reason=type(exc).__name__+': '+str(exc)
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
            if not (out/'CHILD_EXIT.json').exists():
                durable(out/'CHILD_EXIT.json',dict(pid=child.pid,wait_returncode=child.returncode,utc=time.time(),source='Popen.wait after runner error'))
    finally:
        stop.set()
        if thread: thread.join(15)
        # A heartbeat can fail immediately before thread termination. It is an
        # execution failure even if the child returned a substantive review.
        if heartbeat_errors:
            rc=1; reason=(reason+'; ' if reason else '')+'Heartbeat failed: '+repr(heartbeat_errors)
        try:
            durable(out/'digest.json',dict(stage='completed' if rc==0 else 'failed',rc=rc,reason=reason,utc=time.time()),replace=True)
        except Exception as exc:
            rc=1; reason=(reason+'; ' if reason else '')+'Final digest publication failed: '+repr(exc)
        # EXIT must be attempted independently of digest and COMPLETE writes.
        # Preserve pending evidence: do not overwrite or remove an uncertain
        # publication merely to make a successful terminal appear.
        try:
            outputs={n:sha(out/n) for n in ('runner.py','brief.txt','EXPECTED.json','PROCESS.json','CHILD_EXIT.json','review.md') if (out/n).exists()}
            durable(out/'COMPLETE.json',dict(rc=rc,reason=reason,outputs=outputs,utc=time.time(),scope='review execution; not approval'))
        except Exception as exc:
            rc=1; reason=(reason+'; ' if reason else '')+'Terminal publication failed: '+repr(exc)
        finally:
            try: durable(out/'EXIT.json',dict(rc=rc,reason=reason,utc=time.time()))
            finally: os.close(fd)
    return rc


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',type=Path);p.add_argument('--bundle',type=Path)
    p.add_argument('--manifest-sha256');p.add_argument('--launch',type=Path);p.add_argument('--run',type=Path)
    a=p.parse_args()
    if a.prepare:
        if not a.bundle or not a.manifest_sha256:p.error('prepare needs bundle and manifest hash')
        prepare(a.prepare.absolute(),a.bundle.resolve(),a.manifest_sha256)
    elif a.launch: print(json.dumps(launch(a.launch.resolve())))
    elif a.run: raise SystemExit(run(a.run.resolve()))
    else:p.error('one action required')

if __name__=='__main__':main()
