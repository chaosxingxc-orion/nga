#!/usr/bin/env python3
"""Guarded host-side resource claim/release adapter for R3 jobs on host 175.

The allocation file is the ownership source of truth. This adapter never
infers ownership from npu-smi. Claim and release are short, locked,
idempotent transactions; scientific acceptance is outside this module.
"""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types

ALLOC_DEFAULT = "/mnt/cephfs/xingchao/experiments/jev/CHIP-ALLOCATION.json"

def utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def read_bytes(path):
    # Reject symlink components before resolving.  Resolving first makes the
    # subsequent ``is_symlink`` check vacuous and could silently redirect the
    # ownership ledger to an attacker-controlled file.
    path = validated_path(path)
    with path.open("rb") as f:
        before, raw, after = os.fstat(f.fileno()), f.read(), None
        after = os.fstat(f.fileno())
    ident = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if ident(before) != ident(after):
        raise RuntimeError("allocation changed during read")
    return raw


def validated_path(path):
    """Return a regular allocation path without traversing symlink components."""
    raw_path = Path(path)
    absolute = raw_path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise RuntimeError(f"symlink allocation path: {raw_path}")
    resolved = absolute.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise RuntimeError(f"not a regular allocation file: {resolved}")
    return resolved

def load(path):
    return json.loads(read_bytes(path))

def write_atomic(path, value):
    path = Path(path)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".pending", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        try: os.unlink(name)
        except FileNotFoundError: pass
    return sha_bytes(raw)

def read_json_if(path):
    path = Path(path)
    return load(path) if path.exists() else None

def locked(path):
    f = Path(str(path) + ".lock").open("a+")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    return f

def validate_doc(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get("allocation"), list) or not isinstance(doc.get("free"), list):
        raise RuntimeError("invalid allocation document")
    chips = [e.get("chip") for e in doc["allocation"] + doc["free"]]
    if any(type(c) is not int or not 0 <= c < 8 for c in chips) or len(chips) != len(set(chips)):
        raise RuntimeError("invalid or duplicated chip entry")

def successor_guard(args):
    """Load only the controller explicitly pinned by the exact launch plan."""
    values = [getattr(args, key, None) for key in ('plan', 'plan_sha256', 'precondition_sha256')]
    if not any(values):
        return None
    if not all(values):
        raise RuntimeError('complete successor claim binding required')
    path, plan_pin, precondition_pin = values
    p = load(path)
    canonical = (json.dumps(dict(p, review_sha256='PENDING'), indent=2, sort_keys=True) + '\n').encode()
    if sha_bytes(canonical) != plan_pin:
        raise RuntimeError('claim plan identity differs')
    if (p.get('run') != args.run or p.get('chip') != args.chip or
            validated_path(p['allocation']) != validated_path(args.alloc) or
            Path(p['adapter']).resolve() != Path(__file__).resolve() or
            p['files'].get(p['adapter']) != sha_bytes(read_bytes(__file__)) or
            args.proof != str(Path(p['out']) / 'attempts/1/CLAIM.json')):
        raise RuntimeError('claim plan resource binding differs')
    controller = p.get('successor_guard', {}).get('controller')
    if not controller or Path(controller).name != 'r3_formal_train_successor.py':
        raise RuntimeError('registered successor controller required')
    raw = read_bytes(controller)
    if p['files'].get(controller) != sha_bytes(raw):
        raise RuntimeError('claim controller pin differs')
    module = types.ModuleType('claim_successor_controller'); module.__file__ = controller
    exec(compile(raw, controller, 'exec', dont_inherit=True), module.__dict__)
    def check(allocation):
        # Check the pinned bytes on each observation, including recovery.
        if read_bytes(path) != plan_raw or read_bytes(controller) != raw:
            raise RuntimeError('claim binding changed during transaction')
        result = module.claim_precondition(p, plan_pin, precondition_pin, allocation, types.SimpleNamespace(**globals()))
        return dict(result, plan_sha256=plan_pin, controller_sha256=sha_bytes(raw))
    plan_raw = read_bytes(path)
    return check


def claim(args):
    alloc = validated_path(args.alloc)
    guard = successor_guard(args)
    intent_path = Path(args.proof).with_suffix(Path(args.proof).suffix + ".intent")
    with locked(alloc):
        before_raw = read_bytes(alloc); before = json.loads(before_raw); validate_doc(before)
        if guard and (Path(args.proof).exists() or intent_path.exists()):
            raise RuntimeError('guarded claim already attempted; explicit repair required')
        existing = read_json_if(args.proof)
        if existing is not None:
            if existing.get("schema") == "r3-resource-claim-v1" and existing.get("run") == args.run and existing.get("chip") == args.chip:
                if 'successor_precondition' in existing:
                    raise RuntimeError('guarded claim cannot be replayed without precondition')
                print(json.dumps({"status": "ALREADY_CLAIMED", "chip": args.chip, "run": args.run, "proof": args.proof}))
                return
            raise RuntimeError("claim proof already exists with another identity")
        intent = read_json_if(intent_path)
        if intent is not None and (intent.get("schema") != "r3-resource-claim-intent-v1" or
                                   intent.get("run") != args.run or intent.get("chip") != args.chip):
            raise RuntimeError("claim intent identity differs")
        # Recover a crash after the allocation ledger was replaced but before
        # the immutable claim proof was written.  The intent carries both
        # snapshots, so an after-image match is safe to finalize; an unrelated
        # ledger change must never be overwritten.
        if intent is not None:
            if 'successor_precondition' in intent:
                raise RuntimeError('guarded intent requires explicit repair')
            after = intent.get("allocation_after")
            after_raw = (json.dumps(after, indent=2, sort_keys=True, allow_nan=False) + "\n").encode() if after is not None else None
            after_hash = sha_bytes(after_raw) if after_raw is not None else None
            current_hash = sha_bytes(before_raw)
            if after_hash == current_hash:
                proof = {"schema": "r3-resource-claim-v1", "run": args.run, "chip": args.chip,
                         "allocation": str(alloc), "allocation_before_sha256": intent.get("allocation_before_sha256"),
                         "allocation_after_sha256": after_hash, "allocation_before": intent.get("allocation_before"),
                         "allocation_after": after, "entry": intent.get("entry"),
                         "claimed_utc": intent.get("entry", {}).get("claimed_utc")}
                Path(args.proof).parent.mkdir(parents=True, exist_ok=True)
                write_atomic(args.proof, proof)
                try: intent_path.unlink()
                except FileNotFoundError: pass
                print(json.dumps({"status": "CLAIM_RECOVERED", "chip": args.chip, "run": args.run, "proof": args.proof}))
                return
            if intent.get("allocation_before_sha256") != current_hash:
                raise RuntimeError("claim intent exists but allocation is neither before nor after")
        if any(e.get("chip") == args.chip for e in before["allocation"]):
            raise RuntimeError(f"chip {args.chip} is allocated")
        if sum(e.get("chip") == args.chip for e in before["free"]) != 1:
            raise RuntimeError(f"chip {args.chip} is not explicitly free")
        guard_evidence = guard(before) if guard else None
        now = utc()
        entry = {"chip": args.chip, "owner": args.owner, "run": args.run, "purpose": args.purpose,
                 "claimed_utc": now, "release_when": "retained container exited and guarded release proof written"}
        after = dict(before); after["free"] = [e for e in before["free"] if e.get("chip") != args.chip]
        after["allocation"] = sorted(before["allocation"] + [entry], key=lambda e: e["chip"])
        after["updated_utc"], after["updated_by"] = now, "r3_resource_adapter claim"
        intent = {"schema": "r3-resource-claim-intent-v1", "run": args.run, "chip": args.chip,
                  "allocation_before_sha256": sha_bytes(before_raw), "allocation_before": before,
                  "allocation_after": after,
                  "entry": entry, "proof": str(Path(args.proof).resolve())}
        if guard:
            intent['successor_precondition'] = guard_evidence
        Path(args.proof).parent.mkdir(parents=True, exist_ok=True)
        write_atomic(intent_path, intent)
        if guard and guard(before) != guard_evidence:
            raise RuntimeError('claim precondition changed before commit')
        if read_bytes(alloc) != before_raw:
            raise RuntimeError('allocation changed before claim commit')
        after_hash = write_atomic(alloc, after)
        proof = {"schema": "r3-resource-claim-v1", "run": args.run, "chip": args.chip,
                 "allocation": str(alloc), "allocation_before_sha256": sha_bytes(before_raw),
                 "allocation_after_sha256": after_hash, "allocation_before": before,
                 "allocation_after": after, "entry": entry, "claimed_utc": now}
        if guard:
            proof["successor_precondition"] = guard_evidence
            write_atomic(args.proof, proof)
            intent_path.unlink()
            print(json.dumps({"status": "CLAIMED", "chip": args.chip, "run": args.run, "proof": args.proof}))
            return
    Path(args.proof).parent.mkdir(parents=True, exist_ok=True); write_atomic(args.proof, proof)
    try: intent_path.unlink()
    except FileNotFoundError: pass
    print(json.dumps({"status": "CLAIMED", "chip": args.chip, "run": args.run, "proof": args.proof}))

def abort_claim(args):
    """Undo a claim when no container was created; never infer from npu-smi."""
    alloc = validated_path(args.alloc); claim = load(args.claim)
    if claim.get("schema") != "r3-resource-claim-v1" or claim.get("chip") != args.chip or claim.get("run") != args.run:
        raise RuntimeError("claim identity differs")
    if 'successor_precondition' in claim:
        raise RuntimeError('automatic abort disabled for guarded claim; explicit repair required')
    if docker_inspect(args.container) is not None:
        raise RuntimeError("container exists; use guarded release")
    if live_chip_conflict(args.chip, args.container):
        raise RuntimeError("live container still owns device")
    with locked(alloc):
        before_raw = read_bytes(alloc); before = json.loads(before_raw); validate_doc(before)
        owners = [e for e in before["allocation"] if e.get("chip") == args.chip and e.get("run") == args.run]
        if len(owners) != 1 or any(e.get("chip") == args.chip for e in before["free"]):
            raise RuntimeError("claim ownership differs")
        after = dict(before)
        after["allocation"] = [e for e in before["allocation"] if e is not owners[0]]
        after["free"] = sorted(before["free"] + [{"chip": args.chip, "previous_run": args.run, "release_evidence": str(Path(args.proof).resolve()), "released_utc": utc()}], key=lambda e: e["chip"])
        after["updated_utc"], after["updated_by"] = utc(), "r3_resource_adapter abort_claim"
        intent = {"schema":"r3-resource-abort-intent-v1","run":args.run,"chip":args.chip,"allocation_before":before,"allocation_before_sha256":sha_bytes(before_raw),"allocation_after":after,"allocation_after_sha256":sha_bytes((json.dumps(after,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()),"proof":str(Path(args.proof).resolve())}
        write_atomic(Path(args.proof).with_suffix(Path(args.proof).suffix+".intent"), intent)
        after_hash = write_atomic(alloc, after)
        proof={"schema":"r3-resource-abort-v1","run":args.run,"chip":args.chip,"scientific_acceptance":False,"allocation_before_sha256":sha_bytes(before_raw),"allocation_after_sha256":after_hash,"allocation_before":before,"allocation_after":after,"aborted_utc":utc()}
    write_atomic(args.proof, proof)
    try: Path(args.proof).with_suffix(Path(args.proof).suffix+".intent").unlink()
    except FileNotFoundError: pass
    print(json.dumps({"status":"CLAIM_ABORTED","chip":args.chip,"run":args.run,"proof":args.proof}))

def docker_inspect(name):
    p = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, check=False, timeout=30)
    if p.returncode:
        # Docker CLI emits [] on stdout for an absent object. Only its exact
        # one-object daemon response proves absence; transport errors never do.
        absent = {f'Error: No such object: {name}', f'Error response from daemon: No such container: {name}'}
        if p.returncode == 1 and p.stderr.strip().lower() in {x.lower() for x in absent} and p.stdout.strip() in ('', '[]'):
            return None
        raise RuntimeError('Docker observation uncertain: ' + p.stderr[:200])
    rows = json.loads(p.stdout)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError('Docker successful observation malformed/empty')
    value = rows[0]
    if not isinstance(value.get('Id'), str) or not value['Id'] or not isinstance(value.get('State'), dict):
        raise RuntimeError('Docker container observation incomplete')
    if value.get('Name') != '/' + name and not value['Id'].startswith(name):
        raise RuntimeError('Docker observation requested identity differs')
    return value


def require(ok, message):
    if not ok: raise RuntimeError(message)


def image_inspect(image_id):
    p = subprocess.run(['docker', 'image', 'inspect', image_id], capture_output=True, text=True, check=True, timeout=30)
    rows = json.loads(p.stdout)
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('Id') != image_id:
        raise RuntimeError('Docker image observation differs')
    return rows[0]


def environment_map(items):
    require(isinstance(items, list), 'container environment list required')
    result = {}
    for item in items:
        require(isinstance(item, str) and '=' in item, 'invalid container environment')
        key, value = item.split('=', 1)
        require(key not in result, 'duplicate container environment key')
        result[key] = value
    return result


def daemon_policy():
    """Observe defaults from the actual daemon, not from the candidate container."""
    value=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True))
    require(value.get('DefaultRuntime') and value.get('CgroupVersion') in ('1','2'), 'unknown Docker defaults')
    return {'runtime':value['DefaultRuntime'],
            'cgroupns':'private' if value['CgroupVersion']=='2' else 'host'}


def verify_effective_policy(observed, image, environment, *, daemon=None):
    """Shared CPU/NPU execution policy; command, mounts/devices checked by caller."""
    require(image is not None and observed.get('Image')==image.get('Id'), 'pinned image configuration required')
    daemon=daemon_policy() if daemon is None else daemon
    cfg=observed.get('Config',{});host=observed.get('HostConfig',{});defaults=image.get('Config',{})
    expected=environment_map(defaults.get('Env') or []);expected.update(environment)
    require(environment_map(cfg.get('Env'))==expected,'retained environment differs')
    for key in ('User','WorkingDir','StopSignal'):
        require((cfg.get(key) or '')==(defaults.get(key) or ''),'retained image default differs: '+key)
    require(cfg.get('Healthcheck')==defaults.get('Healthcheck'),'retained healthcheck differs')
    for key in ('Tty','OpenStdin','StdinOnce'):
        require(not cfg.get(key),'retained interactive configuration: '+key)
    for key in ('CapAdd','CapDrop','SecurityOpt','DeviceRequests','DeviceCgroupRules','GroupAdd',
                'Binds','VolumesFrom','Links','ExtraHosts','Dns','DnsSearch','DnsOptions','Sysctls','Tmpfs',
                'PortBindings','StorageOpt','Annotations','LxcConf','VolumeDriver','CgroupParent',
                'Cgroup','UsernsMode','Isolation','ContainerIDFile','CpusetCpus','CpusetMems',
                'BlkioWeightDevice','BlkioDeviceReadBps','BlkioDeviceWriteBps','BlkioDeviceReadIOps','BlkioDeviceWriteIOps'):
        require(not host.get(key),'retained extra configuration: '+key)
    for key in ('Memory','MemoryReservation','MemorySwap','NanoCpus','CpuShares','CpuPeriod','CpuQuota',
                'CpuRealtimePeriod','CpuRealtimeRuntime','CpuCount','CpuPercent','BlkioWeight',
                'IOMaximumIOps','IOMaximumBandwidth','OomScoreAdj'):
        require(host.get(key,0)==0,'retained resource override: '+key)
    for key in ('MemorySwappiness','PidsLimit'):
        require(host.get(key) is None,'retained resource override: '+key)
    for key in ('Init','OomKillDisable','ReadonlyRootfs','PublishAllPorts','Privileged','AutoRemove'):
        require(host.get(key) in (None,False),'retained host flag differs: '+key)
    require(host.get('Runtime')==daemon['runtime'],'retained runtime differs')
    require(host.get('CgroupnsMode')==daemon['cgroupns'],'retained namespace differs: CgroupnsMode')
    require(host.get('NetworkMode')=='none','retained network differs')
    for key in ('PidMode','UTSMode'):
        require(not host.get(key),'retained namespace differs: '+key)
    require(host.get('IpcMode') in ('private',''),'retained IPC differs')
    restart=host.get('RestartPolicy') or {}
    require(restart.get('Name','no') in ('no','') and restart.get('MaximumRetryCount',0)==0,
            'retained restart policy differs')


def live_chip_conflict(chip, own_name):
    # Batch the *complete* inventory rather than dropping created/restarting
    # containers or relying on a status filter that could race a restart. Keep
    # the retained target's separate generation checks in release().
    p = subprocess.run(["docker", "ps", "-aq", "--no-trunc"], capture_output=True,
                       text=True, check=False, timeout=30)
    if p.returncode: raise RuntimeError("docker ps failed")
    ids = p.stdout.split()
    if len(ids) != len(set(ids)):
        raise RuntimeError('duplicate container in device inventory')
    for start in range(0, len(ids), 128):
        batch = ids[start:start + 128]
        observed = subprocess.run(["docker", "inspect", *batch], capture_output=True,
                                  text=True, check=False, timeout=30)
        if observed.returncode:
            raise RuntimeError('Docker inventory observation uncertain: ' + observed.stderr[:200])
        rows = json.loads(observed.stdout)
        if (not isinstance(rows, list) or len(rows) != len(batch)
                or not all(isinstance(d, dict) for d in rows)
                or sorted(d.get('Id', '') for d in rows) != sorted(batch)):
            raise RuntimeError('Docker inventory identities differ; retry observation')
        for d in rows:
            state, host = d.get('State'), d.get('HostConfig')
            if not isinstance(state, dict) or not isinstance(host, dict):
                raise RuntimeError('incomplete Docker inventory observation')
            status = state.get('Status')
            if status not in ('created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead'):
                raise RuntimeError('unknown Docker inventory state')
            devices = host.get('Devices')
            if devices is not None and (not isinstance(devices, list) or not all(
                    isinstance(x, dict) and isinstance(x.get('PathOnHost'), str) for x in devices)):
                raise RuntimeError('invalid Docker inventory device bindings')
            if (own_name and d.get("Name", "").lstrip("/") == own_name) or status in ("exited", "dead"):
                continue
            if any(x['PathOnHost'] == f"/dev/davinci{chip}" for x in devices or []):
                return True
    return False

def release(args):
    alloc = validated_path(args.alloc)
    # Bind the parsed generation and its evidence hash to the same snapshot.
    # A later replacement is rejected by revalidate_release below.
    claim_raw = read_bytes(args.claim)
    claim = json.loads(claim_raw)
    claim_pin = sha_bytes(claim_raw)
    if claim.get("schema") != "r3-resource-claim-v1" or claim.get("chip") != args.chip or claim.get("run") != args.run:
        raise RuntimeError("claim identity differs")
    container = docker_inspect(args.container)
    expected_id = getattr(args, 'container_id', None)
    if expected_id is not None and (container is None or container.get('Id') != expected_id):
        raise RuntimeError('release container generation differs')
    if container is None or container.get("State", {}).get("Status") not in ("exited", "dead"):
        raise RuntimeError("retained container has not exited")
    if container.get("HostConfig", {}).get("AutoRemove"): raise RuntimeError("auto-remove container")
    # Release never exempts a live holder by name: the same name may now refer
    # to a replacement generation. Revalidate under the allocation lock at the
    # commit boundary as well. All cooperating allocation writers use this lock.
    def revalidate_release():
        if sha_bytes(read_bytes(args.claim)) != claim_pin:
            raise RuntimeError('release claim changed')
        if live_chip_conflict(args.chip, None):
            raise RuntimeError("live container still owns device")
        current = docker_inspect(args.container)
        if current is None or current.get('Id') != container['Id']:
            raise RuntimeError('release container generation differs')
        if current.get('State', {}).get('Status') not in ('exited', 'dead') or current.get('HostConfig', {}).get('AutoRemove'):
            raise RuntimeError('retained container has not exited')
        if current['State'].get('ExitCode') != container['State'].get('ExitCode'):
            raise RuntimeError('release container exit differs')
    revalidate_release()
    intent_path = Path(args.proof).with_suffix(Path(args.proof).suffix + ".intent")
    with locked(alloc):
        before_raw = read_bytes(alloc); before = json.loads(before_raw); validate_doc(before)
        if 'successor_precondition' in claim:
            if intent_path.exists() or Path(args.proof).exists():
                raise RuntimeError('guarded release already attempted; explicit repair required')
            owners = [x for x in before['allocation'] if x['chip'] == args.chip]
            if owners != [claim['entry']] or any(x['chip'] == args.chip for x in before['free']):
                raise RuntimeError('release claim generation differs')
        revalidate_release()
        existing = read_json_if(args.proof)
        if existing is not None:
            if existing.get("schema") != "r3-resource-release-v1" or existing.get("run") != args.run or existing.get("chip") != args.chip:
                raise RuntimeError("release proof identity differs")
            if 'successor_precondition' in claim and existing.get('claim_sha256') != claim_pin:
                raise RuntimeError('release proof claim generation differs')
            if expected_id is not None and existing.get('container_id') != expected_id:
                raise RuntimeError('release proof container generation differs')
            print(json.dumps({"status": "ALREADY_RELEASED", "chip": args.chip, "run": args.run, "proof": args.proof}))
            return
        intent = read_json_if(intent_path)
        if intent is not None:
            if intent.get("schema") != "r3-resource-release-intent-v1" or intent.get("run") != args.run or intent.get("chip") != args.chip:
                raise RuntimeError("release intent identity differs")
            if expected_id is not None and intent.get('container_id') != expected_id:
                raise RuntimeError('release intent container generation differs')
            if 'successor_precondition' in claim and intent.get('claim_sha256') != claim_pin:
                raise RuntimeError('release intent claim generation differs')
            current_hash = sha_bytes(read_bytes(alloc))
            if current_hash == intent.get("allocation_before_sha256"):
                after = intent["allocation_after"]
                revalidate_release()
                after_hash = write_atomic(alloc, after)
                before = intent["allocation_before"]
                before_raw = json.dumps(before, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
            elif current_hash == intent.get("allocation_after_sha256"):
                after = intent["allocation_after"]
                after_hash = intent["allocation_after_sha256"]
                before = intent["allocation_before"]
                before_raw = json.dumps(before, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
            else:
                raise RuntimeError("release intent exists but allocation is neither before nor after")
        else:
            owners = [e for e in before["allocation"] if e.get("chip") == args.chip and e.get("run") == args.run]
            if len(owners) != 1 or any(e.get("chip") == args.chip for e in before["free"]): raise RuntimeError("ownership differs")
            after = dict(before); after["allocation"] = [e for e in before["allocation"] if e is not owners[0]]
            after["free"] = sorted(before["free"] + [{"chip": args.chip, "previous_run": args.run,
                "release_evidence": str(Path(args.proof).resolve()), "released_utc": utc()}], key=lambda e: e["chip"])
            after["updated_utc"], after["updated_by"] = utc(), "r3_resource_adapter release"
            intent = {"schema": "r3-resource-release-intent-v1", "run": args.run, "chip": args.chip,
                      "container_id": container["Id"], "claim_sha256": claim_pin,
                      "allocation_before": before, "allocation_before_sha256": sha_bytes(before_raw),
                      "allocation_after": after, "allocation_after_sha256": sha_bytes((json.dumps(after, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()),
                      "proof": str(Path(args.proof).resolve())}
            write_atomic(intent_path, intent)
            revalidate_release()
            after_hash = write_atomic(alloc, after)
        proof = {"schema": "r3-resource-release-v1", "run": args.run, "chip": args.chip,
                 "container": args.container, "container_id": container["Id"], "claim_sha256": claim_pin,
                 "container_started_at": container["State"].get("StartedAt"),
                 "container_finished_at": container["State"].get("FinishedAt"),
                 "exit_code": container["State"].get("ExitCode"), "scientific_acceptance": False,
                 "allocation_before_sha256": sha_bytes(before_raw), "allocation_after_sha256": after_hash,
                 "allocation_before": before, "allocation_after": after, "released_utc": utc()}
        if 'successor_precondition' in claim:
            write_atomic(args.proof, proof)
            intent_path.unlink()
            print(json.dumps({"status": "OPERATIONALLY_RELEASED", "chip": args.chip, "run": args.run, "proof": args.proof}))
            return
    write_atomic(args.proof, proof)
    try: intent_path.unlink()
    except FileNotFoundError: pass
    print(json.dumps({"status": "OPERATIONALLY_RELEASED", "chip": args.chip, "run": args.run,
                      "exit_code": proof["exit_code"], "proof": args.proof}))


def reclaim_legacy(args):
    """Release a legacy owner without inventing a historical claim receipt.

    Pins the exact owner entry, retained generation and successful terminal marker.
    The marker's directory must appear in the container's command arguments.
    """
    alloc = validated_path(args.alloc)
    container = docker_inspect(args.container)
    if container is None or container['Id'] != args.container_id:
        raise RuntimeError('legacy container generation differs')
    if container['State']['Status'] != 'exited' or container['State']['ExitCode'] != 0:
        raise RuntimeError('legacy container not successfully exited')
    if container['HostConfig'].get('AutoRemove') or not any(
            x.get('PathOnHost') == f'/dev/davinci{args.chip}' for x in container['HostConfig'].get('Devices') or []):
        raise RuntimeError('legacy device binding differs')
    marker = validated_path(args.marker)
    marker_raw = read_bytes(marker)
    if sha_bytes(marker_raw) != args.marker_sha256 or not marker_raw.decode().startswith('rc=0 '):
        raise RuntimeError('legacy terminal marker differs')
    if not any(arg == str(marker.parent) or arg.startswith(str(marker.parent) + '/')
               for arg in container['Config'].get('Cmd', [])):
        raise RuntimeError('marker not bound to container command')
    if live_chip_conflict(args.chip, args.container):
        raise RuntimeError('another nonterminal container maps chip')
    with locked(alloc):
        before = load(alloc); validate_doc(before)
        entries = [x for x in before['allocation'] if x['chip'] == args.chip]
        if len(entries) != 1 or sha_bytes(json.dumps(entries[0], sort_keys=True).encode()) != args.entry_sha256:
            raise RuntimeError('legacy owner entry changed')
        proof_path = Path(args.proof)
        if proof_path.exists():
            raise RuntimeError('legacy reclaim evidence already exists; reconcile before retry')
        after = dict(before)
        after['allocation'] = [x for x in before['allocation'] if x['chip'] != args.chip]
        after['free'] = sorted(before['free'] + [dict(chip=args.chip, previous_run=entries[0]['run'],
            released_utc=utc(), release_evidence=str(proof_path.resolve()))], key=lambda x:x['chip'])
        after['updated_by'], after['updated_utc'] = 'r3_resource_adapter legacy reclaim', utc()
        proof = dict(schema='r3-legacy-reclaim-v1', scientific_acceptance=False, chip=args.chip,
                     container=args.container, container_id=container['Id'],
                     marker=str(marker), marker_sha256=args.marker_sha256,
                     allocation_before=before, allocation_after=after,
                     note='Operational resource release only; historical pending claims are not approved.')
        # Durable before/after evidence precedes mutation; interruption is reconciled from these snapshots.
        write_atomic(proof_path, proof)
        write_atomic(alloc, after)
    print(json.dumps({'status':'LEGACY_OPERATIONALLY_RELEASED','chip':args.chip,'proof':str(proof_path)}))

def main(argv=None):
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="op", required=True)
    c = sub.add_parser("claim"); c.add_argument("--alloc", default=ALLOC_DEFAULT); c.add_argument("--run", required=True); c.add_argument("--chip", type=int, required=True); c.add_argument("--owner", required=True); c.add_argument("--purpose", required=True); c.add_argument("--proof", required=True)
    c.add_argument("--plan"); c.add_argument("--plan-sha256"); c.add_argument("--precondition-sha256")
    a = sub.add_parser("abort"); a.add_argument("--alloc", default=ALLOC_DEFAULT); a.add_argument("--run", required=True); a.add_argument("--chip", type=int, required=True); a.add_argument("--container", required=True); a.add_argument("--claim", required=True); a.add_argument("--proof", required=True)
    r = sub.add_parser("release"); r.add_argument("--alloc", default=ALLOC_DEFAULT); r.add_argument("--run", required=True); r.add_argument("--chip", type=int, required=True); r.add_argument("--container", required=True); r.add_argument("--container-id"); r.add_argument("--claim", required=True); r.add_argument("--proof", required=True)
    l = sub.add_parser('reclaim-legacy')
    for name in ('alloc', 'container', 'container-id', 'marker', 'marker-sha256', 'entry-sha256', 'proof'):
        l.add_argument('--' + name, required=True)
    l.add_argument('--chip', type=int, required=True)
    a = p.parse_args(argv)
    return {'claim':claim, 'abort':abort_claim, 'release':release, 'reclaim-legacy':reclaim_legacy}[a.op](a)

if __name__ == "__main__": raise SystemExit(main())
